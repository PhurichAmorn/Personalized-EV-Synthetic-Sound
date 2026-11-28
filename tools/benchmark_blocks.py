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
from scipy.stats import norm
from experiment import block_arms as ba, sound_blocks as sb, source_search as ss
from experiment.block_arms import enc
from experiment.source_search import BlockDiscovery, block_features, block_moves

ORACLES = ('matched', 'multimodal', 'interaction', 'label', 'psycho')
GOOD_Z, NEITHER_Z = float(os.environ.get('GOOD_Z', 3)), float(os.environ.get('NEITHER_Z', 0))  # env override only for the Both/Neither-removed sensitivity run (GOOD_Z=1e9 NEITHER_Z=-1e9). Both good when both sounds are above GOOD_Z SD, Neither when both are below NEITHER_Z SD. Calibrated 2026-11-23 to the real block sessions
REPLAY = os.environ.get('REPLAY') == '1'  # 1 = the app until 2026-11-24 (pair 14 replays pair 4, adaptive 9/22); default: no replay, one more challenger pair (adaptive 10/23), as the app
# (19 sessions, 311 choices: Both good 1.6%, Neither 2.3%); simulated Current at 17 pairs, 5 oracles x 4 profiles x 3 seeds: Both good 2.7%, Neither 2.5%.
# (+-0.5 SD gave 49% Both good and 0.1% Neither: the session soon plays only good sounds, so Both good needs a high bar.)
NEW_BIAS = float(os.environ.get('NEW_BIAS', 0))  # SD added to a sound the listener has not heard before (real block sessions: the new sound won 65% of champion pairs, 2026-11-27)
SYNTH_OFF = {'buzz': 0, 'chord': 'off', 'bell': False, 'vowel': False}
_G = {}  # per-process: table, truth sounds


class Base(BlockDiscovery):
    """The app's session with a seed (so arms and noise are reproducible) and no rendering."""
    def __init__(self, seed, adaptive):
        super().__init__(renderer=lambda r: None); self.adaptive = adaptive; self.replay = REPLAY; self._seed = seed
    def held_out_scores(self, X): return X @ self._weights()
    def start(self, motion='rise'):
        with mock.patch.object(ss.random, 'SystemRandom', lambda: random.Random(self._seed)): super().start(motion)


class Current(Base): pass


class Random(ba.RandomMixin, Base): pass


class InfoGain(ba.InfoGainMixin, Base): pass


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


# ---- Arms added 2026-11-23 (plan amendment): code shared with the app in experiment/block_arms.py ----
class GPScores:
    def held_out_scores(self, X): return self._gp().predict(_G['enc'], cov=False)[0]  # the arm's own model, not the app's linear one


class PBOGP(GPScores, ba.PBOMixin, Base): pass
class Duel(GPScores, ba.DuelMixin, ba.FreeMixin, Base): pass
class Robust(ba.RobustMixin, Base): pass


class Guess(ba.GuessBlocks, Base): pass  # best guess vs might-be-better (2026-11-27): no starts, no champion


class GuessLevels(Guess):  # trial 2026-11-27: pitch and brightness levels as categories (lower top-10%, not adopted)
    feature_names = ba.LEVEL_FEATURE_NAMES
    def _features(self, recipe): return ba.level_features(recipe['blocks'])
    def held_out_scores(self, X):
        if 'Xg' not in _G: _G['Xg'] = np.array([ba.level_features(r['blocks']) for r in _G['truth']])
        return _G['Xg'] @ self._weights()


class GuessBoth(Guess):  # trial 2026-11-27: the curve AND one category per level (= v1 without bias, worse with NEW_BIAS; not adopted)
    feature_names = ss.BLOCK_FEATURE_NAMES + ba.LEVEL_FEATURE_NAMES[-10:]
    def _features(self, recipe): return np.concatenate([block_features(recipe['blocks']), ba.level_features(recipe['blocks'])[-10:]])
    def held_out_scores(self, X):
        if 'Xb' not in _G: _G['Xb'] = np.array([self._features(r) for r in _G['truth']])
        return _G['Xb'] @ self._weights()


# ---- Pair-choice arms on the Best guess shell (2026-11-27): same model (Bayesian Bradley-Terry over block features), same 15,614 sounds,
# same shared rules (clearly different, no pair twice); only _pick differs. Names in the report: docs/research/benchmark_guess_results.md ----
class Shell(Guess):
    def _build_space(self): self.space, self.X, self.ids = _G['truth'], _G['X'], _G['ids']  # built once per process (truth())
    def _diff(self, a):
        """Mean and SD of u(sound) - u(a) for every sound."""
        mean, cov = self._posterior(); D = self.X - self.X[a]; return D @ mean, np.sqrt(np.maximum(np.einsum('ij,jk,ik->i', D, cov, D), 1e-12))
    def _draw(self): self._sample(); return self.X @ self._w_sample  # one Thompson sample (half spread, as the app)


class GRandom(Shell):  # random pairs: the floor
    def _pick(self):
        r = np.array([self.rng.random() for _ in self.ids]); a = self._first(r); return a, self._partner(a, np.array([self.rng.random() for _ in self.ids]))


class GGreedy(Shell):  # no exploration: best vs second best by posterior mean
    def _pick(self): m = self.X @ self._weights(); a = self._first(m); return a, self._partner(a, m)


class GExplore(Shell):  # best guess vs the most uncertain comparison (largest SD of the difference)
    def _pick(self): a = self._first(self.X @ self._weights()); return a, self._partner(a, self._diff(a)[1])


class GDTS(Shell):  # double Thompson sampling (Wu & Liu 2016), linear version: each sound from its own posterior draw
    def _pick(self): a = self._first(self._draw()); return a, self._partner(a, self._draw())


class GBrochu(Shell):  # Brochu, de Freitas & Ghosh 2007: best heard so far (incumbent) vs the sound of highest expected improvement over it
    def _pick(self):
        m = self.X @ self._weights(); heard = {i for r in self._choices() for i in r['pair']}
        inc = [k for k, i in enumerate(self.ids) if i in heard and self.ok[k]]
        a = max(inc, key=lambda k: m[k]) if inc else self._first(np.zeros(len(self.ids)))
        d, s = self._diff(a); z = d / s; return a, self._partner(a, d * norm.cdf(z) + s * norm.pdf(z))


class GRUCB(Shell):  # relative UCB (Zoghi et al. 2014), linear version: optimistic candidate vs its most optimistic rival
    C = 1.
    def _pick(self):
        mean, cov = self._posterior(); sd = np.sqrt(np.maximum(np.einsum('ij,jk,ik->i', self.X, cov, self.X), 1e-12))
        a = self._first(self.X @ mean + self.C * sd); d, s = self._diff(a); return a, self._partner(a, d + self.C * s)


class GPBO(Shell):  # dueling Thompson (Gonzalez et al. 2017), linear version: A from a posterior draw, B where P(B beats A) is most uncertain
    DRAWS = 100
    def _pick(self):
        a = self._first(self._draw()); mean, cov = self._posterior(); D = self.X - self.X[a]
        W = np.random.default_rng(self.rng.randrange(2 ** 32)).multivariate_normal(mean, cov, self.DRAWS, method='cholesky')
        return a, self._partner(a, (1 / (1 + np.exp(-(D @ W.T)))).var(1))


class GEUBO(Shell):  # EUBO (Lin et al. 2022): the app's EUBOBlocks pair choice (experiment/block_arms.py) on the benchmark shell
    DRAWS, TOP = ba.EUBOBlocks.DRAWS, ba.EUBOBlocks.TOP
    _pick = ba.EUBOBlocks._pick


class GIGA(Shell):
    """Interactive genetic algorithm (Fukumoto 2026, IJAE-D-26-00011, Table 1) with pairwise answers instead of 1-7 ratings: population 8,
    each generation = 4 pairs (fitness: win 1, loss 0, Both good 1 each, Neither 0 each), tournament selection (2), elitism (1), 2-point
    crossover 90%, mutation 5% per gene (pitch +-2 steps, brightness +-1 step, other genes redrawn). No model: the final sound is the best of
    the last finished generation. Genes the table rejects are redrawn; a pair that is not clearly different gets a random partner."""
    GENES = ('body', 'top', 'level', 'partner', 'pitch', 'brightness', 'buzz', 'chord', 'bell', 'vowel')
    def start(self, motion='rise'):
        self.pop, self.queue, self.elite = None, [], None; super().start(motion)
    def _random_gene(self):
        while True:
            r = self.space[self.rng.randrange(len(self.space))]['blocks']
            g = {**{k: r[k] for k in self.GENES}, 'brightness': min(range(len(ba.BRIGHTNESS_GRID)), key=lambda i: abs(ba.BRIGHTNESS_GRID[i] - r['brightness']))}
            if self._index(g) is not None: return g
    def _index(self, g):
        r = self._recipe({**g, 'brightness': ba.BRIGHTNESS_GRID[g['brightness']]}); return _G['index'].get(self._id(r)) if r else None
    def _fix(self, g):
        if g['top'] not in ('synth', 'bell'): g.update(SYNTH_OFF)
        if g['partner'] not in (None, *sb.PARTNERS.get(g['top'], ())): g['partner'] = None
        return g
    def _mutate(self, g):
        g = dict(g)
        for k in self.GENES:
            if self.rng.random() >= .05: continue
            if k == 'pitch': g[k] = min(max(g[k] + self.rng.choice((-2, -1, 1, 2)), 0), len(sb.PITCHES) - 1)
            elif k == 'brightness': g[k] = min(max(g[k] + self.rng.choice((-1, 1)), 0), len(ba.BRIGHTNESS_GRID) - 1)
            else: g[k] = self._random_gene()[k]
        return self._fix(g)
    def _child(self, p1, p2):
        for _ in range(20):
            g = dict(p1)
            if self.rng.random() < .9:
                i, j = sorted(self.rng.sample(range(len(self.GENES) + 1), 2)); g.update({k: p2[k] for k in self.GENES[i:j]})
            g = self._mutate(self._fix(g))
            if self._index(g) is not None: return g
        return self._random_gene()
    def _fitness(self):
        rows = self._choices()[-4:]; fit = {}
        for r in rows:
            for i in r['pair']: fit[i] = max(fit.get(i, 0.), 1. if r['winner'] == i or r['choice'] == 'good' else 0.)
        return fit
    def _scores(self):
        fit = self._fitness(); return [fit.get(self.ids[self._index(g)], 0.) for g in self.pop]
    def _best(self, f):  # ties: the previous elite, then the first
        return self.pop[max(range(8), key=lambda n: (f[n], self.pop[n] is self.elite, -n))]
    def _next_generation(self):
        f = self._scores(); self.elite = self._best(f)
        pick = lambda: max(self.rng.sample(range(8), 2), key=lambda n: (f[n], self.rng.random()))
        self.pop = [self.elite] + [self._child(self.pop[pick()], self.pop[pick()]) for _ in range(7)]
    def _pairing(self):
        idx = [self._index(g) for g in self.pop]
        for _ in range(50):
            order = list(range(8)); self.rng.shuffle(order); pairs = [(idx[order[n]], idx[order[n + 1]]) for n in range(0, 8, 2)]
            if all(a != b and frozenset((self.ids[a], self.ids[b])) not in self.met and self._clear(self.space[a], self.space[b]) for a, b in pairs): return pairs
        return [(a, b if a != b and self._clear(self.space[a], self.space[b]) else self._partner(a, np.array([self.rng.random() for _ in self.ids]))) for a, b in pairs]
    def _pick(self):
        if not self.queue:
            if self.pop is None: self.pop = [self._random_gene() for _ in range(8)]; self.pop = [g if self._index(g) is not None else self._random_gene() for g in self.pop]
            else: self._next_generation()
            self.queue = self._pairing()
        return self.queue.pop(0)
    def _rank_finalists(self):
        """The paper's final: the best individual of the last finished generation (the elite chosen from it)."""
        if self.pop is None: self.finalists = []; return
        g = self._best(self._scores()) if not self.queue and self._choices() else self.elite or self.pop[0]  # queue empty: the generation just finished
        self.finalists = [self._add(self.space[self._index(g)], {'kind': 'guess', 'summary': 'IGA elite'})]


class Pairs(GPScores, ba.FreeMixin, Base):
    """Two random clearly different sounds, no champion, no model (benchmark only)."""
    def _pick(self, cand):
        a = cand[self.rng.randrange(len(cand))]; return a, next(c for c in self.rng.sample(cand, len(cand)) if c is not a and self._clear(a, c))


CORE = ('current', 'random', 'infogain', 'iec')
ARMS = {'current': Current, 'random': Random, 'infogain': InfoGain, 'iec': IEC, 'pbogp': PBOGP, 'duel': Duel, 'pairs': Pairs, 'robust': Robust, 'guess': Guess, 'guesslevels': GuessLevels, 'guessboth': GuessBoth,
        'grandom': GRandom, 'ggreedy': GGreedy, 'gexplore': GExplore, 'gdts': GDTS, 'gbrochu': GBrochu, 'grucb': GRUCB, 'gpbo': GPBO, 'geubo': GEUBO, 'giga': GIGA}
GUESS_ARMS = ('guess', 'grandom', 'ggreedy', 'gexplore', 'gdts', 'gbrochu', 'grucb', 'gpbo', 'geubo', 'giga')  # the 2026-11-27 pair-choice comparison


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
    _G['ids'] = [d._id(r) for r in T]; _G['index'] = {i: k for k, i in enumerate(_G['ids'])}; d.close(); _G['truth'] = T; _G['X'] = np.array([block_features(r['blocks']) for r in T]); _G['enc'] = enc([r['blocks'] for r in T]); _G['table'] = d.table
    return T


_ENTRY = {}


def bands(table, recipe):
    k = sb.key(recipe['blocks'])  # nearest_entry scans the whole table for an unmeasured combination: cached (the psycho oracle was 15x slower than the others)
    if k not in _ENTRY: _ENTRY[k] = sb.nearest_entry(table, recipe['blocks'])
    return np.array(_ENTRY[k]['bands'][sb.point(recipe['fx']['tone'])], float)


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
    adaptive = (9 if budget < 17 else budget - 8) + (0 if REPLAY else 1); pairs = 12 if budget == 12 else budget - 1  # 12 = early cut; 17 = the app (adaptive 9/10); longer: adaptive stretched (20: 12/13, 30: 22/23, ...). Until 2026-11-27 budgets 18-29 were cut at 16 pairs
    d = ARMS[arm](seed, adaptive); d.start('rise'); rng = random.Random(seed * 31 + 5); n = 0; best = -9.
    for _ in range(pairs):
        if len(d.pair) != 2: break
        za, zb = (z(d.candidates[i]['recipe']) for i in d.pair); best = max(best, za, zb); heard = {i for r in d.history for i in r['pair']}
        ba_, bb_ = (NEW_BIAS * (i not in heard) for i in d.pair); d.feedback(choice=answer(rng, za + ba_, zb + bb_, noise)); n += 1
    d._rank_finalists(); short = [z(d.candidates[i]['recipe']) for i in d.finalists] or [-9.]
    X = _G['X']; sc = d.held_out_scores(X); g = np.random.default_rng(0); i, j = g.integers(len(X), size=(2, 3000)); gap = zt[i] - zt[j]; keep = np.abs(gap) > .5
    acc = float(np.mean(np.sign(sc[i] - sc[j])[keep] == np.sign(gap)[keep])) if keep.any() else float('nan')
    d.close(); u1 = short[0]; share = (int(np.sum(zt > u1)) + 1) / len(zt)
    return dict(oracle=family, profile=profile, seed=seed, arm=arm, budget=budget, noise=f'{noise[0]}:{noise[1]}', pairs=n, z1=round(u1, 3), regret=round(max(float(zt.max()) - u1, 0), 3),
                share=round(share, 4), top5=int(share <= .05), top10=int(share <= .10), heard10=int((np.sum(zt > best) + 1) / len(zt) <= .10), short5=int(any(np.sum(zt > s) + 1 <= .05 * len(zt) for s in short)), acc=round(acc, 3))


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


def load_rows(files):
    rows = []
    for f in files:
        for r in csv.DictReader(open(f)): rows.append({**r, 'profile': int(r['profile']), 'seed': int(r['seed']), 'budget': int(r['budget']), 'top10': int(r['top10']), 'top5': int(r['top5']), 'short5': int(r['short5']), 'heard10': int(r.get('heard10') or -1), 'regret': float(r['regret']), 'acc': float(r['acc'])})
    keys = [(r['oracle'], r['profile'], r['seed'], r['arm'], r['budget'], r['noise']) for r in rows]
    assert len(keys) == len(set(keys)), 'duplicate sessions in the chunk files'
    return rows


MIN_DIFF = .05  # plan section 5: better = CI above 0 and a difference of at least 5 points


def report(rows, noise, boots=2000):
    """The plan's contrast tables (docs/research/benchmark_blocks_plan.md section 4-5): paired by (profile, seed), profile-level bootstrap 95% CI."""
    import collections
    rng = np.random.default_rng(0); cell = collections.defaultdict(dict)
    for r in rows:
        if r['noise'] == noise: cell[(r['oracle'], r['budget'], r['profile'], r['seed'])][r['arm']] = r
    oracles = [o for o in ORACLES if any(k[0] == o for k in cell)]
    def per_profile(o, b, a, c, metric, ba=None):  # {profile: mean paired difference} for arm a at budget ba (default b) minus arm c at budget b
        d = collections.defaultdict(list)
        for (oo, bb, p, s), arms in cell.items():
            if oo != o or bb != b: continue
            other = cell.get((o, ba, p, s), {}) if ba else arms
            if (ba and a in other or not ba and a in arms) and c in arms: d[p].append((other[a] if ba else arms[a])[metric] - arms[c][metric])
        return {p: np.mean(v) for p, v in d.items()}
    def ci(sets):  # sets: list of {profile: value}, one per oracle; pooled = mean over oracles of the profile mean
        arr = [np.array(list(d.values())) for d in sets]
        if not all(len(x) for x in arr): return None
        point = np.mean([x.mean() for x in arr]); bs = [np.mean([rng.choice(x, len(x)).mean() for x in arr]) for _ in range(boots)]
        return point, np.percentile(bs, 2.5), np.percentile(bs, 97.5)
    def call(lo, hi, pt): return 'BETTER' if lo > 0 and pt >= MIN_DIFF else 'WORSE' if hi < 0 else 'no detectable difference'
    budgets = sorted({k[1] for k in cell}); n = len({(k[2], k[3]) for k in cell if k[0] == oracles[0] and k[1] == budgets[0]})
    print(f'noise {noise}; {len(oracles)} oracles; {n} sessions per oracle, budget and arm; rule: BETTER = CI above 0 and difference >= {MIN_DIFF}\n')
    print('PRIMARY: current minus random, top-10% retrieval'); tally = collections.Counter()
    for o in oracles:
        for b in budgets:
            r = ci([per_profile(o, b, 'current', 'random', 'top10')])
            if r: tally[call(r[1], r[2], r[0])] += 1; print(f'  {o:12} {b:3}  {r[0]:+.3f} [{r[1]:+.3f}, {r[2]:+.3f}]  {call(r[1], r[2], r[0])}')
    print('  tally:', dict(tally))
    print('\nHEADLINE: current minus random pooled over oracles, top-10%')
    for b in budgets:
        r = ci([per_profile(o, b, 'current', 'random', 'top10') for o in oracles])
        if r: print(f'  budget {b:3}  {r[0]:+.3f} [{r[1]:+.3f}, {r[2]:+.3f}]  {call(r[1], r[2], r[0])}')
    arms = {a for v in cell.values() for a in v}
    all_arms = set(arms)  # the loops below rebind `arms` to one cell's dict
    pairs = [(a, c) for a, c in (('infogain', 'current'), ('iec', 'current'), ('pbogp', 'current'), ('pbogp', 'infogain'), ('robust', 'current'), ('duel', 'current'), ('random', 'pairs'), ('current', 'pairs'), ('guess', 'current'), *((g, 'guess') for g in GUESS_ARMS[1:])) if a in arms and c in arms]
    for metric, name in (('top10', 'top-10% retrieval (higher is better)'), ('regret', 'regret in SD (lower is better)')):
        print(f'\nSECONDARY: arm A minus arm B, {name}')
        for a, c in pairs:
            for o in oracles:
                line = ''
                for b in budgets:
                    r = ci([per_profile(o, b, a, c, metric)]); line += f'  {b}: {r[0]:+.3f} [{r[1]:+.3f}, {r[2]:+.3f}]' if r else ''
                print(f'  {a:>8} - {c:<8} {o:12}{line}')
            for b in budgets:
                r = ci([per_profile(o, b, a, c, metric) for o in oracles])
                if r: print(f'  {a:>8} - {c:<8} {f"pooled @{b}":12}  {r[0]:+.3f} [{r[1]:+.3f}, {r[2]:+.3f}]' + (f'  {call(r[1], r[2], r[0])}' if metric == 'top10' else ''))
    base = 'current' if 'current' in all_arms else 'guess'
    print(f'\nBUDGET EFFECT: {base} at the longer budget minus {base} at the shorter, top-10%')
    for o in oracles:
        line = ''
        for lo, hi in zip(budgets, budgets[1:]):
            if hi in budgets and lo in budgets:
                d = collections.defaultdict(list)
                for (oo, bb, p, s), arms in cell.items():
                    if oo == o and bb == hi and base in arms and base in cell.get((o, lo, p, s), {}): d[p].append(arms[base]['top10'] - cell[(o, lo, p, s)][base]['top10'])
                r = ci([{p: np.mean(v) for p, v in d.items()}]); line += f'  {hi} vs {lo}: {r[0]:+.3f} [{r[1]:+.3f}, {r[2]:+.3f}]' if r else ''
        print(f'  {o:12}{line}')
    print('\nOTHER OUTCOMES: current minus random (top-5% = the #1 is in the top 5%; shortlist top-5% = any of the up to 5 shortlisted sounds is)')
    for metric in ('top5', 'short5'):
        for o in oracles:
            line = ''
            for b in budgets:
                r = ci([per_profile(o, b, 'current', 'random', metric)]); line += f'  {b}: {r[0]:+.3f} [{r[1]:+.3f}, {r[2]:+.3f}]' if r else ''
            print(f'  {metric:6} {o:12}{line}')
        line = ''
        for b in budgets:
            r = ci([per_profile(o, b, 'current', 'random', metric) for o in oracles]); line += f'  {b}: {r[0]:+.3f} [{r[1]:+.3f}, {r[2]:+.3f}]' if r else ''
        print(f'  {metric:6} {"pooled":12}{line}')
    print('\nEQUIVALENT RANDOM PAIRS: how many pairs Random needs to match an arm (linear interpolation of Random top-10% between the budgets played; a point estimate with no CI)')
    def mean_top10(o, b, a):
        sel = [v[a]['top10'] for k, v in cell.items() if k[0] == o and k[1] == b and a in v]
        return float(np.mean(sel)) if sel else None
    for o in oracles + ['pooled']:
        group = oracles if o == 'pooled' else [o]
        def level(b, a):
            vals = [mean_top10(x, b, a) for x in group]; return None if any(v is None for v in vals) else float(np.mean(vals))
        curve = [(b, level(b, 'random')) for b in budgets]
        if any(v is None for _, v in curve): print(f'  {o:12} Random is missing at a budget: no estimate'); continue
        curve = [(x, y) for (x, _), y in zip(curve, np.maximum.accumulate([v for _, v in curve]))]  # Random can only gain from more pairs: smooth sampling dips
        if curve[-1][1] <= curve[0][1]: print(f'  {o:12} Random does not rise with budget: no estimate'); continue
        for a in sorted(all_arms - {'random'}):
            for b in budgets:
                v = level(b, a)
                if v is None or b == budgets[-1]: continue
                lo, hi = curve[0][1], curve[-1][1]
                if v < lo or v > hi: print(f'  {o:12} {a:9} at {b} pairs: top-10% {v:.3f}, outside what Random reached ({lo:.3f} to {hi:.3f})'); continue
                eq = float(np.interp(v, [y for _, y in curve], [x for x, _ in curve])); print(f'  {o:12} {a:9} at {b} pairs: matches Random at {eq:.1f} pairs (saves {eq - b:+.1f})')
    print('\nMEANS (top10, regret, held-out acc) per arm, pooled over oracles')
    for b in budgets:
        for a in sorted(all_arms):
            sel = [v[a] for k, v in cell.items() if k[1] == b and a in v]
            if sel: print(f'  budget {b:3} {a:9} top10 {np.mean([x["top10"] for x in sel]):.3f}  regret {np.mean([x["regret"] for x in sel]):.2f}  acc {np.nanmean([x["acc"] for x in sel]):.3f}' + (f'  best-heard top10 {np.mean([x["heard10"] for x in sel]):.3f}' if all(x.get("heard10", -1) >= 0 for x in sel) else ''))


if __name__ == '__main__' and sys.argv[1:2] == ['report']:  # python -m tools.benchmark_blocks report [noise=logistic:0.5] a.csv b.csv ...
    args = sys.argv[2:]; noise = args.pop(0)[len('noise='):] if args and args[0].startswith('noise=') else 'logistic:0.5'; report(load_rows(args), noise)
elif __name__ == '__main__' and sys.argv[1:2] == ['summarize']:  # python -m tools.benchmark_blocks summarize a.csv b.csv ...: combine chunk files
    rows = []
    for f in sys.argv[2:]:
        for r in csv.DictReader(open(f)): rows.append({**r, 'profile': int(r['profile']), 'seed': int(r['seed']), 'budget': int(r['budget']), 'top10': int(r['top10']), 'regret': float(r['regret']), 'acc': float(r['acc'])})
    keys = [(r['oracle'], r['profile'], r['seed'], r['arm'], r['budget'], r['noise']) for r in rows]
    assert len(keys) == len(set(keys)), 'duplicate sessions in the chunk files'
    summary(rows)
elif __name__ == '__main__':
    e = os.environ.get; noise = e('NOISE', 'logistic:0.5').split(':') + ['0']; noise = (noise[0], float(noise[1]))
    jobs = [(f, p, s, a, b, noise) for f in e('ORACLES', ','.join(ORACLES)).split(',') for p in range(int(e('PROFILES', 5))) for s in range(int(e('SEED_START', 0)), int(e('SEED_START', 0)) + int(e('SEEDS', 2)))
            for b in map(int, e('BUDGETS', '12,17,30').split(',')) for a in e('ARMS', ','.join(CORE)).split(',')]
    truth(); print(len(_G['truth']), 'sounds in the ground-truth set;', len(jobs), 'sessions', flush=True)
    with Pool(int(e('WORKERS', os.cpu_count()))) as pool: rows = pool.map(run, jobs, chunksize=4)
    out = e('OUT', 'benchmark_blocks.csv')
    with open(out, 'w', newline='') as f: w = csv.DictWriter(f, rows[0]); w.writeheader(); w.writerows(rows)
    summary(rows); print('rows ->', out)
