import unittest
from types import SimpleNamespace, MethodType
from unittest.mock import Mock, patch

from backend.gamepad_input import GamepadInput


BUTTONS = dict(CONTROLLER_BUTTON_DPAD_UP=11, CONTROLLER_BUTTON_DPAD_DOWN=12,
               CONTROLLER_BUTTON_DPAD_LEFT=13, CONTROLLER_BUTTON_DPAD_RIGHT=14,
               CONTROLLER_BUTTON_A=0, CONTROLLER_BUTTON_B=1)


def reader_for(device=None):
    reader = SimpleNamespace(device=device, devices=[], selected_id=-1, enabled=True,
        unmapped=False,
        navigation_enabled=True, _next_scan=float('inf'), api=Mock(),
        pygame=SimpleNamespace(event=Mock(), joystick=Mock(), error=RuntimeError,
            CONTROLLER_AXIS_TRIGGERRIGHT=5, CONTROLLER_AXIS_TRIGGERLEFT=4, **BUTTONS),
        stateChanged=Mock(), devicesChanged=Mock(), navigation=Mock(), batteryChanged=Mock(),
        battery_level='unknown', poll_battery=Mock(), trigger=GamepadInput.trigger)
    for method in ('reset_navigation', 'release_device', 'poll_navigation', 'scan'):
        setattr(reader, method, MethodType(getattr(GamepadInput, method), reader))
    reader.reset_navigation()
    return reader


class GamepadInputTests(unittest.TestCase):
    def test_trigger_range_and_deadzone(self):
        self.assertEqual(GamepadInput.trigger(-32768), 0)
        self.assertEqual(GamepadInput.trigger(300), 0)
        self.assertAlmostEqual(GamepadInput.trigger(16384), .5, places=4)
        self.assertEqual(GamepadInput.trigger(32768), 1)

    def test_mapped_device_and_disconnect(self):
        reader = reader_for()
        reader.devices = [dict(id=42, index=0, name='Test controller')]
        reader.scan = lambda: setattr(reader, 'devices', [])
        reader.poll_navigation = Mock()
        reader.api.get_count.return_value = 1
        device = reader.api.Controller.return_value
        device.name = 'Test controller'
        device.get_axis.side_effect = [32767, 16384]
        GamepadInput.poll(reader)
        state = reader.stateChanged.emit.call_args.args
        self.assertEqual(state[0:2], ('Test controller', 1))
        self.assertAlmostEqual(state[2], .5, places=4)
        device.attached.return_value = False
        reader.api.get_count.return_value = 0
        GamepadInput.poll(reader)
        device.quit.assert_called_once()
        device.stop_rumble.assert_called_once()
        reader.stateChanged.emit.assert_called_with('', 0, 0, '')

    def test_manual_disconnect_does_not_auto_reopen_until_enabled(self):
        reader = reader_for(Mock())
        reader.poll = Mock()
        device = reader.device
        GamepadInput.setEnabled(reader, False)
        device.quit.assert_called_once()
        self.assertFalse(reader.enabled)
        self.assertIsNone(reader.device)
        GamepadInput.setEnabled(reader, True)
        self.assertTrue(reader.enabled)
        self.assertEqual(reader.selected_id, -1)
        self.assertEqual(reader._next_scan, 0)

    def test_controller_selection_clears_old_input(self):
        reader = reader_for(Mock())
        reader.poll = Mock()
        device = reader.device
        GamepadInput.select(reader, 17)
        device.quit.assert_called_once()
        self.assertTrue(reader.enabled)
        self.assertEqual(reader.selected_id, 17)
        self.assertIsNone(reader._navigation_down)
        reader.poll.assert_called_once()

    def test_live_scan_adds_and_removes_controllers(self):
        reader = SimpleNamespace(api=Mock(), pygame=Mock(), devices=[], devicesChanged=Mock(),
                                 device=None, unmapped=False)
        reader.api.get_count.return_value = 1
        reader.api.is_controller.return_value = True
        reader.api.name_forindex.return_value = 'Test pad'
        joystick = reader.pygame.joystick.Joystick.return_value
        joystick.get_instance_id.return_value = 12
        GamepadInput.scan(reader)
        self.assertEqual(reader.devices, [dict(id=12, index=0, name='Test pad')])
        joystick.quit.assert_called_once()
        reader.api.get_count.return_value = 0
        GamepadInput.scan(reader)
        self.assertEqual(reader.devices, [])
        self.assertEqual(reader.devicesChanged.emit.call_count, 2)

    def test_unmapped_joystick_uses_hat_and_a_b_buttons(self):
        reader = reader_for()
        reader.api.get_count.return_value = 1
        reader.api.is_controller.return_value = False
        joystick = reader.pygame.joystick.Joystick.return_value
        joystick.get_instance_id.return_value = 42
        joystick.get_name.return_value = 'Generic pad'
        joystick.get_numhats.return_value = 1
        joystick.get_numbuttons.return_value = 2
        joystick.get_hat.return_value = (0, 0)
        pressed = set()
        joystick.get_button.side_effect = lambda button: button in pressed
        GamepadInput.scan(reader)
        self.assertEqual(reader.devices[0]['name'], 'Generic pad')
        reader._next_scan = float('inf')
        GamepadInput.poll(reader)
        self.assertEqual(reader.stateChanged.emit.call_args.args,
                         ('Generic pad', 0, 0, 'SDL mapping unavailable: D-pad/A/B only; triggers disabled.'))
        reader.reset_navigation()
        def tick(seconds):
            with patch('backend.gamepad_input.time.monotonic', return_value=seconds):
                reader.poll_navigation()
        tick(0); tick(.1)
        joystick.get_hat.return_value = (0, 1)
        tick(.2); tick(.26)
        reader.navigation.emit.assert_called_with('up')
        joystick.get_hat.return_value = (0, 0)
        tick(.3); tick(.36)
        pressed.add(0)
        tick(.4); tick(.46)
        reader.navigation.emit.assert_called_with('confirm')
        pressed.clear(); tick(.5); tick(.56)
        pressed.add(1); tick(.6); tick(.66)
        reader.navigation.emit.assert_called_with('back')

    def make_navigation(self):
        reader = reader_for(Mock())
        held = set()
        reader.device.get_button.side_effect = lambda value: value in held
        def tick(seconds):
            with patch('backend.gamepad_input.time.monotonic', return_value=seconds):
                reader.poll_navigation()
        return reader, held, tick

    def test_debounce_and_no_held_repeat(self):
        reader, held, tick = self.make_navigation()
        tick(0); tick(.1)
        held.add(12); tick(.2); tick(.26)
        reader.navigation.emit.assert_called_once_with('down')
        tick(.8); tick(10)
        self.assertEqual(reader.navigation.emit.call_count, 1)
        held.clear(); tick(10.1); tick(10.16)
        held.add(0); tick(10.2); tick(10.26)
        reader.navigation.emit.assert_called_with('confirm')
        self.assertEqual(reader.navigation.emit.call_count, 2)
        held.clear(); tick(10.3); tick(10.36)
        held.add(1); tick(10.4); tick(10.46)
        reader.navigation.emit.assert_called_with('back')

    def test_held_on_connection_and_focus_requires_release(self):
        reader, held, tick = self.make_navigation()
        held.add(14); tick(0); tick(2); tick(5)
        reader.navigation.emit.assert_not_called()
        held.clear(); tick(5.1); tick(5.2)
        held.add(14); tick(5.3); tick(5.4)
        reader.navigation.emit.assert_called_once_with('right')
        reader.navigation_enabled = False; tick(6)
        reader.navigation_enabled = True; tick(7); tick(9)
        self.assertEqual(reader.navigation.emit.call_count, 1)

    def test_short_glitches_and_conflicting_buttons_are_ignored(self):
        reader, held, tick = self.make_navigation()
        tick(0); tick(.1)
        held.add(11); tick(.2)
        held.clear(); tick(.22); tick(.3)
        reader.navigation.emit.assert_not_called()
        held.update((11, 14)); tick(.4); tick(.5)
        held.remove(11); tick(.6); tick(2)
        reader.navigation.emit.assert_not_called()
