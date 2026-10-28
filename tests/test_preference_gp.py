import unittest
from unittest.mock import patch

import numpy as np

from experiment.preference_gp import select_query


class PreferenceGPTest(unittest.TestCase):
    def test_challenger_follows_preference_direction(self):
        pool = [[0.0], [0.3], [0.6], [1.0]]
        self.assertEqual(select_query(pool, [[0.]], [[1.]], ['B'], [.5], incumbent=1), (1, 3))
        self.assertEqual(select_query(pool, [[0.]], [[1.]], ['A'], [.5], incumbent=1), (1, 0))

    def test_seen_pairs_and_near_duplicates_are_excluded(self):
        pool = [[0.], [.001], [.3], [.8]]
        self.assertEqual(select_query(pool, [], [], [], [.5], [(3, 0)], incumbent=0), (0, 2))
        self.assertEqual(select_query(pool, [], [], [], [.5], incumbent=0,
                                      min_distance=.5), (0, 3))
        self.assertIsNone(select_query(pool, [], [], [], [.5], [(0, 2), (0, 3)], incumbent=0))

    def test_uncertainty_allows_exploration_after_observed_tie(self):
        self.assertEqual(select_query([[0.], [.1], [1.]], [[0.]], [[.1]], ['equal'], [.5],
                                      incumbent=0), (0, 2))

    def test_group_kernel_transfers_pitch_preference_across_texture(self):
        pool = [[0., 1., 1.], [1., 1., 1.], [0., 0., 0.], [1., 0., 0.],
                [.5, 0., .5], [0., 0., .5], [.5, .5, 0.]]
        args = (pool, [[0., 0., 0.]], [[1., 0., 0.]], ['B'], [0., 0., 0.])
        self.assertEqual(select_query(*args, seen_pairs=((0, 3),), incumbent=0,
                                      kernel_groups=((0,), (1, 2))), (0, 1))
        self.assertEqual(select_query(*args, seen_pairs=((0, 3),), incumbent=0), (0, 4))

    def test_zero_variance_and_failed_fit_keep_incumbent(self):
        pool = [[0.], [.5], [1.]]
        with patch('experiment.preference_gp._kernel', side_effect=lambda a, b: np.zeros((len(a), len(b)))):
            self.assertEqual(select_query(pool, [[0.]], [[1.]], ['equal'], [.5], incumbent=1), (1, 0))
        with patch('experiment.preference_gp.np.linalg.cholesky', side_effect=np.linalg.LinAlgError):
            self.assertEqual(select_query(pool, [[0.]], [[1.]], ['B'], [.5], incumbent=1), (1, 0))
