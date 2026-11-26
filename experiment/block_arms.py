"""Experimental pair-selection variants of the building-block session (2026-11-23), for listener tests in the app and for the simulated benchmark
(tools/benchmark_blocks.py, docs/research/benchmark_blocks_plan.md). All four are BlockDiscovery with one change: how pairs 5-13 are chosen. Starts,
playoff, replay, fine-tune pairs, the Bradley-Terry shortlist and the export are the same code, so a session differs from "Building blocks" only there.
  random : champion vs challenger, challengers in random order (the control: the tournament with no model)
  robust : champion vs challenger, champion = Bradley-Terry best of everything heard (not the last winner)
  pbo    : champion vs challenger, challengers ordered by EUBO under a GP preference model (kernel over the blocks)
  infogain: champion vs challenger, challengers ordered by EUBO under the app's own linear model (200 posterior draws)
  duel   : no champion; both sounds picked by two posterior draws of the same GP (Thompson duel)
Not benchmarked yet when added: treat as experimental."""
import numpy as np
from scipy.stats import norm
from experiment import sound_blocks as sb
from experiment.source_search import BLOCK_OPENING, BlockDiscovery, block_features

CATS = ('body', 'top', 'partner', 'level', 'buzz', 'chord', 'bell', 'vowel')
_VOC = {}
LC, LP, LB = 3., 2., .3  # kernel length scales: categorical differences, pitch steps, brightness (acum). Fixed guesses, not tuned on any result.
BRIGHTNESS_GRID = (.25, .4, .55, .7, .85)


def enc(blocks):
    cat = np.array([[_VOC.setdefault((k, str(b.get(k))), len(_VOC)) for k in CATS] for b in blocks])
    return cat, np.array([[b['pitch'], b['brightness']] for b in blocks], float)


def kern(A, B):
    d = (A[0][:, None, :] != B[0][None, :, :]).sum(-1); dp = (A[1][:, None, 0] - B[1][None, :, 0]) / LP; db = (A[1][:, None, 1] - B[1][None, :, 1]) / LB
    return np.exp(-d / LC - .5 * (dp ** 2 + db ** 2))


class GP:
    """Bradley-Terry preference model with a GP prior over sounds (Chu & Ghahramani style), Laplace approximation on the sounds heard.
    P(w beats l) = sigmoid(f_w - f_l); only decisive A/B answers are used (Both good and Neither carry no comparison here)."""
    def __init__(self, blocks, pairs):
        self.U = enc(blocks); n = self.n = len(blocks)
        if not n: return
        K = kern(self.U, self.U) + 1e-4 * np.eye(n); self.Kinv = np.linalg.inv(K); f = np.zeros(n)
        for _ in range(30):
            d = f[[w for w, _ in pairs]] - f[[l for _, l in pairs]]; p = 1 / (1 + np.exp(-d)); g = -self.Kinv @ f; W = np.zeros((n, n))
            for (w, l), pp in zip(pairs, p):
                g[w] += 1 - pp; g[l] -= 1 - pp; q = pp * (1 - pp); W[w, w] += q; W[l, l] += q; W[w, l] -= q; W[l, w] -= q
            step = np.linalg.solve(self.Kinv + W, g); f += step
            if np.abs(step).max() < 1e-6: break
        self.f = f; self.Sigma = np.linalg.inv(self.Kinv + W)
    def predict(self, C, cov=True):
        Kcc = kern(C, C) if cov else None
        if not self.n: return np.zeros(len(C[0])), Kcc
        Ks = kern(C, self.U); A = Ks @ self.Kinv
        return A @ self.f, ((Kcc - A @ Ks.T + A @ self.Sigma @ A.T) if cov else None)


class RandomMixin:
    def _order_broad(self, out, here): out = list(out); self.rng.shuffle(out); return out


class InfoGainMixin:
    """EUBO-style: expected best of the pair, E[max(u(candidate), u(champion))], over DRAWS posterior draws of the taste."""
    DRAWS = 200
    def _order_broad(self, out, here):
        mean, cov = self._posterior(); W = np.random.default_rng(self.rng.randrange(2 ** 32)).multivariate_normal(mean, cov, self.DRAWS, method='cholesky')
        uh = W @ block_features(here)
        return sorted(out, key=lambda m: -np.maximum(W @ self._features(m[0]), uh).mean())


class RobustMixin:
    winner_stays = False
    def _proposals(self):
        if BLOCK_OPENING + 1 <= self.completed - self.motion_pairs <= BLOCK_OPENING + self.adaptive and self._bt_ranked():
            rows = self._choices(); self.champion = None if rows and rows[-1]['choice'] == 'neither' else self._bt_ranked()[0]  # after Neither the app picks a champion outside the rejected pair
        return super()._proposals()


class GPMixin:
    def _gp(self):
        rows = [r for r in self._ranking_rows() if r['winner'] and len(set(r['pair'])) == 2]; ids = list(dict.fromkeys(i for r in rows for i in r['pair'])); ix = {i: k for k, i in enumerate(ids)}
        return GP([self._sound(i) for i in ids], [(ix[r['winner']], ix[next(i for i in r['pair'] if i != r['winner'])]) for r in rows])


class PBOMixin(GPMixin):
    def _order_broad(self, out, here):
        C = enc([m[0]['blocks'] for m in out] + [here]); mu, cov = self._gp().predict(C); h = len(out)
        m = mu[:h] - mu[h]; s = np.sqrt(np.maximum(np.diag(cov)[:h] + cov[h, h] - 2 * cov[:h, h], 1e-9))
        return [out[i] for i in np.argsort(-(mu[h] + m * norm.cdf(m / s) + s * norm.pdf(m / s)))]  # EUBO = E[max(f_challenger, f_champion)]


class FreeMixin(GPMixin):
    """No champion in the adaptive pairs: the pair comes from 400 random table-passing sounds plus the sounds heard; _pick says how."""
    def _random_sounds(self, n):
        out, rng = [], self.rng
        for _ in range(n * 30):
            top = rng.choice(list(sb.TOPS)); s = {'body': rng.choice(list(sb.BODIES)), 'top': top, 'level': rng.choice(list(sb.TOP_LEVELS)), 'pitch': rng.randrange(len(sb.PITCHES)),
                                                  'brightness': rng.choice(BRIGHTNESS_GRID), 'partner': rng.choice((None, *sb.PARTNERS.get(top, ())))}
            if top in ('synth', 'bell'): s.update(buzz=rng.choice((0, 2)), chord=rng.choice(('off', 'on')), bell=rng.random() < .5, vowel=rng.random() < .5)
            r = self._recipe(s)
            if r: out.append(r)
            if len(out) == n: break
        return out
    def _proposals(self):
        step = self.completed - self.motion_pairs
        if not (self.completed >= self.motion_pairs and BLOCK_OPENING + 1 <= step <= BLOCK_OPENING + self.adaptive): return super()._proposals()
        self.check_parent = None; cand = self._random_sounds(400) + [self.candidates[i]['recipe'] for i in {i for r in self._choices() for i in r['pair']}]
        a, b = self._pick(cand)
        self.rematch = [self._add(a, {'kind': 'duel', 'summary': 'free pair'}), self._add(b, {'kind': 'duel', 'summary': 'free pair'})]
        return []
    def _clear(self, a, b): return a['blocks']['top'] != b['blocks']['top'] or self._gap(a, b) >= sb.MIN_GAP  # the app's rule: close pairs are not offered


class DuelMixin:
    """Thompson duel: two posterior draws, each one's best sound is one side of the pair (the second must be clearly different from the first)."""
    def _pick(self, cand):
        mu, cov = self._gp().predict(enc([c['blocks'] for c in cand])); L = np.linalg.cholesky(cov + 1e-6 * np.eye(len(cand))); g = np.random.default_rng(self.rng.randrange(2 ** 32))
        f1 = mu + L @ g.standard_normal(len(cand)); f2 = mu + L @ g.standard_normal(len(cand)); a = int(np.argmax(f1))
        return cand[a], cand[next(int(k) for k in np.argsort(-f2) if k != a and self._clear(cand[a], cand[k]))]


# The sessions the app offers (backend/bridge.py, Search selector).
class RandomBlocks(RandomMixin, BlockDiscovery): policy = 'source-blocks-v1-random'
class InfoGainBlocks(InfoGainMixin, BlockDiscovery): policy = 'source-blocks-v1-infogain'
class RobustBlocks(RobustMixin, BlockDiscovery): policy = 'source-blocks-v1-robust'
class PBOBlocks(PBOMixin, BlockDiscovery): policy = 'source-blocks-v1-pbo'
class DuelBlocks(DuelMixin, FreeMixin, BlockDiscovery): policy = 'source-blocks-v1-duel'
