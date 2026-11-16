"""Simulated listeners for the sound-map search (experiment/source_search.py SoundMapDiscovery).
Each listener has a hidden taste over the pool: an ideal sound (a random pool sound) and random weights saying which features matter;
a sound's utility is minus its weighted distance to the ideal. Answers are noisy (Bradley-Terry with temperature), with Both good /
Neither when both sounds are clearly above / below the listener's median. Score: where the shortlist's top sound sits in the
listener's own ranking of the whole pool. Baseline: the same session with challengers in random order (no learning).
Usage: python -m tools.benchmark_sound_map [listeners per condition, default 200]"""
import math, random, sys
from multiprocessing import Pool
import numpy as np
from experiment.source_search import SoundMapDiscovery

NOISE = .15  # temperature: utility gap at which the better sound wins 73% of the time


def session(args):
    seed, policy = args
    rng = np.random.default_rng(seed)
    d = SoundMapDiscovery(renderer=lambda r: None); d.start(); d.rng = random.Random(seed)
    if policy == 'random': d._sampled = lambda recipe: d.rng.random()  # challengers in random order
    units = np.array([s['unit'] for s in d.pool])
    ideal, weight = units[rng.integers(len(units))], rng.dirichlet(np.ones(units.shape[1]) * .5)  # a few features matter most
    utility = lambda u: -float(np.sqrt(weight @ (u - ideal) ** 2))
    pool_u = np.array([utility(u) for u in units]); median = float(np.median(pool_u))
    for _ in range(20):
        if len(d.pair) != 2: break
        ua, ub = (utility(d._unit(d.candidates[i]['recipe'])) for i in d.pair)
        if min(ua, ub) > median + .1: choice = 'good'
        elif max(ua, ub) < median - .1: choice = 'neither'
        else: choice = 'A' if rng.random() < 1 / (1 + math.exp(-(ua - ub) / NOISE)) else 'B'
        d.feedback(choice=choice)
    top = utility(d._unit(d.candidates[d.finalists[0]]['recipe']))
    d.close()
    return int(np.sum(pool_u > top)) + 1  # 1 = the listener's favourite sound in the whole pool


if __name__ == '__main__':
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 200
    with Pool() as pool:
        for policy in ('map', 'random'):
            ranks = np.array(pool.map(session, [(s, policy) for s in range(n)]))
            print(f"{policy:7} listeners {n}: top sound is the favourite {np.mean(ranks == 1):.0%}, in top 5% {np.mean(ranks <= 4.5):.0%} "
                  f"(+-{2 * np.sqrt(np.mean(ranks <= 4.5) * (1 - np.mean(ranks <= 4.5)) / n):.0%}), top 10% {np.mean(ranks <= 9):.0%}, median rank {np.median(ranks):.0f} of 90")
