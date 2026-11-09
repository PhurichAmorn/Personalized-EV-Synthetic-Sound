import { useState } from 'react'
import { InputGraph, LoadGraph, VerticalBars, WaveGraph } from './OverlayGraphs'
import type { State } from './App'

type Props = {
  state: State
  error: string
  onCommand: (name: string, payload?: Record<string, unknown>) => Promise<unknown> | void
  onPersonalize: () => void
  onStartStop: () => void
  analyser: () => AnalyserNode | null
  granular: boolean
  granularMode: 'steady' | 'rise' | 'evolving'
  onGranular: () => void
  onGranularCycle: () => void
  onTheme: (name: string) => void
}

function Metric({ label, value }: { label: string; value: string }) {
  return <div className="beamng-overlay-metric"><span>{label}</span><strong>{value}</strong></div>
}

export default function BeamNGOverlay({ state, error, onCommand, onPersonalize, onStartStop, analyser, granular, granularMode, onGranular, onGranularCycle, onTheme }: Props) {
  const connected = state.sourceMode !== 'BeamNG' || state.beamngConnected
  const throttle = state.sourceMode === 'BeamNG' ? state.beamngThrottle : state.throttleInput
  const brake = state.sourceMode === 'BeamNG' ? state.beamngBrake : state.brakeInput
  const regen = state.sourceMode === 'BeamNG' ? state.beamngRegen : state.charge
  const locked = state.search.active || state.soundSweepActive || !!state.sourceDiscovery?.active
  const cycleLabel = granular ? granularMode : state.soundRecipeSelection[state.soundTheme]
  const [dragError, setDragError] = useState('')
  // Move the window by dragging the header (the JS call is used because the data-tauri-drag-region attribute did not work).
  const startDrag = (event: React.MouseEvent) => {
    if (event.button !== 0 || (event.target as HTMLElement).closest('button, select, input, a')) return
    window.__TAURI__?.window?.getCurrentWindow().startDragging().catch(reason => setDragError(`Cannot move window: ${reason}`))
  }
  const startResize = (event: React.MouseEvent) => {
    event.stopPropagation()
    window.__TAURI__?.window?.getCurrentWindow().startResizeDragging('SouthEast').catch(reason => setDragError(`Cannot resize window: ${reason}`))
  }
  return <main className="beamng-overlay-card">
    <div className="beamng-overlay-grip" aria-hidden="true" />
    <header className="beamng-overlay-header" onMouseDown={startDrag}>
      <div><span className="beamng-overlay-kicker">EV SOUND LAB</span><h1>Drive audio</h1></div>
      <span className={'beamng-overlay-status' + (connected ? ' connected' : '')} role="status">
        <i />{state.sourceMode === 'Simulator' ? 'SIMULATOR' : connected ? 'BEAMNG LINK' : 'DISCONNECTED'}
      </span>
      <button className="beamng-overlay-close" type="button" aria-label="Close overlay" onClick={() => void window.__TAURI__?.window?.getCurrentWindow().close()}>×</button>
    </header>
    <div className="overlay-modes" role="group" aria-label="Sound mode">
      <button type="button" aria-pressed={granular} disabled={locked} onClick={onGranular}>GS</button>
      {state.soundThemes.map(name => <button type="button" key={name} aria-pressed={!granular && name === state.soundTheme} disabled={locked} onClick={() => onTheme(name)}>{name}</button>)}
      <button type="button" className="overlay-modes-next" disabled={locked} title="Next mode / tune" aria-label={`Next mode, currently ${cycleLabel}`}
        onClick={() => granular ? onGranularCycle() : onCommand('recipeCycle', { name: state.soundTheme })}>&#9197; <small>{cycleLabel}</small></button>
    </div>
    <div className="overlay-grid">
      <div>
        <div className="overlay-caption">INPUT</div>
        <div className="overlay-input-row">
          <VerticalBars throttle={state.controllerThrottle} brake={state.controllerBrake} regen={regen} />
          <InputGraph throttle={throttle} brake={brake} />
        </div>
      </div>
      <div>
        <div className="overlay-caption">MOTOR LOAD</div>
        <LoadGraph load={state.motorLoad ?? 0} />
      </div>
    </div>
    <WaveGraph granular={granular} analyser={analyser} onCommand={onCommand} />
    <section className="beamng-overlay-metrics" aria-label="Live vehicle telemetry">
      <Metric label="KM/H" value={connected ? Math.round(state.speed).toString() : '—'} />
      <Metric label="THROTTLE" value={connected ? `${Math.round(throttle * 100)}%` : '—'} />
      <Metric label="BRAKE" value={connected ? `${Math.round(brake * 100)}%` : '—'} />
      <Metric label="REGEN" value={connected ? `${Math.round(regen * 100)}%` : '—'} />
    </section>
    {(error || state.beamngError || dragError) && <p className="beamng-overlay-error" role="alert">{error || state.beamngError || dragError}</p>}
    <footer className="beamng-overlay-actions">
      <button className="control beamng-overlay-start" disabled={state.starting || state.soundSweepActive} onClick={onStartStop}>
        {state.starting ? 'Starting…' : state.running ? 'Stop sound' : 'Start sound'}
      </button>
      <button className="control" disabled={state.soundSweepActive} onClick={onPersonalize}>Personalize sound</button>
    </footer>
    <div className="beamng-overlay-resize" role="separator" aria-label="Resize overlay" onMouseDown={startResize} />
  </main>
}
