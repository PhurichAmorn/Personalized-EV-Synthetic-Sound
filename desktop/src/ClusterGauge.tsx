type Props = {
  kind: 'power' | 'speed'
  power?: number
  charge?: number
  speed?: number
  maximum?: number
  startupProgress?: number
  startupBlend?: number
}

const top = 40
const bottom = 390
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

export default function ClusterGauge({ kind, power = 0, charge = 0, speed = 0, maximum = 220, startupProgress = 0, startupBlend = 0 }: Props) {
  const powerZero = top + (bottom - top) * .72
  const shownPower = power + (startupProgress - power) * startupBlend
  const shownCharge = charge * (1 - startupBlend)
  const shownSpeed = speed + (maximum * startupProgress - speed) * startupBlend
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
  const fillColor = kind === 'power' ? (shownCharge > 0 ? '#7dc8d8' : '#e3c894') : '#c4af8b'
  const fadeEnd = marker === fillStart ? fillEnd : fillStart

  return <svg viewBox="0 0 220 430" className="cluster-gauge" role="img" aria-label={kind === 'power' ? 'Power and charge gauge' : 'Speed gauge'}>
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
      <text x="170" y={powerZero + 10} fill={shownCharge > 0 ? '#7dc8d8' : '#7fadb9'} fontSize="9">CHARGE</text>
      {[25, 50, 75, 100].map(value => {
        const y = powerZero + value / 100 * (bottom - powerZero)
        const x = position(kind, y) + 10
        return <g key={value}><line x1={x} x2={x + 14} y1={y} y2={y} stroke="#7dc8d8" strokeWidth="1" /><text x={x + 24} y={y + 4} textAnchor="start" fill="#7dc8d8" fontSize="12">{value}</text></g>
      })}
    </>}
    {labels.map(value => {
      const y = labelY(value)
      const x = position(kind, y) + direction * 10
      return <g key={value}><line x1={x} x2={x + direction * 14} y1={y} y2={y} stroke={kind === 'power' ? '#d9ccad' : '#a3adb6'} strokeWidth="1" /><text x={x + direction * 24} y={y + 4} textAnchor={direction === 1 ? 'start' : 'end'} fill={kind === 'power' ? '#d9ccad' : '#a3adb6'} fontSize="12">{value}</text></g>
    })}
    <line x1={position(kind, marker) - 20} x2={position(kind, marker) + 20} y1={marker} y2={marker} stroke="#f4e8d0" strokeWidth="2" />
  </svg>
}
