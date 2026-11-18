import assert from 'node:assert/strict'
import { build } from '../desktop/node_modules/esbuild/lib/main.js'
const out = await build({ entryPoints: ['desktop/src/stackVoice.ts'], bundle: true, write: false, format: 'esm', platform: 'node', logLevel: 'error' })
const { trendGains, stackStems } = await import('data:text/javascript;base64,' + Buffer.from(out.outputFiles[0].text).toString('base64'))
// trendGains: rest at zero drive, full at full drive; mix 0 follows the pedal only, mix 1 the speed only.
const t = { rest: [.8, .3, .1], full: [.5, .6, 1], mix: [0, .5, 1] }
assert.deepEqual(trendGains(t, 0, 0).map(v => +v.toFixed(6)), [.8, .3, .1])
assert.deepEqual(trendGains(t, 120, 1).map(v => +v.toFixed(6)), [.5, .6, 1])
assert.ok(Math.abs(trendGains(t, 120, 0)[0] - .8) < 1e-9, 'body follows the pedal, not the speed')
assert.ok(Math.abs(trendGains(t, 0, 1)[2] - .1) < 1e-9, 'top follows the speed, not the pedal')
assert.ok(Math.abs(trendGains(t, 60, 0)[2] - .55) < 1e-9, 'half speed, half way')
// Roles: with a trend the top layer is the top player, for 3, 4 and 5 layers; without it the old layout stays (3 layers: nothing in the top player but fifths).
const rms = c => Math.sqrt(c.reduce((s, v) => s + v * v, 0) / c.length)
for (const layers of [3, 4, 5]) {
  const base = { rootHz: 60, layers, timbres: [0, 1, 1, 1, 1], fall: .8, depth: 0, seed: 0, fifth: 0, shimmer: 0, spread: 0, peakHz: 200, peakDb: 0, cutoff: 3000 }
  const old = stackStems(base), roles = stackStems({ ...base, trend: { rest: [1, 1, 1], full: [1, 1, 1], mix: [0, 0, 0] } })
  assert.ok(rms(roles[2][0]) > 0, `${layers} layers: the top player plays the top layer`)
  if (layers === 3) assert.equal(rms(old[2][0]), 0, 'old layout: top player empty for 3 layers')
}
console.log('stack roles ok')
