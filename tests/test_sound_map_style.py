import importlib.util, sys, unittest
from pathlib import Path

HERE = Path(__file__).resolve().parents[1] / 'tools' / 'sound_map'


@unittest.skipUnless(importlib.util.find_spec('mosqito'), 'sound-map tools need mosqito (.venv-soundmap)')
class StyleTest(unittest.TestCase):
    def test_styled_genomes_keep_their_style(self):
        sys.path.insert(0, str(HERE))
        import generate as g
        g.STACK_CHOICES.update({f'stT{k}': g.FRAME_TEXTURES for k in range(5)}); g.VOICES[:] = ['stack']  # as --style sets them
        for name in g.STYLES:
            g.STYLE = name
            for _ in range(200):
                genome = g.styled(g.mutate(g.styled(g.random_genome('stack'))))
                self.assertEqual(g.style_of(genome), name)
        g.STYLE = None
        self.assertEqual(g.style_of({'voice': 'stack', 'stLayers': 4, 'stT0': 9, 'stT1': 1, 'stT2': 3, 'stT3': 6, 'stT4': 0}), 'blend')
        self.assertGreaterEqual(g.gap({'bands': [0] * 8, 'pitch': 0, 'inharm': 0, 'R': 0, 'F': 0, 'style': 'choir'},
                                      {'bands': [0] * 8, 'pitch': 0, 'inharm': 0, 'R': 0, 'F': 0, 'style': 'glass'}), 1)


if __name__ == '__main__':
    unittest.main()
