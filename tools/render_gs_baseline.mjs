/** Controlled source/renderer comparisons using the exact app grain core and map. */
import {readFileSync,writeFileSync} from 'node:fs'
import ts from '../desktop/node_modules/typescript/lib/typescript.js'
import {GranularEngine} from '../desktop/public/audio/granular-processor.mjs'
async function moduleAt(path) {
 const code=ts.transpileModule(readFileSync(path,'utf8'),{compilerOptions:{target:ts.ScriptTarget.ES2022,module:ts.ModuleKind.ES2022}}).outputText
 return import(`data:text/javascript;base64,${Buffer.from(code).toString('base64')}`)
}
const {drivingSoundTargets}=await moduleAt('desktop/src/drivingSoundMapping.ts')
const {driveEnvelopeTarget}=await moduleAt('desktop/src/audioAutomation.ts')
const root='artifacts/gs_baseline_research',rate=48000
const knots=[
 [0,0,0,0,0],[1,0,0,0,0],[3,20,.35,.55,.6],[7,60,.6,.8,.8],
 [11,110,.8,1,1],[14,120,.55,.6,.55],[16,100,0,0,-.4],[19,40,0,0,-.6],[22,0,0,0,0],
]
function inputs(time) {
 let index=0
 while(index<knots.length-2&&time>knots[index+1][0]) index++
 const a=knots[index],b=knots[index+1],amount=Math.max(0,Math.min(1,(time-a[0])/(b[0]-a[0])))
 const values=a.map((value,i)=>value+(b[i]-value)*amount)
 return {running:true,starting:false,speedKmh:values[1],power:values[2],throttle:values[3],motorLoad:values[4],rpm:values[1]/160*12000,maxRpm:12000,acceleration:(b[1]-a[1])/3.6/(b[0]-a[0])}
}
const trace=Array.from({length:221},(_,i)=>({time:i/10,...inputs(i/10)}))
const clips=[],verification={}
for(const source of ['procedural','recorded']) {
 const bytes=readFileSync(`${root}/${source}_loop.f32`)
 const interleaved=new Float32Array(bytes.buffer.slice(bytes.byteOffset,bytes.byteOffset+bytes.length))
 const data=[0,1].map(channel=>Float32Array.from({length:interleaved.length/2},(_,i)=>interleaved[2*i+channel]))
 for(const scene of ['neutral','drive']) {
  let ordinary
  for(const renderer of ['sample','granular']) {
   const frames=(scene==='neutral'?10:22)*rate
   const output=new Float32Array(frames*2),engine=new GranularEngine(data,rate)
   let position=0,pitch=scene==='neutral'?1:2**(-10/12),level=scene==='neutral'?1:0,targetRate=pitch,targetGain=level,smoothing=.18,lastTarget=0
   for(let i=0;i<frames;i++) {
    if(i%480===0&&scene==='drive') {
     const target=drivingSoundTargets(inputs(i/rate),false,'linear','rise')
     targetRate=target.rate
     const envelope=driveEnvelopeTarget(target.driveGain,1.1,target.driveGain<lastTarget)
     targetGain=envelope.gain;smoothing=envelope.smoothing;lastTarget=target.driveGain
    }
    pitch+=(targetRate-pitch)*(1-Math.exp(-1/(.35*rate)))
    level+=(targetGain-level)*(1-Math.exp(-1/(smoothing*rate)))
    let values
    if(renderer==='granular') {const left=engine.sample(pitch);values=[left,engine.right]}
    else {
     const index=Math.floor(position),fraction=position-index
     values=data.map(channel=>channel[index%channel.length]*(1-fraction)+channel[(index+1)%channel.length]*fraction)
     position+=pitch
    }
    const fade=Math.max(0,Math.min(1,i/(.2*rate),(frames-1-i)/(.3*rate)))
    for(let channel=0;channel<2;channel++) {
     output[2*i+channel]=values[channel]*level*level*fade*fade*(3-2*fade)
     if(!Number.isFinite(output[2*i+channel])) throw Error('Non-finite baseline audio')
    }
   }
   if(renderer==='sample') ordinary=output
   else if(scene==='neutral') {
    let maximum=0
    for(let i=2*rate;i<2*(frames-rate);i++) maximum=Math.max(maximum,Math.abs(output[i]-ordinary[i]))
    if(maximum>1e-5) throw Error(`Neutral granular transparency failed: ${maximum}`)
    verification[source]={neutral_maximum_difference:maximum}
   }
   const file=`${source}_${renderer}_${scene}.f32`
   writeFileSync(`${root}/${file}`,Buffer.from(output.buffer))
   clips.push({source,renderer,scene,file})
  }
 }
}
writeFileSync(`${root}/renders.json`,JSON.stringify({clips,trace,verification},null,2))
console.log('Rendered 8 dry source/renderer/trace combinations; neutral transparency checks passed.')
