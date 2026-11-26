"""Loudness pass for the building-block safe-area table (2026-11-22): block sounds are built on the spot, so unlike pool sounds
(loudness.py) they had no loudness matching, and the starts played 6-12 sones apart (Moody quietest, Glass loudest). For every table entry
at every low-pass point: render through the app's driving chain (drive.mjs, Rising, the entry's default large space), take 9-14 s of the
drive (cruise, as the brightness measure), and store its Zwicker loudness (ISO 532-1, MoSQITo, sones, mean after the first 0.5 s) at the
app's raw level (rms .13 = 70 dB SPL, as score.py and loudness.py) in entry['sones']. The session turns it into a playback gain
(sound_blocks.gain_for). Only entries without 'sones' are measured, so it can run after each sweep.
ponytail: one space (large) and one drive point (cruise); measure dry and other points if those are heard to differ in level.
  WORKERS=14 python tools/sound_map/block_loudness.py"""
import json, os, subprocess, sys
for var in ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'VECLIB_MAXIMUM_THREADS'): os.environ[var] = '1'
from multiprocessing import Pool
import numpy as np
from scipy.signal import fftconvolve
from mosqito.sq_metrics import loudness_zwtv
from drive import convolver, TMP
from score import prepare, HERE, FS, SPL
sys.path.insert(0, os.path.join(HERE, '..', '..', 'experiment'))
import sound_blocks as sb


def sones(job):
    """(id, voice, fx) -> mean Zwicker loudness (sones) over 9-14 s of the Rising drive, at the app's raw level."""
    key, voice, fx = job
    batch = f'{TMP}/{key}.json'; json.dump([{'id': key, 'voice': voice, 'fx': fx, 'modes': ['rise']}], open(batch, 'w'))
    subprocess.run(['node', 'drive.mjs', batch, TMP], check=True)
    base = f'{TMP}/{key}.rise'
    x = np.fromfile(base + '.f32', np.float32).astype(float).reshape(2, -1)
    for p in (batch, base + '.f32', base + '.gain.json'): os.remove(p)
    ir = convolver(np.fromfile(f"{TMP}/room-{fx['size']}.f32", np.float32).astype(float).reshape(2, -1)); rv = fx['reverb']
    y = ((1 - rv * .5) * x + rv * np.array([fftconvolve(x[c], ir[c])[:x.shape[1]] for c in (0, 1)])).mean(0)[9 * FS:14 * FS]
    n = loudness_zwtv(y / .13 * 20e-6 * 10 ** (SPL / 20), FS)[0]
    return float(np.mean(n[len(n) // 10:]))


if __name__ == '__main__':
    table = sb.load_table()
    if not table: sys.exit(f'no table at {sb.TABLE}: run block_sweep.py first')
    prepare(); os.makedirs(TMP, exist_ok=True)
    todo = [k for k, e in table['entries'].items() if 'sones' not in e]
    jobs = [(f'l{n}c{j}', *sb.build(table['entries'][k]['sound'], c)) for n, k in enumerate(todo) for j, c in enumerate(sb.CUTOFFS)]
    print(f'{len(todo)} entries x {len(sb.CUTOFFS)} low-pass points = {len(jobs)} renders', flush=True)
    with Pool(int(os.environ.get('WORKERS', max(1, os.cpu_count() - 1)))) as pool:
        out = []
        for i, v in enumerate(pool.imap(sones, jobs, chunksize=4)):
            out.append(v)
            if (i + 1) % 200 == 0: print(f'{i + 1}/{len(jobs)}', flush=True)
    for n, k in enumerate(todo): table['entries'][k]['sones'] = [round(v, 3) for v in out[n * len(sb.CUTOFFS):(n + 1) * len(sb.CUTOFFS)]]
    allv = [v for e in table['entries'].values() for v in e.get('sones', [])]
    table['loudness'] = {'target_sones': round(float(np.median(allv)), 3), 'reference': 'mean Zwicker loudness, 9-14 s of the Rising drive, large space',
                         'max_db': sb.MAX_GAIN_DB, 'source': 'tools/sound_map/block_loudness.py'}
    json.dump(table, open(sb.TABLE, 'w'), indent=0)
    print(f"{len(todo)} entries measured; loudness {min(allv):.1f}-{max(allv):.1f} sones, target (median) {table['loudness']['target_sones']:.1f}")
