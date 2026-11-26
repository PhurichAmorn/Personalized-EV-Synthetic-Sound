import assert from 'node:assert/strict'
import test from 'node:test'
import { analyse } from './signalAnalysis.ts'

test('finds the two strongest partials and the level of a two-tone frame', () => {
  const rate = 48000, samples = Array.from({ length: 2048 }, (_, i) => .5 * Math.sin(2 * Math.PI * 220 * i / rate) + .2 * Math.sin(2 * Math.PI * 660 * i / rate))
  const { top, level } = analyse({ rate, samples, source: 'app' })
  assert.ok(Math.abs(top[0].f - 220) < 3, `first ${top[0].f}`)
  assert.ok(Math.abs(top[1].f - 660) < 3, `second ${top[1].f}`)
  assert.ok(Math.abs(level - 10 * Math.log10((.5 ** 2 + .2 ** 2) / 2)) < .5, `level ${level}`)
})
