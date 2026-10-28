const glows = {
  standby: '#78b6e2',
  Sport: '#da645a',
  Comfort: '#64ba8d',
  Deep: '#4a9eff',
}

export default function MountainHorizon({ running, mode }: { running: boolean; mode: string }) {
  const activeGlow = !running ? 'standby' : mode in glows ? mode : 'Deep'
  return <svg viewBox="0 0 760 430" preserveAspectRatio="none" className="mountain-horizon" aria-hidden="true">
    <defs>
      {Object.entries(glows).map(([name, color]) => <radialGradient id={`horizonGlow-${name}`} key={name}><stop stopColor={color} stopOpacity=".16" /><stop offset=".5" stopColor={color} stopOpacity=".06" /><stop offset="1" stopColor={color} stopOpacity="0" /></radialGradient>)}
      <linearGradient id="horizonFade" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stopColor="#080d13" stopOpacity="0" /><stop offset="1" stopColor="#080d13" /></linearGradient>
      <linearGradient id="horizonEdges"><stop stopColor="#080d13" /><stop offset=".16" stopColor="#080d13" stopOpacity="0" /><stop offset=".84" stopColor="#080d13" stopOpacity="0" /><stop offset="1" stopColor="#080d13" /></linearGradient>
    </defs>
    {Object.keys(glows).map(name => <ellipse className="horizon-glow" key={name} cx="380" cy="330" rx="380" ry="120" fill={`url(#horizonGlow-${name})`} opacity={name === activeGlow ? 1 : 0} />)}
    <path d="M0 360 C70 345 90 320 140 340 C210 350 230 300 270 320 C340 355 380 310 425 330 C510 365 555 290 600 315 C670 345 700 350 760 360 L760 430 L0 430Z" fill="#17212c" />
    <path d="M0 380 C80 360 105 335 145 345 C225 370 250 285 290 310 C370 365 410 350 450 335 C520 390 560 290 610 320 C670 350 710 375 760 370 L760 430 L0 430Z" fill="#131d28" />
    <path d="M0 400 C120 380 140 335 200 350 C280 390 320 370 380 360 C440 330 475 345 535 385 C610 370 650 345 760 385 L760 430 L0 430Z" fill="#0e1721" />
    <rect y="365" width="760" height="65" fill="url(#horizonFade)" />
    <rect width="760" height="430" fill="url(#horizonEdges)" />
  </svg>
}
