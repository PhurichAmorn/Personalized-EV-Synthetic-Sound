import { useEffect, useRef, useState, useImperativeHandle, type Ref } from 'react'
import { createPortal } from 'react-dom'
import type { State } from './App'
import SourceSearch from './SourceSearch'
import SteadySource, { type SourceHandle } from './SteadySource'
import type { GranularMode } from './granularPlayer'

export default function SoundEditor({ active, state, onCommand, embedded = false, ref, granularMode, onModeChange, onSourceSelected, onAudioError, personalizeOpen = false }: { onAudioError?: (message: string) => void; personalizeOpen?: boolean; onSourceSelected?: () => void; granularMode: GranularMode; onModeChange: (mode: GranularMode) => void; ref?: Ref<SourceHandle>; embedded?: boolean; active: boolean; state: State; onCommand: (name: string, payload?: Record<string, unknown>) => Promise<unknown> | void }) {
  const source = useRef<SourceHandle>(null)
  const [discoveryContainer] = useState(() => document.createElement('div'))
  useEffect(() => {
    const host = personalizeOpen ? document.getElementById('source-discovery-slot') : null
    if (host) host.appendChild(discoveryContainer)
    return () => discoveryContainer.remove()
  }, [personalizeOpen, state.search.active, state.sourceDiscovery?.active, discoveryContainer])
  const [sourcePlaying, setSourcePlaying] = useState(false)
  const command = useRef(onCommand)
  command.current = onCommand
  const startSound = (refresh = false) => {
    if (source.current) { command.current('sourceAudition', { value: true }); source.current.start(refresh) }
  }
  useImperativeHandle(ref, () => ({ start: startSound, analyser: () => source.current?.analyser() ?? null, auditionContext: () => source.current?.auditionContext() ?? {}, audition: (urls, input, label) => source.current?.audition(urls, input, label) ?? Promise.resolve(false), stop: () => { source.current?.stop(); setSourcePlaying(false); command.current('sourceAudition', { value: false }) } }))
  const discoveryWorkspace = embedded && !state.search.active && !state.soundSweepActive && !!state.sourceDiscovery?.active
  useEffect(() => { void command.current('sourceAudition', { value: sourcePlaying || discoveryWorkspace }) }, [sourcePlaying, discoveryWorkspace])
  useEffect(() => () => { void command.current('sourceAudition', { value: false }) }, [])
  const backendReady = typeof state.sourceAudition === 'boolean' && typeof state.motorLoad === 'number'
  return <section className={"sound-editor" + (embedded ? " sound-editor-embedded" : "")} hidden={!active || embedded} aria-labelledby="sound-editor-title">
    <header className="sound-editor-header" hidden={embedded}>
      <div><small className="sound-workspace-brand">EV SOUND LAB</small><h2 id="sound-editor-title">Sound design dashboard</h2></div>
    </header>
    <div className="sound-mapping-status" hidden={embedded}><span>Live simulator response · fixed mapping</span></div>
    {active && <>
      <div className="sound-editor-transport" hidden={embedded}>
        <button type="button" disabled={state.search.active || state.soundSweepActive} onClick={() => { if (!state.running) startSound(); onCommand('toggle') }}>{state.running ? 'Stop vehicle' : 'Start vehicle'}</button>
        <span>{state.starting ? 'Starting…' : state.running ? 'Ready · W throttle / S brake · controller triggers' : 'Vehicle stopped'}</span>
      </div>
      {backendReady && !state.search.active && !state.soundSweepActive && createPortal(<SourceSearch hidden={!personalizeOpen} discovery={state.sourceDiscovery} onCommand={onCommand} onContext={() => source.current?.auditionContext() ?? { input: 'live', style: granularMode }} mode={granularMode} onModeChange={onModeChange} playing={sourcePlaying} running={state.running && !state.starting} activity={state.power > .01 || ((state.motorLoad ?? 0) < -.01 && state.speed > 1)} onStop={() => source.current?.stop()} onAudition={(candidate, input) => { return source.current?.audition(candidate.urls, input, candidate.label) ?? Promise.resolve(false) }} />, discoveryContainer)}
      {backendReady && !state.search.active && !state.soundSweepActive ? <><SteadySource headless onError={onAudioError} granularMode={granularMode} onModeChange={onModeChange} ref={source} compact={embedded} blocked={false} onPlay={() => { onSourceSelected?.(); setSourcePlaying(true) }} onPlayingChange={setSourcePlaying} driving={{ running: state.running, starting: state.starting, speedKmh: state.speed, power: state.power, acceleration: state.acceleration, rpm: state.rpm, maxRpm: state.maxRpm, throttle: state.throttleInput, brake: state.brakeInput, motorLoad: typeof state.motorLoad === 'number' ? state.motorLoad : null }} /></> : <p className="sound-editor-error">{!backendReady ? 'Restart EV Sound Lab to load live source support.' : 'Stop the experiment or audio debug sweep to try the source renderer.'}</p>}
    </>}
  </section>
}
