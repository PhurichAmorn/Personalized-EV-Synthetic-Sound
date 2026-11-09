import assert from 'node:assert/strict'
import {readFileSync} from 'node:fs'
import ts from '../desktop/node_modules/typescript/lib/typescript.js'
const code=ts.transpileModule(readFileSync('desktop/src/simulatedDrive.ts','utf8'),{compilerOptions:{target:ts.ScriptTarget.ES2022,module:ts.ModuleKind.ES2022}}).outputText
const {simulatedDrive,SIMULATED_DRIVE_SECONDS}=await import(`data:text/javascript;base64,${Buffer.from(code).toString('base64')}`)
assert.equal(SIMULATED_DRIVE_SECONDS,22)
assert.equal(simulatedDrive(0).speedKmh,0)
assert.equal(simulatedDrive(14).speedKmh,120)
assert.ok(simulatedDrive(18).motorLoad<0)
assert.equal(simulatedDrive(22).speedKmh,0)
for(const time of [-1,0,3.4,10,18,22,99,NaN]) {
 const input=simulatedDrive(time)
 assert.deepEqual(input,simulatedDrive(time),'Replay is deterministic')
 assert.ok(Object.values(input).every(x=>typeof x==='boolean'||Number.isFinite(x)))
 assert.ok(input.speedKmh>=0&&input.speedKmh<=120)
}
console.log('Style audition uses a deterministic bounded acceleration, cruise, regen and stop trace.')
