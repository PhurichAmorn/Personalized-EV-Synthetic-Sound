export type CurvePoint = { x: number; y: number }
export type Layer = { name: string; enabled: boolean; ratio: number; start: number; end: number; entry: number; levelPoints?: CurvePoint[] }
export type Effects = { echoMix: number; echoSeconds: number; echoFeedback: number; reverbMix: number; reverbDecay: number; reverbDamping: number }
export type SoundConfig = { startHz: number; endHz: number; curve: number; duration: number; attack: number; release: number; growth: number; normalize: boolean; effects: Effects; layers: Layer[]; pitchPoints?: CurvePoint[] }
export const DEFAULT_SOUND: SoundConfig = {
  startHz: 190, endHz: 275, curve: 1.6, duration: 12, attack: .8, release: .8, growth: .25, normalize: true,
  pitchPoints: [{ x: 0, y: 0 }, { x: .2, y: .04 }, { x: .45, y: .25 }, { x: .7, y: .64 }, { x: .9, y: .94 }, { x: 1, y: 1 }],
  effects: { echoMix: 0, echoSeconds: .24, echoFeedback: .25, reverbMix: 0, reverbDecay: 1.2, reverbDamping: .6 },
  layers: [
    { name: 'Foundation', enabled: true, ratio: 1, start: .56, end: .56, entry: 0 },
    { name: 'Harmonic body', enabled: true, ratio: 2, start: .05, end: .075, entry: 0 },
    { name: 'Upper tone', enabled: true, ratio: 3, start: 0, end: .012, entry: 0 },
    { name: 'Shimmer', enabled: true, ratio: 4, start: 0, end: .004, entry: 0 },
    { name: 'Chord third', enabled: false, ratio: 1.25, start: .12, end: .18, entry: 0 },
    { name: 'Chord fifth', enabled: false, ratio: 1.5, start: .12, end: .18, entry: 0 },
  ],
}
// Suggested curves keep the foundation steady and reveal upper layers gradually.
DEFAULT_SOUND.layers[0].levelPoints = [{ x: 0, y: .56 }, { x: .5, y: .56 }, { x: 1, y: .56 }]
DEFAULT_SOUND.layers[1].levelPoints = [{ x: 0, y: .04 }, { x: .35, y: .045 }, { x: .7, y: .065 }, { x: 1, y: .075 }]
DEFAULT_SOUND.layers[2].levelPoints = [{ x: 0, y: 0 }, { x: .35, y: 0 }, { x: .7, y: .006 }, { x: 1, y: .012 }]
DEFAULT_SOUND.layers[3].levelPoints = [{ x: 0, y: 0 }, { x: .55, y: 0 }, { x: .85, y: .002 }, { x: 1, y: .004 }]
DEFAULT_SOUND.layers[4].levelPoints = [{ x: 0, y: .02 }, { x: .4, y: .04 }, { x: 1, y: .08 }]
DEFAULT_SOUND.layers[5].levelPoints = [{ x: 0, y: .02 }, { x: .4, y: .04 }, { x: 1, y: .08 }]
export const BUILTIN_SOUND_PRESETS: { id: string; name: string; config: SoundConfig }[] = [
  { id: 'cinematic', name: 'Cinematic swell · suggested curves', config: structuredClone(DEFAULT_SOUND) },
  ...[
    { id: 'smooth', name: 'Smooth electric', voices: [{ ratio: 1, level: .72 }, { ratio: 2, level: .22 }, { ratio: 3, level: .06 }] },
    { id: 'warm', name: 'Warm mechanical', voices: [{ ratio: 1, level: .56 }, { ratio: 2, level: .34 }, { ratio: 3, level: .15 }, { ratio: .5, level: .25 }] },
  ].map(preset => {
    const config = structuredClone(DEFAULT_SOUND)
    config.startHz = 110; config.endHz = 198; config.curve = 1; config.growth = 0
    config.pitchPoints = [{ x: 0, y: 0 }, { x: 1 / 12, y: 0 }, { x: 10 / 12, y: 1 }, { x: 1, y: 1 }]
    config.layers = config.layers.map((layer, i) => {
      const voice = preset.voices[i]
      const level = voice?.level ?? 0
      return { ...layer, name: i === 3 && voice ? 'Low support' : layer.name, enabled: !!voice, ratio: voice?.ratio ?? layer.ratio, start: level, end: level, entry: 0, levelPoints: [{ x: 0, y: level }, { x: 1, y: level }] }
    })
    return { id: preset.id, name: preset.name, config }
  }),
]
export const RATE = 24000
const smooth = (x: number) => { const p = Math.max(0, Math.min(1, x)); return p * p * (3 - 2 * p) }
export function curveValue(position: number, points: CurvePoint[], shape = 1) {
  const p = Math.max(0, Math.min(1, position))
  for (let i = 1; i < points.length; i++) {
    if (p <= points[i].x) {
      const a = points[i - 1], b = points[i]
      return a.y + (b.y - a.y) * smooth(Math.pow((p - a.x) / (b.x - a.x), shape))
    }
  }
  return points[points.length - 1].y
}
export function progression(time: number, config: SoundConfig) {
  if (config.pitchPoints) return curveValue(time / config.duration, config.pitchPoints, config.curve)
  return smooth(Math.pow(Math.min(1, time / Math.max(.1, config.duration - config.release)), config.curve))
}
export function layerLevel(time: number, layer: Layer, config: SoundConfig) {
  if (!layer.enabled || time < layer.entry) return 0
  const rise = progression(time, config)
  const level = layer.levelPoints ? curveValue(time / config.duration, layer.levelPoints) : layer.start + (layer.end - layer.start) * rise
  return level * smooth((time - layer.entry) / Math.max(.05, config.attack))
}
export function applyEffects(channels: Float32Array[], effects: Effects) {
  for (const channel of channels) {
    if (effects.echoMix > 0) {
      const delay = Math.max(1, Math.round(effects.echoSeconds * RATE))
      const repeats = new Float32Array(channel.length)
      for (let i = delay; i < channel.length; i++) repeats[i] = channel[i - delay] + effects.echoFeedback * repeats[i - delay]
      for (let i = 0; i < channel.length; i++) channel[i] = channel[i] * (1 - effects.echoMix) + repeats[i] * effects.echoMix
    }
    if (effects.reverbMix > 0) {
      const dry = channel.slice(), wet = new Float32Array(channel.length)
      for (const milliseconds of [31, 37, 41, 43]) {
        const delay = Math.round(milliseconds / 1000 * RATE), line = new Float32Array(delay)
        const feedback = Math.pow(10, -3 * milliseconds / 1000 / effects.reverbDecay)
        let filtered = 0
        for (let i = 0; i < channel.length; i++) {
          const index = i % delay, delayed = line[index]
          filtered = delayed * (1 - effects.reverbDamping) + filtered * effects.reverbDamping
          line[index] = dry[i] + filtered * feedback
          wet[i] += delayed / 4
        }
      }
      for (let i = 0; i < channel.length; i++) channel[i] = dry[i] * (1 - effects.reverbMix) + wet[i] * effects.reverbMix
    }
    if (effects.echoMix > 0 || effects.reverbMix > 0) {
      // Fit the effect tail inside the preview, with a short fade at the boundary.
      const fade = Math.min(channel.length, Math.round(.08 * RATE))
      for (let i = channel.length - fade; i < channel.length; i++) channel[i] *= smooth((channel.length - 1 - i) / fade)
    }
  }
}
export function renderSound(config: SoundConfig, solo: number | null = null): { channels: Float32Array[]; scale: number } {
  const frames = Math.round(RATE * config.duration)
  const channels = [new Float32Array(frames), new Float32Array(frames)]
  let phase = 0, squares = 0, peak = 0
  const layers = config.layers.map((layer, i) => ({ ...layer, enabled: layer.enabled && (solo === null || solo === i) }))
  for (let i = 0; i < frames; i++) {
    const time = i / RATE, rise = progression(time, config)
    phase += 2 * Math.PI * (config.startHz + (config.endHz - config.startHz) * rise) / RATE
    const envelope = smooth((config.duration - time) / config.release) * (1 - config.growth + config.growth * rise)
    let left = 0, right = 0
    for (const layer of layers) {
      const value = Math.sin(phase * layer.ratio) * layerLevel(time, layer, config) * envelope
      left += value * Math.SQRT1_2
      right += value * Math.SQRT1_2
    }
    channels[0][i] = left; channels[1][i] = right
  }
  applyEffects(channels, config.effects)
  for (const channel of channels) for (const sample of channel) {
    squares += sample * sample
    peak = Math.max(peak, Math.abs(sample))
  }
  const rms = Math.sqrt(squares / (frames * 2))
  // Silent configurations stay silent; level matching is capped to prevent extreme gain.
  const requested = config.normalize && rms > 1e-6 ? Math.min(4, .13 / rms) : 1
  const scale = peak > 0 ? Math.min(requested, .85 / peak) : 1
  channels.forEach(channel => { for (let i = 0; i < frames; i++) channel[i] *= scale })
  return { channels, scale }
}
export function wavFile(channels: Float32Array[]) {
  const frames = channels[0].length, buffer = new ArrayBuffer(44 + frames * 4), view = new DataView(buffer)
  const word = (offset: number, value: string) => { for (let i = 0; i < value.length; i++) view.setUint8(offset + i, value.charCodeAt(i)) }
  word(0, 'RIFF'); view.setUint32(4, buffer.byteLength - 8, true); word(8, 'WAVE'); word(12, 'fmt ')
  view.setUint32(16, 16, true); view.setUint16(20, 1, true); view.setUint16(22, 2, true)
  view.setUint32(24, RATE, true); view.setUint32(28, RATE * 4, true); view.setUint16(32, 4, true); view.setUint16(34, 16, true)
  word(36, 'data'); view.setUint32(40, frames * 4, true)
  for (let i = 0; i < frames; i++) for (let c = 0; c < 2; c++) view.setInt16(44 + (i * 2 + c) * 2, Math.round(Math.max(-1, Math.min(1, channels[c][i])) * 32767), true)
  return new Blob([buffer], { type: 'audio/wav' })
}
