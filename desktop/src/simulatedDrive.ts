import type { DrivingInput } from './drivingSoundMapping'
export const SIMULATED_DRIVE_SECONDS = 22
const knots = [
  [0,0,0,0,0], [1,0,0,0,0], [3,20,.35,.55,.6], [7,60,.6,.8,.8],
  [11,110,.8,1,1], [14,120,.55,.6,.55], [16,100,0,0,-.4], [19,40,0,0,-.6], [22,0,0,0,0],
]
/** Identical listening trace for each style, independent of live vehicle telemetry. */
export function simulatedDrive(time: number): DrivingInput {
  const t = Math.max(0, Math.min(SIMULATED_DRIVE_SECONDS, Number.isFinite(time) ? time : 0))
  let index = 0
  while (index < knots.length - 2 && t > knots[index + 1][0]) index++
  const a = knots[index], b = knots[index + 1], amount = (t - a[0]) / (b[0] - a[0])
  const value = a.map((start, i) => start + (b[i] - start) * amount)
  return { running: true, starting: false, speedKmh: value[1], power: value[2], throttle: value[3], motorLoad: value[4], rpm: value[1] / 160 * 12000, maxRpm: 12000, acceleration: (b[1] - a[1]) / 3.6 / (b[0] - a[0]) }
}
