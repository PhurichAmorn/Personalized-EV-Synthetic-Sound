"""Controller integration checks; audio hardware is mocked, DSP still runs."""
import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('QSG_RHI_BACKEND', 'software')

import math
import unittest
from unittest.mock import patch

import numpy as np
from PySide6.QtCore import QCoreApplication, QEvent, Qt
from PySide6.QtGui import QGuiApplication, QKeyEvent
from PySide6.QtTest import QSignalSpy

from audio import PROFILES, DEBUG_THEMES
from audio import SoundEngine
from simulation.vehicle_model import VehicleModel
from backend.controller import SimulatorController




class SimulatorIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QGuiApplication.instance() or QGuiApplication([])

    def setUp(self):
        self.controller = SimulatorController()
        self.controller.timer.setInterval(1_000_000)
        self.start_patch = patch.object(self.controller.audio, 'start')
        self.stop_patch = patch.object(self.controller.audio, 'stop')
        self.start_audio = self.start_patch.start()
        self.stop_audio = self.stop_patch.start()

    def tearDown(self):
        self.controller.shutdown()
        self.start_patch.stop()
        self.stop_patch.stop()

    def tick(self, elapsed=0.02):
        self.controller._last_tick = 1000.0
        with patch('backend.controller.time.perf_counter', return_value=1000.0 + elapsed):
            self.controller._tick()

    def key(self, event_type, key, watched=None, repeat=False):
        event = QKeyEvent(event_type, key, Qt.KeyboardModifier.NoModifier, '', repeat)
        if watched is None:
            return self.controller.eventFilter(self.controller, event)
        return QCoreApplication.sendEvent(watched, event)

    def test_real_elapsed_time_drives_model_and_smoothing(self):
        self.controller.toggle()
        self.controller.throttle = 1
        expected = VehicleModel.from_name('Compact EV')
        expected.update(1, 0, 0.07)
        self.tick(0.07)
        self.assertAlmostEqual(self.controller.speed, expected.speed, places=7)
        self.assertAlmostEqual(self.controller.power, 1 - math.exp(-0.07 / 0.35))
        before = self.controller.speed
        # Laptop sleep/long stalls advance at most 250 ms, not minutes of driving.
        self.tick(60)
        self.assertLess(self.controller.speed - before, 5)

    def test_light_pedal_during_regen_never_lights_power(self):
        for name in self.controller.vehicleNames:
            self.controller.car = VehicleModel.from_name(name)
            self.controller.car.speed = 60
            self.controller.display_power = self.controller.display_charge = 0
            self.controller.throttle = 0
            for _ in range(40):
                self.tick()
            self.assertGreater(self.controller.charge, 0)
            self.controller.throttle = .04
            for _ in range(30):
                self.tick()
                self.assertLess(self.controller.car.motor_torque_nm, 0)
                self.assertGreater(self.controller.charge, 0)
                self.assertEqual(self.controller.power, 0)
            self.controller.throttle = .5
            for _ in range(60):
                self.tick()
                self.assertEqual(self.controller.power * self.controller.charge, 0)
                if self.controller.power > 0:
                    self.assertGreater(self.controller.car.motor_torque_nm, 0)
            self.assertGreater(self.controller.power, .4)
            self.assertEqual(self.controller.charge, 0)

    def test_signed_meter_crosses_zero_smoothly_without_overlapping_fills(self):
        self.controller.display_charge = .8
        self.controller.throttle = 1
        self.controller.car.motor_torque_nm = 10
        self.controller.car.regen = 0
        with patch.object(self.controller.car, 'update'):
            self.tick()
            self.assertGreater(self.controller.charge, 0)
            self.assertEqual(self.controller.power, 0)
            for _ in range(50):
                self.tick()
                self.assertEqual(self.controller.power * self.controller.charge, 0)
            self.assertGreater(self.controller.power, .8)
            self.controller.car.motor_torque_nm = -10
            self.controller.car.regen = .1
            previous = self.controller.power
            self.tick()
            self.assertGreater(self.controller.power, 0)
            self.assertLess(previous - self.controller.power, .2)
            self.assertEqual(self.controller.charge, 0)
            for _ in range(50):
                self.tick()
                self.assertEqual(self.controller.power * self.controller.charge, 0)
            self.assertEqual(self.controller.power, 0)
            self.assertGreater(self.controller.charge, 0)
            self.controller.car.motor_torque_nm = 0
            self.controller.car.regen = 0
            for _ in range(60):
                self.tick()
            self.assertEqual(self.controller.power, 0)
            self.assertEqual(self.controller.charge, 0)


    def test_start_stop_selection_and_keyboard_priority(self):
        self.key(QEvent.Type.KeyPress, Qt.Key.Key_W)
        self.assertEqual(self.controller.throttle, 0)
        self.controller.selectVehicle('Performance EV')
        self.assertEqual('Performance EV', self.controller.selectedVehicle)
        self.controller.toggle()
        self.start_audio.assert_called_once()
        self.assertTrue(self.controller.running)
        self.controller.selectVehicle('Compact EV')
        self.assertEqual('Performance EV', self.controller.selectedVehicle)
        self.key(QEvent.Type.KeyPress, Qt.Key.Key_W)
        for _ in range(30):
            self.tick()
        self.assertGreater(self.controller.speed, 0)
        self.assertGreater(self.controller.power, 0)
        self.assertGreater(self.controller.audio.params[1], 0)
        self.key(QEvent.Type.KeyPress, Qt.Key.Key_S)
        self.tick()
        self.assertEqual(self.controller.car.drive_power, 0)
        self.assertEqual(self.controller.audio.params[1], 0)
        self.assertTrue(self.controller.regenActive)
        self.key(QEvent.Type.KeyRelease, Qt.Key.Key_W)
        self.key(QEvent.Type.KeyRelease, Qt.Key.Key_S)
        self.assertEqual(self.controller.throttle, 0)
        self.assertEqual(self.controller.brake, 0)
        self.key(QEvent.Type.KeyPress, Qt.Key.Key_W)
        self.controller.eventFilter(self.controller, QEvent(QEvent.Type.ApplicationDeactivate))
        self.assertEqual(self.controller.throttle, 0)
        self.controller.toggle()
        self.assertFalse(self.controller.running)
        self.assertEqual(self.controller.speed, 0)
        self.assertEqual(self.controller.rpm, 0)
        self.assertEqual(self.controller.power, 0)
        self.assertEqual(self.controller.charge, 0)
        self.assertEqual(self.controller.car.soc, 0.8)

    def test_only_neutral_presets_are_exposed(self):
        self.assertEqual(self.controller.vehicleNames, ['Compact EV', 'Performance EV'])
        for name in VehicleModel.available_names():
            self.controller.selectVehicle(name)
            self.assertEqual(self.controller.selectedVehicle, 'Compact EV')
        for name in self.controller.vehicleNames:
            self.controller.selectVehicle(name)
            self.assertEqual(self.controller.selectedVehicle, name)
            for brand in ('Honda', 'Tesla', 'Mazda', 'Porsche'):
                self.assertNotIn(brand, self.controller.specs)

    def test_audio_failure_leaves_vehicle_stopped(self):
        self.start_audio.side_effect = RuntimeError('No audio device')
        self.controller.toggle()
        self.assertFalse(self.controller.running)
        self.assertIn('No audio device', self.controller.error)
        self.stop_audio.assert_called_once()

    def test_empty_battery_has_no_launch_sound(self):
        self.controller.car.soc = 0
        self.controller.throttle = 1
        self.tick()
        self.assertEqual(self.controller.audio.params[1], 0)
        self.assertEqual(self.controller.speed, 0)


    def test_common_sound_bridge_across_vehicles(self):
        pitches = []
        for name in self.controller.vehicleNames:
            self.controller.selectVehicle(name)
            self.controller.car.speed = 110
            self.controller.car.motor_torque_nm = .5 * self.controller.car.max_torque_nm
            self.controller.throttle = 1
            self.controller.toggle()
            self.controller._update_audio()
            pitches.append(self.controller.audio.electric_hz_target)
            self.assertGreater(self.controller.audio.params[1], 0)
            self.controller.shutdown()
        for pitch in pitches:
            profile = DEBUG_THEMES[self.controller.sound_theme]
            scale = profile['electric_pitch_scale']
            start = profile.get('electric_start_hz', profile['electric_pitch_offset'] + scale * profile['base_hz'])
            self.assertAlmostEqual(pitch, start + scale * 180 * self.controller.audio.order_synth.pitch_progression(110))

    def test_controller_analog_inputs_and_safety_gates(self):
        c = self.controller
        c.setGamepadState('Test pad', .5, .25, '')
        self.assertTrue(c.controllerConnected)
        self.assertEqual((c.throttleInput, c.brakeInput), (.5, .25))
        self.assertEqual((c.throttle, c.brake), (0, 0))
        c.toggle()
        c.setSoundStarting(True)
        c.setGamepadState('Test pad', 1, 0, '')
        self.assertEqual(c.throttle, 0)
        c.setSoundStarting(False)
        c.setGamepadState('Test pad', 1, 0, '')
        self.assertEqual(c.throttle, 0)
        c.setGamepadState('Test pad', 0, 0, '')
        c.setGamepadState('Test pad', .5, .25, '')
        self.assertEqual((c.throttle, c.brake), (.5, .25))
        self.tick()
        self.assertLessEqual(c.car.motor_torque_nm, 0)
        self.key(QEvent.Type.KeyPress, Qt.Key.Key_W)
        self.assertEqual(c.throttle, 1)
        c.eventFilter(self.app, QEvent(QEvent.Type.ApplicationDeactivate))
        self.assertEqual((c.throttle, c.brake), (0, 0))
        c.eventFilter(self.app, QEvent(QEvent.Type.ApplicationActivate))
        c.setGamepadState('Test pad', .5, .25, '')
        self.assertEqual(c.throttle, 0)
        c.setGamepadState('Test pad', 0, 0, '')
        c.setGamepadState('Test pad', 1, 0, '')
        self.assertEqual(c.throttle, 1)
        c.setGamepadState('', 0, 0, '')
        self.assertFalse(c.controllerConnected)
        self.assertEqual((c.throttle, c.brake), (0, 0))

    def test_keyboard_input_bars_are_binary(self):
        self.controller.toggle()
        for key, field in ((Qt.Key.Key_W, 'throttleInput'), (Qt.Key.Key_S, 'brakeInput')):
            self.key(QEvent.Type.KeyPress, key)
            self.assertEqual(getattr(self.controller, field), 1)
            self.key(QEvent.Type.KeyRelease, key)
            self.assertEqual(getattr(self.controller, field), 0)

    def test_live_ticks_do_not_notify_configuration_or_connection_bindings(self):
        c = self.controller
        signals = {name: QSignalSpy(getattr(c, name)) for name in (
            'changed', 'vehicleChanged', 'sessionChanged', 'soundThemeChanged',
            'audioErrorChanged', 'controllerChanged', 'controllerDevicesChanged', 'inputChanged')}
        c.toggle()
        self.assertEqual(signals['sessionChanged'].count(), 1)
        initial_ticks = signals['changed'].count()
        for _ in range(10):
            self.tick()
        self.assertEqual(signals['changed'].count() - initial_ticks, 10)
        for name in ('vehicleChanged', 'soundThemeChanged', 'audioErrorChanged',
                     'controllerChanged', 'controllerDevicesChanged', 'inputChanged'):
            self.assertEqual(signals[name].count(), 0, name)
        c.setGamepadState('Test pad', 0, 0, '')
        c.setGamepadState('Test pad', 0, 0, '')
        c.setGamepadState('Test pad', .25, .5, '')
        c.setGamepadState('Test pad', .25, .5, '')
        self.assertEqual(signals['controllerChanged'].count(), 1)
        self.assertEqual(signals['inputChanged'].count(), 1)
        self.assertEqual(signals['changed'].count() - initial_ticks, 10)
        c._set_audio_error('Test error')
        c._set_audio_error('Test error')
        self.assertEqual(signals['audioErrorChanged'].count(), 1)
        c.selectSoundTheme('Premium EV')
        self.assertEqual(signals['soundThemeChanged'].count(), 0)  # Retired profile cannot change the sound.
        c.toggle()
        self.assertEqual(signals['sessionChanged'].count(), 2)
        c.selectVehicle('Performance EV')
        self.assertEqual(signals['vehicleChanged'].count(), 1)



    def test_order_sweep_is_audio_only_and_blocks_driving(self):
        original = vars(self.controller.car).copy()
        self.controller.toggleSoundSweep()
        self.controller.sweep_timer.setInterval(1_000_000)
        self.assertTrue(self.controller.soundSweepActive)
        self.assertFalse(self.controller.running)
        self.assertEqual(self.controller.audio.order_synth.request[:2], (1000, 20))
        self.controller.toggle()
        self.key(QEvent.Type.KeyPress, Qt.Key.Key_W)
        self.assertFalse(self.controller.running)
        self.assertEqual(self.controller.throttle, 0)
        for elapsed, rpm, throttle in ((6, 6000, 20), (12, 1000, 50), (18, 6000, 50), (24, 1000, 100), (30, 6000, 100)):
            self.controller._sweep_elapsed = elapsed - .02
            self.controller._sweep_last_tick = 1000
            with patch('backend.controller.time.perf_counter', return_value=1000.02):
                self.controller._sweep_tick()
            self.assertAlmostEqual(self.controller.sweep_rpm, rpm, delta=.01)
            self.assertEqual(self.controller.sweep_throttle, throttle)
        self.assertEqual(vars(self.controller.car), original)
        self.controller.toggleSoundSweep()
        self.controller._sweep_last_tick = 1000
        with patch('backend.controller.time.perf_counter', return_value=1000.02):
            self.controller._sweep_tick()
        self.assertFalse(self.controller.audio.order_synth.request[2])
        self.controller._sweep_elapsed = 37
        self.controller._sweep_last_tick = 1000
        with patch('backend.controller.time.perf_counter', return_value=1000.02):
            self.controller._sweep_tick()
        self.assertFalse(self.controller.soundSweepActive)
        self.stop_audio.assert_called()

    def test_procedural_audio_remains_finite_and_bounded(self):
        engine = SoundEngine()
        output = np.zeros((512, 1), dtype=np.float32)
        for rpm, drive, regen in ((0, 0, 0), (4000, 0.5, 0), (10000, 1, 0), (6000, 0, 0.4)):
            engine.set_parameters(rpm, 12000, drive, regen, PROFILES['Sound Profile A'])
            for _ in range(50):
                engine._callback(output, len(output), None, None)
                self.assertTrue(np.isfinite(output).all())
                self.assertLessEqual(float(np.max(np.abs(output))), 1)
            if drive or regen:
                self.assertGreater(float(np.max(np.abs(output))), 0.01)


if __name__ == '__main__':
    unittest.main()
