import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock
from unittest.mock import patch

from PySide6.QtCore import QCoreApplication
from audio import SOUND_THEMES
from experiment.live_search import (LiveSearch, CONTROLS, GP_CONTROLS, COMFORT_CONTROLS,
                                    CHARACTER_CONTROLS, profile_for)


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

    def test_search_blocks_resume_and_favorite(self):
        self.search.start('Pilot', 'Comfort')
        self.assertEqual(len(self.search.data['candidates']), 6)
        self.assertEqual(len(self.search.data['survivors']), 0)
        for _ in range(3):
            self.rate_pair()
        self.assertEqual(len(self.search.data['survivors']), 3)
        parent = self.search.data['parent']
        self.search.choose('A')
        self.search.rate('A', 4)
        self.search.choose('B')
        self.search.rate('B', 4)
        self.search.next()
        self.assertIn(parent, self.search.data['survivors'])
        for _ in range(6):
            self.rate_pair()
        self.assertEqual(self.search.checkpoint, 'break')
        self.assertEqual(len(self.search.traceSession(self.search.data['id'])['comparisons']), 10)
        completed = self.search.data['completed']
        pair_at_break = dict(self.search.data['pair'])
        candidates_at_break = len(self.search.data['candidates'])
        self.search.next()
        self.assertEqual(self.search.data['completed'], completed)
        self.search.continueBlock()
        self.assertNotEqual(self.search.data['pair'], pair_at_break)
        self.assertGreater(len(self.search.data['candidates']), candidates_at_break)
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
            self.assertEqual(set(c['controls']), set(CHARACTER_CONTROLS))
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
        for _ in range(3):
            self.rate_pair(6, 2)
        first_winner = self.search.data['history'][0]['winner']
        slot = next(slot for slot, ident in self.search.data['pair'].items() if ident == first_winner)
        other = 'B' if slot == 'A' else 'A'
        self.assertEqual(self.search.data['ratings'][slot], 6)
        self.assertEqual(self.search.ratingSources[slot], 1)
        self.assertEqual(self.search.data['ratings'][other], 0)
        self.assertFalse(self.search.feedbackReady)
        self.search.choose(other)
        self.search.rate(other, 7)
        self.assertTrue(self.search.feedbackReady)
        self.search.next()
        self.assertEqual(self.search.data['history'][3]['rating_sources'][slot], 1)
        self.assertEqual(self.search.data['history'][3]['winner'], self.search.data['history'][3]['pair'][other])

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

    def test_gp_feature_discovery_and_final_combinations(self):
        with patch('experiment.live_search.secrets.randbits', return_value=12345):
            self.search.start('Pilot', 'Deep', 'gp_preference')
        self.assertEqual(self.search.data['algorithm'], 'gp-feature-v2')
        self.assertEqual(len(self.search.data['initial']), 12)
        groups = (('register',), ('motion',), ('tone', 'whirl'),
                  ('pulse', 'shimmer'), ('ensemble', 'phrase'), ('response', 'regen'))
        for number, group in enumerate(groups):
            pair = self.search.data['pair']
            self.assertEqual(set(pair.values()), set(self.search.data['initial'][2*number:2*number+2]))
            a, b = (self.search.data['candidates'][pair[slot]]['controls'] for slot in ('A', 'B'))
            self.assertEqual({key for key in CHARACTER_CONTROLS if a[key] != b[key]}, set(group))
            self.search.choose('A'); self.search.choose('B')
            self.search.ratePreference('B')
            self.search.next()
            self.assertEqual(self.search.data['feature_winners'][str(number)], pair['B'])
            if number == 3:
                pending = dict(self.search.data['pair'])
                ident = self.search.data['id']
                self.search.finish(False)
                self.search.restore(ident, False)
                self.assertEqual(self.search.data['pair'], pending)
                self.assertEqual(len(self.search.data['feature_winners']), 4)
        self.assertEqual(self.search.data['completed'], 6)
        for _ in range(11):
            self.search.choose('A'); self.search.choose('B')
            self.search.ratePreference('B'); self.search.next()
            if self.search.checkpoint:
                self.search.continueBlock()
        self.assertEqual(self.search.pairNumber, 18)
        for number in (18, 19, 20):
            pair = self.search.data['pair']
            mixed = self.search.data['candidates'][max(pair.values())]
            self.assertEqual(mixed['kind'], 'feature-mix')
            self.assertGreaterEqual(len(mixed['parents']), 2)
            self.search.choose('A'); self.search.choose('B')
            self.search.ratePreference('B'); self.search.next()
        self.assertEqual(self.search.checkpoint, 'cap')

    def test_gp_mix_tries_other_preferred_groups_when_first_mix_duplicates_favorite(self):
        with patch('experiment.live_search.secrets.randbits', return_value=12345):
            self.search.start('Pilot', 'Comfort', 'gp_preference')
        for number in range(20):
            if number >= 17:
                latest = max(self.search.data['pair'].values())
                self.assertEqual(self.search.data['candidates'][latest]['kind'], 'feature-mix')
            self.search.choose('A'); self.search.choose('B')
            self.search.ratePreference('A'); self.search.next()
            if self.search.checkpoint == 'break':
                self.search.continueBlock()

    def test_gp_ties_leave_features_unresolved_and_continue_with_model(self):
        with patch('experiment.live_search.secrets.randbits', return_value=12345):
            self.search.start('Pilot', 'Comfort', 'gp_preference')
        for _ in range(20):
            self.search.choose('A'); self.search.choose('B')
            self.search.ratePreference('equal'); self.search.next()
            if self.search.checkpoint == 'break':
                self.search.continueBlock()
        self.assertEqual(self.search.data['feature_winners'], {})
        self.assertEqual(self.search.checkpoint, 'cap')

    def test_deep_first_pair_avoids_extreme_whirl_and_ensemble(self):
        self.search.start('Pilot', 'Deep', 'evolutionary')
        seed, opening = (self.search.data['candidates'][ident] for ident in self.search.data['initial'][:2])
        self.assertLessEqual(seed['controls']['ensemble'], .3)
        self.assertLessEqual(opening['controls']['whirl'], .2)
        self.assertEqual(opening['controls']['phrase'], 0)

    def test_delete_saved_session_removes_directory_and_blocks_active(self):
        self.search.start('Pilot', 'Deep')
        ident = self.search.data['id']
        path = self.search.path.parent
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
            if self.search.checkpoint == 'break':
                self.assertEqual(len(self.search.traceSession(self.search.data['id'])['comparisons']), 10)
                last_pair = dict(self.search.data['pair'])
                self.search.continueBlock()
                self.assertNotEqual(self.search.data['pair'], last_pair)
                self.assertEqual(len(self.search.traceSession(self.search.data['id'])['comparisons']), 11)
        self.assertEqual(self.search.checkpoint, 'cap')
        self.search.continueBlock()
        self.assertEqual(self.search.data['block_end'], 40)
        self.assertEqual(self.search.checkpoint, '')
        self.assertEqual(self.search.preference, '')

    def test_gp_retains_incumbent_on_tie_and_replaces_only_with_winner(self):
        self.search.start('Pilot', 'Comfort', 'gp_preference')
        self.assertEqual(self.search.data['algorithm'], 'gp-feature-v2')
        incumbent = self.search.data['pair']['A']
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
        for candidate in d['candidates'].values():
            candidate['controls'] = dict.fromkeys(GP_CONTROLS, .5)
            candidate['profile'] = profile_for(d['base'], candidate['controls'])
        for value in (.2, .8):
            d['initial'].append(self.search._candidate(d, dict.fromkeys(GP_CONTROLS, value)))
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
        d['initial'] = d['initial'][:6]
        d['incumbent'] = d['initial'][0]
        ident = d['id']
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
          for method in ('gp_preference', 'evolutionary'):
            search = LiveSearch(self.controller, root=Path(self.directory.name) / method)
            search.start('Pilot', mode, method)
            candidates = [search.data['candidates'][ident] for ident in search.data['initial']]
            self.assertEqual(len(candidates), 12 if method == 'gp_preference' else 6)
            self.assertTrue(all(set(row['controls']) == set(CHARACTER_CONTROLS) for row in candidates))
            for key in ('electric_pulse', 'electric_shimmer', 'orchestral_mix', 'traction_cycle_mix'):
                self.assertGreater(max(c['profile'][key] for c in candidates), .3 if key == 'orchestral_mix' else .5)
                self.assertLess(min(c['profile'][key] for c in candidates), .2)
            if mode != 'Deep':
                self.assertGreater(max(c['profile']['electric_whirl'] for c in candidates), .5)
            if method == 'evolutionary':
                self.assertEqual(candidates[0]['controls'], search.data['baseline_controls'])
            search.monitor.stop()

        controls = dict.fromkeys(CHARACTER_CONTROLS, .5)
        self.assertEqual(profile_for(SOUND_THEMES['Comfort'], controls),
                         profile_for(SOUND_THEMES['Sport'], controls))

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
            pool, xa, xb, outcomes, anchor, _ = query.call_args.args
            first = next(iter(self.search.data['candidates'].values()))['controls']
            self.assertEqual(pool[0], [first[key] for key in CHARACTER_CONTROLS])
            self.assertTrue(all(len(row) == 10 for row in pool + xa + xb))
            self.assertEqual(outcomes, ['A', 'B', 'equal', 'B', 'A', 'B', 'equal'])
            self.assertEqual(anchor, [self.search.data['baseline_controls'][key] for key in CHARACTER_CONTROLS])
            incumbent = query.call_args.kwargs['incumbent']
            expected = self.search.data['candidates'][original_incumbent]['controls']
            self.assertEqual(pool[incumbent], [expected[key] for key in CHARACTER_CONTROLS])
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
