"""Building-block sounds (2026-11-21): a sound is a body texture, a top texture (the 3 upper octave layers), a top level, synth knobs,
pitch, brightness, space and movement. build() turns one into the stack voice + effects the app already plays live
(desktop/src/mapVoice.ts 'stack', levels.ts MapRecipe v5), so the app needs no new synth code.

Chosen by ear (listening pages 2026-11-21): 4 layers (more layers were heard only as 'wider'); textures that sounded alike were merged
(strings / strings pad / cello / synth -> Synth; hollow dropped); Soft body (plain sine) because a strong top covers a soft body anyway
(Plain and Synth bodies under a Glass top: gap .31). Synth knobs kept only where heard: buzz (2 steps), chord, bell and vowel (at full
setting only). Brightness is the outer low-pass, set per sound from the measured table (tools/sound_map/block_sweep.py), not a fixed amount.
"""
import json
from pathlib import Path

BODIES = {'soft': 0, 'blocks': 11, 'electric': 9, 'glass': 3}  # stackVoice.ts STACK_TEXTURES index
TOPS = {'glass': 3, 'electric': 9, 'blocks': 11, 'plain': 0, 'synth': 10, 'bell': 10, 'moody': 10}  # 'bell' = Bell synth: the synth voice with glass bell modes;
# 'moody' = the synth voice on a minor chord with ensemble (detuned copies) on the upper layers: fixed settings, no synth knobs
TOP_LEVELS = {'soft': .35, 'medium': .49, 'strong': .8}  # stack 'fall': each layer's level relative to the one below
PITCHES = [round(75 * 2 ** (k * 4 / 12), 1) for k in (-2, -1, 0, 1, 2)]  # 4-semitone steps (always heard), 47-119 Hz inside 41-130
CUTOFFS = [800, 1500, 2800, 5200]  # outer low-pass points measured by the sweep; brightness between them is interpolated
SPACES = {'dry': {'reverb': 0, 'size': 1.2}, 'large': {'reverb': .4, 'size': 2.5}}  # levels.ts SPACE; medium dropped: medium vs large sounded the same (2026-11-21)
MOVEMENTS = {'still': 0, 'wobble': 6}  # vibrato cents at 5.2 Hz (levels.ts motion()); not searched: wobble was hard to hear (change test 2026-11-15)
BUZZ = [{}, {'fundamental': .4, 'brightness': .65}, {'fundamental': .1, 'brightness': .85}]
BUZZ_STEPS = (0, 2)  # the session moves buzz off <-> strong only; level 1 (some) is never offered
BRIGHT_GRID = (.25, .4, .55, .7, .85)  # brightness targets (acum) of the benchmark's ground-truth pool (tools/benchmark_blocks.py truth())
CHORDS = {'off': {}, 'on': {'chord': .8, 'chordType': 1, 'width': 1}}  # minor chord; chord type alone was not heard (major vs minor sounded the same, 2026-11-21)

_OFF = dict(vowel=0, vowelShape=.5, fundamental=1, whine=0, whineRatio=8.75, bellModes=0, detune=0, chordType=0, lowDetune=0, lowCut=0, width=0)
SYNTH = {**_OFF, 'brightness': .45, 'hollow': .2, 'bell': 0, 'air': 0, 'softTop': 1800, 'chord': 0}
BELL = {**SYNTH, 'hollow': 1, 'bell': 1, 'bellModes': 1}  # 'Bell synth': heard as a light electric shimmer (knob test 2026-11-21)
MOODY = {**SYNTH, **CHORDS['on']}
ENSEMBLE = 12  # cents, Moody top only (knob test 2026-11-22: ensemble good on Synth, not on Glass; resonance, drift and pulse not heard)
# Blocks voice from pool sound f41ca6c825 with its noise removed (noise mix .55 was heard as weird noise, 2026-11-21).
BLOCKS = {'shape': {'rootRatio': .9843, 'slope': .8841, 'evenGain': .1779, 'peak1Hz': 343.07, 'peak1Gain': 2.114, 'peak2Hz': 2596.9, 'peak2Gain': .2036,
                    'peakWidth': .6725, 'cutoff': 464.1, 'inharm': .0053, 'fmMix': 0, 'fmRatio': 6.461, 'fmIndex': 2.461, 'noiseMix': 0,
                    'noiseCenter': 3711.2, 'noiseWidth': 243.8, 'amRate': 2.681, 'amDepth': 0, 'lope': .8296, 'drive': 0},
          'controls': {'body': .5, 'character': .5, 'ensemble': .104, 'movement': 0}}
# Roles and resonance from pool sound 1b8f116b7e (body-led grid sound): the body keeps leading while the top opens with the drive.
TREND = {'rest': [.9206, .3494, .9367], 'full': [.9953, .8371, .8221], 'mix': [.9565, .3234, .4426]}

DEFAULT = {'body': 'soft', 'top': 'glass', 'level': 'medium', 'buzz': 0, 'chord': 'off', 'bell': False, 'vowel': False,
           'pitch': 2, 'brightness': .5, 'space': 'large', 'movement': 'still', 'partner': None}
# Partner: a second style on the highest layer (layer 4) only, kept where heard as good (mixed-top tests 1-2, 2026-11-22). Two layers sounded
# nice on Moody but one keeps each style's own character; Moody + Electric, Digital + Glass were worse; Electric's partners and Synth pad +
# Digital were not heard. A sound has one synth voice, so a synth-voice main top only takes non-synth partners.
PARTNERS = {'moody': ('glass',), 'glass': ('moody', 'synth'), 'blocks': ('bell',), 'bell': ('glass', 'blocks'), 'plain': ('glass', 'moody'), 'synth': ('glass',)}
PARTNER_LAYER = 3  # timbres index of layer 4
# Starts: the styles kept by ear (style auditions 2026-11-21), written as blocks. Pure is the Plain top (sine layers, 0.34 acum).
# Four starts, one for each style heard as different while driving (2026-11-22 sessions): Moody and Synth pad were heard as near-alike
# (the same voice and chord, Moody adds ensemble), and so were Pure and Digital. Synth pad and Digital stay reachable by changes.
# The octave-band gap misses this (Pure-Digital .62, while Glass-Synth pad .53 sounds clearly different), so the choice is by ear.
STARTS = {'glass': {'top': 'glass'}, 'pure': {'top': 'plain'}, 'bell': {'top': 'bell'}, 'moody': {'top': 'moody'}}
NAMES = {'glass': 'Glass', 'electric': 'Electric', 'blocks': 'Blocks', 'plain': 'Plain', 'synth': 'Synth', 'bell': 'Bell synth', 'moody': 'Moody', 'soft': 'Soft'}


def full(sound):
    """A block sound with every field (defaults filled in)."""
    return {**DEFAULT, **sound}


def has_synth(sound):
    return full(sound)['top'] in ('synth', 'bell')


def synth_settings(sound):
    s = full(sound)
    if s['top'] == 'moody': return dict(MOODY)
    if not has_synth(s) and s['partner'] in ('synth', 'bell', 'moody'):  # a synth-voice partner on a non-synth top brings its own settings
        return synth_settings({'top': s['partner'], 'chord': 'on' if s['partner'] == 'synth' else 'off'})
    base = BELL if s['top'] == 'bell' else SYNTH
    knobs = {**BUZZ[s['buzz']], **CHORDS[s['chord']], **({'bell': 1} if s['bell'] else {}), **({'vowel': 1} if s['vowel'] else {})}
    return {**base, **knobs}


def build(sound, cutoff):
    """Block sound + outer low-pass (Hz) -> (voice, fx) as mapVoice.ts / drive.py play them."""
    s = full(sound)
    top = TOPS[s['top']]
    timbres = [BODIES[s['body']], top, top, top, top]
    if s['partner']: timbres[PARTNER_LAYER] = TOPS[s['partner']]
    pad = s['chord'] != 'off' or 'moody' in (s['top'], s['partner']) or (s['partner'] == 'synth' and not has_synth(s))
    stack = {'rootHz': PITCHES[s['pitch']], 'layers': 4, 'timbres': timbres, 'fall': TOP_LEVELS[s['level']],
             'depth': .45 if pad else .2,  # a chord pad breathes more slowly and deeply (Moody / Synth starts)
             'seed': 0, 'fifth': 0, 'shimmer': 0, 'spread': .3, 'peakHz': 99.34, 'peakDb': 3.47, 'cutoff': cutoff, 'twinkle': 0,
             'trend': TREND, 'plain': synth_settings(s), 'blocks': BLOCKS, **({'ensemble': ENSEMBLE} if 'moody' in (s['top'], s['partner']) else {})}
    fx = {'tone': cutoff, 'res': 2.165, 'tremDepth': 0, 'tremRate': .335, 'chorus': 0, 'vibDepth': MOVEMENTS[s['movement']], 'vibRate': 5.2,
          'bodyHz': 562.4, 'bodyDb': 0, 'pump': 0, 'drift': 0, 'follow': 1, 'gain': 1, **SPACES[s['space']]}
    return {'kind': 'stack', 'stack': stack}, fx


def describe(sound):
    """Plain words, shown to the listener: 'Soft body · Glass top (medium) · 75 Hz · chord minor'."""
    s = full(sound)
    words = [f"{NAMES[s['body']]} body", f"{NAMES[s['top']]} top ({s['level']})" + (f" + {NAMES[s['partner']]} on top layer" if s['partner'] else ''),
             f"{PITCHES[s['pitch']]:g} Hz", f"brightness {s['brightness']:.2f}"]
    if has_synth(s):
        words += [w for w in (('buzz ' + ('some', 'strong')[s['buzz'] - 1]) if s['buzz'] else '', 'chord' if s['chord'] != 'off' else '',
                              'bell' if s['bell'] else '', 'vowel' if s['vowel'] else '') if w]
    return ' · '.join(words + [f"{s['space']} space", s['movement']])


def key(sound):
    """Table key of the parts the sweep measured (brightness and space are set on top)."""
    s = full(sound)
    synth = f"|b{s['buzz']}c{s['chord']}{'B' if s['bell'] else ''}{'V' if s['vowel'] else ''}" if has_synth(s) else ''
    return f"{s['body']}|{s['top']}|{s['level']}|{s['pitch']}|{s['movement']}{synth}" + (f"|p{s['partner']}" if s['partner'] else '')


def sweep_items():
    """Every block combination the sweep measures: [(key, sound)]. Main grid with synth knobs off; synth knobs on the Soft body at 3 pitches
    and on every body at the middle pitch (medium top). ponytail: other pitches and levels use the
    nearest measured entry; measure them too if a session sound fails its final check."""
    out = {}
    def add(x): out[key(x)] = x
    for b in BODIES:
        for t in TOPS:
            for lv in TOP_LEVELS:
                for p in range(len(PITCHES)): add({'body': b, 'top': t, 'level': lv, 'pitch': p})
    for t, ps in PARTNERS.items():  # partners at 3 pitches (knobs off), as the synth knobs; other pitches and knobs use the nearest entry
        for p in ps:
            for b in BODIES:
                for lv in TOP_LEVELS:
                    for pi in (0, 2, 4): add({'body': b, 'top': t, 'level': lv, 'pitch': pi, 'partner': p})
    for t in ('synth', 'bell'):
        for buzz in (0, 2):  # the session moves buzz off <-> strong only
            for ch in CHORDS:
                for bell in (False, True):
                    for vowel in (False, True):
                        for p in (0, 2, 4): add({'top': t, 'buzz': buzz, 'chord': ch, 'bell': bell, 'vowel': vowel, 'pitch': p})
                        for b in BODIES:  # the other bodies at the middle pitch: a body can cover a knob (buzz under a Blocks body, heard 2026-11-21)
                            add({'body': b, 'top': t, 'buzz': buzz, 'chord': ch, 'bell': bell, 'vowel': vowel, 'pitch': 2})
    return list(out.items())


TABLE = Path(__file__).with_name('sound_blocks_table.json')


def load_table(path=TABLE):
    return json.loads(Path(path).read_text()) if Path(path).exists() else None


def nearest_entry(table, sound):
    """The measured entry for this sound, else the closest measured one (same top, then fewest differing fields)."""
    k = key(sound)
    if k in table['entries']: return table['entries'][k]
    s = full(sound)
    # Rows not measured yet stand in for their closest relative: a partner mix for its main style alone, Moody for Synth with the chord
    # (the same voice; Moody adds ensemble). ponytail: estimates until the sweep adds the real rows.
    if s['partner']: return nearest_entry(table, {**s, 'partner': None})
    if s['top'] == 'moody': return nearest_entry(table, {**s, 'top': 'synth', 'chord': 'on'})
    def cost(entry_key):
        e = dict(zip(('body', 'top', 'level', 'pitch', 'movement'), entry_key.split('|')[:5]))
        return (e['top'] != s['top']) * 10 + (e['body'] != s['body']) + (e['level'] != s['level']) + abs(int(e['pitch']) - s['pitch']) + (e['movement'] != s['movement']) * 2 \
            + (0 if entry_key.split('|', 5)[5:] == k.split('|', 5)[5:] else 3)
    return table['entries'][min(table['entries'], key=cost)]


def cutoff_for(entry, target):
    """Outer low-pass for a target sharpness (acum): interpolated in log cutoff between the measured points, clamped to the range."""
    import math
    pts = sorted(zip(entry['S'], CUTOFFS))
    if target <= pts[0][0]: return pts[0][1]
    if target >= pts[-1][0]: return pts[-1][1]
    for (s0, c0), (s1, c1) in zip(pts, pts[1:]):
        if s0 <= target <= s1:
            u = 0 if s1 == s0 else (target - s0) / (s1 - s0)
            return round(math.exp(math.log(c0) + u * (math.log(c1) - math.log(c0))))


MIN_GAP = .35  # octave-band gap below which a change is not offered: .15-.31 were not heard, .34-.37 just heard (listening pages 2026-11-21)


def gap(a, b):
    """Octave-band spectrum gap, as the listening pages measured it: RMS of the dB differences / 10."""
    return round((sum((x - y) ** 2 for x, y in zip(a, b)) / len(a)) ** .5 / 10, 3)


def point(cutoff):
    """Index of the measured low-pass point that stands for this cutoff: the nearest at or above it, so brighter is never assumed safe."""
    return min(range(len(CUTOFFS)), key=lambda j: (CUTOFFS[j] < cutoff, abs(CUTOFFS[j] - cutoff)))


def safe(entry, cutoff, modes=('rise',)):
    """Does the measured entry pass the drive check at this cutoff in these modes?"""
    return all(entry['pass'][point(cutoff)][m] for m in modes)


def sharpness_at(entry, cutoff):
    """Cruise sharpness at a cutoff, interpolated in log cutoff between the measured points."""
    import math
    x = math.log(min(max(cutoff, CUTOFFS[0]), CUTOFFS[-1]))
    for (c0, s0), (c1, s1) in zip(zip(CUTOFFS, entry['S']), zip(CUTOFFS[1:], entry['S'][1:])):
        if math.log(c0) <= x <= math.log(c1): return s0 + (x - math.log(c0)) / (math.log(c1) - math.log(c0)) * (s1 - s0)
    return entry['S'][-1]


MAX_GAIN_DB = 12  # never boost or cut a sound by more than this (as loudness.py)


def gain_for(table, entry, cutoff):
    """Playback gain (linear) that brings this sound to the table's loudness target (median), from its loudness at this low-pass
    (interpolated in log cutoff, as sharpness_at); 1 when the table has no loudness yet. Sones double per +10 dB."""
    if 'sones' not in entry or not table.get('loudness'): return 1.
    import math
    n = sharpness_at({'S': entry['sones']}, cutoff)
    db = max(-MAX_GAIN_DB, min(MAX_GAIN_DB, 10 * math.log2(table['loudness']['target_sones'] / max(n, 1e-6))))
    return round(10 ** (db / 20), 4)

if __name__ == '__main__':  # self-check
    items = sweep_items()
    assert len({k for k, _ in items}) == len(items)
    v, fx = build({'top': 'synth', 'chord': 'on'}, 2000)
    assert v['stack']['timbres'][1] == 10 and v['stack']['plain']['chordType'] == 1 and fx['tone'] == 2000
    assert gap([0] * 9, [-3.5] * 9) == .35
    assert build({'top': 'bell'}, 800)[0]['stack']['plain']['bellModes'] == 1
    v = build({'top': 'glass', 'partner': 'moody'}, 2000)[0]['stack']; assert v['timbres'] == [0, 3, 3, 10, 3] and v['ensemble'] == ENSEMBLE and v['plain']['chord'] == .8
    assert all(t not in ('synth', 'bell', 'moody') or not set(ps) & {'synth', 'bell', 'moody'} for t, ps in PARTNERS.items())  # one synth voice
    e = {'S': [.3, .4, .5, .6], 'pass': [{'rise': True}] * 3 + [{'rise': False}]}
    assert cutoff_for(e, .45) and 1500 < cutoff_for(e, .45) < 2800 and cutoff_for(e, .1) == 800 and cutoff_for(e, .9) == 5200
    assert safe(e, 2000) and not safe(e, 5000) and abs(sharpness_at(e, 1500) - .4) < 1e-9
    t = {'loudness': {'target_sones': 9.}}
    assert gain_for(t, {'sones': [9.] * 4}, 2000) == 1 and abs(gain_for(t, {'sones': [4.5] * 4}, 2000) - 10 ** .5) < 1e-3  # half as loud: +10 dB
    assert gain_for({}, e, 2000) == 1 and gain_for(t, {'sones': [.01] * 4}, 2000) == round(10 ** .6, 4)  # no loudness: 1; capped at +12 dB
    print(len(items), 'sweep items; self-check OK;', describe({'top': 'synth', 'chord': 'on'}))


def knob_settings(top):
    """Every synth-knob setting a top has: 16 on the Synth and Bell tops (buzz x chord x bell x vowel), one (all off) on the others."""
    if top not in ('synth', 'bell'): return [{'buzz': 0, 'chord': 'off', 'bell': False, 'vowel': False}]
    return [{'buzz': bz, 'chord': ch, 'bell': bl, 'vowel': vw} for bz in BUZZ_STEPS for ch in CHORDS for bl in (False, True) for vw in (False, True)]


def combos(table):
    """Every combination body x top x level x pitch x brightness step x partner x knob setting, as [(blocks, passes the drive check)];
    a passing sound carries the brightness the table reaches (several steps can reach the same one, see pool)."""
    import itertools
    out = []
    for body, top, lv, pi, br in itertools.product(BODIES, TOPS, TOP_LEVELS, range(len(PITCHES)), BRIGHT_GRID):
        for partner in (None, *PARTNERS.get(top, ())):
            for knobs in knob_settings(top):
                s = full({'body': body, 'top': top, 'level': lv, 'pitch': pi, 'brightness': br, 'partner': partner, **knobs})
                entry = nearest_entry(table, s); cutoff = cutoff_for(entry, br); ok = safe(entry, cutoff)
                if ok: s['brightness'] = round(sharpness_at(entry, cutoff), 2)
                out.append((s, ok))
    return out


def pool(table):
    """The sounds the session can reach (the benchmark's ground truth): the combinations that pass the drive check, each distinct sound once."""
    seen, out = set(), []
    for s, ok in combos(table):
        k = key(s) + f"|{s['brightness']}"
        if ok and k not in seen: seen.add(k); out.append(s)
    return out


def summary(table):
    """How big the space is, for the Sound Lab page: parameter levels, then the funnel free product -> valid combinations -> pass the drive check -> distinct sounds, and a row per top."""
    rows, per_top, seen = combos(table), {}, set()
    for s, ok in rows:
        t = per_top.setdefault(s['top'], {'valid': 0, 'safe': 0, 'distinct': 0}); t['valid'] += 1; t['safe'] += ok
        k = key(s) + f"|{s['brightness']}"
        if ok and k not in seen: seen.add(k); t['distinct'] += 1
    knob_n = max(len(knob_settings(t)) for t in TOPS); partner_n = max(len(PARTNERS.get(t, ())) for t in TOPS) + 1
    free = len(BODIES) * len(TOPS) * len(TOP_LEVELS) * len(PITCHES) * len(BRIGHT_GRID) * partner_n * knob_n
    return {'parameters': [['Body', len(BODIES), ', '.join(BODIES)], ['Top texture', len(TOPS), ', '.join(TOPS)], ['Top level', len(TOP_LEVELS), ', '.join(TOP_LEVELS)],
                           ['Pitch', len(PITCHES), ' / '.join(f'{p:g}' for p in PITCHES) + ' Hz'], ['Brightness', len(BRIGHT_GRID), ' / '.join(f'{b:g}' for b in BRIGHT_GRID) + ' acum'],
                           ['Partner', partner_n, 'none, or 1-2 depending on the top'], ['Synth knobs', knob_n, 'buzz (off/strong) x chord x bell x vowel, Synth and Bell tops only']],
            'free': free, 'valid': len(rows), 'safe': sum(ok for _, ok in rows), 'distinct': len(seen),
            'tops': [{'top': t, 'partners': len(PARTNERS.get(t, ())) + 1, 'knobs': len(knob_settings(t)), **per_top[t]} for t in TOPS]}
