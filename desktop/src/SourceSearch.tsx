import { useEffect, useRef, useState } from 'react'
import Confirm from './Confirm'
import type { GranularMode } from './granularPlayer'
import type { SourceRecipe } from './sourceRecipe'
import { describeSound, isLiveRecipe, isTuningRecipe, tooSimilar, type LiveRecipe } from './levels'
import { liveStems } from './voiceCache'
import { describeBlocks, describeBlocksShort, useLang, useT } from './i18n'
import SoundProfile from './SoundProfile'
import { FinalMap, type AlgorithmSession } from './AlgorithmView'
import { playWelcome } from './welcomeSound'
import { PersonalizeCloseButton } from './PersonalizeClose'
import EvaluationPanel from './EvaluationPanel'
import { SoundGraph } from './OverlayGraphs'
export type DiscoveryCandidate = { id: string; label: string; recipe: SourceRecipe | LiveRecipe; urls: string[]; traces: Partial<Record<GranularMode, string>> }
export type SourceDiscoveryState = { active: boolean; busy: boolean; error: string; completed: number; maxComparisons?: number; pair: DiscoveryCandidate[]; heard: string[]; selected: string | null; finalists?: Array<DiscoveryCandidate & { strength: number; wins: number; games: number; score: number; ratingCount: number }>; stage?: 'discovery' | 'playoff' | 'done'; pairMode?: 'rating' | 'choice'; step?: number; totalSteps?: number; playoffDone?: number; playoffTotal?: number; final: string | null; rating?: number | null; quarantined: number; checkpoint: boolean; policy?: string }
// Row 1: Prefer A | Prefer B; row 2: Neither | Both good (the grid is two columns).
const ANSWERS = [['A', 'Prefer A'], ['B', 'Prefer B'], ['neither', 'Neither'], ['good', 'Both good']] as const
type Answer = typeof ANSWERS[number][0]
type Command = (name: string, payload?: Record<string, unknown>) => Promise<unknown> | void
type SearchKind = 'blocks-guess' | 'blocks'
const SEARCHES: [SearchKind, string][] = [['blocks-guess', 'Best guess'], ['blocks', 'Building blocks (previous)']]  // a button list, not a <select>: the native dropdown popup is unreadable in the BeamNG overlay
export default function SourceSearch({ hidden, discovery, onCommand, onContext, onAudition, onStop, playing, running, activity, mode, onModeChange, analyser }: { analyser: () => AnalyserNode | null; hidden: boolean; discovery?: SourceDiscoveryState; onCommand: Command; onContext: () => Record<string, unknown>; onAudition: (candidate: DiscoveryCandidate, input: 'driving' | 'simulated') => Promise<boolean | string>; onStop: () => void; playing: boolean; running: boolean; activity: boolean; mode: GranularMode; onModeChange: (mode: GranularMode) => void }) {
  const [audition, setAudition] = useState<string | null>(null)
  const [readyAudition, setReadyAudition] = useState<string | null>(null)
  const auditionSequence = useRef(0)
  const [sessionStarting, setSessionStarting] = useState(false)
  const [satisfaction, setSatisfaction] = useState(0), [comment, setComment] = useState('')
  // The last-question stars and comment start empty for every session: clear them when a session starts and once the answers are saved.
  useEffect(() => { if (discovery?.active || discovery?.rating != null) { setSatisfaction(0); setComment('') } }, [discovery?.active, discovery?.rating])
  const [error, setError] = useState('')
  const [pendingFinal, setPendingFinal] = useState<string | null>(null)
  const [pending, setPending] = useState(false)
  const [ratings, setRatings] = useState<Record<string, number>>({})
  const [choice, setChoice] = useState<Answer | null>(null)
  const [showMore, setShowMore] = useState(false)  // shortlist #4-5
  const [search, setSearch] = useState<SearchKind>('blocks-guess')  // which search the next session uses: Best guess is the standard; Building blocks is the previous session
  const heard = useRef(new Set<string>())
  // Highest speed (km/h) reached while each sound of the pair was playing; sent with every answer so the record shows whether the whole range was heard.
  const speedPeaks = useRef<Record<string, number>>({})
  // What is sounding now, for the label: a sound of this pair, or the pick from the last pair that keeps playing while the next pair builds.
  type NowPlaying = { id: string; kind: 'final' | 'sound' | 'pick'; x?: string; previous?: boolean }
  const [nowPlaying, setNowPlaying] = useState<NowPlaying | null>(null)
  const t = useT(), lang = useLang()
  const nowPlayingText = (() => {
    if (!nowPlaying) return ''
    let text = ''
    if (nowPlaying.kind === 'final') text = t('Your sound')
    else if (nowPlaying.kind === 'sound') text = t('Sound {x}', { x: nowPlaying.x ?? '' }).trim()
    else if (nowPlaying.kind === 'pick') text = t('Your pick (Sound {x})', { x: nowPlaying.x ?? '' })
    if (nowPlaying.previous) text = t('Previous {label}', { label: text })
    return text
  })()
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
  useEffect(() => { speedPeaks.current = {} }, [revision])
  useEffect(() => {
    if (!audition || !playing || !discovery?.active) return
    const timer = window.setInterval(() => { const speed = Number(onContext().speedKmh) || 0; speedPeaks.current[audition] = Math.max(speedPeaks.current[audition] ?? 0, speed) }, 250)
    return () => window.clearInterval(timer)
  }, [audition, playing, discovery?.active])
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
    if (discovery?.active && !sessionReady) return
    void onCommand('sourceDiscoveryPlayed', { id: candidate.id })  // every press, for the record (heard() needs driving)
    const token = ++auditionSequence.current; heard.current.delete(candidate.id); setAudition(candidate.id); setReadyAudition(null); setError('')
    try { const ready = await onAudition(candidate, 'driving'); if (token === auditionSequence.current) { if (ready === true) { setReadyAudition(candidate.id); setNowPlaying({ id: candidate.id, kind: 'sound', x: discovery?.pair[0]?.id === candidate.id ? 'A' : discovery?.pair[1]?.id === candidate.id ? 'B' : '' }) } else setError(typeof ready === 'string' ? `Candidate audio failed: ${ready}` : 'Candidate audio could not start. Try replaying it.') } }
    catch (problem) { if (token === auditionSequence.current) setError(problem instanceof Error ? problem.message : 'Audition failed.') }
  }
  // After the session the final sound keeps playing (through the last question and the thank-you), labelled as the driver's sound.
  const playFinal = (candidate: DiscoveryCandidate) => { auditionSequence.current++; if (nowPlaying?.id !== candidate.id || !playing) void onAudition(candidate, 'driving'); setNowPlaying({ id: candidate.id, kind: 'final' }) }
  // Pair 1 asks Rising vs Evolving (same sound), so the session starts with one button.
  const [menuOpen, setMenuOpen] = useState(false)
  const [participant, setParticipant] = useState(false)  // ticked before Start: the saved session is labelled as a real participant's
  const [tipOpen, setTipOpen] = useState(false)  // how to drive: shown once when Start session is clicked, then the session starts
  const [newSession, setNewSession] = useState(false)  // after a finished session only New session shows; clicking it brings back the search list
  const begin = async () => {
    setNewSession(false); setMenuOpen(false); setSessionStarting(true); setError('')
    onStop(); if (!running) playWelcome()  // the session starts the car too: same welcome as the START button
    try {
      const vehicle = await onCommand('vehicleStart') as { running?: boolean; starting?: boolean } | null
      if (vehicle ? (!vehicle.running && !vehicle.starting) : !running) return
      onModeChange('rise'); await onCommand('sourceDiscoveryStart', { search, participant }); setParticipant(false)
    } catch (problem) {
      setError(problem instanceof Error ? problem.message : 'Could not start session.')
    } finally {
      setSessionStarting(false)
    }
  }
  const feedback = async () => {
    if (!discovery || discovery.pair.length !== 2) return
    setPending(true);onStop();setAudition(null);setNowPlaying(null)
    try { await onCommand('sourceDiscoveryFeedback', { ratings: { A: ratings[discovery.pair[0].id], B: ratings[discovery.pair[1].id] }, context: { ...onContext(), speedPeaks: { ...speedPeaks.current } } }) }
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
    else if (pick) { if (nowPlaying?.id !== pick.id) void onAudition(pick, 'driving'); setNowPlaying({ id: pick.id, kind: 'pick', x: choice }) }
    else if (nowPlaying) setNowPlaying({ ...nowPlaying, previous: true })
    try { await onCommand(final ? 'sourceDiscoveryPlayoff' : 'sourceDiscoveryFeedback', { choice, context: { ...onContext(), speedPeaks: { ...speedPeaks.current } } }) }
    finally { setPending(false) }
  }
  const final = discovery?.stage === 'playoff'
  // Best guess session (2026-11-27): no podium (kept in code for the other sessions). After the last pair comes the blind test, then the
  // model's #1 becomes the final sound, then the last questions: the podium labelled the #1 and would bias the blind test.
  const noPodium = discovery?.policy === 'source-blocks-guess-v1'
  // Session finished and answered: the comparison panel turns into the saved screen (no count, one panel, the X moves into it).
  const [route, setRoute] = useState<AlgorithmSession | null>(null)
  const saved = !!discovery && !discovery.active && !newSession && !!discovery.finalists?.length && !!discovery.final && discovery.rating != null
  // No-podium session: after the blind test the final sound is revealed on its own page (confetti, profile, route) before the last questions.
  const [revealed, setRevealed] = useState(false)
  useEffect(() => { if (discovery?.active) setRevealed(false) }, [discovery?.active])
  const revealing = noPodium && !!discovery && !discovery.active && !newSession && !!discovery.final && discovery.rating == null && !revealed
  const finalCandidate = discovery?.finalists?.find(c => c.id === discovery.final)
  useEffect(() => { if (!saved && !revealing) { setRoute(null); return } let live = true; Promise.resolve(onCommand('sourceDiscoveryExport')).then(data => { if (live && data) setRoute(data as AlgorithmSession) }).catch(() => {}); return () => { live = false } }, [saved, revealing])  // eslint-disable-line react-hooks/exhaustive-deps
  const choosing = final || discovery?.pairMode === 'choice'
  const sessionReady = Boolean(
    discovery?.active &&
    !sessionStarting &&
    !discovery.busy &&
    running &&
    discovery.pair?.length === 2 &&
    revision &&
    pairReady === revision
  )
  const ready = discovery && !choosing && !discovery.busy && sessionReady && discovery.pair.length === 2 && discovery.pair.every(c => ratings[c.id] !== undefined) && !pending
  // Leaving the lab pauses the session: stop a candidate preview so it does not keep playing on the dashboard.
  useEffect(() => { if (hidden && (audition || nowPlaying)) { onStop(); setAudition(null); setNowPlaying(null) } }, [hidden])
  useEffect(() => { if (!playing) setNowPlaying(null) }, [playing])
  const preparing = Boolean(
    sessionStarting ||
    (discovery?.active && !sessionReady)
  )
  return <div hidden={hidden} className="search-content source-search-content" aria-label="Source discovery">
    <section className="panel p-3 source-search-comparison">
      <div className="source-comparison-header"><div className="source-session-summary">{discovery && !saved && <span>{final ? t('Final round {n} / {total} · ', { n: (discovery.playoffDone ?? 0) + 1, total: discovery.playoffTotal ?? 6 }) : ''}{t('{n} / {total} comparisons', { n: Math.min((discovery.step ?? discovery.completed) + (discovery.active ? 1 : 0), discovery.totalSteps ?? 20), total: discovery.totalSteps ?? 20 })}</span>}</div><div className="flex flex-wrap items-center gap-2">{discovery && !discovery.active && (!discovery.completed || newSession) && <button type="button" className="control" aria-label="Search" aria-haspopup="listbox" aria-expanded={menuOpen} onClick={() => setMenuOpen(open => !open)} onKeyDown={event => { if (event.key === 'Escape') setMenuOpen(false) }}>{t(SEARCHES.find(([value]) => value === search)?.[1] ?? '')} <span aria-hidden="true">{menuOpen ? '▴' : '▾'}</span></button>}{discovery && !discovery.active && (!discovery.completed || newSession) && <label className="participant-check"><input type="checkbox" checked={participant} disabled={sessionStarting} onChange={e => setParticipant(e.target.checked)} /> {t('Participant session')}</label>}{discovery && ((nowPlaying && playing) || preparing) && <div className="ml-auto flex min-w-0 items-center gap-x-3 whitespace-nowrap">{nowPlaying && playing && <p className="min-w-0 truncate text-sm text-neutral-200" role="status">{t('▶ Now playing:')} <strong>{nowPlayingText}</strong></p>}{preparing && <span className="spinner shrink-0" role="status" aria-label={t('Preparing…')} />}</div>}</div><span className="overlay-only-close"><PersonalizeCloseButton /></span></div>
      {discovery && !discovery.active && (!discovery.completed || newSession) && menuOpen && <ul className="search-dropdown-list" role="listbox" aria-label="Search">{SEARCHES.map(([value, label]) => <li key={value} role="option" aria-selected={search === value}><button type="button" className={search === value ? 'selected' : ''} onClick={() => { setSearch(value); setMenuOpen(false) }}>{t(label)}</button></li>)}</ul>}
      {!discovery && <p className="mt-3 text-sm text-neutral-400">Restart the app to load source discovery.</p>}
      {error && <p role="alert" className="mt-3 text-sm text-red-300">{error}</p>}
      {discovery && !discovery.active && !saved && !newSession && (discovery.finalists?.length || discovery.completed) ? <p className="mt-3 text-sm text-neutral-300" role="status">{newSession ? '' : discovery.finalists?.length ? t('Session complete · {n} comparisons.', { n: discovery.step ?? discovery.completed }) + (discovery.final || noPodium ? '' : t(' Choose your final sound from your shortlist below.')) : discovery.completed ? t('Session finished after {n} comparisons.', { n: discovery.completed }) : ''}</p> : null}
      {saved && <div className="source-search-thanks relative" role="status" aria-label="Final sound saved">
        <div className="thanks-head"><div className="thanks-check" aria-hidden="true">✓</div><h3 className="text-lg">{t('Saved · thank you!')}</h3></div>
        <p className="mt-1 text-xs text-neutral-400">{describeShort(discovery.finalists!.find(c => c.id === discovery.final)?.recipe)}</p>
        <div className="thanks-body">
          <SoundProfile recipe={discovery.finalists!.find(c => c.id === discovery.final)?.recipe} />
          {route && <FinalMap session={route} />}
        </div>
      </div>}
      {discovery?.active ? <>
        {final && <p className="mt-3 text-sm text-neutral-300" role="status">{t('Final round: your four finalists, compared head to head. Pick the one you prefer.')}</p>}
        {!discovery.busy && <>
        <div className="source-search-candidates" role="group" aria-label="Source A and B">
          {discovery.pair.map((candidate, index) => <div key={candidate.id} className="source-search-candidate">
            <button type="button" className={'control source-search-listen' + (audition === candidate.id ? ' selected' : '')} disabled={!sessionReady} aria-pressed={audition === candidate.id} onClick={() => listen(candidate)}><strong>{t('Sound {x}', { x: index === 0 ? 'A' : 'B' })}</strong></button>
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
        {choosing ? <div className="source-search-preferences" role="group" aria-label={final ? 'Final round preference' : 'Preference'}>{ANSWERS.map(([value, label]) => <button key={value} type="button" className={'control' + (choice === value ? ' selected' : '')} aria-pressed={choice === value} disabled={pending || !sessionReady} onClick={() => void submitChoice(value)}>{t(label)}</button>)}</div>
        : <div className="source-search-preferences"><button type="button" className="control" disabled={!ready} onClick={() => void feedback()}>{t('Next')}</button></div>}
        </>}
        {discovery.error && <p role="alert" className="mt-3 text-sm text-red-300">{discovery.error} <button type="button" className="control" disabled={discovery.busy} onClick={() => void onCommand('sourceDiscoveryRetry')}>{t('Retry preparation')}</button></p>}
      </> : null}
      {discovery && !discovery.active && <div className="start-session-row"><button type="button" className="control" disabled={discovery.busy || sessionStarting} onClick={() => discovery.completed && !newSession ? setNewSession(true) : setTipOpen(true)}>{sessionStarting ? t('Starting…') : discovery.completed && !newSession ? t('New session') : t('Start session')}</button></div>}
    </section>
    {!discovery?.active && !newSession && !!discovery?.finalists?.length && (revealing ? <section className="panel p-6 source-search-thanks relative" aria-label="Your sound">
      <Confetti key={discovery.final} />
      <div className="thanks-head"><h3 className="text-lg">{t('This is your sound')}</h3></div>
      <p className="mt-1 text-xs text-neutral-400">{describeShort(finalCandidate?.recipe)}</p>
      <div className="thanks-body">
        <SoundProfile recipe={finalCandidate?.recipe} />
        {route && <FinalMap session={route} />}
      </div>
      <div className="mt-4 w-full max-w-[420px] text-left">{/* live, from the final sound now playing: drive to see it change */}
        <p className="overlay-caption">{t('SOUND')}</p><SoundGraph granular active={playing} view="wave" analyser={analyser} onCommand={onCommand} />
        <p className="overlay-caption mt-2">{t('SPECTROGRAM')}</p><SoundGraph granular active={playing} view="spectrogram" analyser={analyser} onCommand={onCommand} />
      </div>
      <button type="button" className="control mt-4" onClick={() => { if (finalCandidate) playFinal(finalCandidate); setRevealed(true) }}>{t('Continue')}</button>
    </section> : discovery.final && discovery.rating == null ? <section className="panel p-6 source-search-thanks" aria-label="Last question">
      <h3 className="text-lg">{t('A few last questions')}</h3>
      <p className="mt-4 text-sm text-neutral-300">{t('How satisfied are you with this sound?')}</p>
      <div className="star-rating" role="radiogroup" aria-label={t('How satisfied are you with this sound?')}>{[1, 2, 3, 4, 5, 6, 7].map(n => <button key={n} type="button" role="radio" aria-checked={satisfaction === n} aria-label={t('{n} of 7', { n })} className={'star' + (n <= satisfaction ? ' on' : '')} onClick={() => setSatisfaction(n)}>★</button>)}</div>
      <p className="star-ends"><span>{t('Not at all')}</span><span>{t('Extremely')}</span></p>
      <label className="mt-4 block w-full max-w-[340px] text-left text-sm text-neutral-300">{t('How would you describe this sound, and how does it make you feel? What do you like or dislike about it? Was anything in the session confusing, hard to tell apart, or unnecessary, or is there anything you would change? (optional)')}
        <textarea className="last-note" lang="ja" rows={3} maxLength={2000} value={comment} onChange={e => setComment(e.target.value)} />
      </label>
      <button type="button" className="control mt-4" disabled={!satisfaction} onClick={() => void onCommand('sourceDiscoveryRate', { rating: satisfaction, comment })}>{t('Save answers')}</button>
    </section> : discovery.final ? null : noPodium ? <section className="panel p-6 source-search-thanks" aria-label="Blind test">
      <EvaluationPanel onCommand={onCommand} onAudition={onAudition} onStop={onStop} running={running} onDone={() => { const c = discovery.finalists![0]; setAudition(null); playFinal(c); void onCommand('sourceDiscoveryFinish', { id: c.id }) }} />
    </section> : podiumReady !== podiumKey ? <section className="panel p-6 source-search-ranking" aria-label="Ranking" role="status">
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
    {tipOpen && <Confirm title={t('Before you start')} text={t('For each sound, accelerate from 0 to 140 km/h so you hear its whole range before you choose. You can listen to A and B as often as you like.')}>
      <button type="button" className="control" onClick={() => setTipOpen(false)}>{t('Go back')}</button><button type="button" className="control" autoFocus onClick={() => { setTipOpen(false); void begin() }}>{t('Start session')}</button>
    </Confirm>}
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
