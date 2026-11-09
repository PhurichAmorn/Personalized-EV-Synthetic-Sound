import { useEffect, useRef } from 'react'

const WINDOW_SECONDS = 15
const GREEN = '#3ddc84'
const RED = '#ff5a52'
const BLUE = '#4aa3ff'

function prepare(canvas: HTMLCanvasElement) {
  const ratio = window.devicePixelRatio || 1
  const width = canvas.clientWidth, height = canvas.clientHeight
  if (canvas.width !== Math.round(width * ratio) || canvas.height !== Math.round(height * ratio)) {
    canvas.width = Math.round(width * ratio); canvas.height = Math.round(height * ratio)
  }
  const drawing = canvas.getContext('2d')
  if (!drawing) return null
  drawing.setTransform(ratio, 0, 0, ratio, 0, 0)
  drawing.clearRect(0, 0, width, height)
  return { drawing, width, height }
}

/** Throttle (green) and brake (red) over the last seconds. Scrolls continuously; no axes. */
export function InputGraph({ throttle, brake }: { throttle: number; brake: number }) {
  const canvas = useRef<HTMLCanvasElement>(null)
  const samples = useRef<{ t: number; throttle: number; brake: number }[]>([])
  // Runs after every render; the app re-renders once per backend state update, so each render adds one sample.
  useEffect(() => {
    const element = canvas.current
    if (!element) return
    const now = performance.now()
    const list = samples.current
    list.push({ t: now, throttle, brake })
    while (list.length > 1 && now - list[0].t > WINDOW_SECONDS * 1000) list.shift()
    const surface = prepare(element)
    if (!surface) return
    const { drawing, width, height } = surface
    const trace = (key: 'throttle' | 'brake', color: string) => {
      drawing.beginPath()
      list.forEach((sample, index) => {
        const x = width - (now - sample.t) / (WINDOW_SECONDS * 1000) * width
        const y = height - 2 - Math.max(0, Math.min(1, sample[key])) * (height - 4)
        if (index === 0) drawing.moveTo(x, y); else drawing.lineTo(x, y)
      })
      drawing.strokeStyle = color; drawing.lineWidth = 1.6; drawing.lineJoin = 'round'; drawing.stroke()
    }
    trace('brake', RED)
    trace('throttle', GREEN)
  })
  return <canvas ref={canvas} className="overlay-graph" aria-label="Throttle (green) and brake (red) over the last 15 seconds" role="img" />
}

/** Signed motor load over the last seconds: drive above the dashed zero line (light), regen below it (blue). Line only. */
export function LoadGraph({ load }: { load: number }) {
  const canvas = useRef<HTMLCanvasElement>(null)
  const samples = useRef<{ t: number; v: number }[]>([])
  useEffect(() => {
    const element = canvas.current
    if (!element) return
    const now = performance.now()
    const list = samples.current
    list.push({ t: now, v: Math.max(-1, Math.min(1, load)) })
    while (list.length > 1 && now - list[0].t > WINDOW_SECONDS * 1000) list.shift()
    const surface = prepare(element)
    if (!surface) return
    const { drawing, width, height } = surface
    const mid = height / 2
    drawing.strokeStyle = 'rgb(255 255 255 / 28%)'; drawing.lineWidth = 1; drawing.setLineDash([3, 3])
    drawing.beginPath(); drawing.moveTo(0, mid); drawing.lineTo(width, mid); drawing.stroke(); drawing.setLineDash([])
    const path = () => {
      drawing.beginPath()
      list.forEach((sample, index) => {
        const x = width - (now - sample.t) / (WINDOW_SECONDS * 1000) * width
        const y = mid - sample.v * (mid - 3)
        if (index === 0) drawing.moveTo(x, y); else drawing.lineTo(x, y)
      })
    }
    drawing.lineWidth = 1.6; drawing.lineJoin = 'round'
    for (const [top, bottom, color] of [[0, mid, '#e5e5e5'], [mid, height, BLUE]] as const) {
      drawing.save(); drawing.beginPath(); drawing.rect(0, top, width, bottom - top); drawing.clip()
      path(); drawing.strokeStyle = color; drawing.stroke(); drawing.restore()
    }
  })
  return <canvas ref={canvas} className="overlay-graph" aria-label="Motor load over the last 15 seconds: drive above zero, regeneration below" role="img" />
}

function drawWave(canvas: HTMLCanvasElement | null, wave: ArrayLike<number>, level: { peak: number }) {
  if (!canvas || !wave.length) return
  const surface = prepare(canvas)
  if (!surface) return
  const { drawing, width, height } = surface
  // Auto-gain: the output is quiet by design (-24 LUFS), so scale the trace to the recent peak (fast attack, slow release).
  let peak = 0
  for (let i = 0; i < wave.length; i++) peak = Math.max(peak, Math.abs(wave[i]))
  level.peak = Math.max(peak, level.peak * .96)
  const gain = level.peak > .002 ? Math.min(40, .9 / level.peak) : 1
  // Start on a rising zero crossing so successive frames line up.
  let start = 0
  for (let i = 1; i < wave.length / 2; i++) if (wave[i - 1] <= 0 && wave[i] > 0) { start = i; break }
  const count = Math.min(wave.length - start, 1024)
  drawing.strokeStyle = 'rgb(255 255 255 / 12%)'; drawing.lineWidth = 1
  drawing.beginPath(); drawing.moveTo(0, height / 2); drawing.lineTo(width, height / 2); drawing.stroke()
  drawing.beginPath()
  for (let i = 0; i < count; i++) {
    const x = i / Math.max(1, count - 1) * width
    const y = height / 2 - Math.max(-1, Math.min(1, wave[start + i] * gain)) * (height / 2 - 2)
    if (i === 0) drawing.moveTo(x, y); else drawing.lineTo(x, y)
  }
  drawing.strokeStyle = '#d6d6d6'; drawing.lineWidth = 1.4; drawing.stroke()
}

/** Live sound waveform: from the granular player's analyser (GS) or the native engine (Comfort/Sport/Deep). */
export function WaveGraph({ granular, analyser, onCommand }: {
  granular: boolean
  analyser: () => AnalyserNode | null
  onCommand: (name: string, payload?: Record<string, unknown>) => Promise<unknown> | void
}) {
  const canvas = useRef<HTMLCanvasElement>(null)
  const level = useRef({ peak: 0 })
  const command = useRef(onCommand)
  command.current = onCommand
  const getAnalyser = useRef(analyser)
  getAnalyser.current = analyser
  useEffect(() => {
    let disposed = false
    if (granular) {
      const samples = new Float32Array(2048)
      let frame = 0
      const tick = () => {
        if (disposed) return
        const node = getAnalyser.current()
        if (node) node.getFloatTimeDomainData(samples); else samples.fill(0)
        drawWave(canvas.current, samples, level.current)
        frame = window.setTimeout(tick, 50)  // ~20 fps is plenty for a small trace
      }
      tick()
      return () => { disposed = true; window.clearTimeout(frame) }
    }
    void command.current('debugVisible', { value: true })
    const timer = window.setInterval(() => {
      void Promise.resolve(command.current('soundDebug')).then(data => {
        if (!disposed) drawWave(canvas.current, (data as { waveform?: number[] } | undefined)?.waveform ?? [], level.current)
      }).catch(() => {})
    }, 100)
    return () => { disposed = true; window.clearInterval(timer); void command.current('debugVisible', { value: false }) }
  }, [granular])
  return <canvas ref={canvas} className="overlay-graph overlay-wave" aria-label="Sound waveform" role="img" />
}

/** Three vertical bars, colour only: throttle (green) and brake (red) from the controller, regen (blue) from the car. */
export function VerticalBars({ throttle, brake, regen }: { throttle: number; brake: number; regen: number }) {
  const bar = (label: string, value: number, color: string) => <div className="overlay-vbar" role="meter" aria-label={label} aria-valuemin={0} aria-valuemax={100} aria-valuenow={Math.round(Math.max(0, Math.min(1, value)) * 100)}>
    <b style={{ height: `${Math.max(0, Math.min(1, value)) * 100}%`, background: color }} />
  </div>
  return <div className="overlay-vbars">
    {bar('Controller throttle', throttle, GREEN)}
    {bar('Controller brake', brake, RED)}
    {bar('Regeneration', regen, BLUE)}
  </div>
}
