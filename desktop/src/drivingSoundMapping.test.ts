import assert from 'node:assert/strict'
import test from 'node:test'
import { drivingSoundTargets } from './drivingSoundMapping.ts'

test('brake held with throttle stays silent at standstill (Rise and Evolving follow the pedal)', () => {
  for (const mode of ['rise', 'evolving'] as const) {
    const input = { running: true, starting: false, speedKmh: 0, throttle: 1, motorLoad: 0, power: 0 }
    assert.ok(drivingSoundTargets(input, false, 'exponential', mode).driveGain > 0, `${mode}: throttle alone sounds`)
    assert.equal(drivingSoundTargets({ ...input, brake: 1 }, false, 'exponential', mode).driveGain, 0, `${mode}: throttle+brake silent`)
  }
})

test('Evolving sweep scales per car: one octave per kmhPerOctave km/h, 80 when unknown', () => {
  const input = { running: true, starting: false, speedKmh: 80, throttle: .5, motorLoad: .5, power: .5 }
  assert.equal(drivingSoundTargets(input, false, 'exponential', 'evolving').stage, 1)
  assert.equal(drivingSoundTargets({ ...input, kmhPerOctave: 40 }, false, 'exponential', 'evolving').stage, 2)
})
