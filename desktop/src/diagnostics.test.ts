import assert from 'node:assert/strict'
import test from 'node:test'
import { spectrumBins } from './signal_bins.ts'

test('spectrum is reduced to bounded 0–2000 Hz bins', () => {
  const bins = spectrumBins([0, 1000, 2000, 2200], [-120, -45, 2, 0])
  assert.equal(bins.length, 96)
  assert.equal(bins[0], 0)
  assert.equal(bins[48], 45)
  assert.equal(bins[95], 90)
})
