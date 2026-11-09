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
  return <main className="beamng-overlay-card">
    <header className="beamng-overlay-header">
      <div><span className="beamng-overlay-kicker">EV SOUND LAB</span><h1>Drive audio</h1></div>
      <span className={'beamng-overlay-status' + (connected ? ' connected' : '')} role="status">
        <i />{state.sourceMode === 'Simulator' ? 'SIMULATOR' : connected ? 'BEAMNG LINK' : 'DISCONNECTED'}
      </span>
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
    {(error || state.beamngError) && <p className="beamng-overlay-error" role="alert">{error || state.beamngError}</p>}
    <footer className="beamng-overlay-actions">
      <button className="control beamng-overlay-start" disabled={state.starting || state.soundSweepActive} onClick={() => onCommand('toggle')}>
        {state.starting ? 'Starting…' : state.running ? 'Stop sound' : 'Start sound'}
      </button>
      <button className="control" disabled={state.soundSweepActive} onClick={onPersonalize}>Personalize sound</button>
    </footer>
    <p className="beamng-overlay-hint">Drag this window by its title area. BeamNG remains in control of the car.</p>
  </main>
}
