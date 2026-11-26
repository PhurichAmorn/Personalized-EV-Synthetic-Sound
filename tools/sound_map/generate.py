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
LIMITS['F'] = float(os.environ.get('LIMIT_F', LIMITS['F']))  # LIMIT_F=0.2: stricter pulsing (layered stacks: listening marks 2026-11-18 sat near 0.3)
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
# Stack voice (desktop/src/stackVoice.ts, 2026-11-17): the same note in 3-5 octaves, each layer its own texture and slow swell, with a
# fixed after-player low peak and low-pass. stRoot is the lowest layer (41-130 Hz; the stack reaches up from there). The first run
# (low-pass 500-3000 Hz) piled up at the darkest settings, so the low-pass now spans the other voices' brightness range.
STACK_GENES = {'stRoot': (41, 130, 1), 'stFall': (.35, .95, 0), 'stDepth': (0, .5, 0), 'stFifth': (0, .6, 0), 'stShimmer': (0, .5, 0),
               'stSpread': (0, 1, 0), 'stPeakHz': (60, 400, 1), 'stPeakDb': (0, 9, 0), 'stCutoff': (800, 6000, 1)}
STACK_CHOICES = {'stLayers': [3, 4, 5], 'stSeed': list(range(6)), **{f'stT{k}': [0, 1, 2, 3] for k in range(5)}}
# Frame (2026-11-17): every layer may take any of 12 textures (stackVoice.ts STACK_TEXTURES: plain, strings, hollow, glass, sparkle,
# air, choir, strings pad, cello, electric, the plain synth voice, the blocks voice); --textures all switches it on. No chorus:
# depth comes from the layers (chorus only added copies of the same sound).
STACK_GENES['stTwinkle'] = (3, 16, 0)
# Roles (2026-11-18, stackVoice.ts StackTrend): the body (lowest layer), middle and top players each have a level at rest, a level at full
# drive and a mix of what drives them (0 pedal, 1 speed). The full levels set what the quick check judges; the drive check plays the real trends.
for _r, _name in enumerate(('Body', 'Mid', 'Top')):
    STACK_GENES.update({f'stRest{_r}': (.05, 1, 0), f'stFull{_r}': (.3, 1, 0), f'stMix{_r}': (0, 1, 0)})
FRAME_TEXTURES = [0, 1, 2, 3, 6, 7, 8, 9, 10, 11]  # no 5 air (wind noise); no 4 sparkle: its pings clicked in 7 of 9 pool sounds (heard 2026-11-18; softer or longer pings did not help)
# Styles (2026-11-18): five texture families. A sound's style is the family of at least half its layers ('blend' otherwise).
# --style NAME grows a stack library of that style only (loose rule: the other layers may be any texture).
# ponytail: counts layers, not their loudness; weight by layer level if a quiet layer is heard to decide the style.
STYLES = {'electric': [9, 10, 11], 'strings': [1, 7, 8], 'glass': [3], 'choir': [6], 'plain': [0, 2]}
STYLE = None
# Body-led (2026-11-19): --body makes the body (lowest layer) the clearly loudest player, so the note heard is always the root and never
# jumps an octave as the middle or top open with the drive (listener: the root decided nothing when another layer led). Fall at most .7,
# and the middle and top levels are capped at half the body's, at rest and at full drive (levels between follow, so the whole drive).
# ponytail: estimated from the settings (fifths and shimmer counted at full level); build_pool.py --grid also checks the measured bands.
BODY = False
GRID_ROOTS = (58, 89)  # Hz: deep below 58, middle to 89, high above (thirds of B's 2026-11-19 survivors)
GENES = {**PLAIN_GENES, **BLOCK_GENES, **FX_GENES, **STACK_GENES}
VOICE_GENES = {'plain': list(PLAIN_GENES) + list(FX_GENES), 'blocks': list(BLOCK_GENES) + list(FX_GENES), 'stack': list(STACK_GENES) + list(FX_GENES)}
NO_CHORUS = set()  # voices that never get chorus (--textures all: stack)
VOICES = ['plain', 'blocks']  # voices new random sounds use; --voices stack (comma list) changes it
# Distinct = clearly different on at least one heard trait. v2 used the app's too-similar steps (spectrum 0.25, 5 semitones,
# inharm 0.25, R 0.1, F 0.15) and the listener heard most sounds as alike (2026-11-17), so every step is larger. Vibrato step
# 5 cents of the 8-cent range (v4). Chorus and vibrato
# count as traits so wide or moving sounds are not replaced by dry near-copies. All steps provisional (not yet checked by ear).
DISTINCT = {'spectrum': .4, 'pitch': 7, 'inharm': .4, 'R': .15, 'F': .2, 'chorus': 1.2, 'vib': 5, 'trend': .35}  # trend: the biggest change in a player's rest/full level or mix (0-1 each)
BANDS = [100, 200, 400, 800, 1600, 3200, 6400]  # Hz, as levels.ts soundProfile
rng = np.random.default_rng(int(os.environ.get('SEED', 1)))  # SEED=2, 3...: a different start per machine (islands, merged by merge.py)
WORKERS = int(os.environ.get('WORKERS', max(1, os.cpu_count() - 1)))  # WORKERS=4 on a laptop: slower, stays cool
LIBRARY = os.environ.get('LIBRARY', 'library.json')  # in out/; a separate name keeps the app's library and pool untouched


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
    g.update({k: int(rng.choice(v)) for k, v in {**PLAIN_CHOICES, **FX_CHOICES, **STACK_CHOICES}.items()})
    if rng.random() < .5: g['chorus'], g['vibDepth'] = rng.uniform(0, .3), 0.  # dry: no wobble, little chorus
    g['voice'] = voice or str(rng.choice(VOICES))
    if g['voice'] in NO_CHORUS: g['chorus'] = 0.
    return g


def mutate(g, sigma=.12):
    child = dict(g)
    for k in rng.choice(VOICE_GENES[g['voice']], size=rng.integers(2, 5), replace=False):
        child[k] = from_unit(k, to_unit(k, g[k]) + rng.normal(0, sigma))
    for k in BLOCK_SWITCHES:
        if g['voice'] == 'blocks' and rng.random() < .05: child[k] = 0. if g[k] else from_unit(k, rng.random())  # switch a block on/off
    for k, v in {**PLAIN_CHOICES, **FX_CHOICES, **STACK_CHOICES}.items():
        if rng.random() < .08: child[k] = int(rng.choice(v))
    if rng.random() < .03 and len(VOICES) > 1: child['voice'] = str(rng.choice([v for v in VOICES if v != g['voice']]))
    if child['voice'] in NO_CHORUS: child['chorus'] = 0.
    return child


def crossover(a, b):
    return {k: (a if rng.random() < .5 else b).get(k, a.get(k)) for k in a.keys() | b.keys()} if a['voice'] == b['voice'] else dict(a)


def style_of(g):
    """Texture family of at least half the layers of a stack genome and more than any other family, else 'blend' (None for other voices)."""
    if g['voice'] != 'stack': return None
    layers = [g[f'stT{k}'] for k in range(g['stLayers'])]
    count = sorted(((sum(t in family for t in layers), name) for name, family in STYLES.items()), reverse=True)
    return count[0][1] if 2 * count[0][0] >= len(layers) and count[0][0] > count[1][0] else 'blend'


def styled(g):
    """With --style: switch random other-texture layers to the style's textures until the sound is of that style."""
    if STYLE is None: return g
    g, family = dict(g), STYLES[STYLE]
    others = [k for k in rng.permutation(g['stLayers']) if g[f'stT{k}'] not in family]
    while style_of(g) != STYLE: g[f'stT{others.pop()}'] = int(rng.choice(family))
    return g


def side_levels(n, fall, shimmer, fifth, root):
    """Level of the middle and the top player relative to the body's, before trends (fifths and shimmer counted at full level)."""
    return (fall if n > 2 else 0), fall ** (n - 1) * (1 + shimmer) + fifth * sum(fall ** k for k in range(n) if root * 2 ** k >= 220)


def body_rule(stack):
    """A stack voice (mapVoice.ts) whose body is at least twice as loud as the middle and the top, at rest and at full drive."""
    mid, top = side_levels(stack['layers'], stack['fall'], stack['shimmer'], stack['fifth'], stack['rootHz'])
    t = stack.get('trend')
    return bool(t) and all(t[e][0] >= 2 * max(t[e][1] * mid, t[e][2] * top) * (1 - 1e-6) for e in ('rest', 'full'))


def body_led(g):
    """With --body: lower the middle and top levels until the body is at least twice as loud as each, at rest and at full drive."""
    if not BODY or g['voice'] != 'stack': return g
    g = dict(g); mid, top = side_levels(g['stLayers'], g['stFall'], g['stShimmer'], g['stFifth'], g['stRoot'])
    for p in ('stRest', 'stFull'):
        if mid: g[p + '1'] = min(g[p + '1'], g[p + '0'] / (2 * mid))
        g[p + '2'] = min(g[p + '2'], g[p + '0'] / (2 * top))
    return g


def used(g):
    return {g[f'stT{k}'] for k in range(g['stLayers'])}


def voice_of(g):
    """mapVoice.ts MapVoice of a genome."""
    if g['voice'] == 'stack':
        return {'kind': 'stack', 'stack': {'rootHz': round(g['stRoot'] * 5) / 5, 'layers': g['stLayers'], 'timbres': [g[f'stT{k}'] for k in range(5)],
                'fall': g['stFall'], 'depth': g['stDepth'], 'seed': g['stSeed'], 'fifth': g['stFifth'], 'shimmer': g['stShimmer'],
                'spread': g['stSpread'], 'peakHz': g['stPeakHz'], 'peakDb': g['stPeakDb'], 'cutoff': g['stCutoff'], 'twinkle': g.get('stTwinkle', 8),
                **({'trend': {'rest': [g[f'stRest{r}'] for r in range(3)], 'full': [g[f'stFull{r}'] for r in range(3)], 'mix': [g[f'stMix{r}'] for r in range(3)]}} if 'stRest0' in g else {}),
                **({'plain': {**{k: g[k] for k in PLAIN_GENES}, **{k: g[k] for k in PLAIN_CHOICES}, 'width': 1}} if 10 in used(g) else {}),
                **({'blocks': {'shape': {k: g[k] for k in BLOCK_GENES if k != 'ensemble'}, 'controls': {'body': .5, 'character': .5, 'ensemble': g['ensemble'], 'movement': 0}}} if 11 in used(g) else {})}}
    if g['voice'] == 'blocks':
        shape = {k: g[k] for k in BLOCK_GENES if k != 'ensemble'}
        return {'kind': 'blocks', 'shape': shape, 'controls': {'body': .5, 'character': .5, 'ensemble': g['ensemble'], 'movement': 0}}
    return {'kind': 'plain', 'plain': {**{k: g[k] for k in PLAIN_GENES}, **{k: g[k] for k in PLAIN_CHOICES}, 'width': 1}}


def fx_of(g):
    fx = {**{k: g[k] for k in FX_GENES}, **{k: g[k] for k in FX_CHOICES}, 'follow': 1}
    if fx['drift']: fx['driftPeriod'] = 14
    return fx


def root_hz(g):
    if g['voice'] == 'stack': return round(g['stRoot'] * 5) / 5
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


SAFE = .25  # guardrail margin above which two near-copies count as equally safe


def better(new, old, others):
    """Local competition between near-copies. If both are comfortably inside the guardrail (margin >= SAFE), the one more different from
    the rest of the archive stays; otherwise the safer one. Before (to 2026-11-17): always the safer one, which pulled the stack voice to
    its darkest settings (darker = less sharp = safer)."""
    if min(new['margin'], old['margin']) < SAFE: return new['margin'] > old['margin']
    novelty = lambda e: min((gap(e['desc'], o['desc']) for o in others), default=0)
    return novelty(new) > novelty(old)


def insert(archive, entry):
    """Archive rule: a clearly different sound is added; a near-copy competes with its nearest (better()). Returns 'added', 'replaced' or None."""
    if any(e['id'] == entry['id'] for e in archive): return None
    gaps = [gap(entry['desc'], e['desc']) for e in archive]
    near = int(np.argmin(gaps)) if gaps else None
    if near is None or gaps[near] >= 1: archive.append(entry); return 'added'
    if better(entry, archive[near], [e for k, e in enumerate(archive) if k != near]): archive[near] = entry; return 'replaced'
    return None


def config():
    """Settings two libraries must share to be merged (merge.py) or resumed."""
    return {'limits': LIMITS, 'distinct': DISTINCT, 'voices': VOICES, 'textures': STACK_CHOICES['stT0'], 'safe': SAFE, 'roles': True, **({'style': STYLE} if STYLE else {}), **({'body': True} if BODY else {})}


def gap(a, b):
    """How different two sounds are, as a multiple of the 'distinct' step on their most different trait (>= 1: distinct)."""
    spectrum = float(np.hypot.reduce(np.array(a['bands']) - np.array(b['bands'])) / np.sqrt(2))
    return max(spectrum / DISTINCT['spectrum'], abs(a['pitch'] - b['pitch']) / DISTINCT['pitch'], abs(a['inharm'] - b['inharm']) / DISTINCT['inharm'],
               abs(a['R'] - b['R']) / DISTINCT['R'], abs(a['F'] - b['F']) / DISTINCT['F'],
               abs(a.get('chorus', 0) - b.get('chorus', 0)) / DISTINCT['chorus'], abs(a.get('vib', 0) - b.get('vib', 0)) / DISTINCT['vib'],
               max((abs(x - y) for x, y in zip(a.get('trend', []), b.get('trend', []))), default=0) / DISTINCT['trend'],  # roles: another trend counts as another sound
               float(a.get('style') != b.get('style')))  # another style is always distinct


def coverage(archive):
    """What the library holds: layer counts, and for each player (body, mid, top) how many sounds rise, stay or fall with the drive
    and what moves it (pedal or speed). A thin row means that kind of sound is missing: run more rounds or another seed."""
    rows = [e['desc'] for e in archive if 'trend' in e['desc']]
    if not rows: return 'coverage: no roles in this library'
    out = ['coverage of %d sounds with roles. layers 3/4/5: %s' % (len(rows), '/'.join(str(sum(d['layers'] == n for d in rows)) for n in (3, 4, 5)))]
    for r, name in enumerate(('body', 'mid', 'top')):
        move = [d['trend'][3 + r] - d['trend'][r] for d in rows]
        out.append('  %s: rises %d, stays %d, falls %d | follows pedal %d, speed %d' % (name, sum(m > .15 for m in move), sum(abs(m) <= .15 for m in move), sum(m < -.15 for m in move),
                   sum(d['trend'][6 + r] < .5 for d in rows), sum(d['trend'][6 + r] >= .5 for d in rows)))
    if BODY:  # the session grid: deep / middle / high root x dark / bright (sharpness above the median of that root band)
        for lo, hi, name in ((0, GRID_ROOTS[0], 'deep'), (*GRID_ROOTS, 'middle'), (GRID_ROOTS[1], 999, 'high')):
            S = [e['metrics']['S'] for e in archive if lo <= e['rootHz'] < hi]
            out.append('  %s: %d sounds, sharpness %s' % (name, len(S), '%.2f-%.2f' % (min(S), max(S)) if S else '-'))
    return '\n'.join(out)


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
    if '--style' in sys.argv:  # one style's library: layered textures only (implies --voices stack --textures all)
        STYLE = sys.argv[sys.argv.index('--style') + 1]
        if STYLE not in STYLES: raise SystemExit(f'--style: one of {", ".join(STYLES)}')
        VOICES[:] = ['stack']
    if '--body' in sys.argv: BODY = True; GENES['stFall'] = (.35, .7, 0)
    if '--voices' in sys.argv: VOICES[:] = sys.argv[sys.argv.index('--voices') + 1].split(',')
    if '--textures' in sys.argv or STYLE:  # frame: every layer any texture; the plain and blocks genes evolve inside stacks too; no chorus
        STACK_CHOICES.update({f'stT{k}': FRAME_TEXTURES for k in range(5)}); NO_CHORUS.add('stack')
        VOICE_GENES['stack'] = [k for k in VOICE_GENES['stack'] if k != 'chorus'] + [k for k in PLAIN_GENES if k != 'rootHz'] + [k for k in BLOCK_GENES if k != 'rootRatio']
    args = [a for a in sys.argv[1:] if not a.startswith('--') and a not in VOICES and a != 'all' and a not in STYLES]
    generations, size, fresh = int(args[0]) if args else 40, 140, .15  # fresh: share of each round that is new random sounds
    archive, log, tried, passed, first = [], [], 0, 0, 0
    if '--resume' not in sys.argv and os.path.exists(LIBRARY + '.trials.jsonl'): os.remove(LIBRARY + '.trials.jsonl')  # a fresh run starts a fresh log
    created = time.strftime('%Y-%m-%d %H:%M')  # identifies this library (the page keeps marks per library)
    if '--resume' in sys.argv and os.path.exists(LIBRARY):  # continue a saved run (e.g. after a Colab disconnect)
        saved = json.load(open(LIBRARY))
        if saved.get('config') != json.loads(json.dumps(config())): raise SystemExit('resume: the saved library was made with other settings')
        archive, log, created = saved['sounds'], saved['log'], saved['created']
        tried, passed, first = log[-1]['tried'], log[-1]['passed'], log[-1]['gen'] + 1
        rng = np.random.default_rng([int(os.environ.get('SEED', 1)), first])  # fresh stream, not a replay of the first rounds
        print(f'resuming {LIBRARY} at round {first} with {len(archive)} sounds', flush=True)
    with Pool(WORKERS) as pool:
        for gen in range(first, generations + 1):
            start = time.time()
            if gen == 0:
                genomes = (seeds() if '--seeds' in sys.argv else []) + [body_led(styled(random_genome())) for _ in range(size)]
            else:
                pick = lambda: archive[rng.integers(len(archive))]['genome']
                genomes = [body_led(styled(random_genome() if rng.random() < fresh else mutate(crossover(pick(), pick()) if rng.random() < .25 else pick()))) for _ in range(size)]
            added = replaced = 0
            trials = open(LIBRARY + '.trials.jsonl', 'a')  # every try, passed or not: the data to learn the safe settings from
            for g, (m, d) in zip(genomes, evaluate([{k: v for k, v in g.items() if k != 'seed'} for g in genomes], pool)):
                tried += 1
                margin = min(1 - m[k] / LIMITS[k] for k in LIMITS)
                trials.write(json.dumps({'gen': gen, 'g': {k: round(v, 4) if isinstance(v, float) else v for k, v in g.items()}, 'm': {k: round(v, 4) for k, v in m.items()}, 'pass': margin > 0}) + '\n')
                if margin <= 0: continue
                passed += 1
                desc = {**d, 'R': m['R'], 'F': m['F'], 'chorus': g['chorus'], 'vib': g['vibDepth'], 'style': style_of(g),
                        **({'trend': [g[f'st{n}{r}'] for n in ('Rest', 'Full', 'Mix') for r in range(3)], 'layers': g['stLayers']} if 'stRest0' in g else {})}
                entry = {'id': hashlib.sha1(json.dumps(g, sort_keys=True).encode()).hexdigest()[:10], 'genome': g, 'voice': voice_of(g),
                         'fx': fx_of(g), 'rootHz': root_hz(g), 'style': style_of(g), 'metrics': m, 'desc': desc, 'margin': margin, 'gen': gen, 'from': g.get('seed')}
                result = insert(archive, entry)
                added += result == 'added'; replaced += result == 'replaced'
            trials.close()
            log.append({'gen': gen, 'tried': tried, 'passed': passed, 'kept': len(archive), 'added': added, 'replaced': replaced,
                        'blocks': sum(e['genome']['voice'] == 'blocks' for e in archive), 'seconds': round(time.time() - start, 1)})
            print(log[-1], flush=True)
            json.dump({'created': created, 'limits': LIMITS, 'distinct': DISTINCT, 'config': config(), 'log': log, 'sounds': archive}, open(LIBRARY + '.tmp', 'w'), indent=1)
            os.replace(LIBRARY + '.tmp', LIBRARY)  # never a half-written library if the machine stops mid-save
    print(coverage(archive), flush=True)
    shutil.rmtree('tmp', ignore_errors=True)
