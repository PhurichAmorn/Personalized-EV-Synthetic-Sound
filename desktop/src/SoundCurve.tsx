import { useRef, type PointerEvent } from 'react'
import { curveValue, type CurvePoint } from './soundAudition'

export default function SoundCurve({ label, points, position, yLabel, shape = 1, valueStart = 0, valueEnd = 100, axisMin = 0, axisMax = 100, unit = '%', duration, onChange }: { label: string; points: CurvePoint[]; position: number; yLabel: string; shape?: number; valueStart?: number; valueEnd?: number; axisMin?: number; axisMax?: number; unit?: string; duration?: number; onChange: (points: CurvePoint[]) => void }) {
  const active = useRef<number | null>(null)
  const svg = useRef<SVGSVGElement>(null)
  const clamp = (value: number) => Math.max(0, Math.min(1, value))
  const actual = (y: number) => valueStart + (valueEnd - valueStart) * y
  const displayY = (y: number) => 280 - (actual(y) - axisMin) / (axisMax - axisMin) * 256
  const pointer = (event: PointerEvent<SVGElement>) => {
    const bounds = svg.current!.getBoundingClientRect()
    const height = clamp(1 - ((event.clientY - bounds.top) / bounds.height * 320 - 24) / 256)
    const y = valueEnd === valueStart ? points[active.current ?? 0].y : clamp((axisMin + height * (axisMax - axisMin) - valueStart) / (valueEnd - valueStart))
    return { x: clamp((event.clientX - bounds.left) / bounds.width * 320 / 256 - 40 / 256), y }
  }
  const move = (index: number, point: CurvePoint) => {
    const x = index === 0 ? 0 : index === points.length - 1 ? 1 : Math.max(points[index - 1].x + .01, Math.min(points[index + 1].x - .01, point.x))
    onChange(points.map((p, i) => i === index ? { x, y: clamp(point.y) } : p))
  }
  const remove = (index: number) => { if (index > 0 && index < points.length - 1) onChange(points.filter((_, i) => i !== index)) }
  const path = Array.from({ length: 151 }, (_, i) => `${i ? 'L' : 'M'}${40 + i / 150 * 256},${displayY(curveValue(i / 150, points, shape))}`).join(' ')
  return <div className="sound-curve-widget">
    <button type="button" disabled={points.length >= 24} aria-label={`Add point to ${label}`} onClick={() => {
      let gap = 1
      for (let i = 2; i < points.length; i++) if (points[i].x - points[i - 1].x > points[gap].x - points[gap - 1].x) gap = i
      const x = (points[gap - 1].x + points[gap].x) / 2
      onChange([...points.slice(0, gap), { x, y: curveValue(x, points, shape) }, ...points.slice(gap)])
    }}>Add point</button>
    <svg ref={svg} viewBox="0 0 320 320" aria-label={label} role="group" onPointerMove={event => { if (active.current !== null) move(active.current, pointer(event)) }} onPointerUp={() => { active.current = null }} onPointerCancel={() => { active.current = null }} onLostPointerCapture={() => { active.current = null }}>
      <rect x="40" y="24" width="256" height="256" fill="#1e1e1e" stroke="#484848" />
      {[.25, .5, .75].map(n => <g key={n} stroke="#323232" strokeWidth=".7"><line x1={40 + n * 256} x2={40 + n * 256} y1="24" y2="280" /><line x1="40" x2="296" y1={24 + n * 256} y2={24 + n * 256} /></g>)}
      <path d={path} fill="none" stroke="var(--accent)" strokeWidth="2" pointerEvents="none" />
      <line x1={40 + clamp(position) * 256} x2={40 + clamp(position) * 256} y1="24" y2="280" stroke="#fafafa" opacity=".4" pointerEvents="none" />
      {[0, .25, .5, .75, 1].map(n => <text key={n} x="35" y={284 - n * 256} textAnchor="end">{Math.round(axisMin + n * (axisMax - axisMin))}</text>)}
      <text x="40" y="301">{duration ? '0 s' : '0%'}</text><text x="270" y="301">{duration ? `${duration} s` : '100%'}</text><text x="150" y="316" textAnchor="middle">{duration ? 'Preview time' : 'Preview progress'}</text>
      <text x="11" y="151" textAnchor="middle" transform="rotate(-90 11 151)">{yLabel}</text>
      {points.map((point, index) => <circle key={index} cx={40 + point.x * 256} cy={displayY(point.y)} r="6" tabIndex={0} role="slider" aria-label={`${label}, point ${index + 1}, at ${duration ? (point.x * duration).toFixed(1) + ' seconds' : Math.round(point.x * 100) + ' percent preview'}`} aria-valuemin={Math.min(valueStart, valueEnd)} aria-valuemax={Math.max(valueStart, valueEnd)} aria-valuenow={actual(point.y)} aria-valuetext={`${actual(point.y).toFixed(1)} ${unit}`} onPointerDown={event => { if (event.button !== 0) return; event.stopPropagation(); active.current = index; svg.current?.setPointerCapture(event.pointerId) }} onDoubleClick={event => { event.stopPropagation(); remove(index) }} onKeyDown={event => {
        if (['ArrowUp', 'ArrowDown', 'ArrowLeft', 'ArrowRight', 'Delete', 'Backspace'].includes(event.key)) {
          event.preventDefault()
          if (event.key === 'Delete' || event.key === 'Backspace') remove(index)
          else {
            const step = event.shiftKey ? .001 : .01
            move(index, { x: point.x + (event.key === 'ArrowRight' ? step : event.key === 'ArrowLeft' ? -step : 0), y: point.y + (event.key === 'ArrowUp' ? step : event.key === 'ArrowDown' ? -step : 0) })
          }
        }
      }}><title>{`${actual(point.y).toFixed(1)} ${unit}`}</title></circle>)}
    </svg>
  </div>
}
