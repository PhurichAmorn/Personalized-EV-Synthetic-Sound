import { useEffect, useRef, useState } from 'react'

export type Powertrain = {
  torque: number; shaftPower: number; wheelPower: number; batteryPower: number
  acceleration: number; soc: number; maxTorque: number; maxRegenTorque: number
  maxRegenPower: number; torqueCurve: [number, number][]; mapDescription: string
}
export type SoundDebug = {
  waveform: number[]; duration_ms: number; frequencies: number[]; spectrum_db: number[]
}

function number(value: number, digits = 0) { return Number.isFinite(value) ? value.toFixed(digits) : '—' }
export default function Diagnostics({ powertrain, rpm, maxRpm, running, sweepActive, onSweep }: {
  powertrain: Powertrain | null
  rpm: number; maxRpm: number; running: boolean; sweepActive: boolean; onSweep: () => void
}) {
  const [trail, setTrail] = useState<{ time: number; rpm: number; torque: number }[]>([])
  const previousRunning = useRef(false)

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

  return <div className="space-y-5">
    <section className="panel space-y-4 p-6">
      <div className="flex items-center justify-between"><h2 className="text-xl">Powertrain telemetry</h2><button className="control text-xs" onClick={() => setTrail([])}>Clear traces</button></div>
      <p className="text-xs text-neutral-400">{powertrain?.mapDescription} · limits before traction and battery constraints</p>
      {powertrain && <div className="grid grid-cols-2 gap-3 text-sm md:grid-cols-3"><div>Torque {number(powertrain.torque, 1)} Nm</div><div>Shaft {number(powertrain.shaftPower, 1)} kW</div><div>Wheels {number(powertrain.wheelPower, 1)} kW</div><div>Battery {number(powertrain.batteryPower, 1)} kW</div><div>Acceleration {number(powertrain.acceleration, 2)} m/s²</div><div>SOC {number(powertrain.soc, 1)}%</div></div>}
      <svg className="h-64 w-full rounded-lg bg-[#202020]" viewBox="0 0 600 300" role="img" aria-label="Motor torque versus RPM">
        <line x1="0" x2="600" y1={300 - (0 - bottom) / (top - bottom) * 300} y2={300 - (0 - bottom) / (top - bottom) * 300} stroke="#4e4e4e" />
        <polyline points={drive} fill="none" stroke="#d6d6d6" strokeWidth="2" strokeDasharray="6 5" />
        <polyline points={regen} fill="none" stroke="#848484" strokeWidth="2" strokeDasharray="6 5" />
        <polyline points={recent} fill="none" stroke="#f2f2f2" strokeWidth="2" />
        {powertrain && <circle cx={rpm / Math.max(1, maxRpm) * 600} cy={300 - (powertrain.torque - bottom) / (top - bottom) * 300} r="5" fill={powertrain.torque < 0 ? '#848484' : '#eaeaea'} />}
      </svg>
      <div className="flex flex-wrap gap-5 text-xs text-neutral-400"><span>Motor RPM: {number(rpm)}</span><span>Drive limit</span><span>Regen limit</span><span>Last 30 s</span></div>
      <button className="control" disabled={running} onClick={onSweep}>{sweepActive ? 'Stop sound sweep' : 'Run sound sweep'}</button>
    </section>
  </div>
}
