export type GranularMode = 'steady' | 'rise' | 'evolving'
/** Audio-thread overlap-add playback; source scan speed remains independent of pitch. */
export class GranularPlayer {
  readonly playbackRate: AudioParam
  readonly loopHold: AudioParam
  readonly evolution: AudioParam
  readonly cycleSpeed: AudioParam
  onended: (() => void) | null = null
  private readonly node: AudioWorkletNode
  private stopped = false
  private started = false
  constructor(audio: AudioContext, buffer: AudioBuffer) {
    this.node = new AudioWorkletNode(audio, 'ev-granular', { numberOfInputs: 0, numberOfOutputs: 1, outputChannelCount: [2] })
    this.playbackRate = this.node.parameters.get('rate')!
    this.loopHold = this.node.parameters.get('hold')!
    this.evolution = this.node.parameters.get('evolve')!
    this.cycleSpeed = this.node.parameters.get('cycleSpeed')!
    this.node.port.postMessage({ type: 'buffer', samples: [buffer.getChannelData(0), buffer.getChannelData(Math.min(1, buffer.numberOfChannels - 1))] })
    this.node.port.onmessage = () => this.onended?.()
  }
  /** Engine stage after the player (Engine style only); null turns it off. */
  setEngine(config: unknown) { this.node.port.postMessage({ type: 'engine', config }) }
  setSource(buffer: AudioBuffer) {
    this.node.port.postMessage({ type: 'buffer', samples: [buffer.getChannelData(0), buffer.getChannelData(Math.min(1, buffer.numberOfChannels - 1))] })
  }
  connect(node: AudioNode) { this.node.connect(node) }
  disconnect() { this.node.disconnect(); this.node.port.close() }
  start(when: number) {
    if (this.started) throw Error('Granular player already started')
    this.started = true; this.node.port.postMessage({ type: 'start', when })
  }
  stop(when: number) {
    if (this.stopped) return
    this.stopped = true; this.node.port.postMessage({ type: 'stop', when })
  }
}
