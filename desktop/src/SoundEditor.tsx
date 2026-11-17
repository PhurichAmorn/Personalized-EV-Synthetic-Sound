import { lazy, Suspense, useEffect, useRef, useState, useImperativeHandle, type Ref } from 'react'
import { createPortal } from 'react-dom'
import type { State } from './App'
import SourceSearch from './SourceSearch'
import SteadySource, { type SourceHandle } from './SteadySource'
import type { GranularMode } from './granularPlayer'
import { LabPlayer } from './labEngine'
import { isLiveRecipe, liveSound } from './levels'
import { liveStems } from './voiceCache'
import { simulatedDrive } from './simulatedDrive'
import type { DiscoveryCandidate } from './SourceSearch'
// Sound Lab page loads on first open: the BeamNG overlay and a plain drive never download it.
const SoundLab = lazy(() => import('./SoundLab'))

export default function SoundEditor({ active, state, onCommand, embedded = false, ref, granularMode, onModeChange, onSourceSelected, onAudioError, personalizeOpen = false }: { onAudioError?: (message: string) => void; personalizeOpen?: boolean; onSourceSelected?: () => void; granularMode: GranularMode; onModeChange: (mode: GranularMode) => void; ref?: Ref<SourceHandle>; embedded?: boolean; active: boolean; state: State; onCommand: (name: string, payload?: Record<string, unknown>) => Promise<unknown> | void }) {
  const source = useRef<SourceHandle>(null)
  const [discoveryContainer] = useState(() => document.createElement('div'))
  useEffect(() => {
    const host = personalizeOpen ? document.getElementById('source-discovery-slot') : null
    if (host) host.appendChild(discoveryContainer)
    return () => discoveryContainer.remove()
  }, [personalizeOpen, state.search.active, state.sourceDiscovery?.active, discoveryContainer])
  const [sourcePlaying, setSourcePlaying] = useState(false)
  const [labStop, setLabStop] = useState(0)
  // Level-search sounds play through the Sound Lab engine (labEngine.ts), not the old style player.
  const [lab] = useState(() => new LabPlayer())
  const [labPlaying, setLabPlaying] = useState(false)
  const driving = { running: state.running, starting: state.starting, speedKmh: state.speed, power: state.power, acceleration: state.acceleration, rpm: state.rpm, maxRpm: state.maxRpm, throttle: state.throttleInput, brake: state.brakeInput, motorLoad: typeof state.motorLoad === 'number' ? state.motorLoad : null }
  const latest = useRef({ input: driving, at: performance.now() })
  useEffect(() => { latest.current = { input: driving, at: performance.now() } }, [state])
  useEffect(() => () => lab.close(), [lab])
  const stopLab = () => { lab.stop(); setLabPlaying(false) }
  const stopAll = () => { source.current?.stop(); stopLab() }
  const audition = async (candidate: DiscoveryCandidate, input: 'driving' | 'simulated') => {
    if (!isLiveRecipe(candidate.recipe)) { stopLab(); return source.current?.audition(candidate.urls, input, candidate.label) ?? false }
    source.current?.stop()
    try {
      const { plain, fx, mode, travel } = liveSound(candidate.recipe)
      await lab.play(candidate.id, await liveStems(candidate.recipe), fx, plain.rootHz, input === 'simulated' ? 'simulated' : 'live',
        () => ({ input: latest.current.input, stale: performance.now() - latest.current.at > 750 }), simulatedDrive, mode, travel)
      setLabPlaying(true); return true
    } catch (problem) { stopLab(); return problem instanceof Error ? problem.message : 'Could not play the sound.' }
  }
  const command = useRef(onCommand)
  command.current = onCommand
  const startSound = (refresh = false) => {
    if (source.current) { command.current('sourceAudition', { value: true }); source.current.start(refresh) }
  }
  useImperativeHandle(ref, () => ({ start: startSound, analyser: () => (lab.playing ? lab.analyser : source.current?.analyser()) ?? null, auditionContext: () => source.current?.auditionContext() ?? {}, audition: (urls, input, label) => source.current?.audition(urls, input, label) ?? Promise.resolve(false), stop: () => { stopAll(); setSourcePlaying(false); command.current('sourceAudition', { value: false }) } }))
  const discoveryWorkspace = embedded && !state.search.active && !state.soundSweepActive && !!state.sourceDiscovery?.active
  useEffect(() => { void command.current('sourceAudition', { value: sourcePlaying || discoveryWorkspace }) }, [sourcePlaying, discoveryWorkspace])
  useEffect(() => () => { void command.current('sourceAudition', { value: false }) }, [])
  const backendReady = typeof state.sourceAudition === 'boolean' && typeof state.motorLoad === 'number'
  return <section className={"sound-editor" + (embedded ? " sound-editor-embedded" : "")} hidden={!active || embedded} aria-label="Sound Lab">
    {active && <>
      {!embedded && <Suspense fallback={null}><SoundLab onStart={stopAll} stopToken={labStop} /></Suspense>}
      {backendReady && !state.search.active && !state.soundSweepActive && createPortal(<SourceSearch hidden={!personalizeOpen} discovery={state.sourceDiscovery} onCommand={onCommand} onContext={() => lab.playing ? lab.context() : source.current?.auditionContext() ?? { input: 'live', style: granularMode }} mode={granularMode} onModeChange={onModeChange} playing={sourcePlaying || labPlaying} running={state.running && !state.starting} activity={state.power > .01 || ((state.motorLoad ?? 0) < -.01 && state.speed > 1)} onStop={stopAll} onAudition={audition} />, discoveryContainer)}
      {backendReady && !state.search.active && !state.soundSweepActive ? <><SteadySource headless onError={onAudioError} granularMode={granularMode} onModeChange={onModeChange} ref={source} compact blocked={false} onPlay={() => { onSourceSelected?.(); setSourcePlaying(true); setLabStop(value => value + 1); stopLab() }} onPlayingChange={setSourcePlaying} driving={driving} /></> : <p className="sound-editor-error">{!backendReady ? 'Restart EV Sound Lab to load live source support.' : 'Stop the experiment or audio debug sweep to try the source renderer.'}</p>}
    </>}
  </section>
}
