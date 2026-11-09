import csv
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

import numpy as np
from scipy.io.wavfile import read

from experiment.recipes import recipe_ids
from tools.render_recipe_review import render_review


class RecipeReviewTest(unittest.TestCase):
    def test_all_recipes_use_same_five_drive_scenarios(self):
        with TemporaryDirectory() as directory:
            render_review(Path(directory))
            files = sorted(Path(directory).glob('*.wav'))
            self.assertEqual(len(files), 18)
            with (Path(directory) / 'metrics.csv').open(newline='') as report:
                rows = list(csv.DictReader(report))
            self.assertEqual(len(rows), 90)
            self.assertEqual({row['position'] for row in rows}, {'low', 'base', 'high'})
            self.assertEqual({row['scenario'] for row in rows},
                             {'start', 'low', 'high', 'accelerate', 'regen'})
            for path in files:
                rate, samples = read(path)
                self.assertEqual(rate, 48000)
                self.assertTrue(np.isfinite(samples).all())
                self.assertLess(np.max(np.abs(samples.astype(np.float32) / 32768)), .5)
            for mode in ('Comfort', 'Sport', 'Deep'):
                spectra = []
                for recipe_id in recipe_ids(mode):
                    _, samples = read(Path(directory) / f'{recipe_id}_base.wav')
                    steady = samples[int(5.2 * 48000):int(6.2 * 48000)] * np.hanning(48000)
                    spectrum = np.abs(np.fft.rfft(steady))
                    spectra.append(spectrum / spectrum.sum())
                self.assertGreater(np.abs(spectra[0] - spectra[1]).sum() / 2, .2, mode)


if __name__ == '__main__':
    unittest.main()
