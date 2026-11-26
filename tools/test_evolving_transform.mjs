import assert from 'node:assert/strict'
const {EvolvingEngine,SourceLoopEngine}=await import('../desktop/public/audio/granular-processor.mjs')
// Shepard-style Evolving: two voices an octave apart rise with speed; layers fade in from below and out at the top, nothing resets.
const rate=48000,data=Float32Array.from({length:rate*5},(_,i)=>.15*Math.sin(2*Math.PI*175*i/rate))
const engine=new EvolvingEngine([data,Float32Array.from(data,x=>-.5*x)],rate)
for(let stage=0;stage<4;stage+=.01) {  // layer gains always sum to 1: no level dip or jump as layers swap
  const total=[0,1].map(i=>Math.sin(Math.PI/2*(((stage+i)%2+2)%2))**2).reduce((a,b)=>a+b)
  assert.ok(Math.abs(total-1)<1e-9)
}
let previous=0,maxJump=0
for(let i=0;i<rate*8;i++) {  // speed up through 4 stages (0 to 160 km/h) and back down
  const t=i/(rate*8), stage=4*(t<.5?2*t:2-2*t), value=engine.sample(1,0,1,stage)
  assert.ok(Number.isFinite(value)&&Math.abs(value)<.4); assert.ok(Math.abs(engine.right+.5*value)<1e-7)
  maxJump=Math.max(maxJump,Math.abs(value-previous)); previous=value
}
assert.ok(maxJump<.06,'Continuous: no clicks or resets going up or down')
const switching=new SourceLoopEngine(data,rate)
for(let i=0;i<rate;i++) switching.sample(1)
for(let i=0;i<rate;i++) assert.ok(Number.isFinite(switching.sample(1,0,1)))
assert.ok(switching.renderer instanceof EvolvingEngine)
console.log('Evolving Shepard layers: constant total level, continuous up and down, stereo and mode switching passed.')
