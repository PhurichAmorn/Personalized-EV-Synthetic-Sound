import assert from 'node:assert/strict'
import {readFileSync} from 'node:fs'
import ts from '../desktop/node_modules/typescript/lib/typescript.js'
import {EvolvingEngine,SourceLoopEngine} from '../desktop/public/audio/granular-processor.mjs'
const code=ts.transpileModule(readFileSync('desktop/src/drivingSoundMapping.ts','utf8'),{compilerOptions:{target:ts.ScriptTarget.ES2022,module:ts.ModuleKind.ES2022}}).outputText
const {drivingSoundTargets}=await import(`data:text/javascript;base64,${Buffer.from(code).toString('base64')}`)
const input={running:true,starting:false,speedKmh:30,rpm:2500,maxRpm:12000,throttle:.2,power:.2,motorLoad:.2}
const low=drivingSoundTargets(input,false,'exponential','evolving')
const full=drivingSoundTargets({...input,throttle:1,power:1,motorLoad:1},false,'exponential','evolving')
assert.ok(low.cycleSpeed<full.cycleSpeed*.6,'Light input must soften the Evolving sweep')
assert.equal(full.cycleSpeed,1,'Full input retains the existing phrase speed')
assert.equal(drivingSoundTargets({...input,throttle:1,power:0},false,'exponential','evolving').cycleSpeed,1,'Full pedal responds even before displayed power catches up')
assert.ok(drivingSoundTargets({...input,throttle:0,power:.7},false,'linear','evolving').cycleSpeed>low.cycleSpeed)
for(const mode of ['steady','rise'])assert.equal(drivingSoundTargets(input,false,'linear',mode).cycleSpeed,1)
const cruise={...input,speedKmh:20,acceleration:0}
const cruising=drivingSoundTargets(cruise,false,'exponential','evolving')
const accelerating=drivingSoundTargets({...cruise,acceleration:1},false,'exponential','evolving')
assert.ok(cruising.driveGain<accelerating.driveGain*.5,'Light low-speed cruise stays quieter than acceleration')
assert.equal(cruising.cycleSpeed,accelerating.cycleSpeed,'Cruise loudness does not secretly change the sweep depth')
assert.equal(drivingSoundTargets({...cruise,throttle:1,power:1,motorLoad:1},false,'exponential','evolving').driveGain,.9)
assert.equal(drivingSoundTargets({...cruise,throttle:0,power:0,motorLoad:0},false,'exponential','evolving').driveGain,0)
assert.ok(Math.abs(drivingSoundTargets({...cruise,throttle:0,power:0,motorLoad:-.7},false,'exponential','evolving').driveGain-.042)<1e-12)
const rate=8000,data=Float32Array.from({length:rate*5},(_,i)=>.1*Math.sin(2*Math.PI*175*i/rate))
const atStage=stage=>{const e=new SourceLoopEngine(data,rate);let sum=0;for(let i=0;i<rate;i++)sum+=Math.abs(e.sample(.8,0,1,1,stage));return sum}
assert.notEqual(atStage(0),atStage(.5),'The shared live/offline wrapper forwards the speed stage')
console.log('Evolving pedal sets loudness; the wrapper forwards the speed stage.')
