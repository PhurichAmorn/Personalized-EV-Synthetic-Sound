/** 'stack' sound-map voice: the same note in several octaves, each octave layer with its own texture and its own slow swell, so the
 * sound feels layered (Shepard-like) yet behaves like any other sound: the granular players raise its pitch with speed. A fixed
 * after-player stage (a low peak and a low-pass, as the engine and cello use) stays put while the pitch climbs, so upper layers thin
 * out and the sound stays deep. Proposed 2026-11-17 after the octave-layer listening tests (tools/sound_map/octaves.ts).
 * Every partial sits on the 0.2 Hz grid of the 5 s loop, so the loop is seamless. Fifths are added only from 220 Hz up: a fifth
 * over a low root put strong partials one root apart and read as roughness.
 * Textures 4-11 (frame, 2026-11-17): sparkle (bell pings), air (noise band), Sound Lab families (choir, strings pad, cello, electric)
 * and the pool's plain synth and blocks voices as layers. A layer is built in its source's own pitch range and moved up by whole
 * octaves (low-passed, then every 2nd/4th... sample, tiled: exact and seamless); a family layer below its range falls back to strings.
 * Inside a stack every source plays one clean copy (family and blocks ensemble 0, plain synth detune 0): stacked detuned copies beat
 * and were heard as pulsing, "up and down like a jet ski" (listening marks, 2026-11-18). Exception: `ensemble`, small fixed detune on the
 * upper layers only (Moody top, 12 cents), heard as good on the synth texture (knob test 2026-11-22). */
import { createSourceStems, DEFAULT_SOURCE_CONTROLS, type SourceFamily, type SourceShape, type SourceControls } from './sourceDesigner'
import { createPlainVoices, EXTRAS_OFF, type PlainParams } from './plainSource'
import { renderRecipe } from './sourceRecipe'
export type StackParams = {
  rootHz: number        // lowest layer (Hz)
  layers: number        // octave layers, 3-5
  timbres: number[]     // per layer: 0 plain, 1 strings, 2 hollow, 3 glass, 4 sparkle, 5 air, 6 choir, 7 strings pad, 8 cello, 9 electric, 10 plain synth, 11 blocks
  fall: number          // level of each layer relative to the one below
  depth: number         // depth of each layer's slow swell (0 = steady)
  seed: number          // which swell pattern (whole cycles per loop) each layer gets
  fifth: number         // level of fifths over layers at 220 Hz and up
  shimmer: number       // glass shimmer over the top layer
  spread: number        // stereo width: how far apart the two ears start (no detuning)
  peakHz: number; peakDb: number; cutoff: number  // after-player stage
  twinkle?: number      // sparkle: bell pings per loop
  trend?: StackTrend    // roles (2026-11-18): body / middle / top players each follow the drive their own way; absent = the old layout and one level for all
  plain?: Partial<PlainParams>                                // texture 10: the plain synth voice (its rootHz is set per layer)
  ensemble?: number     // cents: two detuned copies (+-) of every upper layer; the body stays one clean copy (Moody top, knob test 2026-11-22: good on Synth)
  blocks?: { shape: SourceShape; controls: SourceControls }  // texture 11: the blocks voice (its rootRatio is set per layer)
}
/** Per player (stem): its level at rest and at full drive (0-1), and what drives it: 0 = the pedal, 1 = the speed. Body = lowest layer,
 * middle = layers between, top = highest layer plus fifths and shimmer. So a sound can keep a steady body while its top opens with speed. */
export type StackTrend = { rest: [number, number, number]; full: [number, number, number]; mix: [number, number, number] }
/** Level of each player now, from the speed (km/h) and the pedal (0-1 propulsion). */
export function trendGains(t: StackTrend, speedKmh: number, propulsion: number): number[] {
  const speed = Math.max(0, Math.min(1, speedKmh / 120)), pedal = Math.max(0, Math.min(1, propulsion))
  return [0, 1, 2].map(i => { const u = t.mix[i] * speed + (1 - t.mix[i]) * pedal; return t.rest[i] + (t.full[i] - t.rest[i]) * u })
}
export const STACK_TEXTURES = ['plain', 'strings', 'hollow', 'glass', 'sparkle', 'air', 'choir', 'strings pad', 'cello', 'electric', 'plain synth', 'blocks']
const FAMILY: Record<number, [SourceFamily, number]> = { 6: ['vocal', 1], 7: ['bowed', 1], 8: ['orchestra', .6], 9: ['evolution', .45] }  // family, register
const FS = 48000, FRAMES = FS * 5
const TIMBRES: [number, number][][] = [
  [[1, 1]],                                                // plain
  [[1, 1], [2, .4], [3, .2], [4, .1], [5, .05]],           // strings: falling harmonic series
  [[1, 1], [3, .3], [5, .12], [7, .05]],                   // hollow: odd harmonics (clarinet-like)
  [[1, 1], [2.76, .35], [5.4, .15]],                       // glass: bell modes
]
const SWELLS = [[1, 2, 3, 1, 2], [2, 1, 3, 2, 1], [1, 3, 2, 3, 1], [3, 1, 2, 1, 3], [2, 3, 1, 2, 3], [1, 2, 1, 3, 2]]
const grid = (hz: number) => Math.round(hz * 5) / 5
const rand = (seed: number) => () => { seed = (seed * 1664525 + 1013904223) >>> 0; return seed / 4294967296 }

/** A loop moved up by `octaves` whole octaves: periodic low-pass (two passes, so the filter has settled), keep every 2^n-th sample, tile. */
function octaveUp(x: Float32Array, octaves: number) {
  if (octaves <= 0) return x
  const n = 2 ** octaves, a = 1 - Math.exp(-2 * Math.PI * (FS * .4 / n) / FS), y = new Float32Array(x.length)
  let s1 = 0, s2 = 0, s3 = 0, s4 = 0
  for (let pass = 0; pass < 2; pass++) for (let i = 0; i < x.length; i++) { s1 += a * (x[i] - s1); s2 += a * (s1 - s2); s3 += a * (s2 - s3); s4 += a * (s3 - s4); y[i] = s4 }
  return Float32Array.from(x, (_, i) => y[(i * n) % x.length])
}
/** Source built at hz / 2^m inside [lo, hi], then moved up m octaves; null if hz is below the source's range. */
function inRange(hz: number, lo: number, hi: number, build: (base: number) => Float32Array[]) {
  let m = 0; while (hz / 2 ** m > hi) m++
  if (hz / 2 ** m < lo) return null
  return build(grid(hz / 2 ** m)).map(c => octaveUp(c, m))
}
const sum3 = (stems: Float32Array[][]) => [0, 1].map(c => Float32Array.from(stems[0][c], (v, i) => v + stems[1][c][i] + stems[2][c][i]))
/** Textures 4-11 as a stereo loop at hz, or null (fall back to strings). */
function texture(t: number, hz: number, p: StackParams, k: number): Float32Array[] | null {
  if (t === 4) {  // sparkle: short glass pings at seeded moments, each fading fast; wrapped, so the loop stays seamless. Kept as heard
    // (2026-11-18); the clicky ones are dropped by the stricter pulsing limit instead
    const out = [new Float32Array(FRAMES), new Float32Array(FRAMES)], r = rand(1000 + k * 77 + Math.round(p.seed)), count = Math.round(p.twinkle ?? 8)
    for (let n = 0; n < count; n++) {
      const at = Math.floor(r() * FRAMES), pan = r(), decay = .15 + .25 * r(), modes = TIMBRES[3]
      for (let i = 0; i < FS * 1.2; i++) {
        const env = Math.exp(-i / FS / decay) * Math.min(1, i / (FS * .004)), idx = (at + i) % FRAMES
        let v = 0; for (const [h, a] of modes) v += a * Math.sin(2 * Math.PI * grid(hz * h) * (at + i) / FS)
        out[0][idx] += v * env * (1 - pan * .6); out[1][idx] += v * env * (.4 + pan * .6)
      }
    }
    return out
  }
  if (t === 5) {  // air: a soft noise band around hz from many grid partials with seeded phases (periodic noise)
    const out = [new Float32Array(FRAMES), new Float32Array(FRAMES)], r = rand(5000 + k * 31)
    for (let j = 0; j < 40; j++) {
      const f = grid(hz * 2 ** ((r() - .5) * .8)), ph = [r(), r()]
      for (let c = 0; c < 2; c++) for (let i = 0; i < FRAMES; i++) out[c][i] += Math.sin(2 * Math.PI * (f * i / FS + ph[c]))
    }
    return out
  }
  if (FAMILY[t]) {
    const [family, register] = FAMILY[t], ref = 174.8 * register
    return inRange(hz, ref * .4, ref * 2, base => sum3(createSourceStems({ ...DEFAULT_SOURCE_CONTROLS, ensemble: 0, movement: 0 }, FS, family, { rootRatio: base / ref })))
  }
  if (t === 10) return inRange(hz, 40, 350, base => sum3(createPlainVoices({ ...EXTRAS_OFF, air: 0, ...(p.plain ?? {}), detune: 0, rootHz: base } as PlainParams)))
  if (t === 11 && p.blocks) return inRange(hz, 174.8 * .4, 174.8 * 2, base => sum3(renderRecipe({ version: 1, seed: 0, layers: [{ role: 'foundation', method: 'blocks', gain: 1,
    shape: { ...p.blocks!.shape, rootRatio: base / 174.8 }, controls: { ...p.blocks!.controls, ensemble: 0, movement: 0 } }] })))
  return null
}

/** Three stereo stems (the app's three granular players): lowest layer, the middle layers, then the top layers with fifths and shimmer. */
export function stackStems(p: StackParams): Float32Array[][] {
  const stems = [0, 1, 2].map(() => [new Float32Array(FRAMES), new Float32Array(FRAMES)])
  const swell = SWELLS[Math.round(p.seed) % SWELLS.length]
  const add = (stem: number, hz: number, level: number, cycles: number, offset: number) => {
    if (hz > FS * .45 || level < 1e-4) return
    for (let c = 0; c < 2; c++) {
      const start = (offset + c * .5 * p.spread) % 1, out = stems[stem][c]
      for (let i = 0; i < FRAMES; i++) {
        const env = 1 - p.depth / 2 + p.depth / 2 * Math.sin(2 * Math.PI * (cycles * i / FRAMES + offset + c * .25))
        out[i] += level * env * Math.sin(2 * Math.PI * (hz * i / FS + start))
      }
    }
  }
  const layers = Math.max(1, Math.min(5, Math.round(p.layers)))
  for (let k = 0; k < layers; k++) {
    const copies = k > 0 && p.ensemble ? [[0, 1, 0], [-p.ensemble, .8, .31], [p.ensemble, .8, .67]] : [[0, 1, 0]]  // [cents, level, phase]
    for (const [cents, gain, phase] of copies) {
    const f = grid(p.rootHz * 2 ** k * 2 ** (cents / 1200)), level = p.fall ** k * gain, cycles = swell[k]
    const stem = k === 0 ? 0 : p.trend ? (k === layers - 1 ? 2 : 1) : k < 3 ? 1 : 2  // with roles the top layer is the top player, whatever the layer count
    const t = Math.round(p.timbres[k] ?? 0), loop = t >= TIMBRES.length ? texture(t, f, p, k) : null
    if (loop) {  // as loud as a plain layer at this level (RMS level/sqrt 2), with the layer's own swell
      const rms = Math.sqrt(loop[0].reduce((s, v) => s + v * v, 0) / FRAMES) || 1, scale = level / Math.SQRT2 / rms
      for (let c = 0; c < 2; c++) for (let i = 0; i < FRAMES; i++)
        stems[stem][c][i] += loop[c][i] * scale * (1 - p.depth / 2 + p.depth / 2 * Math.sin(2 * Math.PI * (cycles * i / FRAMES + k * .43 + c * .25)))
    } else TIMBRES[t < TIMBRES.length ? t : 1].forEach(([h, a], j) => add(stem, grid(f * h), level * a, cycles, (k * .43 + j * .17 + phase) % 1))
    if (f >= 220 && p.fifth > 0) add(2, grid(f * 1.5), level * p.fifth, swell[(k + 2) % 5], (k * .31 + .5) % 1)
    if (k === layers - 1 && p.shimmer > 0) for (const [h, a] of TIMBRES[3]) add(2, grid(f * 2 * h), level * p.shimmer * a, swell[(k + 1) % 5], (k * .7 + h * .1) % 1)
    }
  }
  const peak = Math.max(...stems.flatMap(s => s.map(c => c.reduce((m, v) => Math.max(m, Math.abs(v)), 0))))
  const total = Math.max(1e-9, peak * 3)  // the three stems are summed by the players
  return stems.map(s => s.map(c => c.map(v => v / total * 1.2)))
}

/** The fixed after-player stage (granular-processor EngineStage config fields). */
export const stackStage = (p: StackParams) => ({ resonances: [[p.peakHz, p.peakDb, .8]] as [number, number, number][], lowpassHz: p.cutoff, lowpassFollow: true })  // follow: the low-pass moves with pitch; fixed, rising octave layers sounded stalled (2026-11-18)
