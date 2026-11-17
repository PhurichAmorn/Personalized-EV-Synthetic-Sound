"""Sound generator with an open archive (no grid, no size limit): keeps every sound that passes the guardrail and sounds different
from all sounds kept so far. Two voices (desktop/src/mapVoice.ts): the plain synth and the generic 'blocks' voice (harmonic slope,
resonant peaks, FM, noise band, waveshaper, amplitude modulation, inharmonic partials).
"Different" is measured on heard traits (see distinct()); among near-copies the one with more room under the guardrail stays
(novelty search with local competition: Lehman & Stanley 2011; unstructured archive: Cully & Demiris 2018).
No training. Usage: python tools/sound_map/generate.py [rounds, default 40] [--seeds]. --seeds starts from the listener's kept
sounds as well; by default the search starts from random sounds only. Writes out/library.json after every round."""
import hashlib, json, os, shutil, subprocess, sys, time
for var in ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'VECLIB_MAXIMUM_THREADS'): os.environ[var] = '1'  # one thread per worker
from multiprocessing import Pool
import numpy as np
from mosqito.sq_metrics import sharpness_din_st, roughness_dw
from score import FS, PITCHES, play, fluctuation, crowding, prepare

LIMITS = {'S': 1.3, 'R': .3, 'F': .4, 'C': 70}  # guardrail: reject above any (checked on the listener's labels; C from the 2026-11-16 map marks)
# Gene: (low, high, log scale). Plain synth settings (plainSource.ts); no 'air': fixed at 0 like every preset (heard as wind).
PLAIN_GENES = {'rootHz': (80, 200, 1), 'brightness': (0, 1, 0), 'hollow': (0, 1, 0), 'bell': (0, 1, 0), 'softTop': (600, 6000, 1),
               'chord': (0, 1, 0), 'vowel': (0, 1, 0), 'vowelShape': (0, 1, 0), 'fundamental': (.3, 1, 0), 'whine': (0, 1, 0),
               'whineRatio': (3, 8, 0), 'detune': (0, 1, 0)}
PLAIN_CHOICES = {'chordType': list(range(8)), 'bellModes': [0, 1]}
# Blocks voice (sourceDesigner.ts 'blocks'; ranges as the open-pool search, OPEN_KEYS in experiment/source_search.py). rootRatio x 174.8 Hz
# keeps the same 80-200 Hz root range as the plain synth. ensemble = companion detune and pad level.
BLOCK_GENES = {'rootRatio': (80 / 174.8, 200 / 174.8, 1), 'slope': (.3, 2.5, 0), 'evenGain': (0, 1.5, 0), 'peak1Hz': (100, 5000, 1), 'peak1Gain': (0, 4, 0),
               'peak2Hz': (100, 5000, 1), 'peak2Gain': (0, 4, 0), 'peakWidth': (.15, 1, 0), 'cutoff': (400, 8000, 1), 'inharm': (0, .01, 0),
               'fmMix': (0, .8, 0), 'fmRatio': (.5, 7, 0), 'fmIndex': (.2, 2.5, 0), 'noiseMix': (0, .8, 0), 'noiseCenter': (150, 6000, 1),
               'noiseWidth': (50, 2000, 1), 'amRate': (0, 40, 0), 'amDepth': (0, .8, 0), 'lope': (0, 1, 0), 'drive': (0, 4, 0), 'ensemble': (0, 1, 0)}
BLOCK_SWITCHES = ('inharm', 'lope', 'drive', 'fmMix', 'noiseMix', 'amDepth')  # building blocks that are off (0) unless switched on
# Engine effects after the player (labEngine.ts), shared by both voices.
# chorus (0-2, as LEVEL_VALUES), vibrato depth in cents (engine vibrato only; never baked into the loop), body EQ: give sounds width
# and life. Vibrato capped at 8 cents and half of new sounds dry (v4): with 0-20 cents and no dry share, 61% of the v3 pool wobbled
# over 10 cents and sessions sounded ghostly (heard 2026-11-17). The quick check skips them (score.play); the full-drive check (drive.py) renders them.
FX_GENES = {'tone': (800, 6000, 1), 'res': (.6, 8, 1), 'tremDepth': (0, .6, 0), 'tremRate': (.1, 2, 1), 'reverb': (0, .6, 0),
            'chorus': (0, 2, 0), 'vibDepth': (0, 8, 0), 'vibRate': (3, 7, 0), 'bodyHz': (200, 1200, 1), 'bodyDb': (0, 6, 0)}
FX_CHOICES = {'pump': [0, 1], 'drift': [0, 1]}
GENES = {**PLAIN_GENES, **BLOCK_GENES, **FX_GENES}
VOICE_GENES = {'plain': list(PLAIN_GENES) + list(FX_GENES), 'blocks': list(BLOCK_GENES) + list(FX_GENES)}
# Distinct = clearly different on at least one heard trait. v2 used the app's too-similar steps (spectrum 0.25, 5 semitones,
# inharm 0.25, R 0.1, F 0.15) and the listener heard most sounds as alike (2026-11-17), so every step is larger. Vibrato step
# 5 cents of the 8-cent range (v4). Chorus and vibrato
# count as traits so wide or moving sounds are not replaced by dry near-copies. All steps provisional (not yet checked by ear).
DISTINCT = {'spectrum': .4, 'pitch': 7, 'inharm': .4, 'R': .15, 'F': .2, 'chorus': 1.2, 'vib': 5}
BANDS = [100, 200, 400, 800, 1600, 3200, 6400]  # Hz, as levels.ts soundProfile
rng = np.random.default_rng(1)
WORKERS = max(1, os.cpu_count() - 1)


def to_unit(key, value):
    lo, hi, log = GENES[key]
    return (np.log(value / lo) / np.log(hi / lo)) if log else (value - lo) / (hi - lo)


def from_unit(key, u):
    lo, hi, log = GENES[key]; u = float(np.clip(u, 0, 1))
    return float(lo * (hi / lo) ** u if log else lo + (hi - lo) * u)


def random_genome(voice=None):
    g = {k: from_unit(k, rng.random()) for k in GENES}
    for k in BLOCK_SWITCHES:
        if rng.random() > .3: g[k] = 0.  # each building block on with 30% chance: sounds made of a few blocks, not all at once
    g.update({k: int(rng.choice(v)) for k, v in {**PLAIN_CHOICES, **FX_CHOICES}.items()})
    if rng.random() < .5: g['chorus'], g['vibDepth'] = rng.uniform(0, .3), 0.  # dry: no wobble, little chorus
    g['voice'] = voice or ('plain' if rng.random() < .5 else 'blocks'); return g


def mutate(g, sigma=.12):
    child = dict(g)
    for k in rng.choice(VOICE_GENES[g['voice']], size=rng.integers(2, 5), replace=False):
        child[k] = from_unit(k, to_unit(k, g[k]) + rng.normal(0, sigma))
    for k in BLOCK_SWITCHES:
        if g['voice'] == 'blocks' and rng.random() < .05: child[k] = 0. if g[k] else from_unit(k, rng.random())  # switch a block on/off
    for k, v in {**PLAIN_CHOICES, **FX_CHOICES}.items():
        if rng.random() < .08: child[k] = int(rng.choice(v))
    if rng.random() < .03: child['voice'] = 'blocks' if g['voice'] == 'plain' else 'plain'
    return child


def crossover(a, b):
    return {k: (a if rng.random() < .5 else b).get(k, a.get(k)) for k in a.keys() | b.keys()} if a['voice'] == b['voice'] else dict(a)


def voice_of(g):
    """mapVoice.ts MapVoice of a genome."""
    if g['voice'] == 'blocks':
        shape = {k: g[k] for k in BLOCK_GENES if k != 'ensemble'}
        return {'kind': 'blocks', 'shape': shape, 'controls': {'body': .5, 'character': .5, 'ensemble': g['ensemble'], 'movement': 0}}
    return {'kind': 'plain', 'plain': {**{k: g[k] for k in PLAIN_GENES}, **{k: g[k] for k in PLAIN_CHOICES}, 'width': 1}}


def fx_of(g):
    fx = {**{k: g[k] for k in FX_GENES}, **{k: g[k] for k in FX_CHOICES}, 'follow': 1}
    if fx['drift']: fx['driftPeriod'] = 14
    return fx


def root_hz(g):
    return round(174.8 * g['rootRatio'] * 5) / 5 if g['voice'] == 'blocks' else g['rootHz']


def loop_partials(loop):
    """Partials of a seamless 5 s loop: every component sits on the 0.2 Hz loop grid, so FFT bins are exact."""
    spectrum = np.abs(np.fft.rfft(loop)) * 2 / len(loop); hz = np.fft.rfftfreq(len(loop), 1 / FS)
    keep = spectrum > spectrum.max() * 1e-3
    return [[float(f), float(a)] for f, a in zip(hz[keep], spectrum[keep])]


def describe(loop, fx, root):
    """Heard traits for 'distinct': octave-band profile at full pedal (app formula), pitch, inharmonic share of the loop's energy."""
    x = play(loop, fx, *PITCHES['peak'])
    power = np.abs(np.fft.rfft(x)) ** 2; hz = np.fft.rfftfreq(len(x), 1 / FS)
    edges = np.digitize(hz, BANDS); bands = np.array([power[edges == b].sum() for b in range(len(BANDS) + 1)])
    bands = np.sqrt(bands / max(bands.sum(), 1e-30))
    s = np.abs(np.fft.rfft(loop)) ** 2; f = np.fft.rfftfreq(len(loop), 1 / FS); grid = root / 2  # sub-octave companions are harmonic
    off = np.abs(f / grid - np.round(f / grid)) * grid > np.maximum(.015 * f, 1.)
    return {'bands': bands.round(4).tolist(), 'pitch': float(12 * np.log2(root / 80)), 'inharm': float(s[off & (f > 20)].sum() / max(s[f > 20].sum(), 1e-30))}


def check(job):
    """Guardrail measures (worst of cruising and peak pitch; margin > 0 means it passes) plus heard traits."""
    path, fx, root = job
    loop = np.fromfile(path, dtype=np.float32).astype(float); os.remove(path)
    if os.path.exists(path[:-4] + '.json'): partials = json.load(open(path[:-4] + '.json')); os.remove(path[:-4] + '.json')
    else: partials = loop_partials(loop)
    worst = {'S': 0, 'R': 0, 'F': 0, 'C': 0}
    for rate, pedal in PITCHES.values():
        x = play(loop, fx, rate, pedal)
        m = {'S': float(sharpness_din_st(x, FS)), 'R': float(np.mean(roughness_dw(x[:FS], FS)[0])), 'F': fluctuation(x), 'C': crowding(partials, fx, rate, pedal)}
        worst = {k: max(worst[k], m[k]) for k in m}
    return worst, describe(loop, fx, root)


def gap(a, b):
    """How different two sounds are, as a multiple of the 'distinct' step on their most different trait (>= 1: distinct)."""
    spectrum = float(np.hypot.reduce(np.array(a['bands']) - np.array(b['bands'])) / np.sqrt(2))
    return max(spectrum / DISTINCT['spectrum'], abs(a['pitch'] - b['pitch']) / DISTINCT['pitch'], abs(a['inharm'] - b['inharm']) / DISTINCT['inharm'],
               abs(a['R'] - b['R']) / DISTINCT['R'], abs(a['F'] - b['F']) / DISTINCT['F'],
               abs(a.get('chorus', 0) - b.get('chorus', 0)) / DISTINCT['chorus'], abs(a.get('vib', 0) - b.get('vib', 0)) / DISTINCT['vib'])


def evaluate(genomes, pool, tmp='tmp'):
    batch = [{'id': str(i), 'voice': voice_of(g)} for i, g in enumerate(genomes)]
    jobs = []
    for n in range(WORKERS):  # render in parallel too
        json.dump(batch[n::WORKERS], open(f'batch{n}.json', 'w'))
        jobs.append(subprocess.Popen(['node', 'synth.mjs', f'batch{n}.json', tmp]))
    if any(job.wait() for job in jobs): raise RuntimeError('render failed')
    return pool.map(check, [(f'{tmp}/{i}.f32', fx_of(g), root_hz(g)) for i, g in enumerate(genomes)])


def seeds():
    """The listener's kept sounds (plain synth), clipped into the search range."""
    out = []
    for item in json.load(open('manifest.json')):
        if item['label'] != 'ok': continue
        g = random_genome('plain'); given = {**item['plain'], **item['fx']}
        g.update({k: float(np.clip(given.get(k, GENES[k][0]), GENES[k][0], GENES[k][1])) for k in PLAIN_GENES | FX_GENES})
        g.update({k: int(round(given.get(k, 0))) for k in {**PLAIN_CHOICES, **FX_CHOICES}})
        g['seed'] = item['name']; out.append(g)
    return out


if __name__ == '__main__':
    prepare()
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    generations, size, fresh = int(args[0]) if args else 40, 140, .15  # fresh: share of each round that is new random sounds
    archive, log, tried, passed = [], [], 0, 0
    created = time.strftime('%Y-%m-%d %H:%M')  # identifies this library (the page keeps marks per library)
    with Pool(WORKERS) as pool:
        for gen in range(generations + 1):
            start = time.time()
            if gen == 0:
                genomes = (seeds() if '--seeds' in sys.argv else []) + [random_genome() for _ in range(size)]
            else:
                pick = lambda: archive[rng.integers(len(archive))]['genome']
                genomes = [random_genome() if rng.random() < fresh else mutate(crossover(pick(), pick()) if rng.random() < .25 else pick()) for _ in range(size)]
            added = replaced = 0
            for g, (m, d) in zip(genomes, evaluate([{k: v for k, v in g.items() if k != 'seed'} for g in genomes], pool)):
                tried += 1
                margin = min(1 - m[k] / LIMITS[k] for k in LIMITS)
                if margin <= 0: continue
                passed += 1
                desc = {**d, 'R': m['R'], 'F': m['F'], 'chorus': g['chorus'], 'vib': g['vibDepth']}
                entry = {'id': hashlib.sha1(json.dumps(g, sort_keys=True).encode()).hexdigest()[:10], 'genome': g, 'voice': voice_of(g),
                         'fx': fx_of(g), 'rootHz': root_hz(g), 'metrics': m, 'desc': desc, 'margin': margin, 'gen': gen, 'from': g.get('seed')}
                gaps = [gap(desc, e['desc']) for e in archive]
                near = int(np.argmin(gaps)) if gaps else None
                if near is None or gaps[near] >= 1: archive.append(entry); added += 1
                elif margin > archive[near]['margin']: archive[near] = entry; replaced += 1  # local competition: the safer near-copy stays
            log.append({'gen': gen, 'tried': tried, 'passed': passed, 'kept': len(archive), 'added': added, 'replaced': replaced,
                        'blocks': sum(e['genome']['voice'] == 'blocks' for e in archive), 'seconds': round(time.time() - start, 1)})
            print(log[-1], flush=True)
            json.dump({'created': created, 'limits': LIMITS, 'distinct': DISTINCT, 'log': log, 'sounds': archive}, open('library.json', 'w'), indent=1)
    shutil.rmtree('tmp', ignore_errors=True)
