import { useEffect, useRef, useState } from 'react'
import { SOURCE_FAMILIES, type SourceFamily, type SourceControls } from './sourceDesigner'
import { RECIPE_DEFAULT_CONTROLS } from './sourceRecipe'
// Same starting settings as the search's reference recipes, so Sound Lab plays what the search and the clips use.
const DEFAULT_SOURCE_CONTROLS = RECIPE_DEFAULT_CONTROLS
const CONTROLS: { key: keyof SourceControls; label: string; low: string; high: string }[] = [
  { key: 'body', label: 'Body', low: 'Light', high: 'Full low-mid body' },
  { key: 'character', label: 'Harmonic character', low: 'Rounded', high: 'Rich harmonics' },
  { key: 'ensemble', label: 'Ensemble', low: 'Focused voice', high: 'Layered voices' },
  { key: 'movement', label: 'Natural movement', low: 'Stable', high: 'Organic' },
]
type Built = { stems: Float32Array[][] }
export default function SourceCharacterPanel({ hidden, blocked, sharedSource, onSource, onReset, onTrial }: { hidden: boolean; blocked: boolean; sharedSource: boolean; onSource: (stems: Float32Array[][], family: SourceFamily) => void; onReset: () => void; onTrial: () => void }) {
  const [controls, setControls] = useState<SourceControls>(DEFAULT_SOURCE_CONTROLS)
  const [family, setFamily] = useState<SourceFamily>('bowed')
  const [rendered, setRendered] = useState<{ family: SourceFamily; controls: SourceControls } | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const worker = useRef<Worker | null>(null)
  // Built sounds are remembered for the visit: building takes 0.2-0.9 s per style, so only the first click waits.
  const built = useRef(new Map<string, Built>())
  const sourceCallback = useRef(onSource)
  sourceCallback.current = onSource
  useEffect(() => () => worker.current?.terminate(), [])
  const generate = (selectedFamily: SourceFamily = family) => {
    worker.current?.terminate(); setError('')
    const snapshot = { controls: { ...controls }, family: selectedFamily }
    const key = JSON.stringify(snapshot)
    const deliver = (stems: Float32Array[][]) => { sourceCallback.current(stems, snapshot.family); setRendered(snapshot) }
    const cached = built.current.get(key)
    if (cached) { setBusy(false); deliver(cached.stems); return }
    setBusy(true)
    try {
      const next = new Worker(new URL('./sourceDesigner.worker.ts', import.meta.url), { type: 'module' })
      worker.current = next
      next.onmessage = ({ data }: MessageEvent<{ stems?: Float32Array[][]; error?: string }>) => {
        next.terminate(); worker.current = null; setBusy(false)
        if (data.error || !data.stems) { setError(data.error ?? 'Source generation failed.'); return }
        built.current.set(key, { stems: data.stems }); deliver(data.stems)
      }
      next.onerror = () => { next.terminate(); worker.current = null; setBusy(false); setError('Source generation failed. Try again.') }
      next.postMessage(snapshot)
    } catch (problem) { worker.current = null; setBusy(false); setError(problem instanceof Error ? problem.message : 'Could not start source generation.') }
  }
  const pending = rendered !== null && JSON.stringify(rendered) !== JSON.stringify({ controls, family })
  return <section hidden={hidden} className="reference-reconstruction" aria-labelledby="source-character-title">
    <h3 id="source-character-title">Sound styles <small>Base styles · same simulated drive</small></h3>
    <div className="sound-editor-transport">
      <button type="button" disabled={busy || blocked} onClick={onTrial}>Start</button>
      <button type="button" disabled={busy || blocked} onClick={() => generate()}>{busy ? 'Generating…' : 'Regenerate'}</button>
      <button type="button" disabled={busy || blocked} onClick={() => { setControls(DEFAULT_SOURCE_CONTROLS); setFamily('bowed'); setRendered(null); setError(''); onReset() }}>Original sound</button>
      <span role="status">{busy ? 'Rendering source audio' : !sharedSource ? 'Authored comparison active · generate to use shared source' : rendered ? pending ? 'Fine tuning changed · generate to hear it' : `${SOURCE_FAMILIES.find(item => item.id === rendered.family)?.label} active · this visit only` : 'Original source active · choose a family to generate it'}</span>
    </div>
    <div className="sound-editor-transport source-family-buttons" role="group" aria-label="Source family">
      {SOURCE_FAMILIES.filter(item => item.id !== 'blocks' && item.id !== 'resonant').map(item => <button key={item.id} type="button" aria-pressed={family === item.id} disabled={busy || blocked} onClick={() => { setFamily(item.id); generate(item.id) }}>
        {item.label}<small>{item.description}</small>
      </button>)}
    </div>
    <details>
      <summary>Fine tuning</summary>
    <div className="sound-editor-transport">
      {CONTROLS.map(({ key, label, low, high }) => <label key={key} className="sound-slider">
        <span>{label}<output>{Math.round(controls[key] * 100)}</output></span>
        <input type="range" aria-label={`Source ${label.toLowerCase()}`} min="0" max="1" step=".01" value={controls[key]} disabled={busy || blocked} onChange={event => setControls(current => ({ ...current, [key]: Number(event.target.value) }))} />
        <small>{low} · {high}</small>
      </label>)}
    </div>
    </details>
    <p>Press Start, then pick a style. Each style replays the same 22-second drive (0–120 km/h and stop). Chorus, reverb and mapping stay fixed. Nothing is saved.</p>
    {error && <p role="alert">{error}</p>}
  </section>
}
