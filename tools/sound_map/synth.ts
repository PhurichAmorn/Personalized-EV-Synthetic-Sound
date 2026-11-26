// node synth.mjs batch.json outDir: renders each {id, voice} (desktop/src/mapVoice.ts: plain synth or blocks) to outDir/id.f32
// (mono loop of the three stems, 48 kHz; a 'stack' voice with its after-player stage applied). For the plain synth it also writes the partial list [[hz, amp]...] to outDir/id.json;
// blocks has no partial list there, so the check reads its partials off the loop's spectrum.
import { readFileSync, writeFileSync, mkdirSync } from 'node:fs'
import { plainPartials, EXTRAS_OFF, type PlainParams } from '../../desktop/src/plainSource'
import { mapStems, mapStage, mapRootHz, mapTrend, type MapVoice } from '../../desktop/src/mapVoice'
// @ts-expect-error plain JS module shared with the AudioWorklet
import { EngineStage } from '../../desktop/public/audio/granular-processor.mjs'

const [batch, outDir] = process.argv.slice(2)
mkdirSync(outDir, { recursive: true })
for (const { id, voice } of JSON.parse(readFileSync(batch, 'utf8')) as { id: string; voice: MapVoice }[]) {
  const stems = mapStems(voice)
  const full = mapTrend(voice)?.full ?? [1, 1, 1]  // roles: the quick check judges the sound with every player at its full-drive level
  let loop = Float32Array.from(stems[0][0], (v, i) => v * full[0] + stems[1][0][i] * full[1] + stems[2][0][i] * full[2])
  const stage = mapStage(voice)
  if (stage) {  // stack: its fixed after-player stage at the loop's own pitch (approximate: in the drive it stays put while pitch moves)
    const engine = new EngineStage({ baseHz: mapRootHz(voice), rasp: 0, cabin: 0, ...stage }, 48000), out = new Float32Array(loop.length)
    for (let pass = 0; pass < 2; pass++) for (let i = 0; i < loop.length; i++) out[i] = engine.process(loop[i], loop[i], 1)[0]  // second pass: filters settled
    loop = out
  }
  writeFileSync(`${outDir}/${id}.f32`, Buffer.from(loop.buffer))
  if (voice.kind === 'plain') writeFileSync(`${outDir}/${id}.json`, JSON.stringify(plainPartials({ ...EXTRAS_OFF, air: 0, ...voice.plain } as PlainParams).map(({ hz, amp }) => [hz, amp])))
}
