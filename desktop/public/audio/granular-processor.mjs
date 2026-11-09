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

export class SourceLoopEngine {
  constructor(data,rate) {
    this.rate=rate; this.previous=null; this.fade=0; this.right=0; this.data=data; this.evolving=false
    this.renderer=new GranularEngine(data,rate)
  }
  setSource(data) {
    this.data=data; this.previous=this.renderer; this.renderer=this.evolving ? new EvolvingEngine(data,this.rate) : new GranularEngine(data,this.rate); this.fade=0
  }
  sample(rate,hold=0,evolving=0,cycleSpeed=1) {
    if((evolving>=.5)!==this.evolving) {this.evolving=evolving>=.5;this.setSource(this.data)}
    const value=this.renderer.sample(rate,hold,cycleSpeed)
    this.right=this.renderer.right
    if(!this.previous) return value
    const mix=ease(this.fade/(.16*this.rate))
    const result=this.previous.sample(rate,hold,cycleSpeed)*(1-mix)+value*mix
    this.right=this.previous.right*(1-mix)+this.renderer.right*mix
    if(++this.fade>=.16*this.rate) this.previous=null
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
          else this.engine=new SourceLoopEngine(data.samples,sampleRate)
        }
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
