import { useEffect, useRef, useState, type CSSProperties, type KeyboardEvent as ReactKeyboardEvent, type ReactNode } from 'react'
import ClusterGauge from './ClusterGauge'
import SoundEditor from './SoundEditor'
import type { SourceHandle } from './SteadySource'
import type { GranularMode } from './granularPlayer'
import type { State } from './App'

type Props = {
  state: State
  error: string
  onCommand: (name: string, payload?: Record<string, unknown>) => Promise<unknown> | void
  onPersonalize: () => void
  onTrace: () => void
  onOpenOverlay: () => void
  searchPanel?: ReactNode
  personalizeOpen?: boolean
}

type DisplayMode = 'classic' | 'sport' | 'digital'
// Soft glow colour under the speed reading; the rest of the UI stays black and white.
const glows = { White: '#f2f2f2', Ice: '#75c9e8', Mint: '#74d4b0', Violet: '#b9a0ed', Amber: '#e8bd68', Rose: '#ef8ba5' }
const displays: { id: DisplayMode; name: string; description: string }[] = [
  { id: 'classic', name: 'Classic', description: 'Twin circular gauges' },
  { id: 'sport', name: 'Sport', description: 'Twin vertical meters' },
  { id: 'digital', name: 'Digital', description: 'Speed and power bars' },
]

function DisplayPreview({ mode }: { mode: DisplayMode }) {
  if (mode === 'classic') return <svg className="display-preview-svg" viewBox="0 0 100 72" aria-hidden="true">
    <path d="M 3 36 A 17 17 0 0 1 37 36" fill="none" stroke="var(--accent)" strokeWidth="3" opacity=".2" />
    <path d="M 3 36 A 17 17 0 0 0 8 48" fill="none" stroke="#323232" strokeWidth="2" />
    <path d="M 3 36 A 17 17 0 0 1 15 21" fill="none" stroke="var(--accent)" strokeWidth="3" />
    <path d="M 3 36 A 17 17 0 0 0 4.3 42.5" fill="none" stroke="#848484" strokeWidth="1.5" opacity=".8" />
    <path d="M 20 36 L 16 23 L 20.8 36 Z" fill="var(--accent)" /><circle cx="20" cy="36" r="2.5" fill="#f5f5f5" />
    <path d="M 68 48 A 17 17 0 1 1 92 48" fill="none" stroke="#3c3c3c" strokeWidth="3" />
    <path d="M 68 48 A 17 17 0 0 1 74 24" fill="none" stroke="var(--accent)" strokeWidth="3" />
    <path d="M 80 36 L 74 24 L 80.8 35.5 Z" fill="var(--accent)" /><circle cx="80" cy="36" r="2.5" fill="#f5f5f5" />
    <text x="20" y="60" textAnchor="middle">PWR</text><text x="80" y="60" textAnchor="middle">SPD</text>
  </svg>
  if (mode === 'digital') return <svg className="display-preview-svg" viewBox="0 0 100 72" aria-hidden="true"><text x="50" y="34" textAnchor="middle" className="preview-speed">88</text><text x="30" y="48" textAnchor="middle" className="preview-meter-label">POWER</text><text x="70" y="48" textAnchor="middle" className="preview-meter-label">SPEED</text><rect x="12" y="54" width="36" height="4" rx="2" fill="#3c3c3c" /><rect x="12" y="54" width="23" height="4" rx="2" fill="var(--accent)" /><rect x="52" y="54" width="36" height="4" rx="2" fill="#3c3c3c" /><rect x="52" y="54" width="20" height="4" rx="2" fill="var(--accent)" /></svg>
  return <svg className="display-preview-svg" viewBox="0 0 100 72" aria-hidden="true"><path d="M 19 9 C 35 28 35 46 19 63" fill="none" stroke="var(--accent)" strokeWidth="5" /><path d="M 81 9 C 65 28 65 46 81 63" fill="none" stroke="#707070" strokeWidth="5" /><text x="50" y="43" textAnchor="middle">88</text></svg>
}

function easeInOut(t: number) { return t < .5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2 }
function easeOut(t: number) { return 1 - Math.pow(1 - t, 3) }

function InputMeter({ label, level }: { label: 'BRAKE' | 'THROTTLE'; level: number }) {
  return <div className="input-meter">
    <span>{Math.round(level * 100)}%</span>
    <div className="input-meter-track"><div className={label === 'BRAKE' ? 'brake-fill' : 'throttle-fill'} style={{ height: `${Math.max(0, Math.min(1, level)) * 100}%` }} /></div>
    <small>{label}</small>
  </div>
}

// One bar for power and charge: zero sits 28% from the left, charge fills leftwards, power fills rightwards.
function PowerChargeBar({ power, charge }: { power: number; charge: number }) {
  const clamp = (value: number) => Math.max(0, Math.min(1, value))
  const charging = charge > 0
  return <div className="digital-power" role="img" aria-label={charging ? `Charging ${Math.round(clamp(charge) * 100)} percent` : `Power ${Math.round(clamp(power) * 100)} percent`}>
    <div className="dp-head"><span className={charging ? 'on' : ''}>CHARGE</span><strong>{charging ? `${Math.round(clamp(charge) * 100)}%` : `${Math.round(clamp(power) * 100)}%`}</strong><span className={charging ? '' : 'on'}>POWER</span></div>
    <div className="dp-track">
      <b className="dp-charge" style={{ transform: `scaleX(${clamp(charge)})` }} />
      <b className="dp-power" style={{ transform: `scaleX(${charging ? 0 : clamp(power)})` }} />
      <u className="dp-zero" />
      {[25, 50, 75, 100].map(value => <u key={value} className="dp-tick" style={{ left: `${28 + value * .72}%` }}><em>{value}</em></u>)}
    </div>
  </div>
}

export default function Dashboard({ state, error, onCommand, onPersonalize, onTrace, onOpenOverlay, searchPanel, personalizeOpen = false }: Props) {
  const sound = useRef<SourceHandle>(null)
  const [sourceAudioError, setSourceAudioError] = useState('')
  const [granularMode, setGranularMode] = useState<GranularMode>('evolving')
  const [granularSelected, setGranularSelected] = useState(true)
  // The BeamNG overlay window has no sound player, so it asks this window to change the sound mode.
  const publishMode = useRef(() => {})
  publishMode.current = () => { void window.__TAURI__?.event.emit('sound-mode-status', { granularSelected, granularMode }) }
  useEffect(() => { publishMode.current() }, [granularSelected, granularMode])
  const overlayAction = useRef<(message: { action: string; name?: string }) => void>(() => {})
  overlayAction.current = message => {
    if (message.action === 'gs') { setGranularSelected(true); sound.current?.start(true) }
    else if (message.action === 'gs-cycle') { setGranularMode(mode => mode === 'steady' ? 'rise' : mode === 'rise' ? 'evolving' : 'steady'); setGranularSelected(true); sound.current?.start(true) }
    else if (message.action === 'theme' && message.name) { setGranularSelected(false); sound.current?.stop(); onCommand('theme', { name: message.name }) }
    else if (message.action === 'sync') publishMode.current()
  }
  useEffect(() => {
    let stopListening = () => {}
    let gone = false
    void window.__TAURI__?.event.listen('overlay-mode', event => overlayAction.current(event.payload as unknown as { action: string; name?: string }))
      .then(stop => { if (gone) stop(); else stopListening = stop })
    return () => { gone = true; stopListening() }
  }, [])
  useEffect(() => {
    if (state.running && !state.starting && granularSelected && !state.search.active && !state.soundSweepActive && !state.sourceDiscovery?.active) sound.current?.start(true)
  }, [state.running, state.starting])
  const [expanded, setExpanded] = useState(false)
  const [soundLabOpen, setSoundLabOpen] = useState(false)
  const [showInputs, setShowInputs] = useState(false)
  const [customizerOpen, setCustomizerOpen] = useState(false)
  const customizeButton = useRef<HTMLButtonElement>(null)
  const closeButton = useRef<HTMLButtonElement>(null)
  const [display, setDisplay] = useState<DisplayMode>(() => {
    const saved = localStorage.getItem('ev-sound-display')
    return saved === 'sport' || saved === 'digital' ? saved : 'classic'
  })
  const [glow, setGlow] = useState<keyof typeof glows>(() => {
    const saved = localStorage.getItem('ev-sound-glow')
    return saved && saved in glows ? saved as keyof typeof glows : 'White'
  })
  const setGlowColor = (value: keyof typeof glows) => { setGlow(value); localStorage.setItem('ev-sound-glow', value) }
  const [startupProgress, setStartupProgress] = useState(0)
  const [startupBlend, setStartupBlend] = useState(0)
  useEffect(() => {
    if (!state.starting) {
      setStartupProgress(0)
      setStartupBlend(0)
      return
    }
    let frame = 0
    const start = performance.now()
    const tick = (now: number) => {
      const elapsed = now - start
      setStartupProgress(elapsed < 600 ? easeInOut(elapsed / 600) : elapsed < 700 ? 1 : elapsed < 1350 ? 1 - easeInOut((elapsed - 700) / 650) : 0)
      setStartupBlend(elapsed < 1350 ? 1 : elapsed < 1550 ? 1 - easeOut((elapsed - 1350) / 200) : 0)
      if (elapsed < 1550) frame = requestAnimationFrame(tick)
    }
    frame = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(frame)
  }, [state.starting])
  useEffect(() => {
    if (!customizerOpen) return
    closeButton.current?.focus()
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        setCustomizerOpen(false)
        customizeButton.current?.focus()
      }
    }
    window.addEventListener('keydown', onKeyDown)
    return () => window.removeEventListener('keydown', onKeyDown)
  }, [customizerOpen])
  const connected = !!state.controllerName
  const startVehicleFromButton = async () => {
    if (!state.running) {
      sound.current?.stop()
      await onCommand('sourceAudition', { value: false })
    }
    await onCommand('toggle')
  }
  const status = state.soundSweepActive ? 'AUDIO DEBUG' : state.starting ? 'STARTING' : state.running ? 'READY' : 'STANDBY'
  const setDisplayMode = (value: DisplayMode) => {
    setDisplay(value)
    localStorage.setItem('ev-sound-display', value)
  }
  const trapCustomizerFocus = (event: ReactKeyboardEvent<HTMLElement>) => {
    if (event.key !== 'Tab') return
    const controls = Array.from(event.currentTarget.querySelectorAll<HTMLElement>('button:not(:disabled)'))
    if (!controls.length) return
    if (event.shiftKey && document.activeElement === controls[0]) {
      event.preventDefault()
      controls.at(-1)?.focus()
    } else if (!event.shiftKey && document.activeElement === controls.at(-1)) {
      event.preventDefault()
      controls[0].focus()
    }
  }
  return <div className={'dashboard-screen display-' + display} style={{ '--ambient': glows[glow] } as CSSProperties}>
    <aside className={'dashboard-rail' + (expanded ? ' expanded' : '')} aria-label="Main navigation">
      <button className={"rail-button" + (!soundLabOpen ? " active" : "")} title="Dashboard" aria-label="Dashboard" onClick={() => { setSoundLabOpen(false); if (granularSelected && state.running) sound.current?.start() }}><img src="/icons/layout-dashboard.svg" alt="" /><span>DASHBOARD</span></button>
      <button className="rail-button" title="Sound trace" aria-label="Sound trace" onClick={() => { setSoundLabOpen(false); onTrace() }}><img src="/icons/activity.svg" alt="" /><span>TRACE</span></button>
      <button className={"rail-button" + (soundLabOpen ? " active" : "")} title="Sound Lab" aria-label="Sound Lab" onClick={() => { setSoundLabOpen(true) }}><img src="/icons/sliders.svg" alt="" /><span>SOUND LAB</span></button>
    </aside>
    <div className="dashboard-main">
      <header className="dashboard-header" hidden={soundLabOpen}>
        <button className="header-sidebar" title="Toggle sidebar" aria-label="Toggle sidebar" onClick={() => setExpanded(!expanded)}><img src="/icons/panel-left.svg" alt="" /></button>
        <div className="dashboard-brand"><strong>EV SOUND LAB</strong><small>DRIVE SIMULATOR</small></div>
        <select className="vehicle-selector source-selector" aria-label="Telemetry source" value={state.sourceMode} onChange={event => onCommand('sourceMode', { value: event.target.value })}><option>Simulator</option><option>BeamNG</option></select>
        {state.sourceMode === 'BeamNG' && <span className={'source-link-status' + (state.beamngConnected ? ' connected' : '')}>{state.beamngConnected ? 'BEAMNG LINK' : 'DISCONNECTED'}</span>}
        {state.sourceMode === 'BeamNG' && state.beamngError && <span className="source-link-status" role="alert" title={state.beamngError}>{state.beamngError}</span>}
        <div className="header-spacer" />
        <span className="sound-caption">{state.sourceAudition ? 'GRANULAR' : 'SOUND'}</span>
        <div className="theme-buttons" role="group" aria-label="Sound theme">
          <div className="theme-option"><button className={'theme-button' + (granularSelected ? ' active' : '')} aria-pressed={granularSelected} disabled={state.search.active || state.soundSweepActive} onClick={() => { setGranularSelected(true); sound.current?.start(true) }}>GS</button><button className="theme-recipe" aria-label={`Next granular mode, currently ${granularMode}`} title={`Change mode: ${granularMode}`} disabled={state.search.active || state.soundSweepActive} onClick={() => { setGranularMode(mode => mode === 'steady' ? 'rise' : mode === 'rise' ? 'evolving' : 'steady'); setGranularSelected(true); sound.current?.start(true) }}><span aria-hidden="true">⏭</span><small>{granularMode === 'steady' ? 'Steady' : granularMode === 'rise' ? 'Rise' : 'Evolving'}</small></button></div>
          {state.soundThemes.map(name => <div className="theme-option" key={name}>
            <button className={'theme-button ' + name.toLowerCase() + (name === state.soundTheme && !granularSelected ? ' active' : '')} aria-label={`${name} sound, ${state.soundRecipeSelection[name]}`} aria-pressed={name === state.soundTheme && !granularSelected} disabled={state.search.active || state.soundSweepActive || state.sourceDiscovery?.active} onClick={() => { setGranularSelected(false); sound.current?.stop(); onCommand('theme', { name }) }}>{name}</button>
            <button className="theme-recipe" aria-label={`Change ${name} sound recipe, currently ${state.soundRecipeSelection[name]}`} title={`Change tune: ${state.soundRecipeSelection[name]}`} disabled={state.search.active || state.soundSweepActive || state.sourceAudition} onClick={() => onCommand('recipeCycle', { name })}><span aria-hidden="true">⏭</span><small>{state.soundRecipeSelection[name]}</small></button>
          </div>)}
        </div>
        <select className="vehicle-selector" aria-label="Vehicle" value={state.vehicle} disabled={state.running || state.search.active || state.soundSweepActive} onChange={event => onCommand('vehicle', { name: event.target.value })}>{state.vehicleNames.map(name => <option key={name}>{name}</option>)}</select>
        <button ref={customizeButton} className="display-customize-button" aria-label="Customize dashboard display and ambient color" aria-haspopup="dialog" aria-expanded={customizerOpen} onClick={() => setCustomizerOpen(true)}><span className="customize-light" /><span>DISPLAY</span></button>
        <div className="info-holder"><button className="info-button" aria-label="Vehicle specifications" title="Vehicle specifications">i</button><pre className="specs-popover">{state.specs}</pre></div>
      </header>
      {customizerOpen && <div className="display-customizer-backdrop" onMouseDown={event => { if (event.target === event.currentTarget) { setCustomizerOpen(false); customizeButton.current?.focus() } }}>
        <section className="display-customizer" role="dialog" aria-modal="true" aria-labelledby="display-customizer-title" onKeyDown={trapCustomizerFocus}>
          <header className="customizer-header"><div><h2 id="display-customizer-title">Display</h2><p>Set your instrument style.</p></div><button ref={closeButton} className="customizer-close" onClick={() => { setCustomizerOpen(false); customizeButton.current?.focus() }}>Close</button></header>
          <section className="customizer-section" aria-labelledby="display-mode-title"><h3 id="display-mode-title">Instrument display</h3><div className="display-mode-options" role="group" aria-label="Instrument display style">{displays.map(option => <button key={option.id} className={'display-mode-option' + (display === option.id ? ' selected' : '')} aria-pressed={display === option.id} onClick={() => setDisplayMode(option.id)}><DisplayPreview mode={option.id} /><strong>{option.name}</strong><small>{option.description}</small></button>)}</div></section>
          <section className="customizer-section ambient-section" aria-labelledby="ambient-title"><h3 id="ambient-title">Speed glow</h3><div className="ambient-options" role="group" aria-label="Glow under the speed reading">{Object.entries(glows).map(([name, color]) => <button key={name} className={'ambient-option' + (glow === name ? ' selected' : '')} aria-label={name} aria-pressed={glow === name} onClick={() => setGlowColor(name as keyof typeof glows)}><span style={{ backgroundColor: color }} /></button>)}</div></section>
        </section>
      </div>}
      <section className="dashboard-cluster" hidden={soundLabOpen} aria-label="Instrument cluster">
        {display !== 'digital' && <ClusterGauge kind="power" power={state.power} charge={state.charge} startupProgress={startupProgress} startupBlend={startupBlend} design={display === 'classic' ? 'circle' : undefined} />}
        <div className="cluster-center">
          <div className="speed-reading"><span>{!state.running || state.starting ? '—' : Math.round(state.speed)}</span><small>km/h</small></div>
          {display === 'digital' && <PowerChargeBar power={state.power} charge={state.charge} />}
          {state.hasGears && <div className="gear-badge">{!state.running ? 'P' : state.starting ? '—' : state.gear}</div>}
          <div className={'cluster-status ' + (state.running && !state.starting ? 'ready' : '')}>{status}</div>
        </div>
        {display !== 'digital' && <ClusterGauge kind="speed" speed={state.speed} maximum={state.speedGaugeMaximum} startupProgress={startupProgress} startupBlend={startupBlend} design={display === 'classic' ? 'circle' : undefined} />}
      </section>
      <section className={'dashboard-controls' + (personalizeOpen ? ' personalize-active' : '')} hidden={soundLabOpen} aria-label="Driving controls">
        <div className="input-controls">
          <button className={'controller-status' + (connected ? ' connected' : '')} title={state.controllerError || 'W throttle · S brake · controller triggers'} onClick={() => setShowInputs(!showInputs)}>{connected ? '●  CONTROLLER CONNECTED' : '○  CONTROLLER DISCONNECTED'}</button>
          <div className="input-meters"><InputMeter label="BRAKE" level={state.brakeInput} /><InputMeter label="THROTTLE" level={state.throttleInput} /></div>
          {showInputs && <div className="input-options"><label><input type="checkbox" checked={state.controllerEnabled} onChange={event => onCommand('controllerEnabled', { value: event.target.checked })} /> Controller enabled</label><select aria-label="Controller" onChange={event => onCommand('controller', { id: Number(event.target.value) })}><option value="-1">Automatic</option>{state.availableControllers.map(device => <option key={device.id} value={device.id}>{device.name}</option>)}</select></div>}
        </div>
        <div className={'controls-spacer' + (searchPanel ? ' has-search-panel' : '')}>{searchPanel && <div className="dashboard-search-slot">{searchPanel}</div>}</div>
        <div className="start-controls">{!personalizeOpen && <><button type="button" className="start-button" aria-label={state.running ? 'Stop vehicle' : 'Start vehicle'} disabled={state.starting || state.soundSweepActive} onClick={() => void startVehicleFromButton()}><span className={'start-indicator' + (state.running ? ' on' : '')} /><strong>{state.starting ? 'STARTING' : state.running ? 'STOP' : 'START'}</strong></button><button className="personalize-button" disabled={state.soundSweepActive} onClick={onPersonalize}>Personalize sound</button><button className="control overlay-launch-button" onClick={onOpenOverlay}>Open BeamNG overlay</button></>}</div>
      </section>
      {(error || state.audioError || sourceAudioError) && <div role="alert" className="dashboard-error">{error || state.audioError || sourceAudioError}</div>}
      <SoundEditor onAudioError={setSourceAudioError} personalizeOpen={personalizeOpen} onSourceSelected={() => setGranularSelected(true)} granularMode={granularMode} onModeChange={setGranularMode} ref={sound} active state={state} onCommand={onCommand} embedded={!soundLabOpen} />
    </div>
  </div>
}
