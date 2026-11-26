/** FFT and strongest partials of one audio frame, for the Sound signal popup. */
export type Frame = { rate: number; samples: ArrayLike<number>; source: 'app' | 'backend' }

export function fft(re: Float64Array, im: Float64Array) {
  const n = re.length
  for (let i = 1, j = 0; i < n; i++) {
    let bit = n >> 1
    for (; j & bit; bit >>= 1) j ^= bit
    j ^= bit
    if (i < j) { [re[i], re[j]] = [re[j], re[i]]; [im[i], im[j]] = [im[j], im[i]] }
  }
  for (let size = 2; size <= n; size <<= 1) {
    const step = -2 * Math.PI / size
    for (let start = 0; start < n; start += size) for (let k = 0; k < size / 2; k++) {
      const c = Math.cos(step * k), s = Math.sin(step * k), a = start + k, b = a + size / 2
      const tr = re[b] * c - im[b] * s, ti = re[b] * s + im[b] * c
      re[b] = re[a] - tr; im[b] = im[a] - ti; re[a] += tr; im[a] += ti
    }
  }
}

/** Spectrum (dB per bin), level, and the two strongest partials of one frame. */
export function analyse({ rate, samples }: Frame) {
  const n = 2 ** Math.floor(Math.log2(Math.max(256, samples.length)))
  const offset = samples.length - n, re = new Float64Array(n), im = new Float64Array(n)
  let sum = 0, window = 0
  for (let i = 0; i < n; i++) { const v = samples[offset + i] ?? 0, w = .5 - .5 * Math.cos(2 * Math.PI * i / (n - 1)); sum += v * v; re[i] = v * w; window += w }
  fft(re, im)
  const db = new Float32Array(n / 2)
  for (let i = 0; i < n / 2; i++) db[i] = 20 * Math.log10(Math.max(1e-6, 2 * Math.hypot(re[i], im[i]) / window))
  const hz = rate / n, level = 10 * Math.log10(Math.max(1e-9, sum / n))
  const peaks: { f: number; db: number }[] = []
  for (let i = Math.ceil(50 / hz); i < Math.min(n / 2 - 1, 4000 / hz); i++) {
    if (db[i] > -70 && db[i] >= db[i - 1] && db[i] > db[i + 1]) {
      const a = db[i - 1], b = db[i], c = db[i + 1], shift = (a - c) / (2 * (a - 2 * b + c) || 1)  // parabolic peak
      peaks.push({ f: (i + shift) * hz, db: b })
    }
  }
  peaks.sort((a, b) => b.db - a.db)
  return { db, hz, level, top: peaks.slice(0, 2), rate }
}
