/** Retarget from the rendered value, discarding pending fades and stale targets. */
export function smoothParameter(param: AudioParam, value: number, now: number, seconds: number) {
  param.cancelAndHoldAtTime(now)
  param.setTargetAtTime(value, now, seconds)
}

/** Two equal gain stages give a zero-slope onset; riseSeconds reaches 95% level. */
export function driveEnvelopeTarget(gain: number, riseSeconds: number, releasing: boolean) {
  return { gain: Math.sqrt(Math.max(0, Math.min(1, gain))), smoothing: releasing ? .18 : Math.max(.4, riseSeconds) / 3.676 }
}

/** Short modulated stereo copies add ensemble width before the driving envelope. */
export function createChorus(audio: AudioContext) {
  const input = audio.createGain(), output = audio.createGain()
  const dry = audio.createGain(), wet = audio.createGain()
  const split = audio.createChannelSplitter(2), merge = audio.createChannelMerger(2)
  dry.gain.value = .75; wet.gain.value = .25
  input.connect(dry); dry.connect(output)
  input.connect(split); merge.connect(wet); wet.connect(output)
  const voices = [0, 1].map(channel => {
    const delay = audio.createDelay(.05), motion = audio.createGain(), oscillator = audio.createOscillator()
    delay.delayTime.value = channel === 0 ? .018 : .023
    motion.gain.value = .0012
    oscillator.frequency.value = channel === 0 ? .28 : .33
    split.connect(delay, channel); delay.connect(merge, 0, channel)
    oscillator.connect(motion); motion.connect(delay.delayTime); oscillator.start()
    return { delay, motion, oscillator }
  })
  return { input, output, dispose() {
    voices.forEach(({ delay, motion, oscillator }) => { oscillator.stop(); oscillator.disconnect(); motion.disconnect(); delay.disconnect() })
    input.disconnect(); output.disconnect(); dry.disconnect(); wet.disconnect(); split.disconnect(); merge.disconnect()
  } }
}
