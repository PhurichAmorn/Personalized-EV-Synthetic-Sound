import random
import unittest

from experiment.block_arms import GuessBlocks


class GuessBlocksTest(unittest.TestCase):
    def test_full_session(self):
        """17 pairs with a simulated listener who likes low pitch: every pair is two different sounds, the podium and the evaluation are filled."""
        d = GuessBlocks(renderer=lambda r: None); d.start(); rng = random.Random(0); pairs = []
        while d.active:
            self.assertEqual(len(d.pair), 2, d.error)
            a, b = (d.candidates[i]['recipe'] for i in d.pair); pairs.append(frozenset(d.pair))
            self.assertNotEqual(d.pair[0], d.pair[1])
            if len(pairs) > 1: self.assertTrue(d._clear(a, b))
            d.feedback(choice=rng.choice(('A', 'B')) if len(pairs) == 1 else 'A' if a['blocks']['pitch'] <= b['blocks']['pitch'] else 'B')
        self.assertEqual(len(pairs), 17); self.assertEqual(len(set(pairs)), 17)  # no pair played twice
        data = d.export(); ev = data['evaluation']; heard = {i for r in data['history'] for i in r['pair']}
        self.assertIn(ev['baseline'], heard); self.assertEqual(ev['final'], d.finalists[0])
        self.assertLessEqual(d._sound(ev['final'])['pitch'], 1)  # the model learned the taste
        d.close()


if __name__ == '__main__':
    unittest.main()
