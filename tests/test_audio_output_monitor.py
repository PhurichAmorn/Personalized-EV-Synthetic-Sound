import unittest
from types import SimpleNamespace
from unittest.mock import Mock

from backend.audio_output_monitor import AudioOutputMonitor


class AudioOutputMonitorTests(unittest.TestCase):
    def monitor(self):
        controller = SimpleNamespace(audio=Mock(), running=True, soundSweepActive=False,
            audio_error='', changed=Mock(), _update_audio=Mock(), car=object())
        controller._set_audio_error = lambda message: setattr(controller, 'audio_error', message)
        return SimpleNamespace(controller=controller, attempts=0, reopen=Mock())

    def test_recovery_preserves_vehicle_and_restores_sound_inputs(self):
        monitor = self.monitor()
        car = monitor.controller.car
        monitor.controller.audio.stop.side_effect = RuntimeError('Old device removed')
        AudioOutputMonitor.recover(monitor)
        audio = monitor.controller.audio
        audio.refresh_devices.assert_called_once()
        audio.start.assert_called_once()
        monitor.controller._update_audio.assert_called_once()
        self.assertIs(monitor.controller.car, car)
        self.assertEqual(monitor.controller.audio_error, '')

    def test_retries_are_bounded_and_failures_visible(self):
        monitor = self.monitor()
        monitor.controller.audio.start.side_effect = RuntimeError('Output missing')
        for _ in range(3):
            AudioOutputMonitor.recover(monitor)
        self.assertEqual(monitor.attempts, 3)
        self.assertEqual(monitor.reopen.start.call_count, 2)
        self.assertIn('Output missing', monitor.controller.audio_error)

    def test_standby_refresh_does_not_start_playback(self):
        monitor = self.monitor()
        monitor.controller.running = False
        AudioOutputMonitor.recover(monitor)
        monitor.controller.audio.refresh_devices.assert_called_once()
        monitor.controller.audio.start.assert_not_called()

    def test_system_change_schedules_recovery(self):
        monitor = self.monitor()
        monitor.output_signature = lambda: (b'new', 48000, 2)
        monitor.signature = (b'old', 44100, 2)
        monitor.schedule = Mock()
        monitor.controller.audio.stream.active = True
        AudioOutputMonitor.check(monitor)
        monitor.schedule.assert_called_once()
        self.assertEqual(monitor.signature, (b'new', 48000, 2))
