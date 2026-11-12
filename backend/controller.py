import math
import logging
import os
import time

from PySide6.QtCore import QObject, Property, Signal, Slot, QTimer, QEvent, Qt

from audio import DEBUG_THEMES, SOUND_RECIPES, SOUND_THEMES
from audio import SoundEngine
from simulation.vehicle_model import VehicleModel, SIMULATOR_PRESETS
from backend.beamng_telemetry import TorqueScaler


class SimulatorController(QObject):
    changed = Signal()  # Live vehicle telemetry only.
    vehicleChanged = Signal()
    sessionChanged = Signal()
    soundThemeChanged = Signal()
    audioErrorChanged = Signal()
    controllerChanged = Signal()
    controllerDevicesChanged = Signal()
    controllerBatteryChanged = Signal()
    inputChanged = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.car = VehicleModel.from_name('Compact EV')
        self.source_mode = 'Simulator'
        self.beamng_state = None
        self.beamng_received_at = 0.0
        self.beamng_acceleration = 0.0
        self.beamng_previous_sample = None
        self.beamng_error = ''
        self.beamng_torque = TorqueScaler()
        self.beamng_signed_load = None  # torque-based -1..+1 (None when the car has no motor device)
        self.beamng_stale_after = 0.5
        self.audio = SoundEngine()
        self.sound_theme = 'Deep'
        self.sound_recipe = {mode: next(iter(recipes)) for mode, recipes in SOUND_RECIPES.items()}
        self.keys_down = set()
        self.throttle = self.brake = 0.0
        self._last_display_inputs = (0.0, 0.0)
        self.gamepad_name = self.gamepad_error = ''
        self.gamepad = None
        self.gamepad_throttle = self.gamepad_brake = 0.0
        self.external_throttle = self.external_brake = 0.0
        self.gamepad_armed = False
        self.input_focused = True
        self.display_power = self.display_charge = 0.0
        self.audio_error = ''
        self.sound_starting = False
        self.source_audition = False
        self.timer = QTimer(self)
        self.timer.setInterval(20)
        self.timer.timeout.connect(self._tick)
        self._last_tick = None
        self.sweep_timer = QTimer(self)
        self.sweep_timer.setInterval(20)
        self.sweep_timer.timeout.connect(self._sweep_tick)
        self._sweep_elapsed = 0.0
        self._sweep_last_tick = None
        self.sweep_rpm = 1000.0
        self.sweep_throttle = 20.0
        from experiment.experiment_manager import ExperimentManager
        self._experiment = ExperimentManager(self, self)
        from experiment.live_search import LiveSearch
        self._search = LiveSearch(self, self)

    speed = Property(float, lambda self: self._telemetry_value('speed_m_s', self.car.speed / 3.6) * 3.6, notify=changed)
    rpm = Property(float, lambda self: self._telemetry_value('rpm', self.car.rpm), notify=changed)
    hasGears = Property(bool, lambda self: len(self.car.gear_ratios) > 1, notify=vehicleChanged)
    gear = Property(int, lambda self: self.car.current_gear, notify=changed)
    maxRpm = Property(float, lambda self: self.car.max_rpm, notify=vehicleChanged)
    power = Property(float, lambda self: max(0.0, self._telemetry_load(self.display_power)), notify=changed)
    charge = Property(float, lambda self: max(0.0, -self._telemetry_load(-self.display_charge)), notify=changed)
    regenActive = Property(bool, lambda self: self._regen_level() > (.02 if self.source_mode == 'BeamNG' else 0), notify=changed)
    sourceMode = Property(str, lambda self: self.source_mode, notify=changed)
    beamngConnected = Property(bool, lambda self: self.source_mode == 'BeamNG' and self._beamng_fresh(), notify=changed)
    beamngError = Property(str, lambda self: self.beamng_error, notify=changed)
    telemetryThrottle = Property(float, lambda self: self._telemetry_value('throttle', self.throttle), notify=changed)
    telemetryBrake = Property(float, lambda self: self._telemetry_value('brake', self.brake), notify=changed)
    telemetryRegen = Property(float, lambda self: self._regen_level(), notify=changed)
    running = Property(bool, lambda self: self.timer.isActive(), notify=sessionChanged)
    vehicleNames = Property('QStringList', lambda self: list(SIMULATOR_PRESETS), constant=True)
    speedGaugeMaximum = Property(float, lambda self: 300.0 if self.car.max_speed > 220 else 220.0, notify=vehicleChanged)
    selectedVehicle = Property(str, lambda self: self.car.name, notify=vehicleChanged)
    soundThemes = Property('QStringList', lambda self: list(SOUND_THEMES), constant=True)
    experiment = Property(QObject, lambda self: self._experiment, constant=True)
    search = Property(QObject, lambda self: self._search, constant=True)
    soundSweepActive = Property(bool, lambda self: self.sweep_timer.isActive(), notify=sessionChanged)
    selectedSoundTheme = Property(str, lambda self: self.sound_theme, notify=soundThemeChanged)
    error = Property(str, lambda self: self.audio_error, notify=audioErrorChanged)
    controllerConnected = Property(bool, lambda self: bool(self.gamepad_name), notify=controllerChanged)
    controllerName = Property(str, lambda self: self.gamepad_name, notify=controllerChanged)
    controllerBattery = Property(str, lambda self: self.gamepad.battery_level if self.gamepad else 'unknown', notify=controllerBatteryChanged)
    controllerError = Property(str, lambda self: self.gamepad_error, notify=controllerChanged)
    availableControllers = Property('QVariantList', lambda self: self.gamepad.devices if self.gamepad else [], notify=controllerDevicesChanged)
    controllerEnabled = Property(bool, lambda self: self.gamepad.enabled if self.gamepad else True, notify=controllerDevicesChanged)
    throttleInput = Property(float, lambda self: self.telemetryThrottle if self.source_mode == 'BeamNG' else max(self.gamepad_throttle, self.external_throttle, float(Qt.Key.Key_W in self.keys_down)), notify=inputChanged)
    brakeInput = Property(float, lambda self: self.telemetryBrake if self.source_mode == 'BeamNG' else max(self.gamepad_brake, self.external_brake, float(Qt.Key.Key_S in self.keys_down)), notify=inputChanged)

    def _telemetry_value(self, key, fallback):
        if self.source_mode == 'BeamNG' and self.beamng_state is not None:
            value = self.beamng_state.get(key)
            if value is not None:
                return value
        return fallback

    def controller_pedals(self):
        """What the player is pressing right now (controller triggers, W/S): never BeamNG's own pedal values."""
        return (max(self.gamepad_throttle, self.external_throttle, float(Qt.Key.Key_W in self.keys_down)),
                max(self.gamepad_brake, self.external_brake, float(Qt.Key.Key_S in self.keys_down)))

    def _record_beamng(self, now, state):
        """EV_SOUND_BEAMNG_LOG=<file>: append what BeamNG sent and what the app derived from it (10 rows/s)."""
        path = os.environ.get('EV_SOUND_BEAMNG_LOG')
        if not path or now - getattr(self, '_record_last', -1) < 0.1:
            return
        self._record_last = now
        fresh = not os.path.exists(path) or os.path.getsize(path) == 0
        value = lambda key: '' if state.get(key) is None else f'{state[key]:.4f}'
        with open(path, 'a') as handle:
            if fresh:
                handle.write('t,speed_kmh,throttle,brake,motor_torque,regen_field,regen_torque,motor_load_field,app_signed_load,app_regen,peak_drive,peak_regen\n')
            handle.write(f"{now:.2f},{state['speed_m_s'] * 3.6:.2f},{value('throttle')},{value('brake')},{value('motor_torque')},"
                         f"{value('regen')},{value('regen_torque')},{value('motor_load')},"
                         f"{'' if self.beamng_signed_load is None else f'{self.beamng_signed_load:.4f}'},{self._regen_level():.4f},"
                         f"{self.beamng_torque.peaks[0]:.1f},{self.beamng_torque.peaks[1]:.1f}\n")

    def _telemetry_load(self, fallback):
        """Signed motor load -1..+1: scaled real torque if the car reports it, else BeamNG's load field."""
        if self.source_mode == 'BeamNG' and self.beamng_state is not None:
            if self.beamng_signed_load is not None:
                return self.beamng_signed_load
            load = self.beamng_state.get('motor_load')
            if load is not None:
                return load
        return fallback

    def _regen_level(self):
        # The packet's "regen" is the regen-mode setting (stays at 100% while coasting), not actual braking torque.
        if self.source_mode == 'BeamNG' and self.beamng_signed_load is not None:
            return max(0.0, -self.beamng_signed_load)
        return self._telemetry_value('regen', self.car.regen)

    def _beamng_fresh(self):
        return self.beamng_state is not None and time.monotonic() - self.beamng_received_at <= self.beamng_stale_after

    def set_beamng_error(self, message):
        if message != self.beamng_error:
            self.beamng_error = message
            self.changed.emit()

    def receive_beamng_telemetry(self, state, received_at=None):
        now = time.monotonic() if received_at is None else received_at
        speed = state['speed_m_s']
        previous = self.beamng_previous_sample
        self.beamng_acceleration = ((speed - previous[0]) / max(now - previous[1], 1e-3)
                                    if previous and 0 < now - previous[1] <= self.beamng_stale_after else 0.0)
        self.beamng_previous_sample = (speed, now)
        torque = state.get('motor_torque')
        self.beamng_signed_load = (None if torque is None else
                                   self.beamng_torque.update(torque, now - self.beamng_received_at if self.beamng_state is not None else 0.0, speed))
        self.beamng_state = state
        self.beamng_received_at = now
        self._record_beamng(now, state)
        self.set_beamng_error('')
        self.changed.emit()

    @Slot(str)
    def selectSource(self, name):
        if name not in ('Simulator', 'BeamNG'):
            raise ValueError('Unknown telemetry source')
        if name != self.source_mode:
            self.source_mode = name
            self.beamng_previous_sample = None
            self.beamng_acceleration = 0.0
            self._pedals_changed()
            self.changed.emit()

    def _set_audio_error(self, message):
        if message != self.audio_error:
            if message:
                logging.getLogger('Audio').warning(message)
            elif self.audio_error:
                logging.getLogger('Audio').info('Audio output recovered.')
            self.audio_error = message
            self.audioErrorChanged.emit()

    @Slot(int)
    def selectController(self, instance_id):
        if self.gamepad is not None:
            self.gamepad.select(instance_id)

    @Slot(bool)
    def setControllerEnabled(self, enabled):
        if self.gamepad is not None:
            self.gamepad.setEnabled(enabled)

    @Slot(str)
    def selectComparisonSound(self, slot):
        if self.input_focused and self._search.active:
            self._search.choose(slot)

    @Property('QVariantMap', notify=changed)
    def powertrain(self):
        c = self.car
        v = c.speed / 3.6
        rpms = sorted({c.max_rpm * i / 100 for i in range(101)}
                      | {r for r, _ in c.power_taper})
        torque_curve = [[r, c.propulsion_torque_limit(r)] for r in rpms]
        power_curve = [[r, t * r * 2 * math.pi / 60 / 1000] for r, t in torque_curve]
        return dict(mapDescription=c.motor_map_description,
                    torqueCurve=torque_curve, powerCurve=power_curve,
                    torque=c.motor_torque_nm,
                    shaftPower=c.motor_torque_nm * c.rpm * 2 * math.pi / 60 / 1000,
                    wheelPower=(c.drive_force_n - c.regen_force_n) * v / 1000,
                    batteryPower=c.battery_power_w / 1000,
                    acceleration=c.acceleration_m_s2, soc=c.soc * 100,
                    throttle=self.throttle * 100, brake=self.brake * 100,
                    maxTorque=c.max_torque_nm, maxPower=c.max_power_kw,
                    maxRegenTorque=c.max_regen_torque_nm, maxRegenPower=c.max_regen_power_kw,
                    maxChargePower=c.max_charge_power_kw, maxDischargePower=c.max_discharge_power_kw,
                    maxSpeed=c.max_speed, maxBrakeG=c.max_brake_deceleration_g)

    @Property(str, notify=vehicleChanged)
    def specs(self):
        car = self.car
        return (f'{car.name}\n{"Dual motor · AWD" if car.drive_layout == "AWD" else "Rear motor · RWD"}\n'
                f'Peak power: {car.max_power_kw:.0f} kW\n'
                f'Peak torque: {car.max_torque_nm:.0f} Nm\n'
                + (f'Transmission: 2-speed rear · {car.gear_ratios[0]:g}:1 / {car.gear_ratios[1]:g}:1\n'
                   f'Shifts: {car.upshift_speed_kmh:g}/{car.downshift_speed_kmh:g} km/h, {car.shift_duration_s:g} s (estimated)\n'
                   if car.gear_ratios else 'Transmission: fixed reduction\n')
                + f'Battery: {car.battery_kwh:g} kWh {car.battery_type}\n'
                f'Rated range: {car.range_km} km ({car.range_standard})\n'
                f'Mass: {car.mass_kg:,.0f} kg\n'
                f'Top speed: {car.max_speed:.0f} km/h\n'
                f'Dry braking: {car.brake_calibration}\n'
                f'Motor map: {car.motor_map_description}\n'
                f'Simulation RPM ceiling: {car.max_rpm:,.0f} (estimated)\n'
                'Simulator values are approximate.')

    @Property(str, notify=changed)
    def parameters(self):
        if self.soundSweepActive:
            return f'DEBUG ORDER SWEEP  ·  {self.sweep_rpm:.0f} virtual RPM  ·  {self.sweep_throttle:.0f}% throttle  ·  4th order {4 * self.sweep_rpm / 60:.0f} Hz'
        profile = (SOUND_RECIPES[self.sound_theme][self.sound_recipe[self.sound_theme]]
                   if self.sound_theme in SOUND_RECIPES else DEBUG_THEMES[self.sound_theme])
        if profile.get('order_synthesis'):
            rpm = self.audio.order_synth.request[0]
            return f'{self.car.name.upper()}  ·  {rpm:.0f} sound RPM  ·  4th order {4 * rpm / 60:.0f} Hz  ·  throttle {self.throttle * 100:.0f}%'
        hz = (self.audio.electric_hz_target if profile.get('electric_mix')
              else self.audio.params[0])
        return (f'{self.car.name.upper()}  ·  {self.car.max_power_kw:.0f} kW / '
                f'{self.car.max_torque_nm:.0f} Nm  ·  {self.car.rpm:,.0f} / '
                f'{self.car.max_rpm:,.0f} RPM  ·  {hz:.0f} Hz')

    @Slot(str)
    def selectSoundTheme(self, name):
        if self._search.active or self.soundSweepActive or name not in SOUND_THEMES:
            return
        self._search.clearPlayback()
        logging.getLogger('Sound').info('Baseline selected: %s', name)
        self.sound_theme = name
        self._update_audio()
        self.soundThemeChanged.emit()
        self.changed.emit()

    @Slot(str)
    def cycleSoundRecipe(self, name):
        if self._search.active or self.soundSweepActive or name not in SOUND_RECIPES:
            return
        recipes = list(SOUND_RECIPES[name])
        current = recipes.index(self.sound_recipe[name])
        self.sound_recipe[name] = recipes[(current + 1) % len(recipes)]
        self.selectSoundTheme(name)

    @Slot(str)
    def selectVehicle(self, name):
        if self._search.active or self.running or self.soundSweepActive or name not in SIMULATOR_PRESETS:
            return
        self.car = VehicleModel.from_name(name)
        self._set_audio_error('')
        self.vehicleChanged.emit()
        self.changed.emit()

    @Slot()
    def toggle(self):
        if self._experiment.state in ('edit', 'rendering', 'compare', 'saved'):
            return
        if self.soundSweepActive:
            return
        if self.running:
            self.shutdown()
            if self.source_mode == 'Simulator':
                self.car = VehicleModel.from_name(self.car.name)
            self.display_power = self.display_charge = 0.0
        else:
            try:
                self.audio.start()
            except Exception as exc:
                self.audio.stop()
                self._set_audio_error(f'Audio unavailable: {exc}')
                return
            self._set_audio_error('')
            self._last_tick = time.perf_counter()
            self.timer.start()
            logging.getLogger('Vehicle').info('Powering on; pedals unlock after the startup animation.')
            self.sessionChanged.emit()
        self.changed.emit()

    def _pedals_changed(self):
        allowed = self.running and not self.sound_starting and self.input_focused
        if self.source_mode == 'BeamNG':
            self.throttle = self.brake = 0.0
        else:
            self.throttle = max(float(Qt.Key.Key_W in self.keys_down), self.external_throttle, self.gamepad_throttle if self.gamepad_armed else 0) if allowed else 0
            self.brake = max(float(Qt.Key.Key_S in self.keys_down), self.external_brake, self.gamepad_brake if self.gamepad_armed else 0) if allowed else 0
        self._update_audio()
        self._notify_inputs()

    def _notify_inputs(self):
        inputs = (self.throttleInput, self.brakeInput)
        if inputs != self._last_display_inputs:
            self._last_display_inputs = inputs
            self.inputChanged.emit()

    @Slot(str, float, float, str)
    def setGamepadState(self, name, throttle, brake, error):
        previous = (self.gamepad_name, self.gamepad_throttle, self.gamepad_brake, self.gamepad_error)
        if not all(math.isfinite(v) for v in (throttle, brake)):
            name, throttle, brake, error = '', 0, 0, 'Invalid controller input'
        self.gamepad_name, self.gamepad_error = name, error
        self.gamepad_throttle = min(1.0, max(0.0, throttle)) if name else 0
        self.gamepad_brake = min(1.0, max(0.0, brake)) if name else 0
        if not name or not self.running or self.sound_starting or not self.input_focused:
            self.gamepad_armed = False
        elif self.gamepad_throttle == 0 and self.gamepad_brake == 0:
            self.gamepad_armed = True
        current = (self.gamepad_name, self.gamepad_throttle, self.gamepad_brake, self.gamepad_error)
        if name != previous[0]:
            self.gamepad_armed = False
        if current != previous:
            self._pedals_changed()
        if error and error != previous[3]:
            logging.getLogger('Input').warning(error)
        if (name, error) != (previous[0], previous[3]):
            self.controllerChanged.emit()

    def _signed_motor_load(self):
        if self.source_mode == 'BeamNG':
            return max(-1.0, min(1.0, self._telemetry_load(0.0)))
        torque = self.car.motor_torque_nm
        limit = self.car.max_torque_nm if torque >= 0 else self.car.max_regen_torque_nm
        return max(-1.0, min(1.0, torque / max(limit, 1e-9)))

    def _update_audio(self):
        if self.soundSweepActive:
            return
        beamng = self.source_mode == 'BeamNG'
        load = self._signed_motor_load()
        speed = self.speed
        throttle = self.telemetryThrottle if beamng else self.throttle
        if (self.telemetryBrake if beamng else self.brake) > 0:
            throttle = 0.0  # Service brake overrides propulsion; throttle must not drive the sound.
        acceleration = self.beamng_acceleration if beamng else self.car.acceleration_m_s2
        state = 'off' if not self.running else ('starting' if self.sound_starting else 'ready')
        profile = self._search.profile or (
            SOUND_RECIPES[self.sound_theme][self.sound_recipe[self.sound_theme]]
            if self.sound_theme in SOUND_RECIPES else DEBUG_THEMES[self.sound_theme])
        self.audio.set_driving_parameters(speed, throttle * 100, load,
                                         acceleration, state,
                                         profile,
                                         master_volume=0.0 if self.source_audition else self._search.volume,
                                         sound_enabled=not beamng or self._beamng_fresh())

    @Slot(bool)
    def enableSoundDebug(self, enabled):
        self.audio.debug_enabled = enabled

    @Slot(result='QVariantMap')
    def soundDebug(self):
        import numpy as np
        samples = self.audio.debug_output.astype(float)
        window = np.hanning(len(samples))
        amplitudes = 2 * np.abs(np.fft.rfft(samples * window)) / window.sum()
        amplitudes[0] *= .5
        frequencies = np.fft.rfftfreq(len(samples), 1 / self.audio.sample_rate)
        visible = frequencies <= 2000
        levels = 20 * np.log10(np.maximum(amplitudes[visible], 1e-5))
        return dict(waveform=self.audio.debug_output[::4].tolist(),
                    duration_ms=len(samples) * 1000 / self.audio.sample_rate,
                    frequencies=frequencies[visible].tolist(), spectrum_db=levels.tolist())

    @Slot(bool)
    def setSoundStarting(self, starting):
        if self.sound_starting and not starting and self.running:
            logging.getLogger('Vehicle').info('READY — controller triggers or W/S can now drive.')
        self.sound_starting = starting
        if starting:
            self.gamepad_armed = False
            self.throttle = self.brake = 0.0
        self._update_audio()

    @Slot()
    def toggleSoundSweep(self):
        if self.running:
            return
        if self.soundSweepActive:
            self._sweep_elapsed = 36.0  # fade out before closing the stream
            return
        try:
            self.audio.start()
        except Exception as exc:
            self.audio.stop()
            self._set_audio_error(f'Audio unavailable: {exc}')
            return
        self.sound_theme = 'Comfort / Dynamic Orders'
        self.soundThemeChanged.emit()
        self._set_audio_error('')
        self._sweep_elapsed = 0.0
        self._sweep_last_tick = time.perf_counter()
        self.sweep_rpm, self.sweep_throttle = 1000.0, 20.0
        self.audio.set_order_parameters(self.sweep_rpm, self.sweep_throttle)
        self.sweep_timer.start()
        self.sessionChanged.emit()
        self.changed.emit()

    def _sweep_tick(self):
        now = time.perf_counter()
        dt = min(.25, max(0, now - self._sweep_last_tick))
        self._sweep_last_tick = now
        self._sweep_elapsed += dt
        if self._sweep_elapsed >= 37:
            self.sweep_timer.stop()
            self.audio.stop()
            self.sessionChanged.emit()
        elif self._sweep_elapsed >= 36:
            self.audio.set_order_parameters(1000, 0, enabled=False)
        else:
            elapsed = round(self._sweep_elapsed, 6)
            stage = min(2, int(elapsed / 12))
            position = elapsed % 12
            self.sweep_rpm = 1000 + 5000 * (position / 6 if position <= 6 else (12 - position) / 6)
            self.sweep_throttle = (20, 50, 100)[stage]
            self.audio.set_order_parameters(self.sweep_rpm, self.sweep_throttle)
        self.changed.emit()

    def _tick(self):
        now = time.perf_counter()
        # Pause across sleep/long stalls; ordinary timer jitter uses actual elapsed time.
        dt = min(0.25, max(0.0, now - self._last_tick)) if self._last_tick is not None else 0.02
        self._last_tick = now
        if self.source_mode == 'Simulator':
            self.car.update(self.throttle, self.brake, dt)
        elif self._beamng_fresh():
            load = self._signed_motor_load()
            self.display_power, self.display_charge = max(0.0, load), max(0.0, -load)
        self._update_audio()
        if self.source_mode == 'BeamNG':
            self.changed.emit()
            return
        charge = min(1.0, self.car.regen / max(self.car.max_regen_fraction, 1e-9))
        power_target = min(1.0, max(0.0, self.throttle)) if self.car.motor_torque_nm > 0 else 0.0
        current = self.display_power - self.display_charge
        # Both directions pass through zero without lighting both sections.
        target = -charge if charge > 0 else power_target
        response_time = 0.35 if target > 0 and target > current else 0.14
        shown = current + (target - current) * (1 - math.exp(-dt / response_time))
        if target == 0 and abs(shown) < .001:
            shown = 0.0
        self.display_power, self.display_charge = max(0.0, shown), max(0.0, -shown)
        self.changed.emit()

    def eventFilter(self, watched, event):
        if event.type() == QEvent.Type.ApplicationDeactivate:
            self.input_focused = False
            self.gamepad_armed = False
            self.keys_down.clear()
            self._pedals_changed()
        elif event.type() == QEvent.Type.ApplicationActivate:
            self.input_focused = True
        if event.type() in (QEvent.Type.KeyPress, QEvent.Type.KeyRelease):
            if event.key() in (Qt.Key.Key_W, Qt.Key.Key_S):
                from PySide6.QtGui import QGuiApplication
                focus = QGuiApplication.focusObject()
                if focus and (focus.inherits('QQuickTextInput') or focus.inherits('QQuickTextEdit')):
                    self.keys_down.clear()
                    self._pedals_changed()
                    return super().eventFilter(watched, event)
                if not self.running:
                    return super().eventFilter(watched, event)
                if not event.isAutoRepeat():
                    if event.type() == QEvent.Type.KeyPress and self.running:
                        self.keys_down.add(event.key())
                    else:
                        self.keys_down.discard(event.key())
                    self._pedals_changed()
                return True
        return super().eventFilter(watched, event)

    @Slot()
    def shutdown(self):
        was_active = self.running or self.soundSweepActive
        self.sweep_timer.stop()
        self.timer.stop()
        self._last_tick = None
        self.keys_down.clear()
        self.external_throttle = self.external_brake = 0.0
        self.gamepad_armed = False
        self.throttle = self.brake = 0.0
        self._notify_inputs()
        self.audio.stop()
        if was_active:
            logging.getLogger('Vehicle').info('Vehicle stopped; driving input released.')
            self.sessionChanged.emit()
