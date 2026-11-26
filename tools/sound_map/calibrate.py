"""Calibrate the quick guardrail (steady points, about 1 s each) against the full-drive check (drive.py, about 12 s).
Samples sounds near and past the limits (mutations of library sounds plus random ones), measures every sound at steady points along
the simulated drive's path and on the full drive, then picks up to 3 points and per-metric quick limits that reject every sound
failing the drive while rejecting as few passing sounds as possible. Tuned on half the sounds, reported on the other half.
  python tools/sound_map/calibrate.py [sounds, default 600]   # writes out/calibration.json
"""
import itertools, json, os, shutil, subprocess, sys
for var in ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS'): os.environ[var] = '1'
from multiprocessing import Pool
import numpy as np
from mosqito.sq_metrics import sharpness_din_st, roughness_dw
from score import FS, play, fluctuation, crowding, prepare
from generate import LIMITS, WORKERS, random_genome, mutate, voice_of, fx_of, loop_partials, rng
from drive import measure, verdict, LIBRARY_FX, TMP

# (rate, pedal) on the simulated drive's path (simulatedDrive + drivingSoundTargets, Rising), plus the current two points.
POINTS = {'cruise': (.6, .4), 'peak': (1.06, 1.0), 'idle': (.53, 0), 'pullaway': (.69, .34), 'accel': (.8, .48), 'push': (.92, .72),
          'top': (.99, 1.0), 'ease': (.99, .5), 'liftoff': (.99, 0), 'coast': (.85, 0), 'slow': (.63, 0)}


def quick(job):
    path, fx = job
    loop = np.fromfile(path, dtype=np.float32).astype(float)
    partials = json.load(open(path[:-4] + '.json')) if os.path.exists(path[:-4] + '.json') else loop_partials(loop)
    out = {}
    for name, (rate, pedal) in POINTS.items():
        x = play(loop, fx, rate, pedal)
        out[name] = {'S': float(sharpness_din_st(x, FS)), 'R': float(np.mean(roughness_dw(x[:FS], FS)[0])), 'F': fluctuation(x),
                     'C': crowding(partials, fx, rate, pedal)}
    return out


def rule(points, limits, q):
    """Quick verdict: True = reject."""
    return q['C'] > LIMITS['C'] or any(max(q[p][k] for p in points) > limits[k] for k in 'SRF')


def tune(rows, points):
    """Per-metric quick limit: just under the lowest quick value of any sound failing the drive on that metric (never above LIMITS)."""
    limits = {}
    for k in 'SRF':
        fails = [max(r['quick'][p][k] for p in points) for r in rows if r['drive'][k] > LIMITS[k]]
        limits[k] = min([LIMITS[k]] + [v - 1e-3 for v in fails])
    return limits


def score(rows, points, limits):
    missed = sum(1 for r in rows if r['fail'] and not rule(points, limits, r['q']))
    wrong = sum(1 for r in rows if not r['fail'] and rule(points, limits, r['q']))
    return missed, wrong


if __name__ == '__main__':
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 600
    prepare(); os.makedirs(TMP, exist_ok=True); os.makedirs('cal', exist_ok=True)
    lib = [e['genome'] for e in json.load(open('library.json'))['sounds']]
    genomes = [mutate(lib[rng.integers(len(lib))]) if i % 2 else random_genome() for i in range(n)]
    batch = [{'id': str(i), 'voice': voice_of(g)} for i, g in enumerate(genomes)]
    jobs = []
    for w in range(WORKERS):
        json.dump(batch[w::WORKERS], open(f'cal/batch{w}.json', 'w'))
        jobs.append(subprocess.Popen(['node', 'synth.mjs', f'cal/batch{w}.json', 'cal']))
    if any(j.wait() for j in jobs): raise RuntimeError('render failed')
    with Pool(WORKERS) as pool:
        qs = pool.map(quick, [(f'cal/{i}.f32', fx_of(g)) for i, g in enumerate(genomes)])
        print('quick done', flush=True)
        ds = pool.map(measure, [(f'cal{i}', voice_of(g), {**fx_of(g), **LIBRARY_FX}, 'rise') for i, g in enumerate(genomes)])
    shutil.rmtree('cal', ignore_errors=True); rows = []
    for g, q, d in zip(genomes, qs, ds):
        q = {**q, 'C': max(v['C'] for v in q.values())}
        rows.append({'voice': g['voice'], 'quick': q, 'q': q, 'drive': d, 'fail': bool(verdict({'rise': d}))})
    json.dump({'points': POINTS, 'limits': LIMITS, 'rows': [{k: v for k, v in r.items() if k != 'q'} for r in rows]}, open('calibration.json', 'w'))

    tune_rows, test_rows = rows[::2], rows[1::2]
    ok = [r for r in rows if r['q']['C'] <= LIMITS['C']]
    print(f"{len(rows)} sounds; past crowding {len(rows) - len(ok)}; fail the drive {sum(r['fail'] for r in rows)} "
          f"(R {sum(r['drive']['R'] > LIMITS['R'] for r in rows)}, F {sum(r['drive']['F'] > LIMITS['F'] for r in rows)}, S {sum(r['drive']['S'] > LIMITS['S'] for r in rows)})")
    current = ('cruise', 'peak')
    print(f"current rule (cruise+peak, limits {LIMITS}): missed drive fails / wrongly rejected: all {score(rows, current, LIMITS)}")
    results = []
    for size in (2, 3):
        for pts in itertools.combinations(POINTS, size):
            lim = tune(tune_rows, pts)
            results.append((score(tune_rows, pts, lim)[1], pts, lim))
    for _, pts, lim in sorted(results, key=lambda t: (t[0], len(t[1])))[:10]:
        print(f"{'+'.join(pts):28} limits {', '.join(f'{k} {v:.3f}' for k, v in lim.items())}   tune {score(tune_rows, pts, lim)}   test {score(test_rows, pts, lim)}")
