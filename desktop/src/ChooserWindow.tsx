import { LanguageGate, LanguageSelect, useT } from './i18n'

// First window: the language is chosen here too, before the dashboard or the overlay opens (both read the same stored choice).
export default function ChooserWindow() {
  const t = useT()
  const choose = (mode: 'simulator' | 'beamng') => void window.__TAURI__?.core.invoke('start_mode', { mode })
  return <main className="chooser">
    <LanguageGate />
    <small className="chooser-kicker">{t('EV SOUND LAB')}</small>
    <span className="chooser-lang"><LanguageSelect className="control" /></span>
    <h1>{t('What are you driving with?')}</h1>
    <div className="chooser-options">
      <button type="button" className="chooser-option" onClick={() => choose('simulator')} autoFocus>
        <strong>{t('Simulator')}</strong><span>{t('Built-in simulator with the full dashboard. Drive with W/S or a controller.')}</span>
      </button>
      <button type="button" className="chooser-option" onClick={() => choose('beamng')}>
        <strong>BeamNG</strong><span>{t('Small overlay over the game. Telemetry comes from the BeamNG mod.')}</span>
      </button>
    </div>
  </main>
}
