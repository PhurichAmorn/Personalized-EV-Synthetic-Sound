import assert from 'node:assert/strict'
import {readFileSync} from 'node:fs'
import ts from '../desktop/node_modules/typescript/lib/typescript.js'
async function load(path){const code=ts.transpileModule(readFileSync(path,'utf8'),{compilerOptions:{target:ts.ScriptTarget.ES2022,module:ts.ModuleKind.ES2022}}).outputText;return import(`data:text/javascript;base64,${Buffer.from(code).toString('base64')}`)}
const {drivingSoundTargets,responseRiseSeconds}=await load('desktop/src/drivingSoundMapping.ts')
const {driveEnvelopeTarget}=await load('desktop/src/audioAutomation.ts')
const base={running:true,starting:false,speedKmh:5,rpm:350,maxRpm:12000,throttle:.2,motorLoad:.2,power:.2,acceleration:1}
for(const mode of ['steady','rise','evolving']){
 const light=drivingSoundTargets(base,false,'exponential',mode)
 assert.ok(light.driveGain>=.1&&light.driveGain<.2,`${mode}: light pedal needs presence without a full-throttle level`)
 const half=drivingSoundTargets({...base,throttle:.5,motorLoad:.5,power:.5},false,'exponential',mode)
 assert.ok(half.driveGain>light.driveGain)
 const full=drivingSoundTargets({...base,throttle:1,motorLoad:1,power:1,speedKmh:100000,rpm:12000},false,'exponential',mode)
 assert.equal(full.driveGain,.9,'Full-throttle level stays unchanged')
 assert.ok(Math.abs(full.semitones-({steady:-1,rise:1,evolving:5}[mode]))<1e-9,'Upper pitch endpoint stays unchanged')
 const rest=drivingSoundTargets({...base,power:0,throttle:0,motorLoad:0,speedKmh:0,rpm:0},false,'exponential',mode)
 assert.equal(rest.semitones,-11,'Raise starting pitch three semitones, retaining a deep launch')
 assert.equal(rest.driveGain,0,'No idle floor')
 assert.equal(drivingSoundTargets({...base,running:false},false,'exponential',mode).driveGain,0)
 assert.equal(drivingSoundTargets(base,true,'exponential',mode).driveGain,0)
 const coast={...base,power:0,throttle:0,motorLoad:0,speedKmh:50,rpm:4000}
 assert.equal(drivingSoundTargets(coast,false,'exponential',mode).driveGain,0)
 assert.ok(Math.abs(drivingSoundTargets({...coast,motorLoad:-.7},false,'exponential',mode).driveGain-.084)<1e-12,'Regen level stays unchanged')
 console.log(mode,JSON.stringify({light_gain:light.driveGain,half_gain:half.driveGain,light_pitch:light.semitones}))
}
assert.ok(responseRiseSeconds.exponential<=.9,'Controller onset should not take nearly two seconds')
const env=driveEnvelopeTarget(.9,responseRiseSeconds.exponential,false)
const level=t=>(env.gain*(1-Math.exp(-t/env.smoothing)))**2
assert.equal(level(0),0);assert.ok(level(.1)<.15,'Shorter onset still ramps rather than jumping')
assert.ok(level(.8)>.9*.94)
console.log('Partial pedal is audible sooner, starts less deeply, and preserves full input, regen and silence limits.')
