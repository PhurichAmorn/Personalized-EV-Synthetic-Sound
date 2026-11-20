"""Loudness matching: one playback gain per pool sound and variation, so every sound starts equally loud (2026-11-19).
Each sound is rendered with the app's synth (as the quick check) and played at cruise (score.PITCHES), at the app's raw level
(rms .13 = 70 dB SPL, as score.py); its loudness is MoSQITo's Zwicker loudness (ISO 532-1, sones, mean after the first 0.5 s).
The gain brings it to the pool's median loudness (two passes: loudness is not linear in level), within +/- MAX_DB.
Stored as fx['gain'] (linear); the app multiplies its drive level by it. The guardrail is unaffected: its checks scale every
sound to 70 dB anyway.
ponytail: one reference point (cruise) and the quick-check render (full trend levels, no reverb or chorus); measure per drive
point if a sound is heard to swing in level against the others.
  WORKERS=14 python tools/sound_map/loudness.py [pool file, default experiment/sound_map_pool.json]"""
import json, os, subprocess, sys
for var in ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'VECLIB_MAXIMUM_THREADS'): os.environ[var] = '1'
from multiprocessing import Pool
import numpy as np
from mosqito.sq_metrics import loudness_zwtv
from score import prepare, play, FS, SPL, PITCHES

HERE = os.path.dirname(os.path.abspath(__file__))
POOL = os.path.abspath(sys.argv[1]) if len(sys.argv) > 1 else os.path.join(HERE, '..', '..', 'experiment', 'sound_map_pool.json')
WORKERS = int(os.environ.get('WORKERS', max(1, os.cpu_count() - 1)))
MAX_DB = 12  # never boost or cut a sound by more than this


def sones(x):
    n = loudness_zwtv(x, FS)[0]
    return float(np.mean(n[len(n) // 8:]))


def measure(job):
    """(path, fx) -> loudness in sones at the app's raw level, at cruise."""
    path, fx = job
    loop = np.fromfile(path, dtype=np.float32).astype(float); os.remove(path)
    if os.path.exists(path[:-4] + '.json'): os.remove(path[:-4] + '.json')
    rate, pedal = PITCHES['cruise']
    return play(loop, fx, rate, pedal, raw=True)  # the sound's own level, not scaled to 70 dB


def sones_at(x, g): return sones(x * g)


def gain_for(x, target):
    g = 1.
    for _ in range(2):  # sones double per +10 dB (above ~40 phon): correct, then refine once
        g *= 10 ** (10 * np.log2(target / max(sones(x * g), 1e-6)) / 20)
        g = float(np.clip(g, 10 ** (-MAX_DB / 20), 10 ** (MAX_DB / 20)))
    return g


if __name__ == '__main__':
    prepare(); os.makedirs('tmp', exist_ok=True)
    data = json.load(open(POOL))
    sounds = [s for s in data['sounds'] if s['voice']['kind'] == 'stack']
    items = [(s['id'], s) for s in sounds] + [(v['id'], v) for s in sounds for v in s.get('variations', [])]
    batches = [[{'id': i, 'voice': s['voice']} for i, s in items[n::WORKERS]] for n in range(WORKERS)]
    jobs = []
    for n, batch in enumerate(batches):
        if batch: json.dump(batch, open(f'lbatch{n}.json', 'w')); jobs.append(subprocess.Popen(['node', 'synth.mjs', f'lbatch{n}.json', 'tmp']))
    if any(job.wait() for job in jobs): raise RuntimeError('render failed')
    with Pool(WORKERS) as pool:
        signals = pool.map(measure, [(f'tmp/{i}.f32', s['fx']) for i, s in items])
        loud = pool.map(sones, signals)
        target = float(np.median(loud[:len(sounds)]))  # the pool sounds' median
        gains = pool.starmap(gain_for, [(x, target) for x in signals])
        after = pool.starmap(sones_at, zip(signals, gains))
    # Measured values beside the gain (2026-11-20), so a sound at the MAX_DB limit shows how far off it still is:
    # sones at the raw level, sones after the gain, and that gap to the target in dB (sones double per +10 dB).
    for (i, s), g, n0, n1 in zip(items, gains, loud, after):
        s['fx']['gain'] = round(g, 4)
        s['loudness'] = {'sones': round(n0, 3), 'after': round(n1, 3), 'off_db': round(10 * np.log2(n1 / target), 2)}
    data['loudness'] = {'target_sones': round(target, 3), 'reference': 'cruise', 'max_db': MAX_DB}
    json.dump(data, open(POOL, 'w'), indent=0)
    db = 20 * np.log10(gains)
    print(f'{len(items)} sounds: loudness {min(loud):.1f}-{max(loud):.1f} sones (median {target:.1f}); gains {db.min():+.1f} to {db.max():+.1f} dB, '
          f'{int(np.sum(np.abs(db) >= MAX_DB - .01))} at the {MAX_DB} dB limit -> {POOL}')
