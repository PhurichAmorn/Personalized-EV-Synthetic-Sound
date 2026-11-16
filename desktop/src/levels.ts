import { EXTRAS_OFF, plainPartials, type PlainParams } from './plainSource'
import { FX_DEFAULT, type Fx } from './labEngine'
import { drivingSoundTargets } from './drivingSoundMapping'
import { simulatedDrive, SIMULATED_DRIVE_SECONDS } from './simulatedDrive'

/** Level search (experiment/source_search.py LevelDiscovery): a sound is one setting per control.
 * Base: Type x Brightness x Register. Transformation: six controls with 2-3 settings. Everything else is fixed (FIXED_NOTES).
 * Keep level counts in sync with LEVEL_BASE / LEVEL_FX in source_search.py. */
export type LevelRecipe = { version: 2; kind: 'levels'; seed: number
  base: { type: 'strings' | 'choir' | 'glass'; brightness: number; register: number }
  fx: { chorus: number; reverb: number; vibrato: number; follow: number; body: number; tremolo: number } }

// The three types are the blind-tested closest matches to the original Strings, Choir and Glass (2026-11-14).
const TYPES: Record<LevelRecipe['base']['type'], Partial<PlainParams>> = {
  strings: { brightness: .7, softTop: 800, chord: .8 },
  choir: { vowel: .8, vowelShape: .5, brightness: .9, softTop: 1000, chord: 1 },
  glass: { bellModes: 1, brightness: .8, softTop: 4000, chord: 1 },
}
export const REGISTER_HZ = [131, 175, 233]  // deep / middle / high: 5 semitones apart; 131 avoids the chord-pulse fade zone (130-160 Hz)
// Brightness level moves brightness and the soft top together: darker -.25 and x0.7, brighter +.1 and x1.5.
const BRIGHTNESS = [{ add: -.25, top: .7 }, { add: 0, top: 1 }, { add: .1, top: 1.5 }]
export const LEVEL_VALUES = {
  chorus: [0, 1, 2], reverb: [0, .25, .45], vibrato: [0, 3, 6],  // chorus amount, reverb mix (2 s decay), vibrato cents (5.2 Hz)
  follow: [0, 1], body: [0, 4], tremolo: [0, .2],                 // pedal tone off/on, body dB at 450 Hz, tremolo depth at 5 Hz
}
/** Fixed for every search sound: not searched. 0 means off. */
export const SEARCH_FIXED: Fx = { ...FX_DEFAULT, tone: 6000, follow: 0, bodyHz: 450, bodyDb: 0, chorus: 0, reverb: 0, size: 2, tremRate: 5, tremDepth: 0, rasp: 0, vibDepth: 0, vibRate: 5.2 }
const PEDAL_TONE = { tone: 2000, follow: 1 }  // "on": low-pass opens 1-4 kHz with the pedal (off: fixed 6 kHz)

export function levelSound(recipe: LevelRecipe): { plain: PlainParams; fx: Fx } {
  const type = TYPES[recipe.base.type], b = BRIGHTNESS[recipe.base.brightness + 1], f = recipe.fx
  const plain: PlainParams = { ...EXTRAS_OFF, rootHz: REGISTER_HZ[recipe.base.register + 1], brightness: .5, hollow: 0, bell: 0, air: 0, softTop: 1800, chord: 0, ...type }
  plain.brightness = Math.min(1, Math.max(0, plain.brightness + b.add)); plain.softTop = Math.round(plain.softTop * b.top)
  const fx: Fx = { ...SEARCH_FIXED, chorus: LEVEL_VALUES.chorus[f.chorus], reverb: LEVEL_VALUES.reverb[f.reverb], vibDepth: LEVEL_VALUES.vibrato[f.vibrato],
    bodyDb: LEVEL_VALUES.body[f.body], tremDepth: LEVEL_VALUES.tremolo[f.tremolo], ...(f.follow ? PEDAL_TONE : {}) }
  return { plain, fx }
}
export const isLevelRecipe = (recipe: unknown): recipe is LevelRecipe => (recipe as LevelRecipe | null)?.kind === 'levels'

/** Tuning search (experiment/source_search.py TuningDiscovery): a starting sound plus tuning moves; played through tunedSound. */
export type TuningRecipe = { version: 3; kind: 'tuning'; seed: number; motion: Tuning['kind']
  base: Pick<Tuning, 'start' | 'pitch' | 'brightness' | 'character' | 'blend' | 'mix'>; fx: Pick<Tuning, 'movement'> }
export const isTuningRecipe = (recipe: unknown): recipe is TuningRecipe => (recipe as TuningRecipe | null)?.kind === 'tuning'
export const COMFORT_CAP_HZ = 260
/** Octave-band profile of a sound's partials after its own low-pass: the same measure used to compare starting sounds, from the
 * partial list (no audio build, about a millisecond). */
const BANDS = [100, 200, 400, 800, 1600, 3200, 6400, Infinity]
function soundProfile(recipe: LevelRecipe | TuningRecipe) {
  const { plain, fx } = liveSound(recipe), energy = BANDS.map(() => 0)
  for (const { hz, amp } of plainPartials(plain)) energy[BANDS.findIndex(top => hz < top)] += amp * amp / (1 + (hz / fx.tone) ** 4)
  const total = energy.reduce((sum, value) => sum + value, 0) || 1
  return { bands: energy.map(value => Math.sqrt(value / total)), rootHz: plain.rootHz }
}
/** How far apart two sounds are: spectrum 0 (same) .. 1, and pitch gap in semitones. */
export function pairDistance(a: LevelRecipe | TuningRecipe, b: LevelRecipe | TuningRecipe) {
  const p = soundProfile(a), q = soundProfile(b)
  return { spectrum: Math.hypot(...p.bands.map((value, i) => value - q.bands[i])) / Math.SQRT2, semitones: Math.abs(12 * Math.log2(q.rootHz / p.rootHz)) }
}
// A pair is too similar under 0.25 on the spectrum with less than 5 semitones of pitch gap (2026-11-16 session: 0.11-0.13 pairs sounded the same).
export const tooSimilar = (a: LevelRecipe | TuningRecipe, b: LevelRecipe | TuningRecipe) => { const d = pairDistance(a, b); return d.spectrum < .25 && d.semitones < 5 }
/** Plain source, effects and motion for any live-built search sound (level or tuning recipe). */
export function liveSound(recipe: LevelRecipe | TuningRecipe) {
  if (!isTuningRecipe(recipe)) return { ...levelSound(recipe), mode: 'rise' as const, travel: 1 }
  const { plain, fx, travel } = tunedSound({ kind: recipe.motion, ...recipe.base, ...recipe.fx }, COMFORT_CAP_HZ)
  return { plain, fx, travel, mode: recipe.motion }
}

/** Starting sounds for the next search version (2026-11-14; minor 7th chord added to five of them after listening, 2026-11-15). Each is its own full design (base + transformation), made to differ
 * from every other in several ways at once; nothing is shared by rule and everything stays tunable later.
 * Split: the base sound owns colour, notes, structure and register; the transformation owns space and motion only
 * (Space, Vibrato, Tremolo; tone follows pedal fixed on; body resonance dropped: it overlapped Vowel and Brightness).
 * Vibrato "on" = 6 cents at 5.2 Hz for now (amount to be chosen by ear); tremolo "on" = .2 at 5 Hz. */
const SPACE = { small: { chorus: 1, reverb: .25, size: 1.2 }, large: { chorus: 2, reverb: .4, size: 2.5 } }
const motion = (space: 'small' | 'large', vibrato: boolean, tremolo: boolean): Fx => ({ ...SEARCH_FIXED, ...SPACE[space], tone: 2000, follow: 1, bodyDb: 0, vibDepth: vibrato ? 6 : 0, tremDepth: tremolo ? .2 : 0 })
type StartingSound = { id: string; name: string; character: string; plain: Partial<PlainParams>; fx: Fx; settings: string }
// Six starting sounds after the starting sound test (2026-11-15): Growl, Sci-fi sweep, Pulse and Night drive dropped by ear;
// Pure tone and Electric whine changed until kept. Pairs measure 0.2-0.86 apart on the octave-band spectrum (Electric whine - Dark ambience closest).
export const STARTING_SOUNDS: StartingSound[] = [
  { id: 'warm', name: 'Warm pad', character: 'fused notes with a soft chord, dark and low', plain: { rootHz: 131, brightness: .65, softTop: 800, chord: .8, chordType: 2 }, fx: motion('small', true, false), settings: '131 Hz · minor 7th chord · dark · space small · vibrato' },
  // Voice, 2nd version: the stretch and minor 7th made the first one sound like Turbine; now an open chord, no stretch.
  { id: 'voice', name: 'Voice', character: 'soft choir "ooh-aah" on an open chord (5th + octave), no stretch', plain: { rootHz: 147, vowel: 1, vowelShape: .35, brightness: .5, softTop: 1400, chord: .7, chordType: 3 },
    fx: { ...motion('large', true, false), tone: 2500 }, settings: '147 Hz · ooh-aah vowel · 5th + octave · space large · vibrato' },
  { id: 'sparkle', name: 'Sparkle', character: 'separate bright bell tones, high', plain: { rootHz: 233, bellModes: 1, brightness: .55, softTop: 3000, chord: .6, chordType: 2 }, fx: motion('large', false, false), settings: '233 Hz · bell tones · minor 7th chord · gentle top · space large' },
  // Pure tone, 2nd try: "very basic" on its own, so a soft fifth + octave and a large space around the clean tone.
  { id: 'pure', name: 'Pure tone', character: 'clean, soft whistle-like tone with a faint fifth and octave, in a large space', plain: { rootHz: 196, brightness: .15, softTop: 3000, chord: .35, chordType: 3 },
    fx: { ...motion('large', true, false), tone: 6000 }, settings: '196 Hz · near-pure tone · faint 5th + octave · space large · vibrato' },
  // Electric whine, 3rd try: "too high" at 7.5x and still at 5.5x; whine now 4x (top about 1 kHz) with a darker filter.
  { id: 'whine', name: 'Electric whine', character: 'thin hum with a clear high whine that climbs with speed, motor-like', plain: { rootHz: 98, fundamental: .6, brightness: .25, softTop: 700, chord: 0, whine: .6, whineRatio: 4 },
    fx: { ...motion('small', false, false), tone: 2000 }, settings: '98 Hz hum · whine 4x, softer · no chord · space small' },
  // Dark ambience (2026-11-15, replaces Deep metal): chosen on the phone test page as 85% Dark ambience + 15% Ghost choir.
  { id: 'dark', name: 'Dark ambience', character: 'bleak low drone, distant metal, a faint "ooh", huge space that slowly breathes', plain: { rootHz: 76, chord: .69, chordType: 3, bell: .36, vowel: .12, vowelShape: 0, detune: .52, lowDetune: 1, brightness: .47, softTop: 1630 },
    fx: { ...motion('large', false, false), reverb: .55, size: 6, tone: 960, res: 3.9, drift: 1 }, settings: '76 Hz · bleak chord (5th + octave) · distant metal · faint ooh · detuned low end · huge space · filter drift' },
]
// Retired starting sounds: kept only so saved sessions that used them still play in Sound trace.
const RETIRED_SOUNDS: StartingSound[] = [
  { id: 'turbine', name: 'Turbine', character: '', plain: { rootHz: 110, whine: .7, whineRatio: 4.5, fundamental: .5, brightness: .5, softTop: 900, chord: .6, chordType: 2 }, fx: motion('small', false, true), settings: '' },
  { id: 'digital', name: 'Digital', character: '', plain: { rootHz: 196, hollow: .7, brightness: .3, softTop: 1200, chord: .7, chordType: 2, bell: .9 }, fx: motion('large', false, false), settings: '' },
  { id: 'night', name: 'Night drive', character: '', plain: { rootHz: 175, brightness: .7, hollow: .15, softTop: 3000, chord: 1, chordType: 2, detune: .7 }, fx: { ...motion('large', false, false), tone: 1500, res: 8, pump: 1, tremRate: 1.75, tremDepth: .25 }, settings: '' },
]
const findSound = (id: string) => [...STARTING_SOUNDS, ...RETIRED_SOUNDS].find(sound => sound.id === id)!
export const CANDIDATE_SOUNDS = STARTING_SOUNDS  // Sound Lab 04 plays the current starting sounds
export const FAIR_FX: Fx = { ...SEARCH_FIXED, chorus: 1, reverb: .25, size: 1.2, tone: 2000, follow: 1, bodyDb: 0, tremDepth: 0, vibDepth: 0 }

/** Tuning (2026-11-15, 2nd version): how a session moves from a starting sound. Borrow and Climb dropped (too small to hear, and
 * Blend covers Borrow). Every change was made bigger after measuring: most were 0.1-0.2 apart on the octave-band spectrum, while the
 * starting sounds are 0.2-0.86 apart. Sizes are checked by ear in Sound Lab 05 (Change test) before the search trusts them.
 * Source: Pitch (4 semitones per step), Brightness, Character (the sound's own signature off / doubled), Blend with another sound (1/3, 1/2, 2/3).
 * Transformation: Rising or Evolving (chosen first) only. Movement (wobble/pulse/pump) dropped after the change test (small / can't hear);
 * Space always large; comfort cap fixed. */
export type Tuning = { kind: 'rise' | 'evolving'; start: string; pitch: number; brightness: number; character: number
  blend: string | null; mix: number; movement: 'still' | 'wobble' | 'pulse' | 'pump' }
export const TUNING_DEFAULT: Tuning = { kind: 'rise', start: 'warm', pitch: 0, brightness: 0, character: 0, blend: null, mix: .5, movement: 'still' }
export const PITCH_STEP = 8  // semitones per pitch step, one step each way (change test: 4 sounded small, 8 clear)
// Brightness side not offered for a sound (change test: small). Keep in sync with TUNING_LIMITS in source_search.py.
export const NO_BRIGHTNESS: Record<string, number> = { pure: -1, sparkle: 1 }
export const BLEND_MIX = [1 / 2]  // one blend: 1/3, 1/2 and 2/3 all sounded clear, so the extra amounts only cost pairs
// Character less / more: the sound's own signature off / pushed further.
// A side is left out where the change test found it small (keep in sync with TUNING_LIMITS in source_search.py).
export const CHARACTER: Record<string, { label: string; less?: Partial<PlainParams>; more?: Partial<PlainParams> }> = {
  warm: { label: 'chord + richness', less: { chord: 0 } },  // more: small even with detune .9
  voice: { label: 'vowel', less: { vowel: 0 }, more: { vowel: 1, vowelShape: .7 } },  // more = open, brighter "aah-eh"
  sparkle: { label: 'upper bell tones', more: { fundamental: .2, softTop: 6000 } },  // less: small
  pure: { label: 'fifth + octave shimmer' },  // less and more both small
  whine: { label: 'whine', less: { whine: 0 } },  // more: small
  dark: { label: 'ghost voice + metal', more: { vowel: .5, bell: .8 } },  // less: small
  turbine: { label: 'whine level', less: { whine: .35 }, more: { whine: 1 } }, digital: { label: 'chord stretch', less: { bell: .5, hollow: .5 }, more: { bell: 1, hollow: .9 } },
  night: { label: 'detune spread', less: { detune: .35 }, more: { detune: 1 } },  // retired sounds: saved sessions only
}
const full = (p: Partial<PlainParams>): PlainParams => ({ ...EXTRAS_OFF, rootHz: 175, brightness: .5, hollow: 0, bell: 0, air: 0, softTop: 1800, chord: 0, ...p })
export const startPlain = (id: string) => full(findSound(id).plain)
// Mix towards b: pitch on a log scale; on/off settings (bell type, chord type) from the nearer side; whine and vowel shape from the side that has them.
export function blendPlain(a: PlainParams, b: PlainParams, mix = .5): PlainParams {
  const out = { ...a }
  for (const key of Object.keys(a) as (keyof PlainParams)[]) out[key] = a[key] + (b[key] - a[key]) * mix
  const near = mix < .5 ? a : b
  out.rootHz = Math.round(a.rootHz * (b.rootHz / a.rootHz) ** mix); out.bellModes = mix === .5 ? a.bellModes : near.bellModes
  out.whineRatio = a.whine ? (b.whine ? out.whineRatio : a.whineRatio) : b.whineRatio
  out.vowelShape = a.vowel ? (b.vowel ? out.vowelShape : a.vowelShape) : b.vowelShape
  out.chordType = mix === .5 ? (a.chord >= b.chord ? a.chordType : b.chordType) : near.chordType
  out.lowDetune = near.lowDetune
  return out
}
const peakRates = new Map<string, number>()
/** Highest playback rate on the 22 s drive (the note at the top = rootHz x this). */
export function peakRate(kind: Tuning['kind'], travel: number) {
  const key = kind + travel
  if (!peakRates.has(key)) {
    let top = 0
    for (let t = 0; t < SIMULATED_DRIVE_SECONDS; t += .1) top = Math.max(top, drivingSoundTargets(simulatedDrive(t), false, 'exponential', kind, travel).rate)
    peakRates.set(key, top)
  }
  return peakRates.get(key)!
}
export function tunedSound(t: Tuning, peakHz: number) {
  let plain = startPlain(t.start)
  if (t.blend) plain = blendPlain(plain, startPlain(t.blend), t.mix ?? .5)
  if (t.character) plain = { ...plain, ...CHARACTER[t.start][t.character < 0 ? 'less' : 'more'] }
  if (t.brightness) {
    // Darker: -.35, soft top x0.4 (floor 300 Hz). Brighter: +.3, soft top x2 but at most 3.5 kHz: above that it sounded harsh / noisy.
    plain.brightness = Math.min(1, Math.max(0, plain.brightness + (t.brightness > 0 ? .3 : -.35)))
    plain.softTop = Math.round(t.brightness > 0 ? Math.max(plain.softTop, Math.min(3500, plain.softTop * 2)) : Math.max(300, plain.softTop * .4))
  }
  plain.rootHz = Math.round(Math.min(350, Math.max(40, plain.rootHz * 2 ** (PITCH_STEP * t.pitch / 12))))
  // Each sound keeps its own filter (tone, resonance); Movement replaces its vibrato / tremolo / pump.
  const own = findSound(t.start).fx
  const fx: Fx = { ...SEARCH_FIXED, ...SPACE.large, tone: own.tone, res: own.res, drift: own.drift, follow: 1, bodyDb: 0, rasp: 0, peakHz,
    vibDepth: t.movement === 'wobble' ? 12 : 0,  // 12 cents: 6 was too subtle
    tremDepth: t.movement === 'pulse' ? .2 : t.movement === 'pump' ? .25 : 0,
    pump: t.movement === 'pump' ? 1 : 0, tremRate: t.movement === 'pump' ? 1.75 : SEARCH_FIXED.tremRate }
  const travel = 1, top = plain.rootHz * peakRate(t.kind, travel)
  return { plain, fx, travel, top, capped: top > peakHz }
}

/** Synth tries (Sound Lab 04, 2026-11-15): Night drive's additions on the other starting sounds, one at a time or together.
 * Minor 7th needs a chord, so it raises the chord to at least .6. */
export const SYNTH_TRIES: { id: string; label: string; plain: (p: Partial<PlainParams>) => Partial<PlainParams>; fx: Partial<Fx> }[] = [
  { id: 'asis', label: 'As is', plain: () => ({}), fx: {} },
  { id: 'detune', label: '+ Detune', plain: () => ({ detune: .6 }), fx: {} },
  { id: 'minor7', label: '+ Minor 7th', plain: p => ({ chordType: 2, chord: Math.max(p.chord ?? 0, .6) }), fx: {} },
  { id: 'both', label: '+ Detune + Minor 7th', plain: p => ({ detune: .6, chordType: 2, chord: Math.max(p.chord ?? 0, .6) }), fx: {} },
  { id: 'sing', label: '+ Singing filter', plain: () => ({}), fx: { res: 8 } },
]
