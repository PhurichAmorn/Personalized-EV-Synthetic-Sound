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
  onClose: () => void
  searchPanel: ReactNode
}

/** BeamNG mode: the overlay owns the sound player (the dashboard window does not exist in this mode). */
export default function OverlayHost({ state, error, page, onCommand, onPersonalize, onClose, searchPanel }: Props) {
  const car = useCarSound(state, onCommand, page === 'search')
  const [audioError, setAudioError] = useState('')
  const startStop = async () => {
    if (!state.running) car.stop()
    await onCommand('toggle')
  }
  // The HUD never takes keyboard focus from the game, except on the last-question panel (session over, comment box): typing there must not reach the game.
  const discovery = state.sourceDiscovery
  const typing = page === 'search' && !!discovery && !discovery.active && !!discovery.final && discovery.rating == null
  useEffect(() => { void window.__TAURI__?.core.invoke('set_overlay_focusable', { focusable: typing }) }, [page, typing])
  return <>
    {/* One card for both pages: Personalize keeps the live graphs and adds the session below them. */}
    <BeamNGOverlay state={state} error={error || audioError} onCommand={onCommand} onPersonalize={onPersonalize} onClose={onClose} onStartStop={() => void startStop()} analyser={car.analyser}
          granular={car.gs} granularMode={car.mode} onGranular={car.start} onGranularCycle={car.cycle}
          personalize={page === 'search' ? searchPanel : undefined} />
    <SoundEditor onAudioError={setAudioError} {...car.editor} active state={state} onCommand={onCommand} embedded />
  </>
}
