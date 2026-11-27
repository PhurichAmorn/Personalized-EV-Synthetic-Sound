import { useState } from 'react'
import { useT } from './i18n'
import type { DiscoveryCandidate } from './SourceSearch'

type Command = (name: string, payload?: Record<string, unknown>) => Promise<unknown> | void
type Row = { id: string; created: string; participant: boolean; rated: boolean }
type View = { session: string; step: number; total: number; done: boolean; letter?: 'A' | 'B'; candidate?: DiscoveryCandidate }

/** Blind evaluation after a session (experiment/evaluation.py): the session's baseline and final sound, played A-B-A-B while driving, each play
 *  rated 1-7. The driver sees only "Sound A / Sound B"; which one is the final is never shown. */
export default function EvaluationPanel({ onCommand, onAudition, onStop, running }: { onCommand: Command; onAudition: (candidate: DiscoveryCandidate, input: 'driving' | 'simulated') => Promise<boolean | string>; onStop: () => void; running: boolean }) {
  const t = useT()
  const [rows, setRows] = useState<Row[] | null>(null)
  const [view, setView] = useState<View | null>(null)
  const [played, setPlayed] = useState(false)
  const [error, setError] = useState('')
  const run = async (name: string, payload?: Record<string, unknown>) => {
    setError('')
    try { return await onCommand(name, payload) } catch (problem) { setError(problem instanceof Error ? problem.message : String(problem)); return undefined }
  }
  const open = async () => { const list = await run('evaluationSessions'); if (list) setRows(list as Row[]) }
  const close = () => { onStop(); void run('evaluationCancel'); setView(null); setRows(null); setPlayed(false) }
  const start = async (id: string) => { const v = await run('evaluationStart', { id }); if (v) { setView(v as View); setPlayed(false) } }
  const play = async () => {
    if (!view?.candidate) return
    const ready = await onAudition(view.candidate, 'driving')
    if (ready === true) setPlayed(true); else setError(typeof ready === 'string' ? ready : 'The sound could not start. Try again.')
  }
  const rate = async (rating: number) => { onStop(); const v = await run('evaluationRate', { rating }); if (v) { setView(v as View); setPlayed(false) } }

  if (!rows && !view) return <div className="start-session-row"><button type="button" className="control" onClick={() => void open()}>{t('Evaluation (blind)')}</button></div>
  return <section className="panel p-4 mt-3" aria-label="Evaluation">
    <div className="flex items-center justify-between"><h3 className="text-lg">{t('Evaluation')}</h3><button type="button" className="control" onClick={close}>{t('Close')}</button></div>
    {error && <p role="alert" className="mt-2 text-sm text-red-300">{error}</p>}
    {!view && rows && (rows.length ? <ul className="mt-3 space-y-2">{rows.map(r => <li key={r.id} className="flex items-center gap-3 text-sm">
      <span>{r.created.slice(0, 16).replace('T', ' ')}</span><span className="text-neutral-400">{r.participant ? t('Participant') : t('Test')}{r.rated ? ' · ' + t('already rated') : ''}</span>
      <button type="button" className="control ml-auto" onClick={() => void start(r.id)}>{t('Start')}</button></li>)}</ul>
      : <p className="mt-3 text-sm text-neutral-400">{t('No finished session to evaluate yet (only the Best guess session records a baseline and a final sound).')}</p>)}
    {view && !view.done && view.candidate && <div className="mt-3">
      <p className="text-sm text-neutral-300">{t('Play {n} of {total}', { n: view.step + 1, total: view.total })}</p>
      <button type="button" className="control mt-2" disabled={!running} onClick={() => void play()}><strong>{t('▶ Play Sound {x}', { x: view.letter ?? '' })}</strong></button>
      {!running && <p className="mt-1 text-xs text-neutral-400">{t('Start the car first: the sound is rated while driving.')}</p>}
      <p className="mt-4 text-sm text-neutral-300">{t('How much would you like this sound in your car?')}</p>
      <div className="mt-2 flex gap-2" role="radiogroup" aria-label={t('How much would you like this sound in your car?')}>{[1, 2, 3, 4, 5, 6, 7].map(n =>
        <button key={n} type="button" role="radio" aria-checked={false} className="control" disabled={!played} onClick={() => void rate(n)}>{n}</button>)}</div>
      <p className="star-ends"><span>{t('1 Dislike very much')}</span><span>{t('4 Neutral')}</span><span>{t('7 Like very much')}</span></p>
    </div>}
    {view?.done && <p className="mt-3 text-sm text-neutral-300" role="status">{t('Saved · thank you!')}</p>}
  </section>
}
