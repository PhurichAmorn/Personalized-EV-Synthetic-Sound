// node out/orchestra.mjs outDir: layered "orchestral" sounds (several Sound Lab source families stacked on one root) through the app's
// driving chain (chain.ts render), Rising and Evolving. Output per sound and mode: outDir/id.mode.f32 (left then right, pre-reverb,
// drive gain held at 1) and outDir/id.mode.gain.json; orchestra.py adds drive gain and room, writes WAVs and measures S, R, F.
// Octaves only: a fifth over the 87 Hz root (cluster or pure tone) put strong partials 87 Hz apart and read as roughness 0.38-0.59.
// Experiment (2026-11-17): does stacking cello, strings, choir, glass and clusters give the "more dimensions" an orchestral or
// cinematic sound needs? All layers share one player, so they rise together; each layer's pitch is a whole ratio of the root.
import { writeFileSync, mkdirSync, existsSync } from 'node:fs'
import { roomImpulse } from '../../desktop/src/plainSource'
import { createSourceStems, DEFAULT_SOURCE_CONTROLS, type SourceFamily, type SourceControls } from '../../desktop/src/sourceDesigner'
import { SEARCH_FIXED } from '../../desktop/src/levels'
import type { Fx } from '../../desktop/src/labEngine'
import { render } from './chain'

const ROOT = 87.4  // Hz at rest; every layer is root x ratio
const REGISTER: Partial<Record<SourceFamily, number>> = { orchestra: .6, evolution: .45 }  // sourceDesigner registers (loop root = 174.8 x register x rootRatio)
type Layer = { family: SourceFamily; ratio: number; level: number; controls?: Partial<SourceControls> }
export const SOUNDS: { id: string; name: string; idea: string; layers: Layer[]; fx: Partial<Fx> }[] = [
  { id: 'cinematic', name: 'Cinematic swell', idea: 'strings foundation, solo cello an octave up (at the root it read as roughness 0.35), glass shimmer two octaves up (loops allow at most 4x the root)',
    layers: [{ family: 'bowed', ratio: 1, level: .8, controls: { body: .9, ensemble: .3 } }, { family: 'orchestra', ratio: 2, level: .8 },
             { family: 'glass', ratio: 4, level: .22, controls: { movement: .8 } }],
    fx: { chorus: .8, reverb: .45, size: 3, vibDepth: 2, tone: 3500, follow: .6 } },
  { id: 'choral', name: 'Choral glow', idea: 'low strings, choir an octave up, glass shimmer on top',
    layers: [{ family: 'bowed', ratio: 1, level: .9, controls: { body: .8 } }, { family: 'vocal', ratio: 2, level: .6 },
             { family: 'glass', ratio: 4, level: .18, controls: { movement: .9 } }],
    fx: { chorus: .6, reverb: .5, size: 3, vibDepth: 1.5, tone: 4000, follow: .5 } },
  { id: 'electric', name: 'Electric pulse', idea: 'bright electric tone as the base, a pure tone an octave up and glass on top, with a slow pump (1.6 Hz); no strings or choir, so it is not a second Choral glow',
    layers: [{ family: 'evolution', ratio: 1, level: .7, controls: { character: .6 } }, { family: 'rounded', ratio: 2, level: .4 },
             { family: 'glass', ratio: 4, level: .2, controls: { movement: .8 } }],
    fx: { chorus: .2, reverb: .25, size: 2.5, vibDepth: 0, tone: 5000, follow: .8, pump: 1, tremDepth: .35, tremRate: 1.6 } },
]

const rms = (x: Float32Array) => Math.sqrt(x.reduce((s, v) => s + v * v, 0) / x.length)
function layered(layers: Layer[]) {
  const sum = [new Float32Array(48000 * 5), new Float32Array(48000 * 5)]
  for (const { family, ratio, level, controls } of layers) {
    const rootRatio = ROOT * ratio / (174.8 * (REGISTER[family] ?? 1))
    const stems = createSourceStems({ ...DEFAULT_SOURCE_CONTROLS, ...controls }, 48000, family, { rootRatio })
    const ch = [0, 1].map(c => Float32Array.from(stems[0][c], (v, i) => v + stems[1][c][i] + stems[2][c][i]))
    const scale = level / Math.max(rms(ch[0]), 1e-9)  // each layer at its own level, whatever the family's loudness
    for (const c of [0, 1]) for (let i = 0; i < ch[c].length; i++) sum[c][i] += ch[c][i] * scale
  }
  const peak = Math.max(...sum.map(c => c.reduce((m, v) => Math.max(m, Math.abs(v)), 0)))
  return sum.map(c => c.map(v => v / peak * .5))
}

const outDir = process.argv[2]
mkdirSync(outDir, { recursive: true })
for (const { id, layers, fx } of SOUNDS) {
  const size = fx.size ?? SEARCH_FIXED.size, room = `${outDir}/room-${size}.f32`
  if (!existsSync(room)) { const [a, b] = roomImpulse(48000, size); const ir = new Float32Array(2 * a.length); ir.set(a); ir.set(b, a.length); writeFileSync(room, ir) }
  const loop = layered(layers)
  for (const mode of ['rise', 'evolving'] as const) {
    const { out, gains } = render(loop, ROOT, { ...SEARCH_FIXED, ...fx } as Fx, mode)
    writeFileSync(`${outDir}/${id}.${mode}.f32`, out); writeFileSync(`${outDir}/${id}.${mode}.gain.json`, JSON.stringify(gains))
  }
}
writeFileSync(`${outDir}/sounds.json`, JSON.stringify(SOUNDS))
