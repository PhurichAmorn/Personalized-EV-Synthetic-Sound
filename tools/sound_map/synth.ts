// node synth.mjs batch.json outDir: renders each {id, voice} (desktop/src/mapVoice.ts: plain synth or blocks) to outDir/id.f32
// (mono loop of the three stems, 48 kHz). For the plain synth it also writes the partial list [[hz, amp]...] to outDir/id.json;
// blocks has no partial list there, so the check reads its partials off the loop's spectrum.
import { readFileSync, writeFileSync, mkdirSync } from 'node:fs'
import { plainPartials, EXTRAS_OFF, type PlainParams } from '../../desktop/src/plainSource'
import { mapStems, type MapVoice } from '../../desktop/src/mapVoice'

const [batch, outDir] = process.argv.slice(2)
mkdirSync(outDir, { recursive: true })
for (const { id, voice } of JSON.parse(readFileSync(batch, 'utf8')) as { id: string; voice: MapVoice }[]) {
  const stems = mapStems(voice)
  writeFileSync(`${outDir}/${id}.f32`, Buffer.from(Float32Array.from(stems[0][0], (v, i) => v + stems[1][0][i] + stems[2][0][i]).buffer))
  if (voice.kind === 'plain') writeFileSync(`${outDir}/${id}.json`, JSON.stringify(plainPartials({ ...EXTRAS_OFF, air: 0, ...voice.plain } as PlainParams).map(({ hz, amp }) => [hz, amp])))
}
