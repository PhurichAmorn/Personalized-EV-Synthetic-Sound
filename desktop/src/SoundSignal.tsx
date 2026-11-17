import { useEffect, useRef, useState } from 'react'
import type { SoundDebug } from './Diagnostics'
import { analyse, type Frame } from './signalAnalysis'

/** Sound signal: what the car plays now, drawn four ways (waveform, EQ bars, Chladni plate, time and modulation). */
type Source = Frame['source']
type Moment = { t: number; level: number; pitch: number | null; column: Float32Array }
const SECONDS = 10                 // history shown in the time panel
const BANDS = 28, SPEC_BINS = 64   // EQ bars; spectrogram rows
const LOW = 40, HIGH = 16000
const SAND = 2600
const GLOW = '#5fd38d'
// Plate modes (n, m), lowest first: higher pitch picks a busier pattern.
const MODES = Array.from({ length: 8 }, (_, n) => Array.from({ length: 8 }, (_, m) => [n + 1, m + 2] as const)).flat()
  .filter(([n, m]) => n < m).sort((a, b) => a[0] ** 2 + a[1] ** 2 - b[0] ** 2 - b[1] ** 2)

const band = (i: number, count: number, high: number) => LOW * (high / LOW) ** (i / count)
const norm = (db: number) => Math.min(1, Math.max(0, (db + 90) / 80))

/** Right-side panel of the dashboard. `analyser`: the app's sound (GS or a session sound); `soundDebug`: the backend synth (themes). */
export default function SoundSignal({ analyser, soundDebug, onClose }: { analyser: () => AnalyserNode | null; soundDebug: SoundDebug | null; onClose: () => void }) {
  const canvases = useRef<(HTMLCanvasElement | null)[]>([])
  const [source, setSource] = useState<Source | null>(null)
  const store = useRef({
    frame: null as Frame | null, appAt: 0, info: null as ReturnType<typeof analyse> | null, history: [] as Moment[],
    bars: new Float32Array(BANDS), holds: new Float32Array(BANDS), sand: Float32Array.from({ length: 2 * SAND }, Math.random),
    mode: [] as (readonly [number, number, number])[], field: null as OffscreenCanvas | null, fieldKey: '',
  })

  const ingest = (frame: Frame) => {
    const s = store.current, info = analyse(frame), now = performance.now() / 1000
    const high = Math.min(8000, info.rate / 2), column = new Float32Array(SPEC_BINS)
    for (let r = 0; r < SPEC_BINS; r++) {
      const from = Math.floor(band(r, SPEC_BINS, high) / info.hz), to = Math.max(from + 1, Math.floor(band(r + 1, SPEC_BINS, high) / info.hz))
      let top = -120; for (let i = from; i < to && i < info.db.length; i++) top = Math.max(top, info.db[i]); column[r] = norm(top)
    }
    s.frame = frame; s.info = info
    s.history.push({ t: now, level: info.level, pitch: info.top[0]?.f ?? null, column })
    while (s.history.length && s.history[0].t < now - SECONDS) s.history.shift()
  }
  const silent = (x: ArrayLike<number>) => { for (let i = 0; i < x.length; i++) if (Math.abs(x[i]) >= 1e-4) return false; return true }
  const read = useRef(analyser)
  read.current = analyser
  useEffect(() => {  // app sound, about 30 times a second
    const samples = new Float32Array(2048)
    const timer = window.setInterval(() => {
      const node = read.current()
      if (!node) return
      const data = samples.subarray(0, node.fftSize); node.getFloatTimeDomainData(data)
      if (silent(data)) return  // nothing app-side: the backend may be playing
      store.current.appAt = performance.now(); ingest({ rate: node.context.sampleRate, samples: Float32Array.from(data), source: 'app' }); setSource('app')
    }, 33)
    return () => window.clearInterval(timer)
  }, [])
  useEffect(() => {  // backend synth when the app plays nothing
    if (!soundDebug?.waveform.length || performance.now() - store.current.appAt < 400) return
    const quiet = silent(soundDebug.waveform)
    if (!quiet) ingest({ rate: soundDebug.waveform.length / soundDebug.duration_ms * 1000, samples: soundDebug.waveform, source: 'backend' })
    setSource(quiet ? null : 'backend')
  }, [soundDebug])

  useEffect(() => {
    let frame = 0
    const draw = () => {
      frame = requestAnimationFrame(draw)
      canvases.current.forEach((canvas, panel) => {
        if (!canvas) return
        const ratio = window.devicePixelRatio || 1, w = canvas.clientWidth, h = canvas.clientHeight
        if (canvas.width !== Math.round(w * ratio) || canvas.height !== Math.round(h * ratio)) { canvas.width = Math.round(w * ratio); canvas.height = Math.round(h * ratio) }
        const g = canvas.getContext('2d')!
        g.setTransform(ratio, 0, 0, ratio, 0, 0); g.clearRect(0, 0, w, h); g.shadowBlur = 0
        ;[waveform, bars, plate, timeline][panel](g, w, h, store.current)
      })
    }
    frame = requestAnimationFrame(draw)
    return () => cancelAnimationFrame(frame)
  }, [])

  const label = source === 'app' ? 'App sound' : source === 'backend' ? 'Backend synth' : 'Silent'
  const panel = (index: number, title: string, note: string) => <section className="signal-panel">
    <div className="signal-panel-title"><span>{title}</span><small>{note}</small></div>
    <canvas ref={element => { canvases.current[index] = element }} role="img" aria-label={title} />
  </section>
  return <aside className="signal-side" aria-label="Sound signal">
    <header className="signal-side-header">
      <h2>Sound signal</h2>
      <span className="signal-source"><i className={'overlay-led' + (source ? ' on' : '')} />{label}</span>
      <button className="signal-close" type="button" aria-label="Close sound signal" onClick={onClose}>×</button>
    </header>
    {panel(0, 'Waveform', 'pressure over time · phase scope')}
    {panel(1, 'Frequency spectrum', '40 Hz – 16 kHz')}
    {panel(2, 'Chladni plate', 'simulated, from the strongest partials')}
    {panel(3, 'Time & modulation', `decay · pulsing · vibrato · last ${SECONDS} s`)}
  </aside>
}

type Store = {
  frame: Frame | null; info: ReturnType<typeof analyse> | null; history: Moment[]; bars: Float32Array; holds: Float32Array; sand: Float32Array
  mode: (readonly [number, number, number])[]; field: OffscreenCanvas | null; fieldKey: string
}
const text = (g: CanvasRenderingContext2D, value: string, x: number, y: number, align: CanvasTextAlign = 'left') => {
  g.shadowBlur = 0; g.fillStyle = '#9a9a9a'; g.font = '10px "IBM Plex Mono", ui-monospace, monospace'; g.textAlign = align; g.fillText(value, x, y)
}
const glow = (g: CanvasRenderingContext2D, color: string, blur = 8) => { g.strokeStyle = color; g.shadowColor = color; g.shadowBlur = blur }

/** Oscilloscope locked to a rising zero crossing (about three periods), plus x(t) against x(t + quarter period). */
function waveform(g: CanvasRenderingContext2D, w: number, h: number, s: Store) {
  const x = s.frame?.samples, info = s.info
  if (!x || !info) return text(g, 'No sound', w / 2, h / 2, 'center')
  const scope = Math.min(h, w * .32), width = w - scope - 12, period = info.top[0] ? info.rate / info.top[0].f : info.rate / 100
  const span = Math.min(x.length / 2, Math.max(64, Math.round(period * 3)))
  let start = 0; for (let i = 1; i < x.length - span; i++) if (x[i - 1] < 0 && x[i] >= 0) { start = i; break }
  let peak = 1e-4; for (let i = 0; i < x.length; i++) peak = Math.max(peak, Math.abs(x[i]))
  g.strokeStyle = '#2c2c2c'; g.beginPath(); g.moveTo(0, h / 2); g.lineTo(width, h / 2); g.stroke()
  glow(g, '#e8e8e8'); g.lineWidth = 1.6; g.beginPath()
  for (let i = 0; i <= span; i++) { const px = i / span * width, py = h / 2 - x[start + i] / peak * h * .42; i ? g.lineTo(px, py) : g.moveTo(px, py) }
  g.stroke()
  const lag = Math.max(1, Math.round(period / 4)), cx = width + 12 + scope / 2, cy = h / 2
  g.shadowBlur = 0; g.strokeStyle = '#2c2c2c'; g.strokeRect(width + 12, (h - scope) / 2, scope, scope)
  glow(g, GLOW, 6); g.lineWidth = 1; g.beginPath()
  for (let i = 0; i + lag < x.length; i += 2) { const px = cx + x[i] / peak * scope * .45, py = cy - x[i + lag] / peak * scope * .45; i ? g.lineTo(px, py) : g.moveTo(px, py) }
  g.stroke()
  text(g, `peak ${(20 * Math.log10(peak)).toFixed(1)} dBFS · rms ${info.level.toFixed(1)} dBFS`, 4, 12)
  text(g, info.top[0] ? `${(span / info.rate * 1000).toFixed(1)} ms · ${info.top[0].f.toFixed(0)} Hz` : `${(span / info.rate * 1000).toFixed(1)} ms`, 4, h - 4)
}

/** Log-spaced bands, falling slowly, with peak-hold ticks. */
function bars(g: CanvasRenderingContext2D, w: number, h: number, s: Store) {
  const info = s.info, high = info ? Math.min(HIGH, info.rate / 2) : HIGH, gap = 3, size = (w - gap * (BANDS - 1)) / BANDS, floor = h - 16
  for (let b = 0; b < BANDS; b++) {
    let top = -120
    if (info) { const from = Math.floor(band(b, BANDS, high) / info.hz), to = Math.max(from + 1, Math.floor(band(b + 1, BANDS, high) / info.hz)); for (let i = from; i < to && i < info.db.length; i++) top = Math.max(top, info.db[i]) }
    s.bars[b] = Math.max(norm(top), s.bars[b] - .015); s.holds[b] = Math.max(s.bars[b], s.holds[b] - .004)
    const x = b * (size + gap), y = floor - s.bars[b] * (floor - 6)
    const fill = g.createLinearGradient(0, floor, 0, 6); fill.addColorStop(0, '#3a3a3a'); fill.addColorStop(1, '#f2f2f2')
    g.shadowColor = '#ffffff'; g.shadowBlur = 6; g.fillStyle = fill; g.fillRect(x, y, size, floor - y)
    g.shadowColor = GLOW; g.fillStyle = GLOW; g.fillRect(x, floor - s.holds[b] * (floor - 6) - 2, size, 2)
  }
  for (const f of [100, 1000, 10000]) if (f < high) text(g, f >= 1000 ? `${f / 1000}k` : `${f}`, Math.log(f / LOW) / Math.log(high / LOW) * w, h - 2, 'center')
}

/** Chladni figure: sand shaken where the plate moves, so it gathers on the still (nodal) lines of the current mode. */
function plate(g: CanvasRenderingContext2D, w: number, h: number, s: Store) {
  const size = Math.min(w, h - 14), ox = (w - size) / 2, info = s.info
  const pick = (f: number) => MODES[Math.max(0, Math.min(MODES.length - 1, Math.round(Math.log(f / 60) / Math.log(4000 / 60) * (MODES.length - 1))))]
  const top = info?.top ?? []
  s.mode = top.map(p => [...pick(p.f), 10 ** ((p.db - top[0].db) / 20)] as const)
  const z = (x: number, y: number) => s.mode.reduce((sum, [n, m, a]) => sum + a * (Math.cos(n * Math.PI * x) * Math.cos(m * Math.PI * y) - Math.cos(m * Math.PI * x) * Math.cos(n * Math.PI * y)), 0)
  const key = s.mode.map(([n, m, a]) => `${n}${m}${a.toFixed(1)}`).join()
  if (key !== s.fieldKey) {  // faint picture of the vibration, redrawn only when the mode changes
    const cells = 96, image = new ImageData(cells, cells)
    for (let j = 0; j < cells; j++) for (let i = 0; i < cells; i++) { const v = Math.min(1, Math.abs(z(i / cells, j / cells)) / 2), o = 4 * (j * cells + i); image.data.set([30 + 40 * v, 30 + 40 * v, 32 + 40 * v, 255], o) }
    s.field = new OffscreenCanvas(cells, cells); s.field.getContext('2d')!.putImageData(image, 0, 0); s.fieldKey = key
  }
  g.fillStyle = '#121212'; g.fillRect(ox, 0, size, size)
  if (s.field) g.drawImage(s.field, ox, 0, size, size)
  const shake = info && s.mode.length ? Math.min(1, Math.max(0, (info.level + 70) / 50)) * .02 : 0
  g.fillStyle = '#f4efe2'; g.shadowColor = '#f4efe2'; g.shadowBlur = 2
  for (let p = 0; p < SAND; p++) {
    let x = s.sand[2 * p], y = s.sand[2 * p + 1]
    const move = shake * Math.min(1.5, Math.abs(z(x, y)))
    x = Math.min(1, Math.max(0, x + (Math.random() - .5) * move)); y = Math.min(1, Math.max(0, y + (Math.random() - .5) * move))
    s.sand[2 * p] = x; s.sand[2 * p + 1] = y; g.fillRect(ox + x * size, y * size, 1.3, 1.3)
  }
  text(g, s.mode.length ? `mode (${s.mode[0][0]}, ${s.mode[0][1]})${s.mode[1] ? ` + (${s.mode[1][0]}, ${s.mode[1][1]})` : ''} · ${top.map(p => `${p.f.toFixed(0)} Hz`).join(' + ')}` : 'silent: sand at rest', w / 2, h - 2, 'center')
}

/** Three strips over time: level with the decay rate of a falling tail (reverb) and pulse rate (tremolo), pitch with vibrato depth, spectrogram. */
function timeline(g: CanvasRenderingContext2D, w: number, h: number, s: Store) {
  const rows = s.history, now = performance.now() / 1000, strip = (h - 8) / 3, X = (t: number) => w - (now - t) / SECONDS * w
  g.strokeStyle = '#262626'; for (let r = 1; r < 3; r++) { g.beginPath(); g.moveTo(0, r * strip + 2); g.lineTo(w, r * strip + 2); g.stroke() }
  if (rows.length < 2) return text(g, 'No sound yet', w / 2, h / 2, 'center')
  // Level, -80..0 dBFS
  glow(g, '#e8e8e8', 6); g.lineWidth = 1.4; g.beginPath()
  rows.forEach((m, i) => { const y = strip - 4 - Math.max(0, Math.min(1, (m.level + 80) / 80)) * (strip - 14); i ? g.lineTo(X(m.t), y) : g.moveTo(X(m.t), y) }); g.stroke()
  const recent = rows.filter(m => m.t > now - .6), tail = slope(recent.map(m => m.t), recent.map(m => m.level))
  const pulse = pulseRate(rows.filter(m => m.t > now - 4))
  text(g, `level ${rows[rows.length - 1].level.toFixed(0)} dBFS${tail < -6 && recent[0].level > -70 ? ` · tail ${tail.toFixed(0)} dB/s ≈ ${(60 / -tail).toFixed(1)} s to −60 dB` : ''}${pulse ? ` · pulsing ${pulse.toFixed(1)} Hz` : ''}`, 4, 11)
  // Pitch, log 50..1000 Hz
  const top = strip + 2, Y = (f: number) => top + strip - 4 - Math.log(f / 50) / Math.log(20) * (strip - 14)
  glow(g, GLOW, 5); g.fillStyle = GLOW
  rows.forEach(m => { if (m.pitch) g.fillRect(X(m.t) - 1, Y(Math.min(1000, Math.max(50, m.pitch))) - 1, 2, 2) })
  const voiced = rows.filter(m => m.pitch && m.t > now - 1), cents = voiced.map(m => 1200 * Math.log2(m.pitch! / voiced[0].pitch!))
  const mean = cents.reduce((a, b) => a + b, 0) / Math.max(1, cents.length), spread = Math.sqrt(cents.reduce((a, c) => a + (c - mean) ** 2, 0) / Math.max(1, cents.length))
  const drift = slope(voiced.map(m => m.t), cents)
  const pitchNow = rows[rows.length - 1].pitch
  text(g, pitchNow ? `pitch ${pitchNow.toFixed(0)} Hz${voiced.length > 5 ? ` · vibrato ±${spread.toFixed(0)} cents · shift ${(drift / 100).toFixed(1)} st/s` : ''}` : 'pitch —', 4, top + 11)
  // Spectrogram, 40 Hz..8 kHz
  const base = 2 * strip + 4, cell = (strip - 4) / SPEC_BINS
  g.shadowBlur = 0
  rows.forEach((m, i) => {
    const x = X(m.t), next = i + 1 < rows.length ? X(rows[i + 1].t) : w
    for (let r = 0; r < SPEC_BINS; r++) { const v = m.column[r]; if (v < .05) continue; g.fillStyle = `rgb(${40 + 215 * v} ${40 + 215 * v} ${44 + 211 * v})`; g.fillRect(x, base + strip - 4 - (r + 1) * cell, Math.max(1, next - x + .5), cell + .5) }
  })
  text(g, 'spectrogram 40 Hz – 8 kHz', 4, base + 11)
}

function slope(t: number[], v: number[]) {
  if (t.length < 4) return 0
  const mt = t.reduce((a, b) => a + b) / t.length, mv = v.reduce((a, b) => a + b) / v.length
  let num = 0, den = 0; t.forEach((x, i) => { num += (x - mt) * (v[i] - mv); den += (x - mt) ** 2 })
  return den ? num / den : 0
}

/** Strongest repetition of the level between 0.5 and 10 Hz (tremolo, pump, pulsing), if clear. */
function pulseRate(rows: Moment[]) {
  if (rows.length < 30) return null
  const dt = (rows[rows.length - 1].t - rows[0].t) / (rows.length - 1), v = rows.map(m => m.level), mean = v.reduce((a, b) => a + b) / v.length
  const d = v.map(x => x - mean), energy = d.reduce((a, x) => a + x * x, 0)
  if (energy / v.length < .25) return null  // flatter than ±0.5 dB
  let best = 0, lag = 0
  for (let k = Math.max(1, Math.round(.1 / dt)); k <= Math.round(2 / dt) && k < v.length / 2; k++) {
    let c = 0; for (let i = 0; i + k < d.length; i++) c += d[i] * d[i + k]
    if (c / energy > best) { best = c / energy; lag = k }
  }
  return best > .4 ? 1 / (lag * dt) : null
}
