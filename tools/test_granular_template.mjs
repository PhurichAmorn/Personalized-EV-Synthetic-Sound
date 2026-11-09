import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import ts from '../desktop/node_modules/typescript/lib/typescript.js'
async function moduleAt(path) {
  const code=ts.transpileModule(readFileSync(path,'utf8'), { compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.ES2022 } }).outputText
  return import(`data:text/javascript;base64,${Buffer.from(code).toString('base64')}`)
}
const { alignedGrainOffset }=await import('../desktop/public/audio/granular-processor.mjs')
const rate=48000
const data=Float32Array.from({length:rate},(_,i)=>Math.sin(2*Math.PI*175*i/rate)+.3*Math.sin(2*Math.PI*350*i/rate))
function error(a,b) {
  let sum=0
  for(let i=0;i<64;i++) {
    const index=offset=>((Math.round(offset*rate+i*8)%data.length)+data.length)%data.length
    sum+=(data[index(a)]-data[index(b)])**2
  }
  return sum/64
}
for (const scan of [.04,.08,.995]) {
  const reference=scan+.0025
  const result=alignedGrainOffset(data,rate,scan,reference,1)
  assert.ok(result>=0 && result<1)
  assert.ok(error(result,reference)<error(scan,reference)*.05,'Overlap should align waveform phase')
}
const silence=new Float32Array(rate)
assert.equal(alignedGrainOffset(silence,rate,.04,.043,1),.04)
const {drivingSoundTargets}=await moduleAt('desktop/src/drivingSoundMapping.ts')
const input={running:true,starting:false,speedKmh:0,throttle:0,motorLoad:0}
assert.equal(drivingSoundTargets(input).driveGain,0)
let last=-Infinity
for(let effort=0;effort<=100;effort++) {
  const value=effort/100
  const target=drivingSoundTargets({...input,speedKmh:30,throttle:value,motorLoad:value},false,'exponential','steady')
  assert.ok(target.semitones>=last && target.semitones>=-11 && target.semitones<=1)
  const shaped=value*value
  assert.ok(Math.abs(target.semitones-(-10+9*shaped-(1-shaped)**2))<1e-10)
  last=target.semitones
}
assert.equal(drivingSoundTargets({...input,speedKmh:20,throttle:.5,motorLoad:.5},false,'exponential','steady').semitones,drivingSoundTargets({...input,speedKmh:80,throttle:.5,motorLoad:.5},false,'exponential','steady').semitones,'Steady remains power-led')
assert.equal(drivingSoundTargets({...input,speedKmh:50},true).driveGain,0)
console.log('Grain phase alignment, wrap, silence, pitch range and idle/stale mute passed.')
const rolling={...input,speedKmh:8,maxRpm:12000,motorLoad:.5}
const levels=[0,150,300,600,1000,1440].map(rpm=>drivingSoundTargets({...rolling,rpm}).driveGain)
assert.equal(levels[0],0,'Zero RPM with no pedal must be silent')
for(let i=1;i<levels.length;i++) assert.ok(levels[i]>levels[i-1],'Level must rise smoothly across the low-RPM range')
assert.ok(levels[1]<levels.at(-1)*.1,'Near-stop level must already be quiet')
console.log('Low-RPM activity fades progressively to silence.')
const cruise={...input,speedKmh:60,rpm:5000,maxRpm:12000}
const powered=drivingSoundTargets({...cruise,throttle:.7,motorLoad:.7}).driveGain
const regenerating=drivingSoundTargets({...cruise,motorLoad:-.7}).driveGain
assert.equal(drivingSoundTargets(cruise).driveGain,0,'Coasting must not sustain an engine-like speed floor')
assert.ok(regenerating<powered*.22,'Regen must be much quieter than propulsion at the same speed')
assert.equal(drivingSoundTargets({...cruise,rpm:0,motorLoad:-1}).driveGain,0)
console.log('Coasting has no sustained floor; regen is restrained at the same speed.')
const {soundResponse}=await moduleAt('desktop/src/drivingSoundMapping.ts')
for(const mode of ['exponential','linear','logarithmic']) {
  assert.equal(soundResponse(0,mode),0)
  assert.equal(soundResponse(1,mode),1)
  let previous=0
  for(let i=0;i<=100;i++) {const value=soundResponse(i/100,mode);assert.ok(value>=previous && value<=1);previous=value}
}
assert.ok(soundResponse(.25,'exponential')<soundResponse(.25,'linear'))
assert.ok(soundResponse(.25,'linear')<soundResponse(.25,'logarithmic'))
const halfPedal={...cruise,throttle:.5,motorLoad:1}
assert.ok(drivingSoundTargets(halfPedal,false,'exponential').driveGain<drivingSoundTargets(halfPedal,false,'logarithmic').driveGain,'Motor load must not bypass the selected response curve')
console.log('Response curves have exact endpoints, ordered sensitivity, and load cannot bypass shaping.')
const {responseRiseSeconds}=await moduleAt('desktop/src/drivingSoundMapping.ts')
assert.ok(responseRiseSeconds.exponential>responseRiseSeconds.linear)
assert.ok(responseRiseSeconds.linear>responseRiseSeconds.logarithmic)
const atHalfSecond=seconds=>(1-Math.exp(-.5/(seconds/3.676)))**2
assert.ok(atHalfSecond(responseRiseSeconds.logarithmic)-atHalfSecond(responseRiseSeconds.exponential)>.1,'Full-throttle keyboard attack must differ between choices')
console.log('Keyboard full-throttle onset differs between the three response choices.')
const comfort={...cruise,power:.4,throttle:.5,motorLoad:.5,acceleration:0}
const steadyA=drivingSoundTargets(comfort,false,'linear','steady')
const steadyB=drivingSoundTargets({...comfort,speedKmh:150,rpm:12000,throttle:1,motorLoad:1,acceleration:4},false,'linear','steady')
assert.equal(steadyA.semitones,steadyB.semitones,'Steady pitch depends on power, not speed/load/pedal')
assert.equal(steadyA.driveGain,steadyB.driveGain,'Steady level depends on power, not speed')
assert.ok(drivingSoundTargets({...comfort,power:.9},false,'linear','steady').semitones>steadyA.semitones)
let previousRise=-Infinity
for(const speed of [0,20,50,90,120,160,220]) {
 const target=drivingSoundTargets({...comfort,speedKmh:speed},false,'linear','rise')
 assert.ok(target.semitones>previousRise && target.semitones<=1,'Rise keeps climbing beyond 90 km/h within the low register')
 previousRise=target.semitones
}
const sportBase=drivingSoundTargets(comfort,false,'linear','rise')
const sportAccel=drivingSoundTargets({...comfort,acceleration:3},false,'linear','rise')
assert.ok(sportAccel.cutoff>sportBase.cutoff,'Acceleration adds expression to Rise')
console.log('Steady is power-led; Rise climbs with speed and opens with acceleration.')
const launch={...cruise,speedKmh:15,rpm:500,maxRpm:12000,power:.2,throttle:.8,motorLoad:.8}
for(const mode of ['rise','evolving']) {
 const low=drivingSoundTargets(launch,false,'exponential',mode)
 const revved=drivingSoundTargets({...launch,rpm:3500},false,'exponential',mode)
 assert.ok(revved.semitones-low.semitones>2,'RPM must create an audible launch climb')
 assert.ok(revved.semitones<=1)
}
const lowPowerRise=drivingSoundTargets(launch,false,'linear','rise')
const highPowerRise=drivingSoundTargets({...launch,power:.9},false,'linear','rise')
assert.ok(highPowerRise.semitones>lowPowerRise.semitones,'Rise must also respond to power at the same RPM/speed')
assert.ok(drivingSoundTargets({...launch,power:.35},false,'exponential','steady').semitones>-12,'Steady must climb from its deeper start at low power')
console.log('Launch pitch responds clearly to RPM and power, with restrained upper register.')
const settleAt=speed=>drivingSoundTargets({...cruise,speedKmh:speed},false,'linear','evolving').loopHold
assert.equal(settleAt(99),0)
assert.equal(settleAt(99.9),0)
assert.equal(settleAt(100),1)
assert.equal(settleAt(110),1)
assert.equal(settleAt(120),1)
assert.equal(drivingSoundTargets({...cruise,speedKmh:120},false,'linear','rise').loopHold,0)
console.log('Evolving repeats normally below 100 km/h and switches to sustained sound at the threshold.')

for(const mode of ['steady','rise','evolving']) {
 const resting=drivingSoundTargets({...input,power:0,rpm:0,maxRpm:12000},false,'linear',mode)
 assert.equal(resting.semitones,-11,'Every mode starts with the same gentle one-semitone slowdown')
 const full=drivingSoundTargets({...cruise,power:1,throttle:1,motorLoad:1,rpm:12000,maxRpm:12000,speedKmh:300},false,'linear',mode)
 assert.ok(full.semitones>resting.semitones+8 && full.semitones<=(mode==='evolving'?5:1))
}
console.log('All GS modes have a deeper start and retain their upper-register headroom.')
let previousSustained=-Infinity
for(const speed of [100,110,130,160,220]) {
 const target=drivingSoundTargets({...cruise,speedKmh:speed},false,'linear','evolving')
 assert.equal(target.loopHold,1)
 assert.ok(target.rate>previousSustained,'Above 100 the non-looping tone must continue rising with speed')
 previousSustained=target.rate
}
console.log('Above 100, the sustained branch keeps climbing without bringing back phrase loops.')
// Rise starts slower/deeper, then rejoins the original upper register.
const launchRate=drivingSoundTargets({...input,power:0,rpm:0,maxRpm:12000},false,'linear','rise')
assert.equal(launchRate.semitones,-11)
assert.ok(Math.abs(launchRate.rate/2**(-10/12)-2**(-1/12))<1e-12)
let lastLaunchRate=0
for(let step=0;step<=100;step++) {
 const amount=step/100
 const target=drivingSoundTargets({...input,speedKmh:amount*200,rpm:amount*12000,maxRpm:12000,power:amount},false,'linear','rise')
 assert.ok(target.rate>=lastLaunchRate && Number.isFinite(target.rate))
 lastLaunchRate=target.rate
 if(step===100) assert.ok(target.semitones>.7,'Upper register stays close to the existing mapping')
}
console.log('Rise starts one semitone deeper and smoothly recovers its upper register.')

const evolvingLow=drivingSoundTargets({...launch,speedKmh:20},false,'linear','evolving')
const evolvingFast=drivingSoundTargets({...launch,speedKmh:80},false,'linear','evolving')
assert.ok(evolvingFast.rate>evolvingLow.rate,'Evolving must inherit speed-led Rise character below the hold threshold')
assert.ok(drivingSoundTargets({...launch,acceleration:3},false,'linear','evolving').cutoff>drivingSoundTargets({...launch,acceleration:0},false,'linear','evolving').cutoff)
for(const mode of ['steady','rise','evolving']) {
 const regen=drivingSoundTargets({...cruise,motorLoad:-.7},false,'linear',mode)
 assert.ok(Math.abs(regen.driveGain-.12*.7)<1e-12,'Regen gets the stronger shared level')
 assert.equal(drivingSoundTargets({...cruise,motorLoad:0},false,'linear',mode).driveGain,0,'Coasting stays silent')
}
