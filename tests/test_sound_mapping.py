"""Independent sound control checks; no physics, UI or audio hardware."""
import unittest

import numpy as np

from audio import OrderSoundConfig, OrderSynth
from audio import DEBUG_THEMES
from audio import SoundEngine


class SoundMappingTests(unittest.TestCase):
    def render(self, engine, seconds=2):
        chunks = []
        for _ in range(round(seconds * engine.sample_rate / 400)):
            block = np.zeros((400, 1), dtype=np.float32)
            engine._callback(block, 400, None, None)
            chunks.append(block[:, 0].copy())
        return np.concatenate(chunks)

    def example(self, pedal=50, load=.5, accel=0):
        engine = SoundEngine(16000)
        engine.set_driving_parameters(70, pedal, load, accel, 'ready', DEBUG_THEMES['Comfort / Dynamic Orders'])
        samples = self.render(engine)
        return engine, samples[-8000:]

    def test_speed_curve_is_monotonic_and_compressed(self):
        synth = OrderSynth()
        points = [synth.pitch_progression(v) for v in (0, 50, 100, 150, 200, 220, 300)]
        self.assertEqual(points, sorted(points))
        increments = np.diff(points[:5])
        self.assertTrue(np.all(np.diff(increments) < 0))
        self.assertEqual(points[0], 0)
        self.assertEqual(points[-1], 1)
        self.assertEqual(points[-2], 1)

    def test_pedal_and_load_change_energy_without_pitch_shift(self):
        quiet, light = self.example(pedal=10)
        strong, full = self.example(pedal=100)
        self.assertEqual(quiet.order_synth.request[0], strong.order_synth.request[0])
        self.assertGreater(np.std(full), np.std(light))
        frequencies = np.fft.rfftfreq(len(full), 1 / 16000)
        anchor = strong.order_synth.request[0] * 4 / 60
        ratios = []
        for samples in (light, full):
            spectrum = np.abs(np.fft.rfft(samples * np.hanning(len(samples))))
            anchor_energy = spectrum[np.abs(frequencies - anchor) < 4].sum()
            support = spectrum[np.abs(frequencies - anchor * 1.25) < 4].sum()
            ratios.append(support / anchor_energy)
        self.assertGreater(ratios[1], ratios[0])
        _, low = self.example(load=.1)
        _, high = self.example(load=1)
        _, regen = self.example(load=-1)
        self.assertGreater(np.std(high), np.std(low))
        self.assertLess(np.std(regen), np.std(high))
        self.assertFalse(np.allclose(regen, high))

    def test_acceleration_emphasis_decays_and_never_changes_pitch(self):
        engine, _ = self.example(accel=0)
        rpm = engine.order_synth.request[0]
        engine.set_driving_parameters(70, 50, .5, 8, 'ready', DEBUG_THEMES['Comfort / Dynamic Orders'])
        self.render(engine, .4)
        synth = engine.order_synth
        early = synth.accel_fast - synth.accel_baseline
        self.assertGreater(early, .1)
        self.render(engine, 5)
        self.assertLess(synth.accel_fast - synth.accel_baseline, .01)
        self.assertEqual(synth.request[0], rpm)
        self.assertAlmostEqual(synth.rpm, rpm, places=9)

    def test_load_sweep_continuity_and_headroom(self):
        engine = SoundEngine(16000)
        samples = []
        for load in np.linspace(-1, 1, 200):
            engine.set_driving_parameters(150, 100, load, 8, 'ready', DEBUG_THEMES['Comfort / Dynamic Orders'])
            samples.append(self.render(engine, .025))
        samples = np.concatenate(samples)
        self.assertTrue(np.isfinite(samples).all())
        self.assertLess(np.max(np.abs(samples)), .5)
        self.assertLess(np.max(np.abs(np.diff(samples))), .15)

    def test_mapping_configuration_validation(self):
        for kwargs in ({'speed_pitch_curve': 'unknown'}, {'speed_pitch_saturation': 0},
                       {'regen_smoothing': -1}, {'load_gain_curve': ((0, 1), (0, 2))},
                       {'acceleration_dynamic_gain': float('nan')}):
            with self.assertRaises(ValueError):
                OrderSoundConfig(**kwargs)
