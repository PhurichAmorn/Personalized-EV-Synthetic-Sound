import { useCallback, useEffect, useRef, useState } from 'react'
type Scores = { PQ: number; CE: number; PC: number; CU: number }
type Clip = { id: string; label: string; description: string; url: string; seconds: number; sha256: string; scores: Scores }
type Manifest = { model: string; target_lufs: number; clips: Clip[] }
type Rating = 'acceptable' | 'unpleasant' | 'unsure'
export default function AudioStressPool({ hidden, blocked, onPlay }: { hidden: boolean; blocked: boolean; onPlay: () => void }) {
  const player = useRef<HTMLAudioElement>(null)
  const attachPlayer = useCallback((audio: HTMLAudioElement | null) => {
    if (!audio) player.current?.pause()
    else if (audio !== player.current) audio.volume = .2
    player.current = audio
  }, [])
  const [manifest, setManifest] = useState<Manifest | null>(null)
  const [selected, setSelected] = useState('clean')
  const [ratings, setRatings] = useState<Record<string, Rating>>({})
  const [error, setError] = useState('')
  const clip = manifest?.clips.find(item => item.id === selected)
  useEffect(() => {
    const abort = new AbortController()
    void fetch('/audio/stress-pool-v1/manifest.json', { cache: 'no-store', signal: abort.signal }).then(async response => {
      if (!response.ok) throw Error('The graded test pool is unavailable.')
      const data = await response.json()
      if (!Array.isArray(data.clips) || !Number.isFinite(data.target_lufs) || !data.clips.every((item: Clip) => typeof item.id === 'string' && item.url?.startsWith('/audio/stress-pool-v1/') && typeof item.label === 'string' && typeof item.description === 'string' && Number.isFinite(item.seconds) && item.scores && ['PQ', 'CE', 'PC', 'CU'].every(key => Number.isFinite(item.scores[key as keyof Scores])))) throw Error('Invalid test-pool manifest.')
      setManifest(data)
    }).catch(problem => { if (!abort.signal.aborted) setError(problem instanceof Error ? problem.message : 'Could not load test sounds.') })
    return () => { abort.abort(); player.current?.pause() }
  }, [])
  useEffect(() => { if (hidden || blocked) player.current?.pause() }, [hidden, blocked])
  const selectClip = (id: string) => { player.current?.pause(); setSelected(id) }
  const exportRatings = () => {
    if (!manifest) return
    const result = { format: 'ev-audiobox-stress-review-v1', model: manifest.model, target_lufs: manifest.target_lufs, playback_volume: player.current?.volume ?? .2, clips: manifest.clips.map(item => ({ id: item.id, sha256: item.sha256, scores: item.scores, listener_rating: ratings[item.id] ?? null })) }
    const url = URL.createObjectURL(new Blob([JSON.stringify(result, null, 2)], { type: 'application/json' }))
    const anchor = document.createElement('a'); anchor.href = url; anchor.download = 'audiobox-listening-check.json'; anchor.click()
    window.setTimeout(() => URL.revokeObjectURL(url), 1000)
  }
  return <section hidden={hidden} className="reference-reconstruction baseline-comparison" aria-labelledby="stress-pool-title">
    <h3 id="stress-pool-title">Audiobox listening check <small>Clean reference + eight deliberate stress tests</small></h3>
    <p>Deliberately abrasive sounds. Start low; choose a clip, then press Play. Nothing auto-plays. Ratings stay in this visit until exported.</p>
    <div className="sound-editor-transport source-family-buttons" role="group" aria-label="Graded test sounds">
      {manifest?.clips.map(item => <button key={item.id} type="button" aria-pressed={selected === item.id} onClick={() => selectClip(item.id)}>
        {item.label}<small>Quality {item.scores.PQ.toFixed(2)} · Enjoyment {item.scores.CE.toFixed(2)}{ratings[item.id] ? ` · ${ratings[item.id]}` : ''}</small>
      </button>)}
    </div>
    {clip && <>
      <p>{clip.description}</p>
      <audio ref={attachPlayer} controls preload="none" src={clip.url} aria-label="Selected Audiobox stress test" onPlay={onPlay} onError={() => setError('Could not play the selected test sound.')} />
      <p>Model scores: quality {clip.scores.PQ.toFixed(2)} · enjoyment {clip.scores.CE.toFixed(2)} · complexity {clip.scores.PC.toFixed(2)} · usefulness {clip.scores.CU.toFixed(2)}. Predictions, not comfort certification; higher complexity is not necessarily better.</p>
      <div className="sound-editor-transport" role="group" aria-label="Your listening judgment">
        {(['acceptable', 'unpleasant', 'unsure'] as const).map(rating => <button key={rating} type="button" aria-pressed={ratings[selected] === rating} onClick={() => setRatings(current => ({ ...current, [selected]: rating }))}>{rating === 'acceptable' ? 'Acceptable' : rating === 'unpleasant' ? 'Unpleasant' : 'Unsure'}</button>)}
        <button type="button" onClick={exportRatings}>Export listening check</button>
        <a href={clip.url} download>Download clip</a>
      </div>
      <p>Ten seconds each · {manifest?.target_lufs.toFixed(1)} LUFS · same reference and matched loudness. No effect on driving sounds or candidate selection.</p>
    </>}
    {!manifest && !error && <p>Loading graded test pool…</p>}
    {error && <p role="alert">{error}</p>}
  </section>
}
