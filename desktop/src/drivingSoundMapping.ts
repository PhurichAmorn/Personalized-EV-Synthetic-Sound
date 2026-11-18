import type { GranularMode } from './granularPlayer'
export type DrivingInput = { running: boolean; starting: boolean; speedKmh: number; throttle: number; brake?: number; motorLoad: number | null; rpm?: number; maxRpm?: number; power?: number; acceleration?: number }
const unit = (value: number) => Math.max(0, Math.min(1, Number.isFinite(value) ? value : 0))
const ease = (value: number) => { const x = unit(value); return x * x * (3 - 2 * x) }
/** Speed where Rise/Evolving pitch reaches its top. */
export const TOP_KMH = 140
export type SoundResponse = 'exponential' | 'linear' | 'logarithmic'
export const responseRiseSeconds: Record<SoundResponse, number> = { exponential: .8, linear: .65, logarithmic: .5 }
export function soundResponse(value: number, mode: SoundResponse) {
  const x = unit(value)
  if (x === 0 || x === 1) return x
  if (mode === 'exponential') return x * x
  if (mode === 'logarithmic') return Math.log1p(9 * x) / Math.log(10)
  return x
}
/** Power leads Steady; RPM/speed lead Rise/Evolving, with pedal/load presence and acceleration colour. */
/** travel: multiple of the usual pitch climb (1 = shared mapping); a family can climb further from the same resting pitch. */
export function drivingSoundTargets(input: DrivingInput, stale = false, response: SoundResponse = 'exponential', mode: GranularMode = 'evolving', travel = 1) {
  // Service brake overrides propulsion (as in the vehicle model): throttle must not drive the sound.
  const pedal = unit(input.brake ?? 0) > 0 ? 0 : unit(input.throttle)
  const load = input.motorLoad !== null && Number.isFinite(input.motorLoad) ? Math.max(-1, Math.min(1, input.motorLoad)) : null
  const power = load !== null && load < 0 ? 0 : unit(input.power ?? (load === null ? pedal : Math.max(0, load)))
  const effort = mode === 'steady' ? power : load === null ? pedal : unit(.35 * pedal + .65 * Math.max(0, load))
  const propulsion = soundResponse(effort, response)
  // Keep curve-shaped colour while giving partial pedal a responsive, continuous level.
  const speed = Math.max(0, Number.isFinite(input.speedKmh) ? input.speedKmh : 0)
  // Rise stays audible (softer) while rolling off the pedal, so slowing down is heard.
  const presence = Math.max(.65 * effort + .35 * propulsion, mode === 'rise' ? .004 * ease(speed / 20) : 0)  // faint (-24 dB; level goes through sqrt in driveEnvelopeTarget), .07 was still -11.5 dB (2026-11-18)
  const acceleration = mode !== 'steady' ? unit((input.acceleration ?? 0) / 4) : 0
  const regen = load === null ? 0 : Math.max(0, -load)
  const hasRpm = Number.isFinite(input.rpm) && Number.isFinite(input.maxRpm) && input.maxRpm! > 0
  // Even climb with speed up to TOP_KMH (the old curve spent half its climb by 50 km/h and then sounded stalled, 2026-11-18).
  // Rise climbs further and a little faster early (heard as too little climb, 2026-11-18); Evolving keeps the even climb.
  const speedRegister = mode === 'rise' ? unit(speed / 120) ** .75 : unit(speed / TOP_KMH)
  const motion = hasRpm ? unit(input.rpm! / (.12 * input.maxRpm!)) : unit(input.speedKmh / 15)
  const intent = unit((pedal - .03) / .12)
  const activity = mode === 'steady' ? 1 : Math.max(motion * motion * (3 - 2 * motion), intent * intent * (3 - 2 * intent))
  const pitchRegister = mode === 'steady' ? propulsion
    : .9 * speedRegister + .1 * power
  const highSpeed = Math.max(0, Number.isFinite(input.speedKmh) ? input.speedKmh - 100 : 0)
  // Quiet settled low-speed cruising, without weakening launch, strong demand or regen.
  const quietCruise = mode === 'evolving' && Number.isFinite(input.acceleration)
    ? ease(input.speedKmh / 5) * (1 - ease((input.speedKmh - 30) / 40))
      * (1 - ease((Math.max(pedal, power) - .25) / .4)) * (1 - ease((input.acceleration ?? 0) / .8))
    : 0
  // A little launch depth tapers away without raising the upper pitch endpoint.
  const launchDepth = 1 * (1 - pitchRegister) ** 2
  const semitones = -10 - launchDepth + (mode === 'steady' ? 9 : mode === 'rise' ? 13 : 11) * travel * pitchRegister + (mode === 'evolving' ? 4 * (1 - Math.exp(-highSpeed / 80)) : 0)
    + (mode === 'steady' ? 0 : (mode === 'rise' ? 6 : 0) * regen)  // regen sounds higher in Rising (up to +6 semitones); none in Evolving (+6, +3, +2 too high, 2026-11-18)
  return {
    cycleSpeed: mode === 'evolving' ? .25 + .75 * Math.max(pedal, power) : 1,
    // No parking: Evolving's sweeps follow speed stages (stage below); parked sweeps were heard as a stall (2026-11-18).
    loopHold: 0,
    stage: mode === 'evolving' ? speed / 40 : 0,  // Evolving Shepard position: one octave of rise per 40 km/h
    rate: Math.pow(2, semitones / 12), semitones,
    bodyGain: 1,
    padGain: .65 + .2 * propulsion,
    glassGain: .1 + propulsion * .25 + .08 * acceleration,
    airGain: 1,
    cutoff: 1300 + 900 * propulsion - 200 * regen + 350 * acceleration,
    driveGain: input.running && !input.starting && !stale ? activity * (.9 * presence * (1 - .6 * quietCruise) + .06 * regen) : 0,  // regen halved (-6 dB): heard as too loud, 2026-11-18
    propulsion, regen,
  }
}
