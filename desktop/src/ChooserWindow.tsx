export default function ChooserWindow() {
  const choose = (mode: 'simulator' | 'beamng') => void window.__TAURI__?.core.invoke('start_mode', { mode })
  return <main className="chooser">
    <small className="chooser-kicker">EV SOUND LAB</small>
    <h1>What are you driving with?</h1>
    <div className="chooser-options">
      <button type="button" className="chooser-option" onClick={() => choose('simulator')} autoFocus>
        <strong>Simulator</strong><span>Built-in simulator with the full dashboard. Drive with W/S or a controller.</span>
      </button>
      <button type="button" className="chooser-option" onClick={() => choose('beamng')}>
        <strong>BeamNG</strong><span>Small overlay over the game. Telemetry comes from the BeamNG mod.</span>
      </button>
    </div>
  </main>
}
