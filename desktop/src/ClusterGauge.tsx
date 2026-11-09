import { memo } from 'react'
type Props = {
  kind: 'power' | 'speed'
  design?: 'circle'
  power?: number
  charge?: number
  speed?: number
  maximum?: number
  startupProgress?: number
  startupBlend?: number
}

const top = 40
const bottom = 390
const circleStart = 135
const circleSweep = 270
const circleRadius = 140

function circlePoint(angle: number, radius: number) {
  const radians = angle * Math.PI / 180
  return [130 + radius * Math.cos(radians), 215 + radius * Math.sin(radians)] as const
}

function circleArc(from: number, to: number, radius = circleRadius, sweep = 1) {
  const [x1, y1] = circlePoint(from, radius)
  const [x2, y2] = circlePoint(to, radius)
  return `M ${x1} ${y1} A ${radius} ${radius} 0 ${Math.abs(to - from) > 180 ? 1 : 0} ${sweep} ${x2} ${y2}`
}

function position(kind: Props['kind'], y: number) {
  const progress = Math.max(0, Math.min(1, (y - top) / (bottom - top)))
  const bend = Math.pow(Math.sin(Math.PI * progress), 1.15) * 100
  return kind === 'power' ? 154 - bend : 66 + bend
}

const bandWidth = { power: 22, speed: 17 }
function bandPath(kind: Props['kind'], start: number, end: number) {
  const half = bandWidth[kind] / 2
  const outer: string[] = []
  const inner: string[] = []
  for (let index = 0; index <= 80; index++) {
    const y = start + (end - start) * index / 80
    const x = position(kind, y)
    outer.push(`${x + half},${y}`)
    inner.push(`${x - half},${y}`)
  }
  return `M ${outer.join(' L ')} L ${inner.reverse().join(' L ')} Z`
}

function ClusterGauge({ kind, power = 0, charge = 0, speed = 0, maximum = 220, startupProgress = 0, startupBlend = 0, design }: Props) {
  const shownSpeed = speed + (maximum * startupProgress - speed) * startupBlend
  const shownPower = power + (startupProgress - power) * startupBlend
  const shownCharge = charge * (1 - startupBlend)
  if (design === 'circle') {
    const isPower = kind === 'power'
    const maxValue = isPower ? 100 : maximum
    const fraction = isPower ? Math.max(0, Math.min(1, shownPower)) : Math.max(0, Math.min(1, shownSpeed / Math.max(1, maximum)))
    const labelValues = isPower ? [0, 25, 50, 75, 100] : (maximum > 220 ? [0, 40, 80, 120, 180, 240, 300] : [0, 20, 60, 100, 140, 180, 220]).filter(value => value <= maximum)
    const ticks = Array.from({ length: Math.floor(maxValue / (isPower ? 5 : 10)) + 1 }, (_, index) => index * (isPower ? 5 : 10))
    const needleAngle = isPower
      ? shownCharge > 0 ? 180 - 45 * Math.min(1, shownCharge) : 180 + 180 * fraction
      : circleStart + circleSweep * fraction
    const needleColor = '#c5cdd1'
    return <svg viewBox="-15 0 290 430" className="cluster-gauge cluster-circle-gauge" role="img" aria-label={isPower ? 'Circular power and regeneration gauge' : 'Circular speed gauge'}>
      {isPower
        ? <><path d={circleArc(180, 360, circleRadius)} className="circle-gauge-track circle-gauge-power-track" />
          {fraction > 0 && <path d={circleArc(180, 180 + 180 * fraction, circleRadius)} className="circle-gauge-active" />}
          <path d={circleArc(180, 135, circleRadius, 0)} className="circle-gauge-regen-track" />
          {shownCharge > 0 && <path d={circleArc(180, 180 - 45 * Math.min(1, shownCharge), circleRadius, 0)} className="circle-gauge-regen-active" />}</>
        : <><path d={circleArc(circleStart, circleStart + circleSweep)} className="circle-gauge-track" />{fraction > 0 && <path d={circleArc(circleStart, circleStart + circleSweep * fraction)} className="circle-gauge-active" />}</>}
      {ticks.map(value => {
        const major = labelValues.includes(value)
        const angle = isPower ? 180 + 180 * value / maxValue : circleStart + circleSweep * value / maxValue
        const [x1, y1] = circlePoint(angle, major ? 125 : 131)
        const [x2, y2] = circlePoint(angle, 137)
        return <line key={value} x1={x1} y1={y1} x2={x2} y2={y2} className={major ? 'circle-gauge-tick major' : 'circle-gauge-tick'} />
      })}
      {isPower && (() => {
        const [x1, y1] = circlePoint(135, 125)
        const [x2, y2] = circlePoint(135, 137)
        return <line x1={x1} y1={y1} x2={x2} y2={y2} className="circle-gauge-tick major" />
      })()}
      {labelValues.map(value => {
        const angle = isPower ? 180 + 180 * value / maxValue : circleStart + circleSweep * value / maxValue
        const [x, y] = circlePoint(angle, 108)
        return <text key={value} x={x} y={y + 4} className="circle-gauge-label">{value}</text>
      })}
      <text x="130" y="55" className="circle-gauge-caption">{isPower ? 'POWER' : 'SPEED'}</text>
      {isPower && <text x="58" y="320" className="circle-gauge-regen-title" textAnchor="start">CHARGE</text>}
      <g className="circle-gauge-needle" transform={`rotate(${needleAngle} 130 215)`}>
        <path d="M 130 211.5 L 267 215 L 130 218.5 Z" fill={needleColor} />
        <path d="M 139 214.4 L 255 215 L 139 215.6 Z" fill="#edf4f5" opacity=".9" />
      </g>
      <circle cx="130" cy="215" r="3.5" className="circle-gauge-pin-core" />
    </svg>
  }
  const powerZero = top + (bottom - top) * .72
  const marker = kind === 'power'
    ? shownCharge > 0 ? powerZero + Math.min(1, shownCharge) * (bottom - powerZero) : powerZero - Math.min(1, shownPower) * (powerZero - top)
    : bottom - Math.min(1, shownSpeed / Math.max(1, maximum)) * (bottom - top)
  const speedLabels = maximum > 220 ? [0, 40, 80, 120, 180, 240, 300] : [0, 20, 60, 100, 140, 180, 220]
  const labels = kind === 'power' ? [0, 25, 50, 75, 100] : speedLabels
  const labelY = (value: number) => kind === 'power'
    ? powerZero - value / 100 * (powerZero - top)
    : bottom - value / maximum * (bottom - top)
  const direction = kind === 'power' ? 1 : -1
  const fillStart = kind === 'power' ? Math.min(marker, powerZero) : marker
  const fillEnd = kind === 'power' ? Math.max(marker, powerZero) : bottom
  const fillColor = kind === 'power' && shownCharge > 0 ? '#79bfd0' : 'var(--accent)'
  const labelColor = '#a3adb6'
  const fadeEnd = marker === fillStart ? fillEnd : fillStart

  return <svg viewBox="0 0 220 430" className={'cluster-gauge ' + (kind === 'power' ? 'cluster-power-gauge' : 'cluster-speed-gauge')} role="img" aria-label={kind === 'power' ? 'Power and charge gauge' : 'Speed gauge'}>
    <defs>
      <clipPath id={`gauge-fill-${kind}`}><rect x="0" y={fillStart} width="220" height={Math.max(0, fillEnd - fillStart)} /></clipPath>
      <linearGradient id={`gauge-color-${kind}`} gradientUnits="userSpaceOnUse" x1="0" y1={marker} x2="0" y2={fadeEnd}><stop stopColor={fillColor} stopOpacity=".9" /><stop offset="1" stopColor={fillColor} stopOpacity=".08" /></linearGradient>
    </defs>
    <text x={kind === 'power' ? 134 : 56} y="18" fill="#9baab4" fontSize="10" letterSpacing="3" textAnchor={kind === 'power' ? 'end' : 'start'}>{kind === 'power' ? 'POWER %' : 'km/h'}</text>
    <path d={bandPath(kind, top, bottom)} fill="#26313c" />
    <path d={bandPath(kind, top, bottom)} fill={`url(#gauge-color-${kind})`} clipPath={`url(#gauge-fill-${kind})`} />
    {kind === 'speed' && Array.from({ length: Math.floor(maximum / 10) + 1 }, (_, index) => index * 10).filter(value => !speedLabels.includes(value)).map(value => {
      const y = labelY(value)
      const x = position(kind, y) - bandWidth.speed / 2 - 1
      return <line key={value} x1={x} x2={x - 7} y1={y} y2={y} stroke="#66727c" strokeWidth="1" opacity=".7" />
    })}
    {kind === 'power' && <>
      <line x1={position(kind, powerZero) - 24} x2={position(kind, powerZero) + 24} y1={powerZero} y2={powerZero} stroke="#c9d3d8" strokeWidth="1" />
      <text x="170" y={powerZero + 10} fill={shownCharge > 0 ? '#79bfd0' : '#7fadb9'} fontSize="9">CHARGE</text>
      {[25, 50, 75, 100].map(value => {
        const y = powerZero + value / 100 * (bottom - powerZero)
        const x = position(kind, y) + 10
        return <g key={value}><line x1={x} x2={x + 14} y1={y} y2={y} stroke="#79bfd0" strokeWidth="1" /><text x={x + 24} y={y + 4} textAnchor="start" fill="#79bfd0" fontSize="12">{value}</text></g>
      })}
    </>}
    {labels.map(value => {
      const y = labelY(value)
      const x = position(kind, y) + direction * 10
      return <g key={value}><line x1={x} x2={x + direction * 14} y1={y} y2={y} stroke={labelColor} strokeWidth="1" /><text x={x + direction * 24} y={y + 4} textAnchor={direction === 1 ? 'start' : 'end'} fill={labelColor} fontSize="12">{value}</text></g>
    })}
    <line x1={position(kind, marker) - 20} x2={position(kind, marker) + 20} y1={marker} y2={marker} stroke="#f4e8d0" strokeWidth="2" />
  </svg>
}

export default memo(ClusterGauge)
