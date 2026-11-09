import { useEffect, useRef, useState } from 'react'
import type { GranularMode } from './granularPlayer'
import type { SourceRecipe } from './sourceRecipe'
export type DiscoveryCandidate = { id: string; label: string; recipe: SourceRecipe; urls: string[]; traces: Partial<Record<GranularMode, string>>; note?: string }
export type SourceDiscoveryState = { active: boolean; busy: boolean; error: string; completed: number; maxComparisons?: number; pair: DiscoveryCandidate[]; heard: string[]; selected: string | null; favourites: DiscoveryCandidate[]; finalists?: Array<DiscoveryCandidate & { strength: number; wins: number; games: number; score: number; ratingCount: number }>; stage?: 'discovery' | 'playoff' | 'done'; step?: number; totalSteps?: number; playoffDone?: number; playoffTotal?: number; final: string | null; quarantined: number; checkpoint: boolean }
type Command = (name: string, payload?: Record<string, unknown>) => Promise<unknown> | void
export default function SourceSearch({ hidden, discovery, onCommand, onContext, onAudition, onStop, playing, running, activity, mode, onModeChange }: { hidden: boolean; discovery?: SourceDiscoveryState; onCommand: Command; onContext: () => Record<string, unknown>; onAudition: (candidate: DiscoveryCandidate, input: 'driving' | 'simulated') => Promise<boolean | string>; onStop: () => void; playing: boolean; running: boolean; activity: boolean; mode: GranularMode; onModeChange: (mode: GranularMode) => void }) {
  const [audition, setAudition] = useState<string | null>(null)
  const [readyAudition, setReadyAudition] = useState<string | null>(null)
  const auditionSequence = useRef(0)
  const [error, setError] = useState('')
  const [showShortlist, setShowShortlist] = useState(false)
  const [shortlist, setShortlist] = useState<string[]>([])
  const [restartConfirm, setRestartConfirm] = useState(false)
  const [finishConfirm, setFinishConfirm] = useState(false)
  const [pending, setPending] = useState(false)
  const [ratings, setRatings] = useState<Record<string, number>>({})
  const [choice, setChoice] = useState<'A' | 'B' | 'equal' | null>(null)
  const heard = useRef(new Set<string>())
  const revision = discovery?.pair.map(c => c.id).join(':')
  useEffect(() => { auditionSequence.current++; heard.current.clear(); setAudition(null); setReadyAudition(null); setRatings({}); setChoice(null) }, [revision, mode])
  useEffect(() => {
    if (!audition || readyAudition !== audition || !playing || hidden || !discovery?.active || (!running || !activity) || heard.current.has(audition)) return
    const timer = window.setTimeout(() => {
      const context = onContext()
      if (context.candidateId !== audition || Number(context.volume) <= .001) return
      heard.current.add(audition); void onCommand('sourceDiscoveryHeard', { id: audition, context })
    }, 1200)
    return () => window.clearTimeout(timer)
  }, [audition, readyAudition, playing, hidden, running, activity, mode, discovery?.active])
  const listen = async (candidate: DiscoveryCandidate) => {
    const token = ++auditionSequence.current; heard.current.delete(candidate.id); setAudition(candidate.id); setReadyAudition(null); setError('')
    try { const ready = await onAudition(candidate, 'driving'); if (token === auditionSequence.current) { if (ready === true) setReadyAudition(candidate.id); else setError(typeof ready === 'string' ? `Candidate audio failed: ${ready}` : 'Candidate audio could not start. Try replaying it.') } }
    catch (problem) { if (token === auditionSequence.current) setError(problem instanceof Error ? problem.message : 'Audition failed.') }
  }
  const begin = async () => {
    onStop(); setShortlist([]); setShowShortlist(false); setRestartConfirm(false)
    const vehicle = await onCommand('vehicleStart') as { running?: boolean; starting?: boolean } | null
    if (!vehicle?.running && !vehicle?.starting) return
    onModeChange('rise'); await onCommand('sourceDiscoveryStart')
  }
  const bookmark = (candidate: DiscoveryCandidate, enabled: boolean) => void onCommand('sourceDiscoveryBookmark', { id: candidate.id, enabled })
  const feedback = async () => {
    if (!discovery || discovery.pair.length !== 2) return
    setPending(true);onStop();setAudition(null)
    try { await onCommand('sourceDiscoveryFeedback', { ratings: { A: ratings[discovery.pair[0].id], B: ratings[discovery.pair[1].id] }, context: onContext() }) }
    finally { setPending(false) }
  }
  const playoff = async () => {
    if (!discovery || discovery.pair.length !== 2 || !choice) return
    setPending(true);onStop();setAudition(null)
    try { await onCommand('sourceDiscoveryPlayoff', { choice, context: onContext() }) }
    finally { setPending(false) }
  }
  const exportSession = async () => {
    setError('')
    try {
      const result = await onCommand('sourceDiscoveryExport')
      if (!result || typeof result !== 'object') throw Error('Could not export this trial.')
      const url = URL.createObjectURL(new Blob([JSON.stringify({ ...result, shortlist, export_context: onContext() }, null, 2)], { type: 'application/json' }))
      const a = document.createElement('a');a.href = url;a.download = 'ev-source-discovery.json';a.click()
      window.setTimeout(() => URL.revokeObjectURL(url), 1000)
    } catch (problem) { setError(problem instanceof Error ? problem.message : 'Export failed.') }
  }
  const final = discovery?.stage === 'playoff'
  const ready = discovery && !final && !discovery.busy && discovery.pair.length === 2 && discovery.pair.every(c => ratings[c.id] !== undefined) && !pending
  const saved = new Set(discovery?.favourites.map(c => c.id))
  // Leaving the lab pauses the session: stop a candidate preview so it does not keep playing on the dashboard.
  useEffect(() => { if (hidden && audition) { onStop(); setAudition(null) } }, [hidden])
  return <div hidden={hidden} className="search-content source-search-content" aria-label="Source discovery">
    <section className="panel p-4 source-search-comparison">
      <div className="source-comparison-header"><div className="source-session-summary"><h3 className="text-lg">Broad sound discovery</h3>{discovery && <span>{final ? `Final round ${(discovery.playoffDone ?? 0) + 1} / ${discovery.playoffTotal ?? 6} · ` : ''}{discovery.step ?? discovery.completed} / {discovery.totalSteps ?? 20} comparisons</span>}</div><div className="flex flex-wrap gap-2">{discovery && !discovery.active && <button type="button" className="control" disabled={discovery.busy} onClick={() => { if (discovery.completed || discovery.favourites.length) setRestartConfirm(true); else begin() }}>{discovery.completed || discovery.favourites.length ? 'New session' : 'Start session'}</button>}{discovery?.active && <button type="button" className="control" onClick={() => setFinishConfirm(true)}>Finish</button>}<button type="button" className="control" disabled={!discovery?.completed && !discovery?.favourites.length} onClick={() => void exportSession()}>Export</button></div></div>
      {!discovery && <p className="mt-3 text-sm text-slate-400">Restart the app to load source discovery.</p>}
      {finishConfirm && discovery?.active && <div className="mt-3 space-y-3" role="alert"><p className="text-sm">Finish now? You are at step {discovery.step ?? discovery.completed} of {discovery.totalSteps ?? 20}. The remaining pairs are skipped and the finalists come only from what you have rated so far.</p><div className="flex flex-wrap gap-2"><button type="button" className="control" autoFocus onClick={() => setFinishConfirm(false)}>Keep going</button><button type="button" className="control" onClick={() => { setFinishConfirm(false); onStop(); setAudition(null); void onCommand('sourceDiscoveryFinish') }}>Finish now</button></div></div>}
      {restartConfirm && <div className="mt-3 space-y-3"><p className="text-sm">Export before clearing this session.</p><div className="flex flex-wrap gap-2"><button type="button" className="control" onClick={() => void exportSession()}>Export current trial</button><button type="button" className="control" onClick={begin}>Start new and clear</button><button type="button" className="control" onClick={() => setRestartConfirm(false)}>Cancel</button></div></div>}
      {error && <p role="alert" className="mt-3 text-sm text-red-300">{error}</p>}
      {discovery && !discovery.active ? <p className="mt-3 text-sm text-slate-300" role="status">{discovery.finalists?.length ? `Session complete · ${discovery.step ?? discovery.completed} comparisons. Choose your favorite from the ranked finalists below.` : discovery.completed ? `Session finished after ${discovery.completed} comparisons.` : 'Start a session to compare sources.'}</p> : discovery?.active ? <>
        {discovery.busy && <p className="mt-3 text-xs text-slate-400" role="status">Preparing and checking the next pair…</p>}
        {final && <p className="mt-3 text-sm text-slate-300" role="status">Final round: your four finalists, compared head to head. Pick the one you prefer.</p>}
        <div className="source-search-candidates" role="group" aria-label="Source A and B">
          {discovery.pair.map((candidate, index) => <div key={candidate.id} className="source-search-candidate">
            <button type="button" className={'control source-search-listen' + (audition === candidate.id ? ' selected' : '')} disabled={discovery.busy} aria-pressed={audition === candidate.id} onClick={() => listen(candidate)}><strong>Sound {index === 0 ? 'A' : 'B'}</strong><small>{candidate.label}</small></button>
            <button type="button" className="source-favourite-star" aria-label={saved.has(candidate.id) ? 'Remove favourite' : 'Save favourite'} title={saved.has(candidate.id) ? 'Remove favourite' : 'Save favourite'} aria-pressed={saved.has(candidate.id)} onClick={() => bookmark(candidate, !saved.has(candidate.id))}><svg viewBox="0 0 24 24" aria-hidden="true"><path d="m12 3 2.8 5.7 6.3.9-4.6 4.5 1.1 6.3-5.6-3-5.6 3 1.1-6.3L2.9 9.6l6.3-.9L12 3Z" /></svg></button>
            {!final && <div className="source-rating" role="group" aria-label={`Rate sound ${index === 0 ? 'A' : 'B'} from 1 to 7`}><span>Your rating · 1 strongly dislike · 4 neutral · 7 strongly like</span><div>{[1,2,3,4,5,6,7].map(value => <button key={value} type="button" className={'control' + (ratings[candidate.id] === value ? ' selected' : '')} aria-pressed={ratings[candidate.id] === value} onClick={() => setRatings(current => ({ ...current, [candidate.id]: value }))}>{value}</button>)}</div></div>}
            <details className="text-xs text-slate-400"><summary>Source recipe</summary><pre className="source-recipe-json">{JSON.stringify(candidate.recipe, null, 2)}</pre></details>
          </div>)}
        </div>
        {final ? <div className="source-search-preferences" role="group" aria-label="Final round preference">{(['A', 'equal', 'B'] as const).map(value => <button key={value} type="button" className={'control' + (choice === value ? ' selected' : '')} aria-pressed={choice === value} disabled={pending} onClick={() => setChoice(value)}>{value === 'equal' ? 'Like both equally' : `Prefer ${value}`}</button>)}<button type="button" className="control" disabled={!choice || pending} onClick={() => void playoff()}>Save choice · next</button></div>
        : <div className="source-search-preferences"><button type="button" className="control" disabled={!ready} onClick={() => void feedback()}>Save ratings · next pair</button></div>}
        {discovery.error && <p role="alert" className="mt-3 text-sm text-red-300">{discovery.error} <button type="button" className="control" disabled={discovery.busy} onClick={() => void onCommand('sourceDiscoveryRetry')}>Retry preparation</button></p>}
      </> : null}
    </section>
    {!discovery?.active && !!discovery?.finalists?.length && <section className="panel p-4 source-search-favourites" aria-label="Ranked finalists"><h3 className="text-lg">Finalists · choose your favorite</h3><p className="mt-1 text-xs text-slate-400">Ordered by your final-round choices (Bradley-Terry); ratings only break ties. Final choice is yours.</p>{discovery.finalists.map((candidate, index) => <div className="source-favourite-row" key={candidate.id}><button type="button" className="control" onClick={() => listen(candidate)}>Replay · {candidate.label}</button><span>#{index + 1} · {candidate.games ? `${candidate.wins} of ${candidate.games} wins` : 'final round skipped · ranked by ratings'}</span><button type="button" className="control" onClick={() => { onStop(); void onCommand('sourceDiscoveryFinish', { id: candidate.id }) }}>{discovery.final === candidate.id ? 'Your final choice' : 'Choose this sound'}</button></div>)}</section>}
    {!!discovery?.favourites.length && <section className="panel p-4 source-search-favourites">
      <h3 className="text-lg">Favourites · {discovery.favourites.length}</h3>
      <label className="mt-3 flex items-center gap-2 text-sm"><input type="checkbox" checked={showShortlist} onChange={event => setShowShortlist(event.target.checked)} />Show shortlist only</label>
      {discovery.favourites.filter(candidate => !showShortlist || shortlist.includes(candidate.id)).map(candidate => <div key={candidate.id} className="source-favourite-row">
        <button type="button" className="control" onClick={() => listen(candidate)}>Replay · {candidate.label}</button>
        <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={shortlist.includes(candidate.id)} onChange={event => setShortlist(current => event.target.checked ? [...current, candidate.id] : current.filter(id => id !== candidate.id))} />Shortlist</label>
        <input className="control" aria-label={`Note for ${candidate.label}`} placeholder="Optional note" maxLength={300} defaultValue={candidate.note ?? ''} onBlur={event => void onCommand('sourceDiscoveryBookmark', { id: candidate.id, enabled: true, note: event.target.value })} />
        <button type="button" className="control" onClick={() => { bookmark(candidate, false); setShortlist(current => current.filter(id => id !== candidate.id)) }}>Remove</button>
      </div>)}
      <p className="mt-3 text-xs text-slate-400">{shortlist.length} shortlisted · Export to keep your choices. Nothing auto-saves.</p>
    </section>}
  </div>
}
