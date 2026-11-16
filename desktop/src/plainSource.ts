/** Plain base source: a steady 5 s loop with no chorus, reverb, vibrato or wobble.
 * All motion and space come later, after the granular player (Sound Lab transformation stage).
 * Every partial sits on the 0.2 Hz grid, so the 5 s loop repeats seamlessly. */
export type PlainParams = {
  rootHz: number      // register before the driving pitch map (rest is about 10 semitones lower)
  brightness: number  // 0 dark (harmonics fall 15 dB/octave) .. 1 bright (1.8 dB/octave); 0.64 is a sawtooth
  hollow: number      // 0 full (all harmonics) .. 1 hollow (odd harmonics only, clarinet-like)
  bell: number        // 0 in tune .. 1 bell/glass (upper partials stretched sharp)
  air: number         // 0 clean .. 1 breathy (filtered noise mixed in). Fixed at 0 in every preset (decided 2026-11-14); slider kept for experiments only
  softTop: number     // Hz where harmonics roll off steeply (24 dB/octave); moves with pitch like an instrument's own tone
  chord: number       // 0 one note .. 1 soft in-tune chord: a fourth below (0.75x) and a fifth above (1.5x), like the Strings pad
  // Extras (2026-11-14), so A can reach the original styles. Off by default.
  vowel: number       // 0 off .. 1 strong voice-like formant peaks (Choir uses this shape at 1)
  vowelShape: number  // 0 "ooh" (300/870/2240 Hz) .. .5 "aah" (710/1020/2600, as Choir) .. 1 "ee" (270/2290/3010)
  fundamental: number // level of the lowest harmonic: 1 normal .. 0.05 weak, so upper harmonics lead (Electric)
  whine: number       // 0 off .. 1 an extra high tone at whineRatio x the note, with side tones at .41/.68/.9 of it (Jet)
  whineRatio: number  // whine pitch as a multiple of the note; out of tune with the harmonics on purpose
  bellModes: number   // 0 harmonics stretched by Bell .. 1 the six Glass bell modes (1, 2.01, 2.73, 4.17, 5.43, 6.79)
  // Synth extras (2026-11-15, Night drive): analog-style pad.
  detune: number      // 0 one copy per note .. 1 five copies spread +-14 cents (supersaw shimmer)
  chordType: number   // 0 open (4th below + 5th above) .. 1 minor (minor 3rd + 5th) .. 2 minor 7th (+ minor 7th) .. 3 bleak (5th + octave, Dark ambience): equal-tempered
  lowDetune: number   // 0 low partials stay clean .. 1 detune them too: slow breathing beats on purpose (Dark ambience, 2026-11-15)
}
export const EXTRAS_OFF = { vowel: 0, vowelShape: .5, fundamental: 1, whine: 0, whineRatio: 8.75, bellModes: 0, detune: 0, chordType: 0, lowDetune: 0 }
export const EXTRA_KEYS = Object.keys(EXTRAS_OFF) as (keyof typeof EXTRAS_OFF)[]
export const PLAIN_RANGES: Record<keyof PlainParams, { min: number; max: number; step: number; label: string; low: string; high: string }> = {
  rootHz: { min: 40, max: 350, step: 1, label: 'Register', low: 'Deep', high: 'High' },
  brightness: { min: 0, max: 1, step: .01, label: 'Brightness', low: 'Dark', high: 'Bright' },
  hollow: { min: 0, max: 1, step: .01, label: 'Hollow', low: 'Full', high: 'Hollow' },
  bell: { min: 0, max: 1, step: .01, label: 'Bell', low: 'In tune', high: 'Bell / glass' },
  air: { min: 0, max: 1, step: .01, label: 'Air', low: 'Clean', high: 'Breathy' },
  softTop: { min: 800, max: 8000, step: 1, label: 'Soft top', low: 'Soft', high: 'Sharp' },
  chord: { min: 0, max: 1, step: .01, label: 'Chord', low: 'One note', high: '4th below + 5th above' },
  vowel: { min: 0, max: 1, step: .01, label: 'Vowel', low: 'Off', high: 'Strong' },
  vowelShape: { min: 0, max: 1, step: .01, label: 'Vowel shape', low: 'Ooh', high: 'Ee' },
  fundamental: { min: .05, max: 1, step: .01, label: 'Lowest-note level', low: 'Weak', high: 'Normal' },
  whine: { min: 0, max: 1, step: .01, label: 'Whine', low: 'Off', high: 'Loud' },
  whineRatio: { min: 3, max: 12, step: .05, label: 'Whine pitch', low: '3 × note', high: '12 × note' },
  bellModes: { min: 0, max: 1, step: 1, label: 'Bell type', low: 'Stretched', high: 'Glass modes' },
  detune: { min: 0, max: 1, step: .01, label: 'Detune (supersaw)', low: 'One copy', high: '±14 cents' },
  chordType: { min: 0, max: 3, step: 1, label: 'Chord type', low: 'Open', high: 'Bleak' },
  lowDetune: { min: 0, max: 1, step: 1, label: 'Detune low end', low: 'Clean', high: 'Breathing' },
}
export const PLAIN_DEFAULT: PlainParams = { rootHz: 175, brightness: .45, hollow: .2, bell: 0, air: 0, softTop: 1800, chord: .8, ...EXTRAS_OFF }
/** Starting points only; every one is the same generator with different settings. */
export const PLAIN_PRESETS: { name: string; params: PlainParams }[] = [
  { name: 'Warm', params: PLAIN_DEFAULT },
  { name: 'Pure', params: { ...EXTRAS_OFF, rootHz: 175, brightness: .05, hollow: .6, bell: 0, air: 0, softTop: 2000, chord: 0 } },
  { name: 'Reed', params: { ...EXTRAS_OFF, rootHz: 160, brightness: .7, hollow: .9, bell: 0, air: 0, softTop: 2500, chord: 0 } },
  { name: 'Bright', params: { ...EXTRAS_OFF, rootHz: 175, brightness: .75, hollow: .1, bell: 0, air: 0, softTop: 4000, chord: 0.3 } },
  { name: 'Glass', params: { ...EXTRAS_OFF, rootHz: 220, brightness: .55, hollow: .3, bell: .7, air: 0, softTop: 5000, chord: 0 } },
  { name: 'Soft', params: { ...EXTRAS_OFF, rootHz: 175, brightness: .3, hollow: .4, bell: 0, air: 0, softTop: 2200, chord: 0.4 } },
  { name: 'Deep', params: { ...EXTRAS_OFF, rootHz: 95, brightness: .4, hollow: .3, bell: 0, air: 0, softTop: 1500, chord: 0.4 } },
]
export const PLAIN_RATE = 48000
const grid = (hz: number) => Math.round(hz * 5) / 5

const VOWELS = [[300, 870, 2240], [710, 1020, 2600], [270, 2290, 3010]]  // ooh, aah, ee (F1-F3, Hz)
const CLEAN_BELOW = 700  // Hz: no detune below this (a vowel's first formant sits up to about 700 Hz)
const GLASS_MODES = [1, 2.01, 2.73, 4.17, 5.43, 6.79]
const WHINE_TONES = [[1, 1], [.41, .4], [.68, .45], [.9, .12]]  // ratio to the whine, level (as the Jet style)

export function plainPartials(p: PlainParams, ceiling = 9000) {
  const { rootHz, brightness, hollow, bell, softTop, chord } = p
  // Power slope plus an exponential fade (as in the Strings recipe): upper harmonics drop away faster, less buzz near 1-2 kHz.
  const slope = 2.5 - 2.2 * brightness, fade = .45 * (1 - brightness), stretch = .004 * bell
  const shape = p.vowelShape * 2, [from, to] = shape <= 1 ? [VOWELS[0], VOWELS[1]] : [VOWELS[1], VOWELS[2]], mix = shape <= 1 ? shape : shape - 1
  const [f1, f2, f3] = from.map((hz, i) => hz + (to[i] - hz) * mix)
  const gauss = (hz: number, center: number, width: number) => Math.exp(-.5 * ((hz - center) / width) ** 2)
  // Same formant weights as the Choir style; the vowel shapes the source, so it rises with pitch as in Choir.
  const vowel = (hz: number) => 1 - p.vowel + p.vowel * (.3 + 2.2 * gauss(hz, f1, 110) + 1.4 * gauss(hz, f2, 140) + .35 * gauss(hz, f3, 220))
  const partials: { hz: number; amp: number; phase: number; voice: number }[] = []
  // Guardrail: the 4th-below note makes the chord repeat at rootHz/4; at drive rest (about 0.53x) that drops under 20 Hz for
  // low registers and is heard as a flutter. Fade that note out between 160 and 130 Hz (the 5th above stays: repeat rootHz/2).
  const low = Math.max(0, Math.min(1, (rootHz - 130) / 30))
  // [stem, multiple, level]. Minor chords are equal-tempered (as a synth plays them): no exact common repeat, so no low pulse.
  const semi = (n: number) => 2 ** (n / 12)
  const notes = p.chordType < .5 ? [[0, 1, 1], [1, .75, .8 * chord * low], [2, 1.5, .5 * chord]]
    : p.chordType >= 2.5 ? [[0, 1, 1], [1, semi(7), .6 * chord], [2, 2, .45 * chord]]
    : [[0, 1, 1], [1, semi(3), .6 * chord], [2, semi(7), .5 * chord], ...(p.chordType >= 1.5 ? [[1, semi(10), .4 * chord]] : [])]
  // Detune: five copies of every partial spread in cents (uneven, as in a supersaw). Partials under CLEAN_BELOW stay as one
  // copy: detuned they beat slowly (up to 50% loudness swing at 1 Hz, measured 2026-11-15); synth pads keep the low end clean too.
  const spread = [[-1, .5], [-.37, .7], [0, 1], [.29, .7], [.83, .5]], clean = Math.hypot(...spread.map(([, level]) => level))  // same power as the five copies: tone balance unchanged
  const copies = p.detune > 0 ? spread.map(([at, level]) => [semi(at * .14 * p.detune), level]) : [[1, 1]]
  for (const [index, multiple, weight] of notes) {
    if (!weight) continue
    const voice: { hz: number; amp: number }[] = []
    for (const [cents, level] of copies) for (let n = 1; ; n++) {
      if (p.bellModes >= .5 && n > GLASS_MODES.length) break
      const low = copies.length > 1 && !p.lowDetune && rootHz * multiple * n < CLEAN_BELOW
      if (low && cents !== 1) continue
      const gain = low ? clean : level
      const ratio = p.bellModes >= .5 ? GLASS_MODES[n - 1] : n * Math.sqrt(1 + stretch * n * n)
      const hz = grid(rootHz * multiple * ratio * cents)
      if (hz > ceiling) break
      voice.push({ hz, amp: gain * weight * n ** -slope * Math.exp(-fade * (n - 1)) * (n % 2 ? 1 : 1 - .97 * hollow) * (n === 1 ? p.fundamental : 1) * vowel(hz) / (1 + (hz / softTop) ** 4) })
    }
    if (index === 0 && p.whine > 0) {
      const total = voice.reduce((sum, partial) => sum + partial.amp, 0)
      for (const [ratio, level] of WHINE_TONES) {
        const hz = grid(rootHz * p.whineRatio * ratio)
        if (hz < ceiling) voice.push({ hz, amp: .9 * p.whine * level * total })
      }
    }
    // Schroeder phases: spread the partial peaks over the cycle, so the waveform is as flat (unpeaky) as possible.
    voice.forEach((partial, n) => partials.push({ ...partial, phase: Math.PI * (n + 1) ** 2 / voice.length + multiple, voice: index }))
  }
  return partials
}

/** Three stereo stems: main note (with any air), 4th below, 5th above (silent when chord is 0). Same gain for all.
 * Each stem gets its own granular player, as the original player does per layer. Channels are identical: width is an effect.
 * Exactly in-tune chord notes repeat together at rootHz/4: at low registers that pulsed (rootHz 110 at drive rest: 32% loudness
 * pulse at 14.5 Hz, measured 2026-11-14), so plainPartials fades the 4th-below note out under 160 Hz. */
export function createPlainVoices(params: PlainParams, rate = PLAIN_RATE): Float32Array[][] {
  const frames = rate * 5, voices = [0, 1, 2].map(() => new Float64Array(frames))
  for (const { hz, amp, phase, voice } of plainPartials(params, Math.min(9000, rate * .45))) {
    if (amp < 1e-4) continue  // below -80 dB: inaudible, and skipping keeps the build fast
    // Rotating phasor instead of Math.sin per sample (about 5x faster); drift over 5 s is far below audibility.
    const step = 2 * Math.PI * hz / rate, c = Math.cos(step), d = Math.sin(step), tone = voices[voice]
    let sine = Math.sin(phase), cosine = Math.cos(phase)
    for (let i = 0; i < frames; i++) { tone[i] += amp * sine; const next = sine * c + cosine * d; cosine = cosine * c - sine * d; sine = next }
  }
  const rms = (data: Float64Array) => Math.sqrt(data.reduce((sum, value) => sum + value * value, 0) / data.length) || 1
  if (params.air > 0) {
    // Noise band near 0.8-5 kHz; filtered circularly (pre-rolled over the loop end) so the seam is clean.
    let seed = 7
    const white = Float64Array.from({ length: frames }, () => ((seed = (seed * 1664525 + 1013904223) >>> 0) / 2 ** 32) * 2 - 1)
    const band = new Float64Array(frames), high = 1 - Math.exp(-2 * Math.PI * 800 / rate), low = 1 - Math.exp(-2 * Math.PI * 5000 / rate)
    let slow = 0, fast = 0
    for (let pass = 0; pass < 2; pass++) for (let i = 0; i < frames; i++) {
      slow += high * (white[i] - slow); fast += low * (white[i] - slow - fast)
      if (pass) band[i] = fast
    }
    const scale = .6 * params.air * rms(voices[0]) / rms(band)
    for (let i = 0; i < frames; i++) voices[0][i] += band[i] * scale
  }
  const mix = voices[0].map((value, i) => value + voices[1][i] + voices[2][i])
  let peak = 0
  for (const value of mix) peak = Math.max(peak, Math.abs(value))
  const gain = Math.min(.13 / rms(mix), .7 / (peak || 1))
  return voices.map(tone => { const out = Float32Array.from(tone, value => value * gain); return [out, out.slice()] })
}

/** All voices mixed into one stereo loop (for analysis and tests). */
export function createPlainSource(params: PlainParams, rate = PLAIN_RATE): Float32Array[] {
  const [a, b, c] = createPlainVoices(params, rate)
  const out = Float32Array.from(a[0], (value, i) => value + b[0][i] + c[0][i])
  return [out, out.slice()]
}

/** Magnitude spectrum in dB (Hann window, radix-2 FFT) of the first `size` samples. */
export function spectrum(data: Float32Array, rate: number, size = 16384) {
  const re = new Float64Array(size), im = new Float64Array(size)
  for (let i = 0; i < size; i++) re[i] = (data[i % data.length] ?? 0) * (.5 - .5 * Math.cos(2 * Math.PI * i / size))
  for (let i = 1, j = 0; i < size; i++) {
    let bit = size >> 1
    for (; j & bit; bit >>= 1) j ^= bit
    j ^= bit
    if (i < j) { [re[i], re[j]] = [re[j], re[i]]; [im[i], im[j]] = [im[j], im[i]] }
  }
  for (let length = 2; length <= size; length <<= 1) {
    const angle = -2 * Math.PI / length
    for (let start = 0; start < size; start += length) for (let k = 0; k < length / 2; k++) {
      const wr = Math.cos(angle * k), wi = Math.sin(angle * k), a = start + k, b = a + length / 2
      const tr = re[b] * wr - im[b] * wi, ti = re[b] * wi + im[b] * wr
      re[b] = re[a] - tr; im[b] = im[a] - ti; re[a] += tr; im[a] += ti
    }
  }
  const db = new Float32Array(size / 2)
  let weighted = 0, total = 0
  for (let k = 0; k < size / 2; k++) {
    const power = (re[k] ** 2 + im[k] ** 2) / (size * size)
    db[k] = 10 * Math.log10(power + 1e-14)
    weighted += power * k * rate / size; total += power
  }
  return { db, binHz: rate / size, centroid: total ? weighted / total : 0 }
}

/** Synthetic room impulse: decaying stereo noise, darker as it fades. `seconds` is the 60 dB decay. */
export function roomImpulse(rate: number, seconds: number) {
  const frames = Math.round(rate * seconds), channels = [new Float32Array(frames), new Float32Array(frames)]
  let seed = 11
  for (const channel of channels) {
    let smooth = 0
    for (let i = 0; i < frames; i++) {
      const t = i / frames, white = ((seed = (seed * 1664525 + 1013904223) >>> 0) / 2 ** 32) * 2 - 1
      smooth += (1 - .85 * t) * (white - smooth)  // damping grows over the tail
      channel[i] = smooth * Math.exp(-6.9 * t) * (i < rate * .004 ? i / (rate * .004) : 1)
    }
  }
  return channels
}
