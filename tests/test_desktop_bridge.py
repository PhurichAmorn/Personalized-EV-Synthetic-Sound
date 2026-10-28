import unittest
import os
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import Mock

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from PySide6.QtGui import QGuiApplication

from backend.bridge import DesktopBridge
from backend.controller import SimulatorController


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

    def test_snapshot_exposes_existing_vehicle_and_search_state(self):
        state = self.bridge.snapshot()
        self.assertEqual(state['vehicle'], 'Compact EV')
        self.assertFalse(state['running'])
        self.assertEqual(state['hasGears'], self.controller.hasGears)
        self.assertFalse(state['search']['active'])
        self.assertIn('Deep', state['soundThemes'])

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
