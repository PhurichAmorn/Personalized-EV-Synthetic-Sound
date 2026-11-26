import sys, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools' / 'sound_map'))


class BodyLedTest(unittest.TestCase):
    def test_body_is_twice_as_loud_as_middle_and_top_at_rest_and_full(self):
        try: import generate
        except ImportError as e: self.skipTest(f'sound map tools not installed: {e}')
        generate.BODY = True; generate.VOICES[:] = ['stack']; generate.GENES['stFall'] = (.35, .7, 0)
        for _ in range(500):
            g = generate.body_led(generate.random_genome())
            n, f = g['stLayers'], g['stFall']
            top = f ** (n - 1) * (1 + g['stShimmer']) + g['stFifth'] * sum(f ** k for k in range(n) if g['stRoot'] * 2 ** k >= 220)
            self.assertTrue(generate.body_rule(generate.voice_of(g)['stack']))  # the pool filter agrees with the generator
            for p in ('stRest', 'stFull'):
                if n > 2: self.assertLessEqual(g[p + '1'] * f, g[p + '0'] / 2 + 1e-9)
                self.assertLessEqual(g[p + '2'] * top, g[p + '0'] / 2 + 1e-9)

    def test_variations_of_a_body_led_sound_stay_body_led(self):
        try: import variations, generate
        except ImportError as e: self.skipTest(f'sound map tools not installed: {e}')
        import json
        pool = json.load(open(Path(__file__).resolve().parents[1] / 'experiment' / 'sound_map_pool.json'))['sounds']
        led = [s for s in pool if generate.body_rule(s['voice']['stack'])]
        self.assertTrue(led)
        for s in led:
            for name, (voice, fx) in variations.moves(s).items(): self.assertTrue(generate.body_rule(voice['stack']), name)


if __name__ == '__main__':
    unittest.main()
