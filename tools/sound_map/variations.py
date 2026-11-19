"""Phase 2: checked variations of every pool sound, so a session can fine-tune the listener's favourite (pairs 17-19) without
generating anything live. Ladder (2026-11-19; steps doubled 2026-11-20: x1.4 / 2 st / 0.3 were not heard, 'Both good' twice): each variation turns ONE knob of the pool sound's layered (stack) recipe by one or two steps:
  brighter / darker (2)  low-pass (stack cutoff) and tone x/÷ 2 per step, middle and top player levels x/÷ 1.3 per step
  deeper / higher (2)    root -/+ 4 semitones (one step) or 7 (two steps)
  fuller / thinner       upper layers louder/softer (fall +/- .1), more/less fifth (+/- .15)
  swap1 / swap2          one layer's texture swapped (two different layers)
'brighter2' is two steps; the session offers it only after 'brighter' won. No combinations of knobs (yet).
A variation is kept if it passes the quick guardrail and the full 22 s drive check in Rising (Evolving is measured and stored, as for pool
sounds), and is audibly different from its parent but still the same sound: gap (generate.gap, in 'distinct' steps) in [NEAR, FAR];
a brightness step counts as audible when its sharpness moves by at least BRIGHT_S (the spectrum gap hardly moves when the body leads).
A body-led parent (build_pool.py --grid) keeps only variations whose body still leads, by settings and as measured (2026-11-19).
Writes the kept variations into the pool file under each sound ('variations'). Heavy: run on the cooled laptop.
  LIMIT_F=0.2 WORKERS=14 python tools/sound_map/variations.py [pool file, default experiment/sound_map_pool.json]"""
import json, os, subprocess, sys
for var in ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'VECLIB_MAXIMUM_THREADS'): os.environ[var] = '1'
from multiprocessing import Pool
import numpy as np
from generate import LIMITS, FRAME_TEXTURES, check, gap, style_of, body_rule, side_levels
from build_pool import body_leads
from score import prepare
from drive import check_all, verdict, TMP

NEAR, FAR = .6, 1.5  # audibly different (0.6 step; 0.3 was not heard) but not a new sound (1.5 steps; a layer swap may change the style, which counts 1)
BRIGHT_S = .08  # acum (.03 was not heard): smallest sharpness change that counts as an audible brightness step
HERE = os.path.dirname(os.path.abspath(__file__))
POOL = os.path.abspath(sys.argv[1]) if len(sys.argv) > 1 else os.path.join(HERE, '..', '..', 'experiment', 'sound_map_pool.json')
WORKERS = int(os.environ.get('WORKERS', max(1, os.cpu_count() - 1)))
rng = np.random.default_rng(int(os.environ.get('SEED', 1)))
clip = lambda v, lo, hi: float(min(max(v, lo), hi))


def moves(sound):
    """{name: (voice, fx)} for one stack pool sound."""
    lead = body_rule(sound['voice']['stack'])  # a body-led parent (grid pool) keeps only body-led variations
    def make(*changes):
        voice = json.loads(json.dumps(sound['voice'])); fx = dict(sound['fx']); st = voice['stack']
        for change in changes: change(st, fx)
        return voice, fx
    def bright(n):  # n steps (negative: darker)
        def change(st, fx):
            st['cutoff'] = clip(st['cutoff'] * 2 ** n, 800, 6000); fx['tone'] = clip(fx['tone'] * 2 ** n, 800, 6000)
            if 'trend' in st:  # upper players louder, but never past half the body (body rule), so the body stays the base
                mid, top = side_levels(st['layers'], st['fall'], st['shimmer'], st['fifth'], st['rootHz'])
                for e in ('rest', 'full'):
                    t = st['trend'][e]; t[1:] = [clip(x * 1.3 ** n, .02, 1) for x in t[1:]]
                    if lead: t[1] = min(t[1], t[0] / (2 * mid)) if mid else t[1]; t[2] = min(t[2], t[0] / (2 * top))
        return change
    def pitch(semitones):
        def change(st, fx): st['rootHz'] = round(clip(st['rootHz'] * 2 ** (semitones / 12), 41, 130) * 5) / 5
        return change
    def full(d):
        def change(st, fx): st['fall'] = clip(st['fall'] + .1 * d, .35, .95); st['fifth'] = clip(st['fifth'] + .15 * d, 0, .6)
        return change
    st = sound['voice']['stack']; layers = list(range(st['layers'])); rng.shuffle(layers)
    usable = [t for t in FRAME_TEXTURES if (t != 10 or 'plain' in st) and (t != 11 or 'blocks' in st)]  # 10/11 need their voice settings
    def swap(k):
        def change(st, fx): st['timbres'][k] = int(rng.choice([t for t in usable if t != st['timbres'][k]]))
        return change
    out = {'brighter': make(bright(1)), 'brighter2': make(bright(2)), 'darker': make(bright(-1)), 'darker2': make(bright(-2)),
           'deeper': make(pitch(-4)), 'deeper2': make(pitch(-7)), 'higher': make(pitch(4)), 'higher2': make(pitch(7)),
           'fuller': make(full(1)), 'thinner': make(full(-1)), 'swap1': make(swap(layers[0])), 'swap2': make(swap(layers[1 % len(layers)]))}
    for name in ('brighter2', 'darker2', 'deeper2', 'higher2'):
        if out[name] == out[name[:-1]]: del out[name]  # the second step hit the range limit: same as the first
    # lead (set above): a body-led parent (grid pool) keeps only body-led variations: fuller / shimmer must not let the top take over
    return {name: v for name, v in out.items() if (v[0] != sound['voice'] or v[1] != sound['fx']) and (not lead or body_rule(v[0]['stack']))}  # a move at its limit changes nothing


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
            if body_rule(s['voice']['stack']) and not body_leads({'voice': voice, 'desc': desc, 'rootHz': voice['stack']['rootHz']}): continue  # measured
            g = gap(s['desc'], desc)
            audible = (abs(m['S'] - s['metrics']['S']) >= BRIGHT_S if name.startswith(('brighter', 'darker'))
                       else True if name.startswith(('deeper', 'higher')) else g >= NEAR)  # a 4-semitone step is always heard (about 0.57 'distinct' steps)
            if audible and g <= FAR: near[vid] = (m, desc)
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
