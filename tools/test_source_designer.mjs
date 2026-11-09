import assert from 'node:assert/strict'
import {readFileSync} from 'node:fs'
import ts from '../desktop/node_modules/typescript/lib/typescript.js'
const code=ts.transpileModule(readFileSync('desktop/src/sourceDesigner.ts','utf8'),{compilerOptions:{target:ts.ScriptTarget.ES2022,module:ts.ModuleKind.ES2022}}).outputText
const {createSourceStems,DEFAULT_SOURCE_CONTROLS}=await import(`data:text/javascript;base64,${Buffer.from(code).toString('base64')}`)
const rate=8000
const mix=stems=>Float32Array.from(stems[0][0],(_,i)=>stems.reduce((sum,stem)=>sum+stem[0][i],0))
const rms=data=>Math.sqrt(data.reduce((sum,v)=>sum+v*v,0)/data.length)
const baseline=createSourceStems(DEFAULT_SOURCE_CONTROLS,rate)
assert.equal(baseline.length,3)
assert.equal(baseline[0].length,2)
assert.deepEqual(baseline,createSourceStems(DEFAULT_SOURCE_CONTROLS,rate),'Generation must be repeatable')
for(const key of Object.keys(DEFAULT_SOURCE_CONTROLS)) {
 const endpoints=[0,1].map(value=>createSourceStems({...DEFAULT_SOURCE_CONTROLS,[key]:value},rate))
 const a=mix(endpoints[0]),b=mix(endpoints[1])
 assert.ok(rms(a.map((v,i)=>v-b[i]))>.005,`${key} must change the source`)
 for(const stems of endpoints) {
  const samples=mix(stems)
  assert.ok(Math.abs(rms(samples)-.13)<.015,'Keep source energy comparable')
  for(const stem of stems)for(const channel of stem) {
   assert.equal(channel.length,rate*5)
   assert.ok(channel.every(v=>Number.isFinite(v)&&Math.abs(v)<.85))
   let maxStep=0
   for(let i=1;i<channel.length;i++)maxStep=Math.max(maxStep,Math.abs(channel[i]-channel[i-1]))
   assert.ok(Math.abs(channel[0]-channel.at(-1))<maxStep*1.1+1e-6,'Periodic source boundary')
  }
 }
}
assert.throws(()=>createSourceStems({...DEFAULT_SOURCE_CONTROLS,body:NaN},rate))
console.log('Four source controls produce distinct, repeatable, bounded stereo loops with comparable energy.')
const {sourceAudioBuffers}=await import(`data:text/javascript;base64,${Buffer.from(code).toString('base64')}`)
const impulse=[new Float32Array(480),new Float32Array(480)]
for(let i=0;i<480;i++){impulse[0][i]=Math.sin(2*Math.PI*175*i/48000);impulse[1][i]=-.5*impulse[0][i]}
const converted=sourceAudioBuffers({sampleRate:24000,createBuffer(channels,length,rate){assert.equal(rate,24000);const data=Array.from({length:channels},()=>new Float32Array(length));return {getChannelData:i=>data[i],length}}},[impulse])
assert.equal(converted[0].length,240)
for(let i=0;i<240;i++)assert.ok(Math.abs(converted[0].getChannelData(1)[i]+.5*converted[0].getChannelData(0)[i])<1e-7)
// Full-band generation at the actual asset rate, including an extreme candidate.
const started=performance.now()
for(const controls of [DEFAULT_SOURCE_CONTROLS,{body:1,character:1,ensemble:1,movement:1}]) {
 const stems=createSourceStems(controls)
 let peak=0,energy=0
 for(let c=0;c<2;c++)for(let i=0;i<48000*5;i++) {
  const sample=stems.reduce((sum,stem)=>sum+stem[c][i],0)
  peak=Math.max(peak,Math.abs(sample));energy+=sample*sample
 }
 assert.ok(peak<.701)
 assert.ok(Math.abs(Math.sqrt(energy/(48000*10))-.13)<1e-5)
}
console.log(`Full-rate source headroom and stereo device-rate conversion passed (${((performance.now()-started)/1000).toFixed(2)} s for two renders).`)
