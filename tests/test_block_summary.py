import unittest
from experiment import sound_blocks as sb


@unittest.skipUnless(sb.load_table(), 'no safe-area table')
class BlockSummaryTests(unittest.TestCase):
    def test_funnel_and_pool_agree(self):
        table = sb.load_table(); s = sb.summary(table)
        self.assertLessEqual(s['distinct'], s['safe']); self.assertLessEqual(s['safe'], s['valid']); self.assertLessEqual(s['valid'], s['free'])
        self.assertEqual(len(sb.pool(table)), s['distinct'])
        self.assertEqual(sum(t['distinct'] for t in s['tops']), s['distinct'])

    def test_pool_offers_only_what_the_session_moves(self):
        pool = sb.pool(sb.load_table())
        self.assertTrue(all(b['buzz'] in sb.BUZZ_STEPS for b in pool))
        self.assertTrue(all(b['buzz'] == 0 and b['chord'] == 'off' and not b['bell'] and not b['vowel'] for b in pool if not sb.has_synth(b)))


if __name__ == '__main__':
    unittest.main()
