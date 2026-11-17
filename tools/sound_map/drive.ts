// node drive.mjs batch.json outDir: renders each {id, voice, fx, modes} (voice: mapVoice.ts) through the app's driving chain (chain.ts).
// Output per mode: outDir/id.mode.f32 = left then right (pre-reverb, drive gain held at 1) and outDir/id.mode.gain.json
// (drive gain every 50 ms step). Reverb (convolver) is added in drive.py; room impulses go to outDir/room-<size>.f32.
import { readFileSync, writeFileSync, mkdirSync, existsSync } from 'node:fs'
import { roomImpulse } from '../../desktop/src/plainSource'
import { SEARCH_FIXED } from '../../desktop/src/levels'
import { driveSound } from './chain'
import type { MapVoice } from '../../desktop/src/mapVoice'

const [batch, outDir] = process.argv.slice(2)
mkdirSync(outDir, { recursive: true })
for (const { id, voice, fx, modes } of JSON.parse(readFileSync(batch, 'utf8')) as { id: string; voice: MapVoice; fx: { size?: number }; modes: ('rise' | 'evolving')[] }[]) {
  const size = fx.size ?? SEARCH_FIXED.size, room = `${outDir}/room-${size}.f32`
  if (!existsSync(room)) { const [a, b] = roomImpulse(48000, size); const ir = new Float32Array(2 * a.length); ir.set(a); ir.set(b, a.length); writeFileSync(room, ir) }
  for (const mode of modes) {
    const { out, gains } = driveSound(voice, fx, mode)
    writeFileSync(`${outDir}/${id}.${mode}.f32`, out); writeFileSync(`${outDir}/${id}.${mode}.gain.json`, JSON.stringify(gains))
  }
}
