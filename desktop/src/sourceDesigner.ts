export type SourceControls = { body: number; character: number; ensemble: number; movement: number }
export const DEFAULT_SOURCE_CONTROLS: SourceControls = { body: .5, character: .5, ensemble: .5, movement: .5 }
export const SOURCE_FAMILIES = [
  { id: 'bowed', label: 'Bowed ensemble', description: 'Warm, layered strings' },
  { id: 'rounded', label: 'Rounded electronic', description: 'Rounded, hollow synth voices' },
  { id: 'vocal', label: 'Vocal cloud', description: 'Sustained vowel-like resonance' },
  { id: 'glass', label: 'Glass halo', description: 'Smooth, inharmonic shimmer' },
  { id: 'resonant', label: 'Resonant metal', description: 'Dark, softly metallic resonance' },
  { id: 'airy', label: 'Air and tone', description: 'Luminous, softly diffused harmonic tones' },
] as const
export type SourceFamily = typeof SOURCE_FAMILIES[number]['id']
export type SourceShape = { rootRatio?: number; tilt?: number; formantScale?: number; fmRatio?: number; fmIndex?: number; stretch?: number; noiseCenter?: number; noiseWidth?: number; seedPhase?: number; companionSub?: number }
export const SOURCE_RATE = 48000
const rms = (data: Float64Array) => Math.sqrt(data.reduce((sum, value) => sum + value * value, 0) / data.length)

/** Original periodic ensemble synthesis; these macros alter source audio, not the driving map. */
export function createSourceStems(controls: SourceControls, rate = SOURCE_RATE, family: SourceFamily = 'bowed', shape: SourceShape = {}): Float32Array[][] {
  if (!SOURCE_FAMILIES.some(item => item.id === family)) throw Error('Unknown source family')
  if (!Number.isFinite(rate) || rate < 8000 || rate > 192000 || !Number.isInteger(rate)) throw Error('Invalid source sample rate')
  for (const key of Object.keys(DEFAULT_SOURCE_CONTROLS) as (keyof SourceControls)[]) {
    if (!Number.isFinite(controls[key]) || controls[key] < 0 || controls[key] > 1) throw Error('Source controls must be between zero and one')
  }
  const limits: Record<keyof SourceShape, [number, number]> = { rootRatio: [.75, 2], tilt: [-.6, .6], formantScale: [.65, 1.45], fmRatio: [1.2, 4], fmIndex: [.2, 2.5], stretch: [.75, 1.3], noiseCenter: [500, 1900], noiseWidth: [180, 750], seedPhase: [0, 6.3], companionSub: [0, 1] }
  for (const [key, value] of Object.entries(shape)) {
    const bounds = limits[key as keyof SourceShape]
    if (!bounds || !Number.isFinite(value) || value < bounds[0] || value > bounds[1]) throw Error('Invalid source structure parameter')
  }
  const frames = rate * 5, root = Math.round(174.8 * (shape.rootRatio ?? 1) * 5) / 5
  const { body, character, ensemble, movement } = controls
  const tone = (frequency: number, seed: number) => {
    seed += shape.seedPhase ?? 0
    const result = new Float64Array(frames)
    const harmonics = Math.min(24, Math.floor(rate * .45 / frequency))
    const amplitudes = Array.from({ length: harmonics }, (_, i) => {
      const h = i + 1, hz = frequency * h
      const warmth = h === 1 ? .65 + 1.1 * body : 1 + .9 * body * Math.exp(-.5 * ((hz - 450) / 220) ** 2)
      if (family === 'rounded') {
        const odd = h === 1 ? .8 + .4 * body : h === 3 ? .42 + .25 * character : h === 5 ? .12 + .1 * character : h === 7 ? .035 : 0
        return odd * h ** (shape.tilt ?? 0) / (1 + (hz / 2000) ** 6)
      }
      if (family === 'vocal') {
        const formants = 1.8 * Math.exp(-.5 * ((hz - ((470 + 150 * character) * (shape.formantScale ?? 1))) / 100) ** 2)
          + 1.5 * Math.exp(-.5 * ((hz - ((1050 - 200 * character) * (shape.formantScale ?? 1))) / 140) ** 2)
          + .4 * Math.exp(-.5 * ((hz - 2100) / 250) ** 2)
        return warmth * ((h === 1 ? .12 : .015) + formants) / h ** (.85 - (shape.tilt ?? 0))
      }
      const colour = Math.exp(-(.38 - .24 * character) * (h - 1)) / h ** (1.9 - .85 * character)
      return warmth * colour * h ** (shape.tilt ?? 0) / (1 + (hz / (1400 + 600 * character)) ** 4)
    })
    const modes = [1, 2.01, 2.73, 4.17, 5.43, 6.79].map(ratio => Math.round(frequency * (1 + (ratio - 1) * (shape.stretch ?? 1)) * 5) / 5)
    const airTexture = family === 'airy' ? new Float64Array(frames) : null
    if (airTexture) {
      // Pitched clusters retain space without the old broadband wind texture.
      for (let band = 0; band < 24; band++) {
        const harmonic = 2 + Math.floor(band / 3)
        const hz = Math.round((frequency * harmonic + (band % 3 - 1) * .4) * 5) / 5
        if (hz >= rate * .45) continue
        const amplitude = .12 / harmonic ** .7 * Math.exp(-.5 * ((hz - (shape.noiseCenter ?? (800 + 250 * character))) / (shape.noiseWidth ?? 400)) ** 2)
        const angle = 2 * Math.PI * hz / rate, stepSin = Math.sin(angle), stepCos = Math.cos(angle)
        const hash = Math.sin((band + 1) * 12.9898 + seed * 78.233) * 43758.5453
        const initial = 2 * Math.PI * (hash - Math.floor(hash))
        let sine = Math.sin(initial), cosine = Math.cos(initial)
        for (let i = 0; i < frames; i++) {
          airTexture[i] += amplitude * sine
          const next = sine * stepCos + cosine * stepSin
          cosine = cosine * stepCos - sine * stepSin; sine = next
        }
      }
    }
    const modulator = Math.round(frequency * (shape.fmRatio ?? 2.414) * 5) / 5
    for (let i = 0; i < frames; i++) {
      const time = i / rate
      const drift = movement * (.15 * Math.sin(2 * Math.PI * .2 * time + seed) + .055 * Math.sin(2 * Math.PI * .6 * time + seed * 1.7))
      const vibrato = (family === 'rounded' ? .12 : 1) * movement * .07 * (1 + .2 * Math.sin(2 * Math.PI * .4 * time)) * Math.sin(2 * Math.PI * 5.2 * time + seed)
      const phase = 2 * Math.PI * frequency * time + seed + drift + vibrato
      let value = 0
      if (family === 'glass') {
        for (let mode = 0; mode < modes.length; mode++) {
          const hz = modes[mode]
          if (hz >= rate * .45) continue
          const amplitude = (mode === 0 ? .65 + .5 * body : .8 / (mode + 1) ** (1.1 - .4 * character)) / (1 + (hz / 2300) ** 6)
          value += amplitude * (1 + .06 * movement * Math.sin(2 * Math.PI * .4 * time + mode)) * Math.sin(2 * Math.PI * hz * time + seed + drift + vibrato)
        }
      } else if (family === 'resonant') {
        const index = shape.fmIndex ?? (.65 + 1.1 * character)
        value = (.35 + .35 * body) * Math.sin(phase) + .7 * Math.sin(phase + index * Math.sin(2 * Math.PI * modulator * time + seed))
      } else if (family === 'airy') {
        value = (.35 + .4 * body) * Math.sin(phase) + .08 * Math.sin(2 * phase) + airTexture![i]
      } else {
        for (let h = 1; h <= harmonics; h++) value += amplitudes[h - 1] * Math.sin(h * phase)
      }
      result[i] = value * (1 + .035 * movement * Math.sin(2 * Math.PI * 1.4 * time + seed * .7))
    }
    return result
  }
  const foundation = tone(root, .3), pad = new Float64Array(frames)
  // companionSub >= .5: pad voices at .5/1/2 x root (fuller, rated comfortable) instead of .75/1.5/2 (the original tuning).
  const companions = (shape.companionSub ?? 0) >= .5 ? [[.5,.55],[1,.35],[2,.1]] : family === 'rounded' ? [[1,.65],[1,.25],[2,.1]] : [[.75,.55],[1.5,.35],[2,.1]]
  for (const [index, [multiple, weight]] of companions.entries()) {
    const frequency = Math.round((root * multiple + (index - 1) * ensemble * .6) * 5) / 5
    const voice = tone(frequency, 1.1 + index * 1.7)
    for (let i = 0; i < frames; i++) pad[i] += voice[i] * weight
  }
  const upper = new Float64Array(frames)
  for (let i = 0; i < frames; i++) {
    const phase = 2 * Math.PI * root * i / rate
    upper[i] = .7 * Math.sin(2 * phase) + .2 * Math.sin(3 * phase) + .1 * Math.sin(4 * phase)
  }
  const weights = [.095, .065 * ensemble * 2, .002 + .004 * character]
  const layers = [foundation, pad, upper].map((signal, index) => {
    const scale = weights[index] / Math.max(rms(signal), 1e-12)
    // Circular low-pass returns keep early reflections continuous at the loop boundary.
    const filtered = new Float64Array(frames), coefficient = 1 - Math.exp(-2 * Math.PI * 1600 / rate)
    let previous = 0
    for (let i = frames - Math.round(rate * .1); i < frames; i++) previous += coefficient * (signal[i] - previous)
    for (let i = 0; i < frames; i++) { previous += coefficient * (signal[i] - previous); filtered[i] = previous }
    return [[.026,.072,.121],[.039,.094,.147]].map(delays => {
      const channel = new Float32Array(frames), offsets = delays.map(delay => Math.round(delay * rate)), gains = [.15,.08,.035]
      for (let i = 0; i < frames; i++) {
        let value = .88 * signal[i]
        for (let tap = 0; tap < 3; tap++) value += gains[tap] * filtered[(i - offsets[tap] + frames) % frames]
        channel[i] = value * scale
      }
      return channel
    })
  })
  let energy = 0, peak = 0
  for (let c = 0; c < 2; c++) for (let i = 0; i < frames; i++) {
    const sample = layers.reduce((sum, layer) => sum + layer[c][i], 0)
    energy += sample * sample; peak = Math.max(peak, Math.abs(sample))
  }
  const scale = Math.min(.13 / Math.sqrt(energy / (frames * 2)), .7 / Math.max(peak, 1e-12))
  for (const layer of layers) for (const channel of layer) for (let i = 0; i < frames; i++) channel[i] *= scale
  return layers
}

/** Resample once when installing a generated source into a device-rate worklet. */
export function sourceAudioBuffers(audio: AudioContext, stems: Float32Array[][]): AudioBuffer[] {
  return stems.map(channels => {
    const frames = Math.round(channels[0].length * audio.sampleRate / SOURCE_RATE)
    const buffer = audio.createBuffer(2, frames, audio.sampleRate)
    channels.forEach((data, channel) => {
      const output = buffer.getChannelData(channel)
      for (let i = 0; i < frames; i++) {
        const position = i * SOURCE_RATE / audio.sampleRate, index = Math.floor(position), fraction = position - index
        output[i] = data[index % data.length] * (1 - fraction) + data[(index + 1) % data.length] * fraction
      }
    })
    return buffer
  })
}
