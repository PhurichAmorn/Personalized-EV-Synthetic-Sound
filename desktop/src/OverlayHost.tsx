import { useEffect, useRef, useState, type ReactNode } from 'react'
import type { State } from './App'
import BeamNGOverlay from './BeamNGOverlay'
import SoundEditor from './SoundEditor'
import type { SourceHandle } from './SteadySource'
import type { GranularMode } from './granularPlayer'

type Props = {
  state: State
  error: string
  page: 'dashboard' | 'search'
  onCommand: (name: string, payload?: Record<string, unknown>) => Promise<unknown> | void
  onPersonalize: () => void
  onLeave: () => void
  searchPanel: ReactNode
}

/** BeamNG mode: the overlay owns the sound player (the dashboard window does not exist in this mode). */
export default function OverlayHost({ state, error, page, onCommand, onPersonalize, onLeave, searchPanel }: Props) {
  const sound = useRef<SourceHandle>(null)
  const [granularSelected, setGranularSelected] = useState(true)
  const [granularMode, setGranularMode] = useState<GranularMode>('evolving')
  const [audioError, setAudioError] = useState('')
  useEffect(() => {
    if (state.running && !state.starting && granularSelected && !state.search.active && !state.soundSweepActive && !state.sourceDiscovery?.active) sound.current?.start(true)
  }, [state.running, state.starting])
  const startStop = async () => {
    if (!state.running) {
      sound.current?.stop()
      await onCommand('sourceAudition', { value: false })
    }
    await onCommand('toggle')
  }
  return <>
    {page === 'dashboard'
      ? <BeamNGOverlay state={state} error={error || audioError} onCommand={onCommand} onPersonalize={onPersonalize} onStartStop={() => void startStop()}
          granular={granularSelected} granularMode={granularMode}
          onGranular={() => { setGranularSelected(true); sound.current?.start(true) }}
          onGranularCycle={() => { setGranularMode(mode => mode === 'steady' ? 'rise' : mode === 'rise' ? 'evolving' : 'steady'); setGranularSelected(true); sound.current?.start(true) }}
          onTheme={name => { setGranularSelected(false); sound.current?.stop(); void onCommand('theme', { name }) }} />
      : <div className="overlay-personalization">{searchPanel}<button className="control overlay-return" onClick={onLeave}>Back to driving</button></div>}
    <SoundEditor onAudioError={setAudioError} personalizeOpen={page === 'search'} onSourceSelected={() => setGranularSelected(true)} granularMode={granularMode} onModeChange={setGranularMode} ref={sound} active state={state} onCommand={onCommand} embedded />
  </>
}
