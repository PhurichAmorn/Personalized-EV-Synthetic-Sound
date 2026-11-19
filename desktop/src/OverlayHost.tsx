import { useEffect, useState, type ReactNode } from 'react'
import type { State } from './App'
import BeamNGOverlay from './BeamNGOverlay'
import SoundEditor, { useCarSound } from './SoundEditor'

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
  const car = useCarSound(state, onCommand, page === 'search')
  const [audioError, setAudioError] = useState('')
  const startStop = async () => {
    if (!state.running) car.stop()
    await onCommand('toggle')
  }
  // The HUD never takes keyboard focus from the game, including on the Personalize page: it has no text fields, and A/B choices work by mouse or gamepad.
  useEffect(() => { void window.__TAURI__?.core.invoke('set_overlay_focusable', { focusable: false }) }, [page])
  return <>
    {/* One card for both pages: Personalize keeps the live graphs and adds the session below them. */}
    <BeamNGOverlay state={state} error={error || audioError} onCommand={onCommand} onPersonalize={onPersonalize} onStartStop={() => void startStop()} analyser={car.analyser}
          granular={car.gs} granularMode={car.mode} onGranular={car.start} onGranularCycle={car.cycle} onTheme={car.theme}
          personalize={page === 'search' ? searchPanel : undefined} onLeave={onLeave} />
    <SoundEditor onAudioError={setAudioError} {...car.editor} active state={state} onCommand={onCommand} embedded />
  </>
}
