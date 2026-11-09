import { useCallback, useEffect, useRef, useState } from 'react'
type Clip = { id: string; group: 'wobble' | 'chord'; set: string; reference: boolean; label: string; url: string; seconds: number; sha256: string; params: Record<string, unknown> }
type Manifest = { target_lufs: number; clips: Clip[] }
type Answer = { comfort?: 'comfortable' | 'borderline' | 'unpleasant'; differs?: 'same' | 'slightly' | 'clearly'; tags?: string[] }
const STORE = 'ev-roughness-check-v1'
const TAGS = { wobble: ['Slow wavering', 'Flutter / motorboat', 'Buzzy / gritty', 'Nothing noticed'], chord: ['Smoother', 'Rougher / buzzier', 'Deeper / darker', 'Thinner / hollow', 'Fuller / richer'] }
const load = (): { answers: Record<string, Answer>; favourites: Record<string, string> } => {
  try { const saved = JSON.parse(localStorage.getItem(STORE) ?? '{}'); return { answers: saved.answers ?? {}, favourites: saved.favourites ?? {} } } catch { return { answers: {}, favourites: {} } }
}
export default function RoughnessListeningCheck({ hidden, blocked, onPlay }: { hidden: boolean; blocked: boolean; onPlay: () => void }) {
  const player = useRef<HTMLAudioElement>(null)
  const attachPlayer = useCallback((audio: HTMLAudioElement | null) => {
    if (!audio) player.current?.pause()
    else if (audio !== player.current) audio.volume = .2
    player.current = audio
  }, [])
  const [manifest, setManifest] = useState<Manifest | null>(null)
  const [selected, setSelected] = useState('w_ref')
  const [answers, setAnswers] = useState(() => load().answers)
  const [favourites, setFavourites] = useState(() => load().favourites)
  const [error, setError] = useState('')
  useEffect(() => { try { localStorage.setItem(STORE, JSON.stringify({ answers, favourites })) } catch { /* storage unavailable: ratings stay in memory */ } }, [answers, favourites])
  useEffect(() => {
    const abort = new AbortController()
    void fetch('/audio/roughness-check-v1/manifest.json', { cache: 'no-store', signal: abort.signal }).then(async response => {
      if (!response.ok) throw Error('The listening pack is unavailable. Run tools/build_listening_check.py.')
      const data = await response.json()
      if (!Array.isArray(data.clips) || !data.clips.every((c: Clip) => typeof c.id === 'string' && c.url?.startsWith('/audio/roughness-check-v1/'))) throw Error('Invalid listening pack.')
      setManifest(data)
    }).catch(problem => { if (!abort.signal.aborted) setError(problem instanceof Error ? problem.message : 'Could not load the listening pack.') })
    return () => { abort.abort(); player.current?.pause() }
  }, [])
  useEffect(() => { if (hidden || blocked) player.current?.pause() }, [hidden, blocked])
  const clips = manifest?.clips ?? []
  const clip = clips.find(item => item.id === selected)
  const done = clips.filter(item => answers[item.id]?.comfort).length
  const update = (patch: Answer) => setAnswers(current => ({ ...current, [selected]: { ...current[selected], ...patch } }))
  const choose = (id: string) => { player.current?.pause(); setSelected(id) }
  const next = () => { const index = clips.findIndex(item => item.id === selected); if (index >= 0 && index < clips.length - 1) choose(clips[index + 1].id) }
  const toggleTag = (tag: string) => { const tags = answers[selected]?.tags ?? []; update({ tags: tags.includes(tag) ? tags.filter(item => item !== tag) : [...tags, tag] }) }
  const exportResults = () => {
    const result = { format: 'ev-roughness-listening-check-v1', created: new Date().toISOString(), playback_volume: player.current?.volume ?? .2, target_lufs: manifest?.target_lufs, favourites, clips: clips.map(item => ({ id: item.id, set: item.set, reference: item.reference, sha256: item.sha256, params: item.params, comfort: answers[item.id]?.comfort ?? null, differs_from_reference: answers[item.id]?.differs ?? null, tags: answers[item.id]?.tags ?? [] })) }
    const url = URL.createObjectURL(new Blob([JSON.stringify(result, null, 2)], { type: 'application/json' }))
    const anchor = document.createElement('a'); anchor.href = url; anchor.download = 'roughness-listening-check.json'; anchor.click()
    window.setTimeout(() => URL.revokeObjectURL(url), 1000)
  }
  const answer = answers[selected] ?? {}
  const tags = clip ? TAGS[clip.group] : []
  const section = (group: Clip['group']) => clips.filter(item => item.group === group)
  return <section hidden={hidden} className="reference-reconstruction baseline-comparison" aria-labelledby="roughness-check-title">
    <h3 id="roughness-check-title">Roughness &amp; chord listening check <small>20 clips · about 15 minutes</small></h3>
    <details open>
      <summary>What to do</summary>
      <ol>
        <li>Use headphones in a quiet room. Start with volume low (player starts at 20%) and set it once, then leave it. Every clip is loudness-matched, so do not change volume between clips.</li>
        <li>Each clip is a 22 s drive-up sweep of the same sound. Listen to at least the first 15 s, then answer. Nothing auto-plays.</li>
        <li>For each clip choose <b>Comfortable / Borderline / Unpleasant</b>: would you be happy hearing this for a long drive? Add tags for what you hear. Trust your first reaction; do not compare to the numbers.</li>
        <li>Press <b>Export results</b> at the end and send me the downloaded <code>roughness-listening-check.json</code>. Answers are also kept in this browser if you close the page.</li>
      </ol>
      <p><b>Part 1 · Wobble (11 clips).</b> Play <b>Reference</b> first: it is the plain sound. The others add a volume wobble of different speeds. Listen for: <i>slow wavering</i> (2–8 Hz: like a slow tremolo or breathing), <i>flutter</i> (about 20–30 Hz: like a motorboat or helicopter), <i>buzz / grit</i> (50–150 Hz: rough, rasping, like a kazoo or growl). For each, say how different it sounds from the Reference, and when it starts to bother you. Faint wobble that you only notice when you look for it is "Slightly different" and probably "Comfortable". The sounds are shuffled, so rate each on its own.</p>
      <p><b>Part 2 · Chords (9 clips, 3 sets of 3).</b> Within a set, the three sounds are the same type of sound with different harmony underneath. Listen for: <i>smoother vs rougher</i> (is there a faint buzz or beating under the tone?), <i>deeper vs thinner</i> (low weight vs hollow), <i>fuller vs plain</i>. After rating all three in a set, mark the one you would most like to drive with using <b>My favourite of this set</b>.</p>
      <p>Warning: some clips are deliberately rough. If any is uncomfortable, stop, mark it Unpleasant and move on.</p>
    </details>
    {(['wobble', 'chord'] as const).map(group => <div key={group}>
      <h4>{group === 'wobble' ? 'Part 1 · Wobble' : 'Part 2 · Chords'}</h4>
      <div className="sound-editor-transport source-family-buttons" role="group" aria-label={group === 'wobble' ? 'Wobble clips' : 'Chord clips'}>
        {section(group).map(item => <button key={item.id} type="button" aria-pressed={selected === item.id} onClick={() => choose(item.id)}>{item.label}<small>{answers[item.id]?.comfort ?? 'not rated'}{favourites[item.set] === item.id ? ' · favourite' : ''}</small></button>)}
      </div>
    </div>)}
    {clip && <>
      <h4>{clip.label}</h4>
      <audio key={clip.id} ref={attachPlayer} controls preload="none" src={clip.url} aria-label={clip.label} onPlay={onPlay} onError={() => setError('Could not play this clip.')} />
      <div className="sound-editor-transport" role="group" aria-label="Comfort">
        {(['comfortable', 'borderline', 'unpleasant'] as const).map(value => <button key={value} type="button" aria-pressed={answer.comfort === value} onClick={() => update({ comfort: value })}>{value[0].toUpperCase() + value.slice(1)}</button>)}
      </div>
      {clip.group === 'wobble' && !clip.reference && <div className="sound-editor-transport" role="group" aria-label="Difference from reference">
        <span>Compared with Reference:</span>
        {(['same', 'slightly', 'clearly'] as const).map(value => <button key={value} type="button" aria-pressed={answer.differs === value} onClick={() => update({ differs: value })}>{value === 'same' ? 'Same' : value === 'slightly' ? 'Slightly different' : 'Clearly different'}</button>)}
      </div>}
      <div className="sound-editor-transport" role="group" aria-label="What you hear">
        <span>What I hear:</span>
        {tags.map(tag => <button key={tag} type="button" aria-pressed={answer.tags?.includes(tag) ?? false} onClick={() => toggleTag(tag)}>{tag}</button>)}
      </div>
      {clip.group === 'chord' && <div className="sound-editor-transport">
        <button type="button" aria-pressed={favourites[clip.set] === clip.id} onClick={() => setFavourites(current => ({ ...current, [clip.set]: current[clip.set] === clip.id ? '' : clip.id }))}>My favourite of this set</button>
      </div>}
      <div className="sound-editor-transport">
        <button type="button" onClick={next} disabled={clips.findIndex(item => item.id === selected) === clips.length - 1}>Next clip</button>
        <button type="button" onClick={exportResults}>Export results</button>
        <span>{done} / {clips.length} rated</span>
      </div>
      <p>Listening check only: it does not change driving sounds or candidate selection. Ratings stay in this browser until you clear them; export before sending.</p>
    </>}
    {!manifest && !error && <p>Loading listening pack…</p>}
    {error && <p role="alert">{error}</p>}
  </section>
}
