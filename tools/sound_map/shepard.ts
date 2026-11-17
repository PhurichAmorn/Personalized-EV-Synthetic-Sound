// node out/shepard.mjs outDir: Shepard-Risset prototypes on the 22 s simulated drive (offline oscillator bank, not the granular player).
// Octave-spaced components glide up together under a fixed bell-shaped level curve over log frequency; a component leaving the
// top fades out as one enters at the bottom, so the rise never ends. Mapping (proposal, 2026-11-17): glide speed follows power
// (regen glides down, cruise holds), and an optional low-pass opens with vehicle speed, so brightness carries speed.
// Output per sound: outDir/id.rise.f32 (left then right, drive gain held at 1) and id.rise.gain.json (drive gain every 50 ms), as
// orchestra.ts, so orchestra.py adds gain and room, writes WAVs and measures the guardrail.
import { writeFileSync, mkdirSync, existsSync } from 'node:fs'
import { roomImpulse } from '../../desktop/src/plainSource'
import { simulatedDrive, SIMULATED_DRIVE_SECONDS } from '../../desktop/src/simulatedDrive'
import { drivingSoundTargets, responseRiseSeconds } from '../../desktop/src/drivingSoundMapping'
import { driveEnvelopeTarget } from '../../desktop/src/audioAutomation'
// @ts-expect-error plain JS module shared with the AudioWorklet
import { GranularEngine } from '../../desktop/public/audio/granular-processor.mjs'

const FS = 48000, STEP = FS / 20, N = SIMULATED_DRIVE_SECONDS * FS
const OCTAVES = 9, F0 = 27.5                 // components from 27.5 Hz up to about 14 kHz
const BELL_CENTRE = Math.log2(220), BELL_WIDTH = 1.4  // octaves (Gaussian sigma)
const UP = 1 / 8, DOWN = 1 / 12              // octaves per second at full power / full regen: slow, a rise is not a siren
type Shepard = { id: string; name: string; idea: string; glide: boolean; filter: boolean; strings: boolean; fx: { reverb: number; size: number }
  granular?: { measures: boolean } }
export const SOUNDS: Shepard[] = [
  { id: 'shepard-glide', name: 'Shepard glide', idea: 'endless rise while you accelerate (glide speed follows power), holds at cruise, glides down on regen; no speed filter', glide: true, filter: false, strings: false, fx: { reverb: .35, size: 2.5 } },
  { id: 'shepard-filter', name: 'Shepard glide + rising low-pass', idea: 'the same glide, plus a low-pass that opens from about 400 Hz at rest to about 4.5 kHz at 120 km/h: brightness carries speed', glide: true, filter: true, strings: false, fx: { reverb: .35, size: 2.5 } },
  { id: 'filter-only', name: 'Filter sweep only', idea: 'a fixed octave stack (no glide); only the low-pass opens with speed', glide: false, filter: true, strings: false, fx: { reverb: .35, size: 2.5 } },
  { id: 'granular-raw', name: 'Granular Shepard, no click prevention', idea: 'the app\'s granular player on a flat octave-stack loop, gliding twice as fast as above so the drive wraps several times; at each octave the playback rate jumps from 2 back to 1 with no crossfade and no bell filter. For comparison: this is what a click or step sounds like', glide: true, filter: true, strings: false, fx: { reverb: .35, size: 2.5 }, granular: { measures: false } },
  { id: 'granular-shepard', name: 'Granular Shepard, all prevention', idea: 'the same player and loop; at each octave a second player starts an octave lower and the two crossfade over 40 ms (equal power), and a fixed band filter (70 Hz to 1 kHz, 4th order each side) hides the top and bottom tones that change at the jump', glide: true, filter: true, strings: false, fx: { reverb: .35, size: 2.5 }, granular: { measures: true } },
  { id: 'granular-strings', name: 'Granular Shepard strings, all prevention', idea: 'as above with the string-like voice (soft harmonics on every octave component, so the loop still maps onto itself an octave up)', glide: true, filter: true, strings: true, fx: { reverb: .5, size: 3 }, granular: { measures: true } },
  { id: 'shepard-strings', name: 'Shepard strings', idea: 'glide and rising low-pass with a string-like voice: each octave component has a few soft string-like harmonics, and the two ears start at different phases for width', glide: true, filter: true, strings: true, fx: { reverb: .5, size: 3 } },
]

// Granular route (option A): a 5 s flat octave-stack loop (every component on the 0.2 Hz loop grid), played by the app's GranularEngine.
// The rate glides 1 -> 2 (one octave) and wraps; with measures a fresh player takes over an octave lower via a 40 ms equal-power
// crossfade, and a fixed band filter after the player plays the role of the bell. Returns the wrap times for the click check.
const LOOP_ROOT = 27.6
function octaveLoop(strings: boolean) {
  const frames = FS * 5, harmonics = strings ? [1, .35, .15, .07] : [1], loop = [new Float32Array(frames), new Float32Array(frames)]
  for (let k = 0; k < OCTAVES; k++) harmonics.forEach((h, j) => {
    const f = LOOP_ROOT * 2 ** k * (j + 1); if (f > FS * .45) return
    for (const c of [0, 1]) { const start = strings ? (c * .37 + (k * harmonics.length + j) * .61) % 1 : 0
      for (let i = 0; i < frames; i++) loop[c][i] += h * Math.sin(2 * Math.PI * (f * i / FS + start)) * .1 }
  })
  return loop
}
class Biquad {
  b = [1, 0, 0]; a = [0, 0]; s = [0, 0, 0, 0]
  constructor(type: 'lowpass' | 'highpass', hz: number) {
    const w = 2 * Math.PI * hz / FS, al = Math.sin(w) / (2 * Math.SQRT1_2), c = Math.cos(w), a0 = 1 + al
    this.b = type === 'lowpass' ? [(1 - c) / 2 / a0, (1 - c) / a0, (1 - c) / 2 / a0] : [(1 + c) / 2 / a0, -(1 + c) / a0, (1 + c) / 2 / a0]
    this.a = [-2 * c / a0, (1 - al) / a0]
  }
  run(x: number) { const s = this.s, y = this.b[0] * x + this.b[1] * s[0] + this.b[2] * s[1] - this.a[0] * s[2] - this.a[1] * s[3]; s[1] = s[0]; s[0] = x; s[3] = s[2]; s[2] = y; return y }
}
function renderGranular(s: Shepard) {
  const measures = s.granular!.measures, loop = octaveLoop(s.strings)
  const out = new Float32Array(2 * N), gains: number[] = [], wraps: number[] = []
  type Voice = { engine: any; offset: number; fade: number; dir: number }  // offset: octaves added to the shared position
  let voices: Voice[] = [{ engine: new GranularEngine(loop, FS), offset: 0, fade: 1, dir: 0 }]
  const XFADE = Math.round(.04 * FS)
  const bands = [0, 1].map(() => measures ? [new Biquad('highpass', 70), new Biquad('highpass', 70), new Biquad('lowpass', 1000), new Biquad('lowpass', 1000)] : [])
  // Click test: twice the glide speed and a start halfway through an octave, so the 22 s drive wraps several times (at UP the
  // whole drive climbs only about 0.95 octave and never wraps).
  let position = .5, rate = 0, gain = 0, gainTarget = 0, smoothing = .05, driveTarget = 0, cutoff = 400
  const lp = [[0, 0], [0, 0]]
  for (let n = 0; n < N; n++) {
    if (n % STEP === 0) {
      const input = simulatedDrive(n / FS), t = drivingSoundTargets(input, false, 'exponential', 'rise'), load = input.motorLoad ?? 0
      rate = 2 * (load >= 0 ? UP * (input.power ?? 0) : -DOWN * -load)
      const env = driveEnvelopeTarget(t.driveGain, responseRiseSeconds.exponential, t.driveGain < driveTarget)
      driveTarget = t.driveGain; gainTarget = env.gain; smoothing = env.smoothing
      cutoff = 400 * 2 ** (3.5 * Math.min(1, input.speedKmh / 120)); gains.push(gain)
    }
    gain += (gainTarget - gain) * (1 - Math.exp(-1 / (smoothing * FS)))
    position += rate / FS
    if (position >= 1 || position < 0) {  // one octave done: wrap
      const step = position >= 1 ? -1 : 1; position += step; wraps.push(n / FS)
      if (measures) { for (const v of voices) { v.offset -= step; v.dir = -1 } voices.push({ engine: new GranularEngine(loop, FS), offset: 0, fade: 0, dir: 1 }) }
    }
    let l = 0, r = 0
    for (const v of voices) {
      if (v.dir) v.fade = Math.max(0, Math.min(1, v.fade + v.dir / XFADE))
      const w = Math.sin(Math.PI / 2 * v.fade)  // equal power
      l += w * v.engine.sample(2 ** (position + v.offset)); r += w * v.engine.right
    }
    voices = voices.filter(v => v.dir >= 0 || v.fade > 0)
    const a = 1 - Math.exp(-2 * Math.PI * cutoff / FS)
    const xs = [l, r]
    for (let c = 0; c < 2; c++) {
      let x = xs[c]; for (const f of bands[c]) x = f.run(x)
      lp[c][0] += a * (x - lp[c][0]); lp[c][1] += a * (lp[c][0] - lp[c][1])
      out[c * N + n] = lp[c][1] * (measures ? 2 : 1)
    }
  }
  return { out, gains, wraps }
}

const bell = (f: number) => Math.exp(-.5 * ((Math.log2(f) - BELL_CENTRE) / BELL_WIDTH) ** 2)
function render(s: Shepard) {
  const out = new Float32Array(2 * N), gains: number[] = []
  const harmonics = s.strings ? [1, .35, .15, .07] : [1]
  // Width from a different starting phase per channel, not detuned copies: a 0.35% detuned pair beat as pulsing 0.44 (limit 0.4).
  const detune = [[1], [1]]
  const phase = detune.map((c, ch) => c.map(() => Float64Array.from({ length: OCTAVES * harmonics.length }, (_, i) => s.strings ? (ch * .37 + i * .61) % 1 : 0)))
  let position = 0, rate = 0, gain = 0, gainTarget = 0, smoothing = .05, driveTarget = 0, cutoff = 400
  const lp = [[0, 0], [0, 0]]  // two one-pole stages per channel
  for (let n = 0; n < N; n++) {
    if (n % STEP === 0) {
      const input = simulatedDrive(n / FS), t = drivingSoundTargets(input, false, 'exponential', 'rise')
      const load = input.motorLoad ?? 0
      rate = !s.glide ? 0 : load >= 0 ? UP * (input.power ?? 0) : -DOWN * -load
      const env = driveEnvelopeTarget(t.driveGain, responseRiseSeconds.exponential, t.driveGain < driveTarget)
      driveTarget = t.driveGain; gainTarget = env.gain; smoothing = env.smoothing
      cutoff = s.filter ? 400 * 2 ** (3.5 * Math.min(1, input.speedKmh / 120)) : 20000
      gains.push(gain)
    }
    gain += (gainTarget - gain) * (1 - Math.exp(-1 / (smoothing * FS)))
    position = ((position + rate / FS) % 1 + 1) % 1  // octaves; wraps, so the stack maps onto itself
    const a = 1 - Math.exp(-2 * Math.PI * cutoff / FS)
    for (let c = 0; c < 2; c++) {
      let x = 0
      for (let k = 0; k < OCTAVES; k++) {
        const f = F0 * 2 ** (k + position), level = bell(f)
        if (level < 1e-3) continue
        harmonics.forEach((h, j) => {
          const fh = f * (j + 1); if (fh > FS * .45) return
          detune[c].forEach((d, i) => {
            const p = phase[c][i]; const idx = k * harmonics.length + j
            p[idx] = (p[idx] + fh * d / FS) % 1
            x += level * h * Math.sin(2 * Math.PI * p[idx]) / detune[c].length
          })
        })
      }
      lp[c][0] += a * (x - lp[c][0]); lp[c][1] += a * (lp[c][0] - lp[c][1])
      out[c * N + n] = (s.filter ? lp[c][1] : x) * .15
    }
  }
  return { out, gains }
}

const outDir = process.argv[2]
mkdirSync(outDir, { recursive: true })
for (const s of SOUNDS) {
  const room = `${outDir}/room-${s.fx.size}.f32`
  if (!existsSync(room)) { const [a, b] = roomImpulse(48000, s.fx.size); const ir = new Float32Array(2 * a.length); ir.set(a); ir.set(b, a.length); writeFileSync(room, ir) }
  if (s.granular) {
    const { out, gains, wraps } = renderGranular(s)
    writeFileSync(`${outDir}/${s.id}.rise.f32`, out); writeFileSync(`${outDir}/${s.id}.rise.gain.json`, JSON.stringify(gains))
    writeFileSync(`${outDir}/${s.id}.rise.wraps.json`, JSON.stringify(wraps))
  } else {
    const { out, gains } = render(s)
    writeFileSync(`${outDir}/${s.id}.rise.f32`, out); writeFileSync(`${outDir}/${s.id}.rise.gain.json`, JSON.stringify(gains))
  }
}
writeFileSync(`${outDir}/sounds.json`, JSON.stringify(SOUNDS))
