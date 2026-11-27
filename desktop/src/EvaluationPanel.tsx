import { useState } from 'react'
import { useT } from './i18n'
import type { DiscoveryCandidate } from './SourceSearch'

type Command = (name: string, payload?: Record<string, unknown>) => Promise<unknown> | void
type View = { session: string; step: number; total: number; done: boolean; letter?: 'A' | 'B'; candidate?: DiscoveryCandidate }

/** Blind evaluation right after the session (experiment/evaluation.py): the session's baseline and final sound, played A-B-A-B while driving,
 *  each play rated 1-7. The driver sees only "Sound A / Sound B"; which one is the final is never shown. */
export default function EvaluationPanel({ onCommand, onAudition, onStop, running }: { onCommand: Command; onAudition: (candidate: DiscoveryCandidate, input: 'driving' | 'simulated') => Promise<boolean | string>; onStop: () => void; running: boolean }) {
  const t = useT()
  const [view, setView] = useState<View | null>(null)
  const [played, setPlayed] = useState(false)
  const [error, setError] = useState('')
  const run = async (name: string, payload?: Record<string, unknown>) => {
    setError('')
    try { const v = await onCommand(name, payload) as View | undefined; if (v) { setView(v); setPlayed(false) } } catch (problem) { setError(problem instanceof Error ? problem.message : String(problem)) }
  }
  const play = async () => {
    if (!view?.candidate) return
    const ready = await onAudition(view.candidate, 'driving')
    if (ready === true) setPlayed(true); else setError(typeof ready === 'string' ? ready : 'The sound could not start. Try again.')
  }
  const rate = (rating: number) => { onStop(); void run('evaluationRate', { rating }) }

  return <div className="mt-4 border-t border-neutral-700 pt-4" aria-label="Evaluation">
    {error && <p role="alert" className="mb-2 text-sm text-red-300">{error}</p>}
    {!view && <>
      <h3 className="text-lg">{t('One more step: a short blind test')}</h3>
      <p className="mt-1 text-sm text-neutral-400">{t('You will hear two sounds, A and B, twice each while driving. Rate each one.')}</p>
      <button type="button" className="control mt-3" onClick={() => { onStop(); void run('evaluationStart') }}>{t('Start the test')}</button>
    </>}
    {view && !view.done && view.candidate && <>
      <p className="text-sm text-neutral-300">{t('Play {n} of {total}', { n: view.step + 1, total: view.total })}</p>
      <button type="button" className="control mt-2" disabled={!running} onClick={() => void play()}><strong>{t('▶ Play Sound {x}', { x: view.letter ?? '' })}</strong></button>
      {!running && <p className="mt-1 text-xs text-neutral-400">{t('Start the car first: the sound is rated while driving.')}</p>}
      <p className="mt-4 text-sm text-neutral-300">{t('How much would you like this sound in your car?')}</p>
      <div className="mt-2 flex gap-2" role="group" aria-label={t('How much would you like this sound in your car?')}>{[1, 2, 3, 4, 5, 6, 7].map(n =>
        <button key={n} type="button" className="control" disabled={!played} onClick={() => rate(n)}>{n}</button>)}</div>
      <p className="star-ends"><span>{t('1 Dislike very much')}</span><span>{t('4 Neutral')}</span><span>{t('7 Like very much')}</span></p>
    </>}
    {view?.done && <p className="text-sm text-neutral-300" role="status">{t('Test saved · thank you!')}</p>}
  </div>
}
