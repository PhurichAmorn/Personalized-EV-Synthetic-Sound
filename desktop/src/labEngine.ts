import { GranularPlayer, type GranularMode } from './granularPlayer'
import { createChorus, driveEnvelopeTarget, smoothParameter } from './audioAutomation'
import { drivingSoundTargets, responseRiseSeconds, type DrivingInput, type SoundResponse } from './drivingSoundMapping'
import { roomImpulse } from './plainSource'
import { sourceAudioBuffers } from './sourceDesigner'

/** Shared audio engine: plain stems -> one granular player per stem (driving motion) -> transformation effects.
 * Sound Lab and source discovery both play through this, so a session sounds exactly like the lab. */
import { trendGains, type StackTrend } from './stackVoice'
export type Fx = { tone: number; follow: number; bodyHz: number; bodyDb: number; chorus: number; reverb: number; size: number; tremRate: number; tremDepth: number; rasp: number; vibDepth: number; vibRate: number
  pump: number; res: number  // pump 1: tremolo becomes a sidechain-style duck (sudden dip, slow swell); res: low-pass resonance (Q)
  peakHz?: number  // comfort cap: highest note (Hz) the drive may reach
  stage?: { resonances: [number, number, number][]; lowpassHz: number }  // fixed after-player stage of a 'stack' map voice (mapStage)
  trend?: StackTrend  // per-player drive trends of a 'stack' map voice with roles (mapTrend)
  gain?: number  // loudness match (tools/sound_map/loudness.py): playback gain so every pool sound starts equally loud
  drift?: number }  // 1: low-pass breathes +-1100 cents on a 14 s cycle (Dark ambience)
export type Motion = { mode: 'source' | GranularMode; travel: number; response: SoundResponse; input: 'drive' | 'manual'; position: number; pedal: number }
// Starts near the original styles' warmth: their chorus and room, a gentle body bump at 450 Hz.
export const FX_DEFAULT: Fx = { tone: 6000, follow: .5, bodyHz: 450, bodyDb: 3, chorus: 1, reverb: .25, size: 2, tremRate: 6, tremDepth: 0, rasp: 0, vibDepth: 0, vibRate: 5.2, pump: 0, res: .6 }
export const FX_OFF: Fx = { ...FX_DEFAULT, tone: 18000, follow: 0, bodyDb: 0, chorus: 0, reverb: 0 }
export const clamp = (value: number, min: number, max: number) => Math.max(min, Math.min(max, value))
export const manualInput = (x: number, pedal = .6): DrivingInput => ({ running: true, starting: false, speedKmh: 130 * x, throttle: pedal, power: pedal, motorLoad: pedal, rpm: 130 * x / 160 * 12000, maxRpm: 12000, acceleration: 0 })
const workletReady = new WeakMap<AudioContext, Promise<void>>()
export function granularWorklet(context: AudioContext) {
  let ready = workletReady.get(context)
  if (!ready) { ready = context.audioWorklet.addModule('/audio/granular-processor.mjs?v=9'); workletReady.set(context, ready) }
  return ready
}

export function buildRig(context: AudioContext, sources: AudioBuffer[], mode: Motion['mode'], analyser: AnalyserNode) {
  const granular = mode !== 'source'
  const players = sources.map(source => granular ? new GranularPlayer(context, source) : Object.assign(context.createBufferSource(), { buffer: source, loop: true }))
  // Vibrato after the player: a delay line swept by a sine (pitch deviation = 2 pi x rate x sweep depth).
  const vib = context.createDelay(.05), vibLfo = context.createOscillator(), vibDepth = context.createGain()
  vib.delayTime.value = .012; vibDepth.gain.value = 0; vibLfo.connect(vibDepth); vibDepth.connect(vib.delayTime); vibLfo.start()
  const trem = context.createGain(), lfo = context.createOscillator(), lfoDepth = context.createGain()
  const body = context.createBiquadFilter(), low = context.createBiquadFilter(), chorus = createChorus(context)
  const drive = context.createGain(), dry = context.createGain(), wet = context.createGain(), master = context.createGain()
  let convolver = context.createConvolver()
  body.type = 'peaking'; body.Q.value = 1.5; low.type = 'lowpass'; low.Q.value = .6
  drive.gain.value = 0; master.gain.value = 0
  lfo.connect(lfoDepth); lfoDepth.connect(trem.gain); lfo.start()
  const drift = context.createOscillator(), driftDepth = context.createGain()
  drift.frequency.value = 1 / 14; driftDepth.gain.value = 0; drift.connect(driftDepth); driftDepth.connect(low.detune); drift.start()
  const stemGains = players.map(() => context.createGain())  // one level per player: roles follow the drive differently (fx.trend)
  players.forEach((player, i) => { player.connect(stemGains[i]); stemGains[i].connect(vib) }); vib.connect(trem); trem.connect(body); body.connect(low); low.connect(chorus.input); chorus.output.connect(drive)
  drive.connect(dry); dry.connect(master); drive.connect(convolver); convolver.connect(wet); wet.connect(master); master.connect(analyser)
  const startedAt = context.currentTime + .03
  players.forEach(player => player.start(startedAt))
  const rig = { players, stemGains, granular, vib, vibLfo, vibDepth, trem, lfo, lfoDepth, drift, driftDepth, body, low, chorus, drive, dry, wet, master, startedAt, driveTarget: 0, size: 0, engineKey: '', rootHz: 0, pump: 0,
    setRoom(seconds: number) {
      // A new convolver per decay: reassigning .buffer is not allowed in every WebKit version.
      const next = context.createConvolver(), [left, right] = roomImpulse(context.sampleRate, seconds)
      const impulse = context.createBuffer(2, left.length, context.sampleRate)
      impulse.copyToChannel(left, 0); impulse.copyToChannel(right, 1); next.buffer = impulse
      drive.connect(next); next.connect(wet); drive.disconnect(convolver); convolver.disconnect(); convolver = next
    },
    dispose() {
      try { players.forEach(player => player.stop(context.currentTime)); lfo.stop(); vibLfo.stop(); drift.stop() } catch { /* already stopped */ }
      players.forEach(player => player.disconnect())
      ;[...stemGains, vib, vibLfo, vibDepth, drift, driftDepth, trem, lfo, lfoDepth, body, low, drive, dry, wet, master, convolver].forEach(node => node.disconnect()); chorus.dispose()
    } }
  return rig
}

export function applyFx(rig: ReturnType<typeof buildRig>, fx: Fx, rootHz: number, immediate = false) {
  const now = rig.master.context.currentTime
  const set = (param: AudioParam, value: number) => immediate ? param.setValueAtTime(value, now) : smoothParameter(param, value, now, .05)
  rig.rootHz = rootHz
  set(rig.low.Q, fx.res); set(rig.driftDepth.gain, fx.drift ? 1100 : 0)
  if (rig.pump !== fx.pump) {
    rig.pump = fx.pump
    // Ramp-up saw from 8 harmonics: gain dips at once, then swells back over the beat (no click from a hard edge).
    if (fx.pump) rig.lfo.setPeriodicWave(rig.lfo.context.createPeriodicWave(new Float32Array(9), Float32Array.from({ length: 9 }, (_, n) => n ? (n % 2 ? 1 : -1) / n : 0)))
    else rig.lfo.type = 'sine'
  }
  set(rig.body.frequency, fx.bodyHz); set(rig.body.gain, fx.bodyDb)
  set(rig.lfo.frequency, fx.tremRate); set(rig.lfoDepth.gain, fx.tremDepth / 2); set(rig.trem.gain, 1 - fx.tremDepth / 2)
  set(rig.vibLfo.frequency, fx.vibRate); set(rig.vibDepth.gain, fx.vibDepth / 1731 / (2 * Math.PI * fx.vibRate))
  rig.chorus.setAmount(fx.chorus, now)
  set(rig.dry.gain, 1 - fx.reverb * .5); set(rig.wet.gain, fx.reverb)
  if (Math.abs(rig.size - fx.size) > .01) { rig.size = fx.size; rig.setRoom(fx.size) }
  const engineKey = JSON.stringify([fx.rasp, fx.stage ?? null])
  if (rig.granular && rig.engineKey !== engineKey) {
    rig.engineKey = engineKey
    for (const player of rig.players as GranularPlayer[]) player.setEngine(fx.stage ? { baseHz: rootHz, rasp: fx.rasp, cabin: 0, ...fx.stage } : fx.rasp > 0 ? { baseHz: rootHz, rasp: fx.rasp, resonances: [], lowpassHz: 0, cabin: 0 } : null)
  }
}

export type Rig = ReturnType<typeof buildRig>

/** One control step (every 50 ms): pitch, level envelope and pedal-following tone from the driving input. */
export function driveRig(rig: Rig, motion: Pick<Motion, 'mode' | 'travel' | 'response'>, fx: Fx, input: DrivingInput, immediate = false, stale = false) {
  const now = rig.master.context.currentTime, current = rig
  const set = (param: AudioParam, value: number, smoothing: number) => immediate ? param.setValueAtTime(value, now) : smoothParameter(param, value, now, smoothing)
  if (!current.granular) {
    set(current.drive.gain, fx.gain ?? 1, .05); set(current.low.frequency, fx.tone, .05); return
  }
  const target = drivingSoundTargets(input, stale, motion.response, motion.mode as GranularMode, motion.travel)
  for (const player of current.players as GranularPlayer[]) {
    const rate = fx.peakHz && current.rootHz ? Math.min(target.rate, fx.peakHz / current.rootHz) : target.rate
    // Rising: pitch falls slower than it climbs (1 s vs 0.35 s), so hard braking glides down instead of swooping; Evolving's two crossfading
    // voices already hide a fast fall (2026-11-20: Rising dropped 3.5 semitones in the last 20 km/h of a 0.9 g stop, heard as a skip).
    set(player.playbackRate, rate, motion.mode === 'rise' && rate < player.playbackRate.value ? 1 : .35)
    set(player.evolution, motion.mode === 'evolving' ? 1 : 0, .05)
    set(player.cycleSpeed, target.cycleSpeed, .15)
    set(player.stage, target.stage, .35)
    set(player.loopHold, target.loopHold, .05)
  }
  const levels = fx.trend ? trendGains(fx.trend, input.speedKmh, target.propulsion) : null
  current.stemGains.forEach((gain, i) => set(gain.gain, levels ? levels[i] : 1, .35))
  const envelope = driveEnvelopeTarget(target.driveGain, responseRiseSeconds[motion.response], target.driveGain < current.driveTarget)
  current.driveTarget = target.driveGain
  set(current.drive.gain, envelope.gain * (fx.gain ?? 1), envelope.smoothing)
  set(current.low.frequency, clamp(fx.tone * 2 ** (fx.follow * (2 * target.propulsion - 1)), 200, 20000), .15)
}

/** Discovery playback: one candidate at a time, live driving or the 22 s simulated drive, through the same chain as Sound Lab. */
export class LabPlayer {
  analyser: AnalyserNode | null = null
  candidateId: string | null = null
  private audio: AudioContext | null = null
  private rig: Rig | null = null
  private timer = 0
  private input: 'live' | 'simulated' = 'live'
  private mode: GranularMode = 'rise'
  private request = 0  // every play/stop bumps it; a play still waiting (stems, worklet) when a newer one starts gives up
  volume = .7
  get playing() { return !!this.rig }
  /** stems may still be building (a promise): the wait happens here, so a click on another sound meanwhile cancels this one.
   * Before (2026-11-18), a sound that finished building late started a second rig nobody drove: it played on, deaf to the pedal.
   * Returns false when a newer play or a stop came first. */
  async play(id: string, stems: Float32Array[][] | Promise<Float32Array[][]>, fx: Fx, rootHz: number, input: 'live' | 'simulated', live: () => { input: DrivingInput | undefined; stale: boolean }, simulated: (t: number) => DrivingInput, mode: GranularMode = 'rise', travel = 1) {
    this.stop(); const request = this.request
    if (!this.audio) {
      this.audio = new AudioContext(); this.analyser = this.audio.createAnalyser(); this.analyser.fftSize = 2048; this.analyser.connect(this.audio.destination)
    }
    const context = this.audio
    let voices: Float32Array[][]
    try { voices = await stems; await context.resume(); await granularWorklet(context) }
    catch (problem) { if (request !== this.request) return false; throw problem }  // a stale failure must not stop the newer sound
    if (request !== this.request) return false
    this.mode = mode
    const motion = { mode, travel, response: 'exponential' as const }
    const rig = buildRig(context, sourceAudioBuffers(context, voices), mode, this.analyser!)
    applyFx(rig, fx, rootHz, true)
    this.rig = rig; this.candidateId = id; this.input = input
    const step = (immediate = false) => {
      if (this.rig !== rig) return
      const state = input === 'simulated' ? { input: simulated(context.currentTime - rig.startedAt), stale: false } : live()
      driveRig(rig, motion, fx, state.input ?? { running: false, starting: false, speedKmh: 0, throttle: 0, motorLoad: null }, immediate, state.stale)
    }
    step(true); this.timer = window.setInterval(() => step(), 50)
    rig.master.gain.setTargetAtTime(this.volume, context.currentTime, .05)
    return true as const
  }
  stop() {
    this.request++; window.clearInterval(this.timer)
    const rig = this.rig; this.rig = null; this.candidateId = null
    if (rig && this.audio) { rig.master.gain.setTargetAtTime(0, this.audio.currentTime, .03); window.setTimeout(rig.dispose, 200) }
  }
  context() { return { volume: this.volume, candidateId: this.candidateId, input: this.input, style: this.mode, response: 'exponential', spatial: true } }
  close() { this.stop(); void this.audio?.close(); this.audio = null }
}
