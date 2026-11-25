import { useEffect, useRef, useState, type CSSProperties, type KeyboardEvent as ReactKeyboardEvent, type ReactNode } from 'react'
import ClusterGauge from './ClusterGauge'
import SoundEditor, { useCarSound } from './SoundEditor'
import SoundSignal from './SoundSignal'
import type { SoundDebug } from './Diagnostics'
import NavRail from './NavRail'
import type { State } from './App'
import { playWelcome } from './welcomeSound'
import { LanguageSelect, useT } from './i18n'
import { Brand } from './PageShell'

type Props = {
  state: State
  error: string
  onCommand: (name: string, payload?: Record<string, unknown>) => Promise<unknown> | void
  onPersonalize: () => void
  onTrace: () => void
  searchPanel?: ReactNode
  personalizeOpen?: boolean
  initialSoundLab?: boolean
}

type DisplayMode = 'classic' | 'sport' | 'digital'
const displays: { id: DisplayMode; name: string }[] = [
  { id: 'classic', name: 'Classic' },
  { id: 'sport', name: 'Sport' },
  { id: 'digital', name: 'Digital' },
]

/** Preview of an instrument display: the real cluster components with demo values, scaled down (so it always matches). */
function DisplayPreview({ mode }: { mode: DisplayMode }) {
  const design = mode === 'classic' ? 'circle' : undefined
  return <div className="display-preview" aria-hidden="true"><div className="display-preview-scene"><div className={'dashboard-cluster display-' + mode}>
    {mode !== 'digital' && <ClusterGauge kind="power" power={.55} charge={0} design={design} />}
    <div className="cluster-center"><div className="speed-reading"><span>88</span><small>km/h</small></div>{mode === 'digital' && <PowerChargeBar power={.55} charge={0} />}</div>
    {mode !== 'digital' && <ClusterGauge kind="speed" speed={88} maximum={220} design={design} />}
  </div></div></div>
}

function easeInOut(t: number) { return t < .5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2 }
function easeOut(t: number) { return 1 - Math.pow(1 - t, 3) }

function InputMeter({ label, level }: { label: 'BRAKE' | 'THROTTLE'; level: number }) {
  const t = useT()
  return <div className="input-meter">
    <span>{Math.round(level * 100)}%</span>
    <div className="input-meter-track"><div className={label === 'BRAKE' ? 'brake-fill' : 'throttle-fill'} style={{ height: `${Math.max(0, Math.min(1, level)) * 100}%` }} /></div>
    <small>{t(label)}</small>
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

export default function Dashboard({ state, error, onCommand, onPersonalize, onTrace, searchPanel, personalizeOpen = false, initialSoundLab = false }: Props) {
  const [sourceAudioError, setSourceAudioError] = useState('')
  const car = useCarSound(state, onCommand, personalizeOpen)
  const t = useT()
  const [expanded, setExpanded] = useState(false)
  const [soundLabOpen, setSoundLabOpen] = useState(initialSoundLab)
  const [showInputs, setShowInputs] = useState(false)
  const [customizerOpen, setCustomizerOpen] = useState(false)
  // Sound signal panel: opened from the header (SIGNAL); polls the backend synth only while open.
  const [signalOpen, setSignalOpen] = useState(false)
  const [soundDebug, setSoundDebug] = useState<SoundDebug | null>(null)
  useEffect(() => {
    if (!signalOpen) return
    void onCommand('debugVisible', { value: true })
    const timer = window.setInterval(() => { void Promise.resolve(onCommand('soundDebug')).then(data => { if (data) setSoundDebug(data as SoundDebug) }).catch(() => {}) }, 100)
    return () => { window.clearInterval(timer); setSoundDebug(null); void onCommand('debugVisible', { value: false }) }
  }, [signalOpen])
  const customizeButton = useRef<HTMLButtonElement>(null)
  const closeButton = useRef<HTMLButtonElement>(null)
  const [display, setDisplay] = useState<DisplayMode>(() => {
    const saved = localStorage.getItem('ev-sound-display')
    return saved === 'sport' || saved === 'digital' ? saved : 'classic'
  })
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
    if (!state.running) { car.stop(); playWelcome() }  // welcome choir on the click itself, not after the backend answers
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
  return <div className="dashboard-screen" style={{ '--ambient': '#f2f2f2' } as CSSProperties}>
    <NavRail active={soundLabOpen ? 'soundlab' : 'dashboard'} expanded={expanded} onSelect={target => {
      if (target === 'trace') { setSoundLabOpen(false); onTrace(); return }
      setSoundLabOpen(target === 'soundlab')
      if (target === 'dashboard') car.resume()
    }} />
    <div className={'dashboard-main'}>
      {/* Header and cluster unmount while Sound Lab is open, so backend state updates do not re-render hidden gauges. */}
      {!soundLabOpen && <header className="dashboard-header">
        <button className="header-sidebar" title={t('Toggle sidebar')} aria-label={t('Toggle sidebar')} onClick={() => setExpanded(!expanded)}><img src="/icons/panel-left.svg" alt="" /></button>
        <Brand sub="DRIVE SIMULATOR" />
        <div className="header-spacer" />
        <span className="sound-caption">{state.sourceAudition ? 'GRANULAR' : t('SOUND')}</span>
        <div className="theme-buttons" role="group" aria-label="Sound motion">
          {(['rise', 'evolving'] as const).map(mode => <div className="theme-option" key={mode}><button className={'theme-button' + (car.gs && car.mode === mode ? ' active' : '')} aria-pressed={car.gs && car.mode === mode} disabled={state.search.active || state.soundSweepActive || !!state.sourceDiscovery?.active} onClick={() => car.select(mode)}>{t(mode === 'rise' ? 'Rising' : 'Evolving')}</button></div>)}
        </div>
        {!!state.mySounds?.length && <select className="vehicle-selector" aria-label="GS sound: final pick of a session" title="GS sound" value={state.mySound?.session ?? ''} disabled={state.search.active || state.soundSweepActive || !!state.sourceDiscovery?.active} onChange={event => onCommand('mySound', { id: event.target.value })}><option value="">Standard sound</option>{state.mySounds.map(s => <option key={s.session} value={s.session}>{s.created.slice(5, 16).replace('T', ' ')} · {s.label || 'sound'}</option>)}</select>}
        <select className="vehicle-selector" aria-label="Vehicle" value={state.vehicle} disabled={state.running || state.search.active || state.soundSweepActive || !!state.sourceDiscovery?.active} onChange={event => onCommand('vehicle', { name: event.target.value })}>{state.vehicleNames.map(name => <option key={name}>{name}</option>)}</select>
        <button ref={customizeButton} className="display-customize-button" aria-label={t('Customize dashboard display')} aria-haspopup="dialog" aria-expanded={customizerOpen} onClick={() => setCustomizerOpen(true)}><span className="customize-light" /><span>{t('DISPLAY')}</span></button>
        <button className={'display-customize-button' + (signalOpen ? ' active' : '')} aria-pressed={signalOpen} aria-label={t('Show or hide the sound signal panel')} onClick={() => setSignalOpen(open => !open)}><span className="customize-light" /><span>{t('SIGNAL')}</span></button>
        <div className="info-holder">
          <button className="info-button" aria-label="Vehicle specifications" title="Vehicle specifications">i</button>
          <pre className="specs-popover">
            {(() => {
              const text = state.specs || ''
              const match = text.match(/(Simulat(?:or|ed) values? are approximate\.?)$/i)
              if (match && match.index !== undefined) {
                return (
                  <>
                    {text.slice(0, match.index)}
                    <span className="specs-disclaimer">{match[1]}</span>
                  </>
                )
              }
              return text
            })()}
          </pre>
        </div>
        <LanguageSelect />
      </header>}
      {customizerOpen && <div className="display-customizer-backdrop" onMouseDown={event => { if (event.target === event.currentTarget) { setCustomizerOpen(false); customizeButton.current?.focus() } }}>
        <section className="display-customizer" role="dialog" aria-modal="true" aria-labelledby="display-customizer-title" onKeyDown={trapCustomizerFocus}>
          <header className="customizer-header"><div><h2 id="display-customizer-title">{t('Display')}</h2><p>{t('Set your instrument style.')}</p></div><button ref={closeButton} className="customizer-close" onClick={() => { setCustomizerOpen(false); customizeButton.current?.focus() }}>{t('Close')}</button></header>
          <section className="customizer-section" aria-labelledby="display-mode-title"><h3 id="display-mode-title">{t('Instrument display')}</h3><div className="display-mode-options" role="group" aria-label="Instrument display style">{displays.map(option => <button key={option.id} className={'display-mode-option' + (display === option.id ? ' selected' : '')} aria-pressed={display === option.id} onClick={() => setDisplayMode(option.id)}><DisplayPreview mode={option.id} /><strong>{t(option.name)}</strong></button>)}</div></section>
        </section>
      </div>}
      {!soundLabOpen && <section className={'dashboard-cluster display-' + display} aria-label="Instrument cluster">  {/* mode class on the cluster, not the screen: the previews inside the screen keep their own */}
        {display !== 'digital' && <ClusterGauge kind="power" power={state.power} charge={state.charge} startupProgress={startupProgress} startupBlend={startupBlend} design={display === 'classic' ? 'circle' : undefined} />}
        <div className="cluster-center">
          <div className="speed-reading"><span>{!state.running || state.starting ? '—' : Math.round(state.speed)}</span><small>km/h</small></div>
          {display === 'digital' && <PowerChargeBar power={state.power} charge={state.charge} />}
          {state.hasGears && <div className="gear-badge">{!state.running ? 'P' : state.starting ? '—' : state.gear}</div>}
          <div className={'cluster-status ' + (state.running && !state.starting ? 'ready' : '')}>{status}</div>
        </div>
        {display !== 'digital' && <ClusterGauge kind="speed" speed={state.speed} maximum={state.speedGaugeMaximum} startupProgress={startupProgress} startupBlend={startupBlend} design={display === 'classic' ? 'circle' : undefined} />}
      </section>}
      <section className={'dashboard-controls' + (personalizeOpen ? ' personalize-active' : '')} hidden={soundLabOpen} aria-label="Driving controls">
        <div className="input-controls">
          <button className={'controller-status' + (connected ? ' connected' : '')} title={state.controllerError || t('W throttle · S brake · controller triggers')} onClick={() => setShowInputs(!showInputs)}>{t(connected ? '●  CONTROLLER CONNECTED' : '○  CONTROLLER DISCONNECTED')}</button>
          <div className="input-meters"><InputMeter label="BRAKE" level={state.brakeInput} /><InputMeter label="THROTTLE" level={state.throttleInput} /></div>
          {showInputs && <div className="input-options"><label><input type="checkbox" checked={state.controllerEnabled} onChange={event => onCommand('controllerEnabled', { value: event.target.checked })} /> {t('Controller enabled')}</label><select aria-label="Controller" onChange={event => onCommand('controller', { id: Number(event.target.value) })}><option value="-1">{t('Automatic')}</option>{state.availableControllers.map(device => <option key={device.id} value={device.id}>{device.name}</option>)}</select></div>}
        </div>
        <div className={'controls-spacer' + (searchPanel ? ' has-search-panel' : '')}>{searchPanel && <div className="dashboard-search-slot">{searchPanel}</div>}</div>
        <div className="start-controls">{!personalizeOpen && <><button type="button" className="start-button" aria-label={t(state.running ? 'Stop vehicle' : 'Start vehicle')} disabled={state.starting || state.soundSweepActive} onClick={() => void startVehicleFromButton()}><span className={'start-indicator' + (state.running ? ' on' : '')} /><strong>{t(state.running ? 'STOP' : 'START')}</strong></button><button className="personalize-button" disabled={state.soundSweepActive} onClick={onPersonalize}>{t(state.sourceDiscovery?.active ? 'Resume session' : 'Personalize sound')}</button></>}</div>
      </section>
      {(error || state.audioError || sourceAudioError) && <div role="alert" className="dashboard-error">{error || state.audioError || sourceAudioError}</div>}
      <SoundEditor onAudioError={setSourceAudioError} {...car.editor} active state={state} onCommand={onCommand} embedded={!soundLabOpen} />
    </div>
    {signalOpen && <SoundSignal analyser={car.analyser} soundDebug={soundDebug} onClose={() => setSignalOpen(false)} />}
  </div>
}
