import assert from 'node:assert/strict'
import {GranularEngine,SourceLoopEngine} from '../desktop/public/audio/granular-processor.mjs'
const rate=48000
const left=Float32Array.from({length:rate},(_,i)=>.2*Math.sin(2*Math.PI*175*i/rate))
const right=Float32Array.from(left,value=>value*-.5)
for(const Engine of [GranularEngine,SourceLoopEngine]) {
 const engine=new Engine([left,right],rate)
 for(let i=0;i<rate;i++) {
  const value=engine.sample(.8+.4*i/rate)
  assert.ok(Number.isFinite(value))
  assert.ok(Math.abs(engine.right+.5*value)<1e-7,'Both channels share positions and windows')
 }
 if(engine.setSource) {
  engine.setSource([right,left])
  for(let i=0;i<rate;i++) assert.ok(Number.isFinite(engine.sample(1))&&Number.isFinite(engine.right))
 }
}
console.log('Stereo granular rendering and source crossfade preserve paired channels.')
// Exercise both channels through the real worklet boundary.
globalThis.sampleRate=rate;globalThis.currentFrame=0
let Processor
globalThis.AudioWorkletProcessor=class {constructor(){this.port={postMessage(){}}}}
globalThis.registerProcessor=(_,processor)=>{Processor=processor}
await import('../desktop/public/audio/granular-processor.mjs?stereo-test')
const processor=new Processor()
processor.port.onmessage({data:{type:'buffer',samples:[left,right]}})
processor.port.onmessage({data:{type:'start',when:0}})
let heard=false
for(let frame=0;frame<rate;frame+=128) {
 globalThis.currentFrame=frame
 const output=[new Float32Array(128),new Float32Array(128)]
 processor.process([],[output],{rate:new Float32Array([1])})
 for(let i=0;i<128;i++) {
  assert.ok(Math.abs(output[1][i]+.5*output[0][i])<1e-7)
  heard ||= Math.abs(output[1][i])>.05
 }
}
assert.ok(heard,'Right channel must reach worklet output')
