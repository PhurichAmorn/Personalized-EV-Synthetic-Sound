"""Phase 2: checked variations of every pool sound, so a session can fine-tune the listener's favourite (pairs 17-19) without
generating anything live. Each variation is the pool sound with ONE named move (or two, as a combination) on its layered (stack) recipe:
  brighter / darker      low-pass (stack cutoff) and tone x/÷ 1.5
  deeper / higher        root -/+ 3 semitones
  fuller / thinner       upper layers louder/softer (fall), more/less fifth
  smoother / shimmer     less/more swell depth and glass shimmer, fewer/more sparkle pings
  body+ / body-          low peak +/- 3 dB
  swap1 / swap2          one layer's texture swapped (two different layers)
  brighter+deeper ... and the other three bright/pitch combinations
A variation is kept if it passes the quick guardrail and the full 22 s drive check in Rising (Evolving is measured and stored, as for pool
sounds), and is audibly different from its parent but still the same sound: gap (generate.gap, in 'distinct' steps) in [NEAR, FAR].
Writes the kept variations into the pool file under each sound ('variations'). Heavy: run on the cooled laptop.
  LIMIT_F=0.2 WORKERS=14 python tools/sound_map/variations.py [pool file, default experiment/sound_map_pool.json]"""
import json, os, subprocess, sys
for var in ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'VECLIB_MAXIMUM_THREADS'): os.environ[var] = '1'
from multiprocessing import Pool
import numpy as np
from generate import LIMITS, FRAME_TEXTURES, check, gap, style_of
from score import prepare
from drive import check_all, verdict, TMP

NEAR, FAR = .3, 1.5  # audibly different (0.3 step) but not a new sound (1.5 steps; a layer swap may change the style, which counts 1)
HERE = os.path.dirname(os.path.abspath(__file__))
POOL = os.path.abspath(sys.argv[1]) if len(sys.argv) > 1 else os.path.join(HERE, '..', '..', 'experiment', 'sound_map_pool.json')
WORKERS = int(os.environ.get('WORKERS', max(1, os.cpu_count() - 1)))
rng = np.random.default_rng(int(os.environ.get('SEED', 1)))
clip = lambda v, lo, hi: float(min(max(v, lo), hi))


def moves(sound):
    """{name: (voice, fx)} for one stack pool sound."""
    def make(*changes):
        voice = json.loads(json.dumps(sound['voice'])); fx = dict(sound['fx']); st = voice['stack']
        for change in changes: change(st, fx)
        return voice, fx
    def bright(k):
        def change(st, fx): st['cutoff'] = clip(st['cutoff'] * k, 800, 6000); fx['tone'] = clip(fx['tone'] * k, 800, 6000)
        return change
    def pitch(semitones):
        def change(st, fx): st['rootHz'] = round(clip(st['rootHz'] * 2 ** (semitones / 12), 41, 130) * 5) / 5
        return change
    def full(d):
        def change(st, fx): st['fall'] = clip(st['fall'] + .15 * d, .35, .95); st['fifth'] = clip(st['fifth'] + .2 * d, 0, .6)
        return change
    def shimmer(d):
        def change(st, fx):
            st['depth'] = clip(st['depth'] + .2 * d, 0, .5); st['shimmer'] = clip(st['shimmer'] + .2 * d, 0, .5)
            st['twinkle'] = clip(st.get('twinkle', 8) + 4 * d, 3, 16)
        return change
    def body(db):
        def change(st, fx): st['peakDb'] = clip(st['peakDb'] + db, 0, 9)
        return change
    st = sound['voice']['stack']; layers = list(range(st['layers'])); rng.shuffle(layers)
    usable = [t for t in FRAME_TEXTURES if (t != 10 or 'plain' in st) and (t != 11 or 'blocks' in st)]  # 10/11 need their voice settings
    def swap(k):
        def change(st, fx): st['timbres'][k] = int(rng.choice([t for t in usable if t != st['timbres'][k]]))
        return change
    out = {'brighter': make(bright(1.5)), 'darker': make(bright(1 / 1.5)), 'deeper': make(pitch(-3)), 'higher': make(pitch(3)),
           'fuller': make(full(1)), 'thinner': make(full(-1)), 'smoother': make(shimmer(-1)), 'shimmer': make(shimmer(1)),
           'body+': make(body(3)), 'body-': make(body(-3)), 'swap1': make(swap(layers[0])), 'swap2': make(swap(layers[1 % len(layers)])),
           'brighter+deeper': make(bright(1.5), pitch(-3)), 'brighter+higher': make(bright(1.5), pitch(3)),
           'darker+deeper': make(bright(1 / 1.5), pitch(-3)), 'darker+higher': make(bright(1 / 1.5), pitch(3))}
    return {name: v for name, v in out.items() if v[0] != sound['voice'] or v[1] != sound['fx']}  # a move at its limit changes nothing


def quick(items, pool):
    """[(id, voice, fx, rootHz)] -> {id: (metrics, desc)} with the generator's guardrail check (render with the app's synth)."""
    batches = [[{'id': i, 'voice': v} for i, v, _, _ in items[n::WORKERS]] for n in range(WORKERS)]
    jobs = []
    for n, batch in enumerate(batches):
        if batch: json.dump(batch, open(f'vbatch{n}.json', 'w')); jobs.append(subprocess.Popen(['node', 'synth.mjs', f'vbatch{n}.json', 'tmp']))
    if any(job.wait() for job in jobs): raise RuntimeError('render failed')
    return dict(zip([i for i, *_ in items], pool.map(check, [(f'tmp/{i}.f32', fx, root) for i, _, fx, root in items])))


if __name__ == '__main__':
    prepare(); os.makedirs('tmp', exist_ok=True); os.makedirs(TMP, exist_ok=True)
    data = json.load(open(POOL)); sounds = [s for s in data['sounds'] if s['voice']['kind'] == 'stack']
    with Pool(WORKERS) as pool:
        items, meta = [], {}
        for s in sounds:
            for name, (voice, fx) in moves(s).items():
                vid = f"{s['id']}-{name}"; items.append((vid, voice, fx, voice['stack']['rootHz'])); meta[vid] = (s, name, voice, fx)
        print(f'{len(items)} variations of {len(sounds)} sounds: quick check', flush=True)
        checked = quick(items, pool)
        near = {}
        for vid, (m, d) in checked.items():
            s, name, voice, fx = meta[vid]
            if any(m[k] > LIMITS[k] for k in LIMITS): continue
            desc = {**d, 'R': m['R'], 'F': m['F'], 'chorus': fx.get('chorus', 0), 'vib': fx.get('vibDepth', 0),
                    'style': style_of({'voice': 'stack', 'stLayers': voice['stack']['layers'], **{f'stT{k}': t for k, t in enumerate(voice['stack']['timbres'])}})}
            if NEAR <= gap(s['desc'], desc) <= FAR: near[vid] = (m, desc)
        print(f'{len(near)} pass the quick check and are near their parent: full-drive check', flush=True)
        drive = check_all({vid: meta[vid][2:] for vid in near}, pool)
    kept = 0
    for s in sounds: s['variations'] = []
    for vid, (m, desc) in near.items():
        s, name, voice, fx = meta[vid]
        if verdict(drive[vid]): continue
        s['variations'].append({'id': vid, 'parent': s['id'], 'move': name, 'voice': voice, 'fx': fx, 'rootHz': voice['stack']['rootHz'],
                                'style': desc['style'], 'metrics': m, 'desc': desc,
                                'drive': {k: v for k, v in drive[vid]['rise'].items() if k != 'at'},
                                'driveEvolving': {k: v for k, v in drive[vid]['evolving'].items() if k != 'at'}})
        kept += 1
    data['variations'] = {'near': NEAR, 'far': FAR, 'kept': kept}
    json.dump(data, open(POOL, 'w'), indent=0)
    per = [len(s['variations']) for s in sounds]
    print(f'{kept} variations kept -> {POOL}; per sound min {min(per)}, median {int(np.median(per))}, max {max(per)}')
