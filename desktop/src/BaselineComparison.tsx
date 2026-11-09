import { useEffect, useRef, useState, useCallback } from 'react'

type Clip = { id: string; url: string; seconds: number; lufs: number; peak_4x: number; sha256_pcm: string; waveform: number[] }
type Manifest = { version: number; target_lufs: number; room: string; source_hashes: Record<string,string>; renderer_sha256: string; mapping_sha256: string; clips: Clip[] }
type Choice = { source: 'procedural' | 'recorded'; renderer: 'sample' | 'granular'; scene: 'neutral' | 'drive'; space: 'dry' | 'hall' }

export default function BaselineComparison({ hidden, blocked, onPlay }: { hidden: boolean; blocked: boolean; onPlay: () => void }) {
  const player = useRef<HTMLAudioElement>(null)
  const attachPlayer = useCallback((audio: HTMLAudioElement | null) => {
    if (!audio) player.current?.pause()
    else if (audio !== player.current) audio.volume = .7
    player.current = audio
  }, [])
  const [manifest, setManifest] = useState<Manifest | null>(null)
  const [error, setError] = useState('')
  const [stage, setStage] = useState<'source' | 'renderer' | 'space'>('source')
  const [choice, setChoice] = useState<Choice>({ source: 'procedural', renderer: 'sample', scene: 'neutral', space: 'dry' })
  const [position, setPosition] = useState(0)
  const id = `${choice.source}_${choice.renderer}_${choice.scene}_${choice.space}`
  const clip = manifest?.clips.find(item => item.id === id)
  useEffect(() => {
    const abort = new AbortController()
    void fetch('/audio/baseline-v1/manifest.json', { cache: 'no-store', signal: abort.signal }).then(async response => {
      if (!response.ok) throw Error('Baseline comparison audio is unavailable.')
      const data = await response.json()
      if (!Array.isArray(data.clips) || !Number.isFinite(data.target_lufs) || !data.clips.every((item: Clip) => typeof item.id === 'string' && item.url?.startsWith('/audio/baseline-v1/') && Number.isFinite(item.seconds) && Number.isFinite(item.lufs) && Array.isArray(item.waveform) && item.waveform.every(Number.isFinite))) throw Error('Baseline manifest is invalid.')
      setManifest(data)
    }).catch(problem => { if (!abort.signal.aborted) setError(problem instanceof Error ? problem.message : 'Could not load baseline audio.') })
    return () => { abort.abort(); player.current?.pause() }
  }, [])
  useEffect(() => { if (blocked || hidden) player.current?.pause() }, [blocked, hidden])
  useEffect(() => { player.current?.pause(); setPosition(0) }, [id])
  const changeStage = (next: typeof stage) => {
    setStage(next)
    setChoice(current => ({ ...current, renderer: next === 'source' ? 'sample' : current.renderer, space: next === 'space' ? 'hall' : 'dry', scene: next === 'renderer' ? 'drive' : 'neutral' }))
  }
  const exportSelection = () => {
    if (!manifest || !clip) return
    const value = { format: 'gs-baseline-selection-v1', selected: choice, playback_volume: player.current?.volume ?? .7, clip: { id: clip.id, sha256_pcm: clip.sha256_pcm, lufs: clip.lufs }, source_hashes: manifest.source_hashes, renderer_sha256: manifest.renderer_sha256, mapping_sha256: manifest.mapping_sha256, room: choice.space === 'hall' ? manifest.room : null, target_lufs: manifest.target_lufs }
    const url = URL.createObjectURL(new Blob([JSON.stringify(value, null, 2)], { type: 'application/json' }))
    const anchor = document.createElement('a'); anchor.href = url; anchor.download = 'gs-baseline-selection.json'; anchor.click()
    window.setTimeout(() => URL.revokeObjectURL(url), 1000)
  }
  const waveform = clip?.waveform.map((value, index, values) => {
    const x = 10 + index / Math.max(1, values.length - 1) * 620
    const height = Math.min(40, value * 80)
    return `M${x},${50-height}V${50+height}`
  }).join(' ')
  return <section hidden={hidden} className="reference-reconstruction baseline-comparison" aria-labelledby="baseline-comparison-title">
    <h3 id="baseline-comparison-title">Baseline comparison <small>Fixed clips · vehicle can stay stopped</small></h3>
    <div className="sound-editor-transport" role="group" aria-label="Comparison stage">
      <button type="button" aria-pressed={stage === 'source'} onClick={() => changeStage('source')}>1 · Source</button>
      <button type="button" aria-pressed={stage === 'renderer'} onClick={() => changeStage('renderer')}>2 · Renderer</button>
      <button type="button" aria-pressed={stage === 'space'} onClick={() => changeStage('space')}>3 · Hall</button>
    </div>
    <div className="sound-editor-transport">
      <label>Source <select className="sound-preset-select" aria-label="Baseline source" value={choice.source} onChange={event => setChoice(current => ({ ...current, source: event.target.value as Choice['source'] }))}><option value="procedural">Current synthesized strings</option><option value="recorded">Recorded cello section</option></select></label>
      <label>Renderer <select className="sound-preset-select" aria-label="Baseline renderer" disabled={stage === 'source'} value={choice.renderer} onChange={event => setChoice(current => ({ ...current, renderer: event.target.value as Choice['renderer'] }))}><option value="sample">Ordinary playback</option><option value="granular">Granular</option></select></label>
      <label>Space <select className="sound-preset-select" aria-label="Baseline room" disabled={stage !== 'space'} value={choice.space} onChange={event => setChoice(current => ({ ...current, space: event.target.value as Choice['space'] }))}><option value="dry">Dry</option><option value="hall">Great Hall reflections</option></select></label>
      <label>Test <select className="sound-preset-select" aria-label="Baseline test trace" disabled={stage === 'source'} value={choice.scene} onChange={event => setChoice(current => ({ ...current, scene: event.target.value as Choice['scene'] }))}><option value="neutral">Neutral tone</option><option value="drive">Identical driving trace</option></select></label>
    </div>
    {clip && <>
      <audio ref={attachPlayer} controls preload="none" src={clip.url} aria-label="Selected baseline comparison" onPlay={onPlay} onTimeUpdate={event => setPosition(event.currentTarget.currentTime)} onError={() => { setError('Could not play this baseline clip.') }} />
      <svg viewBox="0 0 640 100" width="100%" height="100" role="img" aria-label="Selected clip waveform">
        <path d={waveform} stroke="var(--accent)" strokeWidth="1" opacity=".7" />
        <line x1={10 + position / clip.seconds * 620} x2={10 + position / clip.seconds * 620} y1="5" y2="95" stroke="currentColor" />
      </svg>
      <p>{choice.scene === 'drive' ? '0–120 km/h · accelerate, hold, lift off, stop. Shared pitch/level mapping.' : 'Fixed register. Neutral granular playback should stay close to ordinary playback.'} Level matched to {manifest?.target_lufs.toFixed(1)} LUFS; playback volume stays under your control.</p>
      <div className="sound-editor-transport"><button type="button" onClick={exportSelection}>Export selection</button><a href={clip.url} download>Download selected clip</a><a href="/audio/baseline-v1/ATTRIBUTION.txt" target="_blank" rel="noreferrer">Sources & licences</a></div>
    </>}
    {!clip && !error && <p>Loading comparison clips…</p>}
    {error && <p role="alert">{error}</p>}
    <p>Cello: VSCO 2 CE, CC0. Hall: C4DM / Queen Mary, CC BY-NC-SA 4.0. Stereo projection; not binaural surround.</p>
  </section>
}
