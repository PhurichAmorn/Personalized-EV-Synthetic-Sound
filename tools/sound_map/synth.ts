// node synth.mjs batch.json outDir: renders each {id, plain} with the app's synth to outDir/id.f32 (mono loop, 48 kHz)
// and writes its partial list [[hz, amp]...] to outDir/id.json.
import { readFileSync, writeFileSync, mkdirSync } from 'node:fs'
import { createPlainSource, plainPartials, EXTRAS_OFF, type PlainParams } from '../../desktop/src/plainSource'

const [batch, outDir] = process.argv.slice(2)
mkdirSync(outDir, { recursive: true })
for (const { id, plain } of JSON.parse(readFileSync(batch, 'utf8')) as { id: string; plain: Partial<PlainParams> }[]) {
  const full = { ...EXTRAS_OFF, air: 0, ...plain } as PlainParams
  writeFileSync(`${outDir}/${id}.f32`, Buffer.from(createPlainSource(full)[0].buffer))
  writeFileSync(`${outDir}/${id}.json`, JSON.stringify(plainPartials(full).map(({ hz, amp }) => [hz, amp])))
}
