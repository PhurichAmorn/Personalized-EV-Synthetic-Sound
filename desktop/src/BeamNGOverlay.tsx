import { useState } from 'react'
import type { State } from './App'

type Props = {
  state: State
  error: string
  onCommand: (name: string, payload?: Record<string, unknown>) => Promise<unknown> | void
  onPersonalize: () => void
}

function Metric({ label, value }: { label: string; value: string }) {
  return <div className="beamng-overlay-metric"><span>{label}</span><strong>{value}</strong></div>
}

export default function BeamNGOverlay({ state, error, onCommand, onPersonalize }: Props) {
  const connected = state.sourceMode !== 'BeamNG' || state.beamngConnected
  const throttle = state.sourceMode === 'BeamNG' ? state.beamngThrottle : state.throttleInput
  const brake = state.sourceMode === 'BeamNG' ? state.beamngBrake : state.brakeInput
  const regen = state.sourceMode === 'BeamNG' ? state.beamngRegen : state.charge
  const [dragError, setDragError] = useState('')
  // Drag from any empty part of the card (not from buttons, the dropdown or the close button).
  const startDrag = (event: React.MouseEvent) => {
    if (event.button !== 0 || (event.target as HTMLElement).closest('button, select, input, a')) return
    window.__TAURI__?.window?.getCurrentWindow().startDragging().catch(reason => setDragError(`Cannot move window: ${reason}`))
  }
  const startResize = (event: React.MouseEvent) => {
    event.stopPropagation()
    window.__TAURI__?.window?.getCurrentWindow().startResizeDragging('SouthEast').catch(reason => setDragError(`Cannot resize window: ${reason}`))
  }
  return <main className="beamng-overlay-card" onMouseDown={startDrag}>
    <div className="beamng-overlay-grip" aria-hidden="true" />
    <header className="beamng-overlay-header" data-tauri-drag-region>
      <div data-tauri-drag-region><span className="beamng-overlay-kicker" data-tauri-drag-region>EV SOUND LAB</span><h1 data-tauri-drag-region>Drive audio</h1></div>
      <span className={'beamng-overlay-status' + (connected ? ' connected' : '')} role="status">
        <i />{state.sourceMode === 'Simulator' ? 'SIMULATOR' : connected ? 'BEAMNG LINK' : 'DISCONNECTED'}
      </span>
      <button className="beamng-overlay-close" type="button" aria-label="Close overlay" onClick={() => void window.__TAURI__?.window?.getCurrentWindow().close()}>×</button>
    </header>
    <label className="beamng-overlay-source">Input source
      <select value={state.sourceMode} onChange={event => onCommand('sourceMode', { value: event.target.value })}>
        <option>Simulator</option><option>BeamNG</option>
      </select>
    </label>
    <section className="beamng-overlay-metrics" aria-label="Live vehicle telemetry">
      <Metric label="SPEED · KM/H" value={connected ? Math.round(state.speed).toString() : '—'} />
      <Metric label="THROTTLE" value={connected ? `${Math.round(throttle * 100)}%` : '—'} />
      <Metric label="BRAKE" value={connected ? `${Math.round(brake * 100)}%` : '—'} />
      <Metric label="REGEN" value={connected ? `${Math.round(regen * 100)}%` : '—'} />
    </section>
    {(error || state.beamngError || dragError) && <p className="beamng-overlay-error" role="alert">{error || state.beamngError || dragError}</p>}
    <footer className="beamng-overlay-actions">
      <button className="control beamng-overlay-start" disabled={state.starting || state.soundSweepActive} onClick={() => onCommand('toggle')}>
        {state.starting ? 'Starting…' : state.running ? 'Stop sound' : 'Start sound'}
      </button>
      <button className="control" disabled={state.soundSweepActive} onClick={onPersonalize}>Personalize sound</button>
    </footer>
    <div className="beamng-overlay-resize" role="separator" aria-label="Resize overlay" onMouseDown={startResize} />
    <p className="beamng-overlay-hint">Drag any empty area of this overlay to move it; × closes it. BeamNG remains in control of the car.</p>
  </main>
}
