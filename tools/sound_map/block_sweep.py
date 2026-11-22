"""Safe-area sweep for building-block sounds (experiment/sound_blocks.py, 2026-11-21): every combination the session can offer is played
through the full-drive check (drive.py: the app's driving chain, Rising and Evolving) at each measured low-pass point. Writes
experiment/sound_blocks_table.json: per combination, the cruise sharpness at each point (so a brightness step is a measured 0.10 acum),
its octave-band spectrum (so a change the ear would not hear is never offered)
and whether each point passes the guardrail (Rising decides, as for pool sounds; Evolving recorded for Evolving sessions).
Heavy (about 4000 renders): run on the cooled laptop. With a table already there, only combinations missing from it are measured and
merged in (a new top texture adds its own rows; delete the table to measure everything again).
  LIMIT_F=0.2 WORKERS=14 python tools/sound_map/block_sweep.py"""
import json, os, sys, time
for var in ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'VECLIB_MAXIMUM_THREADS'): os.environ[var] = '1'
from multiprocessing import Pool
from drive import measure, MODES, DRIVE_LIMITS, TMP
from score import prepare, HERE
sys.path.insert(0, os.path.join(HERE, '..', '..', 'experiment'))
import sound_blocks as sb

if __name__ == '__main__':
    prepare(); os.makedirs(TMP, exist_ok=True)
    old = sb.load_table(); items = [(k, s) for k, s in sb.sweep_items() if not old or k not in old['entries']]
    jobs = [(f'b{n}c{j}', *sb.build(sound, c), mode) for n, (_, sound) in enumerate(items) for j, c in enumerate(sb.CUTOFFS) for mode in MODES]
    print(f'{len(items)} combinations x {len(sb.CUTOFFS)} low-pass points x {len(MODES)} modes = {len(jobs)} drive checks', flush=True)
    results, t = {}, time.time()
    with Pool(int(os.environ.get('WORKERS', max(1, os.cpu_count() - 1)))) as pool:
        for i, m in enumerate(pool.imap(measure, jobs, chunksize=4)):
            results[(jobs[i][0], jobs[i][3])] = m
            if (i + 1) % 200 == 0: print(f'{i + 1}/{len(jobs)} in {(time.time() - t) / 60:.0f} min', flush=True)
    entries, failed = dict(old['entries']) if old else {}, 0
    for n, (k, sound) in enumerate(items):
        per = [{mode: results[(f'b{n}c{j}', mode)] for mode in MODES} for j in range(len(sb.CUTOFFS))]
        ok = [{mode: all(p[mode][x] <= DRIVE_LIMITS[x] for x in 'SRF') for mode in MODES} for p in per]
        failed += sum(not o['rise'] for o in ok)
        entries[k] = {'sound': sound, 'S': [round(p['rise']['cruise'], 3) for p in per], 'pass': ok, 'bands': [p['rise']['bands'] for p in per],
                      'worst': [{mode: {x: round(p[mode][x], 3) for x in 'SRF'} for mode in MODES} for p in per]}
    out = {'created': (old or {}).get('created', time.strftime('%Y-%m-%d')), 'updated': time.strftime('%Y-%m-%d'), 'source': 'tools/sound_map/block_sweep.py', 'cutoffs': sb.CUTOFFS, 'pitches': sb.PITCHES,
           'limits': DRIVE_LIMITS, 'entries': entries}
    json.dump(out, open(sb.TABLE, 'w'), indent=0)
    print(f'{len(items)} new, {len(entries)} combinations -> {sb.TABLE}; {failed} of {len(items) * len(sb.CUTOFFS)} new points fail in Rising')
