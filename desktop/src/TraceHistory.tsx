import { useEffect, useState } from 'react'
import type { SourceRecipe } from './sourceRecipe'
import { liveStems } from './voiceCache'
import { isLiveRecipe, liveSound, type LiveRecipe } from './levels'
import { LabPlayer } from './labEngine'
import { simulatedDrive } from './simulatedDrive'
import { useT, type T } from './i18n'
import AlgorithmView from './AlgorithmView'
import SoundProfile from './SoundProfile'

// Level sounds are built live in the app (no offline render): the trace plays them on the 22 s simulated drive.
const traceLab = new LabPlayer()

type Command = <T = unknown>(name: string, payload?: Record<string, unknown>) => Promise<T | null>
export type HistoryPreview = { session?: string; candidate?: string; status?: 'rendering' | 'ready' | 'error'; url?: string; error?: string }
type Row = { id: string; created: string; completed: number; final: string | null; finalists: number; done: boolean; rating?: number | null; participant?: boolean; starred?: boolean }
type Saved = { id: string; label: string; recipe: SourceRecipe | LiveRecipe; ratings?: number[]; audio_descriptor?: number[]; origin?: { kind?: string; move?: string; motion?: string; summary?: string } }
type Session = {
  id: string; created: string; final: string | null; final_rating?: number | null; participant?: boolean; researcher_note?: string; final_comment?: string
  policy?: string; preference_model?: { feature_weights?: Record<string, number>; feature_sd?: Record<string, number> }
  // rating_source: 'rating-1-7' (legacy and normal pairs) or 'choice' (parent check). Sessions before 2026-11-10 have no rating_source and are 1-7.
  history: { pair: string[]; ratings?: { A: number; B: number }; rating_source?: 'rating-1-7' | 'choice'; choice?: 'A' | 'B' | 'equal' | 'good' | 'neither'; winner?: string | null; origin_by_candidate?: Record<string, string> }[]
  playoff_history: { pair: string[]; choice: 'A' | 'B' | 'equal'; winner: string | null }[]
  finalists: (Saved & { strength: number; wins: number; games: number; score: number })[]
  candidates: Record<string, Saved>
}
const BANDS = ['<100', '100', '180', '300', '500', '800', '1.2k', '1.8k', '2.6k', '4k', '6.5k', '12k+']
const when = (iso: string) => new Date(iso).toLocaleString([], { dateStyle: 'medium', timeStyle: 'short' }) // the computer's own clock and zone
const short = (id: string) => id.slice(0, 6)
// Texture style of a layered sound, as the search groups them (= map_style in experiment/source_search.py).
const STYLES: Record<string, number[]> = { electric: [9, 10, 11], strings: [1, 7, 8], glass: [3, 4], choir: [6], plain: [0, 2] }
function styleOf(recipe: SourceRecipe | LiveRecipe) {
  const voice = (recipe as { voice?: { kind: string; stack?: { layers: number; timbres: number[] } } }).voice
  if (voice?.kind !== 'stack' || !voice.stack) return null
  const layers = voice.stack.timbres.slice(0, voice.stack.layers)
  const count = Object.entries(STYLES).map(([name, family]) => [layers.filter(t => family.includes(t)).length, name] as const).sort((a, b) => b[0] - a[0])
  return 2 * count[0][0] >= layers.length && count[0][0] > count[1][0] ? count[0][1] : 'blend'
}
const OPPOSITE: Record<string, string> = { brighter: 'darker', darker: 'brighter', deeper: 'higher', higher: 'deeper', fuller: 'thinner', thinner: 'fuller', smoother: 'shimmer', shimmer: 'smoother', 'body+': 'body-', 'body-': 'body+' }
/** Why each pair's sounds were played: a returning winner, or where a new sound came from (and, for fine-tune variations, the move
 * credit that led there: a won move +1 and its opposite -1, as the search counts it). */
function pairReasons(session: Session, t: T) {
  const credit: Record<string, number> = {}, out: Record<string, string>[] = []
  let lastWinner: { id: string; pair: number } | null = null
  session.history.forEach((row, index) => {
    const reasons: Record<string, string> = {}
    for (const id of row.pair) {
      const c = session.candidates[id], origin = c?.origin ?? {}, blocks = (c?.recipe as { blocks?: { top: string } } | undefined)?.blocks
      const style = blocks ? blocks.top : c ? styleOf(c.recipe) : null, tag = style ? ` · ${style}` : ''  // block sounds: their own top, not the old sound-map style groups
      if (lastWinner?.id === id) { reasons[id] = t('Your pick from pair {n}, defending', { n: lastWinner.pair }); continue }
      const move = origin.move && origin.move !== 'original' ? origin.move : null
      reasons[id] = origin.kind === 'motion' ? t('Same sound, {motion}', { motion: t(origin.motion === 'evolving' ? 'Evolving' : 'Rising') })
        : origin.kind === 'opening' ? (blocks ? origin.summary ?? t('Opening: typical sound') + tag : t('Opening: typical sound') + tag)
        : origin.kind === 'region' ? t('Styles compete') + tag
        : origin.kind === 'challenger' ? t('Challenger from your leading styles') + tag
        : origin.kind === 'variation' ? (move ? `${t('{move} version of your pick', { move })}${move.split('+').some(m => (credit[m] ?? 0) > 0) ? ` · '${move.split('+').filter(m => (credit[m] ?? 0) > 0).join("', '")}' won before` : ''}` : t('The original of your pick'))
        : origin.summary ?? ''
    }
    out.push(reasons)
    if (row.winner) {
      lastWinner = { id: row.winner, pair: index + 1 }
      for (const id of row.pair) for (const m of (session.candidates[id]?.origin?.move ?? '').split('+').filter(m => m && m !== 'original')) {
        const sign = id === row.winner ? 1 : -1; credit[m] = (credit[m] ?? 0) + sign; if (OPPOSITE[m]) credit[OPPOSITE[m]] = (credit[OPPOSITE[m]] ?? 0) - sign
      }
    }
  })
  return out
}
const isLive = isLiveRecipe  // built and played in the app, not rendered offline
// Source settings shown in the trace: level/tuning base, or a sound-map voice (plain synth or blocks shape + controls).
const settingsOf = (r: LiveRecipe): object => 'base' in r ? r.base : r.voice ? (r.voice.kind === 'blocks' ? { voice: 'blocks', ...r.voice.shape, ...r.voice.controls } : r.voice.kind === 'stack' ? { voice: 'stack', ...r.voice.stack } : r.voice.plain) : r.plain ?? {}

export default function TraceHistory({ command, preview }: { command: Command; preview?: HistoryPreview }) {
  const [rows, setRows] = useState<Row[]>([])
  const t = useT()
  const [session, setSession] = useState<Session | null>(null)
  const [sound, setSound] = useState<string | null>(null)
  const [confirmDelete, setConfirmDelete] = useState(false)
  const refresh = () => command<Row[]>('historyList').then(list => setRows(list ?? []))
  useEffect(() => { void refresh(); return () => { void command('historyPreviewClear') } }, []) // leaving the screen drops the generated sound
  const open = async (id: string) => {
    setSound(null); setConfirmDelete(false); void command('historyPreviewClear')
    setSession(await command<Session>('historyGet', { id }))
  }
  const [livePlaying, setLivePlaying] = useState(false)
  const [playingId, setPlayingId] = useState<string | null>(null)  // the sound playing from the replay
  const stopLive = () => { traceLab.stop(); setLivePlaying(false); setPlayingId(null) }
  useEffect(() => stopLive, [])
  const expand = (id: string) => { stopLive(); setSound(id); if (!isLive(session!.candidates[id]?.recipe)) void command('historyPreview', { id: session!.id, candidate: id }) }
  const collapse = () => { stopLive(); setSound(null); void command('historyPreviewClear') }
  const playLive = (id: string, recipe: LiveRecipe) => {
    const { plain, fx, mode, travel } = liveSound(recipe)
    void traceLab.play(id, liveStems(recipe), fx, plain.rootHz, 'simulated', () => ({ input: undefined, stale: true }), simulatedDrive, mode, travel).then(started => { if (started) { setLivePlaying(true); setPlayingId(id) } })
  }
  const star = async (id: string, value: boolean) => { await command('historyStar', { id, value }); void refresh() }
  const [note, setNote] = useState(''), [editing, setEditing] = useState(false)
  useEffect(() => { setNote(session?.researcher_note ?? ''); setEditing(false) }, [session?.id])
  // Researcher edits of the saved session: the Participant/Test tag and a note (saved when the box loses focus).
  const meta = async (change: { participant?: boolean; note?: string }) => {
    if (!session) return
    await command('historyMeta', { id: session.id, ...change }); setSession({ ...session, ...('note' in change ? { researcher_note: change.note } : change) }); void refresh()
  }
  const starred = !!rows.find(row => row.id === session?.id)?.starred
  const remove = async () => {
    if (!session) return
    await command('historyDelete', { id: session.id })
    setSession(null); setSound(null); setConfirmDelete(false); void command('historyPreviewClear'); void refresh()
  }
  const detail = session && sound ? session.candidates[sound] : null
  // A plain function, not a component: a component defined here is a new type every render and remounts its buttons, which swallowed clicks.
  const soundRow = (id: string, tag: string) => {
    const c = session!.candidates[id]
    return <div className={'history-sound' + (sound === id ? ' open' : '')}>
      <span>{tag}</span><strong>{c ? short(id) : id}</strong>
      <button type="button" className="control" aria-pressed={sound === id} onClick={() => sound === id ? collapse() : expand(id)}>{t(sound === id ? 'Close' : 'Expand')}</button>
    </div>
  }
  return <div className={'history-layout' + (detail ? ' with-detail' : '')}>
    <section className="panel history-list" aria-label="Saved sessions">
      <h2 className="text-xl">{t('Sound trace')}</h2>
      {/* Only finished sessions are listed; unfinished ones stay on disk. */}
      {!rows.some(row => row.final || row.done) && <p className="text-sm text-neutral-400">{t('No saved sessions yet. Sound discovery sessions save here automatically.')}</p>}
      {rows.filter(row => row.final || row.done).map(row => <button key={row.id} className={'control history-item' + (session?.id === row.id ? ' selected' : '')} aria-pressed={session?.id === row.id} onClick={() => void open(row.id)}>
        <strong>{row.participant ? <span className="tag-participant">{t('Participant')}</span> : <span className="tag-test">{t('Test')}</span>}{row.starred && <span className="history-star" aria-label="Starred">★ </span>}{when(row.created)}</strong>
        <span>{t('{n} comparisons · {state}', { n: row.completed, state: t(row.final ? 'favorite chosen' : 'finalists ranked') })}{row.rating != null && ` · ${t('Satisfaction {n}/7', { n: row.rating })}`}</span>
      </button>)}
    </section>
    <section className="panel history-trace" aria-label="Session trace">
      {!session ? <p className="text-neutral-400">{t('Select a session to inspect.')}</p> : <>
        <div className="trace-panel-head"><div><h2 className="text-xl">{when(session.created)}</h2><p className="mt-1 text-neutral-400">{t('{n} rated pairs · {m} final-round pairs', { n: session.history.length, m: session.playoff_history.length })}{session.final_rating != null && ` · ${t('Satisfaction {n}/7', { n: session.final_rating })}`}</p>{session.researcher_note && <p className="mt-1 text-sm text-neutral-300"><strong>{t('Note')}:</strong> {session.researcher_note}</p>}{session.final_comment && <p className="mt-1 text-sm text-neutral-300" lang="ja">{session.final_comment}</p>}</div>
          <div className="flex gap-2">
            <button className="icon-button" aria-pressed={editing} title={t('Edit tag and notes')} aria-label={t('Edit tag and notes')} onClick={() => setEditing(!editing)}>⋯</button>
            <button className={'icon-button star-button' + (starred ? ' on' : '')} aria-pressed={starred} title={t(starred ? 'Starred: kept at the top. Click to unstar.' : 'Star to mark this session as one to keep')} aria-label={t('Star session')} onClick={() => void star(session.id, !starred)}>{starred ? '★' : '☆'}</button>
            {confirmDelete ? <><button className="control" onClick={() => setConfirmDelete(false)}>{t('Keep')}</button><button className="control border-red-500" onClick={() => void remove()}>{t(starred ? 'Delete starred session' : 'Delete')}</button></>
              : <button className="icon-button danger" title={t('Delete session')} aria-label={t('Delete session')} onClick={() => setConfirmDelete(true)}><img src="/icons/trash.svg" alt="" /></button>}
          </div>
        </div>
        {editing && <div className="trace-edit" role="group" aria-label={t('Edit session')}>
          <fieldset><legend>{t('Tag')}</legend>
            {([[true, 'Participant'], [false, 'Test']] as const).map(([value, name]) => <label key={name}><input type="radio" name="session-tag" checked={!!session.participant === value} onChange={() => void meta({ participant: value })} /> <span className={value ? 'tag-participant' : 'tag-test'}>{t(name)}</span></label>)}
          </fieldset>
          <label htmlFor="session-note">{t('Note')}</label>
          <textarea id="session-note" className="session-note" rows={1} aria-label={t('Note')} value={note} onChange={e => setNote(e.target.value)} onBlur={() => { if (note !== (session.researcher_note ?? '')) void meta({ note }) }} />
        </div>}
        <AlgorithmView key={session.id} session={session} playingId={playingId} onPlay={id => { const c = session.candidates[id]; if (playingId === id) stopLive(); else if (c && isLive(c.recipe)) { stopLive(); playLive(id, c.recipe as LiveRecipe) } }} />
        <div className="history-steps history-tree">
          {(() => {
            // Tree: the chosen sound continues down the trunk; the other sound branches off to the side and ends there.
            // A sound that was not the previous pick but wins starts a new trunk segment ("new pick").
            const reasons = pairReasons(session, t)
            return session.history.map((row, index) => {
              const ab = (id: string) => row.pair[0] === id ? 'A' : 'B', label = (id: string) => t('Sound {x}', { x: ab(id) })
              const sound = (id: string, kept: boolean) => <div className={'tree-sound' + (kept ? ' kept' : ' dropped')}>
                {soundRow(id, row.rating_source === 'choice' ? `${label(id)}${kept && row.winner ? t(' · ★ chosen') : ''}` : `${label(id)}${t(' · rated {n}/7', { n: row.ratings?.[ab(id)] ?? '–' })}`)}
                <p className="history-why">{reasons[index][id] || row.origin_by_candidate?.[id]}</p></div>
              const trunk = row.winner ? [row.winner] : row.choice === 'good' ? row.pair : []
              const branch = row.pair.filter(id => !trunk.includes(id))
              const fresh = row.winner && index > 0 && session.history[index - 1].winner !== row.winner
              const answer = t(row.choice === 'neither' ? 'neither liked' : row.choice === 'good' ? 'both good' : row.choice === 'equal' ? 'liked equally' : '')
              return <div className={'tree-node' + (fresh ? ' fresh' : '')} key={index}>
                <h3>{t('Pair {n}', { n: index + 1 })}{fresh ? t(' · new pick') : ''}{answer ? ` · ${answer}` : ''}</h3>
                <div className="tree-row">
                  <div className="tree-trunk">{trunk.map(id => <div key={id}>{sound(id, true)}</div>)}{!trunk.length && <p className="history-why">{t('— no pick —')}</p>}</div>
                  <div className="tree-branch">{branch.map(id => <div key={id}>{sound(id, false)}</div>)}</div>
                </div>
              </div>
            })
          })()}
          {session.playoff_history.map((row, index) => <div className="history-step" key={'p' + index}>
            <h3>{t('Final round {n}', { n: index + 1 })} · {row.choice === 'equal' ? t('liked equally') : t('Sound {x} preferred', { x: row.choice })}</h3>
            {row.pair.map((id, i) => <div key={id}>{soundRow(id, `${t('Sound {x}', { x: 'AB'[i] })}${row.winner === id ? t(' · preferred') : ''}`)}</div>)}
          </div>)}
          {session.finalists.length > 0 && <div className="history-step"><h3>{t('Ranked finalists')}</h3>
            {session.finalists.map((f, index) => <div key={f.id}>{soundRow(f.id, `#${index + 1}${session.final === f.id ? t(' · favorite') : ''} · ${t('{w}/{g} wins · mean rating {r}', { w: f.wins, g: f.games, r: f.score.toFixed(1) })}`)}</div>)}
          </div>}
        </div>
      </>}
    </section>
    {detail && sound && <aside className="panel history-detail" aria-label="Sound details">
      <div className="trace-panel-head"><h2 className="text-xl">{t('Sound {id}', { id: short(sound) })}</h2><button className="control" onClick={collapse}>{t('Close')}</button></div>
      <h3>{t('Preview')}</h3>
      {isLive(detail.recipe) ? <><button type="button" className="control" onClick={() => livePlaying ? stopLive() : playLive(sound, detail.recipe as LiveRecipe)}>{t(livePlaying ? 'Stop' : '▶ Play on the 22 s drive')}</button>
        <h3>{t('Settings')}</h3>
        <dl className="history-params">{[...Object.entries(settingsOf(detail.recipe as LiveRecipe)), ...Object.entries(detail.recipe.fx)].map(([k, v]) => <div key={k}><dt>{k}</dt><dd>{String(v)}</dd></div>)}</dl>
      </> : <>
      {preview?.candidate !== sound || preview.status === 'rendering' || !preview.status ? <p className="loading-note text-sm text-neutral-400" role="status"><span className="spinner" aria-hidden="true" />{t('Generating sound…')}</p>
        : preview.status === 'error' ? <p className="text-sm text-red-300" role="alert">{preview.error}</p>
        : <audio controls autoPlay src={preview.url} />}
      <p className="text-xs text-neutral-500">{t('Generated on demand and discarded when you close this or leave the page.')}</p>
      </>}
      <SoundProfile recipe={detail.recipe} />
      {detail.ratings && <><h3>{t('Ratings')}</h3><p className="text-sm">{detail.ratings.join(', ')} <span className="text-neutral-400">(1–7)</span></p></>}
      {!isLive(detail.recipe) && <h3>{t('Parameters')}</h3>}
      {!isLive(detail.recipe) && detail.recipe.layers.map((layer, index) => <details key={index} open={index === 0}><summary>{layer.role} · {layer.method} · gain {layer.gain.toFixed(2)}</summary>
        <dl className="history-params">{Object.entries(layer.shape as Record<string, unknown>).filter(([, v]) => typeof v === 'number').map(([k, v]) => <div key={k}><dt>{k}</dt><dd>{(v as number).toFixed(3)}</dd></div>)}</dl>
      </details>)}
      {detail.audio_descriptor && <><h3>{t('Spectrum (energy share by Hz band)')}</h3>
        <div className="history-bands" role="img" aria-label="Spectral energy by band">{detail.audio_descriptor.map((v, i) => <div key={i}><b style={{ height: `${Math.min(100, v * 250)}%` }} /><small>{BANDS[i]}</small></div>)}</div></>}
    </aside>}
  </div>
}
