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
