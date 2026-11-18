import { useState } from 'react'
import type { State } from '../App'
import Confirm from '../Confirm'

/* Old GP-preference / evolutionary A/B search (backend: experiment/legacy/live_search.py), kept as a baseline record.
   The app can no longer start one: App renders this only while state.search.active, which nothing sets now. */

export type Search = {
  active: boolean; participant: string; mode: string; learningMethod: string; algorithm: string
  stage: string; pairRecipes: Record<string, string>
  pairNumber: number; selected: string; triedA: boolean; triedB: boolean
  preference: string; preferenceReady: boolean; checkpoint: string; error: string
  ratingA: number; ratingB: number; ratingSources: Record<string, number>; feedbackReady: boolean
}
type SavedSession = { id: string; text: string; favorite: boolean }
type Command = <T = unknown>(name: string, payload?: Record<string, unknown>) => Promise<T | null>

export default function LegacySearch({ state, command, onError, onDone }: { state: State; command: Command; onError: (message: string) => void; onDone: () => void }) {
  const [participant, setParticipant] = useState('')
  const [mode, setMode] = useState('Deep')
  const [method, setMethod] = useState('gp_preference')
  const [sessions, setSessions] = useState<SavedSession[]>([])
  const [favoriteChoiceOpen, setFavoriteChoiceOpen] = useState(false)
  async function startSearch() {
    const result = await command<State>('searchStart', { participant, mode, method })
    if (!result?.search.active) { if (result?.search.error) onError(result.search.error); return }
    await chooseUnrated(result.search)
    if (!result.running) await command('toggle')
  }
  async function restore(id: string, favoriteOnly: boolean) {
    const result = await command<State>('searchRestore', { id, favoriteOnly })
    if (!result || result.search.error) { if (result?.search.error) onError(result.search.error); return }
    if (!favoriteOnly) await chooseUnrated(result.search)
    if (!result.running) await command('toggle')
  }
  async function next() {
    const result = await command<State>('searchNext')
    if (result?.search.active && !result.search.checkpoint && !result.search.error) await chooseUnrated(result.search)
  }
  async function chooseUnrated(search: Search) {
    const slot = search.learningMethod === 'evolutionary' && search.ratingA > 0 && search.ratingB === 0 ? 'B' : 'A'
    await command('searchChoose', { slot })
  }
  async function finishSearch(satisfied: boolean, favoriteSlot = '') {
    const result = await command<State>('searchFinish', { satisfied, favoriteSlot })
    if (result && !result.search.active && !result.search.error) { setFavoriteChoiceOpen(false); onDone() }
  }
  async function refreshSessions() { setSessions(await command<SavedSession[]>('searchSessions', { participant }) || []) }
  return <div className="search-content">
    <p className="text-sm text-neutral-400">{state.search.mode} · Pair {state.search.pairNumber}{state.search.stage ? <> · {state.search.stage}</> : ['gp-feature-v2', 'gp-feature-v3', 'gp-feature-v4'].includes(state.search.algorithm) && <> · {state.search.pairNumber <= 6 ? 'Explore features' : state.search.pairNumber >= 18 && state.search.pairNumber <= 20 ? 'Combine preferred features' : 'Refine preference'}</>}</p>
        <section className="panel space-y-4 p-6"><h3 className="text-lg">Session setup</h3><label className="block"><span className="label">Participant alias</span><input className="control mt-2 w-full" maxLength={80} value={participant} onChange={event => setParticipant(event.target.value)} /></label><label className="block"><span className="label">Starting sound</span><select className="control mt-2 w-full" value={state.search.mode} disabled={state.search.active} onChange={event => setMode(event.target.value)}>{state.soundThemes.map(name => <option key={name}>{name}</option>)}</select></label><label className="block"><span className="label">Method</span><select className="control mt-2 w-full" value={method} onChange={event => setMethod(event.target.value)}><option value="gp_preference">GP preference + BO</option><option value="evolutionary">Evolutionary</option><option value="recipe_preference">Recipe window pilot</option></select></label><div className="flex gap-2"><button className="control" disabled={state.search.active || state.running || state.soundSweepActive} onClick={() => void startSearch()}>New session</button><button className="control" onClick={() => void refreshSessions()}>Find saved</button></div></section>
        <section className="panel p-4">{state.search.active ? <><h3 className="text-lg">A/B comparison</h3>
          {state.search.pairNumber % 20 === 0 && !state.search.checkpoint && <p className="mt-3 rounded-lg border border-neutral-500/60 bg-neutral-950/30 p-3 text-sm text-neutral-200" role="status"><strong>Last pair in this block.</strong> Listen to A and B. If satisfied, save your favorite. Otherwise grade this pair to finish the block.</p>}
          <p className="text-xs text-neutral-400">Hold W or your controller trigger while switching A/B to hear each sound under motion.</p><div className="my-4 grid grid-cols-2 gap-3">{(['A', 'B'] as const).map(slot => <button key={slot} data-sound-slot={slot} className={'control py-8 text-2xl ' + (state.search.selected === slot ? 'selected' : '')} onClick={() => void command('searchChoose', { slot })}>Sound {slot}{state.search.pairRecipes[slot] && <small className="mt-1 block text-xs font-normal">{state.search.pairRecipes[slot]}</small>}{state.search.learningMethod === 'evolutionary' && state.search.ratingSources[slot] > 0 && <small className="mt-1 block text-xs font-normal">Previously heard · score {slot === 'A' ? state.search.ratingA : state.search.ratingB}/7</small>}</button>)}</div>
          {state.search.learningMethod === 'evolutionary' ? <div className="space-y-3">{(['A', 'B'] as const).map(slot => {
            const score = slot === 'A' ? state.search.ratingA : state.search.ratingB
            const source = state.search.ratingSources[slot] || 0
            return <div key={slot}><div className="mb-2 flex items-center justify-between"><span className="label">Sound {slot} · score 1–7</span>{source > 0 && <span className="text-xs text-neutral-200">Score carried from pair {source}; tap to change</span>}</div><div className="preference-scale"><span className="preference-line" />{Array.from({ length: 7 }, (_, index) => index + 1).map(value => <button key={value} data-rating-slot={slot} data-rating-value={value} aria-label={`Sound ${slot} score ${value}`} aria-pressed={score === value} className={'preference-node' + (score === value ? ' selected' : '')} disabled={!(slot === 'A' ? state.search.triedA : state.search.triedB) && !source} onClick={() => void command('searchRate', { slot, value })}>{value}</button>)}</div></div>
          })}{state.search.preference && !(state.search.ratingA && state.search.ratingB) && <p className="text-xs text-neutral-400">This resumed pair has a saved pairwise preference. Next can use it, or score both sounds to replace it.</p>}</div> : <div className="preference-scale-wrap"><div className="label">Which sound do you prefer?</div><div className="mt-2 grid grid-cols-2 gap-2" role="group" aria-label="Sound preference">{(['A', 'B'] as const).map(value => <button key={value} data-preference={value} aria-pressed={state.search.preference === value} className={'control py-3 text-sm' + (state.search.preference === value ? ' selected' : '')} disabled={!state.search.triedA || !state.search.triedB || !!state.search.checkpoint} onClick={() => void command('searchPreference', { value })}>Prefer {value}</button>)}<button data-preference="equal" aria-pressed={state.search.preference === 'equal'} className={'control mx-auto preference-secondary' + (state.search.preference === 'equal' ? ' selected' : '')} disabled={!state.search.triedA || !state.search.triedB || !!state.search.checkpoint} onClick={() => void command('searchPreference', { value: 'equal' })}>Like both equally</button><button data-preference="neither" className="control mx-auto preference-secondary text-neutral-300" disabled={!state.search.triedA || !state.search.triedB || !!state.search.checkpoint} onClick={() => void command('searchNeither')}>Neither · new pair</button></div></div>}
          {state.search.checkpoint && <p className="mt-4 rounded-lg border border-neutral-500/60 bg-neutral-950/30 p-3 text-sm text-neutral-200" role="status"><strong>{state.search.checkpoint === 'cap' ? 'Block complete.' : 'Checkpoint saved.'}</strong> Continue searching?</p>}
          <div className="experiment-actions mt-4"><button className="control justify-self-start" onClick={() => void finishSearch(false)}>Pause search</button><button className="control justify-self-center" disabled={!state.search.triedA || !state.search.triedB} onClick={() => setFavoriteChoiceOpen(true)}>I'm satisfied</button>{state.search.checkpoint ? <button className="control justify-self-end" onClick={async () => { const result = await command<State>('searchContinue'); if (result?.search.active && !result.search.checkpoint) await chooseUnrated(result.search) }}>Continue search</button> : <button className="control justify-self-end" disabled={!state.search.feedbackReady} onClick={() => void next()}>{state.search.pairNumber % 20 === 0 ? 'Finish block' : 'Next pair'}</button>}</div>
          {state.search.error && <p role="alert" className="mt-3 text-red-300">{state.search.error}</p>}
        </> : <><h3 className="text-lg">History</h3><div className="mt-3 max-h-[55vh] space-y-2 overflow-y-auto pr-2">{sessions.length ? sessions.map(session => <div className="rounded-lg border border-neutral-700 p-3" key={session.id}><div className="text-sm">{session.text}</div><div className="mt-2 flex gap-2"><button className="control text-xs" onClick={() => void restore(session.id, false)}>Continue</button><button className="control text-xs" disabled={!session.favorite} onClick={() => void restore(session.id, true)}>Use favorite</button></div></div>) : <p className="text-sm text-neutral-400">Choose “Find saved” to load session history.</p>}</div></>}</section>
      {favoriteChoiceOpen && <Confirm title="Which sound do you prefer?" text={<>Choose the sound to save as your favorite.{state.search.error && <strong role="alert" className="mt-2 block text-red-300">{state.search.error}</strong>}</>}>
        <button className="control" autoFocus onClick={() => setFavoriteChoiceOpen(false)}>Cancel</button><button className="control" onClick={() => void finishSearch(true, 'A')}>Save Sound A</button><button className="control" onClick={() => void finishSearch(true, 'B')}>Save Sound B</button>
      </Confirm>}
  </div>
}

/** Close with an old search open: save (pause) or discard it first. True when the window may close. */
export async function closeLegacySearch(command: Command, discard: boolean) {
  if (discard) return !!await command<boolean>('searchDiscard')
  const result = await command<State>('searchFinish', { satisfied: false })
  return !!result && !result.search.active && !result.search.error
}
