export const GRAIN_SECONDS = .16
export const OVERLAP = 4
export function alignedGrainOffset(data, sampleRate, scan, reference, rate) {
  const wrap = index => ((index % data.length) + data.length) % data.length
  const center = Math.round(scan * sampleRate), expected = Math.round(reference * sampleRate)
  const step = Math.max(1, Math.round(sampleRate / 6000)), radius = Math.round(.012 * sampleRate)
  const target = new Float32Array(64)
  let energy = 0
  for (let i = 0; i < target.length; i++) {
    target[i] = data[wrap(expected + Math.round(i * step * rate))]
    energy += target[i] * target[i]
  }
  if (energy < 1e-10) return wrap(center) / sampleRate
  let best = center, bestScore = -Infinity
  for (let delta = -radius; delta <= radius; delta += step) {
    let dot = 0, power = 0
    for (let i = 0; i < target.length; i++) {
      const value = data[wrap(center + delta + Math.round(i * step * rate))]
      dot += target[i] * value; power += value * value
    }
    const score = dot / Math.sqrt(Math.max(energy * power, 1e-20)) - .0001 * Math.abs(delta) / radius
    if (score > bestScore) { bestScore = score; best = center + delta }
  }
  return wrap(best) / sampleRate
}

// The same rendering core runs in the AudioWorklet and offline regression tests.
export class GranularEngine {
  constructor(data, rate) {
    this.channels = Array.isArray(data) ? data : [data, data]
    this.data = this.channels[0]; this.right = 0; this.rate = rate
    this.length = Math.round(GRAIN_SECONDS * rate)
    this.hop = Math.round(this.length / OVERLAP)
    this.window = Float32Array.from({length:this.length}, (_,i) => (1-Math.cos(2*Math.PI*i/this.length))/OVERLAP)
    this.grains = []; this.age = 0
    this.scanPosition=0; this.scanStep=1; this.holdTarget=null
  }
  sample(rate,hold=0) {
    if(hold>=.5 && this.holdTarget===null) {
      const phase=this.scanPosition%(2.5*this.rate)
      this.holdTarget=this.scanPosition+Math.max(0,2.2*this.rate-phase)
    } else if(hold<.5) this.holdTarget=null
    const data = this.data, size = data.length
    if (this.age % this.hop === 0) {
      const scan = this.scanPosition / this.rate
      // Previous grain's position is exact: no lookahead pitch prediction.
      const previous = this.grains[this.grains.length-1]
      const offset = previous ? alignedGrainOffset(data,this.rate,scan,previous.position/this.rate,rate) : 0
      this.grains.push({position:offset*this.rate,age:0})
    }
    let result = 0, right = 0
    const rightData = this.channels[1] ?? data
    for (const grain of this.grains) {
      const index = Math.floor(grain.position), fraction = grain.position-index
      const value = data[index % size]*(1-fraction)+data[(index+1) % size]*fraction
      result += value*this.window[grain.age]
      right += (rightData[index % size]*(1-fraction)+rightData[(index+1) % size]*fraction)*this.window[grain.age]
      grain.position = (grain.position+rate) % size; grain.age++
    }
    if (this.grains[0]?.age >= this.length) this.grains.shift()
    if(this.holdTarget===null) {
      this.scanStep=Math.min(1,this.scanStep+1/(.2*this.rate))
      this.scanPosition+=this.scanStep
    } else {
      const remaining=this.holdTarget-this.scanPosition
      if(remaining<1) {this.scanPosition=this.holdTarget;this.scanStep=0}
      else {this.scanStep=Math.min(this.scanStep,Math.sqrt(remaining/(.25*this.rate)));this.scanPosition+=Math.min(remaining,this.scanStep)}
    }
    this.age++; this.right = right
    return result
  }
}

const ease = value => { const x=Math.max(0,Math.min(1,value)); return x*x*(3-2*x) }
const handoff=value=>{const x=Math.max(0,Math.min(1,value))**.75;return x*x*x*(10+x*(-15+6*x))}
// Two overlapping rises transform the stationary source; no alternate WAV is needed.
export class EvolvingEngine {
  constructor(data,rate) {
    this.rate=rate; this.right=0; this.scanPosition=0; this.scanStep=1; this.holdTarget=null; this.cycleSpeed=null
    this.voices=[new GranularEngine(data,rate),new GranularEngine(data,rate)]
  }
  sample(rate,hold=0,cycleSpeed=1) {
    const target=Number.isFinite(cycleSpeed)?Math.max(.25,Math.min(1,cycleSpeed)):1
    this.cycleSpeed=this.cycleSpeed===null?target:this.cycleSpeed+(target-this.cycleSpeed)*(1-Math.exp(-1/(.25*this.rate)))
    let left=0,right=0
    for(let i=0;i<2;i++) {
      const local=(this.scanPosition/this.rate+i*2.5)%5
      const rise=ease(local/4.5)
      const envelope=Math.sin(Math.PI/2*handoff(local/2))*Math.cos(Math.PI/2*handoff((local-2.5)/2))
      const value=this.voices[i].sample(rate*2**(9*rise/12))
      left+=value*envelope;right+=this.voices[i].right*envelope
    }
    if(hold>=.5 && this.holdTarget===null) this.holdTarget=this.scanPosition+Math.max(0,2.2*this.rate-this.scanPosition%(2.5*this.rate))
    else if(hold<.5) this.holdTarget=null
    if(this.holdTarget===null) {
      this.scanStep=Math.min(this.cycleSpeed,this.scanStep+1/(.2*this.rate));this.scanPosition+=this.scanStep
    } else {
      const remaining=this.holdTarget-this.scanPosition
      if(remaining<1){this.scanPosition=this.holdTarget;this.scanStep=0}
      else {this.scanStep=Math.min(this.scanStep,Math.sqrt(remaining/(.25*this.rate)));this.scanPosition+=Math.min(remaining,this.scanStep)}
    }
    this.right=right
    return left
  }
}

/** Engine character added live AFTER the granular player, so playback can neither smear nor shift it.
 * Rasp: firing cycles alternate louder/softer (half-order growl, uneven cylinders) with a little per-cycle randomness,
 * blended across each cycle. No slow sine pulses (heard as tremolo); follows live pitch.
 * Resonances: fixed-frequency peaks (exhaust/intake/cabin) plus a low-pass; they stay put while pitch climbs.
 * Cabin: a short, dark room (about 0.5 s, highs damped) mixed at config.cabin; not the bright 2 s hall that sounded airy.
 * Also used by the Solo cello for its fixed body resonances (rasp 0).
 * config: {baseHz, rasp, resonances:[[hz, gainDb, q]...], lowpassHz, cabin, dry} or null. */
export class EngineStage {
  constructor(config,sampleRate) {
    this.config=config; this.fs=sampleRate; this.cycle=0; this.count=0; this.from=1; this.to=1; this.seed=12345  // seeded: renders are reproducible
    const biquad=(b0,b1,b2,a0,a1,a2)=>({b:[b0/a0,b1/a0,b2/a0],a:[a1/a0,a2/a0]})
    this.filters=[...config.resonances.map(([hz,gainDb,q])=>{  // RBJ peaking EQ
      const A=10**(gainDb/40),w=2*Math.PI*hz/sampleRate,alpha=Math.sin(w)/(2*q)
      return biquad(1+alpha*A,-2*Math.cos(w),1-alpha*A,1+alpha/A,-2*Math.cos(w),1-alpha/A)
    }),...(config.lowpassHz?[(()=>{const w=2*Math.PI*config.lowpassHz/sampleRate,alpha=Math.sin(w)/(2*.707),c=Math.cos(w)
      return biquad((1-c)/2,1-c,(1-c)/2,1+alpha,-2*c,1-alpha)})()]:[])]
    this.state=[0,1].map(()=>this.filters.map(()=>[0,0,0,0]))
    const k=sampleRate/44100
    this.rooms=[0,1].map(side=>({combs:[557,593,641,677].map(d=>({buffer:new Float64Array(Math.round((d+side*17)*k)),index:0,low:0})),
      passes:[225,341].map(d=>({buffer:new Float64Array(Math.round((d+side*17)*k)),index:0}))}))
  }
  room(x,side) {
    const room=this.rooms[side];let sum=0
    for(const comb of room.combs){const delayed=comb.buffer[comb.index];comb.low=delayed*.5+comb.low*.5;comb.buffer[comb.index]=x*.03+comb.low*.72;comb.index=(comb.index+1)%comb.buffer.length;sum+=delayed}
    for(const pass of room.passes){const delayed=pass.buffer[pass.index];pass.buffer[pass.index]=sum+delayed*.5;pass.index=(pass.index+1)%pass.buffer.length;sum=delayed-sum}
    return sum
  }
  process(left,right,rate) {
    this.cycle+=this.config.baseHz*rate/this.fs
    if(this.cycle>=1) {
      this.cycle-=1; this.count++; this.from=this.to
      this.seed=(this.seed*1664525+1013904223)>>>0  // LCG
      const random=this.seed/4294967296*2-1, alternate=this.count%2?1:-1
      this.to=1+this.config.rasp*(.15*random+alternate)  // mostly the regular half-order alternation (tonal growl); fully random sounded noisy (tone-to-noise 17 vs 34 dB) and wobbly
    }
    const gain=this.config.rasp?this.from+(this.to-this.from)*(.5-.5*Math.cos(Math.PI*this.cycle)):1
    const out=[left*gain,right*gain]
    for(let c=0;c<2;c++) for(let f=0;f<this.filters.length;f++) {
      const {b,a}=this.filters[f],s=this.state[c][f],x=out[c]
      const y=b[0]*x+b[1]*s[0]+b[2]*s[1]-a[0]*s[2]-a[1]*s[3]
      s[1]=s[0];s[0]=x;s[3]=s[2];s[2]=y;out[c]=y
    }
    if(this.config.cabin) for(let c=0;c<2;c++) out[c]=out[c]*(1-.5*this.config.cabin)+this.config.cabin*8*this.room(out[c],c)
    return out
  }
}

export class SourceLoopEngine {
  constructor(data,rate) {
    this.rate=rate; this.previous=null; this.fade=0; this.right=0; this.data=data; this.evolving=false; this.engineStage=null
    this.renderer=new GranularEngine(data,rate)
  }
  setEngine(config) { this.engineStage=config?new EngineStage(config,this.rate):null }
  setSource(data) {
    this.data=data; this.previous=this.renderer; this.renderer=this.evolving ? new EvolvingEngine(data,this.rate) : new GranularEngine(data,this.rate); this.fade=0
  }
  sample(rate,hold=0,evolving=0,cycleSpeed=1) {
    if((evolving>=.5)!==this.evolving) {this.evolving=evolving>=.5;this.setSource(this.data)}
    let value=this.renderer.sample(rate,hold,cycleSpeed)
    this.right=this.renderer.right
    if(this.engineStage&&!this.previous) { const [l,r]=this.engineStage.process(value,this.right,rate); this.right=r; return l }
    if(!this.previous) return value
    const mix=ease(this.fade/(.16*this.rate))
    let result=this.previous.sample(rate,hold,cycleSpeed)*(1-mix)+value*mix
    this.right=this.previous.right*(1-mix)+this.renderer.right*mix
    if(++this.fade>=.16*this.rate) this.previous=null
    if(this.engineStage) { const [l,r]=this.engineStage.process(result,this.right,rate); this.right=r; result=l }
    return result
  }
}

if (typeof registerProcessor === 'function') {
  class GranularProcessor extends AudioWorkletProcessor {
    static get parameterDescriptors() { return [{name:'rate',defaultValue:1,minValue:.1,maxValue:4,automationRate:'a-rate'}, {name:'hold',defaultValue:0,minValue:0,maxValue:1,automationRate:'k-rate'}, {name:'evolve',defaultValue:0,minValue:0,maxValue:1,automationRate:'k-rate'}, {name:'cycleSpeed',defaultValue:1,minValue:.25,maxValue:1,automationRate:'k-rate'}] }
    constructor() {
      super(); this.startFrame = Infinity; this.stopFrame = Infinity; this.engine = null
      this.port.onmessage = ({data}) => {
        if (data.type === 'buffer') {
          if(this.engine) this.engine.setSource(data.samples)
          else { this.engine=new SourceLoopEngine(data.samples,sampleRate); this.engine.setEngine(this.engineConfig??null) }
        }
        if (data.type === 'engine') { this.engineConfig=data.config; this.engine?.setEngine(data.config) }
        if (data.type === 'start') this.startFrame = Math.round(data.when*sampleRate)
        if (data.type === 'stop') this.stopFrame = Math.round(data.when*sampleRate)
      }
    }
    process(inputs,outputs,parameters) {
      const output = outputs[0][0], rates = parameters.rate, hold = parameters.hold?.[0] ?? 0, evolving = parameters.evolve?.[0] ?? 0, cycleSpeed = parameters.cycleSpeed?.[0] ?? 1
      for (let i=0;i<output.length;i++) {
        const frame = currentFrame+i
        const active=this.engine && frame>=this.startFrame && frame<this.stopFrame
        output[i] = active ? this.engine.sample(rates.length===1?rates[0]:rates[i],hold,evolving,cycleSpeed) : 0
        if(outputs[0][1]) outputs[0][1][i]=active ? this.engine.right : 0
      }
      if (currentFrame+output.length>=this.stopFrame) { this.port.postMessage('ended'); return false }
      return true
    }
  }
  registerProcessor('ev-granular',GranularProcessor)
}
