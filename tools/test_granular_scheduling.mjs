import assert from 'node:assert/strict'
import { GranularEngine } from '../desktop/public/audio/granular-processor.mjs'
const sampleRate=48000
const source=Float32Array.from({length:sampleRate},(_,i)=>.4*Math.sin(2*Math.PI*175*i/sampleRate)+.1*Math.sin(2*Math.PI*350*i/sampleRate))
const engine=new GranularEngine(source,sampleRate)
const granular=new Float32Array(sampleRate*3), ordinary=new Float32Array(granular.length)
let position=0
for(let i=0;i<granular.length;i++) {
  const rate=.75+.5*i/granular.length
  granular[i]=engine.sample(rate)
  const index=Math.floor(position),fraction=position-index
  ordinary[i]=source[index%source.length]*(1-fraction)+source[(index+1)%source.length]*fraction
  position+=rate
}
const maximumStep=signal=>signal.reduce((maximum,value,i)=>i?Math.max(maximum,Math.abs(value-signal[i-1])):maximum,0)
assert.ok(maximumStep(granular)<maximumStep(ordinary)*1.5,'Acceleration must not add impulse-like sample jumps')
for(let start=sampleRate*.2;start<granular.length-480;start+=480) {
  let energy=0
  for(let i=start;i<start+480;i++) energy+=granular[i]**2
  assert.ok(Math.sqrt(energy/480)>.1,'No missing grains or silent gaps after startup')
}
// Exercise the actual worklet message/render boundary without any UI timer.
globalThis.sampleRate=sampleRate
globalThis.currentFrame=0
let Processor
const messages=[]
globalThis.AudioWorkletProcessor=class { constructor(){this.port={postMessage:message=>messages.push(message)}} }
globalThis.registerProcessor=(name,processor)=>{Processor=processor}
await import('../desktop/public/audio/granular-processor.mjs?processor-test')
const processor=new Processor()
processor.port.onmessage({data:{type:'buffer',samples:source}})
processor.port.onmessage({data:{type:'start',when:.02}})
processor.port.onmessage({data:{type:'stop',when:.8}})
const rendered=[]
for(let frame=0;frame<sampleRate;frame+=128) {
  globalThis.currentFrame=frame
  const block=new Float32Array(128)
  const alive=processor.process([],[[block]],{rate:new Float32Array([1])})
  rendered.push(...block)
  if(!alive) break
}
assert.ok(rendered.slice(.3*sampleRate,.4*sampleRate).some(value=>Math.abs(value)>.1),'Audio continues at 300 ms with no UI callbacks')
assert.ok(rendered.slice(.8*sampleRate).every(value=>value===0),'Stop occurs at the requested audio frame')
assert.deepEqual(messages,['ended'])
console.log(`Audio-thread acceleration check passed. Max sample step: granular ${maximumStep(granular).toFixed(4)}, ordinary ${maximumStep(ordinary).toFixed(4)}. No gaps; exact scheduled stop.`)
const {readFileSync}=await import('node:fs')
function sourceWav(name) {
  const wav=readFileSync(`desktop/public/audio/original_steady_${name}.wav`)
  for(let offset=12;offset<wav.length;) {
    const size=wav.readUInt32LE(offset+4)
    if(wav.toString('ascii',offset,offset+4)==='data') {
      const samples=new Float32Array(size/8)
      for(let i=0;i<samples.length;i++) samples[i]=wav.readFloatLE(offset+8+i*8)
      return samples
    }
    offset+=8+size+(size%2)
  }
  throw Error('Missing source samples')
}
const sources=['body','pad','glass','air'].map(sourceWav)
const engines=sources.map(source=>new GranularEngine(source,sampleRate))
const gains=[1,.8,.25,1], positions=[0,0,0,0]
const actualGranular=new Float32Array(sampleRate*3), actualOrdinary=new Float32Array(actualGranular.length)
for(let i=0;i<actualGranular.length;i++) {
  const pitch=.75+.5*i/actualGranular.length
  for(let stem=0;stem<engines.length;stem++) {
    const rate=stem===3?1:pitch, data=sources[stem], position=positions[stem]
    actualGranular[i]+=engines[stem].sample(rate)*gains[stem]
    const index=Math.floor(position),fraction=position-index
    actualOrdinary[i]+=(data[index%data.length]*(1-fraction)+data[(index+1)%data.length]*fraction)*gains[stem]
    positions[stem]+=rate
  }
  assert.ok(Number.isFinite(actualGranular[i]) && Math.abs(actualGranular[i])<.95)
}
assert.ok(maximumStep(actualGranular)<maximumStep(actualOrdinary)*1.5,'Actual layered source must not introduce large sample discontinuities')
console.log(`Original four-stem acceleration check passed. Max sample step: granular ${maximumStep(actualGranular).toFixed(4)}, ordinary ${maximumStep(actualOrdinary).toFixed(4)}.`)
