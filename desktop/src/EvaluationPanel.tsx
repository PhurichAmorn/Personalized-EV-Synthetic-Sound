import { useState } from 'react'
import { useT } from './i18n'
import type { DiscoveryCandidate } from './SourceSearch'

type Command = (name: string, payload?: Record<string, unknown>) => Promise<unknown> | void
type View = { session: string; done: boolean; pair: Array<DiscoveryCandidate & { letter: 'A' | 'B' }> }

/** Blind evaluation right after the last pair, before the final sound is revealed (experiment/evaluation.py): the session's baseline and final
 *  sound as Sound A and Sound B. The driver switches freely while driving (as in the session) and rates each 1-7; which one is the final is never shown. */
export default function EvaluationPanel({ onCommand, onAudition, onStop, running, onDone }: { onDone: () => void; onCommand: Command; onAudition: (candidate: DiscoveryCandidate, input: 'driving' | 'simulated') => Promise<boolean | string>; onStop: () => void; running: boolean }) {
  const t = useT()
  const [view, setView] = useState<View | null>(null)
  const [playing, setPlaying] = useState<string | null>(null)
  const [played, setPlayed] = useState<Record<string, boolean>>({})
  const [ratings, setRatings] = useState<Record<string, number>>({})
  const [error, setError] = useState('')
  const run = async (name: string, payload?: Record<string, unknown>) => {
    setError('')
    try { return await onCommand(name, payload) as View | undefined } catch (problem) { setError(problem instanceof Error ? problem.message : String(problem)) }
  }
  const play = async (c: View['pair'][number]) => {
    void run('evaluationPlayed', { letter: c.letter })
    const ready = await onAudition(c, 'driving')
    if (ready === true) { setPlaying(c.letter); setPlayed(p => ({ ...p, [c.letter]: true })) } else setError(typeof ready === 'string' ? ready : 'The sound could not start. Try again.')
  }
  const save = async () => { onStop(); const v = await run('evaluationRate', { ratings }); if (v?.done) onDone() }
  const ready = !!view && view.pair.every(c => played[c.letter] && ratings[c.letter])

  return <div aria-label="Evaluation">
    {error && <p role="alert" className="mb-2 text-sm text-red-300">{error}</p>}
    <h3 className="text-lg">{t('Before you hear your sound: a short blind test')}</h3>
    {!view ? <>
      <p className="mt-1 text-sm text-neutral-400">{t('Switch between Sound A and Sound B while driving, as often as you like, then rate each one.')}</p>
      <button type="button" className="control mt-3" onClick={async () => { onStop(); const v = await run('evaluationStart'); if (v) setView(v) }}>{t('Start the test')}</button>
    </> : <>
      {!running && <p className="mt-1 text-xs text-neutral-400">{t('Start the car first: the sound is rated while driving.')}</p>}
      <p className="mt-3 text-sm text-neutral-300">{t('How much would you like this sound in your car?')}</p>
      {view.pair.map(c => <div key={c.letter} className="mt-3">
        <button type="button" className={'control' + (playing === c.letter ? ' selected' : '')} aria-pressed={playing === c.letter} disabled={!running} onClick={() => void play(c)}><strong>{t('▶ Play Sound {x}', { x: c.letter })}</strong></button>
        <div className="mt-2 flex justify-center gap-2" role="radiogroup" aria-label={t('Sound {x}', { x: c.letter })}>{[1, 2, 3, 4, 5, 6, 7].map(n =>
          <button key={n} type="button" role="radio" aria-checked={ratings[c.letter] === n} className={'control' + (ratings[c.letter] === n ? ' selected' : '')} disabled={!played[c.letter]} onClick={() => setRatings(r => ({ ...r, [c.letter]: n }))}>{n}</button>)}</div>
      </div>)}
      <p className="star-ends"><span>{t('1 Dislike very much')}</span><span>{t('4 Neutral')}</span><span>{t('7 Like very much')}</span></p>
      <button type="button" className="control mt-3" disabled={!ready} onClick={() => void save()}>{t('Save answers')}</button>
    </>}
  </div>
}
