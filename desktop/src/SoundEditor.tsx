import { lazy, Suspense, useEffect, useRef, useState, useImperativeHandle, type Ref } from 'react'
import { createPortal } from 'react-dom'
import type { State } from './App'
import SourceSearch from './SourceSearch'
import SteadySource, { type SourceHandle } from './SteadySource'
import type { GranularMode } from './granularPlayer'
import { LabPlayer } from './labEngine'
import { isLiveRecipe, liveSound } from './levels'
import { liveStems, ownStems } from './voiceCache'
import { simulatedDrive } from './simulatedDrive'
import type { DiscoveryCandidate } from './SourceSearch'
// Sound Lab page loads on first open: the BeamNG overlay and a plain drive never download it.
const SoundLab = lazy(() => import('./SoundLab'))

export default function SoundEditor({ active, state, onCommand, embedded = false, ref, granularMode, onModeChange, onSourceSelected, onAudioError, personalizeOpen = false, gsSelected }: { gsSelected: boolean; onAudioError?: (message: string) => void; personalizeOpen?: boolean; onSourceSelected?: () => void; granularMode: GranularMode; onModeChange: (mode: GranularMode) => void; ref?: Ref<SourceHandle>; embedded?: boolean; active: boolean; state: State; onCommand: (name: string, payload?: Record<string, unknown>) => Promise<unknown> | void }) {
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
  const audition = async (candidate: DiscoveryCandidate, input: 'driving' | 'simulated', motion?: GranularMode) => {
    if (!isLiveRecipe(candidate.recipe)) { stopLab(); return source.current?.audition(candidate.urls, input, candidate.label) ?? false }
    source.current?.stop()
    try {
      const { plain, fx, mode, travel } = liveSound(candidate.recipe)
      const started = await lab.play(candidate.id, liveStems(candidate.recipe), fx, plain.rootHz, input === 'simulated' ? 'simulated' : 'live',
        () => ({ input: latest.current.input, stale: performance.now() - latest.current.at > 750 }), simulatedDrive, motion ?? mode, travel)
      if (started) setLabPlaying(true)
      return true  // superseded by a newer click: not an error
    } catch (problem) { stopLab(); return problem instanceof Error ? problem.message : 'Could not play the sound.' }
  }
  const command = useRef(onCommand)
  command.current = onCommand
  // GS plays the driver's sound (newest saved final, kept across restarts) in the GS mode; the stock source only before any session.
  const my = state.mySound
  const mine = my && isLiveRecipe(my.recipe) ? { id: my.id, label: my.label, recipe: my.recipe, urls: [], traces: {} } : null
  // Load the driver's own sound at app start (from disk after its first build), so GS and BeamNG never wait for a build.
  useEffect(() => { if (mine) void ownStems(mine.recipe).catch(() => {}) }, [mine?.id])
  const startSound = (refresh = false, motion = granularMode) => {
    if (mine) { onSourceSelected?.(); void audition(mine, 'driving', motion) }
    else source.current?.start(refresh)
  }
  useImperativeHandle(ref, () => ({ start: startSound, analyser: () => (lab.playing ? lab.analyser : source.current?.analyser()) ?? null, auditionContext: () => source.current?.auditionContext() ?? {}, audition: (urls, input, label) => source.current?.audition(urls, input, label) ?? Promise.resolve(false), stop: () => { stopAll(); setSourcePlaying(false) } }))
  const discoveryWorkspace = embedded && (!!state.sourceDiscovery?.active || (personalizeOpen && !!state.sourceDiscovery?.finalists?.length))
  // The one mute rule: the backend car sound plays only when a theme is chosen and nothing app-side plays (session, podium, GS).
  const muteBackend = !state.search.active && !state.soundSweepActive && (gsSelected || sourcePlaying || labPlaying || discoveryWorkspace)
  useEffect(() => { void command.current('sourceAudition', { value: muteBackend }) }, [muteBackend])
  useEffect(() => () => { void command.current('sourceAudition', { value: false }) }, [])
  const backendReady = typeof state.sourceAudition === 'boolean' && typeof state.motorLoad === 'number'
  return <section className={"sound-editor" + (embedded ? " sound-editor-embedded" : "")} hidden={!active || embedded} aria-label="Sound Lab">
    {active && <>
      {!embedded && <Suspense fallback={null}><SoundLab state={state} onCommand={onCommand} onStart={stopAll} stopToken={labStop} /></Suspense>}
      {backendReady && !state.search.active && !state.soundSweepActive && createPortal(<SourceSearch hidden={!personalizeOpen} discovery={state.sourceDiscovery} onCommand={onCommand} onContext={() => lab.playing ? lab.context() : source.current?.auditionContext() ?? { input: 'live', style: granularMode }} mode={granularMode} onModeChange={onModeChange} playing={sourcePlaying || labPlaying} running={state.running && !state.starting} activity={state.power > .01 || ((state.motorLoad ?? 0) < -.01 && state.speed > 1)} onStop={stopAll} onAudition={audition} />, discoveryContainer)}
      {backendReady && !state.search.active && !state.soundSweepActive ? <><SteadySource onError={onAudioError} granularMode={granularMode} ref={source} onPlay={() => { onSourceSelected?.(); setSourcePlaying(true); setLabStop(value => value + 1); stopLab() }} onPlayingChange={setSourcePlaying} driving={driving} /></> : <p className="sound-editor-error">{!backendReady ? 'Restart EV Sound Lab to load live source support.' : 'Stop the experiment or audio debug sweep to try the source renderer.'}</p>}
    </>}
  </section>
}

type Command = (name: string, payload?: Record<string, unknown>) => Promise<unknown> | void
/** One owner for what the car plays: GS (the driver's sound, else the stock source) or a backend theme. Dashboard and the BeamNG overlay both use it. */
export function useCarSound(state: State, onCommand: Command, personalizeOpen: boolean) {
  const ref = useRef<SourceHandle>(null)
  const [gs, setGs] = useState(true)
  const [mode, setMode] = useState<GranularMode>('rise')
  const start = (next = mode) => { setGs(true); ref.current?.start(true, next) }
  const idle = !state.search.active && !state.soundSweepActive && !state.sourceDiscovery?.active
  // Car on, or Personalize closed: GS (re)starts in the GS mode, which also ends any podium playback.
  // ...and when the driver's sound changes (picked in the list), GS switches to it.
  // A new driver's sound also brings its motion (the session's pair 1 choice): GS switches to Rise or Evolving with it.
  const soundId = useRef(state.mySound?.id)
  useEffect(() => {
    const changed = soundId.current !== state.mySound?.id; soundId.current = state.mySound?.id
    const own = (state.mySound?.recipe as { motion?: unknown } | undefined)?.motion
    const next = changed && (own === 'rise' || own === 'evolving') ? own : mode
    if (next !== mode) setMode(next)
    if (state.running && !state.starting && gs && idle && !personalizeOpen) start(next)
  }, [state.running, state.starting, personalizeOpen, state.mySound?.id])
  return {
    gs, mode, start: () => start(),
    select: (next: GranularMode) => { setMode(next); start(next) },
    cycle: () => { const next = mode === 'steady' ? 'rise' : mode === 'rise' ? 'evolving' : 'steady'; setMode(next); start(next) },
    stop: () => ref.current?.stop(),
    resume: () => { if (gs && state.running) ref.current?.start() },
    analyser: () => ref.current?.analyser() ?? null,
    editor: { ref, gsSelected: gs, granularMode: mode, onModeChange: setMode, onSourceSelected: () => setGs(true), personalizeOpen },
  }
}
