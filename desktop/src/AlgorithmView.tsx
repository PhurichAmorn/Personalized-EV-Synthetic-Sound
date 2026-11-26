import { useState } from 'react'
import { useT } from './i18n'

// The Sound trace's "how the search worked" section: which approach ran, how each pair was chosen, what the model learned, and where in
// the sound space the session went. It reads only what the session export already holds; older sessions without block sounds show the approach only.
type Blocks = { top: string; pitch: number; brightness: number }
type Cand = { label?: string; recipe?: unknown; origin?: { kind?: string; summary?: string } }
const blocksOf = (c?: Cand) => (c?.recipe as { blocks?: Blocks } | undefined)?.blocks
export type AlgorithmSession = {
  policy?: string; final: string | null
  history: { pair: string[]; choice?: string; winner?: string | null }[]
  candidates: Record<string, Cand>
  preference_model?: { feature_weights?: Record<string, number>; feature_sd?: Record<string, number> }
}

const APPROACHES: [string, string, string][] = [  // [policy prefix, name, how it picks pairs]
  ['source-blocks-v1-random', 'Building blocks · random challengers (control)', 'The same session, but the challengers come in random order: no model picks them.'],
  ['source-blocks-v1-robust', 'Building blocks · robust champion', 'Bayesian Bradley-Terry model and Thompson sampling. The champion is the best sound by the answers so far, not the last winner.'],
  ['source-blocks-v1-pbo', 'Building blocks · PBO model', 'Challengers are ordered by expected utility under a Gaussian-process preference model. The winner stays.'],
  ['source-blocks-v1-duel', 'Building blocks · duel (no champion)', 'Two sounds, each the best of one random draw from a Gaussian-process model. Nobody stays.'],
  ['source-blocks-v1', 'Building blocks', 'Bayesian Bradley-Terry model. Thompson sampling picks each challenger, with a bonus for unheard sounds. The winner stays.'],
  ['source-tuning-v1', 'Sound families (baseline)', 'Hand-made sound families with tuning moves and direction learning.'],
  ['source-map-', 'Sound map (generated pool)', 'A generated pool of sounds searched by region.'],
  ['source-open-', 'Open pool (older)', 'An earlier search over a generated pool.'],
  ['source-levels-', 'Level search (older)', 'An earlier search over sound levels.'],
  ['source-style-explore-', 'Base-style exploration (older)', 'An earlier search over base styles.'],
]
const approachOf = (policy = '') => APPROACHES.find(([prefix]) => policy.startsWith(prefix))
const TOP_COLORS: Record<string, string> = { glass: '#6cc4f0', electric: '#f5a742', blocks: '#b58cf0', plain: '#8ed07a', synth: '#f06c9b', bell: '#f0e06c', moody: '#9aa5b1' }
const KIND_COLORS: Record<string, string> = { motion: '#9aa5b1', start: '#8ed07a', challenger: '#6cc4f0', duel: '#b58cf0', tune: '#f5a742', replay: '#f06c9b' }
const KIND_LABELS: Record<string, string> = { motion: 'Motion', start: 'Start', challenger: 'Challenger', duel: 'Duel', tune: 'Tune', replay: 'Replay' }

/** How each pair came about: from the origin of its sounds, and a pair played before is a replay. */
function pairKinds(session: AlgorithmSession): string[] {
  const seen = new Set<string>()
  return session.history.map(row => {
    const key = [...row.pair].sort().join('|'), replay = seen.has(key)
    seen.add(key)
    const kinds = row.pair.map(id => session.candidates[id]?.origin?.kind)
    return replay ? 'replay' : kinds.includes('duel') ? 'duel' : kinds.includes('motion') ? 'motion' : kinds.includes('change') ? 'tune'
      : kinds.includes('broad') ? 'challenger' : 'start'
  })
}

export default function AlgorithmView({ session, onPlay, playingId }: { session: AlgorithmSession; onPlay: (id: string) => void; playingId: string | null }) {
  const t = useT()
  const [step, setStep] = useState(0)  // the pair shown: the map reveals the session up to it
  const approach = approachOf(session.policy)
  const hasBlocks = Object.values(session.candidates).some(blocksOf)
  if (!approach && !hasBlocks) return null
  return <section className="algo-view" aria-label="How the search worked">
    <h3>{t('Approach')}</h3>
    <p className="algo-approach"><strong>{t(approach?.[1] ?? session.policy ?? '')}</strong>{approach && <> · <span>{t(approach[2])}</span></>}</p>
    {hasBlocks && <>
      <Timeline session={session} step={step} onStep={setStep} />
      <Replay session={session} step={step} onStep={setStep} onPlay={onPlay} playingId={playingId} />
      <SoundMap session={session} step={step} />
      <Weights session={session} />
    </>}
  </section>
}

function Timeline({ session, step, onStep }: { session: AlgorithmSession; step: number; onStep: (n: number) => void }) {
  const t = useT(), kinds = pairKinds(session)
  return <div className="algo-block"><h4>{t('How each pair was chosen')}</h4>
    <div className="algo-timeline" role="list">{session.history.map((row, index) => {
      const winnerSide = row.winner ? (row.pair[0] === row.winner ? 'A' : 'B') : row.choice === 'good' ? 'A+B' : row.choice === 'neither' ? '–' : '?'
      return <button type="button" key={index} role="listitem" className={'algo-chip' + (index === step ? ' current' : '')} onClick={() => onStep(index)} title={`${t('Pair {n}', { n: index + 1 })} · ${t(KIND_LABELS[kinds[index]] ?? '')} · ${winnerSide}`}>
        <i style={{ background: KIND_COLORS[kinds[index]] }} /><b>{index + 1}</b><small>{winnerSide}</small></button>
    })}</div>
    <p className="algo-legend">{Object.entries(KIND_LABELS).filter(([k]) => kinds.includes(k)).map(([k, label]) => <span key={k}><i style={{ background: KIND_COLORS[k] }} />{t(label)}</span>)}
      <span className="algo-note">{t('Letter = the side you picked (– = neither)')}</span></p>
  </div>
}

const PITCH_HZ = [47, 59.5, 75, 94.5, 119]
function SoundMap({ session, step }: { session: AlgorithmSession; step: number }) {
  const t = useT()
  const order: string[] = [], firstPair: Record<string, number> = {}
  session.history.forEach((row, index) => { for (const id of row.pair) if (!order.includes(id)) { order.push(id); firstPair[id] = index } })
  const pts = order.flatMap((id, n) => { const b = blocksOf(session.candidates[id]); return b ? [{ id, n: n + 1, b }] : [] })
  if (!pts.length) return null
  const W = 360, H = 220, L = 40, R = 12, T = 10, B = 28
  const lo = Math.min(...pts.map(p => p.b.brightness)) - .05, hi = Math.max(...pts.map(p => p.b.brightness)) + .05
  const x = (pitch: number) => L + (pitch + .5) / 5 * (W - L - R), y = (br: number) => T + (1 - (br - lo) / (hi - lo)) * (H - T - B)
  const used = new Map<string, number>()  // sounds on the same grid cell are nudged apart
  const placed = pts.map(p => { const key = `${p.b.pitch}|${p.b.brightness.toFixed(2)}`, k = used.get(key) ?? 0; used.set(key, k + 1); return { ...p, cx: x(p.b.pitch) + (k % 3 - (k > 0 ? 1 : 0)) * 7, cy: y(p.b.brightness) + Math.floor(k / 3) * 7 } })
  const at = (id: string) => placed.find(p => p.id === id)
  const path = session.history.slice(0, step + 1).flatMap(row => { const p = row.winner ? at(row.winner) : null; return p ? [p] : [] }).filter((p, i, all) => i === 0 || p.id !== all[i - 1].id)
  const tops = [...new Set(placed.map(p => p.b.top))]
  return <div className="algo-block"><h4>{t('Where the session went')}</h4>
    <svg viewBox={`0 0 ${W} ${H}`} className="algo-map" role="img" aria-label={t('Sounds heard by pitch and brightness')}>
      {PITCH_HZ.map((hz, i) => <g key={hz}><line x1={x(i)} x2={x(i)} y1={T} y2={H - B} className="algo-grid" /><text x={x(i)} y={H - 12} className="algo-axis" textAnchor="middle">{hz}</text></g>)}
      <text x={W / 2} y={H - 1} className="algo-axis" textAnchor="middle">{t('pitch (Hz)')}</text>
      <text x={10} y={T + 8} className="algo-axis">{t('brighter')}</text><text x={10} y={H - B - 2} className="algo-axis">{t('softer')}</text>
      {path.length > 1 && <polyline points={path.map(p => `${p.cx},${p.cy}`).join(' ')} className="algo-path" />}
      {placed.map(p => <g key={p.id} opacity={firstPair[p.id] <= step ? 1 : .15}>
        <circle cx={p.cx} cy={p.cy} r={p.id === session.final ? 8 : 6} fill={TOP_COLORS[p.b.top] ?? '#999'} className={session.history[step]?.pair.includes(p.id) ? 'algo-now' : p.id === session.final ? 'algo-final' : ''} />
        <text x={p.cx} y={p.cy + 3} className="algo-dot" textAnchor="middle">{p.n}</text></g>)}
    </svg>
    <p className="algo-legend">{tops.map(top => <span key={top}><i style={{ background: TOP_COLORS[top] ?? '#999' }} />{top}</span>)}
      <span className="algo-note">{t('Number = order heard · line = the winners in turn · yellow ring = the pair shown · white ring = your final sound · faded = not heard yet')}</span></p>
  </div>
}

// Thank-you page: every sound heard as a grey dot, the final sound as one big dot. Nothing else.
export function FinalMap({ session }: { session: AlgorithmSession }) {
  const t = useT(), heard = [...new Set(session.history.flatMap(row => row.pair))]
  const pts = heard.flatMap(id => { const b = blocksOf(session.candidates[id]); return b ? [{ id, b }] : [] })
  const final = pts.find(p => p.id === session.final)
  if (!final) return null
  const W = 360, H = 220, L = 40, R = 12, T = 10, B = 28
  const lo = Math.min(...pts.map(p => p.b.brightness)) - .05, hi = Math.max(...pts.map(p => p.b.brightness)) + .05
  const x = (pitch: number) => L + (pitch + .5) / 5 * (W - L - R), y = (br: number) => T + (1 - (br - lo) / (hi - lo)) * (H - T - B)
  return <div className="algo-block"><h4>{t('Where your sound is')}</h4>
    <svg viewBox={`0 0 ${W} ${H}`} className="algo-map" role="img" aria-label={t('Sounds heard by pitch and brightness')}>
      {PITCH_HZ.map((hz, i) => <g key={hz}><line x1={x(i)} x2={x(i)} y1={T} y2={H - B} className="algo-grid" /><text x={x(i)} y={H - 12} className="algo-axis" textAnchor="middle">{hz}</text></g>)}
      <text x={W / 2} y={H - 1} className="algo-axis" textAnchor="middle">{t('pitch (Hz)')}</text>
      <text x={10} y={T + 8} className="algo-axis">{t('brighter')}</text><text x={10} y={H - B - 2} className="algo-axis">{t('softer')}</text>
      {pts.filter(p => p.id !== final.id).map(p => <circle key={p.id} cx={x(p.b.pitch)} cy={y(p.b.brightness)} r={4} fill="#737373" opacity={.6} />)}
      <circle cx={x(final.b.pitch)} cy={y(final.b.brightness)} r={9} fill="#fbbf24" stroke="#fff" strokeWidth={2} />
    </svg>
    <p className="algo-legend"><span><i style={{ background: '#fbbf24' }} />{t('Your sound')}</span><span><i style={{ background: '#737373' }} />{t('Other sounds you heard')}</span></p>
  </div>
}

function Weights({ session }: { session: AlgorithmSession }) {
  const t = useT(), w = session.preference_model?.feature_weights, sd = session.preference_model?.feature_sd
  if (!w || !sd) return null
  const names = Object.keys(w), span = Math.max(1, ...names.map(n => Math.abs(w[n]) + (sd[n] ?? 0)))
  const ROW = 15, W = 360, mid = 245, scale = 105 / span, H = names.length * ROW + 8
  return <div className="algo-block"><h4>{t('What the model learned')}</h4>
    <svg viewBox={`0 0 ${W} ${H}`} className="algo-weights" role="img" aria-label={t('Learned weight and uncertainty for each sound feature')}>
      <line x1={mid} x2={mid} y1={0} y2={H} className="algo-zero" />
      {names.map((name, i) => { const y = 4 + i * ROW + ROW / 2, v = w[name], s = sd[name] ?? 0
        return <g key={name}><text x={4} y={y + 3} className="algo-axis">{name}</text>
          <line x1={mid + (v - s) * scale} x2={mid + (v + s) * scale} y1={y} y2={y} className="algo-sd" />
          <circle cx={mid + v * scale} cy={y} r={3.5} className={v >= 0 ? 'algo-pos' : 'algo-neg'} /></g> })}
    </svg>
    <p className="algo-legend"><span className="algo-note">{t('Dot = learned weight (right = liked more, left = less). Line = uncertainty: a long line means the model barely heard that setting. Final linear Bradley-Terry model; the PBO and duel sessions pick pairs with a different model.')}</span></p>
  </div>
}

/** Step through the session pair by pair: play each sound and see which one was picked and where it sits on the map. */
function Replay({ session, step, onStep, onPlay, playingId }: { session: AlgorithmSession; step: number; onStep: (n: number) => void; onPlay: (id: string) => void; playingId: string | null }) {
  const t = useT(), row = session.history[step], last = session.history.length - 1
  if (!row) return null
  const side = (id: string, letter: string) => <div className={'algo-side' + (row.winner === id ? ' picked' : '')}>
    <button type="button" className="control" aria-pressed={playingId === id} onClick={() => onPlay(id)}>{playingId === id ? '■ ' : '▶ '}{t('Sound {x}', { x: letter })}</button>
    <span>{row.winner === id ? t('picked') : row.choice === 'good' ? t('also good') : ''}</span>
    <p>{(session.candidates[id]?.label ?? id).replace(/ · /g, ' · ')}</p></div>
  return <div className="algo-block"><h4>{t('Replay the session')}</h4>
    <div className="algo-stepper">
      <button type="button" className="control" disabled={step <= 0} onClick={() => onStep(step - 1)}>◀</button>
      <strong>{t('Pair {n}', { n: step + 1 })} / {session.history.length}</strong>
      <button type="button" className="control" disabled={step >= last} onClick={() => onStep(step + 1)}>▶</button>
      <span className="algo-note">{row.choice === 'neither' ? t('neither liked') : row.choice === 'good' ? t('both good') : ''}</span>
    </div>
    <div className="algo-pair">{side(row.pair[0], 'A')}{row.pair[1] && side(row.pair[1], 'B')}</div>
  </div>
}
