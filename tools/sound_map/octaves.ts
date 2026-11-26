// node out/octaves.mjs outDir: "octave stack" sources, a Shepard-like layered texture that behaves like a normal sound.
// The loop holds the same note in several octaves (55 Hz up), each octave layer with its own timbre and its own slow level drift
// (whole cycles per 5 s loop, so the loop stays seamless), and the app's granular player raises the pitch with speed as for every
// other sound (Rising and Evolving). A fixed low peak and low-pass after the player (the app's after-player stage, as for the engine
// and cello) stay put while the pitch climbs, so upper layers thin out and lower ones fill in: layered, deep, no endless rise.
// Output as orchestra.ts (id.mode.f32, id.mode.gain.json); orchestra.py adds gain and room, writes WAVs and measures S, R, F.
import { writeFileSync, mkdirSync, existsSync } from 'node:fs'
import { roomImpulse } from '../../desktop/src/plainSource'
import { SEARCH_FIXED } from '../../desktop/src/levels'
import type { Fx } from '../../desktop/src/labEngine'
import { render } from './chain'

const FS = 48000, FRAMES = FS * 5, ROOT = 55  // every partial a multiple of 0.2 Hz: seamless 5 s loop
type Timbre = 'sine' | 'strings' | 'hollow' | 'glass'
// Partials per timbre: [harmonic multiple, level]. Glass: bell-like inharmonic modes rounded to the loop grid.
const TIMBRES: Record<Timbre, [number, number][]> = {
  sine: [[1, 1]],
  strings: [[1, 1], [2, .4], [3, .2], [4, .1], [5, .05]],
  hollow: [[1, 1], [3, .3], [5, .12], [7, .05]],
  glass: [[1, 1], [2.76, .35], [5.4, .15]],
}
type Layer = { octave: number; timbre: Timbre; level: number; drift: number; depth: number }  // drift: level cycles per loop (0.2 Hz each)
export const SOUNDS: { id: string; name: string; idea: string; layers: Layer[]; stage: { resonances: [number, number, number][]; lowpassHz: number }; fx: Partial<Fx> }[] = [
  { id: 'octave-organ', name: 'Octave organ', idea: 'the same note in five octaves (55 Hz up), plain tones, each octave swelling slowly at its own pace; low peak at 110 Hz',
    layers: [0, 1, 2, 3, 4].map((o, i) => ({ octave: o, timbre: 'sine', level: [1, .9, .7, .45, .25][i], drift: [1, 2, 3, 1, 2][i], depth: .25 })),
    stage: { resonances: [[110, 6, .8]], lowpassHz: 900 }, fx: { reverb: .4, size: 3, chorus: .3 } },
  { id: 'layered-strings', name: 'Layered strings', idea: 'string-like tone in four octaves, each octave drifting on its own so the layers trade places; low peak at 110 Hz',
    layers: [0, 1, 2, 3].map((o, i) => ({ octave: o, timbre: 'strings', level: [1, .8, .5, .25][i], drift: [1, 2, 1, 3][i], depth: .35 })),
    stage: { resonances: [[110, 5, .8]], lowpassHz: 1200 }, fx: { reverb: .5, size: 3, chorus: .5 } },
  { id: 'texture-stack', name: 'Texture stack', idea: 'a different texture per octave: plain sub at the bottom, strings in the middle, hollow above, glass shimmer on top; each drifts on its own',
    layers: [{ octave: 0, timbre: 'sine', level: 1, drift: 1, depth: .15 }, { octave: 1, timbre: 'strings', level: .8, drift: 2, depth: .3 },
             { octave: 2, timbre: 'hollow', level: .45, drift: 3, depth: .35 }, { octave: 3, timbre: 'glass', level: .18, drift: 1, depth: .5 }],
    stage: { resonances: [[110, 5, .8], [440, 2, 1.2]], lowpassHz: 1800 }, fx: { reverb: .45, size: 3, chorus: .4 } },
  { id: 'deep-hollow', name: 'Deep hollow stack', idea: 'hollow, clarinet-like tone in four octaves, darker: low peak at 82 Hz and a low-pass at 700 Hz',
    layers: [0, 1, 2, 3].map((o, i) => ({ octave: o, timbre: 'hollow', level: [1, .75, .45, .2][i], drift: [2, 1, 3, 2][i], depth: .3 })),
    stage: { resonances: [[82, 6, .7]], lowpassHz: 700 }, fx: { reverb: .35, size: 2.5, chorus: .3 } },
]

function loop(layers: Layer[]) {
  const out = [new Float32Array(FRAMES), new Float32Array(FRAMES)]
  layers.forEach((L, li) => {
    for (const [h, a] of TIMBRES[L.timbre]) {
      const f = Math.round(ROOT * 2 ** L.octave * h * 5) / 5; if (f > FS * .45) continue
      for (let c = 0; c < 2; c++) {
        const start = (c * .29 + li * .43 + h * .17) % 1, sway = c * .25  // ears and layers start apart: width without detuning
        for (let i = 0; i < FRAMES; i++) {
          const env = 1 - L.depth / 2 + L.depth / 2 * Math.sin(2 * Math.PI * (L.drift * i / FRAMES + li * .3 + sway))
          out[c][i] += L.level * a * env * Math.sin(2 * Math.PI * (f * i / FS + start))
        }
      }
    }
  })
  const peak = Math.max(...out.map(c => c.reduce((m, v) => Math.max(m, Math.abs(v)), 0)))
  return out.map(c => c.map(v => v / peak * .5))
}

const outDir = process.argv[2]
mkdirSync(outDir, { recursive: true })
for (const s of SOUNDS) {
  const fx = { ...SEARCH_FIXED, ...s.fx } as Fx, room = `${outDir}/room-${fx.size}.f32`
  if (!existsSync(room)) { const [a, b] = roomImpulse(48000, fx.size); const ir = new Float32Array(2 * a.length); ir.set(a); ir.set(b, a.length); writeFileSync(room, ir) }
  const source = loop(s.layers)
  for (const mode of ['rise', 'evolving'] as const) {
    const { out, gains } = render(source, ROOT, fx, mode, s.stage)
    writeFileSync(`${outDir}/${s.id}.${mode}.f32`, out); writeFileSync(`${outDir}/${s.id}.${mode}.gain.json`, JSON.stringify(gains))
  }
}
writeFileSync(`${outDir}/sounds.json`, JSON.stringify(SOUNDS.map(s => ({ ...s, fx: { ...s.fx } }))))
