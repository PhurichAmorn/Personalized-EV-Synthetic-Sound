import sys, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools' / 'sound_map'))


class LoudnessTest(unittest.TestCase):
    def test_gain_brings_a_quiet_and_a_loud_sound_to_the_same_loudness(self):
        try: import numpy as np, loudness
        except ImportError as e: self.skipTest(f'sound map tools not installed: {e}')
        t = np.arange(loudness.FS) / loudness.FS
        tone = np.sin(2 * np.pi * 220 * t) + .5 * np.sin(2 * np.pi * 660 * t)
        quiet, loud = tone * .02, tone * .2  # Pa: 20 dB apart
        target = loudness.sones(tone * .06)
        for x in (quiet, loud):
            self.assertAlmostEqual(loudness.sones(x * loudness.gain_for(x, target)) / target, 1, delta=.1)


if __name__ == '__main__':
    unittest.main()
