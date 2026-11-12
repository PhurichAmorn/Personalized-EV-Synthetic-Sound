export type SourceControls = { body: number; character: number; ensemble: number; movement: number }
export const DEFAULT_SOURCE_CONTROLS: SourceControls = { body: .5, character: .5, ensemble: .5, movement: .5 }
export const SOURCE_FAMILIES = [
  { id: 'bowed', label: 'Strings', description: 'Warm, dark bowed-string pad' },
  { id: 'rounded', label: 'Pure tone', description: 'Clean, smooth electronic tone' },
  { id: 'vocal', label: 'Choir', description: 'Small choir singing "aah"; the brightest style' },
  { id: 'glass', label: 'Glass', description: 'Bell-like, shimmering tones' },
  // Merged into Cluster (2026-11-11): measured almost identical to airy. Kept so old session recipes still replay; hidden in Sound Lab.
  { id: 'resonant', label: 'Metal (merged into Cluster)', description: 'Dark, softly metallic resonance' },
  { id: 'airy', label: 'Cluster', description: 'Soft, diffuse clusters of tones' },
  { id: 'engine', label: 'Engine (parked)', description: 'Firing-pulse harmonics with exhaust resonance' },
  { id: 'orchestra', label: 'Cello (parked)', description: 'One warm bowed cello, deep to high, with gentle chorus and room' },
  { id: 'evolution', label: 'Electric', description: 'Bright electric tone modelled on the IONIQ 5 N Evolution mode: strong upper harmonics, quiet base' },
  { id: 'supersonic', label: 'Jet', description: 'Turbine-like whine near 1 kHz over a low rumble, modelled on the IONIQ 5 N Supersonic mode' },
  { id: 'blocks', label: 'Open blocks', description: 'Generic building blocks: harmonic series, resonances, pulse, FM, noise band, waveshaper' },
] as const
export type SourceFamily = typeof SOURCE_FAMILIES[number]['id']
export type SourceShape = { rootRatio?: number; tilt?: number; formantScale?: number; fmRatio?: number; fmIndex?: number; stretch?: number; noiseCenter?: number; noiseWidth?: number; seedPhase?: number; companionSub?: number; lope?: number; drive?: number
  // 'blocks' only: harmonic slope, even-harmonic gain, two resonant peaks (Hz, gain, width in octaves), low-pass, inharmonicity, FM/noise mix, amplitude modulation.
  slope?: number; evenGain?: number; peak1Hz?: number; peak1Gain?: number; peak2Hz?: number; peak2Gain?: number; peakWidth?: number; cutoff?: number; inharm?: number; fmMix?: number; noiseMix?: number; amRate?: number; amDepth?: number }
export const SOURCE_RATE = 48000
/** Engine stage settings (applied live after the granular player, see granular-processor.mjs EngineStage).
 * Matched to the IONIQ 5 N Ignition mode (2-7 s of ev-sound-example/hyundai-ignition-evolution-supersonic.mp3):
 * stable resonance peaks near 175, 370 and 560 Hz; energy falls steeply above 1 kHz; rasp 12-16% while accelerating. */
export type EngineStageConfig = { baseHz: number; rasp: number; resonances: [number, number, number][]; lowpassHz: number; cabin: number
  /** Shared effects: chorus amount (1 = the usual 25% wet, 0 = off) and whether the room reverb is on. The air layer is always off with a stage. */
  chorus: number; room: boolean }
export const ENGINE_RASP = .25
export const ENGINE_REGISTER = .57  // loop pitch vs the shared 174.8 Hz: about 65 Hz at launch, closer to the IONIQ's ~60 Hz idle
const ENGINE_BODY_DB = 5
const ENGINE_SUB_DB = 9
const ENGINE_PEAK_DB = 2
const ENGINE_LOPE = .3  // half-order burble (half the firing rate): the deep low end of an engine
const ENGINE_EVEN = .45  // even harmonics softened: a mostly-odd series sounds hollow, a more electric colour
const CELLO_LOW_DB = 7
const CELLO_CHORUS = 1
const CELLO_SLOPE = 2.3
const CELLO_HALL = .5
const CELLO_REGISTER = .6  // about 56 Hz at rest
const ENGINE_CABIN = .22  // wet level of the short dark cabin reverb in the engine stage (0 = dry)
/** Evolution: harmonic weights measured from the IONIQ 5 N Evolution mode (7.5-10.5 s of
 * ev-sound-example/hyundai-ignition-evolution-supersonic.mp3): strongest at orders 4 and 2, weak fundamental. */
// Plain style (no after-player stage): shared chorus, room and air like the pads, so it layers and blends like any style.
// Orders 6-9 softened after listening (Sound Lab option B, chosen 2026-11-11): the peak was too sharp.
const EVOLUTION_ORDERS = [.1, .8, .22, 1, .25, .2, .22, .12, .06]
/** Jet: measured from the IONIQ 5 N Supersonic mode (11.5-16 s of the same clip): a steady whine near 1 kHz with side tones
 * at about 0.41, 0.68 and 0.9 of it, over a low rumble (65-115 Hz). Plain style (no stage), smooth: no noise, no wobble. */
const JET_REGISTER = .915  // rumble root about 160 Hz before the speed mapping
const JET_WHINE = 8.75  // whine = 8.75 x root: about 1.4 kHz before the mapping, 750 Hz-1.25 kHz on the drive
const JET_WHINE_LEVEL = .9  // whine vs rumble: about 22% of energy below 200 Hz, as in the reference
// The 0.9x side tone is kept quiet: close to the whine, it rubbed at about 100 Hz and sounded rough (roughness 18% -> 7%).
const JET_SIDES: [number, number][] = [[.41, .4], [.68, .45], [.9, .12]]  // turbine side tones: ratio to the whine, level
const EVOLUTION_REGISTER = .45  // main note about 42 Hz at rest, as in the reference launch
const EVOLUTION_TAIL = .05  // weight of the harmonics above order 9 (kept low: a bright tail sounded sharp)
export function engineStageFor(family: string, shape: SourceShape = {}): EngineStageConfig | null {
  if (family === 'orchestra') return {
    // Solo cello: cello-body resonances fixed in pitch (air mode near 100 Hz, wood modes near 200 and 400 Hz, bridge region
    // near 1.5 kHz; approximate, from published cello acoustics), a warm low end, no ensemble.
    // Reverb is built into the loop (CELLO_HALL), not the shared room: a room tail holds the pitch from a moment ago and beat
    // against the rising note (loudness wobble 11% vs 0.1%). The shared chorus adds no wobble, so it stays on.
    baseHz: 0, rasp: 0, chorus: CELLO_CHORUS, room: false, cabin: 0, lowpassHz: 2400,
    resonances: [[60, CELLO_LOW_DB, .7], [105, 5, 4], [200, 4, 4], [400, 3, 4], [1500, 2, 1]] }
  if (family !== 'engine') return null
  // A low boom near 50 Hz and broad body peaks at 120 and 250 Hz, with a gentler 175 Hz peak, give the IONIQ's even,
  // deep low-mid (63-500 Hz within about 7 dB) instead of one dominant peak.
  return { baseHz: Math.round(174.8 * ENGINE_REGISTER * (shape.rootRatio ?? 1) * 5) / 5, rasp: ENGINE_RASP,
    resonances: [[50, ENGINE_SUB_DB, .7], [120, ENGINE_BODY_DB, .7], [250, ENGINE_BODY_DB * .75, .8], [175, ENGINE_PEAK_DB, 2], [370, 6, 2], [560, 6, 2]], lowpassHz: 1500, cabin: ENGINE_CABIN, chorus: 0, room: false }
}
/** How far a family's pitch climbs with speed, as a multiple of the shared mapping's one-octave climb.
 * Engine follows the IONIQ 5 N Ignition reference (about 60 Hz idle to 250 Hz in first gear); orchestra goes deep to high. */
export const PITCH_TRAVEL: Partial<Record<string, number>> = { engine: 2.2, orchestra: 2.4, evolution: 2.2, supersonic: .8 }  // jet: whine stays about 750 Hz-1.25 kHz  // cello: about 65 Hz (low C) at rest to about 320 Hz
const rms = (data: Float64Array) => Math.sqrt(data.reduce((sum, value) => sum + value * value, 0) / data.length)

/** Original periodic ensemble synthesis; these macros alter source audio, not the driving map. */
export function createSourceStems(controls: SourceControls, rate = SOURCE_RATE, family: SourceFamily = 'bowed', shape: SourceShape = {}): Float32Array[][] {
  if (!SOURCE_FAMILIES.some(item => item.id === family)) throw Error('Unknown source family')
  if (!Number.isFinite(rate) || rate < 8000 || rate > 192000 || !Number.isInteger(rate)) throw Error('Invalid source sample rate')
  for (const key of Object.keys(DEFAULT_SOURCE_CONTROLS) as (keyof SourceControls)[]) {
    if (!Number.isFinite(controls[key]) || controls[key] < 0 || controls[key] > 1) throw Error('Source controls must be between zero and one')
  }
  const limits: Record<keyof SourceShape, [number, number]> = { rootRatio: [.4, 2], tilt: [-.6, .6], formantScale: [.65, 1.45], fmRatio: [.5, 7], fmIndex: [.2, 2.5], stretch: [.75, 1.3], noiseCenter: [150, 6000], noiseWidth: [50, 3000], seedPhase: [0, 6.3], companionSub: [0, 1], lope: [0, 1], drive: [0, 6],
    slope: [.2, 3], evenGain: [0, 1.5], peak1Hz: [100, 5000], peak1Gain: [0, 4], peak2Hz: [100, 5000], peak2Gain: [0, 4], peakWidth: [.1, 1.2], cutoff: [300, 10000], inharm: [0, .02], fmMix: [0, 1], noiseMix: [0, 1], amRate: [0, 40], amDepth: [0, 1] }
  for (const [key, value] of Object.entries(shape)) {
    const bounds = limits[key as keyof SourceShape]
    if (!bounds || !Number.isFinite(value) || value < bounds[0] || value > bounds[1]) throw Error('Invalid source structure parameter')
  }
  // Per-family register: with PITCH_TRAVEL these start deep at rest (engine about 60 Hz, like an idling engine) and climb high.
  const register = family === 'engine' ? ENGINE_REGISTER : family === 'orchestra' ? CELLO_REGISTER : family === 'evolution' ? EVOLUTION_REGISTER : family === 'supersonic' ? JET_REGISTER : 1
  const frames = rate * 5, root = Math.round(174.8 * register * (shape.rootRatio ?? 1) * 5) / 5
  const { body, character, ensemble, movement } = controls
  const tone = (frequency: number, seed: number) => {
    seed += shape.seedPhase ?? 0
    const result = new Float64Array(frames)
    const harmonics = Math.min(family === 'engine' || family === 'evolution' ? 48 : 24, Math.floor(rate * .45 / frequency))  // a low engine note needs more orders to reach its exhaust band
    const amplitudes = Array.from({ length: harmonics }, (_, i) => {
      const h = i + 1, hz = frequency * h
      const warmth = h === 1 ? .65 + 1.1 * body : 1 + .9 * body * Math.exp(-.5 * ((hz - 450) / 220) ** 2)
      if (family === 'engine') {
        // Plain firing pulses: aligned harmonics with a shallow slope (character = brighter). Exhaust resonances are applied
        // after the player (engine stage) so they stay at fixed frequencies while pitch climbs.
        return (h % 2 ? 1 : ENGINE_EVEN) * warmth * h ** -(1.7 - .8 * character + (shape.tilt ?? 0)) / (1 + (hz / (1300 + 1200 * character)) ** 4)
      }
      if (family === 'rounded') {
        const odd = h === 1 ? .8 + .4 * body : h === 3 ? .42 + .25 * character : h === 5 ? .12 + .1 * character : h === 7 ? .035 : 0
        return odd * h ** (shape.tilt ?? 0) / (1 + (hz / 2000) ** 6)
      }
      if (family === 'vocal') {
        // Open "aah" vowel: smooth glottal slope (not the flat pulse-train slope that made it sound like an engine), F1/F2/F3 peaks.
        const scale = shape.formantScale ?? 1
        const formants = 2.2 * Math.exp(-.5 * ((hz - (650 + 120 * character) * scale) / 110) ** 2)
          + 1.4 * Math.exp(-.5 * ((hz - (1080 - 120 * character) * scale) / 140) ** 2)
          + .35 * Math.exp(-.5 * ((hz - 2600 * scale) / 220) ** 2)
        return warmth * (.3 + formants) * h ** -(1.3 - (shape.tilt ?? 0)) / (1 + (hz / 3200) ** 4)
      }
      if (family === 'supersonic') return h ** -1.5 / (1 + (hz / 600) ** 4)  // low rumble only; the whine is added per sample
      if (family === 'evolution') {
        const weight = h <= EVOLUTION_ORDERS.length ? EVOLUTION_ORDERS[h - 1] : EVOLUTION_TAIL * 9 / h
        return weight / (1 + (hz / (2200 + 600 * character)) ** 4)  // soft top: above 2 kHz under 1% of the energy
      }
      if (family === 'orchestra') {
        // Solo cello: sawtooth-like bowed string (Helmholtz motion). Its body resonances are applied after the player
        // (engineStageFor) so they stay at fixed frequencies like a real instrument body.
        // Warm, smooth slope (steeper than a raw sawtooth): at low pitch a bright series rubbed in the ear as vibration.
        return warmth * h ** -(CELLO_SLOPE - (shape.tilt ?? 0)) / (1 + (hz / (1800 + 800 * character)) ** 4)
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
    const halfOrder = Math.round(frequency / 2 * 5) / 5, ampSum = amplitudes.reduce((a, b) => a + b, 0) || 1
    // 'blocks': partials on the 0.2 Hz loop grid (stretched by inharm), envelope = slope x even gain x two resonances x low-pass.
    const blockHz: number[] = [], blockAmp: number[] = [], noiseBand = family === 'blocks' && (shape.noiseMix ?? 0) > 0 ? new Float64Array(frames) : null
    if (family === 'blocks') {
      const cutoff = shape.cutoff ?? 3000, width = shape.peakWidth ?? .4
      const peak = (hz: number, center: number | undefined, gain: number | undefined) => center === undefined ? 0 : (gain ?? 0) * Math.exp(-.5 * (Math.log2(hz / center) / width) ** 2)
      for (let h = 1; h <= 48; h++) {
        const hz = Math.round(frequency * h * Math.sqrt(1 + (shape.inharm ?? 0) * h * h) * 5) / 5
        if (hz >= Math.min(rate * .45, cutoff * 4)) break
        blockHz.push(hz)
        blockAmp.push(h ** -(shape.slope ?? 1.2) * (h % 2 ? 1 : shape.evenGain ?? 1) * (1 + peak(hz, shape.peak1Hz, shape.peak1Gain) + peak(hz, shape.peak2Hz, shape.peak2Gain)) / (1 + (hz / cutoff) ** 4))
      }
      if (noiseBand) {
        // Dense random-phase sine cluster on the loop grid: band noise that still loops seamlessly.
        const center = shape.noiseCenter ?? 1000, bandwidth = shape.noiseWidth ?? 400, level = (shape.noiseMix ?? 0) * blockAmp.reduce((a, b) => a + b, 0) / Math.sqrt(80)
        for (let k = 0; k < 80; k++) {
          const u = Math.sin((k + 1) * 12.9898 + seed * 78.233) * 43758.5453, v = Math.sin((k + 1) * 4.1414 + seed * 39.17) * 24634.6345
          const hz = Math.round((center + (u - Math.floor(u) - .5) * 2 * bandwidth) * 5) / 5
          if (hz <= 20 || hz >= rate * .45) continue
          const step = 2 * Math.PI * hz / rate, initial = 2 * Math.PI * (v - Math.floor(v))
          for (let i = 0; i < frames; i++) noiseBand[i] += level * Math.sin(initial + step * i)
        }
      }
    }
    const jetTones = family === 'supersonic' ? [[1, JET_WHINE_LEVEL], ...JET_SIDES.map(([ratio, level]) => [ratio, JET_WHINE_LEVEL * level])].map(([ratio, level]) => [Math.round(frequency * JET_WHINE * ratio * 5) / 5, level]) : []  // on the 0.2 Hz loop grid
    const blockSum = blockAmp.reduce((a, b) => a + b, 0) || 1, amRate = Math.round((shape.amRate ?? 0) * 5) / 5
    // Choir: five voices detuned on the 0.2 Hz loop grid, each with its own vibrato rate (whole cycles per 5 s loop).
    const section = family === 'vocal'
    const voiceOffsets = [0, -.4, .4, -.8, .8], vibratoRates = [5.2, 5, 5.4, 4.8, 5.6]
    const vibratoDepth = .006 * movement * frequency  // Hz deviation: about 6-10 cents at full movement
    const modulator = Math.round(frequency * (shape.fmRatio ?? 2.414) * 5) / 5
    for (let i = 0; i < frames; i++) {
      const time = i / rate
      const still = family === 'engine' || family === 'orchestra' || family === 'evolution' || family === 'supersonic'  // no pad-style drift, vibrato or sway (heard as wobble)
      const drift = still ? 0 : movement * (.15 * Math.sin(2 * Math.PI * .2 * time + seed) + .055 * Math.sin(2 * Math.PI * .6 * time + seed * 1.7))
      const vibrato = still ? 0 : (family === 'rounded' ? .12 : 1) * movement * .07 * (1 + .2 * Math.sin(2 * Math.PI * .4 * time)) * Math.sin(2 * Math.PI * 5.2 * time + seed)
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
      } else if (family === 'engine') {
        for (let h = 1; h <= harmonics; h++) value += amplitudes[h - 1] * Math.sin(h * phase)
        // Half-order lope: uneven cylinder-to-cylinder firing adds 0.5x and 1.5x orders.
        const lope = shape.lope ?? ENGINE_LOPE
        value += lope * ampSum * .12 * (Math.sin(2 * Math.PI * halfOrder * time + seed * .37 + drift) + .6 * Math.sin(2 * Math.PI * halfOrder * 3 * time + seed * .9 + drift))
        const drive = shape.drive ?? 0
        if (drive > 0) value = Math.tanh(drive * 3 * value / ampSum) * ampSum / (1 + drive)
      } else if (family === 'blocks') {
        const offset = seed + drift + vibrato
        for (let p = 0; p < blockHz.length; p++) value += blockAmp[p] * Math.sin(2 * Math.PI * blockHz[p] * time + (p + 1) * offset)
        value += (shape.lope ?? 0) * blockSum * .12 * (Math.sin(2 * Math.PI * halfOrder * time + seed * .37 + drift) + .6 * Math.sin(2 * Math.PI * halfOrder * 3 * time + seed * .9 + drift))
        value += (shape.fmMix ?? 0) * blockSum * .5 * Math.sin(phase + (shape.fmIndex ?? 1) * Math.sin(2 * Math.PI * modulator * time + seed))
        if (noiseBand) value += noiseBand[i]
        const drive = shape.drive ?? 0
        if (drive > 0) value = Math.tanh(drive * 3 * value / blockSum) * blockSum / (1 + drive)
        value *= 1 - (shape.amDepth ?? 0) * .5 * (1 - Math.cos(2 * Math.PI * amRate * time))
      } else if (section) {
        for (let v = 0; v < voiceOffsets.length; v++) {
          const hz = frequency + voiceOffsets[v]
          const vibratoPhase = 2 * Math.PI * vibratoRates[v] * time + seed + v
          const theta = 2 * Math.PI * hz * time + seed * (v + 1) + drift + vibratoDepth / vibratoRates[v] * Math.sin(vibratoPhase)
          // sin(h*theta) by recurrence: one sin/cos per voice instead of one per harmonic.
          const c2 = 2 * Math.cos(theta); let previous = 0, current = Math.sin(theta)
          for (let h = 1; h <= harmonics; h++) {
            value += amplitudes[h - 1] * current
            const next = c2 * current - previous; previous = current; current = next
          }
        }
        value /= voiceOffsets.length
      } else if (family === 'evolution') {
        // Staggered harmonic start phases (h^2 x golden angle): same spectrum, but the harmonics no longer peak together
        // each cycle, so the tone is smooth instead of a pointy pulse (roughness 18% -> 9%). The reference's off-series
        // partial near 1.2x was dropped: it made the tone edgy.
        for (let h = 1; h <= harmonics; h++) value += amplitudes[h - 1] * Math.sin(h * phase + h * h * 2.39996)
      } else if (family === 'supersonic') {
        for (let h = 1; h <= harmonics; h++) value += amplitudes[h - 1] * Math.sin(h * phase + h * h * 2.39996)  // staggered: smooth rumble
        for (let k = 0; k < jetTones.length; k++) value += jetTones[k][1] * ampSum * Math.sin(2 * Math.PI * jetTones[k][0] * time + seed * (k + 2.3))
      } else if (family === 'airy') {
        value = (.35 + .4 * body) * Math.sin(phase) + .08 * Math.sin(2 * phase) + airTexture![i]
      } else {
        for (let h = 1; h <= harmonics; h++) value += amplitudes[h - 1] * Math.sin(h * phase)
      }
      result[i] = value * (1 + (still ? 0 : .035) * movement * Math.sin(2 * Math.PI * 1.4 * time + seed * .7))
    }
    return result
  }
  const foundation = tone(root, .3), pad = new Float64Array(frames)
  // companionSub >= .5: pad voices at .5/1/2 x root (fuller, rated comfortable) instead of .75/1.5/2 (the original tuning).
  // Engine: no sub-octave voice (it made the idle rumble press on the ears); orders 1 and 2 instead.
  const companions = (shape.companionSub ?? 0) >= .5 ? [[.5,.55],[1,.35],[2,.1]] : family === 'rounded' ? [[1,.65],[1,.25],[2,.1]] : family === 'engine' ? [[1,.55],[1,.3],[2,.15]] : family === 'blocks' ? [[1,.5],[1,.3],[.5,.2]] : [[.75,.55],[1.5,.35],[2,.1]]
  for (const [index, [multiple, weight]] of companions.entries()) {
    const frequency = Math.round((root * multiple + (family === 'orchestra' || family === 'engine' ? 0 : (index - 1) * ensemble * .6)) * 5) / 5  // orchestra/engine voices stay in tune: detuning beat as a slow wobble
    const voice = tone(frequency, 1.1 + index * 1.7)
    for (let i = 0; i < frames; i++) pad[i] += voice[i] * weight
  }
  const upper = new Float64Array(frames)
  for (let i = 0; i < frames; i++) {
    const phase = 2 * Math.PI * root * i / rate
    upper[i] = .7 * Math.sin(2 * phase) + .2 * Math.sin(3 * phase) + .1 * Math.sin(4 * phase)
  }
  // Engine: body layer only. Each layer has its own granular player; copies of the same pitches in the pad and upper
  // layers drifted in and out of phase while revs climbed and beat at about 2-3.5 Hz (heard as wobble).
  const weights = family === 'engine' || family === 'orchestra' || family === 'evolution' || family === 'supersonic' ? [.095, 0, 0] : [.095, .065 * ensemble * 2, .002 + .004 * character]
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
  const builtInHall = family === 'orchestra' ? CELLO_HALL : 0
  if (builtInHall) layers[0].forEach((channel, c) => hall(channel, rate, c, builtInHall))  // built-in hall: rises with the note, so no beating
  let energy = 0, peak = 0
  for (let c = 0; c < 2; c++) for (let i = 0; i < frames; i++) {
    const sample = layers.reduce((sum, layer) => sum + layer[c][i], 0)
    energy += sample * sample; peak = Math.max(peak, Math.abs(sample))
  }
  const scale = Math.min(.13 / Math.sqrt(energy / (frames * 2)), .7 / Math.max(peak, 1e-12))
  for (const layer of layers) for (const channel of layer) for (let i = 0; i < frames; i++) channel[i] *= scale
  return layers
}


/** Concert-hall reverb baked into a looped channel (Schroeder/Freeverb: 8 damped combs + 4 allpasses, about 2 s decay).
 * Runs over the loop twice and keeps the second pass, so the tail wraps around and the loop stays seamless.
 * Channel 1 uses slightly longer delays for stereo width. */
function hall(channel: Float32Array, rate: number, side: number, wet = .45) {
  const k = rate / 44100, spread = side ? 23 : 0
  const combs = [1116, 1188, 1277, 1356, 1422, 1491, 1557, 1617].map(d => ({ buffer: new Float64Array(Math.round((d + spread) * k)), index: 0, low: 0 }))
  const passes = [556, 441, 341, 225].map(d => ({ buffer: new Float64Array(Math.round((d + spread) * k)), index: 0 }))
  const out = new Float32Array(channel.length)
  for (let pass = 0; pass < 2; pass++) for (let i = 0; i < channel.length; i++) {
    const input = channel[i] * .015
    let sum = 0
    for (const comb of combs) {
      const delayed = comb.buffer[comb.index]; comb.low = delayed * .8 + comb.low * .2  // damping: darker tail
      comb.buffer[comb.index] = input + comb.low * .86; comb.index = (comb.index + 1) % comb.buffer.length; sum += delayed
    }
    for (const allpass of passes) {
      const delayed = allpass.buffer[allpass.index]; allpass.buffer[allpass.index] = sum + delayed * .5
      allpass.index = (allpass.index + 1) % allpass.buffer.length; sum = delayed - sum
    }
    if (pass) out[i] = sum
  }
  const dryLevel = Math.sqrt(channel.reduce((a, b) => a + b * b, 0)), wetLevel = Math.sqrt(out.reduce((a, b) => a + b * b, 0)) || 1
  for (let i = 0; i < channel.length; i++) channel[i] = (1 - wet * .5) * channel[i] + wet * out[i] * dryLevel / wetLevel
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
