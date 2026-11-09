import assert from 'node:assert/strict'
import {readFileSync} from 'node:fs'
import {SourceLoopEngine} from '../desktop/public/audio/granular-processor.mjs'
function source(name) {
 const wav=readFileSync(`desktop/public/audio/original_${name}_source.wav`)
 for(let offset=12;offset<wav.length;) {
  const size=wav.readUInt32LE(offset+4)
  if(wav.toString('ascii',offset,offset+4)==='data') return Float32Array.from({length:size/8},(_,i)=>wav.readFloatLE(offset+8+i*8))
  offset+=8+size+size%2
 }
 throw Error('Missing samples')
}
const rate=48000,steady=source('steady'),evolving=source('evolving')
assert.equal(steady.length,5*rate); assert.equal(evolving.length,steady.length)
let difference=0
for(let i=0;i<steady.length;i++) difference+=(steady[i]-evolving[i])**2
assert.ok(Math.sqrt(difference/steady.length)>.05,'Evolving must contain distinct authored source audio')
const engine=new SourceLoopEngine(evolving,rate)
let previous=0,maxStep=0,minRms=Infinity,energy=0
for(let i=0;i<rate*10;i++) {
 const value=engine.sample(1)
 assert.ok(Number.isFinite(value) && Math.abs(value)<.85)
 if(i>rate) maxStep=Math.max(maxStep,Math.abs(value-previous))
 energy+=value*value
 if(i%480===479) {if(i>rate) minRms=Math.min(minRms,Math.sqrt(energy/480));energy=0}
 previous=value
}
assert.ok(maxStep<.06,'Loop boundary must not create impulse-like jumps')
assert.ok(minRms>.005,'Overlapping phrase transitions must not fall into digital silence')
engine.setSource(steady)
for(let i=0;i<rate;i++) {const value=engine.sample(1);assert.ok(Number.isFinite(value));assert.ok(Math.abs(value-previous)<.06);previous=value}
console.log('Distinct five-second sources, evolving phrase loop continuity, levels and live source crossfade passed.')
const {GranularEngine}=await import('../desktop/public/audio/granular-processor.mjs')
const held=new GranularEngine(evolving,rate)
let last=0
for(let i=0;i<rate*8;i++) {
 const value=held.sample(.9+.2*i/(rate*8),i>=rate?1:0)
 assert.ok(Number.isFinite(value) && Math.abs(value-last)<.06)
 last=value
}
assert.equal(held.data,evolving,'High-speed hold must retain the evolving source')
assert.ok(Math.abs(held.scanPosition/rate-2.2)<.001,'Finish this rise and sustain before another phrase begins')
const frozen=held.scanPosition
for(let i=0;i<rate;i++) held.sample(1.2,1)
assert.equal(held.scanPosition,frozen,'No phrase restart while holding')
for(let i=0;i<rate;i++) held.sample(1,0)
assert.ok(held.scanPosition>frozen+rate*.8,'Slowing resumes the same source smoothly')
console.log('High-speed sustain keeps the same source, finishes the rise, stops resets, and resumes on release.')
