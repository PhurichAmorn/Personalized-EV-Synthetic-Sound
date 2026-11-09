import assert from 'node:assert/strict'
import {readFileSync} from 'node:fs'
import ts from '../desktop/node_modules/typescript/lib/typescript.js'
const code=ts.transpileModule(readFileSync('desktop/src/sourceDesigner.ts','utf8'),{compilerOptions:{target:ts.ScriptTarget.ES2022,module:ts.ModuleKind.ES2022}}).outputText
const {createSourceStems}=await import(`data:text/javascript;base64,${Buffer.from(code).toString('base64')}`)
const rate=8000,signal=createSourceStems({body:.7,character:.5,ensemble:0,movement:0},rate,'airy')[0][0]
let energy=0,pitched=0
for(const v of signal)energy+=v*v
energy/=signal.length
for(let harmonic=1;harmonic<=12;harmonic++)for(let detune=-3;detune<=3;detune++){
 const hz=174.8*harmonic+detune*.2
 let re=0,im=0
 for(let i=0;i<signal.length;i++){const p=2*Math.PI*hz*i/rate;re+=signal[i]*Math.cos(p);im+=signal[i]*Math.sin(p)}
 pitched+=2*(re*re+im*im)/signal.length**2
}
assert.ok(pitched/energy>.98,`Airy should be pitched rather than wind-like; harmonic energy ${pitched/energy}`)
console.log('Airy source concentrates energy around pitched partials rather than broadband wind.')
