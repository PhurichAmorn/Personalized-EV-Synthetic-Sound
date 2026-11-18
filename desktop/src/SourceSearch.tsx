import { useEffect, useRef, useState } from 'react'
import Confirm from './Confirm'
import type { GranularMode } from './granularPlayer'
import type { SourceRecipe } from './sourceRecipe'
import { describeSound, isLiveRecipe, isTuningRecipe, tooSimilar, type LiveRecipe } from './levels'
import { liveStems } from './voiceCache'
import { playWelcome } from './welcomeSound'
export type DiscoveryCandidate = { id: string; label: string; recipe: SourceRecipe | LiveRecipe; urls: string[]; traces: Partial<Record<GranularMode, string>> }
export type SourceDiscoveryState = { active: boolean; busy: boolean; error: string; completed: number; maxComparisons?: number; pair: DiscoveryCandidate[]; heard: string[]; selected: string | null; finalists?: Array<DiscoveryCandidate & { strength: number; wins: number; games: number; score: number; ratingCount: number }>; stage?: 'discovery' | 'playoff' | 'done'; pairMode?: 'rating' | 'choice'; step?: number; totalSteps?: number; playoffDone?: number; playoffTotal?: number; final: string | null; acceptable?: boolean | null; quarantined: number; checkpoint: boolean }
// Row 1: Prefer A | Prefer B; row 2: Neither | Both good (the grid is two columns).
const ANSWERS = [['A', 'Prefer A'], ['B', 'Prefer B'], ['neither', 'Neither'], ['good', 'Both good']] as const
type Answer = typeof ANSWERS[number][0]
type Command = (name: string, payload?: Record<string, unknown>) => Promise<unknown> | void
export default function SourceSearch({ hidden, discovery, onCommand, onContext, onAudition, onStop, playing, running, activity, mode, onModeChange }: { hidden: boolean; discovery?: SourceDiscoveryState; onCommand: Command; onContext: () => Record<string, unknown>; onAudition: (candidate: DiscoveryCandidate, input: 'driving' | 'simulated') => Promise<boolean | string>; onStop: () => void; playing: boolean; running: boolean; activity: boolean; mode: GranularMode; onModeChange: (mode: GranularMode) => void }) {
  const [audition, setAudition] = useState<string | null>(null)
  const [readyAudition, setReadyAudition] = useState<string | null>(null)
  const auditionSequence = useRef(0)
  const [error, setError] = useState('')
  const [pendingFinal, setPendingFinal] = useState<string | null>(null)
  const [pending, setPending] = useState(false)
  const [ratings, setRatings] = useState<Record<string, number>>({})
  const [choice, setChoice] = useState<Answer | null>(null)
  const [showMore, setShowMore] = useState(false)  // shortlist #4-5
  const [search, setSearch] = useState<'tuning' | 'map'>('tuning')  // which search the next session uses (baseline or sound map)
  const heard = useRef(new Set<string>())
  // What is sounding now, for the label: a sound of this pair, or the pick from the last pair that keeps playing while the next pair builds.
  const [nowPlaying, setNowPlaying] = useState<{ id: string; label: string } | null>(null)
  const [pairReady, setPairReady] = useState<string | null>(null)  // revision whose two sounds are built (buttons wait for both)
  const revision = discovery?.pair.map(c => c.id).join(':')
  // Too-similar pairs: the app measures each new pair and asks the search for another (motion pair excluded: same sound on purpose).
  useEffect(() => {
    const [a, b] = discovery?.pair ?? []
    // Sound-map pairs are checked in the backend on more traits (spectrum, pitch, inharmonicity, roughness, pulsing); this rule sees only the
    // first two, so it would drop FM/noise/grit sounds that differ from the champion exactly where it cannot look.
    if (!discovery?.active || !a || !b || !isTuningRecipe(a.recipe) || !isTuningRecipe(b.recipe) || a.recipe.motion !== b.recipe.motion) return
    if (tooSimilar(a.recipe, b.recipe)) void onCommand('sourceDiscoverySkip', { ids: [a.id, b.id] })
  }, [revision])
  // Build both sounds of a new pair (and the shortlist) in the background, so the first switch is instant too.
  // The podium waits for its three sounds to be built (a loading panel meanwhile), so every ▶ Play works at once; the rest build after.
  const podiumKey = discovery?.finalists?.slice(0, 3).map(c => c.id).join(':') ?? ''
  const [podiumReady, setPodiumReady] = useState('')
  useEffect(() => {
    const finalists = discovery?.finalists ?? [], build = (c: DiscoveryCandidate) => isLiveRecipe(c.recipe) ? liveStems(c.recipe).catch(() => null) : null
    void Promise.all(finalists.slice(0, 3).map(build)).then(() => { setPodiumReady(podiumKey); finalists.slice(3).forEach(build) })
  }, [podiumKey])
  // Both sounds of the pair are built before A/B can be pressed, so a press always plays at once (a late build once left a second, deaf player).
  useEffect(() => {
    const pair = discovery?.pair ?? [], key = revision ?? null
    void Promise.all(pair.map(c => isLiveRecipe(c.recipe) ? liveStems(c.recipe) : null)).catch(() => null).then(() => setPairReady(key))
  }, [revision])
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
    try { const ready = await onAudition(candidate, 'driving'); if (token === auditionSequence.current) { if (ready === true) { setReadyAudition(candidate.id); setNowPlaying({ id: candidate.id, label: `Sound ${discovery?.pair[0]?.id === candidate.id ? 'A' : discovery?.pair[1]?.id === candidate.id ? 'B' : ''}`.trim() }) } else setError(typeof ready === 'string' ? `Candidate audio failed: ${ready}` : 'Candidate audio could not start. Try replaying it.') } }
    catch (problem) { if (token === auditionSequence.current) setError(problem instanceof Error ? problem.message : 'Audition failed.') }
  }
  // Pair 1 asks Rising vs Evolving (same sound), so the session starts with one button.
  const begin = async () => {
    onStop(); if (!running) playWelcome()  // the session starts the car too: same welcome as the START button
    const vehicle = await onCommand('vehicleStart') as { running?: boolean; starting?: boolean } | null
    if (!vehicle?.running && !vehicle?.starting) return
    onModeChange('rise'); await onCommand('sourceDiscoveryStart', { search })
  }
  const feedback = async () => {
    if (!discovery || discovery.pair.length !== 2) return
    setPending(true);onStop();setAudition(null);setNowPlaying(null)
    try { await onCommand('sourceDiscoveryFeedback', { ratings: { A: ratings[discovery.pair[0].id], B: ratings[discovery.pair[1].id] }, context: onContext() }) }
    finally { setPending(false) }
  }
  // Final round and parent-check pairs take a direct choice; other pairs use the 1-7 sliders (kept for both, see pairMode).
  const submitChoice = async () => {
    if (!discovery || discovery.pair.length !== 2 || !choice) return
    // The pick keeps playing while the next pair is prepared, so the listener can keep driving it; Neither stops the sound.
    const pick = choice === 'A' ? discovery.pair[0] : choice === 'B' ? discovery.pair[1] : null
    setPending(true);setAudition(null);auditionSequence.current++
    if (choice === 'neither') { onStop(); setNowPlaying(null) }
    else if (pick) { if (nowPlaying?.id !== pick.id) void onAudition(pick, 'driving'); setNowPlaying({ id: pick.id, label: `Your pick (Sound ${choice})` }) }
    else if (nowPlaying) setNowPlaying({ ...nowPlaying, label: `Previous ${nowPlaying.label}` })
    try { await onCommand(final ? 'sourceDiscoveryPlayoff' : 'sourceDiscoveryFeedback', { choice, context: onContext() }) }
    finally { setPending(false) }
  }
  const final = discovery?.stage === 'playoff'
  const choosing = final || discovery?.pairMode === 'choice'
  const ready = discovery && !choosing && !discovery.busy && discovery.pair.length === 2 && discovery.pair.every(c => ratings[c.id] !== undefined) && !pending
  // Leaving the lab pauses the session: stop a candidate preview so it does not keep playing on the dashboard.
  useEffect(() => { if (hidden && (audition || nowPlaying)) { onStop(); setAudition(null); setNowPlaying(null) } }, [hidden])
  useEffect(() => { if (!playing) setNowPlaying(null) }, [playing])
  const preparing = discovery?.active && (discovery.busy || pairReady !== (revision ?? null))
  return <div hidden={hidden} className="search-content source-search-content" aria-label="Source discovery">
    <section className="panel p-3 source-search-comparison">
      <div className="source-comparison-header"><div className="source-session-summary"><h3 className="text-lg">Broad sound discovery</h3>{discovery && <span>{final ? `Final round ${(discovery.playoffDone ?? 0) + 1} / ${discovery.playoffTotal ?? 6} · ` : ''}{discovery.step ?? discovery.completed} / {discovery.totalSteps ?? 20} comparisons</span>}</div><div className="flex flex-wrap gap-2">{discovery && !discovery.active && <select className="control" aria-label="Search" value={search} onChange={event => setSearch(event.target.value as 'tuning' | 'map')}><option value="tuning">Sound families (baseline)</option><option value="map">Sound map (generated)</option></select>}{discovery && !discovery.active && <button type="button" className="control" disabled={discovery.busy} onClick={() => void begin()}>{discovery.completed ? 'New session' : 'Start session'}</button>}</div></div>
      {!discovery && <p className="mt-3 text-sm text-neutral-400">Restart the app to load source discovery.</p>}
      {error && <p role="alert" className="mt-3 text-sm text-red-300">{error}</p>}
      {discovery && !discovery.active ? <p className="mt-3 text-sm text-neutral-300" role="status">{discovery.finalists?.length ? `Session complete · ${discovery.step ?? discovery.completed} comparisons.${discovery.final ? '' : ' Choose your final sound from your shortlist below.'}` : discovery.completed ? `Session finished after ${discovery.completed} comparisons.` : 'Start a session to compare sources.'}</p> : discovery?.active ? <>
        {nowPlaying && playing && <p className="mt-3 text-sm text-neutral-200" role="status">▶ Now playing: <strong>{nowPlaying.label}</strong></p>}
        {preparing && <p className="loading-note mt-3 text-xs text-neutral-400" role="status"><span className="spinner" aria-hidden="true" />Preparing the next pair…{nowPlaying && playing ? ' Keep driving your pick meanwhile.' : ''}</p>}
        {final && <p className="mt-3 text-sm text-neutral-300" role="status">Final round: your four finalists, compared head to head. Pick the one you prefer.</p>}
        {!discovery.busy && <>
        <div className="source-search-candidates" role="group" aria-label="Source A and B">
          {discovery.pair.map((candidate, index) => <div key={candidate.id} className="source-search-candidate">
            <button type="button" className={'control source-search-listen' + (audition === candidate.id ? ' selected' : '')} disabled={discovery.busy || preparing} aria-pressed={audition === candidate.id} onClick={() => listen(candidate)}><strong>Sound {index === 0 ? 'A' : 'B'}</strong></button>
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
          </div>)}
        </div>
        {choosing ? <div className="source-search-preferences" role="group" aria-label={final ? 'Final round preference' : 'Preference'}>{ANSWERS.map(([value, label]) => <button key={value} type="button" className={'control' + (choice === value ? ' selected' : '')} aria-pressed={choice === value} disabled={pending} onClick={() => setChoice(value)}>{label}</button>)}<button type="button" className="control" disabled={!choice || pending} onClick={() => void submitChoice()}>Save choice · next</button></div>
        : <div className="source-search-preferences"><button type="button" className="control" disabled={!ready} onClick={() => void feedback()}>Next</button></div>}
        </>}
        {discovery.error && <p role="alert" className="mt-3 text-sm text-red-300">{discovery.error} <button type="button" className="control" disabled={discovery.busy} onClick={() => void onCommand('sourceDiscoveryRetry')}>Retry preparation</button></p>}
      </> : null}
    </section>
    {!discovery?.active && !!discovery?.finalists?.length && (discovery.final && discovery.acceptable == null ? <section className="panel p-6 source-search-thanks" aria-label="Last question">
      <h3 className="text-lg">One last question</h3>
      <p className="mt-1 text-sm text-neutral-300">Would you be happy with this sound in your car?</p>
      <div className="mt-4 flex flex-wrap justify-center gap-2"><button type="button" className="control" onClick={() => { const c = discovery.finalists!.find(c => c.id === discovery.final); if (c) void listen(c) }}>▶ Play it again</button>
        {([[true, 'Yes'], [false, 'No']] as const).map(([answer, label]) => <button key={label} type="button" className="control" onClick={() => { onStop(); setAudition(null); void onCommand('sourceDiscoveryAccept', { answer }) }}>{label}</button>)}</div>
    </section> : discovery.final ? <section className="panel p-6 source-search-thanks" aria-label="Final sound saved" role="status">
      <div className="thanks-check" aria-hidden="true">✓</div>
      <h3 className="text-lg">Saved · thank you!</h3>
      <p className="mt-1 text-sm text-neutral-300">Your final sound is #{discovery.finalists.findIndex(c => c.id === discovery.final) + 1} of your ranked sounds. This session is saved in Sound trace.</p>
      <p className="mt-2 text-sm">{describeSound(discovery.finalists.find(c => c.id === discovery.final)?.recipe)}</p>
      <button type="button" className="control mt-4" onClick={() => { const c = discovery.finalists!.find(c => c.id === discovery.final); if (c) void listen(c) }}>Play your final sound</button>
    </section> : podiumReady !== podiumKey ? <section className="panel p-6 source-search-ranking" aria-label="Ranking" role="status">
      <span className="spinner" aria-hidden="true" /><h3 className="text-lg">Ranking your best sounds…</h3>
      <p className="mt-1 text-sm text-neutral-400">Preparing your top three so each one plays at once.</p>
    </section> : <section className="panel p-4 source-search-favourites" aria-label="Ranked finalists">
      <Confetti key={podiumKey} />
      <h3 className="text-lg">Your top three · choose your final sound</h3>
      <p className="mt-1 text-xs text-neutral-400">Ranked by all your choices in this session. The final choice is yours.</p>
      <div className="podium">{[1, 0, 2].filter(rank => discovery.finalists![rank]).map(rank => { const candidate = discovery.finalists![rank]; return <div className={'podium-place place-' + (rank + 1)} key={candidate.id}>
        <div className="podium-card">
          <button type="button" className={'control' + (audition === candidate.id ? ' selected' : '')} aria-pressed={audition === candidate.id} onClick={() => listen(candidate)}>▶ Play</button>
          <small className="podium-describe">{describeSound(candidate.recipe)}</small>
          <small>{candidate.games ? `won ${candidate.wins} of ${candidate.games} choices` : 'not compared yet'}</small>
          <button type="button" className="control podium-choose" onClick={() => setPendingFinal(candidate.id)}>Choose this sound</button>
        </div>
        <div className="podium-step"><b>{rank + 1}</b></div>
      </div> })}</div>
      {discovery.finalists.length > 3 && (showMore ? <div className="mt-4 space-y-2">{discovery.finalists.slice(3).map((candidate, index) => <div className="source-favourite-row" key={candidate.id}>
        <b>#{index + 4}</b>
        <button type="button" className={'control' + (audition === candidate.id ? ' selected' : '')} aria-pressed={audition === candidate.id} onClick={() => listen(candidate)}>▶ Play</button>
        <small className="text-neutral-400">{describeSound(candidate.recipe)} · {candidate.games ? `won ${candidate.wins} of ${candidate.games} choices` : 'not compared yet'}</small>
        <button type="button" className="control" onClick={() => setPendingFinal(candidate.id)}>Choose this sound</button>
      </div>)}</div> : <button type="button" className="control mt-4" onClick={() => setShowMore(true)}>Show more ({discovery.finalists.length - 3})</button>)}
    </section>)}
    {pendingFinal && <Confirm title="Are you sure this is your final sound?" text={<>You picked #{discovery!.finalists!.findIndex(c => c.id === pendingFinal) + 1}. It will be saved as the result of this session.</>}>
      <button type="button" className="control" autoFocus onClick={() => setPendingFinal(null)}>Go back</button><button type="button" className="control" onClick={() => { const id = pendingFinal; setPendingFinal(null); onStop(); setAudition(null); void onCommand('sourceDiscoveryFinish', { id }) }}>Yes, save it</button>
    </Confirm>}
  </div>
}

/** A short burst of confetti over the podium, once per podium; pure CSS, gone after 4 s (none with reduced motion). */
function Confetti() {
  const [on, setOn] = useState(true)
  useEffect(() => { const timer = window.setTimeout(() => setOn(false), 4000); return () => window.clearTimeout(timer) }, [])
  if (!on) return null
  const colours = ['#f5c542', '#4fc3f7', '#ef5350', '#66bb6a', '#ab47bc', '#ffa726']
  return <div className="confetti" aria-hidden="true">{Array.from({ length: 60 }, (_, i) => <i key={i} style={{ left: `${(i * 37) % 100}%`, background: colours[i % colours.length],
    animationDelay: `${(i % 12) * .08}s`, animationDuration: `${2.2 + (i % 5) * .3}s`, transform: `rotate(${i * 29}deg)` }} />)}</div>
}
