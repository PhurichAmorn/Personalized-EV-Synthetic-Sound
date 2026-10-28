"""Profile behavior and staged sound continuity, without audio hardware."""
import unittest

import numpy as np

from audio import SOUND_THEMES
from audio import SoundEngine
from experiment.live_search import GP_CONTROLS, profile_for


class SoundProfileTests(unittest.TestCase):
    @staticmethod
    def render(engine, seconds):
        blocks = []
        for _ in range(round(seconds * engine.sample_rate / 400)):
            block = np.empty((400, 1), dtype=np.float32)
            engine._callback(block, 400, None, None)
            blocks.append(block[:, 0].copy())
        return np.concatenate(blocks)

    def test_cruise_relaxes_and_acceleration_adds_body_without_changing_pitch(self):
        for name, profile in SOUND_THEMES.items():
            with self.subTest(theme=name):
                levels = []
                for acceleration in (0, 4):
                    engine = SoundEngine(16000)
                    engine.set_driving_parameters(70, 60, .6, acceleration, 'ready', profile)
                    pitch = engine.electric_hz_target
                    samples = self.render(engine, 4)[-16000:]
                    levels.append(np.std(samples))
                    self.assertLess(np.max(np.abs(samples)), .5)
                    engine.set_driving_parameters(70, 0, -.6, -3, 'ready', profile)
                    self.assertEqual(engine.electric_hz_target, pitch)
                    regen = self.render(engine, 4)[-16000:]
                    self.assertLess(np.std(regen), np.std(samples))
                    engine.set_driving_parameters(70, 0, 0, 0, 'ready', profile)
                    coast = self.render(engine, 6)[-16000:]
                    self.assertLess(np.max(np.abs(coast)), 1e-6)
                self.assertGreater(levels[1], levels[0] * 1.15)
        self.assertLess(SOUND_THEMES['Comfort']['drive_cruise_gain'], SOUND_THEMES['Sport']['drive_cruise_gain'])

    def test_stage_weights_blend_without_gaps_or_boundary_jumps(self):
        speeds = np.linspace(0, 250, 25001)
        weights = SoundEngine.traction_stage_weights(speeds)
        self.assertTrue(np.all(weights >= 0))
        np.testing.assert_allclose(weights.sum(axis=0), 1)
        self.assertLess(np.max(np.abs(np.diff(weights, axis=1))), .001)
        np.testing.assert_array_equal(np.argmax(weights[:, [0, 4500, 8500, 15000]], axis=0), [0, 1, 2, 3])

    def test_deep_baseline_rises_with_speed_without_repeating_pitch_phrase(self):
        engine = SoundEngine(16000)
        pitches = []
        dominant = []
        for speed in (20, 70, 140):
            engine.set_driving_parameters(speed, 100, .8, 4, 'ready', SOUND_THEMES['Deep'])
            pitches.append(engine.electric_hz_target)
            samples = self.render(engine, 3)
            self.assertTrue(np.isfinite(samples).all())
            self.assertLess(np.max(np.abs(samples)), .5)
            spectrum = np.abs(np.fft.rfft(samples[-16000:] * np.hanning(16000)))
            dominant.append(np.argmax(spectrum))
        self.assertGreater(pitches[1] - pitches[0], 20)
        self.assertGreater(pitches[2] - pitches[1], 15)
        self.assertEqual(dominant, sorted(dominant))
        self.assertEqual(engine.traction_cycle_position, 0)

    def test_deep_sweep_boundary_hover_regen_and_theme_switch_are_continuous(self):
        engine = SoundEngine(48000)
        chunks = []
        speeds = np.concatenate((np.linspace(0, 170, 250),
                                 70 + .1 * np.sin(np.arange(80)), np.linspace(170, 0, 250)))
        for i, speed in enumerate(speeds):
            regen = i >= 330
            engine.set_driving_parameters(float(speed), 0 if regen else 100,
                -.8 if regen else .8, -3 if regen else 4, 'ready', SOUND_THEMES['Deep'])
            frames = (240, 480, 960)[i % 3]
            block = np.empty((frames, 2), dtype=np.float32)
            engine._callback(block, frames, None, None)
            np.testing.assert_array_equal(block[:, 0], block[:, 1])
            chunks.append(block[:, 0].copy())
        for theme in ('Sport', 'Comfort', 'Deep'):
            engine.set_driving_parameters(60, 100, 1, 4, 'ready', SOUND_THEMES[theme])
            chunks.append(self.render(engine, 1))
        samples = np.concatenate(chunks)
        self.assertTrue(np.isfinite(samples).all())
        self.assertLess(np.max(np.abs(samples)), .5)
        self.assertLess(np.max(np.abs(np.diff(samples))), .08)
        self.assertGreater(np.max(np.abs(engine.traction_phases)), 0)

    def test_profile_search_preserves_response_and_scales_traction_pitch(self):
        base = SOUND_THEMES['Deep']
        controls = {key: .5 for key in GP_CONTROLS}
        low = profile_for(base, dict(controls, pitch_trajectory=0))
        high = profile_for(base, dict(controls, pitch_trajectory=1))
        for profile in (low, high):
            self.assertEqual(profile['traction_mix'], base['traction_mix'])
            self.assertEqual(profile['drive_cruise_gain'], base['drive_cruise_gain'])
        peaks = []
        for profile in (low, high):
            engine = SoundEngine(16000)
            engine.set_driving_parameters(45, 100, 1, 8, 'ready', profile)
            samples = self.render(engine, 4)[-16000:]
            spectrum = np.abs(np.fft.rfft(samples * np.hanning(len(samples))))
            peaks.append(np.argmax(spectrum))
        self.assertGreater(peaks[1], peaks[0] * 2)

    def test_response_validation_and_archived_profile_defaults(self):
        engine = SoundEngine(16000)
        for changes in ({'traction_mix': float('nan')}, {'drive_cruise_gain': -1},
                        {'traction_cycle_s': -1}, {'traction_cycle_s': 2.5, 'traction_crossfade_s': 2},
                        {'traction_sweep_hz': float('nan')},
                        {'traction_morph_mix': 1.1},
                        {'traction_stage_colour': -1},
                        {'electric_regen_richness': -1},
                        {'orchestral_mix': float('nan')},
                        {'drive_attack_s': 0}, {'acceleration_richness': 2}):
            with self.assertRaises(ValueError):
                engine.set_driving_parameters(50, 50, .5, 0, 'ready', dict(SOUND_THEMES['Deep'], **changes))
        archived = dict(base_hz=70., gain=.32, richness=.22, electric_mix=1.)
        engine.set_driving_parameters(50, 50, .5, 0, 'ready', archived)
        np.testing.assert_array_equal(engine.response_target, [1, 0, 0, 0])

    def test_sport_regen_is_richer_without_getting_louder(self):
        spectra, levels = [], []
        for richness in (0, SOUND_THEMES['Sport']['electric_regen_richness']):
            engine = SoundEngine(16000)
            profile = dict(SOUND_THEMES['Sport'], electric_regen_richness=richness)
            engine.set_driving_parameters(70, 0, -.8, -3, 'ready', profile)
            samples = self.render(engine, 4)[-16000:]
            self.assertLess(np.max(np.abs(samples)), .5)
            spectrum = np.abs(np.fft.rfft(samples * np.hanning(len(samples))))**2
            frequencies = np.fft.rfftfreq(len(samples), 1 / engine.sample_rate)
            fundamental = engine.electric_hz_target
            spectra.append(spectrum[(frequencies > 1.6 * fundamental) & (frequencies < 3.2 * fundamental)].sum())
            levels.append(np.std(samples))
        self.assertGreater(spectra[1], spectra[0] * 1.3)
        self.assertAlmostEqual(levels[1] / levels[0], 1, delta=.06)

    def test_deep_ensemble_adds_fifth_voice_with_controlled_high_frequencies(self):
        self.assertEqual(SOUND_THEMES['Deep']['traction_morph_mix'], 0)
        fifth_energy = []
        for mix in (0, SOUND_THEMES['Deep']['orchestral_mix']):
            engine = SoundEngine(16000)
            profile = dict(SOUND_THEMES['Deep'], orchestral_mix=mix)
            engine.set_driving_parameters(70, 100, .8, 4, 'ready', profile)
            samples = self.render(engine, 5)[-16000:]
            spectrum = np.abs(np.fft.rfft(samples * np.hanning(len(samples))))**2
            frequencies = np.fft.rfftfreq(len(samples), 1 / engine.sample_rate)
            fifth_energy.append(spectrum[np.abs(frequencies - 1.5 * engine.electric_hz_target) < 3].sum())
            self.assertLess(np.max(np.abs(samples)), .5)
            self.assertLess(spectrum[frequencies > 1000].sum() / spectrum.sum(), .02)
        self.assertGreater(fifth_energy[1], fifth_energy[0] * 3)

    def test_timed_phrase_repeats_same_sweep_with_slow_normalized_crossfades(self):
        positions = np.linspace(.48, 4, 35201)
        age, weights = SoundEngine.traction_cycle_envelopes(positions, 1.20 / 2.5)
        self.assertTrue(np.all(weights >= 0))
        np.testing.assert_allclose((weights**2).sum(axis=0), 1, atol=1e-12)
        self.assertLess(np.max(np.abs(np.diff(weights, axis=1))), .001)
        age, weights = SoundEngine.traction_cycle_envelopes(np.array([.5, 1.5, 2.5]), .24)
        np.testing.assert_allclose(np.sum(np.clip(age, 0, 1) * weights, axis=0), [.5, .5, .5])

    def test_deep_crossfade_has_no_audible_level_hole(self):
        for morph in (0, 1):
            engine = SoundEngine(16000)
            engine.traction_crossfade_seconds = 1.2
            engine.traction_sweep_hz = 55
            engine.traction_morph_mix = morph
            engine.traction_stage_colour = 1
            size = 8 * engine.sample_rate
            samples = engine._render_traction_cycle(np.ones(size), np.full(size, 90.),
                                                    np.full(size, 650.), np.full(size, .22))
            levels = [np.std(block) for block in samples[3 * engine.sample_rate:].reshape(-1, 1600)]
            self.assertLess(max(levels) / min(levels), 1.25)

    def test_phrase_morph_has_one_tonal_anchor_at_handover(self):
        engine = SoundEngine(16000)
        engine.traction_cycle_position = 1.24
        engine.traction_crossfade_seconds = 1.2
        engine.traction_sweep_hz = 55
        engine.traction_morph_mix = 1
        engine.traction_cycle_controls = np.array([2.5, 1.2, 55., 1., 0.])
        size = engine.sample_rate
        samples = engine._render_traction_cycle(np.zeros(size), np.full(size, 90.),
                                                np.full(size, 650.), np.full(size, .22))
        age, weights = engine.traction_cycle_envelopes(np.array([1.24]), .48)
        rise = np.clip(age, 0, 1)
        rise = rise * rise * (3 - 2 * rise)
        expected_hz = float(np.sum(weights**2 * (130 + 55 * rise)))
        spectrum = np.abs(np.fft.rfft(samples * np.hanning(len(samples))))**2
        frequencies = np.fft.rfftfreq(size, 1 / engine.sample_rate)
        anchor_energy = spectrum[np.abs(frequencies - expected_hz) < 4].sum()
        self.assertGreater(anchor_energy / spectrum.sum(), .95)

    def test_new_deep_phrase_has_a_distinct_upper_tone(self):
        engine = SoundEngine(16000)
        engine.traction_crossfade_seconds = 1.2
        engine.traction_sweep_hz = 55
        engine.traction_stage_colour = 1
        engine.traction_cycle_controls = np.array([2.5, 1.2, 55., 0., 1.])
        rate = engine.sample_rate
        samples = engine._render_traction_cycle(np.ones(5 * rate), np.full(5 * rate, 90.),
                                                np.full(5 * rate, 650.), np.full(5 * rate, .22))

        def upper_ratio(segment):
            spectrum = np.abs(np.fft.rfft(segment * np.hanning(len(segment))))**2
            frequencies = np.fft.rfftfreq(len(segment), 1 / rate)
            return spectrum[(frequencies > 350) & (frequencies < 600)].sum() / spectrum[(frequencies > 100) & (frequencies < 250)].sum()

        first = samples[int(1.5 * rate):int(1.9 * rate)]
        second = samples[int(4.0 * rate):int(4.4 * rate)]
        self.assertGreater(upper_ratio(second), upper_ratio(first) * 3)
        self.assertLess(np.max(np.abs(np.diff(samples))), .08)

    def test_full_throttle_phrase_interval_light_pedal_and_coast_pause(self):
        archived = dict(SOUND_THEMES['Deep'], traction_cycle_s=2.5, traction_mix=.72)
        positions = []
        for pedal in (100, 50):
            engine = SoundEngine(16000)
            engine.set_driving_parameters(70, pedal, 1, 4, 'ready', archived)
            self.render(engine, 5.2)
            positions.append(engine.traction_cycle_position)
        self.assertAlmostEqual(positions[0], 2, delta=.08)
        self.assertLess(positions[1], positions[0] * .5)
        engine.set_driving_parameters(70, 0, 0, 0, 'ready', archived)
        self.render(engine, 4)
        paused = engine.traction_cycle_position
        self.render(engine, 1)
        self.assertAlmostEqual(engine.traction_cycle_position, paused, places=7)
        engine.set_driving_parameters(0, 0, 0, 0, 'ready', archived)
        self.render(engine, 6)
        self.assertEqual(engine.traction_cycle_position, 0)

    def test_timed_phrase_repetitions_and_archived_deep_switch_have_no_clicks(self):
        engine = SoundEngine(48000)
        profile = dict(SOUND_THEMES['Deep'], traction_cycle_s=2.5, traction_mix=.72)
        engine.set_driving_parameters(70, 100, 1, 4, 'ready', profile)
        chunks = [self.render(engine, 9)]
        archived = {key: value for key, value in profile.items()
                    if key not in ('traction_cycle_s', 'traction_crossfade_s')}
        for selected in (archived, dict(profile, traction_morph_mix=1), profile):
            engine.set_driving_parameters(70, 100, 1, 4, 'ready', selected)
            chunks.append(self.render(engine, 1))
        samples = np.concatenate(chunks)
        self.assertTrue(np.isfinite(samples).all())
        self.assertLess(np.max(np.abs(samples)), .5)
        self.assertLess(np.max(np.abs(np.diff(samples))), .08)

    def test_deep_variable_callback_sizes_sample_rates_and_reset(self):
        for rate in (8000, 44100, 48000):
            engine = SoundEngine(rate)
            engine.set_driving_parameters(200, 100, 1, 8, 'ready', SOUND_THEMES['Deep'])
            for frames in (64, 256, 1024, 2048, 0):
                block = np.empty((frames, 1), dtype=np.float32)
                engine._callback(block, frames, None, None)
                self.assertTrue(np.isfinite(block).all())
                if frames:
                    self.assertLess(np.max(np.abs(block)), .5)
            engine._reset()
            np.testing.assert_array_equal(engine.traction_phases, np.zeros(4))
            np.testing.assert_array_equal(engine.traction_cycle_phases, np.zeros(2))
            np.testing.assert_array_equal(engine.orchestral_phases, np.zeros((3, 3)))
            self.assertEqual(engine.traction_cycle_position, 0)
            self.assertEqual(engine.traction_morph_phase, 0)
            self.assertEqual(engine.sound_speed, 0)


if __name__ == '__main__':
    unittest.main()
