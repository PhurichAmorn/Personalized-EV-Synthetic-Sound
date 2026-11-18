"""Build the app pool from per-style libraries: PER sounds per style (diverse, farthest-point on the sound traits), plus the best blends.
  python tools/sound_map/build_pool.py out.json pool.electric.json pool.strings.json ... [--blends old_pool.json]
Blends are the old pool's sounds whose layer textures do not make one style. Writes the pool file; run variations.py on it next."""
import json, sys
import numpy as np
from generate import STYLES

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
