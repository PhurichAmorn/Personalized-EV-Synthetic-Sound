import assert from 'node:assert/strict'
import test from 'node:test'
import { createSourceStems, DEFAULT_SOURCE_CONTROLS } from './sourceDesigner.ts'

const pad = (family: 'glass' | 'rounded', companionSub?: number) => createSourceStems(DEFAULT_SOURCE_CONTROLS, 8000, family, companionSub === undefined ? {} : { companionSub })[1][0]
const differs = (a: Float32Array, b: Float32Array) => a.some((value, i) => value !== b[i])

test('companionSub switches the pad tuning and defaults to the original', () => {
  assert.ok(!differs(pad('glass'), pad('glass', 0)), 'explicit 0 equals default')
  assert.ok(differs(pad('glass'), pad('glass', 1)), 'sub-octave tuning changes the pad')
  assert.ok(differs(pad('rounded'), pad('rounded', 1)), 'sub-octave overrides the rounded set too')
})

test('companionSub outside 0..1 is rejected', () => {
  assert.throws(() => pad('glass', 2), /Invalid source structure parameter/)
})

test('every family renders finite, bounded audio that loops without a jump', () => {
  for (const family of ['bowed', 'rounded', 'vocal', 'glass', 'resonant', 'airy', 'engine', 'orchestra', 'evolution', 'supersonic'] as const) {
    const stems = createSourceStems(DEFAULT_SOURCE_CONTROLS, 8000, family)
    for (const channel of stems.flat()) {
      assert.ok(channel.every(Number.isFinite), family)
      assert.ok(Math.max(...channel.map(Math.abs)) <= .7 + 1e-6, family)
      const step = Math.max(...channel.slice(1).map((value, i) => Math.abs(value - channel[i])))
      assert.ok(Math.abs(channel[0] - channel[channel.length - 1]) <= step * 1.5 + 1e-6, `${family} loop seam`)
    }
  }
})
