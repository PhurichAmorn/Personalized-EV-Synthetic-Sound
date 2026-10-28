import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('QSG_RHI_BACKEND', 'software')
from PySide6.QtGui import QGuiApplication
from PySide6.QtMultimedia import QMediaPlayer
from scipy.io.wavfile import read

from experiment.experiment_manager import (ExperimentStore, RenderPair,
                                           RenderSignals, candidate_snapshot)
from audio import OrderSoundConfig
from backend.controller import SimulatorController


class ExperimentTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QGuiApplication.instance() or QGuiApplication([])

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.simulator = SimulatorController()
        self.simulator.search.root = Path(self.temp.name) / "interactive"
        self.manager = self.simulator.experiment
        self.manager.store = ExperimentStore(self.temp.name)
        self.simulator.audio.start = Mock()
        self.simulator.audio.stop = Mock()

    def tearDown(self):
        self.simulator.search.close()
        self.manager.close()
        self.simulator.shutdown()
        self.temp.cleanup()

    def test_practice_skip_and_exact_records(self):
        self.assertEqual(self.manager.profiles, ['Comfort', 'Sport', 'Deep'])
        self.manager.start('Deep', True)
        self.assertEqual(self.manager.state, 'practice')
        self.manager.beginComparison()
        self.assertEqual(self.manager.state, 'edit')
        with patch.object(self.manager.pool, 'start'):
            self.manager.prepare()
        self.assertEqual(self.manager.state, 'rendering')
        self.manager._rendered(self.manager.token, {'A': {'path': 'a.wav'}, 'B': {'path': 'b.wav'}}, '')
        self.assertEqual(self.manager.state, 'compare')
        self.manager.saveRating('A', 6, 3, 'Not heard')
        self.assertEqual(self.manager.savedCount, 0)
        self.manager.playing = 'A'
        self.manager._media_status(QMediaPlayer.MediaStatus.EndOfMedia)
        self.manager.playing = 'B'
        self.manager._media_status(QMediaPlayer.MediaStatus.EndOfMedia)
        self.manager.saveRating('tie', 6, 6, 'Both comfortable')
        self.manager.saveRating('B', 2, 7, 'Duplicate prevented')
        self.assertEqual(self.manager.savedCount, 1)
        path = Path(self.manager.sessionPath)
        session = json.loads((path / 'session.json').read_text())
        self.assertTrue(session['practice_selected'])
        events = [json.loads(line) for line in (path / 'events.jsonl').read_text().splitlines()]
        pair = next(row for row in events if row['kind'] == 'pair_created')
        self.assertEqual(pair['candidates']['A']['controls'], self.manager.controls['A'])
        self.assertIn('order_config', pair['candidates']['B'])
        comparison = [row for row in events if row['kind'] == 'comparison']
        self.assertEqual(len(comparison), 1)
        self.assertEqual(comparison[0]['preferred'], 'tie')
        self.manager.finish()
        self.manager.start('Deep', False)
        self.assertEqual(self.manager.state, 'edit')
        self.assertNotEqual(self.manager.sessionPath, str(path))
        self.assertTrue(path.exists())

    def test_failed_write_keeps_pending_rating(self):
        self.manager.start('Deep', False)
        self.manager.stage = 'compare'
        self.manager.heard = {'A', 'B'}
        with patch.object(self.manager.store, 'append', side_effect=OSError('disk full')):
            self.manager.saveRating('A', 6, 3, '')
        self.assertEqual(self.manager.state, 'compare')
        self.assertEqual(self.manager.savedCount, 0)
        self.assertIn('disk full', self.manager.message)
        self.manager.saveRating('A', 6, 3, '')
        self.assertEqual(self.manager.state, 'saved')
        self.assertEqual(self.manager.message, '')

    def test_rendered_candidates_are_reproducible_and_distinct(self):
        controls = dict(self.manager.controls['A'])
        config = OrderSoundConfig()
        pair = {label: candidate_snapshot('Deep', values, config) for label, values in self.manager.controls.items()}
        signals = RenderSignals()
        results = []
        signals.done.connect(lambda token, renders, error: results.append((renders, error)))
        job = RenderPair('test', Path(self.temp.name), pair, signals)
        job.run()
        renders, error = results[-1]
        self.assertFalse(error)
        self.assertNotEqual(renders['A']['sha256'], renders['B']['sha256'])
        first_hash = renders['A']['sha256']
        job.run()
        self.assertEqual(results[-1][0]['A']['sha256'], first_hash)
        rate, samples = read(renders['A']['path'])
        self.assertEqual(rate, 48000)
        self.assertEqual(len(samples), rate * 16)
        self.assertEqual(controls, self.manager.controls['A'])
        with self.assertRaises(ValueError):
            candidate_snapshot('Deep', dict(controls, pitch_scale=float('nan')), config)




