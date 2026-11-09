import assert from 'node:assert/strict'
import {readFileSync} from 'node:fs'
const {EvolvingEngine,SourceLoopEngine}=await import('../desktop/public/audio/granular-processor.mjs')
const rate=48000,data=Float32Array.from({length:rate*5},(_,i)=>.15*Math.sin(2*Math.PI*175*i/rate))
const engine=new EvolvingEngine([data,Float32Array.from(data,x=>-.5*x)],rate)
let previous=0,maxJump=0
const crossings=[];let count=0
for(let i=0;i<rate*10;i++) {
 const value=engine.sample(1)
 assert.ok(Number.isFinite(value)&&Math.abs(value)<.4)
 assert.ok(Math.abs(engine.right+.5*value)<1e-7)
 maxJump=Math.max(maxJump,Math.abs(value-previous))
 if(i<rate*2.4&&previous<=0&&value>0)count++
 if(i%12000===11999&&i<rate*2.4){crossings.push(count);count=0}
 previous=value
}
assert.ok(maxJump<.06)
assert.ok(crossings[8]>crossings[4],'Same stationary source gains a rising pitch through transformation')
for(let i=0;i<rate*5;i++) engine.sample(1,1)
const held=engine.scanPosition
for(let i=0;i<rate;i++)engine.sample(1.2,1)
assert.equal(engine.scanPosition,held,'High-speed hold stops phrase resets, while pitch can keep climbing')
for(let i=0;i<rate;i++)engine.sample(1,0)
assert.ok(engine.scanPosition>held+rate*.8)
const switching=new SourceLoopEngine(data,rate)
for(let i=0;i<rate;i++) switching.sample(1)
for(let i=0;i<rate;i++) assert.ok(Number.isFinite(switching.sample(1,0,1)))
assert.ok(switching.renderer instanceof EvolvingEngine)
console.log('Shared-source evolving pitch rise, stereo, continuous output, high-speed hold and mode switching passed.')
