"""MAP-Elites sound generator: fills a grid of kinds of sound (pitch x brightness x texture) with the safest sound per box.
Every candidate is rendered by the app's synth and checked by the guardrail (MoSQITo sharpness, roughness + fluctuation).
No training. Usage: python tools/sound_map/generate.py [rounds, default 40]. Writes out/library.json after every round."""
import json, os, shutil, subprocess, sys, time
for var in ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'VECLIB_MAXIMUM_THREADS'): os.environ[var] = '1'  # one thread per worker
from multiprocessing import Pool
import numpy as np
from mosqito.sq_metrics import sharpness_din_st, roughness_dw
from score import FS, PITCHES, play, fluctuation, prepare

LIMITS = {'S': 1.3, 'R': .3, 'F': .4}  # guardrail: reject above any (checked on the listener's labels)
# Gene: (low, high, log scale). Search space = the app's synth settings plus the engine effects the guardrail can hear.
GENES = {'rootHz': (80, 200, 1), 'brightness': (0, 1, 0), 'hollow': (0, 1, 0), 'bell': (0, 1, 0), 'softTop': (600, 6000, 1),
         'chord': (0, 1, 0), 'vowel': (0, 1, 0), 'vowelShape': (0, 1, 0), 'fundamental': (.3, 1, 0), 'whine': (0, 1, 0),
         'whineRatio': (3, 8, 0), 'detune': (0, 1, 0), 'air': (0, .4, 0),
         'tone': (800, 6000, 1), 'res': (.6, 8, 1), 'tremDepth': (0, .6, 0), 'tremRate': (.1, 2, 1), 'reverb': (0, .6, 0)}
CHOICES = {'chordType': list(range(8)), 'bellModes': [0, 1], 'pump': [0, 1], 'drift': [0, 1]}
FX_KEYS = {'tone', 'res', 'tremDepth', 'tremRate', 'reverb', 'pump', 'drift'}
PITCH_EDGES, BRIGHT_EDGES = [100, 140], [.45, .6, .75, .95]  # Hz; sharpness (acum)
TEXTURES = ['tone', 'chord', 'wide', 'bell', 'voice', 'whine']
rng = np.random.default_rng(1)
WORKERS = max(1, os.cpu_count() - 1)


def texture(g):
    """Main character, from the settings (first match wins)."""
    if g['whine'] > .4: return 'whine'
    if g['vowel'] > .5: return 'voice'
    if g['bellModes'] or g['bell'] > .5: return 'bell'
    if g['detune'] > .4: return 'wide'
    if g['chord'] > .4: return 'chord'
    return 'tone'


def to_unit(key, value):
    lo, hi, log = GENES[key]
    return (np.log(value / lo) / np.log(hi / lo)) if log else (value - lo) / (hi - lo)


def from_unit(key, u):
    lo, hi, log = GENES[key]; u = float(np.clip(u, 0, 1))
    return float(lo * (hi / lo) ** u if log else lo + (hi - lo) * u)


def random_genome():
    g = {k: from_unit(k, rng.random()) for k in GENES}
    g.update({k: int(rng.choice(v)) for k, v in CHOICES.items()}); return g


def mutate(g):
    child = dict(g)
    for k in rng.choice(list(GENES), size=rng.integers(2, 5), replace=False):
        child[k] = from_unit(k, to_unit(k, g[k]) + rng.normal(0, .12))
    for k, v in CHOICES.items():
        if rng.random() < .08: child[k] = int(rng.choice(v))
    return child


def crossover(a, b):
    return {k: (a if rng.random() < .5 else b).get(k, a.get(k)) for k in a.keys() | b.keys()}


def split(g):
    plain = {k: v for k, v in g.items() if k not in FX_KEYS}
    plain['width'] = 1
    fx = {k: g[k] for k in FX_KEYS if k in g}; fx['follow'] = 1
    if fx.get('drift'): fx['driftPeriod'] = 14
    return plain, fx


def check(job):
    """Guardrail measures, worst of cruising and peak pitch; margin > 0 means it passes."""
    path, fx = job
    loop = np.fromfile(path, dtype=np.float32).astype(float); os.remove(path)
    worst = {'S': 0, 'R': 0, 'F': 0}
    for rate, pedal in PITCHES.values():
        x = play(loop, fx, rate, pedal)
        m = {'S': float(sharpness_din_st(x, FS)), 'R': float(np.mean(roughness_dw(x[:FS], FS)[0])), 'F': fluctuation(x)}
        worst = {k: max(worst[k], m[k]) for k in m}
    return worst


def cell(g, m):
    return f"{int(np.digitize(g['rootHz'], PITCH_EDGES))}-{int(np.digitize(m['S'], BRIGHT_EDGES))}-{texture(g)}"


def evaluate(genomes, pool, tmp='tmp'):
    batch = [{'id': str(i), 'plain': split(g)[0]} for i, g in enumerate(genomes)]
    jobs = []
    for n in range(WORKERS):  # render in parallel too (about 0.2 s per sound in one process)
        json.dump(batch[n::WORKERS], open(f'batch{n}.json', 'w'))
        jobs.append(subprocess.Popen(['node', 'synth.mjs', f'batch{n}.json', tmp]))
    if any(job.wait() for job in jobs): raise RuntimeError('render failed')
    return pool.map(check, [(f'{tmp}/{i}.f32', split(g)[1]) for i, g in enumerate(genomes)])


def seeds():
    """The listener's kept sounds start the grid (clipped into the search range)."""
    out = []
    for item in json.load(open('manifest.json')):
        if item['label'] != 'ok': continue
        g = {k: float(np.clip({**item['plain'], **item['fx']}.get(k, GENES[k][0]), GENES[k][0], GENES[k][1])) for k in GENES}
        g.update({k: int(round({**item['plain'], **item['fx']}.get(k, 0))) for k in CHOICES})
        g['seed'] = item['name']; out.append(g)
    return out


if __name__ == '__main__':
    prepare()
    generations, size = int(sys.argv[1]) if len(sys.argv) > 1 else 40, 140
    elites, log, tried, passed = {}, [], 0, 0
    with Pool(WORKERS) as pool:
        for gen in range(generations + 1):
            start = time.time()
            if gen == 0:
                genomes = seeds() + [random_genome() for _ in range(size)]
            else:
                pick = lambda: elites[list(elites)[rng.integers(len(elites))]]['genome']
                genomes = [mutate(crossover(pick(), pick()) if rng.random() < .25 else pick()) for _ in range(size)]
            for g, m in zip(genomes, evaluate([{k: v for k, v in g.items() if k != 'seed'} for g in genomes], pool)):
                tried += 1
                margin = min(1 - m[k] / LIMITS[k] for k in LIMITS)
                if margin <= 0: continue
                passed += 1
                c = cell(g, m)
                if c not in elites or margin > elites[c]['margin']:
                    elites[c] = {'cell': c, 'genome': g, 'metrics': m, 'margin': margin, 'gen': gen, 'from': g.get('seed')}
            log.append({'gen': gen, 'tried': tried, 'passed': passed, 'filled': len(elites), 'seconds': round(time.time() - start, 1)})
            print(log[-1], flush=True)
            json.dump({'limits': LIMITS, 'textures': TEXTURES, 'pitchEdges': PITCH_EDGES, 'brightEdges': BRIGHT_EDGES,
                       'log': log, 'elites': sorted(elites.values(), key=lambda e: e['cell'])}, open('library.json', 'w'), indent=1)
    shutil.rmtree('tmp', ignore_errors=True)
