import { useEffect, useState, type ReactNode } from 'react'
import ClusterGauge from './ClusterGauge'
import MountainHorizon from './MountainHorizon'
import type { State } from './App'

type Props = {
  state: State
  error: string
  onCommand: (name: string, payload?: Record<string, unknown>) => void
  onPersonalize: () => void
  onTrace: () => void
  searchPanel?: ReactNode
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

export default function Dashboard({ state, error, onCommand, onPersonalize, onTrace, searchPanel }: Props) {
  const [expanded, setExpanded] = useState(false)
  const [showInputs, setShowInputs] = useState(false)
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
  const connected = !!state.controllerName
  const status = state.soundSweepActive ? 'AUDIO DEBUG' : state.starting ? 'STARTING' : state.running ? 'READY' : 'STANDBY'
  return <div className="dashboard-screen">
    <aside className={'dashboard-rail' + (expanded ? ' expanded' : '')} aria-label="Main navigation">
      <button className="rail-button active" title="Dashboard" aria-label="Dashboard"><img src="/icons/layout-dashboard.svg" alt="" /><span>DASHBOARD</span></button>
      <button className="rail-button" title="Sound trace" aria-label="Sound trace" onClick={onTrace}><img src="/icons/activity.svg" alt="" /><span>TRACE</span></button>
    </aside>
    <div className="dashboard-main">
      <header className="dashboard-header">
        <button className="header-sidebar" title="Toggle sidebar" aria-label="Toggle sidebar" onClick={() => setExpanded(!expanded)}><img src="/icons/panel-left.svg" alt="" /></button>
        <div className="dashboard-brand"><strong>EV SOUND LAB</strong><small>DRIVE SIMULATOR</small></div>
        <div className="header-spacer" />
        <span className="sound-caption">SOUND</span>
        <div className="theme-buttons" role="group" aria-label="Sound theme">
          {state.soundThemes.map(name => <button key={name} className={'theme-button ' + name.toLowerCase() + (name === state.soundTheme ? ' active' : '')} aria-label={`${name} sound`} aria-pressed={name === state.soundTheme} disabled={state.search.active || state.soundSweepActive} onClick={() => onCommand('theme', { name })}>{name}</button>)}
        </div>
        <select className="vehicle-selector" aria-label="Vehicle" value={state.vehicle} disabled={state.running || state.search.active || state.soundSweepActive} onChange={event => onCommand('vehicle', { name: event.target.value })}>{state.vehicleNames.map(name => <option key={name}>{name}</option>)}</select>
        <div className="info-holder"><button className="info-button" aria-label="Vehicle specifications" title="Vehicle specifications">i</button><pre className="specs-popover">{state.specs}</pre></div>
      </header>
      <section className="dashboard-cluster" aria-label="Instrument cluster">
        <ClusterGauge kind="power" power={state.power} charge={state.charge} startupProgress={startupProgress} startupBlend={startupBlend} />
        <div className="cluster-center">
          <MountainHorizon running={state.running} mode={state.soundTheme} />
          <div className="speed-reading"><span>{!state.running || state.starting ? '—' : Math.round(state.speed)}</span><small>km/h</small></div>
          {state.hasGears && <div className="gear-badge">{!state.running ? 'P' : state.starting ? '—' : state.gear}</div>}
          <div className={'cluster-status ' + (state.running && !state.starting ? 'ready' : '')}>{status}</div>
        </div>
        <ClusterGauge kind="speed" speed={state.speed} maximum={state.speedGaugeMaximum} startupProgress={startupProgress} startupBlend={startupBlend} />
      </section>
      <section className="dashboard-controls" aria-label="Driving controls">
        <div className="input-controls">
          <button className={'controller-status' + (connected ? ' connected' : '')} title={state.controllerError || 'W throttle · S brake · controller triggers'} onClick={() => setShowInputs(!showInputs)}>{connected ? '●  CONTROLLER CONNECTED' : '○  CONTROLLER DISCONNECTED'}</button>
          <div className="input-meters"><InputMeter label="BRAKE" level={state.brakeInput} /><InputMeter label="THROTTLE" level={state.throttleInput} /></div>
          {showInputs && <div className="input-options"><label><input type="checkbox" checked={state.controllerEnabled} onChange={event => onCommand('controllerEnabled', { value: event.target.checked })} /> Controller enabled</label><select aria-label="Controller" onChange={event => onCommand('controller', { id: Number(event.target.value) })}><option value="-1">Automatic</option>{state.availableControllers.map(device => <option key={device.id} value={device.id}>{device.name}</option>)}</select></div>}
        </div>
        <div className={'controls-spacer' + (searchPanel ? ' has-search-panel' : '')}>{searchPanel && <div className="dashboard-search-slot">{searchPanel}</div>}</div>
        <div className="start-controls"><button className="start-button" aria-label={state.running ? 'Stop vehicle' : 'Start vehicle'} disabled={state.soundSweepActive} onClick={() => onCommand('toggle')}><span className={'start-indicator' + (state.running && !state.starting ? ' on' : '')} /><strong>{state.running ? 'STOP' : 'START'}</strong></button>{!state.search.active && <button className="personalize-button" disabled={state.running} onClick={onPersonalize}>Personalize sound</button>}</div>
      </section>
      {(error || state.audioError) && <div role="alert" className="dashboard-error">{error || state.audioError}</div>}
    </div>
  </div>
}
