import random
import tempfile
import unittest
from pathlib import Path

from experiment.block_arms import DuelBlocks, InfoGainBlocks, PBOBlocks, RandomBlocks, RobustBlocks
from tests.test_block_discovery import fake_table

ARMS = (InfoGainBlocks, RandomBlocks, RobustBlocks, PBOBlocks, DuelBlocks)


class BlockArmsTest(unittest.TestCase):
    def play(self, cls, seed, motion=None):
        tmp = tempfile.TemporaryDirectory(); self.addCleanup(tmp.cleanup); path = Path(tmp.name) / 'table.json'; fake_table(path)
        d = cls(table_path=path); d.start(motion); d.rng = random.Random(seed); rng = random.Random(seed + 1); seen = []
        while d.active and d.completed < d.pairs:
            self.assertEqual(len(d.pair), 2); self.assertEqual(len(set(d.pair)), 2); seen.append(tuple(d.pair))
            d.feedback(choice=rng.choice(('A', 'B', 'A', 'B', 'good', 'neither')))
        return d, seen

    def test_every_arm_plays_a_full_session_and_ranks(self):
        for cls in ARMS:
            for motion in (None, 'rise'):
                d, seen = self.play(cls, 3, motion)
                self.assertEqual(d.completed, 17 if motion is None else 16, cls.__name__)
                d._rank_finalists(); self.assertTrue(d.finalists, cls.__name__); self.assertTrue(d.export()['policy'].startswith('source-blocks-v1-'))
                d.close()

    def test_duel_adaptive_pairs_have_no_champion_and_others_keep_one(self):
        d, seen = self.play(DuelBlocks, 5, 'rise'); kinds = [d.candidates[i]['origin']['kind'] for p in seen[3:12] for i in p]
        self.assertIn('duel', kinds); self.assertNotIn('broad', kinds); d.close()  # a start that is heard again keeps its first origin
        d, seen = self.play(PBOBlocks, 5, 'rise'); o = lambda i: d.candidates[i]['origin']
        self.assertTrue(all(any(o(i)['kind'] == 'broad' for i in p) for p in seen[3:12])); d.close()

    def test_robust_champion_is_the_bradley_terry_best(self):
        d, seen = self.play(RobustBlocks, 7, 'rise')
        self.assertFalse(RobustBlocks.winner_stays); self.assertTrue(PBOBlocks.winner_stays); d.close()


if __name__ == '__main__':
    unittest.main()
