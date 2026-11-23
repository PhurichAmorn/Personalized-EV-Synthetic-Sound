"""Simulated listeners for the building-block session (BlockDiscovery, experiment/source_search.py): the benchmark plan in docs/research/.
A hidden oracle (one of five families) answers every pair; four arms differ only in how the broad challengers of the adaptive pairs are
ordered (Current = the app, Random, InfoGain = EUBO-style, IEC = crossover with the best other sound, no model). Everything else (starts, playoff,
replay, fine-tune pairs, Bradley-Terry shortlist, Both good / Neither handling) is the app's code, so arms differ in one place.
Budgets (pairs played, motion pair skipped = the oracle has no motion taste, Rising only):
  12 = 3 opening + 9 adaptive, scored right after (learner only);  17 = the app's session (adaptive 9);  30 = adaptive stretched to 22.
Oracle utilities are z-scored over every sound the table allows (the ground truth), so noise and thresholds are in SD units.
Usage: PYTHONHASHSEED=0 python -m tools.benchmark_blocks   (env: PROFILES, SEEDS, SEED_START, BUDGETS, ARMS, ORACLES, NOISE=logistic:0.5|flip:0.1|none, OUT, WORKERS)
Chunks (any split of oracles, budgets, arms, seeds, on any machine) combine with: python -m tools.benchmark_blocks summarize a.csv b.csv ..."""
import csv, itertools, json, math, os, random, sys
from multiprocessing import Pool
from unittest import mock
import numpy as np
from experiment import sound_blocks as sb, source_search as ss
from experiment.source_search import BlockDiscovery, block_features, block_moves

ORACLES = ('matched', 'multimodal', 'interaction', 'label', 'psycho')
GOOD_Z, NEITHER_Z = 3., 0.  # Both good when both sounds are above GOOD_Z SD, Neither when both are below NEITHER_Z SD. Calibrated 2026-11-23 to the real block sessions
# (19 sessions, 311 choices: Both good 1.6%, Neither 2.3%); simulated Current at 17 pairs, 5 oracles x 4 profiles x 3 seeds: Both good 2.7%, Neither 2.5%.
# (+-0.5 SD gave 49% Both good and 0.1% Neither: the session soon plays only good sounds, so Both good needs a high bar.)
SYNTH_OFF = {'buzz': 0, 'chord': 'off', 'bell': False, 'vowel': False}
_G = {}  # per-process: table, truth sounds


class Base(BlockDiscovery):
    """The app's session with a seed (so arms and noise are reproducible) and no rendering."""
    def __init__(self, seed, adaptive):
        super().__init__(renderer=lambda r: None); self.adaptive = adaptive; self._seed = seed
    def start(self, motion='rise'):
        with mock.patch.object(ss.random, 'SystemRandom', lambda: random.Random(self._seed)): super().start(motion)


class Current(Base): pass


class Random(Base):
    def _order_broad(self, out, here): out = list(out); self.rng.shuffle(out); return out


class InfoGain(Base):
    """EUBO-style: expected best of the pair, E[max(u(candidate), u(champion))], over 200 posterior draws of the taste."""
    def _order_broad(self, out, here):
        mean, cov = self._posterior(); W = np.random.default_rng(self.rng.randrange(2 ** 32)).multivariate_normal(mean, cov, 200, method='cholesky')
        uh = W @ block_features(here)
        return sorted(out, key=lambda m: -np.maximum(W @ self._features(m[0]), uh).mean())


class IEC(Base):
    """No model: uniform crossover of the champion with the sound that has the most wins (among the others), one random move on the child; offspring in random order."""
    KEYS = ('body', 'top', 'level', 'partner', 'buzz', 'chord', 'bell', 'vowel', 'pitch', 'brightness')
    def _order_broad(self, out, here):
        rows = self._choices(); wins = {}
        for r in rows:
            for i in r['pair']: wins.setdefault(i, 0.)
            if r['winner']: wins[r['winner']] += 1
            elif r['choice'] == 'good':
                for i in r['pair']: wins[i] += .5
        mates = [i for i in wins if i != self.champion]
        if not mates: out = list(out); self.rng.shuffle(out); return out
        mate = self._sound(max(mates, key=lambda i: (wins[i], i))); kids, seen = [], set()
        for _ in range(300):
            c = {k: (mate if self.rng.random() < .5 else here)[k] for k in self.KEYS}
            if c['top'] not in ('synth', 'bell'): c.update(SYNTH_OFF)
            if c['partner'] not in (None, *sb.PARTNERS.get(c['top'], ())): c['partner'] = None
            if self.rng.random() < .5:
                moves = block_moves(c, self.rng.choice(ss.BLOCK_BROAD_GROUPS))
                if moves: c = moves[self.rng.randrange(len(moves))][0]
            r = self._recipe(c)
            if r is None or sum(r['blocks'][k] != here[k] for k in here) < 2 or sb.key(r['blocks']) in seen: continue
            seen.add(sb.key(r['blocks'])); kids.append((r, {'kind': 'broad', 'groups': [], 'parent': self.champion, 'summary': 'IEC: crossover', 'far': 0}))
        rest = list(out); self.rng.shuffle(rest)
        return kids + rest


ARMS = {'current': Current, 'random': Random, 'infogain': InfoGain, 'iec': IEC}


def truth():
    """Every sound the table allows: body x top x partner x level x pitch x synth knobs x a brightness grid, as the session would build it."""
    if 'truth' in _G: return _G['truth']
    d = Base(0, 9); d._load(); T = []; seen = set()
    for body, top, lv, pi, br in itertools.product(sb.BODIES, sb.TOPS, sb.TOP_LEVELS, range(len(sb.PITCHES)), (.25, .4, .55, .7, .85)):
        knobs = [dict(SYNTH_OFF)] if top not in ('synth', 'bell') else [{'buzz': bz, 'chord': ch, 'bell': bl, 'vowel': vw} for bz in (0, 2) for ch in ('off', 'on') for bl in (False, True) for vw in (False, True)]
        for partner in (None, *sb.PARTNERS.get(top, ())):
            for k in knobs:
                r = d._recipe({'body': body, 'top': top, 'level': lv, 'pitch': pi, 'brightness': br, 'partner': partner, **k})
                if r and sb.key(r['blocks']) + f"|{r['blocks']['brightness']}" not in seen:
                    seen.add(sb.key(r['blocks']) + f"|{r['blocks']['brightness']}"); T.append(r)
    d.close(); _G['truth'] = T; _G['X'] = np.array([block_features(r['blocks']) for r in T]); _G['table'] = d.table
    return T


def bands(table, recipe):
    e = sb.nearest_entry(table, recipe['blocks']); return np.array(e['bands'][sb.point(recipe['fx']['tone'])], float)


def make_oracle(family, seed):
    """-> function(recipe) -> raw utility. The families are written on the sound's block values, brightness, or the table's measured octave bands, not on the model's feature vector."""
    rng = np.random.default_rng(seed); table = _G['table']
    val = {k: {v: rng.normal() for v in vs} for k, vs in (('body', sb.BODIES), ('top', sb.TOPS), ('level', sb.TOP_LEVELS))}
    sk = {k: rng.normal() * .7 for k in ('buzz', 'chord', 'bell', 'vowel', 'partner')}
    p0, b0, pw, bw = rng.uniform(0, 4), rng.uniform(.25, .85), rng.uniform(.3, 1), rng.uniform(.3, 1)
    def additive(r, v=val, p=p0, b=b0):
        s = r['blocks']; u = v['body'][s['body']] + v['top'][s['top']] + v['level'][s['level']] - pw * (s['pitch'] - p) ** 2 / 4 - bw * ((s['brightness'] - b) / .2) ** 2
        return u + sk['buzz'] * (s['buzz'] > 0) + sk['chord'] * (s['chord'] != 'off') + sk['bell'] * s['bell'] + sk['vowel'] * s['vowel'] + sk['partner'] * (s['partner'] is not None)
    if family == 'matched': return additive
    if family == 'multimodal':
        v2 = {k: {v: rng.normal() for v in vs} for k, vs in val.items()}; p2, b2 = rng.uniform(0, 4), rng.uniform(.25, .85)
        return lambda r: max(additive(r), additive(r, v2, p2, b2))  # two separate peaks (raw scales alike: z-scored together after)
    if family == 'interaction':
        c = rng.choice([-1, 1]) * 1.2; table2 = {(t, l): rng.normal() for t in sb.TOPS for l in sb.TOP_LEVELS}
        return lambda r: .4 * additive(r) + c * ((r['blocks']['pitch'] - 2) / 2) * ((r['blocks']['brightness'] - .55) / .2) + 1.2 * table2[(r['blocks']['top'], r['blocks']['level'])]
    if family == 'label':  # one random value for each whole (body, top, partner) combination, plus a little pitch taste
        tab = {}
        def u(r):
            s = r['blocks']; k = (s['body'], s['top'], s['partner'])
            if k not in tab: tab[k] = rng.normal()
            return tab[k] - .3 * (s['pitch'] - p0) ** 2 / 4
        return u
    if family == 'psycho':  # measured octave bands (the model never sees them): low/mid/high balance and spread, an ideal point on each
        t1, t2, t3 = rng.normal(0, 4), rng.normal(0, 3), rng.uniform(2, 8)
        def u(r):
            b = bands(table, r); low, mid, high = b[:3].mean(), b[3:6].mean(), b[6:].mean()
            return -((low - mid - t1) / 5) ** 2 - ((mid - high - t2) / 5) ** 2 - ((b.std() - t3) / 3) ** 2
        return u
    raise ValueError(family)


def oracle(family, seed):
    """Utility z-scored over the ground-truth set; the array is cached for the profile."""
    T = truth(); raw = make_oracle(family, seed); u = np.array([raw(r) for r in T]); m, s = u.mean(), u.std() or 1.
    return (lambda r: (raw(r) - m) / s), (u - m) / s


def answer(rng, za, zb, noise):
    if min(za, zb) > GOOD_Z: return 'good'
    if max(za, zb) < NEITHER_Z: return 'neither'
    kind, level = noise
    if kind == 'logistic': a = rng.random() < 1 / (1 + math.exp(-(za - zb) / level))
    else: a = (za > zb) != (rng.random() < level) if kind == 'flip' else za > zb
    return 'A' if a else 'B'


def run(job):
    family, profile, seed, arm, budget, noise = job
    z, zt = oracle(family, 7919 * profile + ORACLES.index(family))
    adaptive = 22 if budget == 30 else 9; pairs = {12: 12, 17: 16, 30: 29}[budget]
    d = ARMS[arm](seed, adaptive); d.start('rise'); rng = random.Random(seed * 31 + 5); n = 0
    for _ in range(pairs):
        if len(d.pair) != 2: break
        za, zb = (z(d.candidates[i]['recipe']) for i in d.pair); d.feedback(choice=answer(rng, za, zb, noise)); n += 1
    d._rank_finalists(); short = [z(d.candidates[i]['recipe']) for i in d.finalists] or [-9.]
    w = d._weights(); X = _G['X']; g = np.random.default_rng(0); i, j = g.integers(len(X), size=(2, 3000)); gap = zt[i] - zt[j]; keep = np.abs(gap) > .5
    acc = float(np.mean(np.sign((X[i] - X[j]) @ w)[keep] == np.sign(gap)[keep])) if keep.any() else float('nan')
    d.close(); u1 = short[0]; share = (int(np.sum(zt > u1)) + 1) / len(zt)
    return dict(oracle=family, profile=profile, seed=seed, arm=arm, budget=budget, noise=f'{noise[0]}:{noise[1]}', pairs=n, z1=round(u1, 3), regret=round(max(float(zt.max()) - u1, 0), 3),
                share=round(share, 4), top5=int(share <= .05), top10=int(share <= .10), short5=int(any(np.sum(zt > s) + 1 <= .05 * len(zt) for s in short)), acc=round(acc, 3))


def summary(rows):
    """Per oracle and budget: mean top-10% and regret by arm, and the paired difference to Random with a profile-level bootstrap CI."""
    import collections
    rng = np.random.default_rng(0); by = collections.defaultdict(dict)
    for r in rows: by[(r['oracle'], r['budget'], r['noise'])].setdefault((r['profile'], r['seed']), {})[r['arm']] = r
    for key in sorted(by):
        cells = by[key]; arms = sorted({a for c in cells.values() for a in c}); print(key, 'n =', len(cells))
        for a in arms:
            t10 = np.mean([c[a]['top10'] for c in cells.values() if a in c]); rg = np.mean([c[a]['regret'] for c in cells.values() if a in c]); ac = np.nanmean([c[a]['acc'] for c in cells.values() if a in c])
            line = f'   {a:9} top10 {t10:.2f}  regret {rg:.2f}  held-out acc {ac:.2f}'
            if a != 'random' and 'random' in arms:
                by_p = collections.defaultdict(list)
                for (p, s), c in cells.items():
                    if a in c and 'random' in c: by_p[p].append(c[a]['top10'] - c['random']['top10'])
                ps = [np.mean(v) for v in by_p.values()]; boots = [np.mean(rng.choice(ps, len(ps))) for _ in range(1000)]
                line += f'   vs random {np.mean(ps):+.2f} [{np.percentile(boots, 2.5):+.2f}, {np.percentile(boots, 97.5):+.2f}]'
            print(line)


if __name__ == '__main__' and sys.argv[1:2] == ['summarize']:  # python -m tools.benchmark_blocks summarize a.csv b.csv ...: combine chunk files
    rows = []
    for f in sys.argv[2:]:
        for r in csv.DictReader(open(f)): rows.append({**r, 'profile': int(r['profile']), 'seed': int(r['seed']), 'budget': int(r['budget']), 'top10': int(r['top10']), 'regret': float(r['regret']), 'acc': float(r['acc'])})
    keys = [(r['oracle'], r['profile'], r['seed'], r['arm'], r['budget'], r['noise']) for r in rows]
    assert len(keys) == len(set(keys)), 'duplicate sessions in the chunk files'
    summary(rows)
elif __name__ == '__main__':
    e = os.environ.get; noise = e('NOISE', 'logistic:0.5').split(':') + ['0']; noise = (noise[0], float(noise[1]))
    jobs = [(f, p, s, a, b, noise) for f in e('ORACLES', ','.join(ORACLES)).split(',') for p in range(int(e('PROFILES', 5))) for s in range(int(e('SEED_START', 0)), int(e('SEED_START', 0)) + int(e('SEEDS', 2)))
            for b in map(int, e('BUDGETS', '12,17,30').split(',')) for a in e('ARMS', ','.join(ARMS)).split(',')]
    truth(); print(len(_G['truth']), 'sounds in the ground-truth set;', len(jobs), 'sessions', flush=True)
    with Pool(int(e('WORKERS', os.cpu_count()))) as pool: rows = pool.map(run, jobs, chunksize=4)
    out = e('OUT', 'benchmark_blocks.csv')
    with open(out, 'w', newline='') as f: w = csv.DictWriter(f, rows[0]); w.writeheader(); w.writerows(rows)
    summary(rows); print('rows ->', out)
