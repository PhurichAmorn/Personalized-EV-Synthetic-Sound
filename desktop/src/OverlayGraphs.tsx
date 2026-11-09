import { useEffect, useRef } from 'react'

const WINDOW_SECONDS = 15
const GREEN = '#3ddc84'
const RED = '#ff5a52'

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
      drawing.lineTo(width, height); drawing.lineTo(width - (now - list[0].t) / (WINDOW_SECONDS * 1000) * width, height); drawing.closePath()
      drawing.globalAlpha = .16; drawing.fillStyle = color; drawing.fill(); drawing.globalAlpha = 1
    }
    trace('brake', RED)
    trace('throttle', GREEN)
  })
  return <canvas ref={canvas} className="overlay-graph" aria-label="Throttle (green) and brake (red) over the last 15 seconds" role="img" />
}

function drawWave(canvas: HTMLCanvasElement | null, wave: ArrayLike<number>) {
  if (!canvas || !wave.length) return
  const surface = prepare(canvas)
  if (!surface) return
  const { drawing, width, height } = surface
  // Start on a rising zero crossing so successive frames line up.
  let start = 0
  for (let i = 1; i < wave.length / 2; i++) if (wave[i - 1] <= 0 && wave[i] > 0) { start = i; break }
  const count = Math.min(wave.length - start, 1024)
  drawing.strokeStyle = 'rgb(255 255 255 / 12%)'; drawing.lineWidth = 1
  drawing.beginPath(); drawing.moveTo(0, height / 2); drawing.lineTo(width, height / 2); drawing.stroke()
  drawing.beginPath()
  for (let i = 0; i < count; i++) {
    const x = i / Math.max(1, count - 1) * width
    const y = height / 2 - Math.max(-1, Math.min(1, wave[start + i])) * (height / 2 - 2)
    if (i === 0) drawing.moveTo(x, y); else drawing.lineTo(x, y)
  }
  drawing.strokeStyle = '#d6d6d6'; drawing.lineWidth = 1.3; drawing.stroke()
}

/** Live sound waveform: from the granular player's analyser (GS) or the native engine (Comfort/Sport/Deep). */
export function WaveGraph({ granular, analyser, onCommand }: {
  granular: boolean
  analyser: () => AnalyserNode | null
  onCommand: (name: string, payload?: Record<string, unknown>) => Promise<unknown> | void
}) {
  const canvas = useRef<HTMLCanvasElement>(null)
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
        drawWave(canvas.current, samples)
        frame = window.setTimeout(tick, 50)  // ~20 fps is plenty for a small trace
      }
      tick()
      return () => { disposed = true; window.clearTimeout(frame) }
    }
    void command.current('debugVisible', { value: true })
    const timer = window.setInterval(() => {
      void Promise.resolve(command.current('soundDebug')).then(data => {
        if (!disposed) drawWave(canvas.current, (data as { waveform?: number[] } | undefined)?.waveform ?? [])
      }).catch(() => {})
    }, 100)
    return () => { disposed = true; window.clearInterval(timer); void command.current('debugVisible', { value: false }) }
  }, [granular])
  return <canvas ref={canvas} className="overlay-graph overlay-wave" aria-label="Sound waveform" role="img" />
}

/** What the player is pressing on the controller (not the game's own pedal values). */
export function PedalBars({ throttle, brake }: { throttle: number; brake: number }) {
  const bar = (label: string, value: number, color: string) => <div className="overlay-pedal">
    <span>{label}</span>
    <div className="overlay-pedal-track"><b style={{ width: `${Math.round(Math.max(0, Math.min(1, value)) * 100)}%`, background: color }} /></div>
    <output>{Math.round(Math.max(0, Math.min(1, value)) * 100)}%</output>
  </div>
  return <div className="overlay-pedals" role="group" aria-label="Controller input">
    {bar('THROTTLE', throttle, GREEN)}
    {bar('BRAKE', brake, RED)}
  </div>
}
