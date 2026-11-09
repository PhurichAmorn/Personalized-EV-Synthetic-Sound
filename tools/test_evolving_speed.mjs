import assert from 'node:assert/strict'
import {readFileSync} from 'node:fs'
import ts from '../desktop/node_modules/typescript/lib/typescript.js'
import {EvolvingEngine,SourceLoopEngine} from '../desktop/public/audio/granular-processor.mjs'
const code=ts.transpileModule(readFileSync('desktop/src/drivingSoundMapping.ts','utf8'),{compilerOptions:{target:ts.ScriptTarget.ES2022,module:ts.ModuleKind.ES2022}}).outputText
const {drivingSoundTargets}=await import(`data:text/javascript;base64,${Buffer.from(code).toString('base64')}`)
const input={running:true,starting:false,speedKmh:30,rpm:2500,maxRpm:12000,throttle:.2,power:.2,motorLoad:.2}
const low=drivingSoundTargets(input,false,'exponential','evolving')
const full=drivingSoundTargets({...input,throttle:1,power:1,motorLoad:1},false,'exponential','evolving')
assert.ok(low.cycleSpeed<full.cycleSpeed*.6,'Light input must slow the Evolving rise/repeat clock')
assert.equal(full.cycleSpeed,1,'Full input retains the existing phrase speed')
assert.equal(drivingSoundTargets({...input,throttle:1,power:0},false,'exponential','evolving').cycleSpeed,1,'Full pedal responds even before displayed power catches up')
assert.ok(drivingSoundTargets({...input,throttle:0,power:.7},false,'linear','evolving').cycleSpeed>low.cycleSpeed)
for(const mode of ['steady','rise'])assert.equal(drivingSoundTargets(input,false,'linear',mode).cycleSpeed,1)
const cruise={...input,speedKmh:20,acceleration:0}
const cruising=drivingSoundTargets(cruise,false,'exponential','evolving')
const accelerating=drivingSoundTargets({...cruise,acceleration:1},false,'exponential','evolving')
assert.ok(cruising.driveGain<accelerating.driveGain*.5,'Light low-speed cruise stays quieter than acceleration')
assert.equal(cruising.cycleSpeed,accelerating.cycleSpeed,'Cruise loudness does not secretly change the phrase clock')
assert.equal(drivingSoundTargets({...cruise,throttle:1,power:1,motorLoad:1},false,'exponential','evolving').driveGain,.9)
assert.equal(drivingSoundTargets({...cruise,throttle:0,power:0,motorLoad:0},false,'exponential','evolving').driveGain,0)
assert.ok(Math.abs(drivingSoundTargets({...cruise,throttle:0,power:0,motorLoad:-.7},false,'exponential','evolving').driveGain-.084)<1e-12)
const rate=8000,data=Float32Array.from({length:rate*5},(_,i)=>.1*Math.sin(2*Math.PI*175*i/rate))
const slow=new EvolvingEngine(data,rate),fast=new EvolvingEngine(data,rate),legacy=new EvolvingEngine(data,rate)
let previous=0,maxJump=0
for(let i=0;i<rate*3;i++){
 const value=slow.sample(.8,0,low.cycleSpeed)
 const fastValue=fast.sample(.8,0,1)
 assert.equal(fastValue,legacy.sample(.8),'Full phrase speed is sample-identical to the previous default')
 assert.ok(Number.isFinite(value));maxJump=Math.max(maxJump,Math.abs(value-previous));previous=value
}
assert.ok(slow.scanPosition<fast.scanPosition*.6)
for(let i=0;i<rate*2;i++){
 const value=slow.sample(.8,0,1);maxJump=Math.max(maxJump,Math.abs(value-previous));previous=value
}
assert.ok(maxJump<.1,'Changing cycle speed must not reset phrase phase or cause impulse jumps')
const held=new EvolvingEngine(data,rate)
for(let i=0;i<rate*12;i++)held.sample(.8,1,low.cycleSpeed)
const position=held.scanPosition
for(let i=0;i<rate;i++)held.sample(.9,1,1)
assert.equal(held.scanPosition,position,'High-speed hold still prevents phrase resets')
const shared=new SourceLoopEngine(data,rate)
for(let i=0;i<rate;i++)shared.sample(.8,0,1,low.cycleSpeed)
assert.ok(shared.renderer.scanPosition<rate*.6,'The shared live/offline wrapper forwards cycle speed')
console.log('Evolving phrase timing follows pedal/power, keeps full-speed audio, changes smoothly and retains high-speed hold.')
