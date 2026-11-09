import { useEffect, useRef, useState } from 'react'
import { DEFAULT_SOURCE_CONTROLS, SOURCE_FAMILIES, type SourceFamily, type SourceControls } from './sourceDesigner'
const CONTROLS: { key: keyof SourceControls; label: string; low: string; high: string }[] = [
  { key: 'body', label: 'Body', low: 'Light', high: 'Full low-mid body' },
  { key: 'character', label: 'Harmonic character', low: 'Rounded', high: 'Rich harmonics' },
  { key: 'ensemble', label: 'Ensemble', low: 'Focused voice', high: 'Layered voices' },
  { key: 'movement', label: 'Natural movement', low: 'Stable', high: 'Organic' },
]
export default function SourceCharacterPanel({ hidden, blocked, sharedSource, onSource, onReset, onTrial }: { hidden: boolean; blocked: boolean; sharedSource: boolean; onSource: (stems: Float32Array[][]) => void; onReset: () => void; onTrial: () => void }) {
  const [controls, setControls] = useState<SourceControls>(DEFAULT_SOURCE_CONTROLS)
  const [family, setFamily] = useState<SourceFamily>('bowed')
  const [rendered, setRendered] = useState<{ family: SourceFamily; controls: SourceControls } | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const worker = useRef<Worker | null>(null)
  const sourceCallback = useRef(onSource)
  sourceCallback.current = onSource
  useEffect(() => () => worker.current?.terminate(), [])
  const generate = (selectedFamily: SourceFamily = family) => {
    worker.current?.terminate(); setBusy(true); setError('')
    const snapshot = { controls: { ...controls }, family: selectedFamily }
    try {
      const next = new Worker(new URL('./sourceDesigner.worker.ts', import.meta.url), { type: 'module' })
      worker.current = next
      next.onmessage = ({ data }: MessageEvent<{ stems?: Float32Array[][]; error?: string }>) => {
        next.terminate(); worker.current = null; setBusy(false)
        if (data.error || !data.stems) { setError(data.error ?? 'Source generation failed.'); return }
        sourceCallback.current(data.stems); setRendered(snapshot)
      }
      next.onerror = () => { next.terminate(); worker.current = null; setBusy(false); setError('Source generation failed. Try again.') }
      next.postMessage(snapshot)
    } catch (problem) { worker.current = null; setBusy(false); setError(problem instanceof Error ? problem.message : 'Could not start source generation.') }
  }
  const pending = rendered !== null && JSON.stringify(rendered) !== JSON.stringify({ controls, family })
  return <section hidden={hidden} className="reference-reconstruction" aria-labelledby="source-character-title">
    <h3 id="source-character-title">Source families <small>Six directions · same simulated drive</small></h3>
    <div className="sound-editor-transport">
      <button type="button" disabled={busy || blocked} onClick={onTrial}>Start source trial · Rise</button>
      <button type="button" disabled={busy || blocked} onClick={() => generate()}>{busy ? 'Generating…' : 'Generate selected family'}</button>
      <button type="button" disabled={busy || blocked} onClick={() => { setControls(DEFAULT_SOURCE_CONTROLS); setFamily('bowed'); setRendered(null); setError(''); onReset() }}>Restore original source</button>
      <span role="status">{busy ? 'Rendering source audio' : !sharedSource ? 'Authored comparison active · generate to use shared source' : rendered ? pending ? 'Fine tuning changed · generate to hear it' : `${SOURCE_FAMILIES.find(item => item.id === rendered.family)?.label} active · this visit only` : 'Original source active · choose a family to generate it'}</span>
    </div>
    <div className="sound-editor-transport source-family-buttons" role="group" aria-label="Source family">
      {SOURCE_FAMILIES.map(item => <button key={item.id} type="button" aria-pressed={family === item.id} disabled={busy || blocked} onClick={() => { setFamily(item.id); generate(item.id) }}>
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
    <p>Start the Rise trial, then choose a family. Each choice generates its source and replays the same drive. Chorus, reverb and mapping stay fixed. No automatic saving or preference learning yet.</p>
    {error && <p role="alert">{error}</p>}
  </section>
}
