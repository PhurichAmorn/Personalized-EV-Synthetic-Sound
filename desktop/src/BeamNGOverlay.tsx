import { useEffect, useRef, useState, type ReactNode } from 'react'
import { InputGraph, LoadGraph, SoundGraph, VerticalBars } from './OverlayGraphs'
import type { State } from './App'
import { LanguageSelect, useT } from './i18n'

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
  personalize?: ReactNode  // Personalize page: shown inside the card, below the live graphs
}

export default function BeamNGOverlay({ state, error, onCommand, onPersonalize, onStartStop, analyser, granular, granularMode, onGranular, onGranularCycle, personalize }: Props) {
  const t = useT()
  const connected = state.sourceMode !== 'BeamNG' || state.beamngConnected
  const throttle = state.sourceMode === 'BeamNG' ? state.beamngThrottle : state.throttleInput
  const brake = state.sourceMode === 'BeamNG' ? state.beamngBrake : state.brakeInput
  const regen = state.sourceMode === 'BeamNG' ? state.beamngRegen : state.charge
  const locked = state.search.active || state.soundSweepActive || !!state.sourceDiscovery?.active
  const [dragError, setDragError] = useState('')
  // Sound graphs (wave and spectrogram, both shown). Never shown during an experiment session: seeing the sound could bias what the participant rates.
  const session = state.search.active || !!state.sourceDiscovery?.active
  // Personalize: the window grows to fit the session (no scrolling), and returns to its driving size afterwards.
  const card = useRef<HTMLElement>(null)
  useEffect(() => {
    const win = window.__TAURI__?.window?.getCurrentWindow(), LogicalSize = window.__TAURI__?.dpi?.LogicalSize, element = card.current
    if (!personalize || !win || !LogicalSize || !element) return
    const before = { width: window.innerWidth, height: window.innerHeight }
    const fit = () => { void win.setSize(new LogicalSize(window.innerWidth, Math.min(element.offsetHeight + 24, screen.availHeight - 40))).catch(reason => setDragError(`Cannot resize window: ${reason}`)) }
    const observer = new ResizeObserver(fit)
    observer.observe(element)
    return () => { observer.disconnect(); void win.setSize(new LogicalSize(window.innerWidth, before.height)).catch(() => {}) }
  }, [!!personalize])
  // Move the window by dragging the header (the JS call is used because the data-tauri-drag-region attribute did not work).
  const startDrag = (event: React.MouseEvent) => {
    if (event.button !== 0 || (event.target as HTMLElement).closest('button, select, input, a')) return
    window.__TAURI__?.window?.getCurrentWindow().startDragging().catch(reason => setDragError(`Cannot move window: ${reason}`))
  }
  const startResize = (event: React.MouseEvent) => {
    event.stopPropagation()
    window.__TAURI__?.window?.getCurrentWindow().startResizeDragging('SouthEast').catch(reason => setDragError(`Cannot resize window: ${reason}`))
  }
  return <main ref={card} className={'beamng-overlay-card' + (personalize ? ' personalizing' : '')}>
    <div className="beamng-overlay-grip" aria-hidden="true" onMouseDown={startDrag} />
    <header className="beamng-overlay-header" onMouseDown={startDrag}>
      <div><span className="beamng-overlay-kicker">{t('EV SOUND LAB')}</span><h1>{t(personalize ? 'Personalize sound' : 'Drive audio')}</h1></div>
      <span onMouseDown={event => event.stopPropagation()}><LanguageSelect className="control" /></span>
      <span className={'beamng-overlay-status' + (connected ? ' connected' : '')} role="status">
        <i />{t(state.sourceMode === 'Simulator' ? 'SIMULATOR' : connected ? 'BEAMNG LINK' : 'DISCONNECTED')}
      </span>
      <button className="beamng-overlay-close" type="button" aria-label="Close overlay" onClick={() => void window.__TAURI__?.window?.getCurrentWindow().close()}><svg className="x-icon" viewBox="0 0 24 24" aria-hidden="true"><path d="M4 4L20 20M20 4L4 20" /></svg></button>
    </header>
    {!personalize && <div className="overlay-modes" role="group" aria-label="Sound mode">
      <button type="button" aria-pressed={granular} disabled={locked} onClick={onGranular}>GS</button>
      <button type="button" className="overlay-modes-next" disabled={locked} title="Next motion" aria-label={`Next motion, currently ${granularMode}`}
        onClick={onGranularCycle}>&#9197; <small>{granularMode}</small></button>
    </div>}
    <div className="overlay-grid">
      <div>
        <div className="overlay-caption">{t('INPUT')}</div>
        <div className="overlay-input-row">
          <VerticalBars throttle={state.controllerThrottle} brake={state.controllerBrake} regen={regen} />
          <InputGraph throttle={throttle} brake={brake} />
        </div>
      </div>
      <div>
        <div className="overlay-caption">{t('MOTOR LOAD')}</div>
        <LoadGraph load={state.motorLoad ?? 0} />
      </div>
    </div>
    {!personalize && !session && <div>
      <div className="overlay-caption">{t('SOUND')}</div>
      {(['wave', 'spectrogram'] as const).map(view => <SoundGraph key={view} granular={granular} active={state.running && !state.starting} view={view} analyser={analyser} onCommand={onCommand} />)}
    </div>}
    {personalize && <section className="overlay-personalize" aria-label="Personalize sound">{personalize}</section>}
    {(error || state.beamngError || dragError) && <p className="beamng-overlay-error" role="alert">{error || state.beamngError || dragError}</p>}
    {!personalize && <footer className="beamng-overlay-actions">
      <button className="control beamng-overlay-start" disabled={state.starting || state.soundSweepActive} onClick={onStartStop}>
        <i className={'overlay-led' + (state.starting ? ' starting' : state.running ? ' on' : '')} aria-hidden="true" />
        {t(state.starting ? 'Starting…' : state.running ? 'Stop sound' : 'Start sound')}
      </button>
      <button className="control" disabled={state.soundSweepActive} onClick={onPersonalize}>{t(state.sourceDiscovery?.active ? 'Resume session' : 'Personalize sound')}</button>
    </footer>}
    <div className="beamng-overlay-resize" role="separator" aria-label="Resize overlay" onMouseDown={startResize} />
  </main>
}
