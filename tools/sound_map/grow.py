"""Phase 2 prototype: the sound-map session grows new sounds between pairs, and a simulated-listener test of whether that helps.

GrowingMapDiscovery = SoundMapDiscovery (same opening, answers, model, winner stays, confirmation) plus guided growing: from the first
challenger pair on, CANDIDATES variations of the current favourite and the runner-up are rendered with the app's synth and scored by the
listener model (Thompson sample) on cheap traits (pitch, spectrum, inharmonicity, chorus, vibrato, voice; sharpness, roughness and pulsing
taken from the parent). Only the CHECKED best go through the quick guardrail (tuned limits, calibrate.py); the passing ones join the
session's pool, and the model picks the challenger from pool and new sounds alike. Variation size shrinks over the session.

Test: each simulated listener's hidden favourite is a passing sound OUTSIDE the pool (far from every pool sound), with random weights on
the 9 traits; answers are noisy as in tools/benchmark_sound_map.py. Same listeners, pool-only vs growing.
  python tools/sound_map/grow.py [listeners, default 60]
"""
import json, math, os, random, shutil, subprocess, sys
for var in ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS'): os.environ[var] = '1'
from multiprocessing import Pool
import numpy as np
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..'))
import generate
from generate import (PLAIN_GENES, PLAIN_CHOICES, BLOCK_GENES, FX_GENES, FX_CHOICES, random_genome, mutate, crossover, voice_of, fx_of,
                      root_hz, check, gap, describe)
from score import prepare
from drive import LIBRARY_FX
from experiment.source_search import SoundMapDiscovery, map_unit, map_recipe, MAP_OPENING, STYLE_PAIRS

QUICK = {'S': 1.3, 'R': .263, 'F': .302, 'C': 70}  # quick-check limits tuned to the full drive (calibrate.py, 2026-11-17)
CANDIDATES = 30                                    # variations rendered and scored by the model per pair (cheap)
CHECKED = 4                                        # best-scoring ones that get the quick guardrail (about 2 s each)
SIGMA = (.25, .06)                                 # variation size at the first and last growing pair
NEAR = .5                                          # a new sound must be at least this many 'distinct' steps from every heard sound
NOISE = float(os.environ.get('NOISE', .15))           # simulated listener: utility gap at which the better sound wins 73% of the time


def genome_of(sound):
    """Pool sound (voice + fx) -> generator genome; genes the voice does not use are random (only used if the voice flips)."""
    v, g = sound['voice'], random_genome(sound['voice']['kind'])
    keys = list(FX_GENES) + list(FX_CHOICES)
    g.update({k: sound['fx'][k] for k in keys if k in sound['fx']})
    if v['kind'] == 'plain': g.update({k: v['plain'][k] for k in list(PLAIN_GENES) + list(PLAIN_CHOICES) if k in v['plain']})
    else: g.update({k: v['shape'][k] for k in BLOCK_GENES if k in v['shape']}); g['ensemble'] = v['controls']['ensemble']
    return g


def render(genomes, tmp):
    os.makedirs(tmp, exist_ok=True)
    json.dump([{'id': str(i), 'voice': voice_of(g)} for i, g in enumerate(genomes)], open(f'{tmp}/batch.json', 'w'))
    subprocess.run(['node', 'synth.mjs', f'{tmp}/batch.json', tmp], check=True, stdout=subprocess.DEVNULL)


def make_sounds(genomes, tmp, rendered=None):
    """Quick-check genomes (rendered: their indices in the last render, else render now); returns pool-format sounds that pass
    (drive metrics = quick metrics)."""
    if rendered is None: render(genomes, tmp); rendered = range(len(genomes))
    out = []
    for i, g in zip(rendered, genomes):
        m, d = check((f'{tmp}/{i}.f32', fx_of(g), root_hz(g)))
        if any(m[k] > QUICK[k] for k in QUICK): continue
        s = {'id': f'g{abs(hash(json.dumps(g, sort_keys=True))) % 10**10:010d}', 'voice': voice_of(g), 'fx': {**fx_of(g), **LIBRARY_FX},
             'rootHz': root_hz(g), 'metrics': m, 'desc': {**d, 'R': m['R'], 'F': m['F'], 'chorus': g['chorus'], 'vib': g['vibDepth']},
             'drive': {k: m[k] for k in 'SRF'}, 'genome': g, 'from': 'grown'}
        out.append({**s, 'unit': map_unit(s)})
    return out


class GrowingMapDiscovery(SoundMapDiscovery):
    policy = 'source-map-grow-1'
    tmp = 'grow-tmp'

    def _proposals(self):
        step, rows = self.completed, self._choices()
        if MAP_OPENING + 2 <= step < STYLE_PAIRS - 1 and rows:
            ranked, last = self._ranked(), rows[-1]
            favourite = last['winner'] if last.get('winner') else (self.champion or ranked[0])
            parents = [self.by_cell[self.candidates[i]['recipe']['cell']] for i in [favourite] + [i for i in ranked if i != favourite][:1]]
            genomes = [p.get('genome') or genome_of(p) for p in parents]
            t = (step - MAP_OPENING - 2) / max(1, STYLE_PAIRS - MAP_OPENING - 4); sigma = SIGMA[0] + (SIGMA[1] - SIGMA[0]) * t
            kids = [mutate(genomes[0], sigma) for _ in range(CANDIDATES * 2 // 3)] + \
                   [mutate(crossover(*genomes) if len(genomes) > 1 else genomes[0], sigma) for _ in range(CANDIDATES - CANDIDATES * 2 // 3)]
            heard = [self.by_cell[self.candidates[i]['recipe']['cell']] for r in rows for i in r['pair']]
            render(kids, self.tmp); self._sample(); score = []
            for i, g in enumerate(kids):  # cheap traits; sharpness, roughness, pulsing as the parent
                d = describe(np.fromfile(f'{self.tmp}/{i}.f32', np.float32).astype(float), fx_of(g), root_hz(g))
                est = {'voice': voice_of(g), 'fx': fx_of(g), 'rootHz': root_hz(g), 'drive': parents[0]['drive'],
                       'desc': {**d, 'R': parents[0]['desc']['R'], 'F': parents[0]['desc']['F'], 'chorus': g['chorus'], 'vib': g['vibDepth']}}
                if any(gap(est['desc'], h['desc']) < NEAR for h in heard): continue
                z = 2 * map_unit(est) - 1; score.append((float(np.ravel(np.column_stack([z, z * z])) @ self._w_sample), i))
            best = [i for _, i in sorted(score, reverse=True)[:CHECKED]]
            for s in make_sounds([kids[i] for i in best], self.tmp, best):
                if s['id'] not in self.by_cell and all(gap(s['desc'], h['desc']) >= NEAR for h in heard):
                    self.pool.append(s); self.by_cell[s['id']] = s
        return super()._proposals()


def ideal_bank(n=400):
    """Passing sounds outside the pool, far from every pool sound: hidden favourites for the test (cached in out/ideal_bank.json)."""
    if os.path.exists('ideal_bank.json'): return json.load(open('ideal_bank.json'))
    pool = SoundMapDiscovery(renderer=lambda r: None); pool._load()
    seeds = [genome_of(s) for s in pool.pool]
    genomes = [random_genome() if i % 2 else mutate(seeds[i % len(seeds)], .3) for i in range(n)]
    with Pool(max(1, os.cpu_count() - 1)) as workers:
        found = sum(workers.map(_bank_part, [(genomes[i::32], f'bank-tmp/{i}') for i in range(32)]), [])
    units = np.array([s['unit'] for s in pool.pool])
    far = [s for s in found if np.min(np.linalg.norm(units - s['unit'], axis=1)) > .35]
    bank = [{k: (v.tolist() if isinstance(v, np.ndarray) else v) for k, v in s.items()} for s in far]
    json.dump(bank, open('ideal_bank.json', 'w')); shutil.rmtree('bank-tmp', ignore_errors=True)
    print(f'ideal bank: {len(found)} of {n} passed, {len(bank)} far from the pool', flush=True)
    return bank


def _bank_part(job):
    genomes, tmp = job; generate.rng = np.random.default_rng(abs(hash(tmp)) % 2**32)
    return make_sounds(genomes, tmp)


def session(job):
    seed, policy, bank = job
    rng = np.random.default_rng(seed); generate.rng = np.random.default_rng(seed + 10**6)
    d = (GrowingMapDiscovery if policy == 'grow' else SoundMapDiscovery)(renderer=lambda r: None)
    d.tmp = f'grow-tmp/{seed}'; d.start(); d.rng = random.Random(seed)
    ideal = np.array(bank[seed % len(bank)]['unit']); weight = rng.dirichlet(np.ones(len(ideal)) * .5)
    utility = lambda u: -float(np.sqrt(weight @ (np.asarray(u) - ideal) ** 2))
    pool_u = [utility(s['unit']) for s in d.pool]; median, best_pool = float(np.median(pool_u)), max(pool_u)
    for _ in range(STYLE_PAIRS):
        if len(d.pair) != 2: break
        ua, ub = (utility(d._unit(d.candidates[i]['recipe'])) for i in d.pair)
        if min(ua, ub) > median + .1: choice = 'good'
        elif max(ua, ub) < median - .1: choice = 'neither'
        else: choice = 'A' if rng.random() < 1 / (1 + math.exp(-(ua - ub) / NOISE)) else 'B'
        d.feedback(choice=choice)
    shown = [utility(d._unit(d.candidates[i]['recipe'])) for i in d.finalists[:3]]  # the listener picks from the podium (top 3), noisily
    p = np.exp(np.array(shown) / NOISE); final = shown[int(rng.choice(len(shown), p=p / p.sum()))]
    heard = {i for r in d._choices() for i in r['pair']}
    best_heard = max(utility(d._unit(d.candidates[i]['recipe'])) for i in heard)
    grown = sum(1 for i in heard if d.by_cell[d.candidates[i]['recipe']['cell']].get('from') == 'grown')
    d.close(); shutil.rmtree(d.tmp, ignore_errors=True)
    return final, best_pool, grown, best_heard


if __name__ == '__main__':
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 60
    prepare(); bank = ideal_bank()
    with Pool(max(1, os.cpu_count() - 1)) as workers:
        for policy in ('pool', 'grow'):
            res = np.array(workers.map(session, [(s, policy, bank) for s in range(n)]))
            final, best, grown, heard = res[:, 0], res[:, 1], res[:, 2], res[:, 3]
            beat = np.mean(final > best)
            print(f"{policy:5} listeners {n}: final closer to the hidden favourite than the best pool sound in {beat:.0%} of sessions "
                  f"(+-{2 * np.sqrt(beat * (1 - beat) / n):.0%}); distance to favourite median {np.median(-final):.3f} "
                  f"(best heard {np.median(-heard):.3f}, best pool sound {np.median(-best):.3f}); new sounds heard per session {np.mean(grown):.1f}", flush=True)
