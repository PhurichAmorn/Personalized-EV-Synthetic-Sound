import { useEffect, useState } from 'react'
import type { SourceRecipe } from './sourceRecipe'

type Command = <T = unknown>(name: string, payload?: Record<string, unknown>) => Promise<T | null>
export type HistoryPreview = { session?: string; candidate?: string; status?: 'rendering' | 'ready' | 'error'; url?: string; error?: string }
type Row = { id: string; created: string; completed: number; final: string | null; finalists: number; done: boolean }
type Saved = { id: string; label: string; recipe: SourceRecipe; ratings?: number[]; audio_descriptor?: number[] }
type Session = {
  id: string; created: string; final: string | null
  // rating_source: 'rating-1-7' (legacy and normal pairs) or 'choice' (parent check). Sessions before 2026-11-10 have no rating_source and are 1-7.
  history: { pair: string[]; ratings?: { A: number; B: number }; rating_source?: 'rating-1-7' | 'choice'; choice?: 'A' | 'B' | 'equal'; winner?: string | null; origin_by_candidate?: Record<string, string> }[]
  playoff_history: { pair: string[]; choice: 'A' | 'B' | 'equal'; winner: string | null }[]
  finalists: (Saved & { strength: number; wins: number; games: number; score: number })[]
  candidates: Record<string, Saved>
}
const BANDS = ['<100', '100', '180', '300', '500', '800', '1.2k', '1.8k', '2.6k', '4k', '6.5k', '12k+']
const when = (iso: string) => new Date(iso).toLocaleString([], { dateStyle: 'medium', timeStyle: 'short' }) // the computer's own clock and zone
const short = (id: string) => id.slice(0, 6)

export default function TraceHistory({ command, preview }: { command: Command; preview?: HistoryPreview }) {
  const [rows, setRows] = useState<Row[]>([])
  const [session, setSession] = useState<Session | null>(null)
  const [sound, setSound] = useState<string | null>(null)
  const [confirmDelete, setConfirmDelete] = useState(false)
  const refresh = () => command<Row[]>('historyList').then(list => setRows(list ?? []))
  useEffect(() => { void refresh(); return () => { void command('historyPreviewClear') } }, []) // leaving the screen drops the generated sound
  const open = async (id: string) => {
    setSound(null); setConfirmDelete(false); void command('historyPreviewClear')
    setSession(await command<Session>('historyGet', { id }))
  }
  const expand = (id: string) => { setSound(id); void command('historyPreview', { id: session!.id, candidate: id }) }
  const collapse = () => { setSound(null); void command('historyPreviewClear') }
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
      <button type="button" className="control" aria-pressed={sound === id} onClick={() => sound === id ? collapse() : expand(id)}>{sound === id ? 'Close' : 'Expand'}</button>
    </div>
  }
  return <div className={'history-layout' + (detail ? ' with-detail' : '')}>
    <section className="panel history-list" aria-label="Saved sessions">
      <h2 className="text-xl">Sound trace</h2>
      {rows.length === 0 && <p className="text-sm text-neutral-400">No saved sessions yet. Sound discovery sessions save here automatically.</p>}
      {rows.map(row => <button key={row.id} className={'control history-item' + (session?.id === row.id ? ' selected' : '')} aria-pressed={session?.id === row.id} onClick={() => void open(row.id)}>
        <strong>{when(row.created)}</strong>
        <span>{row.completed} comparisons · {row.final ? 'favorite chosen' : row.done ? 'finalists ranked' : 'in progress'}</span>
      </button>)}
    </section>
    <section className="panel history-trace" aria-label="Session trace">
      {!session ? <p className="text-neutral-400">Select a session to inspect.</p> : <>
        <div className="trace-panel-head"><div><h2 className="text-xl">{when(session.created)}</h2><p className="mt-1 text-neutral-400">{session.history.length} rated pairs · {session.playoff_history.length} final-round pairs</p></div>
          {confirmDelete ? <div className="flex gap-2"><button className="control" onClick={() => setConfirmDelete(false)}>Keep</button><button className="control border-red-500" onClick={() => void remove()}>Delete</button></div>
            : <button className="icon-button danger" title="Delete session" aria-label="Delete session" onClick={() => setConfirmDelete(true)}><img src="/icons/trash.svg" alt="" /></button>}
        </div>
        <div className="history-steps">
          {session.history.map((row, index) => <div className="history-step" key={index}>
            <h3>Pair {index + 1}{row.rating_source === 'choice' ? ` · ${row.choice === 'equal' ? 'liked equally' : `Sound ${row.choice} preferred`}` : ''}</h3>
            {[['A', 0], ['B', 1]].map(([slot, i]) => { const id = row.pair[i as number]; return <div key={slot as string}>{soundRow(id, row.rating_source === 'choice' ? `Sound ${slot}${row.winner === id ? ' · preferred' : ''}` : `Sound ${slot} · rated ${row.ratings?.[slot as 'A' | 'B']}/7`)}{row.origin_by_candidate?.[id] && <p className="text-xs text-neutral-400">{row.origin_by_candidate[id]}</p>}</div> })}
          </div>)}
          {session.playoff_history.map((row, index) => <div className="history-step" key={'p' + index}>
            <h3>Final round {index + 1} · {row.choice === 'equal' ? 'liked equally' : `Sound ${row.choice} preferred`}</h3>
            {row.pair.map((id, i) => <div key={id}>{soundRow(id, `Sound ${'AB'[i]}${row.winner === id ? ' · preferred' : ''}`)}</div>)}
          </div>)}
          {session.finalists.length > 0 && <div className="history-step"><h3>Ranked finalists</h3>
            {session.finalists.map((f, index) => <div key={f.id}>{soundRow(f.id, `#${index + 1}${session.final === f.id ? ' · favorite' : ''} · ${f.wins}/${f.games} wins · mean rating ${f.score.toFixed(1)}`)}</div>)}
          </div>}
        </div>
      </>}
    </section>
    {detail && sound && <aside className="panel history-detail" aria-label="Sound details">
      <div className="trace-panel-head"><h2 className="text-xl">Sound {short(sound)}</h2><button className="control" onClick={collapse}>Close</button></div>
      <h3>Preview</h3>
      {preview?.candidate !== sound || preview.status === 'rendering' || !preview.status ? <p className="loading-note text-sm text-neutral-400" role="status"><span className="spinner" aria-hidden="true" />Generating sound…</p>
        : preview.status === 'error' ? <p className="text-sm text-red-300" role="alert">{preview.error}</p>
        : <audio controls autoPlay src={preview.url} />}
      <p className="text-xs text-neutral-500">Generated on demand and discarded when you close this or leave the page.</p>
      {detail.ratings && <><h3>Ratings</h3><p className="text-sm">{detail.ratings.join(', ')} <span className="text-neutral-400">(1–7)</span></p></>}
      <h3>Parameters</h3>
      {detail.recipe.layers.map((layer, index) => <details key={index} open={index === 0}><summary>{layer.role} · {layer.method} · gain {layer.gain.toFixed(2)}</summary>
        <dl className="history-params">{Object.entries(layer.shape as Record<string, unknown>).filter(([, v]) => typeof v === 'number').map(([k, v]) => <div key={k}><dt>{k}</dt><dd>{(v as number).toFixed(3)}</dd></div>)}</dl>
      </details>)}
      {detail.audio_descriptor && <><h3>Spectrum (energy share by Hz band)</h3>
        <div className="history-bands" role="img" aria-label="Spectral energy by band">{detail.audio_descriptor.map((v, i) => <div key={i}><b style={{ height: `${Math.min(100, v * 250)}%` }} /><small>{BANDS[i]}</small></div>)}</div></>}
    </aside>}
  </div>
}
