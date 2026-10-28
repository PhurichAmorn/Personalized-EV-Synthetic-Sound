import { useEffect, useRef, useState } from 'react'
import { spectrumBins } from './signal_bins'

export type Powertrain = {
  torque: number; shaftPower: number; wheelPower: number; batteryPower: number
  acceleration: number; soc: number; maxTorque: number; maxRegenTorque: number
  maxRegenPower: number; torqueCurve: [number, number][]; mapDescription: string
}
export type SoundDebug = {
  waveform: number[]; duration_ms: number; frequencies: number[]; spectrum_db: number[]
}

function number(value: number, digits = 0) { return Number.isFinite(value) ? value.toFixed(digits) : '—' }
function line(values: number[], min: number, max: number): string {
  if (!values.length) return ''
  return values.map((value, index) => `${index / Math.max(1, values.length - 1) * 600},${130 - (value - min) / (max - min) * 130}`).join(' ')
}

export default function Diagnostics({ view, powertrain, soundDebug, rpm, maxRpm, running, sweepActive, onSweep }: {
  view: 'telemetry' | 'sound-signal'
  powertrain: Powertrain | null; soundDebug: SoundDebug | null
  rpm: number; maxRpm: number; running: boolean; sweepActive: boolean; onSweep: () => void
}) {
  const [history, setHistory] = useState<number[][]>([])
  const [trail, setTrail] = useState<{ time: number; rpm: number; torque: number }[]>([])
  const previousRunning = useRef(false)
  const canvas = useRef<HTMLCanvasElement>(null)

  useEffect(() => {
    if (!soundDebug) return
    setHistory(rows => [...rows, spectrumBins(soundDebug.frequencies, soundDebug.spectrum_db)].slice(-100))
  }, [soundDebug])

  useEffect(() => {
    const context = canvas.current?.getContext('2d')
    if (!context) return
    context.fillStyle = '#101a22'
    context.fillRect(0, 0, 600, 130)
    const width = 600 / Math.max(1, history.length)
    history.forEach((bins, column) => bins.forEach((level, row) => {
      const fraction = level / 90
      context.fillStyle = `hsl(${190 - fraction * 140} 75% ${14 + fraction * 55}%)`
      context.fillRect(column * width, 130 - (row + 1) * 130 / 96, Math.ceil(width), 2)
    }))
  }, [history])

  useEffect(() => {
    if (running && !previousRunning.current) setTrail([])
    previousRunning.current = running
    if (!running || !powertrain) return
    const time = Date.now()
    setTrail(points => [...points.filter(point => point.time >= time - 30000),
      { time, rpm, torque: powertrain.torque }].slice(-300))
  }, [powertrain, rpm, running])

  const top = Math.max(1, (powertrain?.maxTorque || 1) * 1.15)
  const bottom = -(powertrain?.maxRegenTorque || 1) * 1.15
  const point = (x: number, y: number) => `${x / Math.max(1, maxRpm) * 600},${300 - (y - bottom) / (top - bottom) * 300}`
  const drive = powertrain?.torqueCurve.map(([x, y]) => point(x, y)).join(' ') || ''
  const regen = powertrain ? Array.from({ length: 101 }, (_, index) => {
    const speed = maxRpm * index / 100
    const omega = speed * 2 * Math.PI / 60
    return point(speed, -Math.min(powertrain.maxRegenTorque, powertrain.maxRegenPower * 1000 / Math.max(omega, .001)))
  }).join(' ') : ''
  const recent = trail.map(sample => point(sample.rpm, sample.torque)).join(' ')
  const samples = soundDebug?.waveform || []
  const range = Math.max(.02, ...samples.map(value => Math.abs(value) * 1.15))
  const spectrum = soundDebug?.spectrum_db || []

  return <div className="space-y-5">
    {view === 'telemetry' && <section className="panel space-y-4 p-6">
      <div className="flex items-center justify-between"><h2 className="text-xl">Powertrain telemetry</h2><button className="control text-xs" onClick={() => setTrail([])}>Clear traces</button></div>
      <p className="text-xs text-slate-400">{powertrain?.mapDescription} · limits before traction and battery constraints</p>
      {powertrain && <div className="grid grid-cols-2 gap-3 text-sm md:grid-cols-3"><div>Torque {number(powertrain.torque, 1)} Nm</div><div>Shaft {number(powertrain.shaftPower, 1)} kW</div><div>Wheels {number(powertrain.wheelPower, 1)} kW</div><div>Battery {number(powertrain.batteryPower, 1)} kW</div><div>Acceleration {number(powertrain.acceleration, 2)} m/s²</div><div>SOC {number(powertrain.soc, 1)}%</div></div>}
      <svg className="h-64 w-full rounded-lg bg-[#101a22]" viewBox="0 0 600 300" role="img" aria-label="Motor torque versus RPM">
        <line x1="0" x2="600" y1={300 - (0 - bottom) / (top - bottom) * 300} y2={300 - (0 - bottom) / (top - bottom) * 300} stroke="#3c5661" />
        <polyline points={drive} fill="none" stroke="#cbb78f" strokeWidth="2" strokeDasharray="6 5" />
        <polyline points={regen} fill="none" stroke="#68c9da" strokeWidth="2" strokeDasharray="6 5" />
        <polyline points={recent} fill="none" stroke="#ece8dc" strokeWidth="2" />
        {powertrain && <circle cx={rpm / Math.max(1, maxRpm) * 600} cy={300 - (powertrain.torque - bottom) / (top - bottom) * 300} r="5" fill={powertrain.torque < 0 ? '#68c9da' : '#f1deba'} />}
      </svg>
      <div className="flex flex-wrap gap-5 text-xs text-slate-400"><span>Motor RPM: {number(rpm)}</span><span>Drive limit</span><span>Regen limit</span><span>Last 30 s</span></div>
      <button className="control" disabled={running} onClick={onSweep}>{sweepActive ? 'Stop sound sweep' : 'Run sound sweep'}</button>
    </section>}
    {view === 'sound-signal' && <section className="panel space-y-4 p-6"><h2 className="text-xl">Sound signal</h2><p className="text-xs text-slate-400">Output estimates, refreshed at 10 Hz while visible</p>
      <div><div className="label mb-2">Waveform · ms</div><svg className="h-32 w-full rounded-lg bg-[#101a22]" viewBox="0 0 600 130" role="img" aria-label="Recent audio waveform"><line x1="0" x2="600" y1="65" y2="65" stroke="#38505a" /><polyline points={line(samples, -range, range)} fill="none" stroke="#72e0bd" strokeWidth="1.5" /></svg></div>
      <div><div className="label mb-2">Spectrum · Hz</div><svg className="h-32 w-full rounded-lg bg-[#101a22]" viewBox="0 0 600 130" role="img" aria-label="Audio frequency spectrum"><polyline points={line(spectrum.map(level => Math.max(-90, Math.min(0, level))), -90, 0)} fill="none" stroke="#e7c884" strokeWidth="1.5" /></svg></div>
      <div><div className="label mb-2">Spectrogram · last 10 s</div><canvas ref={canvas} width={600} height={130} className="h-32 w-full rounded-lg" role="img" aria-label="Recent audio spectrogram" /></div>
    </section>}
  </div>
}
