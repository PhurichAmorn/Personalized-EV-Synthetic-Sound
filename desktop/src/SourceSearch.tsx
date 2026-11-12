import { useEffect, useRef, useState } from 'react'
import type { GranularMode } from './granularPlayer'
import type { SourceRecipe } from './sourceRecipe'
export type DiscoveryCandidate = { id: string; label: string; recipe: SourceRecipe; urls: string[]; traces: Partial<Record<GranularMode, string>> }
export type SourceDiscoveryState = { active: boolean; busy: boolean; error: string; completed: number; maxComparisons?: number; pair: DiscoveryCandidate[]; heard: string[]; selected: string | null; finalists?: Array<DiscoveryCandidate & { strength: number; wins: number; games: number; score: number; ratingCount: number }>; stage?: 'discovery' | 'playoff' | 'done'; pairMode?: 'rating' | 'choice'; step?: number; totalSteps?: number; playoffDone?: number; playoffTotal?: number; final: string | null; quarantined: number; checkpoint: boolean }
type Command = (name: string, payload?: Record<string, unknown>) => Promise<unknown> | void
export default function SourceSearch({ hidden, discovery, onCommand, onContext, onAudition, onStop, playing, running, activity, mode, onModeChange }: { hidden: boolean; discovery?: SourceDiscoveryState; onCommand: Command; onContext: () => Record<string, unknown>; onAudition: (candidate: DiscoveryCandidate, input: 'driving' | 'simulated') => Promise<boolean | string>; onStop: () => void; playing: boolean; running: boolean; activity: boolean; mode: GranularMode; onModeChange: (mode: GranularMode) => void }) {
  const [audition, setAudition] = useState<string | null>(null)
  const [readyAudition, setReadyAudition] = useState<string | null>(null)
  const auditionSequence = useRef(0)
  const [error, setError] = useState('')
  const [finishConfirm, setFinishConfirm] = useState(false)
  const [pendingFinal, setPendingFinal] = useState<string | null>(null)
  const [pending, setPending] = useState(false)
  const [ratings, setRatings] = useState<Record<string, number>>({})
  const [choice, setChoice] = useState<'A' | 'B' | 'equal' | null>(null)
  const [showMore, setShowMore] = useState(false)  // shortlist #4-5
  const heard = useRef(new Set<string>())
  const revision = discovery?.pair.map(c => c.id).join(':')
  useEffect(() => { auditionSequence.current++; heard.current.clear(); setAudition(null); setReadyAudition(null); setRatings({}); setChoice(null); setShowMore(false) }, [revision, mode])
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
    onStop()
    const vehicle = await onCommand('vehicleStart') as { running?: boolean; starting?: boolean } | null
    if (!vehicle?.running && !vehicle?.starting) return
    onModeChange('rise'); await onCommand('sourceDiscoveryStart')
  }
  const feedback = async () => {
    if (!discovery || discovery.pair.length !== 2) return
    setPending(true);onStop();setAudition(null)
    try { await onCommand('sourceDiscoveryFeedback', { ratings: { A: ratings[discovery.pair[0].id], B: ratings[discovery.pair[1].id] }, context: onContext() }) }
    finally { setPending(false) }
  }
  // Final round and parent-check pairs take a direct choice; other pairs use the 1-7 sliders (kept for both, see pairMode).
  const submitChoice = async () => {
    if (!discovery || discovery.pair.length !== 2 || !choice) return
    setPending(true);onStop();setAudition(null)
    try { await onCommand(final ? 'sourceDiscoveryPlayoff' : 'sourceDiscoveryFeedback', { choice, context: onContext() }) }
    finally { setPending(false) }
  }
  const final = discovery?.stage === 'playoff'
  const choosing = final || discovery?.pairMode === 'choice'
  const ready = discovery && !choosing && !discovery.busy && discovery.pair.length === 2 && discovery.pair.every(c => ratings[c.id] !== undefined) && !pending
  // Leaving the lab pauses the session: stop a candidate preview so it does not keep playing on the dashboard.
  useEffect(() => { if (hidden && audition) { onStop(); setAudition(null) } }, [hidden])
  return <div hidden={hidden} className="search-content source-search-content" aria-label="Source discovery">
    <section className="panel p-4 source-search-comparison">
      <div className="source-comparison-header"><div className="source-session-summary"><h3 className="text-lg">Broad sound discovery</h3>{discovery && <span>{final ? `Final round ${(discovery.playoffDone ?? 0) + 1} / ${discovery.playoffTotal ?? 6} · ` : ''}{discovery.step ?? discovery.completed} / {discovery.totalSteps ?? 20} comparisons</span>}</div><div className="flex flex-wrap gap-2">{discovery && !discovery.active && <button type="button" className="control" disabled={discovery.busy} onClick={begin}>{discovery.completed ? 'New session' : 'Start session'}</button>}{discovery?.active && <button type="button" className="control" onClick={() => setFinishConfirm(true)}>Finish</button>}</div></div>
      {!discovery && <p className="mt-3 text-sm text-neutral-400">Restart the app to load source discovery.</p>}
      {finishConfirm && discovery?.active && <div className="mt-3 space-y-3" role="alert"><p className="text-sm">Finish now? You are at step {discovery.step ?? discovery.completed} of {discovery.totalSteps ?? 20}. The remaining pairs are skipped and the finalists come only from what you have rated so far.</p><div className="flex flex-wrap gap-2"><button type="button" className="control" autoFocus onClick={() => setFinishConfirm(false)}>Keep going</button><button type="button" className="control" onClick={() => { setFinishConfirm(false); onStop(); setAudition(null); void onCommand('sourceDiscoveryFinish') }}>Finish now</button></div></div>}
      {error && <p role="alert" className="mt-3 text-sm text-red-300">{error}</p>}
      {discovery && !discovery.active ? <p className="mt-3 text-sm text-neutral-300" role="status">{discovery.finalists?.length ? `Session complete · ${discovery.step ?? discovery.completed} comparisons.${discovery.final ? '' : ' Choose your final sound from your top four below.'}` : discovery.completed ? `Session finished after ${discovery.completed} comparisons.` : 'Start a session to compare sources.'}</p> : discovery?.active ? <>
        {discovery.busy && <p className="loading-note mt-3 text-xs text-neutral-400" role="status"><span className="spinner" aria-hidden="true" />Preparing and checking the next pair…</p>}
        {final && <p className="mt-3 text-sm text-neutral-300" role="status">Final round: your four finalists, compared head to head. Pick the one you prefer.</p>}
        {!discovery.busy && <>
        <div className="source-search-candidates" role="group" aria-label="Source A and B">
          {discovery.pair.map((candidate, index) => <div key={candidate.id} className="source-search-candidate">
            <button type="button" className={'control source-search-listen' + (audition === candidate.id ? ' selected' : '')} disabled={discovery.busy} aria-pressed={audition === candidate.id} onClick={() => listen(candidate)}><strong>Sound {index === 0 ? 'A' : 'B'}</strong></button>
            {!choosing && (() => {
              // One-line like/dislike slider, stored as 1-7. Unrated until touched: clicking or a key press on the neutral start position also counts.
              const value = ratings[candidate.id], set = (next: number) => setRatings(current => ({ ...current, [candidate.id]: next }))
              return <label className={'source-rating' + (value === undefined ? ' unset' : '')}>
                <span aria-hidden="true">Dislike</span>
                <input type="range" min={1} max={7} step={1} value={value ?? 4} aria-label={`Rate sound ${index === 0 ? 'A' : 'B'}: 1 strongly dislike, 4 neutral, 7 strongly like`} aria-valuetext={value === undefined ? 'Not rated' : String(value)}
                  onChange={event => set(Number(event.currentTarget.value))} onPointerUp={event => set(Number(event.currentTarget.value))} onKeyUp={event => set(Number(event.currentTarget.value))} />
                <span aria-hidden="true">Like</span>
                <output>{value ?? '–'}</output>
              </label>
            })()}
            <details className="text-xs text-neutral-400"><summary>Source recipe</summary><pre className="source-recipe-json">{JSON.stringify(candidate.recipe, null, 2)}</pre></details>
          </div>)}
        </div>
        {choosing ? <div className="source-search-preferences" role="group" aria-label={final ? 'Final round preference' : 'Preference'}>{(['A', 'equal', 'B'] as const).map(value => <button key={value} type="button" className={'control' + (choice === value ? ' selected' : '')} aria-pressed={choice === value} disabled={pending} onClick={() => setChoice(value)}>{value === 'equal' ? 'Like both equally' : `Prefer ${value}`}</button>)}<button type="button" className="control" disabled={!choice || pending} onClick={() => void submitChoice()}>Save choice · next</button></div>
        : <div className="source-search-preferences"><button type="button" className="control" disabled={!ready} onClick={() => void feedback()}>Next</button></div>}
        </>}
        {discovery.error && <p role="alert" className="mt-3 text-sm text-red-300">{discovery.error} <button type="button" className="control" disabled={discovery.busy} onClick={() => void onCommand('sourceDiscoveryRetry')}>Retry preparation</button></p>}
      </> : null}
    </section>
    {!discovery?.active && !!discovery?.finalists?.length && (discovery.final ? <section className="panel p-6 source-search-thanks" aria-label="Final sound saved" role="status">
      <div className="thanks-check" aria-hidden="true">✓</div>
      <h3 className="text-lg">Saved · thank you!</h3>
      <p className="mt-1 text-sm text-neutral-300">Your final sound is #{discovery.finalists.findIndex(c => c.id === discovery.final) + 1} of your ranked sounds. This session is saved in Sound trace.</p>
      <button type="button" className="control mt-4" onClick={() => { const c = discovery.finalists!.find(c => c.id === discovery.final); if (c) void listen(c) }}>Play your final sound</button>
    </section> : <section className="panel p-4 source-search-favourites" aria-label="Ranked finalists">
      <h3 className="text-lg">Your top three · choose your final sound</h3>
      <p className="mt-1 text-xs text-neutral-400">Ranked by all your choices in this session. The final choice is yours.</p>
      <div className="podium">{[1, 0, 2].filter(rank => discovery.finalists![rank]).map(rank => { const candidate = discovery.finalists![rank]; return <div className={'podium-place place-' + (rank + 1)} key={candidate.id}>
        <div className="podium-card">
          <button type="button" className={'control' + (audition === candidate.id ? ' selected' : '')} aria-pressed={audition === candidate.id} onClick={() => listen(candidate)}>▶ Play</button>
          <small>{candidate.games ? `won ${candidate.wins} of ${candidate.games} choices` : 'not compared yet'}</small>
          <button type="button" className="control podium-choose" onClick={() => setPendingFinal(candidate.id)}>Choose this sound</button>
        </div>
        <div className="podium-step"><b>{rank + 1}</b></div>
      </div> })}</div>
      {discovery.finalists.length > 3 && (showMore ? <div className="mt-4 space-y-2">{discovery.finalists.slice(3).map((candidate, index) => <div className="source-favourite-row" key={candidate.id}>
        <b>#{index + 4}</b>
        <button type="button" className={'control' + (audition === candidate.id ? ' selected' : '')} aria-pressed={audition === candidate.id} onClick={() => listen(candidate)}>▶ Play</button>
        <small className="text-neutral-400">{candidate.games ? `won ${candidate.wins} of ${candidate.games} choices` : 'not compared yet'}</small>
        <button type="button" className="control" onClick={() => setPendingFinal(candidate.id)}>Choose this sound</button>
      </div>)}</div> : <button type="button" className="control mt-4" onClick={() => setShowMore(true)}>Show more ({discovery.finalists.length - 3})</button>)}
    </section>)}
    {pendingFinal && <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 p-4"><div className="panel max-w-md p-6" role="dialog" aria-modal="true" aria-label="Confirm final sound">
      <h2 className="text-xl">Are you sure this is your final sound?</h2>
      <p className="my-4 text-sm text-neutral-300">You picked #{discovery!.finalists!.findIndex(c => c.id === pendingFinal) + 1}. It will be saved as the result of this session.</p>
      <div className="flex flex-wrap gap-2"><button type="button" className="control" autoFocus onClick={() => setPendingFinal(null)}>Go back</button><button type="button" className="control" onClick={() => { const id = pendingFinal; setPendingFinal(null); onStop(); setAudition(null); void onCommand('sourceDiscoveryFinish', { id }) }}>Yes, save it</button></div>
    </div></div>}
  </div>
}
