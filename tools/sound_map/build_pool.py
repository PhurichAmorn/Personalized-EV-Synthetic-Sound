"""Build the app pool: PER sounds per group (diverse, farthest-point on the sound traits). Run variations.py on it next.
  python tools/sound_map/build_pool.py out.json pool.electric.json pool.strings.json ... [--blends old_pool.json]   (per style)
  python tools/sound_map/build_pool.py out.json pool.body.json ... --grid [--exclude id,id]   (per grid cell: deep/middle/high root x dark/bright)
Blends are the old pool's sounds whose layer textures do not make one style. --grid keeps only body-led sounds (body loudest over the whole drive, and measured)."""
import json, sys
import numpy as np
from generate import STYLES, BANDS, GRID_ROOTS, body_rule
from score import PITCHES

PER = 12
LIM = {'S': 1.3, 'R': 0.3, 'F': 0.2}

def style_of(sound):
    layers = sound['voice']['stack']['timbres'][:sound['voice']['stack']['layers']]
    count = sorted(((sum(t in family for t in layers), name) for name, family in STYLES.items()), reverse=True)
    return count[0][1] if 2 * count[0][0] >= len(layers) and count[0][0] > count[1][0] else 'blend'

def traits(sound):
    d = sound['desc']
    return np.array([*d['bands'], d['pitch'], d['inharm'], d['R'], d['F'], d['chorus'], d['vib']], float)

def evolving_ok(sound):
    return 'driveEvolving' in sound and all(sound['driveEvolving'][k] <= LIM[k] for k in LIM)

def body_leads(sound):
    """The body leads over the whole drive (generate.body_rule on its settings) and, measured at full pedal and peak rate, the loudest
    octave band is the band of the body's note."""
    return body_rule(sound['voice']['stack']) and int(np.argmax(sound['desc']['bands'])) == int(np.digitize(sound['rootHz'] * PITCHES['peak'][0], BANDS))

def grid(sounds):
    """Cell per sound: deep / middle / high by root, dark / bright by drive sharpness against the median of that root band."""
    out = {}
    for lo, hi, name in ((0, GRID_ROOTS[0], 'deep'), (*GRID_ROOTS, 'middle'), (GRID_ROOTS[1], 999, 'high')):
        band = [s for s in sounds if lo <= s['rootHz'] < hi]
        if not band: continue
        mid = float(np.median([s['drive']['S'] for s in band]))
        for s in band: out[s['id']] = f"{name}-{'bright' if s['drive']['S'] > mid else 'dark'}"
    return out

def pick(sounds, n):
    """Start at the sound nearest the style's average, then keep adding the one farthest from those taken (Evolving-failing sounds count 30% less)."""
    if len(sounds) <= n: return list(sounds)
    x = np.array([traits(s) for s in sounds]); x = (x - x.mean(0)) / (x.std(0) + 1e-9)
    weight = np.array([1 if evolving_ok(s) else .7 for s in sounds])
    chosen = [int(np.argmin(((x - x.mean(0)) ** 2).sum(1)))]
    while len(chosen) < n:
        gap = np.min([((x - x[i]) ** 2).sum(1) for i in chosen], axis=0) * weight
        gap[chosen] = -1; chosen.append(int(np.argmax(gap)))
    return [sounds[i] for i in sorted(chosen)]

if __name__ == '__main__':
    args = sys.argv[1:]; out = args.pop(0)
    if '--grid' in args:
        args.remove('--grid')
        drop = set(args.pop(args.index('--exclude') + 1).split(',')) if '--exclude' in args else set()  # sounds heard as bad
        if '--exclude' in args: args.remove('--exclude')
        sounds = [s for path in args for s in json.load(open(path))['sounds'] if body_leads(s) and s['id'] not in drop]
        cell = grid(sounds)
        for s in sounds: s['style'], s['cell'] = style_of(s), cell[s['id']]
        names = [f'{r}-{b}' for r in ('deep', 'middle', 'high') for b in ('dark', 'bright')]
        chosen = [s for name in names for s in pick([s for s in sounds if s['cell'] == name], PER)]
        meta = {k: v for k, v in json.load(open(args[0])).items() if k != 'sounds'}
        json.dump({**meta, 'source': 'tools/sound_map build_pool.py --grid: body-led sounds, deep/middle/high x dark/bright', 'sounds': chosen}, open(out, 'w'))
        for name in names:
            mine = [s for s in chosen if s['cell'] == name]
            print(name, len(mine), 'of', sum(s['cell'] == name for s in sounds), 'pass Evolving', sum(evolving_ok(s) for s in mine))
        sys.exit()
    blends = args.pop(args.index('--blends') + 1) if '--blends' in args else None
    if blends: args.remove('--blends')
    pools = [json.load(open(path)) for path in args]
    sounds = []
    for pool in pools:
        for s in pool['sounds']: s['style'] = style_of(s)
        sounds += pick(pool['sounds'], PER)
    if blends:
        old = json.load(open(blends))
        for s in old['sounds']: s['style'] = style_of(s)
        sounds += pick([s for s in old['sounds'] if s['style'] == 'blend'], PER)
    meta = {k: v for k, v in pools[0].items() if k != 'sounds'}
    json.dump({**meta, 'source': 'tools/sound_map build_pool.py: per-style libraries + blends', 'sounds': sounds}, open(out, 'w'))
    for name in [*STYLES, 'blend']:
        mine = [s for s in sounds if s['style'] == name]
        print(name, len(mine), 'pass Evolving', sum(evolving_ok(s) for s in mine))
