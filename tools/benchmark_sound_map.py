"""Simulated listeners for the sound-map search (experiment/source_search.py).
Each listener has a hidden taste over the pool: an ideal sound (a random pool sound) and random weights saying which heard traits matter;
a sound's utility is minus its weighted distance to the ideal. Listener kinds: 'traits' (that only), 'texture' (also a bonus for one
texture style, which the traits cannot see), 'mixed' (half that bonus). Answers are noisy (Bradley-Terry with temperature), with Both
good / Neither when both sounds are clearly above / below the listener's median.
Policies, all on the same pool: grid (HeardMapDiscovery, deep/middle/high x dark/bright cells, the app's session), kmeans (the same
session on k-means regions of the heard traits), styles (StyleMapDiscovery: texture styles as regions, style one-hot in the model),
map (SoundMapDiscovery, no regions), random (grid with challengers in random order: no learning).
Score: where the shortlist's top sound sits in the listener's own ranking of the whole pool.
Usage: python -m tools.benchmark_sound_map [listeners per condition, default 200] [pool file, default the app's pool]"""
import json, math, os, random, sys, tempfile
from multiprocessing import Pool
import numpy as np
from experiment import source_search
from experiment.source_search import SoundMapDiscovery, StyleMapDiscovery, HeardMapDiscovery, MAP_POOL, map_style

NOISE = float(os.environ.get('NOISE', .15))   # temperature: utility gap at which the better sound wins 73% of the time
STYLE_BONUS = float(os.environ.get('STYLE_BONUS', .3))  # texture listener: utility bonus of the liked style (a typical utility gap between pool sounds is ~.1-.4)
PAIRS = int(os.environ.get('PAIRS', 20))  # session length (the app: 20); MAP_EXPLORE and the 3 fine-tune pairs stay, focus takes the rest
POLICIES = {'grid': HeardMapDiscovery, 'kmeans': HeardMapDiscovery, 'styles': StyleMapDiscovery, 'map': SoundMapDiscovery, 'random': HeardMapDiscovery}


def session(args):
    seed, policy, kind, pools = args
    source_search.STYLE_PAIRS = PAIRS
    if os.environ.get('REPEATS') == '0': source_search.MAP_REPEATS = {}  # the session without its 2 repeat pairs
    rng = np.random.default_rng(seed)
    d = POLICIES[policy](renderer=lambda r: None, pool_path=pools['kmeans' if policy == 'kmeans' else 'grid']); d.start('rise'); d.rng = random.Random(seed)
    if policy == 'random': d._sampled = lambda recipe: d.rng.random()  # challengers in random order
    units = np.array([s['unit'] for s in d.pool]); styles = sorted({map_style(s) for s in d.pool})
    ideal, weight = units[rng.integers(len(units))], rng.dirichlet(np.ones(units.shape[1]) * .5)  # a few traits matter most
    liked, bonus = styles[rng.integers(len(styles))], {'traits': 0, 'texture': STYLE_BONUS, 'mixed': STYLE_BONUS / 2}[kind]
    def utility(cell):
        s = d.by_cell[cell]
        return -float(np.sqrt(weight @ (d._unit(map_recipe_of(s)) - ideal) ** 2)) + bonus * (map_style(s) == liked)
    map_recipe_of = lambda s: {'version': 5, 'kind': 'map', 'seed': 0, 'motion': 'rise', 'cell': s['id'], 'voice': s['voice'], 'fx': s['fx']}
    pool_u = np.array([utility(s['id']) for s in d.pool]); median = float(np.median(pool_u))
    for _ in range(PAIRS):
        if len(d.pair) != 2: break
        ua, ub = (utility(d.candidates[i]['recipe']['cell']) for i in d.pair)
        if min(ua, ub) > median + .1: choice = 'good'
        elif max(ua, ub) < median - .1: choice = 'neither'
        else: choice = 'A' if rng.random() < 1 / (1 + math.exp(-(ua - ub) / NOISE)) else 'B'
        d.feedback(choice=choice)
    top = utility(d.candidates[d.finalists[0]]['recipe']['cell'])
    d.close()
    return (int(np.sum(pool_u > top)) + 1) / len(pool_u)  # rank as a share of the pool: 1/len = the listener's favourite


if __name__ == '__main__':
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 200
    grid = os.path.abspath(sys.argv[2]) if len(sys.argv) > 2 else str(MAP_POOL)
    data = json.load(open(grid))
    for s in data['sounds']: s.pop('cell', None)  # the same sounds without cells: k-means regions
    kmeans = os.path.join(tempfile.mkdtemp(), 'pool.json'); json.dump(data, open(kmeans, 'w'))
    pools = {'grid': grid, 'kmeans': kmeans}
    with Pool(int(os.environ.get('WORKERS', os.cpu_count()))) as pool:
        for kind in os.environ.get('KINDS', 'traits,mixed,texture').split(','):
            for policy in os.environ.get('POLICY_LIST', ','.join(POLICIES)).split(','):
                share = np.array(pool.map(session, [(s, policy, kind, pools) for s in range(n)])); top5 = np.mean(share <= .05)
                print(f"{kind:7} {policy:7} pool={len(data['sounds'])} pairs={PAIRS} noise={NOISE} n={n}: pick in the listener's top 5% {top5:.0%} (+-{2 * np.sqrt(top5 * (1 - top5) / n):.0%}), "
                      f"top 10% {np.mean(share <= .1):.0%}, median rank {np.median(share):.0%} of the pool", flush=True)
