"""Full-drive guardrail check: render a sound through the app's driving chain (drive.ts: granular player + labEngine nodes)
over the 22 s simulated drive, in Rising and Evolving mode, and apply the same guardrail limits to the worst moment.
Level is held fixed (drive gain 1, scaled to 70 dB like score.py) so only the sound's character is judged;
the drive gain is used to skip moments where the sound is nearly silent.

  python tools/sound_map/drive.py labelled   # self-check: must reject Growl and Sci-fi sweep and pass every kept sound
  python tools/sound_map/drive.py library    # re-check every box winner; a failure is replaced by its box's next-best passing runner-up
"""
import json, os, subprocess, sys
for var in ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS'): os.environ[var] = '1'
from multiprocessing import Pool
import numpy as np
from scipy.signal import fftconvolve
from mosqito.sq_metrics import sharpness_din_tv, roughness_dw
from score import FS, SPL, HERE, fluctuation, prepare
from generate import LIMITS, split

MODES = ('rise', 'evolving')
GATE = ('rise',)     # modes that decide pass/fail. Evolving is recorded only: it rejects the kept Pure tone (pulsing 0.46, two crossfaded voices)
STEP = FS // 20      # drive control step (50 ms)
AUDIBLE = .3         # drive gain (after the envelope's square root) above which a moment counts
WINDOW = 1.0         # seconds: sharpness and roughness are averaged over this before taking the worst moment
TMP = 'drive-tmp'
POOL = os.path.join(HERE, '..', '..', 'experiment', 'sound_map_pool.json')
LIBRARY_FX = {'size': 2.5, 'follow': 1}  # as the listening page plays library sounds; the rest is levels.SEARCH_FIXED


def convolver(ir):
    """WebAudio ConvolverNode normalisation (spec: calculateNormalizationScale) for a stereo impulse."""
    power = max(np.sqrt(np.sum(ir ** 2) / ir.size), .000125)
    return ir * (.00125 / power * 44100 / FS * .5)


def worst(values, times):
    """Highest WINDOW-long mean and when it happens."""
    w = max(1, int(round(WINDOW / (times[1] - times[0]))))
    mean = np.convolve(values, np.ones(w) / w, 'valid') if len(values) >= w else np.array([values.mean()])
    i = int(np.argmax(mean)); return float(mean[i]), float(times[min(i + w // 2, len(times) - 1)])


def measure(job):
    """job = (id, plain, fx, mode). Returns worst S, R, F over the audible part of the drive, with their times (s)."""
    key, plain, fx, mode = job
    batch = f'{TMP}/{key}.{mode}.json'
    json.dump([{'id': key, 'plain': plain, 'fx': fx, 'modes': [mode]}], open(batch, 'w'))
    subprocess.run(['node', 'drive.mjs', batch, TMP], check=True)
    base = f'{TMP}/{key}.{mode}'
    x = np.fromfile(base + '.f32', np.float32).astype(float).reshape(2, -1)
    gains = np.array(json.load(open(base + '.gain.json')))
    for p in (batch, base + '.f32', base + '.gain.json'): os.remove(p)
    size, reverb = fx.get('size', 2), fx.get('reverb', 0)
    ir = convolver(np.fromfile(f'{TMP}/room-{size}.f32', np.float32).astype(float).reshape(2, -1))
    y = (1 - reverb * .5) * x + reverb * np.array([fftconvolve(x[c], ir[c])[:x.shape[1]] for c in (0, 1)])
    audible = np.flatnonzero(gains >= AUDIBLE)
    start, end = audible[0] * STEP, (audible[-1] + 1) * STEP
    seg = y.mean(0)[start:end]
    seg = seg / np.sqrt(np.mean(seg ** 2)) * 20e-6 * 10 ** (SPL / 20)
    t0 = start / FS
    S, tS = sharpness_din_tv(seg, FS)
    keep = tS > .5  # skip the loudness model's start-up
    s, s_at = worst(np.asarray(S)[keep], np.asarray(tS)[keep])
    R, _, _, tR = roughness_dw(seg, FS)
    r, r_at = worst(np.asarray(R), np.asarray(tR))
    f, f_at = max((fluctuation(seg[i:i + 3 * FS]), i / FS + 1.5) for i in range(0, max(1, len(seg) - 3 * FS + 1), FS))
    return {'S': s, 'R': r, 'F': f, 'at': {'S': t0 + s_at, 'R': t0 + r_at, 'F': t0 + f_at}}


def verdict(per_mode, modes=GATE):
    """Failing (metric, mode) pairs in the given modes; empty means pass."""
    return [f'{k} {m[k]:.2f} > {LIMITS[k]} ({mode}, {m["at"][k]:.0f} s)' for mode, m in per_mode.items() if mode in modes for k in LIMITS if k in m and m[k] > LIMITS[k]]  # C is a settings measure: same on the drive


def check_all(sounds, pool):
    """sounds: {id: (plain, fx)} -> {id: {mode: metrics}}"""
    jobs = [(i, plain, fx, mode) for i, (plain, fx) in sounds.items() for mode in MODES]
    out = {}
    for (i, _, _, mode), m in zip(jobs, pool.map(measure, jobs)): out.setdefault(i, {})[mode] = m
    return out


def library_sound(entry):
    plain, fx = split({k: v for k, v in entry['genome'].items() if k != 'seed'})
    return plain, {**fx, **LIBRARY_FX}


if __name__ == '__main__':
    what = sys.argv[1] if len(sys.argv) > 1 else 'labelled'
    prepare()
    if not os.path.exists('drive.mjs'): subprocess.run(['node', os.path.join(HERE, 'build.mjs')], check=True)
    os.makedirs(TMP, exist_ok=True)
    with Pool(int(os.environ.get('WORKERS', max(1, os.cpu_count() - 1)))) as pool:
        if what == 'labelled':
            items = json.load(open('manifest.json'))
            results = check_all({i['id']: (i['plain'], i['fx']) for i in items}, pool)
            json.dump(results, open('drive_scores.json', 'w'), indent=1)
            flagged = set()
            for i in items:
                fails = verdict(results[i['id']])
                if fails: flagged.add(i['id'])
                note = verdict(results[i['id']], ('evolving',))
                print(f"{i['name'][:22]:24}{i['label']:12}{'REJECT ' + '; '.join(fails) if fails else 'pass'}{'   [evolving: ' + '; '.join(note) + ']' if note else ''}")
            assert {'growl', 'sweep'} <= flagged, 'full-drive check missed a dropped sound'
            assert not flagged & {i['id'] for i in items if i['label'] == 'ok'}, 'full-drive check rejected a kept sound'
            print('full-drive check OK')
        else:
            lib = json.load(open('library.json'))
            results = check_all({e['cell']: library_sound(e) for e in lib['elites']}, pool)
            failed = {c: verdict(r) for c, r in results.items() if verdict(r)}
            # Fallback: the box's runners-up, safest first; the first that passes the full drive takes the box.
            tries = {f"{e['cell']}#{n}": library_sound(r) for e in lib['elites'] if e['cell'] in failed for n, r in enumerate(e.get('runners', []))}
            backup = check_all(tries, pool) if tries else {}
            kept, report = [], {'failed': failed, 'replaced': {}, 'dropped': []}
            for e in lib['elites']:
                c = e['cell']
                if c not in failed: kept.append({**e, 'drive': results[c]}); continue
                ok = next((n for n in range(len(e.get('runners', []))) if not verdict(backup[f'{c}#{n}'])), None)
                if ok is None: report['dropped'].append(c); continue
                kept.append({**e['runners'][ok], 'drive': backup[f'{c}#{ok}'], 'replaces': 'elite failed the full drive'})
                report['replaced'][c] = ok + 1
            lib['elites'], lib['driveCheck'] = kept, report
            json.dump(lib, open('library.json', 'w'), indent=1)
            # Frozen pool for the app's sound-map search (experiment/source_search.py SoundMapDiscovery): only what a session needs.
            pool = {'created': lib.get('created'), 'source': 'tools/sound_map library (generate.py + drive.py library)', 'limits': lib['limits'],
                    'sounds': [{'cell': e['cell'], 'from': e.get('from'), 'genome': {k: v for k, v in e['genome'].items() if k != 'seed'},
                                'metrics': e['metrics'], 'drive': {k: v for k, v in e['drive']['rise'].items() if k != 'at'}} for e in kept]}
            json.dump(pool, open(POOL, 'w'), indent=0)
            print(f'pool for the app: {len(kept)} sounds -> {POOL}')
            evolving = [c for e in kept for c in [e['cell']] if verdict(e['drive'], ('evolving',))]
            report['evolvingOnly'] = evolving
            print(f"{len(results)} winners checked, {len(failed)} failed, {len(report['replaced'])} replaced, {len(report['dropped'])} boxes emptied; {len(evolving)} kept sounds would fail in Evolving (not gated)")
            for c, why in sorted(failed.items()):
                print(f"  {c:16}{'; '.join(why)}  ->  {'runner-up #' + str(report['replaced'][c]) if c in report['replaced'] else 'no passing runner-up, box emptied'}")
