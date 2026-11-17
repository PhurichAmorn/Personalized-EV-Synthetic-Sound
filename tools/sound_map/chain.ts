// The app's driving chain over the 22 s simulated drive, offline (Node check and the listening page share it).
// Same code as the app where it can be: source stems (mapVoice.ts: plain synth or blocks), granular player (granular-processor.mjs), drivingSoundTargets, simulatedDrive,
// driveEnvelopeTarget. The WebAudio nodes of labEngine.buildRig/applyFx/driveRig are replayed sample by sample:
// vibrato delay, tremolo/pump, body peaking EQ, pedal-following low-pass (Q in dB, drift on detune), chorus.
// Returns left then right (pre-reverb, drive gain held at 1) and the drive gain every 50 ms step.
// ponytail: the app plays each of the three stems in its own granular player; here they are summed into one player (grain alignment
// differs slightly). Run one player per stem if the check must match the app sample for sample.
import { mapStems, mapRootHz, mapStage, type MapVoice } from '../../desktop/src/mapVoice'
import { drivingSoundTargets, responseRiseSeconds } from '../../desktop/src/drivingSoundMapping'
import { driveEnvelopeTarget } from '../../desktop/src/audioAutomation'
import { simulatedDrive, SIMULATED_DRIVE_SECONDS } from '../../desktop/src/simulatedDrive'
import { SEARCH_FIXED } from '../../desktop/src/levels'
import type { Fx } from '../../desktop/src/labEngine'
// @ts-expect-error plain JS module shared with the AudioWorklet
import { SourceLoopEngine } from '../../desktop/public/audio/granular-processor.mjs'

const FS = 48000, STEP = FS / 20, N = SIMULATED_DRIVE_SECONDS * FS, BLOCK = 128
const smooth = (seconds: number) => 1 - Math.exp(-1 / (seconds * FS))  // setTargetAtTime per sample

class Delay {  // DelayNode with linear interpolation
  buf = new Float64Array(4096); i = 0
  run(x: number, seconds: number) {
    this.buf[this.i] = x
    const pos = this.i - seconds * FS + this.buf.length, k = Math.floor(pos), f = pos - k
    const y = this.buf[k % this.buf.length] * (1 - f) + this.buf[(k + 1) % this.buf.length] * f
    this.i = (this.i + 1) % this.buf.length; return y
  }
}
class Biquad {  // direct form I, per channel
  b = [1, 0, 0]; a = [0, 0]; s = [[0, 0, 0, 0], [0, 0, 0, 0]]
  set(b0: number, b1: number, b2: number, a0: number, a1: number, a2: number) { this.b = [b0 / a0, b1 / a0, b2 / a0]; this.a = [a1 / a0, a2 / a0] }
  lowpass(hz: number, qDb: number) {  // WebAudio spec: lowpass Q is in dB
    const w = 2 * Math.PI * Math.min(hz, FS / 2 - 1) / FS, alpha = Math.sin(w) / (2 * 10 ** (qDb / 20)), c = Math.cos(w)
    this.set((1 - c) / 2, 1 - c, (1 - c) / 2, 1 + alpha, -2 * c, 1 - alpha)
  }
  peaking(hz: number, q: number, db: number) {
    const A = 10 ** (db / 40), w = 2 * Math.PI * hz / FS, alpha = Math.sin(w) / (2 * q), c = Math.cos(w)
    this.set(1 + alpha * A, -2 * c, 1 - alpha * A, 1 + alpha / A, -2 * c, 1 - alpha / A)
  }
  run(x: number, ch: number) {
    const s = this.s[ch], y = this.b[0] * x + this.b[1] * s[0] + this.b[2] * s[1] - this.a[0] * s[2] - this.a[1] * s[3]
    s[1] = s[0]; s[0] = x; s[3] = s[2]; s[2] = y; return y
  }
}
// Pump: the app's 8-harmonic ramp-up saw (createPeriodicWave, normalised to peak 1 as WebAudio does).
const pumpRaw = (p: number) => { let v = 0; for (let n = 1; n <= 8; n++) v += (n % 2 ? 1 : -1) / n * Math.sin(2 * Math.PI * n * p); return v }
const PUMP_PEAK = Math.max(...Array.from({ length: 4096 }, (_, i) => Math.abs(pumpRaw(i / 4096))))

/** voice/fx as stored: fx filled with levels.SEARCH_FIXED, as the app plays a sound-map recipe. */
export function driveSound(voice: MapVoice, fx: Partial<Fx>, mode: 'rise' | 'evolving') {
  const stems = mapStems(voice), sum = (c: number) => Float32Array.from(stems[0][c], (v, i) => v + stems[1][c][i] + stems[2][c][i])
  // Left stems into both ears, as the check was calibrated (2026-11-16): with width on, the right stem is a few cents sharp, and the
  // L+R mix the check measures turned that stereo spread into beating nobody hears (Sparkle, Bright aah read as pulsing).
  const left = sum(0)
  return render([left, left], mapRootHz(voice), { ...SEARCH_FIXED, ...fx } as Fx, mode, mapStage(voice))
}

/** stage: optional after-player stage (EngineStage config: fixed resonances, low-pass), as the app's engine and cello use. */
export function render([left, right]: Float32Array[], rootHz: number, fx: Fx, mode: 'rise' | 'evolving', stage?: { resonances: [number, number, number][]; lowpassHz: number }) {
  const player = new SourceLoopEngine([left, right], FS)
  if (stage) player.setEngine({ baseHz: rootHz, rasp: fx.rasp, cabin: 0, ...stage })
  else if (fx.rasp > 0) player.setEngine({ baseHz: rootHz, rasp: fx.rasp, resonances: [], lowpassHz: 0, cabin: 0 })
  const vib = [new Delay(), new Delay()], chorus = [new Delay(), new Delay()], body = new Biquad(), low = new Biquad()
  body.peaking(fx.bodyHz, 1.5, fx.bodyDb)
  const vibGain = fx.vibDepth / 1731 / (2 * Math.PI * fx.vibRate), wetC = .25 * fx.chorus, dryC = 1 - wetC
  const motion = { response: 'exponential' as const, travel: 1 }
  const p = { rate: 0, evolve: mode === 'evolving' ? 1 : 0, cycle: 0, hold: 0, cutoff: 0, gain: 0 }, t = { ...p }
  let driveTarget = 0, gainSmooth = smooth(.05)
  const out = new Float32Array(2 * N), gains: number[] = []
  for (let n = 0; n < N; n++) {
    if (n % STEP === 0) {  // driveRig, every 50 ms
      const target = drivingSoundTargets(simulatedDrive(n / FS), false, motion.response, mode, motion.travel)
      t.rate = fx.peakHz ? Math.min(target.rate, fx.peakHz / rootHz) : target.rate
      t.cycle = target.cycleSpeed; t.hold = target.loopHold
      t.cutoff = Math.min(20000, Math.max(200, fx.tone * 2 ** (fx.follow * (2 * target.propulsion - 1))))
      const env = driveEnvelopeTarget(target.driveGain, responseRiseSeconds[motion.response], target.driveGain < driveTarget)
      driveTarget = target.driveGain; t.gain = env.gain; gainSmooth = smooth(env.smoothing)
      if (n === 0) Object.assign(p, t)  // first step is immediate
      gains.push(p.gain)
    }
    p.rate += (t.rate - p.rate) * smooth(.35); p.cycle += (t.cycle - p.cycle) * smooth(.15)
    p.hold += (t.hold - p.hold) * smooth(.05); p.gain += (t.gain - p.gain) * gainSmooth
    p.cutoff += (t.cutoff - p.cutoff) * smooth(.15)
    if (n % BLOCK === 0) low.lowpass(p.cutoff * 2 ** ((fx.drift ? 1100 * Math.sin(2 * Math.PI * n / FS / 14) : 0) / 1200), fx.res)
    const time = n / FS
    let l = player.sample(p.rate, p.hold, p.evolve, p.cycle), r = player.right
    const vibDelay = .012 + vibGain * Math.sin(2 * Math.PI * fx.vibRate * time)
    l = vib[0].run(l, vibDelay); r = vib[1].run(r, vibDelay)
    const phase = fx.tremRate * time % 1
    const trem = 1 - fx.tremDepth / 2 + fx.tremDepth / 2 * (fx.pump ? pumpRaw(phase) / PUMP_PEAK : Math.sin(2 * Math.PI * phase))
    l = low.run(body.run(l * trem, 0), 0); r = low.run(body.run(r * trem, 1), 1)
    out[n] = dryC * l + wetC * chorus[0].run(l, .018 + .0012 * Math.sin(2 * Math.PI * .28 * time))
    out[N + n] = dryC * r + wetC * chorus[1].run(r, .023 + .0012 * Math.sin(2 * Math.PI * .33 * time))
  }
  return { out, gains }
}
