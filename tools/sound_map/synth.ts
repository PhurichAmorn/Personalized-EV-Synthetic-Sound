// node synth.mjs batch.json outDir: renders each {id, plain} with the app's synth to outDir/id.f32 (mono loop, 48 kHz).
import { readFileSync, writeFileSync, mkdirSync } from 'node:fs'
import { createPlainSource, EXTRAS_OFF, type PlainParams } from '../../desktop/src/plainSource'

const [batch, outDir] = process.argv.slice(2)
mkdirSync(outDir, { recursive: true })
for (const { id, plain } of JSON.parse(readFileSync(batch, 'utf8')) as { id: string; plain: Partial<PlainParams> }[])
  writeFileSync(`${outDir}/${id}.f32`, Buffer.from(createPlainSource({ ...EXTRAS_OFF, air: 0, ...plain } as PlainParams)[0].buffer))
