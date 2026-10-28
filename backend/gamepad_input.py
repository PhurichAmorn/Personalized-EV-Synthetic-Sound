import logging
import os
import time

from PySide6.QtCore import QObject, Signal, Slot, QTimer


class GamepadInput(QObject):
    """Poll mapped gamepads and basic navigation on unmapped joysticks."""
    stateChanged = Signal(str, float, float, str)
    devicesChanged = Signal()
    navigation = Signal(str)
    batteryChanged = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.device = None
        self.unmapped = False
        self.devices = []
        self.enabled = True
        self.navigation_enabled = True
        self.selected_id = -1
        self._next_scan = 0.0
        self.battery_level = 'unknown'
        self._next_battery = 0.0
        self._last_raw_buttons = None
        self.reset_navigation()
        self.timer = QTimer(self)
        self.timer.setInterval(20)
        self.timer.timeout.connect(self.poll)
        os.environ.setdefault('PYGAME_HIDE_SUPPORT_PROMPT', '1')
        os.environ.setdefault('SDL_VIDEODRIVER', 'dummy')
        os.environ.setdefault('SDL_JOYSTICK_ALLOW_BACKGROUND_EVENTS', '1')
        try:
            import pygame
            from pygame._sdl2 import controller
            self.pygame, self.api = pygame, controller
            pygame.display.init()
            pygame.joystick.init()
            controller.init()
            self.timer.start()
        except (ImportError, RuntimeError) as exc:
            self.stateChanged.emit('', 0, 0, str(exc))
            self.error = str(exc)

    @staticmethod
    def trigger(value):
        level = min(1.0, max(0.0, value / 32767.0))
        return 0.0 if level < .02 else level

    def reset_navigation(self):
        self._navigation_down = None
        self._pending_navigation = None
        self._pending_since = 0.0
        self._neutral_since = None

    def release_device(self):
        if self.device is not None:
            try:
                self.device.stop_rumble()
            except Exception:
                pass  # Unsupported or disconnected haptics must not block input cleanup.
            self.device.quit()
            self.device = None
        self.unmapped = False
        self.reset_navigation()
        self._last_raw_buttons = None
        self._next_battery = 0.0
        if self.battery_level != 'unknown':
            self.battery_level = 'unknown'
            self.batteryChanged.emit()

    def poll(self):
        if hasattr(self, 'error'):
            self.stateChanged.emit('', 0, 0, self.error)
            return
        try:
            self.pygame.event.pump()
            self.pygame.event.clear()
            if self.device is not None and not (self.device.get_init() if self.unmapped else self.device.attached()):
                self.release_device()
                self.selected_id = -1
                self._next_scan = 0
                self.stateChanged.emit('', 0, 0, '')
            if time.monotonic() >= self._next_scan:
                self.scan()
            if self.enabled and self.device is None:
                for entry in self.devices:
                    if self.selected_id == -1 or self.selected_id == entry['id']:
                        self.unmapped = entry.get('unmapped', False)
                        self.device = (self.pygame.joystick.Joystick(entry['index']) if self.unmapped
                                       else self.api.Controller(entry['index']))
                        self._last_raw_buttons = None
                        self.reset_navigation()
                        break
            if self.device is None:
                self.reset_navigation()
                self.stateChanged.emit('', 0, 0, '')
            else:
                self.stateChanged.emit(self.device.get_name() if self.unmapped else self.device.name,
                    0 if self.unmapped else self.trigger(self.device.get_axis(self.pygame.CONTROLLER_AXIS_TRIGGERRIGHT)),
                    0 if self.unmapped else self.trigger(self.device.get_axis(self.pygame.CONTROLLER_AXIS_TRIGGERLEFT)),
                    'SDL mapping unavailable: D-pad/A/B only; triggers disabled.' if self.unmapped else '')
                self.poll_navigation()
                self.poll_battery()
        except (RuntimeError, self.pygame.error) as exc:
            self.release_device()
            self.stateChanged.emit('', 0, 0, str(exc))

    def poll_battery(self):
        now = time.monotonic()
        if now < self._next_battery:
            return
        try:
            level = (self.device if self.unmapped else self.device.as_joystick()).get_power_level()
            if level not in ('empty', 'low', 'medium', 'full', 'wired'):
                level = 'unknown'
        except Exception:
            level = 'unknown'  # Battery support must not interrupt controller input.
        self._next_battery = now + (1 if level == 'unknown' else 5)
        if level != self.battery_level:
            self.battery_level = level
            self.batteryChanged.emit()

    def poll_navigation(self):
        if not self.navigation_enabled:
            self.reset_navigation()
            return
        try:
            joystick = self.device if self.unmapped else self.device.as_joystick()
            raw_buttons = tuple(i for i in range(joystick.get_numbuttons())
                                 if joystick.get_button(i))
            if raw_buttons != self._last_raw_buttons:
                logging.getLogger('Input').info('Controller raw buttons pressed: %s', raw_buttons)
                self._last_raw_buttons = raw_buttons
        except Exception:
            pass  # Diagnostic button mapping must not interrupt normal input.
        if self.unmapped:
            x, y = self.device.get_hat(0) if self.device.get_numhats() else (0, 0)
            down = ({'right'} if x > 0 else {'left'} if x < 0 else set())
            down |= ({'up'} if y > 0 else {'down'} if y < 0 else set())
            down |= {name for button, name in ((0, 'confirm'), (1, 'back'))
                     if button < self.device.get_numbuttons() and self.device.get_button(button)}
        else:
            buttons = {
                'up': self.pygame.CONTROLLER_BUTTON_DPAD_UP,
                'down': self.pygame.CONTROLLER_BUTTON_DPAD_DOWN,
                'left': self.pygame.CONTROLLER_BUTTON_DPAD_LEFT,
                'right': self.pygame.CONTROLLER_BUTTON_DPAD_RIGHT,
                'confirm': self.pygame.CONTROLLER_BUTTON_A,
                'back': self.pygame.CONTROLLER_BUTTON_B,
            }
            down = {name for name, button in buttons.items() if self.device.get_button(button)}
        now = time.monotonic()
        if len(down) > 1:
            self.reset_navigation()
            return
        # Require neutral after connecting/focus changes; never repeat a held button.
        if self._navigation_down is None:
            if down:
                self._neutral_since = None
            elif self._neutral_since is None:
                self._neutral_since = now
            elif now - self._neutral_since >= .08:
                self._navigation_down = set()
            return
        if down != self._pending_navigation:
            self._pending_navigation = down
            self._pending_since = now
            return
        if now - self._pending_since < .04:
            return
        for name in ('up', 'down', 'left', 'right', 'confirm', 'back'):
            if name in down and name not in self._navigation_down:
                logging.getLogger('Input').info('Controller navigation: %s', name)
                self.navigation.emit(name)
        self._navigation_down = down

    def scan(self):
        devices = []
        for index in range(self.api.get_count()):
            joystick = self.pygame.joystick.Joystick(index)
            mapped = self.api.is_controller(index)
            devices.append(dict(id=joystick.get_instance_id(), index=index,
                                name=self.api.name_forindex(index) if mapped else joystick.get_name(),
                                **({} if mapped else {'unmapped': True})))
            joystick.quit()
        if self.unmapped and self.device is not None and not any(
                entry['id'] == self.device.get_instance_id() for entry in devices):
            self.release_device()
            self.selected_id = -1
        self._next_scan = time.monotonic() + .5
        if devices != self.devices:
            self.devices = devices
            self.devicesChanged.emit()

    @Slot(int)
    def select(self, instance_id):
        self.release_device()
        self.selected_id = instance_id
        self.enabled = True
        self.stateChanged.emit('', 0, 0, '')
        self.devicesChanged.emit()
        self.poll()

    @Slot(bool)
    def setEnabled(self, enabled):
        self.reset_navigation()
        self.enabled = enabled
        if not enabled:
            self.release_device()
        else:
            self.selected_id = -1
            self._next_scan = 0
        self.stateChanged.emit('', 0, 0, '')
        self.devicesChanged.emit()
        self.poll()

    def close(self):
        self.timer.stop()
        self.release_device()
        if hasattr(self, 'api'):
            self.api.quit()
            self.pygame.display.quit()
