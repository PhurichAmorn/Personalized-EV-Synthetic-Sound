import { useEffect, useRef, useState } from 'react'
import { tauriClient, type BackendMessage } from './client'
import Dashboard from './Dashboard'
import PageShell from './PageShell'
import TraceFlow, { type Candidate, type Comparison } from './TraceFlow'

type Search = {
  active: boolean; participant: string; mode: string; learningMethod: string; algorithm: string
  pairNumber: number; selected: string; triedA: boolean; triedB: boolean
  preference: string; preferenceReady: boolean; checkpoint: string; error: string
  ratingA: number; ratingB: number; ratingSources: Record<string, number>; feedbackReady: boolean
}
export type State = {
  running: boolean; starting: boolean; speed: number; rpm: number; gear: number; hasGears: boolean
  maxRpm: number; speedGaugeMaximum: number; power: number; charge: number
  regenActive: boolean; vehicle: string; vehicleNames: string[]; specs: string
  soundTheme: string; soundThemes: string[]; parameters: string
  soundSweepActive: boolean; audioError: string; throttleInput: number; brakeInput: number
  controllerName: string; controllerBattery: string; controllerError: string
  availableControllers: { id: number; name: string }[]; controllerEnabled: boolean
  search: Search
}
type SavedSession = { id: string; text: string; favorite: boolean }
type TraceSession = { id: string; participant: string; mode: string; created: string; completed: number }
type Trace = { id: string; participant: string; mode: string; status: string; completed: number; learning_method?: string; skipped_pairs?: unknown[]; comparisons: Comparison[]; favorite?: string; favorite_slot?: string }

function readError(error: unknown) { return error instanceof Error ? error.message : String(error) }
function number(value: number, digits = 0) { return Number.isFinite(value) ? value.toFixed(digits) : '—' }
function navigate(action: string) {
  const scope = Array.from(document.querySelectorAll<HTMLElement>('[role="dialog"][aria-modal="true"]'))
    .filter(dialog => dialog.offsetParent !== null).at(-1) || document
  const controls = Array.from(scope.querySelectorAll<HTMLElement>('button:not(:disabled), select:not(:disabled), input:not(:disabled)'))
    .filter(control => control.offsetParent !== null)
  const current = document.activeElement as HTMLElement | null
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

export default function App() {
  const client = useRef<ReturnType<typeof tauriClient> | null>(null)
  const keys = useRef(new Set<string>())
  const [state, setState] = useState<State | null>(null)
  const [error, setError] = useState('')
  const [page, setPage] = useState<'dashboard' | 'search' | 'trace'>('dashboard')
  const [participant, setParticipant] = useState('')
  const [mode, setMode] = useState('Deep')
  const [method, setMethod] = useState('gp_preference')
  const [sessions, setSessions] = useState<SavedSession[]>([])
  const [traceSessions, setTraceSessions] = useState<TraceSession[]>([])
  const [trace, setTrace] = useState<Trace | null>(null)
  const [deleteTarget, setDeleteTarget] = useState<Trace | null>(null)
  const [deleteError, setDeleteError] = useState('')
  const [favoriteChoiceOpen, setFavoriteChoiceOpen] = useState(false)
  const [selectedCandidate, setSelectedCandidate] = useState<Candidate | null>(null)
  const [selectedAudition, setSelectedAudition] = useState<Record<string, number>>({})
  const [closeRequested, setCloseRequested] = useState(false)
  const back = useRef<() => void>(() => {})

  useEffect(() => {
    let disposed = false
    let disconnect = () => {}
    try {
      const instance = tauriClient()
      client.current = instance
      void instance.connect((message: BackendMessage) => {
        if (disposed) return
        if (message.event === 'state') setState(message.data as State)
        if (message.event === 'error') setError(String(message.data))
        if (message.event === 'close-request') setCloseRequested(true)
        if (message.event === 'navigate') {
          if (message.data === 'back') back.current()
          else navigate(String(message.data))
        }
      }).then(stop => {
        if (disposed) { stop(); return }
        disconnect = stop
        void instance.command('snapshot').then(data => { if (!disposed) setState(data as State) })
          .catch(reason => { if (!disposed) setError(readError(reason)) })
      }).catch(reason => setError(readError(reason)))
    } catch (reason) { setError(readError(reason)) }
    return () => { disposed = true; disconnect(); client.current = null }
  }, [])

  useEffect(() => {
    void window.__TAURI__?.core.invoke('set_close_guard', { active: !!state?.search.active })
  }, [state?.search.active])

  async function closeWithSearch(discard: boolean) {
    if (discard) {
      const removed = await command<boolean>('searchDiscard')
      if (!removed) return
    } else {
      const result = await command<State>('searchFinish', { satisfied: false })
      if (!result || result.search.active || result.search.error) return
    }
    await window.__TAURI__?.core.invoke('confirm_close', {})
  }

  async function command<T = unknown>(name: string, payload: Record<string, unknown> = {}): Promise<T | null> {
    if (!client.current) return null
    try {
      const result = await client.current.command(name, payload) as T
      setError('')
      return result
    } catch (reason) { setError(readError(reason)); return null }
  }

  useEffect(() => {
    const update = () => {
      void client.current?.command('pedals', { throttle: Number(keys.current.has('w')), brake: Number(keys.current.has('s')) }).catch(setError)
    }
    const down = (event: KeyboardEvent) => {
      if (event.repeat || event.target instanceof HTMLInputElement || event.target instanceof HTMLTextAreaElement || event.target instanceof HTMLSelectElement) return
      const key = event.key.toLowerCase()
      if (key === 'w' || key === 's') { event.preventDefault(); keys.current.add(key); update() }
    }
    const up = (event: KeyboardEvent) => {
      const key = event.key.toLowerCase()
      if (keys.current.delete(key)) { event.preventDefault(); update() }
    }
    const blur = () => {
      keys.current.clear()
      void client.current?.command('focus', { value: false }).catch(setError)
    }
    const focus = () => { void client.current?.command('focus', { value: true }).catch(setError) }
    window.addEventListener('keydown', down)
    window.addEventListener('keyup', up)
    window.addEventListener('blur', blur)
    window.addEventListener('focus', focus)
    return () => { window.removeEventListener('keydown', down); window.removeEventListener('keyup', up); window.removeEventListener('blur', blur); window.removeEventListener('focus', focus) }
  }, [])

  async function startSearch() {
    const result = await command<State>('searchStart', { participant, mode, method })
    if (!result?.search.active) { if (result?.search.error) setError(result.search.error); return }
    await chooseUnrated(result.search)
    if (!result.running) await command('toggle')
  }
  async function restore(id: string, favoriteOnly: boolean) {
    const result = await command<State>('searchRestore', { id, favoriteOnly })
    if (!result || result.search.error) { if (result?.search.error) setError(result.search.error); return }
    if (!favoriteOnly) await chooseUnrated(result.search)
    if (!result.running) await command('toggle')
  }
  async function next() {
    let result = await command<State>('searchNext')
    if (result?.search.active && result.search.checkpoint && !result.search.error) result = await command<State>('searchContinue')
    if (result?.search.active && !result.search.checkpoint && !result.search.error) await chooseUnrated(result.search)
  }
  async function chooseUnrated(search: Search) {
    const slot = search.learningMethod === 'evolutionary' && search.ratingA > 0 && search.ratingB === 0 ? 'B' : 'A'
    await command('searchChoose', { slot })
  }
  async function finishSearch(satisfied: boolean, favoriteSlot = '') {
    const result = await command<State>('searchFinish', { satisfied, favoriteSlot })
    if (result && !result.search.active && !result.search.error) { setFavoriteChoiceOpen(false); setPage('dashboard') }
  }
  async function refreshSessions() { setSessions(await command<SavedSession[]>('searchSessions', { participant }) || []) }
  async function openTrace() { setTraceSessions(await command<TraceSession[]>('traceSessions') || []); setPage('trace') }
  async function deleteExperiment() {
    if (!deleteTarget) return
    setDeleteError('')
    try {
      const deleted = await command<boolean>('traceDelete', { id: deleteTarget.id })
      if (!deleted) throw new Error('Could not delete experiment.')
      setTraceSessions(rows => rows.filter(row => row.id !== deleteTarget.id))
      if (trace?.id === deleteTarget.id) { setTrace(null); setSelectedCandidate(null); setSelectedAudition({}) }
      setDeleteTarget(null)
    } catch (error) { setDeleteError(readError(error)) }
  }
  back.current = () => {
    if (favoriteChoiceOpen) setFavoriteChoiceOpen(false)
    else if (closeRequested) setCloseRequested(false)
    else if (deleteTarget) { setDeleteTarget(null); setDeleteError('') }
    else if (page !== 'dashboard') setPage('dashboard')
  }
  const searchPanel = state && page === 'search' ? (
<div className={'search-dialog ' + (state.search.active ? 'search-active' : '')} role="dialog" aria-modal={state.search.active ? undefined : true} aria-label="Personalize sound"><header className="search-dialog-header"><div><h2 className="text-xl">Personalize sound</h2>{state.search.active && <p className="text-sm text-slate-400">Pair {state.search.pairNumber}{state.search.algorithm === 'gp-feature-v2' && <> · {state.search.pairNumber <= 6 ? 'Explore features' : state.search.pairNumber >= 18 && state.search.pairNumber <= 20 ? 'Combine preferred features' : 'Refine preference'}</>}</p>}</div>{!state.search.active && <button className="control" onClick={() => setPage('dashboard')}>Close</button>}</header>{error && <p role="alert" className="mx-6 mt-5 text-red-300">{error}</p>}<div className="search-content">
        <section className="panel space-y-4 p-6"><h3 className="text-lg">Session setup</h3><label className="block"><span className="label">Participant alias</span><input className="control mt-2 w-full" maxLength={80} value={participant} onChange={event => setParticipant(event.target.value)} /></label><label className="block"><span className="label">Starting sound</span><select className="control mt-2 w-full" value={mode} onChange={event => setMode(event.target.value)}>{state.soundThemes.map(name => <option key={name}>{name}</option>)}</select></label><label className="block"><span className="label">Method</span><select className="control mt-2 w-full" value={method} onChange={event => setMethod(event.target.value)}><option value="gp_preference">GP preference + BO</option><option value="evolutionary">Evolutionary</option></select></label><div className="flex gap-2"><button className="control" disabled={state.search.active || state.running || state.soundSweepActive} onClick={() => void startSearch()}>New session</button><button className="control" onClick={() => void refreshSessions()}>Find saved</button></div></section>
        <section className="panel p-4">{state.search.active ? <><h3 className="text-lg">A/B comparison</h3>
          {state.search.pairNumber % 10 === 0 && !state.search.checkpoint && <p className="mt-3 rounded-lg border border-amber-500/60 bg-amber-950/30 p-3 text-sm text-amber-200" role="status"><strong>{state.search.pairNumber % 20 === 0 ? 'Last pair in this block.' : `Checkpoint at pair ${state.search.pairNumber}.`}</strong> Listen to A and B. If satisfied, save your favorite. Otherwise grade this pair and continue search.</p>}
          <div className="my-4 grid grid-cols-2 gap-3">{(['A', 'B'] as const).map(slot => <button key={slot} data-sound-slot={slot} className={'control py-8 text-2xl ' + (state.search.selected === slot ? 'selected' : '')} onClick={() => void command('searchChoose', { slot })}>Sound {slot}{state.search.learningMethod === 'evolutionary' && state.search.ratingSources[slot] > 0 && <small className="mt-1 block text-xs font-normal">Previously heard · score {slot === 'A' ? state.search.ratingA : state.search.ratingB}/7</small>}</button>)}</div>
          {state.search.learningMethod === 'evolutionary' ? <div className="space-y-3">{(['A', 'B'] as const).map(slot => {
            const score = slot === 'A' ? state.search.ratingA : state.search.ratingB
            const source = state.search.ratingSources[slot] || 0
            return <div key={slot}><div className="mb-2 flex items-center justify-between"><span className="label">Sound {slot} · score 1–7</span>{source > 0 && <span className="text-xs text-emerald-300">Score carried from pair {source}; tap to change</span>}</div><div className="preference-scale"><span className="preference-line" />{Array.from({ length: 7 }, (_, index) => index + 1).map(value => <button key={value} data-rating-slot={slot} data-rating-value={value} aria-label={`Sound ${slot} score ${value}`} aria-pressed={score === value} className={'preference-node' + (score === value ? ' selected' : '')} disabled={!(slot === 'A' ? state.search.triedA : state.search.triedB) && !source} onClick={() => void command('searchRate', { slot, value })}>{value}</button>)}</div></div>
          })}{state.search.preference && !(state.search.ratingA && state.search.ratingB) && <p className="text-xs text-slate-400">This resumed pair has a saved pairwise preference. Next can use it, or score both sounds to replace it.</p>}</div> : <div className="preference-scale-wrap"><div className="label">Which sound do you prefer?</div><div className="mt-2 grid grid-cols-2 gap-2" role="group" aria-label="Sound preference">{(['A', 'B'] as const).map(value => <button key={value} data-preference={value} aria-pressed={state.search.preference === value} className={'control py-3 text-sm' + (state.search.preference === value ? ' selected' : '')} disabled={!state.search.triedA || !state.search.triedB || !!state.search.checkpoint} onClick={() => void command('searchPreference', { value })}>Prefer {value}</button>)}<button data-preference="equal" aria-pressed={state.search.preference === 'equal'} className={'control mx-auto preference-secondary' + (state.search.preference === 'equal' ? ' selected' : '')} disabled={!state.search.triedA || !state.search.triedB || !!state.search.checkpoint} onClick={() => void command('searchPreference', { value: 'equal' })}>Like both equally</button><button data-preference="neither" className="control mx-auto preference-secondary text-slate-300" disabled={!state.search.triedA || !state.search.triedB || !!state.search.checkpoint} onClick={() => void command('searchNeither')}>Neither · new pair</button></div></div>}
          {state.search.checkpoint && <p className="mt-4 rounded-lg border border-amber-500/60 bg-amber-950/30 p-3 text-sm text-amber-200" role="status"><strong>{state.search.checkpoint === 'cap' ? 'Block complete.' : 'Checkpoint saved.'}</strong> Continue searching?</p>}
          <div className="experiment-actions mt-4"><button className="control justify-self-start" onClick={() => void finishSearch(false)}>Pause search</button><button className="control justify-self-center" disabled={!state.search.triedA || !state.search.triedB} onClick={() => setFavoriteChoiceOpen(true)}>I'm satisfied</button>{state.search.checkpoint ? <button className="control justify-self-end" onClick={async () => { const result = await command<State>('searchContinue'); if (result?.search.active && !result.search.checkpoint) await chooseUnrated(result.search) }}>Continue search</button> : <button className="control justify-self-end" disabled={!state.search.feedbackReady} onClick={() => void next()}>{state.search.pairNumber % 10 === 0 ? 'Continue search' : 'Next pair'}</button>}</div>
          {state.search.error && <p role="alert" className="mt-3 text-red-300">{state.search.error}</p>}
        </> : <><h3 className="text-lg">History</h3><div className="mt-3 max-h-[55vh] space-y-2 overflow-y-auto pr-2">{sessions.length ? sessions.map(session => <div className="rounded-lg border border-slate-700 p-3" key={session.id}><div className="text-sm">{session.text}</div><div className="mt-2 flex gap-2"><button className="control text-xs" onClick={() => void restore(session.id, false)}>Continue</button><button className="control text-xs" disabled={!session.favorite} onClick={() => void restore(session.id, true)}>Use favorite</button></div></div>) : <p className="text-sm text-slate-400">Choose “Find saved” to load session history.</p>}</div></>}</section>
      </div></div>
  ) : undefined

  return <div className="dashboard-wrapper">
    {favoriteChoiceOpen && state?.search.active && <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 p-4"><div className="panel max-w-md p-6" role="dialog" aria-modal="true" aria-label="Choose favorite sound"><h2 className="text-xl">Which sound do you prefer?</h2><p className="my-4 text-sm text-slate-300">Choose the sound to save as your favorite.</p>{state.search.error && <p role="alert" className="mb-4 text-sm text-red-300">{state.search.error}</p>}<div className="flex flex-wrap gap-2"><button className="control" autoFocus onClick={() => setFavoriteChoiceOpen(false)}>Cancel</button><button className="control" onClick={() => void finishSearch(true, 'A')}>Save Sound A</button><button className="control" onClick={() => void finishSearch(true, 'B')}>Save Sound B</button></div></div></div>}
    {closeRequested && <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 p-4"><div className="panel max-w-md p-6" role="dialog" aria-modal="true" aria-label="Close active search"><h2 className="text-xl">Close active search?</h2><p className="my-4 text-sm text-slate-300">Save progress, discard this session, or keep working.</p><div className="flex flex-wrap gap-2"><button className="control" onClick={() => setCloseRequested(false)}>Cancel</button><button className="control" onClick={() => void closeWithSearch(false)}>Save and close</button><button className="control border-red-500" onClick={() => void closeWithSearch(true)}>Discard and close</button></div></div></div>}
    {deleteTarget && <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 p-4"><div className="panel max-w-md p-6" role="dialog" aria-modal="true" aria-label="Delete experiment"><h2 className="text-xl">Delete experiment?</h2><p className="my-4 text-sm text-slate-300">Delete “{deleteTarget.participant} · {deleteTarget.mode}” and all saved comparisons? This cannot be undone.</p>{deleteError && <p role="alert" className="mb-4 text-sm text-red-300">{deleteError}</p>}<div className="flex flex-wrap gap-2"><button className="control" onClick={() => { setDeleteTarget(null); setDeleteError('') }}>Cancel</button><button className="control border-red-500" onClick={() => void deleteExperiment()}>Delete experiment</button></div></div></div>}
    {!state && <div className="min-h-screen p-5 md:p-8"><div className="panel p-8">Connecting to simulator…</div></div>}
    {state && (page === 'dashboard' || page === 'search') && <Dashboard state={state} error={error} onCommand={(name, payload) => { void command(name, payload) }} onPersonalize={() => setPage('search')} onTrace={() => void openTrace()} searchPanel={page === 'search' && state.search.active ? searchPanel : null} />}
      {state && page === 'trace' && <PageShell active="trace" onDashboard={() => setPage('dashboard')} onTrace={() => void openTrace()}>
        {error && <div role="alert" className="mb-4 rounded-lg border border-red-500 bg-red-950 p-3 text-red-200">{error}</div>}
        {state.audioError && <div role="alert" className="mb-4 rounded-lg border border-amber-500 bg-amber-950 p-3 text-amber-100">{state.audioError}</div>}
        <div className="grid gap-5 lg:grid-cols-[300px_1fr]">
          <section className="panel space-y-3 p-5"><h2 className="text-xl">Sound trace</h2>{traceSessions.map(session => <button key={session.id} className="control block w-full text-left" onClick={() => void command<Trace>('traceSession', { id: session.id }).then(data => { setTrace(data); setSelectedCandidate(null); setSelectedAudition({}) })}>{session.participant} · {session.mode}<span className="block text-xs text-slate-400">{session.completed || 0} comparisons</span></button>)}</section>
          <section className="panel p-6">{trace ? <>
            <div className="trace-panel-head"><div><h2 className="text-xl">{trace.participant} · {trace.mode}</h2><p className="mt-1 text-slate-400">{trace.completed} comparisons{trace.skipped_pairs?.length ? ` · ${trace.skipped_pairs.length} skipped pair${trace.skipped_pairs.length === 1 ? '' : 's'}` : ''}</p>{trace.status === 'satisfied' && trace.favorite_slot && <p className="mt-1 text-amber-200">Final favorite: Sound {trace.favorite_slot} · {trace.favorite}</p>}</div><button className="icon-button danger" title={trace.status === 'active' ? 'Pause or finish the active session before deleting' : 'Delete experiment'} aria-label="Delete experiment" disabled={trace.status === 'active'} onClick={() => { setDeleteError(''); setDeleteTarget(trace) }}><img src="/icons/trash.svg" alt="" /></button></div>
            <div className="mt-5 max-h-[62vh] overflow-y-auto pr-2"><TraceFlow comparisons={trace.comparisons} method={trace.learning_method} selectedId={selectedCandidate?.id} onSelect={(candidate, audition) => { setSelectedCandidate(candidate); setSelectedAudition(audition) }} /></div>
            {selectedCandidate && <div className="mt-5 rounded-lg border border-emerald-700 p-4"><div className="flex items-center justify-between"><strong>{selectedCandidate.id}</strong><button className="control" disabled={state.search.active} onClick={() => void command('tracePreview', { sessionId: trace.id, candidateId: selectedCandidate.id })}>Replay</button></div><div className="mt-3 grid grid-cols-2 gap-2 text-xs">{Object.entries(selectedCandidate.controls).map(([name, value]) => <div key={name}>{name}: {number(value, 3)}</div>)}</div><details className="mt-3 text-xs"><summary>Full DSP profile</summary><pre className="mt-2 max-h-40 overflow-auto whitespace-pre-wrap">{JSON.stringify(selectedCandidate.profile, null, 2)}</pre></details><details className="mt-3 text-xs"><summary>Saved audition summary</summary><pre className="mt-2 whitespace-pre-wrap">{JSON.stringify(selectedAudition, null, 2)}</pre></details></div>}
          </> : 'Select a session to inspect.'}</section>
        </div>
      </PageShell>}
      {searchPanel && !state?.search.active && <div className="search-overlay">{searchPanel}</div>}
  </div>
}
