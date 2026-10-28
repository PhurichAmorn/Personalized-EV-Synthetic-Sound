import math
import unittest

import numpy as np

from audio import DEBUG_THEMES, PROFILES
from audio import SoundEngine


class SoundEngineTests(unittest.TestCase):
    def test_inactive_generators_sleep_after_theme_fades(self):
        for name, profile in DEBUG_THEMES.items():
            with self.subTest(theme=name):
                engine = SoundEngine()
                engine.set_driving_parameters(110, 100, 1, 4, 'ready', profile)
                self.render(engine, 4)
                before = engine.render_counts.copy()
                samples = self.render(engine, .25)
                called = engine.render_counts > before
                self.assertEqual(bool(called[0]), name == 'Premium EV')
                self.assertEqual(bool(called[1]), bool(profile.get('electric_mix')))
                self.assertEqual(bool(called[2]), bool(profile.get('order_synthesis')))
                self.assertTrue(np.isfinite(samples).all())

    def test_sleeping_theme_resumes_with_current_pitch_without_clicks(self):
        engine = SoundEngine()
        samples = []
        for name in ('Comfort / Dynamic Orders', 'Premium EV', 'Electric Motorsport',
                     'Taycan Inspired', 'Comfort / Dynamic Orders'):
            engine.set_driving_parameters(150, 100, .8, 3, 'ready', DEBUG_THEMES[name])
            samples.append(self.render(engine, 4))
        samples = np.concatenate(samples)
        self.assertTrue(np.isfinite(samples).all())
        self.assertLess(np.max(np.abs(np.diff(samples))), .15)
        self.assertLess(np.max(np.abs(samples)), .95)
        self.assertAlmostEqual(engine.order_synth.rpm, 1000 + 5000 * engine.order_synth.pitch_progression(150))

    def test_taycan_palette_low_register_and_smooth_switch(self):
        engine = SoundEngine()
        profile = DEBUG_THEMES['Taycan Inspired']
        engine.set_driving_parameters(110, 100, 1, 4, 'ready', profile)
        self.assertAlmostEqual(engine.electric_hz_target, 90 + 180 * engine.order_synth.pitch_progression(110))
        samples = self.render(engine, 3)[-engine.sample_rate:]
        spectrum = np.abs(np.fft.rfft(samples * np.hanning(len(samples))))**2
        f = np.fft.rfftfreq(len(samples), 1 / engine.sample_rate)
        self.assertGreater(spectrum[f < 400].sum() / spectrum.sum(), .65)
        engine.set_driving_parameters(110, 0, -.8, -3, 'ready', profile)
        self.assertAlmostEqual(engine.electric_hz_target, 90 + 180 * engine.order_synth.pitch_progression(110))
        engine.set_driving_parameters(110, 100, 1, 4, 'ready', DEBUG_THEMES['Electric Motorsport'])
        switched = self.render(engine, 1)
        self.assertTrue(np.isfinite(switched).all())
        self.assertLess(np.max(np.abs(np.diff(np.concatenate((samples[-512:], switched))))), .15)
        self.assertLess(np.max(np.abs(switched)), .95)
        with self.assertRaises(ValueError):
            engine.set_parameters(0, 12000, 0, 0, dict(profile, electric_pitch_scale=0))

    def test_direct_acceleration_does_not_shift_pitch(self):
        engine = SoundEngine()
        profile = PROFILES['Sound Profile A']
        targets = []
        for acceleration in (0, 4, 8):
            engine.set_parameters(4000, 20000, 0.5, 0, profile,
                                  motor_load=0.8, regen_load=0,
                                  acceleration_m_s2=acceleration)
            targets.append(engine.params)
        self.assertEqual(targets[0][0], targets[1][0])
        self.assertEqual(targets[1][0], targets[2][0])
        self.assertEqual(targets[0][4], targets[2][4])
        self.assertEqual(targets[0][1:4], targets[2][1:4])
        self.assertTrue(np.isfinite(self.render(engine, 0.5)).all())
        engine.set_parameters(4000, 20000, 0, 0.3, profile,
                              motor_load=0, regen_load=0.5, acceleration_m_s2=8)
        self.assertEqual(engine.params[0], targets[0][0])
        self.assertEqual(engine.params[4], profile['richness'])
        samples = self.render(engine, 0.5)
        self.assertLess(np.max(np.abs(np.diff(samples))), 0.15)
        with self.assertRaises(ValueError):
            engine.set_parameters(0, 20000, 0, 0, profile, acceleration_m_s2=math.nan)

    def test_electric_theme_switch_and_restart(self):
        engine = SoundEngine()
        engine.set_parameters(6000, 12000, 0.8, 0, DEBUG_THEMES['Premium EV'])
        a = self.render(engine, 0.5)
        engine.set_parameters(6000, 12000, 0.8, 0, DEBUG_THEMES['Electric Motorsport'])
        b = self.render(engine, 1)
        self.assertGreater(engine.electric_mix, 0.9)
        samples = np.concatenate((a, b))
        self.assertTrue(np.isfinite(samples).all())
        self.assertLess(np.max(np.abs(np.diff(samples))), 0.15)
        self.assertLess(np.max(np.abs(samples)), 0.95)
        engine.set_parameters(0, 12000, 0, 0, DEBUG_THEMES['Electric Motorsport'])
        silence = self.render(engine, 4)
        self.assertLess(np.max(np.abs(silence[-2048:])), 1e-6)
        engine._reset()
        self.assertEqual(np.max(np.abs(engine.electric_phases)), 0)
        self.assertEqual(engine.electric_mix, 0)

    def test_electric_theme_avoids_engine_bass_register(self):
        engine = SoundEngine()
        engine.set_parameters(6000, 12000, 0.8, 0, DEBUG_THEMES['Electric Motorsport'])
        samples = self.render(engine, 4)[-engine.sample_rate:]
        spectrum = np.abs(np.fft.rfft(samples * np.hanning(len(samples))))**2
        frequencies = np.fft.rfftfreq(len(samples), 1 / engine.sample_rate)
        self.assertLess(spectrum[frequencies < 120].sum() / spectrum.sum(), 0.01)

    def test_electric_motor_pitch_tracks_motion_without_lift_off_pitch_step(self):
        engine = SoundEngine()
        profile = DEBUG_THEMES['Electric Motorsport']
        engine.set_driving_parameters(100, 100, 1, 8, 'ready', profile)
        drive_hz = engine.electric_hz_target
        engine.set_driving_parameters(100, 0, -.8, -3, 'ready', profile)
        self.assertEqual(engine.electric_hz_target, drive_hz)
        engine.set_driving_parameters(200, 100, 1, 2, 'ready', profile)
        self.assertGreater(engine.electric_hz_target, drive_hz)
        samples = self.render(engine, 3)[-engine.sample_rate:]
        spectrum = np.abs(np.fft.rfft(samples * np.hanning(len(samples))))**2
        f = np.fft.rfftfreq(len(samples), 1 / engine.sample_rate)
        self.assertLess(spectrum[f > 1000].sum() / spectrum.sum(), .4)

    def test_character_layers_change_timbre_without_clicks_or_clipping(self):
        from experiment.live_search import CHARACTER_CONTROLS, CHARACTER_OPENING, profile_for
        from audio import SOUND_THEMES
        engine = SoundEngine()
        rendered = []
        for values in CHARACTER_OPENING:
            profile = profile_for(SOUND_THEMES['Comfort'], dict(zip(CHARACTER_CONTROLS, values)))
            engine.set_driving_parameters(80, 70, .7, 2, 'ready', profile)
            rendered.append(self.render(engine, .7))
        samples = np.concatenate(rendered)
        self.assertTrue(np.isfinite(samples).all())
        self.assertLess(np.max(np.abs(np.diff(samples))), .15)
        self.assertLess(np.max(np.abs(samples)), .95)
        with self.assertRaises(ValueError):
            engine.set_parameters(4000, 12000, 1, 0, dict(profile, electric_pulse=1.1))

    def test_source_is_tonal_without_broadband_noise(self):
        engine = SoundEngine()
        spectrum = np.abs(np.fft.rfft(engine.source * np.hanning(engine.source.shape[1]), axis=1))**2
        frequencies = np.fft.rfftfreq(engine.source.shape[1], 1 / engine.sample_rate)
        self.assertLess(float(spectrum[:, frequencies > 850].sum() / spectrum.sum()), 1e-6)

    def render(self, engine, seconds):
        blocks = []
        for _ in range(math.ceil(seconds * engine.sample_rate / 512)):
            output = np.zeros((512, 1), dtype=np.float32)
            engine._callback(output, 512, None, None)
            blocks.append(output[:, 0].copy())
        return np.concatenate(blocks)

    def test_torque_controls_launch_and_regenerative_texture(self):
        engine = SoundEngine()
        engine.set_parameters(0, 12000, 0, 0, PROFILES['Sound Profile A'], motor_load=0.8, regen_load=0)
        self.assertGreater(engine.params[1], 0.5)
        self.assertGreater(np.std(self.render(engine, 0.3)[-2048:]), 0.01)
        engine.set_parameters(6000, 12000, 0, 0, PROFILES['Sound Profile A'], motor_load=0, regen_load=0.5)
        self.assertEqual(engine.params[1], 0)
        self.assertGreater(engine.params[2], 0)
        # Regenerative braking can be audible when electrical recovery is very weak.
        self.assertGreater(np.std(self.render(engine, 0.6)[-2048:]), 0.01)

    def test_silence_and_release_decay(self):
        engine = SoundEngine()
        self.assertEqual(np.max(np.abs(self.render(engine, 0.2))), 0)
        engine.set_parameters(6000, 12000, 1, 0, PROFILES['Sound Profile A'], motor_load=1, regen_load=0)
        self.render(engine, 0.5)
        engine.set_parameters(0, 12000, 0, 0, PROFILES['Sound Profile A'], motor_load=0, regen_load=0)
        samples = self.render(engine, 3)
        self.assertLess(np.max(np.abs(samples[-2048:])), 1e-6)

    def test_grains_are_bounded_and_do_not_repeat_a_phrase(self):
        engine = SoundEngine()
        engine.set_parameters(5000, 12000, 0.5, 0, PROFILES['Sound Profile A'], motor_load=0.5, regen_load=0)
        samples = self.render(engine, 7)
        self.assertLessEqual(len(engine.grains), 8)
        self.assertTrue(np.isfinite(samples).all())
        self.assertLess(np.max(np.abs(samples)), 0.95)
        a = samples[engine.sample_rate:2 * engine.sample_rate]
        b = samples[4 * engine.sample_rate:5 * engine.sample_rate]
        self.assertFalse(np.array_equal(a, b))
        self.assertLess(abs(np.corrcoef(a, b)[0, 1]), 0.9)

    def test_callback_boundary_continuity_and_regen_peak(self):
        engine = SoundEngine()
        engine.set_parameters(7000, 12000, 1, 0, PROFILES['Sound Profile A'], motor_load=1, regen_load=0)
        drive = self.render(engine, 1)
        engine.set_parameters(7000, 12000, 0, 0.3, PROFILES['Sound Profile A'], motor_load=0, regen_load=0.5)
        release = self.render(engine, 1)
        samples = np.concatenate([drive, release])
        jumps = np.abs(np.diff(samples))
        boundary_jumps = jumps[511::512]
        self.assertLess(np.max(boundary_jumps), 0.12)
        self.assertLess(np.max(jumps), 0.15)
        self.assertLess(np.max(np.abs(release)), np.max(np.abs(drive)) * 1.1)

    def test_variable_callback_sizes_and_sample_rates(self):
        for sample_rate in (8000, 44100, 48000):
            engine = SoundEngine(sample_rate)
            engine.set_parameters(12000, 12000, 1, 0.4, PROFILES['Sound Profile A'])
            for frames in (64, 256, 512, 1024, 2048, 0):
                output = np.zeros((frames, 1), dtype=np.float32)
                engine._callback(output, frames, None, None)
                self.assertTrue(np.isfinite(output).all())
                if frames:
                    self.assertLessEqual(np.max(np.abs(output)), 1)

    def test_parameter_validation(self):
        engine = SoundEngine()
        for rpm, ceiling in ((math.nan, 12000), (0, 0), (0, math.inf)):
            with self.assertRaises(ValueError):
                engine.set_parameters(rpm, ceiling, 0, 0, PROFILES['Sound Profile A'])
        with self.assertRaises(ValueError):
            engine.set_parameters(0, 12000, 0, 0, PROFILES['Sound Profile A'], motor_load=math.nan)
        with self.assertRaises(ValueError):
            SoundEngine(1000)

    def test_restart_resets_envelopes(self):
        engine = SoundEngine()
        engine.set_parameters(9000, 12000, 1, 0, PROFILES['Sound Profile A'])
        self.render(engine, 0.2)
        engine._reset()
        self.assertEqual(engine.drive_level, 0)
        self.assertEqual(engine.params[1], 0)
        self.assertIsNone(engine.stream)
        # Native fake-device lifecycle tests cover start failure cleanup.

    def test_stereo_output_is_filled_on_both_channels(self):
        engine = SoundEngine(48000)
        engine.set_parameters(6000, 12000, 1, 0, PROFILES['Sound Profile A'])
        output = np.full((1024, 2), np.nan, dtype=np.float32)
        engine._callback(output, len(output), None, None)
        self.assertTrue(np.isfinite(output).all())
        np.testing.assert_array_equal(output[:, 0], output[:, 1])


if __name__ == '__main__':
    unittest.main()
