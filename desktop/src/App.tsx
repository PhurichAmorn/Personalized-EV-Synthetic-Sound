import { lazy, Suspense, useEffect, useRef, useState } from 'react'
import { tauriClient, type BackendMessage } from './client'
import Dashboard from './Dashboard'
import type { SourceDiscoveryState } from './SourceSearch'
import PageShell from './PageShell'
import type { HistoryPreview } from './TraceHistory'
const TraceHistory = lazy(() => import('./TraceHistory'))
import type { NavTarget } from './NavRail'
import OverlayHost from './OverlayHost'
import Confirm from './Confirm'
import { LanguageGate, useT } from './i18n'
import LegacySearch, { closeLegacySearch, type Search } from './legacy/LegacySearch'

export type State = {
  sourceMode: 'Simulator' | 'BeamNG'; beamngConnected: boolean; beamngError: string
  beamngThrottle: number; beamngBrake: number; beamngRegen: number
  running: boolean; starting: boolean; speed: number; rpm: number; gear: number; hasGears: boolean
  maxRpm: number; speedGaugeMaximum: number; kmhPerOctave?: number; power: number; charge: number; acceleration?: number; motorLoad?: number; sourceAudition?: boolean
  regenActive: boolean; vehicle: string; vehicleNames: string[]; specs: string
  soundTheme: string; soundThemes: string[]; soundRecipes: Record<string, string[]>;
  soundRecipeSelection: Record<string, string>; parameters: string
  soundSweepActive: boolean; audioError: string; throttleInput: number; brakeInput: number; controllerThrottle: number; controllerBrake: number
  controllerName: string; controllerBattery: string; controllerError: string
  availableControllers: { id: number; name: string }[]; controllerEnabled: boolean
  sourceDiscovery?: SourceDiscoveryState
  historyPreview?: HistoryPreview
  mySound?: { id: string; session: string; label: string; recipe: unknown } | null  // chosen (else newest) saved final sound; GS plays it
  mySounds?: { session: string; created: string; label: string }[]  // final pick of every saved session, newest first
  search: Search
}

function readError(error: unknown) { return error instanceof Error ? error.message : String(error) }
function number(value: number, digits = 0) { return Number.isFinite(value) ? value.toFixed(digits) : '—' }
let cursorTimer: ReturnType<typeof setTimeout> | undefined
let isCursorActive = false

export function showCursor(durationMs = 2500) {
  isCursorActive = true
  if (typeof document !== 'undefined') {
    document.body.classList.add('dpad-cursor-active')
  }
  if (cursorTimer !== undefined) clearTimeout(cursorTimer)
  cursorTimer = setTimeout(() => {
    cursorTimer = undefined
    isCursorActive = false
    if (typeof document !== 'undefined') {
      document.body.classList.remove('dpad-cursor-active')
    }
  }, durationMs)
}

export function hideCursor() {
  if (cursorTimer !== undefined) {
    clearTimeout(cursorTimer)
    cursorTimer = undefined
  }
  isCursorActive = false
  if (typeof document !== 'undefined') {
    document.body.classList.remove('dpad-cursor-active')
  }
}

export function isCursorVisible() {
  return isCursorActive
}

export function navigate(action: string) {
  const scope = Array.from(document.querySelectorAll<HTMLElement>('[role="dialog"][aria-modal="true"]'))
    .filter(dialog => dialog.offsetParent !== null).at(-1) || document
  const controls = Array.from(scope.querySelectorAll<HTMLElement>('button:not(:disabled), select:not(:disabled), input:not(:disabled)'))
    .filter(control => control.offsetParent !== null)
  const current = document.activeElement as HTMLElement | null

  const isDirectional = action === 'up' || action === 'down' || action === 'left' || action === 'right'

  // If cursor has faded away, the first directional D-pad press wakes it up in place without moving!
  if (isDirectional && !isCursorActive) {
    showCursor()
    if (current && controls.includes(current) && (scope === document || scope.contains(current))) {
      current.focus()
    } else if (controls.length > 0) {
      controls[0].focus()
    }
    return
  }

  showCursor()

  if (scope !== document && !scope.contains(current)) { controls[0]?.focus(); return }
  if (action === 'confirm') {
    if (controls.includes(current as HTMLElement)) current?.click()
    else controls[0]?.focus()
    return
  }
  if (current?.dataset.soundSlot && (action === 'left' || action === 'right')) {
    const target = document.querySelector<HTMLButtonElement>(`[data-sound-slot="${action === 'left' ? 'A' : 'B'}"]`)
    target?.focus(); target?.click(); return
  }
  if (current?.dataset.soundSlot && action === 'down') {
    const slot = current.dataset.soundSlot
    const rating = document.querySelector<HTMLButtonElement>(`[data-rating-slot="${slot}"][aria-pressed="true"]`)
      || document.querySelector<HTMLButtonElement>(`[data-rating-slot="${slot}"][data-rating-value="4"]`)
      || document.querySelector<HTMLButtonElement>('[data-preference][aria-pressed="true"]')
      || document.querySelector<HTMLButtonElement>('[data-preference="A"]')
    rating?.focus(); return
  }
  if (current?.dataset.preference && action === 'up') {
    document.querySelector<HTMLButtonElement>('[data-sound-slot].selected')?.focus(); return
  }
  if (current?.dataset.ratingSlot && action === 'up') {
    document.querySelector<HTMLButtonElement>(`[data-sound-slot="${current.dataset.ratingSlot}"]`)?.focus(); return
  }
  const step = action === 'up' || action === 'left' ? -1 : action === 'down' || action === 'right' ? 1 : 0
  if (!step || !controls.length) return
  const index = controls.indexOf(current as HTMLElement)
  controls[Math.max(0, Math.min(controls.length - 1, index + step))]?.focus()
}

export default function App({ overlay = false }: { overlay?: boolean }) {
  const client = useRef<ReturnType<typeof tauriClient> | null>(null)
  const keys = useRef(new Set<string>())
  const [state, setState] = useState<State | null>(null)
  const [error, setError] = useState('')
  const [page, setPage] = useState<'dashboard' | 'search' | 'trace'>('dashboard')
  const [closeRequested, setCloseRequested] = useState(false)
  const [soundLabStart, setSoundLabStart] = useState(false)
  const back = useRef<() => void>(() => {})

  useEffect(() => {
    let disposed = false
    let disconnect = () => {}
    // State arrives ~30x/s. Render only the newest one per animation frame so slow renders cannot build a backlog of stale states.
    let pending: State | null = null
    let firstState = false
    let frame = 0
    const queueState = (next: State) => {
      pending = next
      if (!frame) frame = requestAnimationFrame(() => { frame = 0; if (!disposed && pending) setState(pending); pending = null })
    }
    try {
      const instance = tauriClient()
      client.current = instance
      void instance.connect((message: BackendMessage) => {
        if (disposed) return
        if (message.event === 'state') {
          if (!firstState) { firstState = true; void window.__TAURI__?.core.invoke('startup_mark', { label: `${overlay ? 'overlay' : 'dashboard'} got first backend state` }) }
          queueState(message.data as State)
        }
        if (message.event === 'error') setError(String(message.data))
        if (message.event === 'close-request') setCloseRequested(true)
        if (message.event === 'navigate') {
          if (overlay) return
          if (message.data === 'back') {
            showCursor()
            back.current()
          } else navigate(String(message.data))
        }
      }).then(stop => {
        if (disposed) { stop(); return }
        disconnect = stop
        void instance.command('snapshot').then(data => { if (!disposed) setState(data as State) })
          .catch(reason => { if (!disposed) setError(readError(reason)) })
      }).catch(reason => setError(readError(reason)))
    } catch (reason) { setError(readError(reason)) }
    return () => { disposed = true; cancelAnimationFrame(frame); disconnect(); client.current = null }
  }, [overlay])

  // Only a running discovery has unsaved work (the current pair); a finished one is already autosaved to Sound trace.
  const sourceTrialPresent = !!state?.sourceDiscovery?.active
  // Dashboard and BeamNG overlay both guard closing while a session runs (only one of the two windows exists).
  useEffect(() => {
    void window.__TAURI__?.core.invoke('set_close_guard', { active: !!state?.search.active || sourceTrialPresent })
  }, [state?.search.active, sourceTrialPresent])

  async function closeWithSearch(discard: boolean) {
    if (state?.search.active ? await closeLegacySearch(command, discard) : discard) await window.__TAURI__?.core.invoke('confirm_close', {})
  }


  async function command<T = unknown>(name: string, payload: Record<string, unknown> = {}): Promise<T | null> {
    if (!client.current) return null
    try {
      const result = await client.current.command(name, payload) as T
      setError('')
      return result
    } catch (reason) { setError(readError(reason)); return null }
  }

  // The startup choice decides the input source: overlay window = BeamNG, dashboard window = Simulator.
  const sourceChosen = useRef(false)
  useEffect(() => {
    if (!state || sourceChosen.current) return
    sourceChosen.current = true
    const wanted = overlay ? 'BeamNG' : 'Simulator'
    if (state.sourceMode !== wanted) void command('sourceMode', { value: wanted })
  }, [state])

  useEffect(() => {
    const update = () => {
      void client.current?.command('pedals', { throttle: Number(keys.current.has('w')), brake: Number(keys.current.has('s')) }).catch(setError)
    }
    const down = (event: KeyboardEvent) => {
      if (event.repeat || event.target instanceof HTMLInputElement || event.target instanceof HTMLTextAreaElement || event.target instanceof HTMLSelectElement) return
      const navigation: Record<string, string> = {
        ArrowUp: 'up', ArrowDown: 'down', ArrowLeft: 'left', ArrowRight: 'right',
        Enter: 'confirm', Escape: 'back',
      }
      const action = navigation[event.key]
      if (action) {
        event.preventDefault()
        if (action === 'back') {
          showCursor()
          back.current()
        } else navigate(action)
        return
      }
      const key = (event.code === 'KeyW' ? 'w' : event.code === 'KeyS' ? 's' : event.key.toLowerCase())  // physical key: works in any keyboard layout
      if (key === 'w' || key === 's') { event.preventDefault(); keys.current.add(key); update() }
    }
    const up = (event: KeyboardEvent) => {
      const key = (event.code === 'KeyW' ? 'w' : event.code === 'KeyS' ? 's' : event.key.toLowerCase())  // physical key: works in any keyboard layout
      if (keys.current.delete(key)) { event.preventDefault(); update() }
    }
    const blur = () => {
      keys.current.clear()
      void client.current?.command('focus', { value: false }).catch(setError)
    }
    const focus = () => { if (!overlay) void client.current?.command('focus', { value: true }).catch(setError) }
    window.addEventListener('keydown', down)
    window.addEventListener('keyup', up)
    window.addEventListener('blur', blur)
    window.addEventListener('focus', focus)
    return () => { window.removeEventListener('keydown', down); window.removeEventListener('keyup', up); window.removeEventListener('blur', blur); window.removeEventListener('focus', focus) }
  }, [overlay])

  // The trace page needs no vehicle: stop the simulation (and its sound) instead of leaving it running unseen.
  function openTrace() { if (state?.running) void command('toggle'); setPage('trace') }
  function goTo(target: NavTarget) {
    if (target === 'trace') return openTrace()
    setSoundLabStart(target === 'soundlab'); setPage('dashboard')
  }
  // Leaving pauses a running session (kept in memory, ratings included): Personalize resumes it, so no warning is needed.
  const leaveLab = () => setPage('dashboard')
  const t = useT()
  const [leaving, setLeaving] = useState(false)  // the X during a session: pause or end it (2026-11-21, replaces Back to driving)
  back.current = () => {
    if (closeRequested) setCloseRequested(false)
    else if (page === 'search') leaveLab()
    else if (page !== 'dashboard') setPage('dashboard')
  }
  // The finished session's shortlist and final sound stay in the dashboard slot too, so the listener can drive with them.
  const personalizationActive = !!(state?.search.active || state?.sourceDiscovery?.active || state?.sourceDiscovery?.finalists?.length)
  const searchPanel = state && page === 'search' ? (
<div className={'search-dialog ' + (personalizationActive ? 'search-active' : '')} role="dialog" aria-modal={personalizationActive ? undefined : true} aria-label="Personalize sound"><header className="search-dialog-header"><div><h2 className="text-xl">{t('Personalize sound')}</h2></div><div className="flex gap-2">{!state.search.active && <button className="control search-close" aria-label={t('Close')} title={t('Close')} onClick={() => state.sourceDiscovery?.active ? setLeaving(true) : leaveLab()}><svg className="x-icon" viewBox="0 0 24 24" aria-hidden="true"><path d="M4 4L20 20M20 4L4 20" /></svg></button>}</div></header>{error && <p role="alert" className="mx-6 mt-5 text-red-300">{error}</p>}{state.search.active ? <LegacySearch state={state} command={command} onError={setError} onDone={() => setPage('dashboard')} /> : <div id="source-discovery-slot" />}</div>
  ) : undefined

  return <div className={overlay ? 'beamng-overlay-root' : 'dashboard-wrapper'}>
    <LanguageGate />
    {closeRequested && (state?.search.active ? <Confirm title="Close active search?" text="Save progress, discard this session, or keep working.">
      <button className="control" onClick={() => setCloseRequested(false)}>Cancel</button><button className="control" onClick={() => void closeWithSearch(false)}>Save and close</button><button className="control border-red-500" onClick={() => void closeWithSearch(true)}>Discard and close</button>
    </Confirm> : <Confirm title="End session and close?" text={`Your ${state?.sourceDiscovery?.completed ?? 0} rated pairs are already saved to Sound trace. Closing ends this session: it cannot be resumed, and the pair you are rating now is lost.`}>
      {/* Closing ends a discovery session: it lives in memory only, so it cannot be resumed after the app restarts. */}
      <button className="control" autoFocus onClick={() => setCloseRequested(false)}>Keep working</button><button className="control border-red-500" onClick={() => void closeWithSearch(true)}>End session and close</button>
    </Confirm>)}
    {leaving && <Confirm title={t('Leave the session?')} text={t('Pause keeps your answers so far: Resume session continues it. End stops it without picking a final sound.')}>
      <button className="control" autoFocus onClick={() => setLeaving(false)}>{t('Keep working')}</button><button className="control" onClick={() => { setLeaving(false); leaveLab() }}>{t('Pause')}</button><button className="control border-red-500" onClick={() => { setLeaving(false); leaveLab(); void command('sourceDiscoveryEnd') }}>{t('End session')}</button>
    </Confirm>}
    {!state && <div className="min-h-screen p-5 md:p-8"><div className="panel p-8">{t('Connecting to simulator…')}</div></div>}
    {state && overlay && (page === 'dashboard' || page === 'search') && <OverlayHost state={state} error={error} page={page} onCommand={(name, payload) => command(name, payload)} onPersonalize={() => setPage('search')} searchPanel={searchPanel} />}
    {state && !overlay && (page === 'dashboard' || page === 'search') && <Dashboard personalizeOpen={page === 'search'} state={state} error={error} onCommand={(name, payload) => command(name, payload)} onPersonalize={() => setPage('search')} onTrace={openTrace} initialSoundLab={soundLabStart} searchPanel={page === 'search' && personalizationActive ? searchPanel : null} />}
      {state && page === 'trace' && <PageShell active="trace" title="SOUND TRACE" onNavigate={goTo}>
        {error && <div role="alert" className="mb-4 rounded-lg border border-red-500 bg-red-950 p-3 text-red-200">{error}</div>}
        <Suspense fallback={null}><TraceHistory command={command} preview={state.historyPreview} /></Suspense>
      </PageShell>}
      {searchPanel && !personalizationActive && !overlay && <div className="search-overlay">{searchPanel}</div>}
  </div>
}
