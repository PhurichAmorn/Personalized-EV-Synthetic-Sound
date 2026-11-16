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
  base: Pick<Tuning, 'start' | 'variant' | 'pitch' | 'brightness' | 'character' | 'blend' | 'mix'>; fx: Pick<Tuning, 'movement'> }
export const isTuningRecipe = (recipe: unknown): recipe is TuningRecipe => (recipe as TuningRecipe | null)?.kind === 'tuning'
export const COMFORT_CAP_HZ = 260
const PITCH_CEILING_HZ = 245  // = PITCH_CEILING_HZ in source_search.py: a root above this sits at the comfort cap for most of the drive
/** Octave-band profile of a sound's partials after its own low-pass: the same measure used to compare starting sounds, from the
 * partial list (no audio build, about a millisecond). */
const BANDS = [100, 200, 400, 800, 1600, 3200, 6400, Infinity]
function soundProfile(recipe: LevelRecipe | TuningRecipe) {
  // Measured where the drive spends most time: a root above PITCH_CEILING_HZ is pulled down to it by the comfort cap, so compare there.
  const { plain, fx } = liveSound(recipe), energy = BANDS.map(() => 0), shift = Math.min(1, PITCH_CEILING_HZ / plain.rootHz)
  for (const { hz, amp } of plainPartials(plain)) energy[BANDS.findIndex(top => hz * shift < top)] += amp * amp / (1 + (hz * shift / fx.tone) ** 4)
  const total = energy.reduce((sum, value) => sum + value, 0) || 1
  return { bands: energy.map(value => Math.sqrt(value / total)), rootHz: plain.rootHz * shift }
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
  // Pad family face, 2026-11-16: Cinematic pad (merged with the pad family; the listener found it "similar to Strings, but better").
  // Style of five reference "EV / ambient / angelic pad" clips: pure synth tones, low root with the chord an octave up, open major-7th
  // harmony, dark, very wide, slow volume swell. Root 98 Hz (the clips' 43-55 Hz sub roots barely play on laptop speakers).
  // Strings and Warm pad (earlier faces) and Open horizon were dropped. Id stays 'warm' (search ids, saved sessions).
  { id: 'warm', name: 'Cinematic pad', character: 'low root with a floating major-7th chord an octave above, dark, very wide, slowly swelling', plain: { rootHz: 98, chord: 1, chordType: 6, brightness: .5, softTop: 1400, fundamental: .5, width: 1 },
    fx: { ...motion('large', false, false), reverb: .55, size: 5, tone: 2000, drift: 1, tremRate: .1, tremDepth: .35 }, settings: '98 Hz · spread major 7th · dark · wide · swell every 10 s · drift' },
  // Voice, 2nd version: the stretch and minor 7th made the first one sound like Turbine; now an open chord, no stretch.
  { id: 'voice', name: 'Voice', character: 'soft choir "ooh-aah" on an open chord (5th + octave), no stretch', plain: { rootHz: 147, vowel: 1, vowelShape: .35, brightness: .5, softTop: 1400, chord: .7, chordType: 3 },
    fx: { ...motion('large', true, false), tone: 2500 }, settings: '147 Hz · ooh-aah vowel · 5th + octave · space large · vibrato' },
  { id: 'sparkle', name: 'Sparkle', character: 'separate bright bell tones, high', plain: { rootHz: 233, bellModes: 1, brightness: .55, softTop: 3000, chord: .6, chordType: 2 }, fx: motion('large', false, false), settings: '233 Hz · bell tones · minor 7th chord · gentle top · space large' },
  // Synth (2026-11-16, replaces Pure tone, whose three sounds were all Maybe): the Night drive 80s-style pad with a gentler pump (the
  // listener found its pump "a little too much"). At least 0.35 from every other family face.
  { id: 'synth', name: 'Synth', character: 'detuned saw pad, bittersweet minor 7th chord, gentle pump, filter sings with the pedal', plain: { rootHz: 175, brightness: .7, hollow: .15, softTop: 3000, chord: 1, chordType: 2, detune: .7 },
    fx: { ...motion('large', false, false), tone: 1500, res: 8, pump: 1, tremRate: 1.75, tremDepth: .15 }, settings: '175 Hz · detuned saw · minor 7th · gentle pump · resonant filter' },
  // Electric whine, 3rd try: "too high" at 7.5x and still at 5.5x; whine now 4x (top about 1 kHz) with a darker filter.
  { id: 'whine', name: 'Electric whine', character: 'thin hum with a clear high whine that climbs with speed, motor-like', plain: { rootHz: 98, fundamental: .6, brightness: .25, softTop: 700, chord: 0, whine: .6, whineRatio: 4 },
    fx: { ...motion('small', false, false), tone: 2000 }, settings: '98 Hz hum · whine 4x, softer · no chord · space small' },
  // Dark ambience (2026-11-15, replaces Deep metal): chosen on the phone test page as 85% Dark ambience + 15% Ghost choir.
  { id: 'dark', name: 'Dark ambience', character: 'bleak low drone, distant metal, a faint "ooh", huge space that slowly breathes', plain: { rootHz: 76, chord: .69, chordType: 3, bell: .36, vowel: .12, vowelShape: 0, detune: .52, lowDetune: 1, brightness: .47, softTop: 1630 },
    fx: { ...motion('large', false, false), reverb: .55, size: 6, tone: 960, res: 3.9, drift: 1 }, settings: '76 Hz · bleak chord (5th + octave) · distant metal · faint ooh · detuned low end · huge space · filter drift' },
]
// Retired starting sounds: kept only so saved sessions that used them still play in Sound trace.
const RETIRED_SOUNDS: StartingSound[] = [
  { id: 'pure', name: 'Pure tone', character: '', plain: { rootHz: 196, brightness: .15, softTop: 3000, chord: .35, chordType: 3 }, fx: { ...motion('large', true, false), tone: 6000 }, settings: '' },
  { id: 'turbine', name: 'Turbine', character: '', plain: { rootHz: 110, whine: .7, whineRatio: 4.5, fundamental: .5, brightness: .5, softTop: 900, chord: .6, chordType: 2 }, fx: motion('small', false, true), settings: '' },
  { id: 'digital', name: 'Digital', character: '', plain: { rootHz: 196, hollow: .7, brightness: .3, softTop: 1200, chord: .7, chordType: 2, bell: .9 }, fx: motion('large', false, false), settings: '' },
  { id: 'night', name: 'Night drive', character: '', plain: { rootHz: 175, brightness: .7, hollow: .15, softTop: 3000, chord: 1, chordType: 2, detune: .7 }, fx: { ...motion('large', false, false), tone: 1500, res: 8, pump: 1, tremRate: 1.75, tremDepth: .25 }, settings: '' },
]
// Faces and retired sounds first: VARIANTS itself calls findSound while it is being built, before it exists.
const findSound = (id: string) => [...STARTING_SOUNDS, ...RETIRED_SOUNDS].find(sound => sound.id === id) ?? Object.values(VARIANTS).flat().find(sound => sound.id === id)!
export const CANDIDATE_SOUNDS = STARTING_SOUNDS
/** Source tree, level 2 (2026-11-16): hand-made variants inside a family, 2-3 each, variants 0.38-0.50 apart and at least
 * 0.28 from every other starting sound (octave-band spectrum, measured at the capped pitch). Sparkle first; a Shimmer variant (stretched + detuned bells) was 0.16 from Low chimes and left out. */
export const VARIANTS: Record<string, StartingSound[]> = {
  sparkle: [
    { ...findSound('sparkle'), id: 'sparkle', name: 'Glass bells', character: 'the Sparkle starting sound: bright glass bell tones, high' },
    // Low chimes, 2nd try: the first was too dark (filter removed the upper bell tones) and sounded like Warm pad (0.04 apart) or Pure tone.
    { id: 'sparkle-chimes', name: 'Low chimes', character: 'deeper bell tones with their upper partials ringing, open chord, huge space', plain: { rootHz: 147, bellModes: 1, brightness: .6, softTop: 4000, chord: .4, chordType: 3, fundamental: .4 },
      fx: { ...motion('large', false, false), reverb: .5, size: 5, tone: 4000 }, settings: '147 Hz · bell tones, upper partials lead · 5th + octave · huge space' },
    // Crystal, 2nd try: "a little too high" at 220 Hz; now 185 Hz with a softer top.
    { id: 'sparkle-crystal', name: 'Crystal', character: 'single thin glass tone, no chord, the upper bell partials lead', plain: { rootHz: 185, bellModes: 1, brightness: .7, softTop: 4000, chord: 0, fundamental: .3 },
      fx: { ...motion('large', false, false), tone: 4000 }, settings: '185 Hz · bell tones · no chord · weak lowest tone' },
  ],
  // Other families (2026-11-16). The octave-band measure sees energy per range, not the kind of tone, so variants inside a family that
  // differ by hollow / bell / vowel / whine can measure close (0.07-0.2) to their original; the ear test decides.
  warm: [
    findSound('warm'),
    { id: 'warm-angelic', name: 'Angelic', character: 'brighter mid-range major chord, little bass, gently swelling', plain: { rootHz: 147, chord: 1, chordType: 4, brightness: .6, softTop: 1200, fundamental: .5, width: 1 },
      fx: { ...motion('large', false, false), reverb: .5, size: 4, tone: 2500, tremRate: .18, tremDepth: .35 }, settings: '147 Hz · major chord · mid-range · wide · swell every 5-6 s' },
    // Dreamy pad: style of the steady background under a reference intro clip (piano left out): D chord with 2nd and 4th (D-E-G-A),
    // 61% of energy at 250-500 Hz, pure tones, very wide. Settings fitted to its energy per range (error 7 points).
    { id: 'warm-dreamy', name: 'Dreamy pad', character: 'soft, open "suspended" chord, neither happy nor sad, warm mid tones, very wide', plain: { rootHz: 147, chord: 1, chordType: 5, brightness: .7, softTop: 900, fundamental: .3 },
      fx: { ...motion('large', false, false), reverb: .5, size: 3.5, tone: 2500 }, settings: '147 Hz · suspended chord (2nd + 4th + 5th + octave) · soft top 900 · wide reverb' },
  ],
  voice: [
    { ...findSound('voice'), name: 'Voice' },
    { id: 'voice-aah', name: 'Bright aah', character: 'open, brighter "aah-eh" choir', plain: { rootHz: 147, vowel: 1, vowelShape: .8, brightness: .65, softTop: 2500, chord: .7, chordType: 3 },
      fx: { ...motion('large', true, false), tone: 3000 }, settings: '147 Hz · aah-eh vowel · bright · 5th + octave · vibrato' },
    { id: 'voice-deep', name: 'Deep ooh', character: 'low, round "ooh" choir', plain: { rootHz: 110, vowel: 1, vowelShape: 0, brightness: .5, softTop: 1200, chord: .7, chordType: 3 },
      fx: { ...motion('large', true, false), tone: 2000 }, settings: '110 Hz · ooh vowel · 5th + octave · vibrato' },
  ],
  synth: [
    findSound('synth'),
    { id: 'synth-dark', name: 'Dark synth', character: 'lower, darker detuned saw on an open chord, no pump, singing filter', plain: { rootHz: 110, brightness: .75, softTop: 2500, chord: .7, chordType: 3, detune: .5 },
      fx: { ...motion('large', false, false), tone: 900, res: 6 }, settings: '110 Hz · detuned saw · 5th + octave · dark resonant filter' },
    { id: 'synth-lead', name: 'Bright lead', character: 'thinner, brighter synth tone, almost no chord, light vibrato', plain: { rootHz: 196, brightness: .8, hollow: .3, softTop: 3500, chord: .3, chordType: 3, detune: .5 },
      fx: { ...motion('large', true, false), tone: 3000, res: 4 }, settings: '196 Hz · bright saw · faint 5th + octave · vibrato' },
  ],
  whine: [
    { ...findSound('whine'), name: 'Electric whine' },
    { id: 'whine-clear', name: 'Clear whine', character: 'the whine louder and lower (3x the hum), so it is clearly heard without being high', plain: { rootHz: 98, fundamental: .6, brightness: .25, softTop: 700, chord: 0, whine: 1, whineRatio: 3 },
      fx: { ...motion('small', false, false), tone: 3000 }, settings: '98 Hz hum · loud whine 3x · no chord' },
    { id: 'whine-turbine', name: 'Turbine', character: 'fuller hum with a whine on top, gently pulsing (the earlier Turbine without its chord)', plain: { rootHz: 110, whine: .7, whineRatio: 4.5, fundamental: .5, brightness: .5, softTop: 900, chord: 0 },
      fx: motion('small', false, true), settings: '110 Hz · hum + whine 4.5x · no chord · tremolo' },
  ],
  dark: [
    { ...findSound('dark'), name: 'Dark ambience' },
    { id: 'dark-ghost', name: 'Ghost choir', character: 'distant "ooh" voices on the bleak chord, huge space', plain: { rootHz: 98, chord: .6, chordType: 3, bell: .15, vowel: .8, vowelShape: 0, detune: .6, brightness: .55, softTop: 1800 },
      fx: { ...findSound('dark').fx, tone: 1300, res: 3 }, settings: '98 Hz · ooh voices · bleak chord · huge space · drift' },
    { id: 'dark-gong', name: 'Gong', character: 'low gong-like bell tones, slowly breathing, huge space', plain: { rootHz: 87, bellModes: 1, chord: .5, chordType: 3, detune: .4, lowDetune: 1, brightness: .5, softTop: 2500 },
      fx: { ...findSound('dark').fx, tone: 1500, res: 3 }, settings: '87 Hz · bell tones · 5th + octave · detuned · huge space · drift' },
  ],
}
// Wide stereo on for every starting sound and variant (2026-11-16, listener: "it should be kept as on"); a sound may still set its own width.
for (const sound of [...STARTING_SOUNDS, ...Object.values(VARIANTS).flat()]) sound.plain.width ??= 1
/** Plain-words description of a search sound, shown after the session so the listener knows what changed. */
export function describeSound(recipe: unknown) {
  if (!isTuningRecipe(recipe)) return ''
  const b = recipe.base, name = (id: string) => findSound(id).name, changes: string[] = []
  if (b.blend) changes.push(`blended halfway with ${name(b.blend)}`)
  if (b.pitch) changes.push(`${PITCH_STEP} semitones ${b.pitch > 0 ? 'higher' : 'lower'}`)
  if (b.brightness) changes.push(b.brightness > 0 ? 'brighter' : 'darker')
  if (b.character) changes.push(`${b.character > 0 ? 'more' : 'less'} ${CHARACTER[b.start]?.label ?? 'character'}`)
  const sound = b.variant && b.variant !== b.start ? `${name(b.variant)} (${name(b.start)} family)` : name(b.start)
  return `${sound}${changes.length ? ': ' + changes.join(', ') : ', unchanged'}`
}  // Sound Lab 04 plays the current starting sounds
export const FAIR_FX: Fx = { ...SEARCH_FIXED, chorus: 1, reverb: .25, size: 1.2, tone: 2000, follow: 1, bodyDb: 0, tremDepth: 0, vibDepth: 0 }

/** Tuning (2026-11-15, 2nd version): how a session moves from a starting sound. Borrow and Climb dropped (too small to hear, and
 * Blend covers Borrow). Every change was made bigger after measuring: most were 0.1-0.2 apart on the octave-band spectrum, while the
 * starting sounds are 0.2-0.86 apart. Sizes are checked by ear in Sound Lab 05 (Change test) before the search trusts them.
 * Source: Pitch (4 semitones per step), Brightness, Character (the sound's own signature off / doubled), Blend with another sound (1/3, 1/2, 2/3).
 * Transformation: Rising or Evolving (chosen first) only. Movement (wobble/pulse/pump) dropped after the change test (small / can't hear);
 * Space always large; comfort cap fixed. */
export type Tuning = { kind: 'rise' | 'evolving'; start: string; variant?: string; pitch: number; brightness: number; character: number  // variant: a VARIANTS id (default: the family face)
  blend: string | null; mix: number; movement: 'still' | 'wobble' | 'pulse' | 'pump' }
export const TUNING_DEFAULT: Tuning = { kind: 'rise', start: 'warm', pitch: 0, brightness: 0, character: 0, blend: null, mix: .5, movement: 'still' }
export const PITCH_STEP = 8  // semitones per pitch step, one step each way (change test: 4 sounded small, 8 clear)
// Brightness side not offered for a sound (change test: small). Keep in sync with TUNING_LIMITS in source_search.py.
export const NO_BRIGHTNESS: Record<string, number> = { sparkle: 1 }
// Character less / more: the sound's own signature off / pushed further.
// A side is left out where the change test found it small (keep in sync with TUNING_LIMITS in source_search.py).
export const CHARACTER: Record<string, { label: string; less?: Partial<PlainParams>; more?: Partial<PlainParams> }> = {
  warm: { label: 'chord + richness', less: { chord: 0 } },  // more: small even with detune .9
  voice: { label: 'vowel', less: { vowel: 0 }, more: { vowel: 1, vowelShape: .7 } },  // more = open, brighter "aah-eh"
  sparkle: { label: 'upper bell tones', more: { fundamental: .2, softTop: 6000 } },  // less: small
  pure: { label: 'fifth + octave shimmer' },  // less and more both small
  whine: { label: 'whine', less: { whine: 0 } },  // more: small
  synth: { label: 'detune spread', less: { detune: .3 }, more: { detune: 1 } },  // not change-tested yet
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
  let plain = startPlain(t.variant ?? t.start)
  if (t.blend) plain = blendPlain(plain, startPlain(t.blend), t.mix ?? .5)
  if (t.character) plain = { ...plain, ...CHARACTER[t.start][t.character < 0 ? 'less' : 'more'] }
  if (t.brightness) {
    // Darker: -.35, soft top x0.4 (floor 300 Hz). Brighter: +.3, soft top x2 but at most 3.5 kHz: above that it sounded harsh / noisy.
    plain.brightness = Math.min(1, Math.max(0, plain.brightness + (t.brightness > 0 ? .3 : -.35)))
    plain.softTop = Math.round(t.brightness > 0 ? Math.max(plain.softTop, Math.min(3500, plain.softTop * 2)) : Math.max(300, plain.softTop * .4))
  }
  plain.rootHz = Math.round(Math.min(350, Math.max(40, plain.rootHz * 2 ** (PITCH_STEP * t.pitch / 12))))
  // Each sound keeps its own filter (tone, resonance); Movement replaces its vibrato / tremolo / pump.
  const own = findSound(t.variant ?? t.start).fx
  // Each sound plays with its own effects, as in Sound Lab (space, swell, pump, vibrato, filter): Movement is no longer a tuning change,
  // and a shared space / no movement removed Cinematic pad's swell and Synth's pump (2026-11-16).
  const fx: Fx = { ...own, follow: 1, bodyDb: 0, rasp: 0, peakHz }
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
