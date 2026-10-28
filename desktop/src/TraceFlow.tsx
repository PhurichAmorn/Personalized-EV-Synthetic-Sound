export type Candidate = {
  id: string
  controls: Record<string, number>
  profile: Record<string, unknown>
  parents?: string[]
  kind?: string
}

export type Comparison = {
  number: number
  pair: { A: Candidate; B: Candidate }
  preference: string
  winner: string | null
  ratings?: Record<string, number>
  rating_sources?: Record<string, number>
  auditions: Record<string, Record<string, number>>
  current?: boolean
  final_choice?: string
}

const slots = ['A', 'B'] as const

function chosenSlot(row: Comparison) {
  return slots.find(slot => row.pair[slot].id === row.winner)
}

function scoreLabel(row: Comparison, method?: string) {
  if (row.final_choice) return `Final favorite · Sound ${row.final_choice}`
  const a = row.ratings?.A
  const b = row.ratings?.B
  const choice = row.preference === 'A' ? 'A preferred' : row.preference === 'B' ? 'B preferred' : row.preference === 'equal' ? 'Liked equally' : ''
  if (row.current) return choice ? `Current pair · ${choice} pending` : a || b ? `Current pair · A ${a || '—'}/7 · B ${b || '—'}/7` : method === 'evolutionary' ? 'Current pair · awaiting scores' : 'Current pair · awaiting choice'
  const chosen = chosenSlot(row)
  if (choice) return `${choice}${row.preference === 'equal' && chosen ? ` · ${chosen} retained` : ''}`
  if (a && b) return `A ${a}/7 · B ${b}/7${chosen ? ` · ${chosen} retained` : ''}`
  return chosen ? `${chosen} retained · score unavailable` : 'No score recorded'
}

function origin(candidate: Candidate, parentId: string) {
  if (candidate.kind === 'gp-proposal') return 'GP proposal · model score not saved'
  if (candidate.kind === 'feature-contrast') return 'Opening feature comparison'
  if (candidate.kind === 'feature-mix') return 'Combination of preferred features'
  if (candidate.kind === 'mutation' && candidate.parents?.includes(parentId)) return 'Mutation of selected sound'
  if (candidate.kind === 'exploration') return 'Broad exploration · controls redrawn'
  if (candidate.kind === 'initial' || candidate.kind === 'mode-seed') return 'Opening candidate'
  return candidate.kind?.replaceAll('-', ' ') || 'Candidate origin not recorded'
}

function shift(from: Candidate, to: Candidate) {
  return Object.entries(to.controls)
    .filter(([name, value]) => Number.isFinite(value) && Number.isFinite(from.controls[name]))
    .map(([name, value]) => ({ name, delta: value - from.controls[name] }))
    .filter(item => Math.abs(item.delta) >= .005)
    .sort((a, b) => Math.abs(b.delta) - Math.abs(a.delta))
    .slice(0, 4)
}

function Link({ previous, next, method }: { previous: Comparison[]; next: Comparison; method?: string }) {
  const last = previous[previous.length - 1]
  const retained = slots.map(slot => ({ slot, candidate: next.pair[slot], source: [...previous].reverse().find(row => row.winner === next.pair[slot].id) }))
    .find(item => item.source)
  const winner = retained?.candidate
  const challenger = retained && next.pair[retained.slot === 'A' ? 'B' : 'A']
  const changes = winner && challenger ? shift(winner, challenger) : []
  const explanation = retained?.source?.number === last.number
    ? `${winner?.id} continues as ${retained.slot}; ${challenger?.id} enters the next pair.`
    : retained?.source
      ? `${winner?.id}, selected in pair ${retained.source.number}, returns as ${retained.slot}; ${challenger?.id} enters this lineage.`
      : method === 'evolutionary' && next.number <= 3
        ? 'Separate opening pair; the three opening winners form independent lineages.'
        : 'No recorded winner or parent link leads directly into this pair.'

  return <div className="trace-link" aria-label={`Transition to pair ${next.number}`}>
    <div className="trace-link-note">
      <div>{explanation}</div>
      {winner && challenger && <>
        <small>{origin(challenger, winner.id)}</small>
        {changes.length > 0 && <div className="trace-shifts" aria-label="Largest control changes relative to the selected sound">
          {changes.map(({ name, delta }) => <span key={name} className={delta > 0 ? 'up' : 'down'}>{name} {delta > 0 ? '+' : '−'}{Math.abs(delta * 100).toFixed(0)} pts</span>)}
        </div>}
      </>}
    </div>
  </div>
}

export default function TraceFlow({ comparisons, method, selectedId, onSelect }: {
  comparisons: Comparison[]
  method?: string
  selectedId?: string
  onSelect: (candidate: Candidate, audition: Record<string, number>) => void
}) {
  if (!comparisons.length) return <p className="text-slate-400">No comparisons recorded yet.</p>
  return <>
    <p className="trace-legend">{method === 'evolutionary' ? 'Evolutionary: score each sound from 1 to 7.' : 'GP: Prefer A, Like both equally, or Prefer B. Neither skips both sounds.'} Green marks the retained sound. Green + and red − show higher or lower saved control values, not sound quality.</p>
    <ol className="trace-flow" aria-label="Comparison flow">
      {comparisons.map((row, index) => <li className="trace-step" key={row.number}>
        <div className="trace-step-heading"><span className="trace-step-number">{row.number}</span><strong>Pair {row.number}</strong><span>{scoreLabel(row, method)}</span></div>
        <div className="trace-pair">
          {slots.map(slot => {
            const candidate = row.pair[slot]
            const retained = row.winner === candidate.id
            const firstSeen = comparisons.slice(0, index).find(previous => slots.some(previousSlot => previous.pair[previousSlot].id === candidate.id))
            return <button key={slot} type="button" className={'trace-candidate' + (retained ? ' winner' : '')} aria-pressed={selectedId === candidate.id} onClick={() => onSelect(candidate, row.auditions[slot] || {})}>
              <span className="trace-candidate-label">Sound {slot}{row.final_choice === slot ? <em>Final favorite</em> : retained && <em>{row.preference === 'equal' ? 'Retained after tie' : 'Selected'}</em>}</span>
              <strong>{candidate.id}</strong>
              {!!row.ratings?.[slot] && <span className="trace-candidate-score">Score {row.ratings[slot]}/7{row.rating_sources?.[slot] ? ` · carried from pair ${row.rating_sources[slot]}` : ''}</span>}
              <small>{firstSeen ? `Same saved sound as pair ${firstSeen.number}` : candidate.kind?.replaceAll('-', ' ') || 'Saved sound'} · Inspect details</small>
            </button>
          })}
        </div>
        {index < comparisons.length - 1 && <Link previous={comparisons.slice(0, index + 1)} next={comparisons[index + 1]} method={method} />}
      </li>)}
    </ol>
  </>
}
