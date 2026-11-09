import unittest
import os
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import Mock, patch

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from PySide6.QtGui import QGuiApplication

from backend.bridge import DesktopBridge
from backend.controller import SimulatorController
from audio import SOUND_RECIPES


class DesktopBridgeTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QGuiApplication.instance() or QGuiApplication([])

    def setUp(self):
        self.controller = SimulatorController()
        self.bridge = DesktopBridge(self.controller)

    def tearDown(self):
        self.controller.search.close()
        self.controller.experiment.close()
        self.controller.shutdown()

    def test_source_audition_mutes_native_audio_and_restores_volume(self):
        with patch.object(self.controller, 'audio', Mock(electric_hz_target=0.0, params=[0.0])) as audio:
            self.bridge.command('sourceAudition', {'value': True})
            self.assertTrue(self.controller.source_audition)
            self.assertEqual(audio.set_driving_parameters.call_args.kwargs['master_volume'], 0.0)
            self.bridge.command('sourceAudition', {'value': False})
            self.assertFalse(self.controller.source_audition)
            self.assertEqual(audio.set_driving_parameters.call_args.kwargs['master_volume'], self.controller.search.volume)
            with self.assertRaises(ValueError):
                self.bridge.command('sourceAudition', {'value': 'yes'})

    def test_snapshot_exposes_acceleration(self):
        self.controller.car.acceleration_m_s2 = 2.75
        self.assertAlmostEqual(self.bridge.snapshot()['acceleration'], 2.75)

    def test_snapshot_exposes_signed_motor_load(self):
        self.controller.car.motor_torque_nm = -.5 * self.controller.car.max_regen_torque_nm
        self.assertAlmostEqual(self.bridge.snapshot()['motorLoad'], -.5)
        self.controller.car.motor_torque_nm = .5 * self.controller.car.max_torque_nm
        self.assertAlmostEqual(self.bridge.snapshot()['motorLoad'], .5)

    def test_snapshot_exposes_existing_vehicle_and_search_state(self):
        state = self.bridge.snapshot()
        self.assertEqual(state['vehicle'], 'Compact EV')
        self.assertFalse(state['running'])
        self.assertEqual(state['hasGears'], self.controller.hasGears)
        self.assertFalse(state['search']['active'])
        self.assertIn('Deep', state['soundThemes'])

    def test_recipe_switch_changes_preview_profile_without_changing_mode_list(self):
        before = self.bridge.snapshot()
        self.assertEqual(before['soundRecipes']['Deep'], ['Traction Glide', 'Orchestral Rise'])
        after = self.bridge.command('recipeCycle', {'name': 'Deep'})
        self.assertEqual(after['soundTheme'], 'Deep')
        self.assertEqual(after['soundRecipeSelection']['Deep'], 'Orchestral Rise')
        self.assertEqual(after['soundThemes'], before['soundThemes'])
        self.assertEqual(SOUND_RECIPES['Deep']['Orchestral Rise']['orchestral_mix'], 0.88)
        self.assertEqual(self.bridge.command('recipeCycle', {'name': 'Deep'})['soundRecipeSelection']['Deep'], 'Traction Glide')
        with self.assertRaisesRegex(ValueError, 'Unknown sound theme'):
            self.bridge.command('recipeCycle', {'name': 'unknown'})

    def test_recipe_preference_session_exposes_recipe_names_in_pair(self):
        with TemporaryDirectory() as directory:
            self.controller.search.root = Path(directory)
            state = self.bridge.command('searchStart', {'participant': 'Pilot', 'mode': 'Comfort',
                                                        'method': 'recipe_preference'})
            self.assertEqual(state['search']['learningMethod'], 'recipe_preference')
            self.assertEqual(state['search']['mode'], 'Comfort')
            self.assertEqual(state['soundTheme'], 'Comfort')
            self.assertEqual(set(state['search']['pairRecipes'].values()), {'Clean Electric', 'Warm Motor'})
            self.assertEqual(state['search']['stage'], 'Explore recipes')
            for slot in ('A', 'B'):
                self.bridge.command('searchChoose', {'slot': slot})
                selected = self.controller.search.data['pair'][slot]
                profile = self.controller.search.data['candidates'][selected]['profile']
                self.assertEqual(self.controller.search.profile, profile)
                self.assertEqual(self.controller.audio.order_active, bool(profile.get('order_synthesis')))
            self.bridge.command('searchPreference', {'value': 'B'})
            self.assertTrue(self.bridge.command('searchNext', {})['search']['active'])

    def test_rejects_unknown_command_and_invalid_pedal_value(self):
        with self.assertRaisesRegex(ValueError, 'Unknown command'):
            self.bridge.command('shutdown', {})
        with self.assertRaisesRegex(ValueError, 'pedal'):
            self.bridge.command('pedals', {'throttle': 2, 'brake': 0})

    def test_failed_second_pedal_keeps_previous_input(self):
        self.bridge.command('pedals', {'throttle': 0.4, 'brake': 0})
        with self.assertRaisesRegex(ValueError, 'brake'):
            self.bridge.command('pedals', {'throttle': 0.9, 'brake': 2})
        self.assertEqual(self.controller.external_throttle, 0.4)

    def test_search_commands_keep_existing_record_format(self):
        with TemporaryDirectory() as directory:
            self.controller.search.root = Path(directory)
            state = self.bridge.command('searchStart', {'participant': 'Test', 'mode': 'Deep', 'method': 'evolutionary'})
            self.assertTrue(state['search']['active'])
            self.bridge.command('searchChoose', {'slot': 'A'})
            self.bridge.command('searchRate', {'slot': 'A', 'value': 5})
            self.bridge.command('searchChoose', {'slot': 'B'})
            state = self.bridge.command('searchRate', {'slot': 'B', 'value': 3})
            self.assertTrue(state['search']['feedbackReady'])
            self.bridge.command('searchNext', {})
            self.assertEqual(self.controller.search.data['completed'], 1)
            self.assertEqual(len(list(Path(directory).rglob('session.json'))), 1)
            session_id = self.controller.search.data['id']
            self.bridge.command('searchFinish', {'satisfied': False})
            trace = self.bridge.command('traceSession', {'id': session_id})
            self.assertEqual(trace['comparisons'][0]['ratings'], {'A': 5, 'B': 3})
            self.controller.audio.start = Mock()
            candidate_id = trace['comparisons'][0]['pair']['A']['id']
            self.assertTrue(self.bridge.command('tracePreview', {'sessionId': session_id, 'candidateId': candidate_id}))
            self.controller.audio.start.assert_called_once()
            self.controller.search.close()

    def test_similar_pair_is_replaced_without_a_rating(self):
        with TemporaryDirectory() as directory:
            self.controller.search.root = Path(directory)
            self.bridge.command('searchStart', {'participant': 'Test', 'mode': 'Deep', 'method': 'gp_preference'})
            original = dict(self.controller.search.data['pair'])
            state = self.bridge.command('searchSimilar', {})
            self.assertEqual(self.controller.search.data['completed'], 0)
            self.assertNotEqual(self.controller.search.data['pair'], original)
            self.assertTrue(state['search']['selected'])
            trace = self.bridge.command('traceSession', {'id': self.controller.search.data['id']})
            self.assertEqual(trace['skipped_pairs'][0]['pair'], original)
            self.controller.search.close()

    def test_gp_preference_command_uses_three_choices(self):
        with TemporaryDirectory() as directory:
            self.controller.search.root = Path(directory)
            self.bridge.command('searchStart', {'participant': 'Test', 'mode': 'Deep', 'method': 'gp_preference'})
            self.bridge.command('searchChoose', {'slot': 'A'})
            self.bridge.command('searchChoose', {'slot': 'B'})
            with self.assertRaisesRegex(ValueError, 'Invalid preference'):
                self.bridge.command('searchPreference', {'value': 7})
            state = self.bridge.command('searchPreference', {'value': 'equal'})
            self.assertEqual(state['search']['preference'], 'equal')
            self.assertTrue(state['search']['feedbackReady'])
            self.bridge.command('searchNext', {})
            self.assertEqual(self.controller.search.data['history'][0]['preference'], 'equal')
            self.controller.search.close()

    def test_gp_neither_command_replaces_both_sounds(self):
        with TemporaryDirectory() as directory:
            self.controller.search.root = Path(directory)
            self.bridge.command('searchStart', {'participant': 'Test', 'mode': 'Deep', 'method': 'gp_preference'})
            original = set(self.controller.search.data['pair'].values())
            self.bridge.command('searchChoose', {'slot': 'A'})
            self.bridge.command('searchChoose', {'slot': 'B'})
            state = self.bridge.command('searchNeither', {})
            self.assertEqual(state['search']['pairNumber'], 1)
            self.assertTrue(original.isdisjoint(self.controller.search.data['pair'].values()))
            self.assertEqual(self.controller.search.data['skipped_pairs'][0]['reason'], 'neither')
            self.controller.search.close()

    def test_finish_saves_explicit_favorite_slot(self):
        with TemporaryDirectory() as directory:
            self.controller.search.root = Path(directory)
            self.bridge.command('searchStart', {'participant': 'Test', 'mode': 'Deep', 'method': 'gp_preference'})
            self.bridge.command('searchChoose', {'slot': 'A'})
            self.bridge.command('searchChoose', {'slot': 'B'})
            with self.assertRaisesRegex(ValueError, 'Choose sound A or B'):
                self.bridge.command('searchFinish', {'satisfied': True})
            chosen = self.controller.search.data['pair']['A']
            state = self.bridge.command('searchFinish', {'satisfied': True, 'favoriteSlot': 'A'})
            self.assertFalse(state['search']['active'])
            self.assertEqual(self.controller.search.data['favorite'], chosen)
            self.assertEqual(self.controller.search.data['playing'], chosen)
            self.controller.search.close()

    def test_focus_loss_releases_keyboard_pedals(self):
        self.controller.timer.start()
        self.bridge.command('starting', {'value': False})
        self.bridge.command('pedals', {'throttle': 1, 'brake': 0})
        self.assertEqual(self.controller.throttle, 1)
        self.bridge.command('focus', {'value': False})
        self.assertEqual(self.controller.throttle, 0)


if __name__ == '__main__':
    unittest.main()
