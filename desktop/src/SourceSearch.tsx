import { useEffect, useRef, useState } from 'react'
import Confirm from './Confirm'
import type { GranularMode } from './granularPlayer'
import type { SourceRecipe } from './sourceRecipe'
import { describeSound, isLiveRecipe, isTuningRecipe, tooSimilar, type LiveRecipe } from './levels'
import { liveStems } from './voiceCache'
import { describeBlocks, describeBlocksShort, useLang, useT } from './i18n'
import { SoundGraph } from './OverlayGraphs'
import { PersonalizeCloseButton } from './PersonalizeClose'
import SoundProfile from './SoundProfile'
import { playWelcome } from './welcomeSound'
export type DiscoveryCandidate = { id: string; label: string; recipe: SourceRecipe | LiveRecipe; urls: string[]; traces: Partial<Record<GranularMode, string>> }
export type SourceDiscoveryState = { active: boolean; busy: boolean; error: string; completed: number; maxComparisons?: number; pair: DiscoveryCandidate[]; heard: string[]; selected: string | null; finalists?: Array<DiscoveryCandidate & { strength: number; wins: number; games: number; score: number; ratingCount: number }>; stage?: 'discovery' | 'playoff' | 'done'; pairMode?: 'rating' | 'choice'; step?: number; totalSteps?: number; playoffDone?: number; playoffTotal?: number; final: string | null; acceptable?: boolean | null; quarantined: number; checkpoint: boolean }
// Row 1: Prefer A | Prefer B; row 2: Neither | Both good (the grid is two columns).
const ANSWERS = [['A', 'Prefer A'], ['B', 'Prefer B'], ['neither', 'Neither'], ['good', 'Both good']] as const
type Answer = typeof ANSWERS[number][0]
type Command = (name: string, payload?: Record<string, unknown>) => Promise<unknown> | void
type SearchKind = 'tuning' | 'map' | 'blocks' | 'blocks-random' | 'blocks-robust' | 'blocks-pbo' | 'blocks-duel' | 'blocks-infogain'
const SEARCHES: [SearchKind, string][] = [['tuning', 'Sound families (baseline)'], ['map', 'Sound map (generated)'], ['blocks', 'Building blocks'], ['blocks-random', 'Building blocks: random challengers (experimental)'], ['blocks-robust', 'Building blocks: robust champion (experimental)'], ['blocks-pbo', 'Building blocks: PBO model (experimental)'], ['blocks-duel', 'Building blocks: duel, no champion (experimental)'], ['blocks-infogain', 'Building blocks: expected-best challengers (experimental)']]  // a button list, not a <select>: the native dropdown popup is unreadable in the BeamNG overlay
export default function SourceSearch({ hidden, discovery, onCommand, onContext, onAudition, onStop, playing, running, activity, mode, onModeChange, analyser }: { analyser: () => AnalyserNode | null; hidden: boolean; discovery?: SourceDiscoveryState; onCommand: Command; onContext: () => Record<string, unknown>; onAudition: (candidate: DiscoveryCandidate, input: 'driving' | 'simulated') => Promise<boolean | string>; onStop: () => void; playing: boolean; running: boolean; activity: boolean; mode: GranularMode; onModeChange: (mode: GranularMode) => void }) {
  const [audition, setAudition] = useState<string | null>(null)
  const [readyAudition, setReadyAudition] = useState<string | null>(null)
  const auditionSequence = useRef(0)
  const [error, setError] = useState('')
  const [pendingFinal, setPendingFinal] = useState<string | null>(null)
  const [pending, setPending] = useState(false)
  const [ratings, setRatings] = useState<Record<string, number>>({})
  const [choice, setChoice] = useState<Answer | null>(null)
  const [showMore, setShowMore] = useState(false)  // shortlist #4-5
  const [search, setSearch] = useState<SearchKind>('tuning')  // which search the next session uses (baseline or sound map)
  const heard = useRef(new Set<string>())
  // What is sounding now, for the label: a sound of this pair, or the pick from the last pair that keeps playing while the next pair builds.
  const [nowPlaying, setNowPlaying] = useState<{ id: string; label: string } | null>(null)
  const t = useT(), lang = useLang()
  // Plain-words sound description in the chosen language (building blocks), else the English one.
  // Short form for the finished screen: the chart shows pitch, brightness, level and space, so only the part names are written.
  const describeShort = (recipe: unknown) => { const r = recipe as { blocks?: Parameters<typeof describeBlocksShort>[0]; motion?: string } | null; return r?.blocks ? describeBlocksShort(r.blocks, r.motion, lang) : describe(recipe) }
  const describe = (recipe: unknown) => { const r = recipe as { blocks?: Parameters<typeof describeBlocks>[0]; motion?: string } | null; return (r?.blocks && describeBlocks(r.blocks, r.motion, lang)) || describeSound(recipe) }
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
    void onCommand('sourceDiscoveryPlayed', { id: candidate.id })  // every press, for the record (heard() needs driving)
    const token = ++auditionSequence.current; heard.current.delete(candidate.id); setAudition(candidate.id); setReadyAudition(null); setError('')
    try { const ready = await onAudition(candidate, 'driving'); if (token === auditionSequence.current) { if (ready === true) { setReadyAudition(candidate.id); setNowPlaying({ id: candidate.id, label: t('Sound {x}', { x: discovery?.pair[0]?.id === candidate.id ? 'A' : discovery?.pair[1]?.id === candidate.id ? 'B' : '' }).trim() }) } else setError(typeof ready === 'string' ? `Candidate audio failed: ${ready}` : 'Candidate audio could not start. Try replaying it.') } }
    catch (problem) { if (token === auditionSequence.current) setError(problem instanceof Error ? problem.message : 'Audition failed.') }
  }
  // After the session the final sound keeps playing (through the last question and the thank-you), labelled as the driver's sound.
  const playFinal = (candidate: DiscoveryCandidate) => { auditionSequence.current++; if (nowPlaying?.id !== candidate.id || !playing) void onAudition(candidate, 'driving'); setNowPlaying({ id: candidate.id, label: t('Your sound') }) }
  // Pair 1 asks Rising vs Evolving (same sound), so the session starts with one button.
  const [menuOpen, setMenuOpen] = useState(false)
  const [newSession, setNewSession] = useState(false)  // after a finished session only New session shows; clicking it brings back the search list
  const begin = async () => {
    setNewSession(false); setMenuOpen(false)
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
  // One click: an answer is saved at once and the next pair follows (no separate Next button, 2026-11-19).
  const submitChoice = async (choice: Answer) => {
    if (!discovery || discovery.pair.length !== 2 || pending) return
    setChoice(choice)
    // The pick keeps playing while the next pair is prepared, so the listener can keep driving it; Neither stops the sound.
    const pick = choice === 'A' ? discovery.pair[0] : choice === 'B' ? discovery.pair[1] : null
    setPending(true);setAudition(null);auditionSequence.current++
    if (choice === 'neither') { onStop(); setNowPlaying(null) }
    else if (pick) { if (nowPlaying?.id !== pick.id) void onAudition(pick, 'driving'); setNowPlaying({ id: pick.id, label: t('Your pick (Sound {x})', { x: choice }) }) }
    else if (nowPlaying) setNowPlaying({ ...nowPlaying, label: t('Previous {label}', { label: nowPlaying.label }) })
    try { await onCommand(final ? 'sourceDiscoveryPlayoff' : 'sourceDiscoveryFeedback', { choice, context: onContext() }) }
    finally { setPending(false) }
  }
  const final = discovery?.stage === 'playoff'
  // Session finished and answered: the comparison panel turns into the saved screen (no count, one panel, the X moves into it).
  const saved = !!discovery && !discovery.active && !newSession && !!discovery.finalists?.length && !!discovery.final && discovery.acceptable != null
  const choosing = final || discovery?.pairMode === 'choice'
  const ready = discovery && !choosing && !discovery.busy && discovery.pair.length === 2 && discovery.pair.every(c => ratings[c.id] !== undefined) && !pending
  // Leaving the lab pauses the session: stop a candidate preview so it does not keep playing on the dashboard.
  useEffect(() => { if (hidden && (audition || nowPlaying)) { onStop(); setAudition(null); setNowPlaying(null) } }, [hidden])
  useEffect(() => { if (!playing) setNowPlaying(null) }, [playing])
  // After the session the final sound's wave and spectrogram are safe to show (they could bias a rating, so never during one).
  const finalGraphs = <div className="final-graphs">{(['wave', 'spectrogram'] as const).map(view => <SoundGraph key={view} granular active={playing} view={view} analyser={analyser} onCommand={onCommand} />)}</div>
  const preparing = discovery?.active && (discovery.busy || pairReady !== (revision ?? null))
  return <div hidden={hidden} className="search-content source-search-content" aria-label="Source discovery">
    <section className="panel p-3 source-search-comparison">
      <div className="source-comparison-header"><div className="source-session-summary">{discovery && !saved && <span>{final ? t('Final round {n} / {total} · ', { n: (discovery.playoffDone ?? 0) + 1, total: discovery.playoffTotal ?? 6 }) : ''}{t('{n} / {total} comparisons', { n: Math.min((discovery.step ?? discovery.completed) + (discovery.active ? 1 : 0), discovery.totalSteps ?? 20), total: discovery.totalSteps ?? 20 })}</span>}</div><div className="flex flex-wrap items-center gap-2">{discovery && !discovery.active && (!discovery.completed || newSession) && <button type="button" className="control" aria-label="Search" aria-haspopup="listbox" aria-expanded={menuOpen} onClick={() => setMenuOpen(open => !open)} onKeyDown={event => { if (event.key === 'Escape') setMenuOpen(false) }}>{t(SEARCHES.find(([value]) => value === search)?.[1] ?? '')} <span aria-hidden="true">{menuOpen ? '▴' : '▾'}</span></button>}{discovery && !discovery.active && <button type="button" className="control" disabled={discovery.busy} onClick={() => discovery.completed && !newSession ? setNewSession(true) : void begin()}>{discovery.completed && !newSession ? t('New session') : t('Start session')}</button>}{discovery && ((nowPlaying && playing) || preparing) && <div className="ml-auto flex min-w-0 items-center gap-x-3 whitespace-nowrap">{nowPlaying && playing && <p className="min-w-0 truncate text-sm text-neutral-200" role="status">{t('▶ Now playing:')} <strong>{nowPlaying.label}</strong></p>}{preparing && <span className="spinner shrink-0" role="status" aria-label={t('Preparing…')} />}</div>}</div>{!saved && <PersonalizeCloseButton />}</div>
      {discovery && !discovery.active && (!discovery.completed || newSession) && menuOpen && <ul className="search-dropdown-list" role="listbox" aria-label="Search">{SEARCHES.map(([value, label]) => <li key={value} role="option" aria-selected={search === value}><button type="button" className={search === value ? 'selected' : ''} onClick={() => { setSearch(value); setMenuOpen(false) }}>{t(label)}</button></li>)}</ul>}
      {!discovery && <p className="mt-3 text-sm text-neutral-400">Restart the app to load source discovery.</p>}
      {error && <p role="alert" className="mt-3 text-sm text-red-300">{error}</p>}
      {discovery && !discovery.active && !saved ? <p className="mt-3 text-sm text-neutral-300" role="status">{newSession ? t('Start a session to compare sources.') : discovery.finalists?.length ? t('Session complete · {n} comparisons.', { n: discovery.step ?? discovery.completed }) + (discovery.final ? '' : t(' Choose your final sound from your shortlist below.')) : discovery.completed ? t('Session finished after {n} comparisons.', { n: discovery.completed }) : t('Start a session to compare sources.')}</p> : null}
      {saved && <div className="source-search-thanks relative" role="status" aria-label="Final sound saved">
        <span className="thanks-close"><PersonalizeCloseButton /></span>
        <div className="thanks-check" aria-hidden="true">✓</div>
        <h3 className="text-lg">{t('Saved · thank you!')}</h3>
        <p className="mt-1 text-xs text-neutral-400">{describeShort(discovery.finalists!.find(c => c.id === discovery.final)?.recipe)}</p>
        <SoundProfile recipe={discovery.finalists!.find(c => c.id === discovery.final)?.recipe} />
        {!document.documentElement.classList.contains('overlay-window') && finalGraphs}
      </div>}
      {discovery?.active ? <>
        {final && <p className="mt-3 text-sm text-neutral-300" role="status">{t('Final round: your four finalists, compared head to head. Pick the one you prefer.')}</p>}
        {!discovery.busy && <>
        <div className="source-search-candidates" role="group" aria-label="Source A and B">
          {discovery.pair.map((candidate, index) => <div key={candidate.id} className="source-search-candidate">
            <button type="button" className={'control source-search-listen' + (audition === candidate.id ? ' selected' : '')} disabled={discovery.busy || preparing} aria-pressed={audition === candidate.id} onClick={() => listen(candidate)}><strong>{t('Sound {x}', { x: index === 0 ? 'A' : 'B' })}</strong></button>
            {!choosing && (() => {
              // One-line like/dislike slider, stored as 1-7. Unrated until touched: clicking or a key press on the neutral start position also counts.
              const value = ratings[candidate.id], set = (next: number) => setRatings(current => ({ ...current, [candidate.id]: next }))
              return <label className={'source-rating' + (value === undefined ? ' unset' : '')}>
                <span aria-hidden="true">{t('Dislike')}</span>
                <input type="range" min={1} max={7} step={1} value={value ?? 4} aria-label={`Rate sound ${index === 0 ? 'A' : 'B'}: 1 strongly dislike, 4 neutral, 7 strongly like`} aria-valuetext={value === undefined ? 'Not rated' : String(value)}
                  onChange={event => set(Number(event.currentTarget.value))} onPointerUp={event => set(Number(event.currentTarget.value))} onKeyUp={event => set(Number(event.currentTarget.value))} />
                <span aria-hidden="true">{t('Like')}</span>
                <output>{value ?? '–'}</output>
              </label>
            })()}
          </div>)}
        </div>
        {choosing ? <div className="source-search-preferences" role="group" aria-label={final ? 'Final round preference' : 'Preference'}>{ANSWERS.map(([value, label]) => <button key={value} type="button" className={'control' + (choice === value ? ' selected' : '')} aria-pressed={choice === value} disabled={pending || preparing} onClick={() => void submitChoice(value)}>{t(label)}</button>)}</div>
        : <div className="source-search-preferences"><button type="button" className="control" disabled={!ready} onClick={() => void feedback()}>{t('Next')}</button></div>}
        </>}
        {discovery.error && <p role="alert" className="mt-3 text-sm text-red-300">{discovery.error} <button type="button" className="control" disabled={discovery.busy} onClick={() => void onCommand('sourceDiscoveryRetry')}>{t('Retry preparation')}</button></p>}
      </> : null}
    </section>
    {!discovery?.active && !newSession && !!discovery?.finalists?.length && (discovery.final && discovery.acceptable == null ? <section className="panel p-6 source-search-thanks" aria-label="Last question">
      <h3 className="text-lg">{t('One last question')}</h3>
      <p className="mt-1 text-sm text-neutral-300">{t('Would you be happy with this sound in your car?')}</p>
      <div className="mt-4 flex flex-wrap justify-center gap-2">{([[true, 'Yes'], [false, 'No']] as const).map(([answer, label]) => <button key={label} type="button" className="control" onClick={() => void onCommand('sourceDiscoveryAccept', { answer })}>{t(label)}</button>)}</div>
    </section> : discovery.final ? null : podiumReady !== podiumKey ? <section className="panel p-6 source-search-ranking" aria-label="Ranking" role="status">
      <span className="spinner" aria-hidden="true" /><h3 className="text-lg">{t('Ranking your best sounds…')}</h3>
      <p className="mt-1 text-sm text-neutral-400">{t('Preparing your top three so each one plays at once.')}</p>
    </section> : <section className="panel p-4 source-search-favourites" aria-label="Ranked finalists">
      <Confetti key={podiumKey} />
      <h3 className="text-lg">{t('Your top three · choose your final sound')}</h3>
      <p className="mt-1 text-xs text-neutral-400">{t('Ranked by all your choices in this session. The final choice is yours.')}</p>
      <div className="podium">{[1, 0, 2].filter(rank => discovery.finalists![rank]).map(rank => { const candidate = discovery.finalists![rank]; return <div className={'podium-place place-' + (rank + 1)} key={candidate.id}>
        <div className="podium-card">
          <button type="button" className={'control' + (audition === candidate.id ? ' selected' : '')} aria-pressed={audition === candidate.id} onClick={() => listen(candidate)}>{t('▶ Play')}</button>
          <small>{candidate.games ? t('won {w} of {g} choices', { w: candidate.wins ?? 0, g: candidate.games }) : t('not compared yet')}</small>
          <button type="button" className="control podium-choose" onClick={() => setPendingFinal(candidate.id)}>{t('Choose this sound')}</button>
        </div>
        <div className="podium-step"><b>{rank + 1}</b></div>
      </div> })}</div>
      {discovery.finalists.length > 3 && (showMore ? <div className="mt-4 space-y-2">{discovery.finalists.slice(3).map((candidate, index) => <div className="source-favourite-row" key={candidate.id}>
        <b>#{index + 4}</b>
        <button type="button" className={'control' + (audition === candidate.id ? ' selected' : '')} aria-pressed={audition === candidate.id} onClick={() => listen(candidate)}>{t('▶ Play')}</button>
        <small className="text-neutral-400">{candidate.games ? t('won {w} of {g} choices', { w: candidate.wins ?? 0, g: candidate.games }) : t('not compared yet')}</small>
        <button type="button" className="control" onClick={() => setPendingFinal(candidate.id)}>{t('Choose this sound')}</button>
      </div>)}</div> : <button type="button" className="control mt-4" onClick={() => setShowMore(true)}>{t('Show more ({n})', { n: discovery.finalists.length - 3 })}</button>)}
    </section>)}
    {pendingFinal && <Confirm title={t('Are you sure this is your final sound?')} text={t('You picked #{n}. It will be saved as the result of this session.', { n: discovery!.finalists!.findIndex(c => c.id === pendingFinal) + 1 })}>
      <button type="button" className="control" autoFocus onClick={() => setPendingFinal(null)}>{t('Go back')}</button><button type="button" className="control" onClick={() => { const id = pendingFinal, c = discovery!.finalists!.find(c => c.id === id); setPendingFinal(null); setAudition(null); if (c) playFinal(c); void onCommand('sourceDiscoveryFinish', { id }) }}>{t('Yes, save it')}</button>
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
