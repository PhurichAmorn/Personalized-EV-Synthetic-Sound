import math
import unittest

import numpy as np

from audio import SOUND_RECIPES, SoundEngine
from experiment.recipes import (
    PROBE_GROUP_FIELDS, PROBE_GROUPS, RECIPE_BASES, RECIPE_NAMES, mode_bounds, probe_profile, recipe_probe_groups,
    recipe_bounds, recipe_controls, recipe_ids, recipe_profile,
)


class RecipeTests(unittest.TestCase):
    def test_probe_group_centers_preserve_recipe_and_share_mode_bounds(self):
        self.assertEqual(PROBE_GROUPS, ('register', 'tone', 'response', 'regen'))
        for mode in SOUND_RECIPES:
            bounds = mode_bounds(mode)
            self.assertEqual(set(bounds), set(PROBE_GROUPS))
            for recipe_id in recipe_ids(mode):
                groups = recipe_probe_groups(recipe_id)
                center = {group: .5 for group in groups}
                self.assertEqual(probe_profile(mode, recipe_id, center), SOUND_RECIPES[mode][RECIPE_NAMES[mode][recipe_id]])
                for group, fields in bounds.items():
                    self.assertTrue(fields)
                    for field, (low, high) in fields.items():
                        self.assertLessEqual(low, high)

    def test_mode_bounds_union_recipe_windows_instead_of_locking_to_one_recipe(self):
        for mode in SOUND_RECIPES:
            bounds = mode_bounds(mode)
            for group, fields in PROBE_GROUP_FIELDS.items():
                for field in fields:
                    values = []
                    for recipe_id in recipe_ids(mode):
                        base = RECIPE_BASES[recipe_id]
                        if field in base:
                            values.append(recipe_bounds(recipe_id).get(field, (base[field], base[field])))
                    if values:
                        self.assertEqual(bounds[group][field],
                                         (min(value[0] for value in values), max(value[1] for value in values)))
        self.assertLess(mode_bounds('Comfort')['register']['electric_pitch_offset'][0],
                        recipe_bounds('comfort_clean_v1')['electric_pitch_offset'][0])

    def test_probe_groups_change_only_mapped_fields_within_mode_bounds(self):
        for mode in SOUND_RECIPES:
            for recipe_id in recipe_ids(mode):
                groups = recipe_probe_groups(recipe_id)
                center = {group: .5 for group in groups}
                original = probe_profile(mode, recipe_id, center)
                bounds = mode_bounds(mode)
                for group in groups:
                    for endpoint in (0., 1.):
                        controls = dict(center, **{group: endpoint})
                        profile = probe_profile(mode, recipe_id, controls)
                        changed = {key for key, value in profile.items() if value != original[key]}
                        self.assertTrue(changed)
                        self.assertTrue(changed <= set(PROBE_GROUP_FIELDS[group]), (mode, recipe_id, group, changed))
                        for key in changed:
                            low, high = bounds[group][key]
                            self.assertLessEqual(low, profile[key], (mode, recipe_id, group, key))
                            self.assertLessEqual(profile[key], high, (mode, recipe_id, group, key))

    def test_probe_group_endpoints_render_distinct_outputs(self):
        scenarios = {
            'register': (80, 60, .6, 1.2),
            'tone': (80, 60, .6, 1.2),
            'response': (60, 90, .8, 3.0),
            'regen': (70, 0, -.6, -2.0),
        }

        def render(profile, scenario):
            engine = SoundEngine(48000)
            engine.set_driving_parameters(*scenario, 'ready', profile)
            output = np.empty((48000, 1), dtype=np.float32)
            engine._callback(output, len(output), None, None)
            return output[:, 0]

        for mode in SOUND_RECIPES:
            for recipe_id in recipe_ids(mode):
                for group in recipe_probe_groups(recipe_id):
                    low = {name: .5 for name in recipe_probe_groups(recipe_id)}
                    high = dict(low)
                    low[group], high[group] = 0., 1.
                    low_audio = render(probe_profile(mode, recipe_id, low), scenarios[group])
                    high_audio = render(probe_profile(mode, recipe_id, high), scenarios[group])
                    difference = np.sqrt(np.mean((low_audio - high_audio) ** 2))
                    self.assertGreater(difference, .004, (mode, recipe_id, group, difference))
                    self.assertLess(max(np.max(np.abs(low_audio)), np.max(np.abs(high_audio))), .45,
                                    (mode, recipe_id, group))

    def test_probe_profiles_reject_unknown_modes_and_invalid_controls(self):
        recipe_id = recipe_ids('Sport')[0]
        center = {group: .5 for group in recipe_probe_groups(recipe_id)}
        for invalid in (-.1, 1.1, math.nan, True):
            controls = dict(center, register=invalid)
            with self.assertRaises(ValueError):
                probe_profile('Sport', recipe_id, controls)
        with self.assertRaisesRegex(ValueError, 'Unknown sound mode'):
            mode_bounds('unknown')
        with self.assertRaisesRegex(ValueError, 'Unknown sound recipe'):
            recipe_probe_groups('unknown_v1')
        with self.assertRaisesRegex(ValueError, 'Unknown sound recipe for mode'):
            probe_profile('Comfort', recipe_id, center)
        with self.assertRaisesRegex(ValueError, 'Invalid probe controls'):
            probe_profile('Sport', 'sport_ice_v1', {'register': .5, 'tone': .5, 'response': .5, 'regen': .5})

    def test_six_versioned_recipes_match_dashboard_previews(self):
        self.assertEqual(tuple(map(len, (recipe_ids(mode) for mode in SOUND_RECIPES))), (2, 2, 2))
        for mode, ids in ((mode, recipe_ids(mode)) for mode in SOUND_RECIPES):
            for recipe_id, preview in zip(ids, SOUND_RECIPES[mode].values()):
                self.assertTrue(recipe_id.endswith('_v1'))
                center = {name: .5 for name in recipe_controls(recipe_id)}
                self.assertEqual(recipe_profile(recipe_id, center), preview)

    def test_linked_controls_stay_inside_physical_windows(self):
        for mode in SOUND_RECIPES:
            for recipe_id in recipe_ids(mode):
                groups = recipe_controls(recipe_id)
                bounds = recipe_bounds(recipe_id)
                self.assertTrue(groups)
                for value in (0., .5, 1.):
                    profile = recipe_profile(recipe_id, {group: value for group in groups})
                    for key, (low, high) in bounds.items():
                        self.assertLessEqual(low, profile[key], (recipe_id, key))
                        self.assertLessEqual(profile[key], high, (recipe_id, key))
                    self.assertEqual(profile.get('electric_whirl', 0), 0)
                    self.assertEqual(profile.get('electric_pulse', 0), 0)
                    self.assertEqual(profile.get('electric_shimmer', 0), 0)
                    engine = SoundEngine()
                    for speed, pedal, load, acceleration in ((0, 80, .7, 2), (40, 60, .6, 1),
                                                               (120, 70, .8, 3), (70, 0, -.6, -2),
                                                               (220, 100, .8, 3)):
                        engine.set_driving_parameters(speed, pedal, load, acceleration, 'ready', profile)
                    if profile.get('order_synthesis'):
                        self.assertLess(4 * engine.order_synth.request[0] / 60, 600)
                    else:
                        self.assertLess(engine.electric_hz_target, 400)

    def test_window_extremes_render_with_headroom_and_continuity(self):
        for mode in SOUND_RECIPES:
            for recipe_id in recipe_ids(mode):
                for point in (0., 1.):
                    profile = recipe_profile(recipe_id, {group: point for group in recipe_controls(recipe_id)})
                    engine = SoundEngine(48000)
                    blocks = []
                    for speed, pedal, load, acceleration in ((40, 35, .35, .5), (110, 85, .8, 3),
                                                               (70, 0, -.5, -2)):
                        for _ in range(150):
                            engine.set_driving_parameters(speed, pedal, load, acceleration, 'ready', profile)
                            block = np.empty((480, 1), dtype=np.float32)
                            engine._callback(block, 480, None, None)
                            blocks.append(block[:, 0].copy())
                    samples = np.concatenate(blocks)
                    self.assertTrue(np.isfinite(samples).all())
                    self.assertLess(np.max(np.abs(samples)), .45, recipe_id)
                    self.assertLess(np.max(np.abs(np.diff(samples))), .15, recipe_id)

    def test_switching_electric_to_ice_recipe_is_smooth(self):
        engine = SoundEngine(48000)
        samples = []
        for name in ('Electric Sport', 'ICE Inspired', 'Electric Sport'):
            for _ in range(150):
                engine.set_driving_parameters(80, 70, .7, 2, 'ready', SOUND_RECIPES['Sport'][name])
                block = np.empty((480, 1), dtype=np.float32)
                engine._callback(block, 480, None, None)
                samples.append(block[:, 0].copy())
        audio = np.concatenate(samples)
        self.assertLess(np.max(np.abs(audio)), .45)
        self.assertLess(np.max(np.abs(np.diff(audio))), .15)

    def test_rejects_invalid_controls_and_keeps_preview_immutable(self):
        recipe_id = recipe_ids('Deep')[1]
        baseline = dict(SOUND_RECIPES['Deep']['Orchestral Rise'])
        groups = recipe_controls(recipe_id)
        controls = {group: .5 for group in groups}
        for invalid in (-.1, 1.1, math.nan, True):
            with self.assertRaises(ValueError):
                recipe_profile(recipe_id, dict(controls, register=invalid))
        with self.assertRaises(ValueError):
            recipe_profile(recipe_id, {'register': .5})
        with self.assertRaises(ValueError):
            recipe_ids('unknown')
        self.assertEqual(SOUND_RECIPES['Deep']['Orchestral Rise'], baseline)


if __name__ == '__main__':
    unittest.main()
