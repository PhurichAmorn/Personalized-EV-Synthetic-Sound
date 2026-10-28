import unittest
from dataclasses import replace

import numpy as np

from audio import OrderSoundConfig, OrderSynth, smooth_curve


class OrderSynthTests(unittest.TestCase):
    def steady(self, rpm, throttle):
        synth = OrderSynth()
        synth.set_parameters(rpm, throttle)
        for _ in range(180):
            synth.render(512)
        samples = np.concatenate([synth.render(512) for _ in range(90)])
        spectrum = np.abs(np.fft.rfft(samples * np.hanning(len(samples))))**2
        frequencies = np.fft.rfftfreq(len(samples), 1 / synth.sample_rate)
        return synth, samples, frequencies, spectrum

    def test_anchor_spectral_balance_and_range(self):
        for rpm in (1000, 3250, 4000, 6000):
            for throttle in (20, 50, 100):
                _, _, frequencies, spectrum = self.steady(rpm, throttle)
                peak_hz = frequencies[np.argmax(spectrum)]
                self.assertAlmostEqual(peak_hz, 4 * rpm / 60, delta=2)
                self.assertGreater(spectrum[frequencies <= 403].sum(), spectrum[frequencies > 403].sum())
                outside = spectrum[(frequencies < 19) | (frequencies > 1201)].sum()
                self.assertLess(outside / spectrum.sum(), 1e-5)

    def test_throttle_changes_level_and_supporting_order_ratio(self):
        measurements = []
        for throttle in (20, 50, 100):
            _, samples, frequencies, spectrum = self.steady(3250, throttle)
            anchor = spectrum[np.abs(frequencies - 4 * 3250 / 60) < 3].sum()
            support = spectrum[np.abs(frequencies - 5 * 3250 / 60) < 3].sum()
            measurements.append((np.std(samples), support / anchor))
        for first, second in zip(measurements, measurements[1:]):
            self.assertLess(first[0], second[0])
            self.assertLess(first[1], second[1])

    def test_dynamic_curve_and_smooth_band_edges(self):
        synth = OrderSynth()
        gains = smooth_curve(np.array([1000, 2500, 3250, 4000, 6000]), synth.config.rpm_dynamic_gain_curve)
        np.testing.assert_allclose(gains, [.70, .85, 1, 1.10, 1.15])
        self.assertTrue(np.all(np.diff(gains) > 0))
        weights = synth.spectral_weights(np.array([19, 20, 21, 39, 40, 400, 800, 1000, 1199, 1200, 1201]))
        self.assertEqual(weights[0], 0)
        self.assertEqual(weights[-1], 0)
        self.assertLess(weights[2], .01)
        self.assertLess(weights[-3], .001)
        self.assertGreater(weights[5], weights[6])
        self.assertGreater(weights[6], weights[7])

    def test_headroom_continuity_silence_and_variable_buffers(self):
        for rate in (8000, 44100, 48000):
            synth = OrderSynth(rate)
            samples = []
            for rpm, pedal in ((1000, 20), (6000, 100), (24000, 100), (0, 0), (1000, 50)):
                synth.set_parameters(rpm, pedal)
                for frames in (64, 256, 512, 2048, 8192, 0):
                    samples.append(synth.render(frames))
            samples = np.concatenate(samples)
            self.assertTrue(np.isfinite(samples).all())
            self.assertLessEqual(np.max(np.abs(samples)), .48 + 1e-9)
            self.assertLess(np.max(np.abs(np.diff(samples))), .15)
            synth.set_parameters(1000, 0, False)
            for _ in range(400):
                tail = synth.render(512)
            self.assertLess(np.max(np.abs(tail)), 1e-6)
            synth.reset()
            self.assertEqual(np.max(np.abs(synth.phases)), 0)

    def test_engine_routing_limiter_and_zero_load(self):
        from audio import SoundEngine
        from audio import DEBUG_THEMES
        engine = SoundEngine()
        profile = DEBUG_THEMES['Comfort / Dynamic Orders']
        engine.set_parameters(10000, 20000, .7, 0, profile, throttle=.5, motor_load=.6)
        self.assertEqual(engine.order_synth.request[:2], (3500, 50))
        samples = []
        for _ in range(350):
            out = np.zeros((512, 1), dtype=np.float32)
            engine._callback(out, 512, None, None)
            samples.append(out[:, 0].copy())
        samples = np.concatenate(samples)
        self.assertLess(np.max(np.abs(samples)), .5)
        self.assertLess(np.max(np.abs(np.diff(samples))), .15)
        engine.set_parameters(0, 20000, 0, 0, profile, throttle=1, motor_load=0)
        self.assertFalse(engine.order_synth.request[2])

    def test_universal_driving_inputs_and_regeneration(self):
        from audio import SoundEngine
        from audio import DEBUG_THEMES
        engine = SoundEngine()
        profile = DEBUG_THEMES['Comfort / Dynamic Orders']
        engine.set_driving_parameters(110, 100, .5, 0, 'ready', profile)
        self.assertAlmostEqual(engine.order_synth.request[0], 1000 + 5000 * engine.order_synth.pitch_progression(110))
        self.assertEqual(engine.order_synth.request[1], 100)
        self.assertEqual(engine.order_synth.driving_controls, (.5, 0))
        engine.set_driving_parameters(110, 100, .5, 8, 'ready', profile)
        self.assertEqual(engine.order_synth.driving_controls, (.5, 1))
        engine.set_driving_parameters(110, 100, 0, 0, 'ready', profile)
        self.assertEqual(engine.order_synth.driving_controls, (0, 0))
        engine.set_driving_parameters(110, 0, -.8, -3, 'ready', profile)
        self.assertEqual(engine.order_synth.request[1], 0)
        self.assertEqual(engine.order_synth.regen_request, .8)
        chunks = []
        for load in (1, -.8, 0):
            engine.set_driving_parameters(110, 100 if load > 0 else 0, load,
                                          6 if load > 0 else -2, 'ready', profile)
            for _ in range(90):
                out = np.zeros((512, 1), dtype=np.float32)
                engine._callback(out, 512, None, None)
                chunks.append(out[:, 0].copy())
        samples = np.concatenate(chunks)
        self.assertTrue(np.isfinite(samples).all())
        self.assertLess(np.max(np.abs(samples)), .5)
        self.assertLess(np.max(np.abs(np.diff(samples))), .15)
        engine.set_driving_parameters(0, 100, 0, 0, 'ready', profile)
        self.assertFalse(engine.order_synth.request[2])
        for args in ((float('nan'), 0, 0, 0, 'ready'),
                     (0, 0, 0, 0, 'unknown'), (-1, 0, 0, 0, 'ready')):
            with self.assertRaises(ValueError):
                engine.set_driving_parameters(*args, profile)

    def test_startup_cue_and_mute(self):
        from audio import SoundEngine
        from audio import DEBUG_THEMES
        engine = SoundEngine()
        profile = DEBUG_THEMES['Comfort / Dynamic Orders']
        engine.set_driving_parameters(0, 0, 0, 0, 'starting', profile)
        self.assertFalse(engine.order_synth.request[2])
        out = np.zeros((int(1.6 * engine.sample_rate), 1), dtype=np.float32)
        engine._callback(out, len(out), None, None)
        self.assertGreater(np.max(np.abs(out)), .01)
        self.assertLess(np.max(np.abs(out)), .1)
        self.assertIsNone(engine.startup_sample)
        engine.set_driving_parameters(100, 100, 1, 5, 'ready', profile, sound_enabled=False)
        out = np.zeros((engine.sample_rate, 1), dtype=np.float32)
        engine._callback(out, len(out), None, None)
        self.assertLess(np.max(np.abs(out[-1000:])), 1e-7)

    def test_optional_body_noise_and_parameter_validation(self):
        config = OrderSoundConfig()
        synth = OrderSynth(config=replace(config, noise_gain=.01))
        synth.set_parameters(3000, 100)
        self.assertTrue(np.isfinite(synth.render(2048)).all())
        for changes in ({'dominant_order': 7}, {'master_gain': 2}, {'noise_gain': .2},
                        {'rpm_smoothing_s': 0}, {'throttle_gain_curve': ((20, 1), (10, .5))}):
            with self.assertRaises(ValueError):
                replace(config, **changes)
        with self.assertRaises(ValueError):
            synth.set_parameters(float('nan'), 20)


if __name__ == '__main__':
    unittest.main()
