import { useEffect, useRef, useState, type RefObject } from 'react'

export default function SoundWaveform({ analyser, active }: { analyser: RefObject<AnalyserNode | null>; active: boolean }) {
  const canvas = useRef<HTMLCanvasElement>(null)
  const [mode, setMode] = useState<'waveform' | 'spectrum'>('spectrum')
  const [hold, setHold] = useState(false)
  const held = useRef(hold)
  const live = useRef(active)
  held.current = hold; live.current = active
  useEffect(() => {
    const element = canvas.current
    if (!element) return
    const drawing = element.getContext('2d')
    if (!drawing) return
    const samples = new Float32Array(2048), frequencies = new Float32Array(1024)
    frequencies.fill(-100)
    let frame = 0, width = 0, height = 0
    const observer = new ResizeObserver(entries => {
      const bounds = entries[0].contentRect
      width = bounds.width; height = bounds.height
      const ratio = window.devicePixelRatio || 1
      element.width = Math.round(width * ratio); element.height = Math.round(height * ratio)
      drawing.setTransform(ratio, 0, 0, ratio, 0, 0)
    })
    observer.observe(element)
    const draw = () => {
      if (held.current) { frame = requestAnimationFrame(draw); return }
      drawing.clearRect(0, 0, width, height)
      const left = 38, right = Math.max(left + 1, width - 12), top = 14, bottom = height - 25
      drawing.strokeStyle = '#263842'; drawing.lineWidth = 1
      drawing.beginPath(); drawing.moveTo(left, top); drawing.lineTo(left, bottom); drawing.lineTo(right, bottom); drawing.stroke()
      drawing.font = '10px Arial'; drawing.fillStyle = '#91a5ad'
      if (analyser.current && live.current) {
        analyser.current.getFloatTimeDomainData(samples)
        analyser.current.getFloatFrequencyData(frequencies)
      } else { samples.fill(0); frequencies.fill(-100) }
      const color = getComputedStyle(element).getPropertyValue('--accent').trim() || '#75c9e8'
      drawing.strokeStyle = color; drawing.lineWidth = 1.5; drawing.beginPath()
      if (mode === 'waveform') {
        // Trigger on a rising zero crossing so successive cycles do not drift sideways.
        let trigger = 0
        for (let i = 1; i < 1024; i++) if (samples[i - 1] <= 0 && samples[i] > 0) { trigger = i; break }
        for (let i = 0; i < 1024; i++) {
          const x = left + i / 1023 * (right - left), y = (top + bottom) / 2 - samples[trigger + i] * (bottom - top) * .45
          if (i === 0) drawing.moveTo(x, y); else drawing.lineTo(x, y)
        }
        drawing.stroke()
        drawing.fillText('+1', 12, top + 8); drawing.fillText('−1', 12, bottom)
        const rate = analyser.current?.context.sampleRate || 48000
        drawing.fillText('0 ms', left, height - 7); drawing.fillText(`${(1024 / rate * 1000).toFixed(1)} ms`, right - 48, height - 7)
      } else {
        const nyquist = (analyser.current?.context.sampleRate || 48000) / 2
        const bins = Math.min(frequencies.length - 1, Math.floor(4000 / nyquist * frequencies.length))
        for (let i = 0; i <= bins; i++) {
          const x = left + i / Math.max(1, bins) * (right - left)
          const db = Number.isFinite(frequencies[i]) ? frequencies[i] : -100
          const y = bottom - Math.max(0, Math.min(1, (db + 100) / 100)) * (bottom - top)
          if (i === 0) drawing.moveTo(x, y); else drawing.lineTo(x, y)
        }
        drawing.stroke()
        drawing.fillText('0 dB', 2, top + 8); drawing.fillText('−100', 2, bottom)
        for (const hz of [0, 1000, 2000, 4000]) drawing.fillText(hz ? `${hz / 1000}k Hz` : '0 Hz', left + hz / 4000 * (right - left) - (hz === 4000 ? 30 : 0), height - 7)
      }
      frame = requestAnimationFrame(draw)
    }
    frame = requestAnimationFrame(draw)
    return () => { cancelAnimationFrame(frame); observer.disconnect() }
  }, [analyser, mode])
  return <div className="sound-signal-view"><div className="sound-signal-controls">
    <button type="button" aria-pressed={mode === 'spectrum'} onClick={() => { setHold(false); setMode('spectrum') }}>Spectrum</button>
    <button type="button" aria-pressed={mode === 'waveform'} onClick={() => { setHold(false); setMode('waveform') }}>Waveform</button>
    <button type="button" aria-pressed={hold} onClick={() => setHold(value => !value)}>{hold ? 'Resume graph' : 'Hold graph'}</button>
  </div><canvas ref={canvas} className="sound-waveform" role="img" aria-label={`${hold ? 'Frozen' : active ? 'Live' : 'Idle'} ${mode === 'spectrum' ? 'frequency spectrum, 0 to 4000 hertz' : 'waveform aligned to a rising zero crossing'}`} /></div>
}
