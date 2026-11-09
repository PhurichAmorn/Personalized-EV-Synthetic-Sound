import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import ts from '../desktop/node_modules/typescript/lib/typescript.js'
const code=ts.transpileModule(readFileSync('desktop/src/audioAutomation.ts','utf8'),{compilerOptions:{module:ts.ModuleKind.ES2022}}).outputText
const {smoothParameter,driveEnvelopeTarget}=await import(`data:text/javascript;base64,${Buffer.from(code).toString('base64')}`)
const events=[{type:'ramp',time:.12,value:0}]
const param={
 cancelAndHoldAtTime(time){events.splice(0,events.length,...events.filter(event=>event.time<time));events.push({type:'hold',time,value:.4})},
 setTargetAtTime(value,time,seconds){events.push({type:'target',value,time,seconds})}
}
smoothParameter(param,.9,.05,.15)
assert.deepEqual(events,[{type:'hold',time:.05,value:.4},{type:'target',value:.9,time:.05,seconds:.15}])
console.log('Re-acceleration cancels pending idle fade and holds current value before retargeting.')

const attack=driveEnvelopeTarget(1,1.4,false)
const level=time=>(attack.gain*(1-Math.exp(-time/attack.smoothing)))**2
assert.equal(level(0),0)
assert.ok(level(.1)<.06,'Full pedal must not immediately produce a loud onset')
assert.ok(Math.abs(level(1.4)-.95)<.002,'Displayed rise time must correspond to 95% output')
assert.equal(driveEnvelopeTarget(0,1.4,true).gain,0)
console.log('Soft onset stays below 6% at 100 ms and reaches 95% at the selected fade-in time.')
