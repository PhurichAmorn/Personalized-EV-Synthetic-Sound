import json
from pathlib import Path
import random
import tempfile
import unittest
from unittest.mock import Mock
from unittest.mock import patch

from PySide6.QtCore import QCoreApplication
from audio import SOUND_THEMES
from experiment.recipes import (PROBE_GROUP_FIELDS, mode_bounds, recipe_bounds, recipe_controls,
                                recipe_ids, recipe_profile, probe_profile, recipe_probe_groups)
from experiment.live_search import (LiveSearch, CONTROLS, GP_CONTROLS, COMFORT_CONTROLS,
                                    CHARACTER_CONTROLS, profile_for, preset_profile_for,
                                    preset_controls_for)


class LiveSearchTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QCoreApplication.instance() or QCoreApplication([])

    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        from simulation.vehicle_model import VehicleModel
        self.controller = Mock(car=VehicleModel.from_name("Compact EV"), selectedVehicle='Compact EV', running=False)
        from audio import SoundEngine
        self.controller.audio = SoundEngine()
        self.search = LiveSearch(self.controller, root=Path(self.directory.name))

    def tearDown(self):
        self.search.monitor.stop()
        self.directory.cleanup()

    def rate_pair(self, a=6, b=3):
        self.search.choose('A')
        self.search.rate('A', a)
        self.search.choose('B')
        self.search.rate('B', b)
        self.search.next()

    def prefer_recipe_pair(self, preference='B'):
        self.search.choose('A')
        self.search.choose('B')
        self.search.ratePreference(preference)
        self.search.next()

    def test_new_methods_share_four_controlled_opening_probes(self):
        for method in ('evolutionary', 'gp_preference', 'recipe_preference'):
            with self.subTest(method=method):
                self.search.start('Pilot', 'Comfort', method)
                data = self.search.data
                self.assertEqual(len(data['initial']), 8)
                self.assertEqual(data['probe_version'], 2)
                self.assertEqual(data['mode'], 'Comfort')
                candidates = data['candidates']
                expected = ('mode_character', 'register', 'tone', 'response')
                for index, probe_id in enumerate(expected):
                    pair = [candidates[ident] for ident in data['initial'][2*index:2*index+2]]
                    self.assertEqual({item['probe_id'] for item in pair}, {probe_id})
                    self.assertEqual({item['mode'] for item in pair}, {'Comfort'})
                    self.assertTrue(all(item['physical_bounds'] == mode_bounds('Comfort') for item in pair))
                    if index:
                        a, b = pair
                        self.assertEqual(a['recipe_id'], b['recipe_id'])
                        group = probe_id
                        self.assertEqual({a['group_values'][group], b['group_values'][group]}, {0., 1.})
                        self.assertTrue(all(a['group_values'][key] == b['group_values'][key]
                                            for key in a['group_values'] if key != group))
                        changed = {key for key in a['profile'] if a['profile'][key] != b['profile'][key]}
                        self.assertLessEqual(changed, set(PROBE_GROUP_FIELDS[group]))
                self.search.finish(False)

    def test_new_search_tunes_one_linked_group_per_pair_within_mode_bounds(self):
        self.search.start('Pilot', 'Sport', 'gp_preference')
        for _ in range(4):
            self.search.choose('A')
            self.search.choose('B')
            self.search.ratePreference('A')
            self.search.next()
        pair = [self.search.data['candidates'][ident] for ident in self.search.data['pair'].values()]
        self.assertEqual(self.search.data['active_probe']['id'], 'tune_register')
        self.assertEqual(len({candidate['recipe_id'] for candidate in pair}), 1)
        a, b = pair
        changed = {key for key in a['profile'] if a['profile'][key] != b['profile'][key]}
        self.assertLessEqual(changed, set(PROBE_GROUP_FIELDS['register']))
        self.assertTrue(all(candidate['physical_bounds'] == mode_bounds('Sport') for candidate in pair))

    def test_recipe_preference_search_uses_shared_probe_stages(self):
        self.search.start('Pilot', 'Sport', 'recipe_preference')
        self.assertEqual(self.search.data['algorithm'], 'recipe-pairwise-v2')
        self.assertEqual({self.search.data['candidates'][ident]['recipe_id']
                          for ident in self.search.data['pair'].values()}, set(recipe_ids('Sport')))
        for number in range(1, 21):
            self.assertEqual(self.search.pairNumber, number)
            for ident in self.search.data['pair'].values():
                candidate = self.search.data['candidates'][ident]
                self.assertEqual(candidate['profile'], probe_profile(
                    'Sport', candidate['recipe_id'],
                    {key: candidate['controls'][key] for key in recipe_probe_groups(candidate['recipe_id'])}))
                self.assertEqual(candidate['recipe_version'], 2)
                self.assertTrue(candidate['physical_bounds'])
            self.prefer_recipe_pair()
        self.assertEqual(self.search.checkpoint, 'cap')
        self.assertEqual(len(self.search.data['history']), 20)

    def test_recipe_preference_neither_replaces_pair_without_consuming_turn(self):
        self.search.start('Pilot', 'Deep', 'recipe_preference')
        original = set(self.search.data['pair'].values())
        self.search.choose('A')
        self.search.choose('B')
        self.search.rejectBoth()
        self.assertEqual(self.search.data['completed'], 0)
        self.assertTrue(original.isdisjoint(self.search.data['pair'].values()))
        self.assertEqual(self.search.data['skipped_pairs'][0]['reason'], 'neither')

    def test_recipe_preference_neither_does_not_restore_rejected_incumbent(self):
        self.search.start('Pilot', 'Deep', 'recipe_preference')
        for _ in range(4):
            self.prefer_recipe_pair()
        old_incumbent = self.search.data['incumbent']
        self.search.choose('A')
        self.search.choose('B')
        rejected = set(self.search.data['pair'].values())
        self.search.rejectBoth()
        self.assertTrue(rejected.issubset(self.search.data['rejected']))
        self.assertNotIn(old_incumbent, self.search.data['pair'].values())
        self.prefer_recipe_pair('equal')
        self.assertNotIn(old_incumbent, self.search.data['pair'].values())

    def test_recipe_preference_restores_exact_pair_and_saved_profiles(self):
        self.search.start('Pilot', 'Comfort', 'recipe_preference')
        for _ in range(5):
            self.prefer_recipe_pair('equal')
        saved_pair = dict(self.search.data['pair'])
        saved_profiles = {ident: dict(candidate['profile']) for ident, candidate in self.search.data['candidates'].items()}
        session_id = self.search.data['id']
        self.search.finish(False)
        self.search.restore(session_id)
        self.assertTrue(self.search.active)
        self.assertEqual(self.search.data['pair'], saved_pair)
        self.assertEqual({ident: candidate['profile'] for ident, candidate in self.search.data['candidates'].items()},
                         saved_profiles)

    def test_recipe_preference_uses_recorded_review_gain(self):
        self.search.start('Pilot', 'Sport', 'recipe_preference')
        for slot, ident in self.search.data['pair'].items():
            self.search.choose(slot)
            recipe_id = self.search.data['candidates'][ident]['recipe_id']
            self.assertAlmostEqual(self.search.volume, .38 if recipe_id == 'sport_electric_v1' else 1.)

    def test_search_blocks_resume_and_favorite(self):
        self.search.start('Pilot', 'Comfort')
        self.assertEqual(len(self.search.data['candidates']), 8)
        self.assertEqual(len(self.search.data['survivors']), 0)
        for _ in range(3):
            self.rate_pair()
        self.assertEqual(self.search.data['active_probe']['id'], 'response')
        self.rate_pair()
        parent = self.search.data['parent']
        self.search.choose('A')
        self.search.rate('A', 4)
        self.search.choose('B')
        self.search.rate('B', 4)
        self.search.next()
        self.assertIn(parent, self.search.data['pair'].values())
        for _ in range(5):
            self.rate_pair()
        self.assertEqual(self.search.checkpoint, '')
        self.assertEqual(self.search.data['completed'], 10)
        self.assertEqual(len(self.search.traceSession(self.search.data['id'])['comparisons']), 11)
        for _ in range(10):
            self.rate_pair()
        self.assertEqual(self.search.checkpoint, 'cap')
        self.search.finish(True, 'B')
        self.assertFalse(self.search.active)
        favorite = self.search.data['favorite']
        ident = self.search.data['id']
        expected = self.search.profile
        self.search.restore(ident, False)
        self.assertTrue(self.search.active)
        self.assertEqual(self.search.checkpoint, 'cap')
        self.search.continueBlock()
        self.assertEqual(self.search.data['block_end'], 40)
        self.assertEqual(self.search.data['favorite'], favorite)
        self.search.finish(False)
        self.search.restore(ident, True)
        self.assertFalse(self.search.active)
        self.assertEqual(self.search.profile, expected)
        self.assertEqual(len(self.search.sessions('pilot')), 1)
        self.assertEqual(self.search.sessions('../other'), [])
        stored = json.loads(self.search.path.read_text())
        self.assertEqual(stored['favorite'], favorite)
        for c in stored['candidates'].values():
            self.assertEqual(set(c['controls']), set(PROBE_GROUP_FIELDS))
            self.assertEqual(c['profile']['gain'], SOUND_THEMES['Comfort']['gain'])

    def test_satisfaction_requires_explicit_favorite_sound(self):
        self.search.start('Pilot', 'Deep', 'gp_preference')
        self.search.choose('A')
        self.search.finish(True, 'A')
        self.assertTrue(self.search.active)
        self.search.choose('B')
        preferred = self.search.data['pair']['A']
        self.search.finish(True)
        self.assertTrue(self.search.active)
        self.assertIsNone(self.search.data['favorite'])
        self.search.finish(True, 'A')
        self.assertFalse(self.search.active)
        self.assertEqual(self.search.data['favorite'], preferred)
        self.assertEqual(self.search.data['playing'], preferred)
        self.assertEqual(self.search.data['endings'][-1]['favorite_slot'], 'A')
        trace = self.search.traceSession(self.search.data['id'])
        self.assertEqual(trace['favorite_slot'], 'A')
        self.assertEqual(trace['comparisons'][-1]['final_choice'], 'A')

    def test_failed_save_does_not_advance_or_lose_ratings(self):
        from unittest.mock import patch
        self.search.start('Pilot', 'Deep')
        self.search.choose('A'); self.search.rate('A', 5)
        self.search.choose('B'); self.search.rate('B', 4)
        with patch('experiment.live_search.os.replace', side_effect=OSError('disk full')):
            self.search.next()
        self.assertEqual(self.search.data['completed'], 0)
        self.assertEqual(self.search.ratingA, 5)
        self.assertIn('disk full', self.search.error)
        self.search.next()
        self.assertEqual(self.search.data['completed'], 1)

    def test_evolutionary_carries_a_repeated_sounds_score(self):
        self.search.start('Pilot', 'Deep', 'evolutionary')
        for _ in range(5):
            self.rate_pair(6, 2)
        first_winner = self.search.data['history'][4]['winner']
        slot = next(slot for slot, ident in self.search.data['pair'].items() if ident == first_winner)
        other = 'B' if slot == 'A' else 'A'
        self.assertEqual(self.search.data['ratings'][slot], 6)
        self.assertEqual(self.search.ratingSources[slot], 5)
        self.assertEqual(self.search.data['ratings'][other], 0)
        self.assertFalse(self.search.feedbackReady)
        self.search.choose(other)
        self.search.rate(other, 7)
        self.assertTrue(self.search.feedbackReady)
        self.search.next()
        history = self.search.data['history'][-1]
        self.assertEqual(history['rating_sources'][slot], 5)
        self.assertEqual(history['winner'], history['pair'][other])

    def test_evolutionary_needs_both_scores_and_accepts_an_old_pairwise_pair(self):
        self.search.start('Pilot', 'Deep', 'evolutionary')
        self.search.choose('A')
        self.search.rate('A', 6)
        self.search.next()
        self.assertEqual(self.search.data['completed'], 0)
        self.search.choose('B')
        self.search.rate('B', 3)
        self.search.next()
        self.assertEqual(self.search.data['history'][0]['ratings'], {'A': 6, 'B': 3})
        self.search.choose('A')
        self.search.choose('B')
        self.search.ratePreference('B')
        self.search.next()
        self.assertEqual(self.search.data['history'][1]['preference'], 'B')

    def test_too_similar_replaces_candidate_without_counting_a_comparison(self):
        self.search.start('Pilot', 'Deep', 'evolutionary')
        original = dict(self.search.data['pair'])
        self.search.choose('A')
        self.search.choose('B')
        anchor = self.search.data['initial'][0]
        original_slot = next(slot for slot, ident in original.items() if ident == anchor)
        self.search.rate(original_slot, 6)
        self.search.retrySimilar()
        d = self.search.data
        self.assertEqual(d['completed'], 0)
        self.assertEqual(d['history'], [])
        self.assertEqual(len(d['skipped_pairs']), 1)
        self.assertEqual(d['skipped_pairs'][0]['pair'], original)
        self.assertEqual(d['candidates'][d['playing']]['kind'], 'similarity-retry')
        self.assertIn(d['candidates'][d['playing']]['parents'][0], d['pair'].values())
        retained_slot = next(slot for slot, ident in d['pair'].items() if ident == anchor)
        self.assertEqual(d['ratings'][retained_slot], 6)
        self.search.retrySimilar()
        self.assertEqual(len(self.search.data['skipped_pairs']), 2)
        self.assertNotEqual(self.search.data['playing'], d['playing'])

    def test_gp_neither_replaces_both_without_counting_or_reusing_them(self):
        self.search.start('Pilot', 'Deep', 'gp_preference')
        original = set(self.search.data['pair'].values())
        self.search.choose('A')
        self.search.rejectBoth()
        self.assertEqual(set(self.search.data['pair'].values()), original)
        self.search.choose('B')
        self.search.rejectBoth()
        self.assertEqual(self.search.data['completed'], 0)
        self.assertEqual(self.search.data['history'], [])
        self.assertTrue(original.isdisjoint(self.search.data['pair'].values()))
        self.assertEqual(set(self.search.data['rejected']), original)
        self.assertEqual(self.search.data['skipped_pairs'][0]['reason'], 'neither')
        self.assertEqual(self.search.pairNumber, 1)
        for _ in range(6):
            self.search.choose('A')
            self.search.choose('B')
            self.search.ratePreference('B')
            self.search.next()
            self.assertTrue(original.isdisjoint(self.search.data['pair'].values()))

    def test_gp_runs_probe_tune_combine_challenge_and_refine_stages(self):
        with patch('experiment.live_search.secrets.randbits', return_value=12345):
            self.search.start('Pilot', 'Deep', 'gp_preference')
        expected = ['mode_character', 'register', 'tone', 'response',
                    'tune_register', 'tune_tone', 'tune_response', 'tune_regen',
                    'tune_register', 'tune_tone', 'tune_response', 'tune_regen',
                    'tune_register', 'tune_tone', 'combine', 'combine', 'combine',
                    'branch_challenge', 'refine_register', 'refine_tone']
        for probe_id in expected:
            self.assertEqual(self.search.data['active_probe']['id'], probe_id)
            self.search.choose('A'); self.search.choose('B')
            self.search.ratePreference('B'); self.search.next()
        self.assertEqual(self.search.checkpoint, 'cap')

    def test_gp_combine_and_branch_challenge_cross_recipe_families(self):
        with patch('experiment.live_search.secrets.randbits', return_value=12345):
            self.search.start('Pilot', 'Sport', 'gp_preference')
        for _ in range(14):
            self.search.choose('A'); self.search.choose('B')
            self.search.ratePreference('A'); self.search.next()
        pair = [self.search.data['candidates'][ident] for ident in self.search.data['pair'].values()]
        self.assertEqual({candidate['kind'] for candidate in pair}, {'probe-combination'})
        self.assertEqual({candidate['probe_id'] for candidate in pair}, {'combine'})
        self.assertEqual(len({candidate['recipe_id'] for candidate in pair}), 2)
        for _ in range(3):
            self.search.choose('A'); self.search.choose('B')
            self.search.ratePreference('B'); self.search.next()
        self.assertEqual(self.search.data['active_probe']['id'], 'branch_challenge')
        challenge = [self.search.data['candidates'][ident] for ident in self.search.data['pair'].values()]
        self.assertIn('probe-branch-challenge', {candidate['kind'] for candidate in challenge})

    def test_gp_ties_leave_features_unresolved_and_continue_with_model(self):
        with patch('experiment.live_search.secrets.randbits', return_value=12345):
            self.search.start('Pilot', 'Comfort', 'gp_preference')
        for _ in range(20):
            self.search.choose('A'); self.search.choose('B')
            self.search.ratePreference('equal'); self.search.next()
        self.assertEqual(self.search.data['probe_winners'], {})
        self.assertEqual(self.search.checkpoint, 'cap')

    def test_deep_opening_compares_recipe_bases_without_modulation_sweeps(self):
        self.search.start('Pilot', 'Deep', 'evolutionary')
        seed, opening = (self.search.data['candidates'][ident] for ident in self.search.data['initial'][:2])
        self.assertEqual(seed['controls'], opening['controls'])
        self.assertEqual(seed['probe_id'], 'mode_character')
        self.assertNotEqual(seed['recipe_id'], opening['recipe_id'])
        self.assertEqual(self.search.data['active_probe']['id'], 'mode_character')

    def test_delete_empty_active_session_and_block_active_with_comparisons(self):
        self.search.start('Pilot', 'Deep')
        ident = self.search.data['id']
        path = self.search.path.parent
        self.assertTrue(self.search.deleteSession(ident))
        self.assertFalse(path.exists())
        self.assertIsNone(self.search.data)
        self.search.start('Pilot', 'Deep')
        ident = self.search.data['id']
        path = self.search.path.parent
        self.rate_pair()
        self.assertFalse(self.search.deleteSession(ident))
        self.assertTrue(path.exists())
        self.search.finish(False)
        self.assertTrue(self.search.deleteSession(ident))
        self.assertFalse(path.exists())
        self.assertIsNone(self.search.data)
        self.assertFalse(self.search.traceSessions())
        self.assertFalse(self.search.deleteSession('../bad'))

    def test_discard_removes_current_session_and_shutdown_does_not_recreate_it(self):
        self.search.start('Pilot', 'Deep')
        path = self.search.path
        self.search.choose('A')
        self.assertTrue(path.exists())
        self.assertTrue(self.search.discard())
        self.assertFalse(self.search.active)
        self.assertFalse(path.exists())
        self.search.close()
        self.assertFalse(path.exists())

    def test_gp_warmup_adaptive_pairing_checkpoints_and_resume(self):
        self.search.start('Pilot', 'Deep', 'gp_preference')
        seen = set()
        for comparison in range(20):
            if comparison == 9:
                rejected_pair = set(self.search.data['pair'].values())
                self.search.choose('A'); self.search.choose('B')
                self.search.rejectBoth()
                self.assertEqual(self.search.pairNumber, 10)
                self.assertEqual(self.search.data['completed'], 9)
                self.assertTrue(rejected_pair.isdisjoint(self.search.data['pair'].values()))
            pair = tuple(sorted(self.search.data['pair'].values()))
            self.assertNotIn(pair, seen)
            seen.add(pair)
            self.search.choose('A')
            self.search.choose('B')
            self.search.ratePreference(('A', 'B', 'equal')[comparison % 3])
            self.search.next()
            self.assertEqual(self.search.data['completed'], comparison + 1)
            self.assertEqual(len(self.search.data['history']), comparison + 1)
            if comparison == 2:
                stored = json.loads(self.search.path.read_text())
                self.assertEqual([row['preference'] for row in stored['history']], ['A', 'B', 'equal'])
                ident = self.search.data['id']
                self.search.finish(False)
                self.search.restore(ident, False)
                self.assertTrue(self.search.active)
                self.assertEqual(self.search.data['history'], stored['history'])
                self.assertEqual(self.search.data['pair'], stored['pair'])
                self.assertEqual(self.search.data['incumbent'], stored['incumbent'])
        self.assertEqual(self.search.checkpoint, 'cap')
        self.search.continueBlock()
        self.assertEqual(self.search.data['block_end'], 40)
        self.assertEqual(self.search.checkpoint, '')
        self.assertEqual(self.search.preference, '')

    def test_gp_retains_incumbent_on_tie_and_replaces_only_with_winner(self):
        self.search.start('Pilot', 'Comfort', 'gp_preference')
        self.assertEqual(self.search.data['algorithm'], 'gp-preference-probe-v1')
        incumbent = None
        for number, score in enumerate(('equal', 'equal', 'equal', 'A', 'B', 'equal')):
            pair = dict(self.search.data['pair'])
            self.search.choose('A'); self.search.choose('B')
            self.search.ratePreference(score)
            expected = pair['A'] if score == 'A' else pair['B'] if score == 'B' else incumbent
            self.search.next()
            incumbent = expected
            self.assertEqual(self.search.data['incumbent'], incumbent)
            if number == 5:
                self.assertIn(incumbent, self.search.data['pair'].values())
            self.assertIsNone(self.search.data['favorite'])

    def test_old_gp_session_resumes_with_legacy_pairing(self):
        self.search.start('Pilot', 'Sport', 'gp_preference')
        d = self.search.data
        d['algorithm'] = 'gp-preference-active-v1'
        d['control_keys'] = GP_CONTROLS
        d['baseline_controls'] = dict.fromkeys(GP_CONTROLS, .5)
        d['bounds'] = {key: [0., 1.] for key in GP_CONTROLS}
        d.pop('incumbent', None)
        d['candidates'] = {}
        d['initial'] = []
        for index in range(6):
            controls = dict.fromkeys(GP_CONTROLS, .5)
            controls[GP_CONTROLS[index % len(GP_CONTROLS)]] = 0. if index % 2 else 1.
            d['initial'].append(self.search._candidate(d, controls, kind='legacy-opening'))
        self.search._pair(d, d['initial'][:2], random.Random(0))
        self.search._commit(d)
        self.search.finish(False)
        self.search.restore(d['id'], False)
        for _ in range(3):
            self.search.choose('A'); self.search.choose('B')
            self.search.ratePreference('B')
            self.search.next()
        self.assertEqual(self.search.data['algorithm'], 'gp-preference-active-v1')
        self.assertNotIn('incumbent', self.search.data)

    def test_prior_character_gp_session_keeps_old_pair_schedule(self):
        self.search.start('Pilot', 'Sport', 'gp_preference')
        d = self.search.data
        d['algorithm'] = 'gp-character-v1'
        d['control_keys'] = CHARACTER_CONTROLS
        controls = preset_controls_for(d['base'])
        d['baseline_controls'] = controls
        d['bounds'] = {key: [0., 1.] for key in CHARACTER_CONTROLS}
        d['candidates'] = {}
        d['initial'] = []
        for index in range(6):
            variant = dict(controls)
            key = CHARACTER_CONTROLS[index % len(CHARACTER_CONTROLS)]
            variant[key] = 0. if index % 2 else 1.
            d['initial'].append(self.search._candidate(d, variant, kind='feature-contrast'))
        d['incumbent'] = d['initial'][0]
        self.search._pair(d, d['initial'][:2], random.Random(0))
        ident = d['id']
        self.search._commit(d)
        self.search.finish(False)
        self.search.restore(ident, False)
        self.search.choose('A'); self.search.choose('B')
        self.search.ratePreference('A')
        winner = self.search.data['pair']['A']
        self.search.next()
        self.assertEqual(self.search.data['algorithm'], 'gp-character-v1')
        self.assertEqual(set(self.search.data['pair'].values()), {winner, d['initial'][2]})

    def test_every_mode_and_method_starts_with_distinct_character_options(self):
        for mode in SOUND_THEMES:
          for method in ('gp_preference', 'evolutionary', 'recipe_preference'):
            search = LiveSearch(self.controller, root=Path(self.directory.name) / method)
            search.start('Pilot', mode, method)
            candidates = [search.data['candidates'][ident] for ident in search.data['initial']]
            self.assertEqual(len(candidates), 8)
            self.assertTrue(all(set(row['controls']) == set(PROBE_GROUP_FIELDS) for row in candidates))
            self.assertTrue(all(
                all(search.data['bounds'][key][0] <= row['controls'][key] <= search.data['bounds'][key][1]
                    for key in PROBE_GROUP_FIELDS) for row in candidates))
            self.assertTrue(all(row['recipe_version'] == 2 and row['physical_bounds'] == mode_bounds(mode)
                                for row in candidates))
            search.monitor.stop()

        comfort, sport = SOUND_THEMES['Comfort'], SOUND_THEMES['Sport']
        comfort_center, sport_center = preset_controls_for(comfort), preset_controls_for(sport)
        self.assertNotEqual(comfort_center, sport_center)
        self.assertNotEqual(preset_profile_for(comfort, comfort_center, comfort_center),
                            preset_profile_for(sport, sport_center, sport_center))

    def test_legacy_comfort_session_keeps_old_controls(self):
        legacy = profile_for(SOUND_THEMES['Comfort'], dict(zip(COMFORT_CONTROLS, (.5, .5, 0., .5))))
        self.assertEqual(legacy['electric_start_hz'], 125.)
        self.assertEqual(legacy['richness'], SOUND_THEMES['Comfort']['richness'])
        self.search.start('Pilot', 'Sport', 'gp_preference')
        d = self.search.data
        d['algorithm'] = 'gp-preference-ei-v2'
        d['control_keys'] = GP_CONTROLS
        d['baseline_controls'] = dict.fromkeys(GP_CONTROLS, .5)
        d['mode'] = 'Comfort'
        d['base'] = dict(SOUND_THEMES['Comfort'])
        for candidate in d['candidates'].values():
            candidate['controls'] = dict.fromkeys(GP_CONTROLS, .5)
            candidate['profile'] = profile_for(d['base'], candidate['controls'])
        self.search.finish(False)
        self.search.restore(d['id'], False)
        self.assertEqual(tuple(self.search.data['control_keys']), GP_CONTROLS)
        self.assertEqual(self.search.data['algorithm'], 'gp-preference-ei-v2')
        self.assertEqual(self.search.data['candidates']['c0001']['profile'],
                         profile_for(SOUND_THEMES['Comfort'], self.search.data['candidates']['c0001']['controls']))

    def test_gp_retry_preserves_third_rating_and_uses_explicit_control_order(self):
        from unittest.mock import patch
        from experiment.preference_gp import select_query
        self.search.start('Pilot', 'Sport', 'gp_preference')
        for score in ('A', 'B', 'equal', 'B', 'A', 'B'):
            self.search.choose('A'); self.search.choose('B')
            self.search.ratePreference(score)
            self.search.next()
        # JSON/object key order must not become GP feature order.
        self.search.data['baseline_controls'] = dict(reversed(list(self.search.data['baseline_controls'].items())))
        for candidate in self.search.data['candidates'].values():
            candidate['controls'] = dict(reversed(list(candidate['controls'].items())))
        self.search.choose('A'); self.search.choose('B')
        self.search.ratePreference('equal')
        original_pair = dict(self.search.data['pair'])
        original_incumbent = self.search.data['incumbent']
        with patch('experiment.live_search.select_query', wraps=select_query) as query, patch(
                'experiment.live_search.os.replace', side_effect=OSError('disk full')):
            self.search.next()
            pool, xa, xb, outcomes, anchor = query.call_args.args
            self.assertEqual(pool[0], [self.search.data['probe_controls'][key]
                                       for key in PROBE_GROUP_FIELDS])
            self.assertTrue(all(len(row) == 4 for row in pool + xa + xb))
            self.assertEqual(outcomes, ['A', 'B', 'equal', 'B', 'A', 'B', 'equal'])
            self.assertEqual(anchor, [self.search.data['probe_controls'][key] for key in PROBE_GROUP_FIELDS])
            incumbent = query.call_args.kwargs['incumbent']
            self.assertEqual(incumbent, 0)
        self.assertEqual(self.search.data['completed'], 6)
        self.assertEqual(self.search.preference, 'equal')
        self.assertEqual(self.search.data['pair'], original_pair)
        self.assertEqual(self.search.data['incumbent'], original_incumbent)
        self.assertEqual(json.loads(self.search.path.read_text())['completed'], 6)
        self.search.next()
        self.assertEqual(self.search.data['completed'], 7)
        self.assertEqual([row['preference'] for row in self.search.data['history']],
                         ['A', 'B', 'equal', 'B', 'A', 'B', 'equal'])

    def test_reproducible_mutation_and_locked_gain(self):
        from copy import deepcopy
        self.search.start('Pilot', 'Sport')
        for _ in range(3):
            self.rate_pair()
        clone = LiveSearch(self.controller, root=Path(self.directory.name) / 'clone')
        clone.data = deepcopy(self.search.data)
        clone.path = clone.root / 'session.json'
        clone.choose('A'); clone.rate('A', 7)
        clone.choose('B'); clone.rate('B', 5)
        clone.next()
        self.rate_pair(7, 5)
        for slot in ('A', 'B'):
            a = self.search.data['candidates'][self.search.data['pair'][slot]]
            b = clone.data['candidates'][clone.data['pair'][slot]]
            self.assertEqual(a['controls'], b['controls'])
            self.assertEqual(a['profile'], b['profile'])
        clone.monitor.stop()
        before = deepcopy(self.search.data['pair'])
        self.search.continueBlock()
        self.assertEqual(self.search.data['pair'], before)

    def test_independent_pitch_controls_and_audio_transitions(self):
        import numpy as np
        from audio import SoundEngine
        rng = __import__('random').Random(19)
        base = SOUND_THEMES['Sport']
        controls = {k: .5 for k in CONTROLS}
        p = profile_for(base, controls)
        wide = profile_for(base, dict(controls, motion=1.))
        self.assertEqual(p['electric_start_hz'], wide['electric_start_hz'])
        self.assertNotEqual(p['electric_pitch_scale'], wide['electric_pitch_scale'])
        engine = SoundEngine()
        samples = []
        for i in range(20):
            p = profile_for(base, {k: rng.random() for k in CONTROLS})
            engine.set_driving_parameters(100, 80, -.8 if i % 2 else .8, 2, 'ready', p)
            for _ in range(8):
                output = np.empty((512, 1), dtype=np.float32)
                engine._callback(output, 512, None, None)
                samples.append(output[:, 0].copy())
        samples = np.concatenate(samples)
        self.assertTrue(np.isfinite(samples).all())
        self.assertLess(np.max(np.abs(samples)), .5)
        self.assertLess(np.max(np.abs(np.diff(samples))), .15)

    def test_extreme_candidate_stays_below_clipping(self):
        import numpy as np
        from audio import SoundEngine
        engine = SoundEngine()
        profile = profile_for(SOUND_THEMES['Sport'], {k: 1. for k in CONTROLS})
        engine.set_driving_parameters(0, 100, 1, 8, 'ready', profile)
        peak = 0.
        for _ in range(200):
            output = np.empty((512, 1), dtype=np.float32)
            engine._callback(output, 512, None, None)
            self.assertTrue(np.isfinite(output).all())
            peak = max(peak, float(np.max(np.abs(output))))
        self.assertLess(peak, .95)

    def test_invalid_feedback_and_bounds(self):
        self.search.start('', 'Deep')
        self.assertFalse(self.search.active)
        self.search.start('Pilot', 'Deep')
        self.search.rate('A', 7)
        self.assertEqual(self.search.ratingA, 0)
        with self.assertRaises(ValueError):
            profile_for(SOUND_THEMES['Deep'], {k: -1 for k in CONTROLS})
        self.search.restore('../bad', False)
        self.assertTrue(self.search.active)


if __name__ == '__main__':
    unittest.main()
