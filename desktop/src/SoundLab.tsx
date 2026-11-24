import { useEffect, useRef, useState, type RefObject } from 'react'
import type { State } from './App'
import type { GranularMode } from './granularPlayer'
import { clamp, LabPlayer } from './labEngine'
import { isLiveRecipe, liveSound, type LiveRecipe } from './levels'
import { liveStems } from './voiceCache'
import { simulatedDrive, SIMULATED_DRIVE_SECONDS } from './simulatedDrive'
import { drawColumn } from './OverlayGraphs'

type Blocks = Record<string, string | number | boolean | null>
type Options = { bodies: string[]; tops: string[]; partners: Record<string, string[]>; levels: string[]; pitches: number[]; buzz: number[]; names: Record<string, string>; default: Blocks; synthTops: string[] }
type Built = { recipe?: LiveRecipe & { label?: string; blocks?: Blocks; checked?: boolean }; error?: string }
type WinnerItem = { session: string; created?: string; label: string; recipe?: unknown; id?: string }
const BUZZ_NAMES = ['Off', 'Some', 'Strong']

const logX = (hz: number) => Math.log(hz / 40) / Math.log(300)  // 40 Hz-12 kHz

/** Sound Lab = listening bench and block builder: build a sound from the session's own blocks (or load your winner's blocks), hear it on the
 * simulated 22 s sweep (looped), in Rising or Evolving, and watch the graphs. Nothing is saved. */
export default function SoundLab({ state, onCommand, onStart, stopToken }: { state: State; onCommand: (name: string, payload?: Record<string, unknown>) => Promise<unknown> | void; onStart: () => void; stopToken: number }) {
  const [player] = useState(() => new LabPlayer())
  const analyser = useRef<AnalyserNode | null>(null)
  const [mode, setMode] = useState<GranularMode>('rise')
  const [volume, setVolume] = useState(.7)
  const [playing, setPlaying] = useState(false)
  const [error, setError] = useState('')
  const [options, setOptions] = useState<Options | null>(null)
  const [blocks, setBlocks] = useState<Blocks>({})
  const [built, setBuilt] = useState<Built>({})
  const [modalOpen, setModalOpen] = useState(false)
  const [previewingId, setPreviewingId] = useState<string | null>(null)
  const [fetchedRecipes, setFetchedRecipes] = useState<Record<string, unknown>>({})

  useEffect(() => { void Promise.resolve(onCommand('blockOptions')).then(o => { if (o) { setOptions(o as Options); setBlocks((o as Options).default) } }) }, [])
  // The block sound is built by the same code a session uses (safe-area table, brightness to low-pass, loudness): the backend returns the live recipe.
  useEffect(() => {
    if (!options) return
    const timer = setTimeout(() => void Promise.resolve(onCommand('blockBuild', { blocks, motion: mode })).then(result => setBuilt((result ?? {}) as Built)).catch(problem => setBuilt({ error: String(problem) })), 200)
    return () => clearTimeout(timer)
  }, [blocks, mode, options])

  const winnerList: WinnerItem[] = (state.mySounds?.length ? state.mySounds : state.mySound ? [state.mySound] : [])
  const hasWinners = winnerList.length > 0

  useEffect(() => {
    if (!modalOpen) return
    const missing = winnerList.filter(item => !item.recipe && !fetchedRecipes[item.session])
    if (!missing.length) return
    let cancelled = false
    void Promise.all(missing.map(async item => {
      try {
        const data = await Promise.resolve(onCommand('historyGet', { id: item.session })) as { final?: string; candidates?: Record<string, { recipe?: unknown }> } | null
        if (!cancelled && data?.final && data.candidates?.[data.final]?.recipe) {
          setFetchedRecipes(prev => ({ ...prev, [item.session]: data.candidates![data.final!].recipe }))
        }
      } catch {}
    }))
    return () => { cancelled = true }
  }, [modalOpen, winnerList])

  const closeModal = () => {
    if (previewingId) {
      player.stop()
      setPreviewingId(null)
    }
    setModalOpen(false)
  }

  useEffect(() => {
    if (!modalOpen) return
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') closeModal() }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [modalOpen, previewingId])

  const getItemRecipe = (item: WinnerItem) =>
    (item.recipe ?? fetchedRecipes[item.session]) as (LiveRecipe & { blocks?: Blocks }) | undefined

  const togglePreview = async (item: WinnerItem) => {
    if (previewingId === item.session) {
      player.stop()
      setPreviewingId(null)
      return
    }
    setError('')
    try {
      let r = getItemRecipe(item)
      if (!r) {
        const data = await Promise.resolve(onCommand('historyGet', { id: item.session })) as { final?: string; candidates?: Record<string, { recipe?: unknown }> } | null
        if (data?.final && data.candidates?.[data.final]?.recipe) {
          r = data.candidates[data.final].recipe as LiveRecipe
          setFetchedRecipes(prev => ({ ...prev, [item.session]: r }))
        }
      }
      if (!r || !isLiveRecipe(r)) {
        setError('Cannot preview this sound.')
        return
      }
      stop()
      setPreviewingId(item.session)
      const { plain, fx, travel, mode: rMode } = liveSound(r)
      analyser.current = null
      const started = await player.play(
        'winner-preview-' + item.session,
        liveStems(r),
        fx,
        plain.rootHz,
        'simulated',
        () => ({ input: undefined, stale: false }),
        time => simulatedDrive(time % SIMULATED_DRIVE_SECONDS),
        rMode ?? mode,
        travel
      )
      analyser.current = player.analyser
      if (!started) setPreviewingId(null)
    } catch (problem) {
      player.stop()
      setPreviewingId(null)
      setError(problem instanceof Error ? problem.message : 'Could not play preview.')
    }
  }

  const loadWinner = async (item: WinnerItem) => {
    if (previewingId) {
      player.stop()
      setPreviewingId(null)
    }
    let r = getItemRecipe(item)
    if (!r) {
      const data = await Promise.resolve(onCommand('historyGet', { id: item.session })) as { final?: string; candidates?: Record<string, { recipe?: unknown }> } | null
      if (data?.final && data.candidates?.[data.final]?.recipe) {
        r = data.candidates[data.final].recipe as LiveRecipe
        setFetchedRecipes(prev => ({ ...prev, [item.session]: r }))
      }
    }
    const b = r && isLiveRecipe(r) && r.blocks ? r.blocks : null
    if (b && options) {
      setBlocks({ ...options.default, ...Object.fromEntries(Object.entries(b).filter(([key]) => key in options.default)) })
      void onCommand('mySound', { id: item.session })
      closeModal()
    }
  }

  const recipe = built.recipe ?? null
  const soundId = 'lab-build-' + (built.recipe?.label ?? '')
  const change = (patch: Blocks) => { setBlocks(current => ({ ...current, ...patch, ...(patch.top && !(options?.partners[patch.top as string] ?? []).includes(current.partner as string) ? { partner: null } : {}) })) }
  const stop = () => { player.stop(); setPlaying(false); setPreviewingId(null) }
  useEffect(() => () => player.close(), [player])
  useEffect(() => { if (stopToken) stop() }, [stopToken])  // something else started playing
  useEffect(() => { if (playing && built.recipe) void play() }, [built.recipe])  // a changed block restarts the sound the same way
  useEffect(() => { player.volume = volume }, [volume])
  const play = async () => {
    if (!recipe) return
    onStart(); setError('')
    try {
      const { plain, fx, travel } = liveSound(recipe)
      analyser.current = null
      const started = await player.play(soundId, liveStems(recipe), fx, plain.rootHz, 'simulated', () => ({ input: undefined, stale: false }), time => simulatedDrive(time % SIMULATED_DRIVE_SECONDS), mode, travel)
      analyser.current = player.analyser
      if (started) setPlaying(true)
    } catch (problem) { stop(); setError(problem instanceof Error ? problem.message : 'Could not play the sound.') }
  }
  return <section className="lab" aria-label="Listening bench">
    <div className="lab-fixed">
    <header className="lab-head"><div><small>LISTENING BENCH</small><h2>Sound Lab</h2></div>
      <div className="lab-transport">
        <span className="lab-seg">{(['rise', 'evolving'] as const).map(item => <button key={item} type="button" className={mode === item ? 'active' : ''} onClick={() => setMode(item)}>{item === 'rise' ? 'Rising' : 'Evolving'}</button>)}</span>
        <button type="button" disabled={!recipe} aria-pressed={playing} onClick={() => void (playing ? stop() : play())}>{playing ? 'Stop' : '▶ Sound sweep'}</button>
        <label className="lab-volume">Vol<input type="range" min="0" max="1" step=".01" value={volume} onChange={event => setVolume(+event.target.value)} /></label>
      </div>
    </header>
    {error && <p className="lab-error" role="alert">{error}</p>}
    <div className="lab-scopes">
      {(['spectrogram', 'spectrum', 'waveform'] as const).map(view => <Scope key={view} analyser={analyser} active={playing || !!previewingId} view={view} />)}
    </div>
    </div>
    <section className="lab-builder" aria-label="Build a sound">
      <h3>Build a sound <small>the session's own blocks, safe-area table and loudness</small></h3>
      <p className="lab-note">Sound sweep plays the sound over the simulated drive (speed climbs, lifts, brakes), looping. Change a block and the sound updates.</p>
      <div className="lab-chips"><button type="button" disabled={!options || !hasWinners} title={hasWinners ? 'Fill the blocks from your latest saved sound' : 'No saved building-block sound yet'} onClick={() => setModalOpen(true)}>Load from winner</button>
        <button type="button" disabled={!options} onClick={() => setBlocks(options!.default)}>Build from scratch</button></div>
      {options && <div className="lab-build-grid">
        <div><p className="lab-label">Top texture</p><div className="lab-chips">{options.tops.map(top => <button key={top} type="button" aria-pressed={blocks.top === top} onClick={() => change({ top })}>{options.names[top]}</button>)}</div></div>
        <div><p className="lab-label">Partner (on the highest layer)</p><div className="lab-chips">{[null, ...(options.partners[blocks.top as string] ?? [])].map(partner => <button key={partner ?? 'none'} type="button" aria-pressed={(blocks.partner ?? null) === partner} onClick={() => change({ partner })}>{partner ? options.names[partner] : 'None'}</button>)}</div></div>
        <div><p className="lab-label">Body (lowest layer)</p><div className="lab-chips">{options.bodies.map(body => <button key={body} type="button" aria-pressed={blocks.body === body} onClick={() => change({ body })}>{options.names[body]}</button>)}</div></div>
        <div><p className="lab-label">Top level</p><div className="lab-chips">{options.levels.map(level => <button key={level} type="button" aria-pressed={blocks.level === level} onClick={() => change({ level })}>{level}</button>)}</div></div>
        <div><p className="lab-label">Pitch</p><div className="lab-chips">{options.pitches.map((hz, index) => <button key={hz} type="button" aria-pressed={blocks.pitch === index} onClick={() => change({ pitch: index })}>{hz} Hz</button>)}</div></div>
        <label className="lab-slider"><span>Brightness (acum)<output>{(+(blocks.brightness ?? .5)).toFixed(2)}{built.recipe?.blocks && Math.abs(+built.recipe.blocks.brightness! - +(blocks.brightness ?? .5)) > .01 ? ` → reached ${(+built.recipe.blocks.brightness!).toFixed(2)}` : ''}</output></span>
          <input type="range" min=".2" max="1.4" step=".01" value={+(blocks.brightness ?? .5)} onChange={event => change({ brightness: +event.target.value })} /></label>
        {options.synthTops.includes(blocks.top as string) && <div><p className="lab-label">Synth knobs (Synth and Bell synth tops only)</p><div className="lab-chips">
          {options.buzz.map(level => <button key={level} type="button" aria-pressed={blocks.buzz === level} onClick={() => change({ buzz: level })}>Buzz: {BUZZ_NAMES[level]}</button>)}
          <button type="button" aria-pressed={blocks.chord === 'on'} onClick={() => change({ chord: blocks.chord === 'on' ? 'off' : 'on' })}>Chord (minor)</button>
          <button type="button" aria-pressed={!!blocks.bell} onClick={() => change({ bell: !blocks.bell })}>Bell</button>
          <button type="button" aria-pressed={!!blocks.vowel} onClick={() => change({ vowel: !blocks.vowel })}>Vowel</button></div></div>}
      </div>}
      {built.error ? <p className="lab-error" role="alert">{built.error}</p> : built.recipe && <p className="lab-note">{built.recipe.label}</p>}
    </section>
    {modalOpen && <div className="lab-modal-backdrop" onMouseDown={e => { if (e.target === e.currentTarget) closeModal() }}>
      <section className="lab-modal" role="dialog" aria-modal="true" aria-labelledby="winner-modal-title">
        <header className="lab-modal-head">
          <div>
            <h3 id="winner-modal-title">Saved Winner Sounds</h3>
            <p>Preview and select a winner sound to load its blocks into Sound Lab.</p>
          </div>
          <button type="button" className="lab-modal-close" onClick={closeModal}>Close</button>
        </header>
        <div className="lab-modal-body">
          {!winnerList.length ? <p className="lab-note">No saved winner sounds found yet. Finish a sound session to save a winner sound.</p> : winnerList.map(item => {
            const r = getItemRecipe(item)
            const b = r && isLiveRecipe(r) && r.blocks ? r.blocks : null
            const isPlayingThis = previewingId === item.session
            const isActive = state.mySound?.session === item.session
            return <div key={item.session} className={'lab-winner-card' + (isActive ? ' active' : '')}>
              <div className="lab-winner-card-head">
                <span className="lab-winner-title">
                  {item.label || 'Saved Sound'}
                  {isActive && <span className="lab-winner-badge">Active</span>}
                </span>
                <span className="lab-winner-meta">{item.created ? new Date(item.created).toLocaleString([], { dateStyle: 'medium', timeStyle: 'short' }) : ''}</span>
              </div>
              {b && <div className="lab-winner-blocks">Top: {b.top}{b.partner ? ` + ${b.partner}` : ''} · Body: {b.body} · Level: {b.level} · Pitch: {options?.pitches[b.pitch as number] ?? b.pitch} Hz</div>}
              <div className="lab-winner-actions">
                <button type="button" aria-pressed={isPlayingThis} onClick={() => void togglePreview(item)}>{isPlayingThis ? '■ Stop' : '▶ Preview'}</button>
                <button type="button" disabled={!b || !options} title={b ? 'Load these blocks into Sound Lab' : 'This saved sound does not contain building blocks'} onClick={() => void loadWinner(item)}>{b ? 'Load blocks' : 'No blocks'}</button>
              </div>
            </div>
          })}
        </div>
      </section>
    </div>}
  </section>
}

/** Quick YIN pitch estimation to lock the waveform to the fundamental period. */
function findPeriod(samples: Float32Array, sr: number): number {
  const minLag = Math.max(16, Math.floor(sr / 600))  // up to 600 Hz
  const maxLag = Math.min(Math.floor(samples.length / 2), Math.floor(sr / 45))  // down to 45 Hz
  const W = 300
  if (samples.length < maxLag + W) return Math.round(sr / 110)

  let runningSum = 0
  let bestLag = 0
  let minCmnd = Infinity
  const thresh = 0.35

  for (let lag = minLag; lag < maxLag; lag += 2) {
    let diff = 0
    for (let j = 0; j < W; j += 2) {
      const d = samples[j] - samples[lag + j]
      diff += d * d
    }
    runningSum += diff
    const count = Math.floor((lag - minLag) / 2) + 1
    const cmnd = diff / (runningSum / count + 1e-6)
    if (cmnd < minCmnd) minCmnd = cmnd
    if (cmnd < thresh) {
      bestLag = lag
      break
    }
  }

  return bestLag > 0 ? bestLag : Math.round(sr / 110)
}

/** One live view of the output; Sound Lab shows all three at once (spectrogram, spectrum, waveform), each with its own draw loop. */
function Scope({ analyser, active, view }: { analyser: RefObject<AnalyserNode | null>; active: boolean; view: 'spectrum' | 'spectrogram' | 'waveform' }) {
  const canvas = useRef<HTMLCanvasElement>(null)
  const live = useRef(active)
  live.current = active
  const [frozen, setFrozen] = useState(false)
  const isFrozen = useRef(false)
  isFrozen.current = frozen
  const prevWave = useRef<Float32Array | null>(null)
  const wake = useRef(() => {})
  useEffect(() => {
    if (!active) { prevWave.current = null }
  }, [active])
  useEffect(() => {
    const element = canvas.current, draw = element?.getContext('2d')
    if (!element || !draw) return
    const freq = new Float32Array(2048), samples = new Float32Array(2048)
    let frame = 0, width = 0, height = 0
    const observer = new ResizeObserver(([entry]) => {
      width = entry.contentRect.width; height = entry.contentRect.height
      const ratio = window.devicePixelRatio || 1
      element.width = Math.round(width * ratio); element.height = Math.round(height * ratio); draw.setTransform(ratio, 0, 0, ratio, 0, 0)
      draw.fillStyle = '#101010'; draw.fillRect(0, 0, width, height)
      wake.current()
    })
    observer.observe(element)
    const css = getComputedStyle(element), ink = css.getPropertyValue('--fg').trim() || '#f2f2f2'
    const render = () => {
      const node = analyser.current, on = live.current && !!node
      // Not playing: draw nothing (the last picture stays) and stop until playback wakes the loop again.
      if (!on) { frame = 0; return }
      frame = requestAnimationFrame(render)
      if (isFrozen.current) return
      node!.getFloatFrequencyData(freq); node!.getFloatTimeDomainData(samples)
      const binHz = node!.context.sampleRate / 4096
      if (view === 'spectrogram') {
        drawColumn(element, hz => freq[Math.round(hz / binHz)] ?? -140, 2)  // shared with the overlay graph
      } else if (view === 'spectrum') {
        draw.fillStyle = '#101010'; draw.fillRect(0, 0, width, height)
        draw.strokeStyle = '#2b2b2b'; draw.beginPath()
        for (const hz of [100, 1000, 10000]) { const x = logX(hz) * width; draw.moveTo(x, 0); draw.lineTo(x, height) }
        draw.stroke()
        draw.strokeStyle = ink; draw.lineWidth = 1.5; draw.beginPath()
        for (let x = 0; x < width; x++) {
          const db = freq[Math.round(40 * 300 ** (x / width) / binHz)] ?? -140, y = height - clamp((db + 120) / 110, 0, 1) * height
          if (x) draw.lineTo(x, y); else draw.moveTo(x, y)
        }
        draw.stroke()
      } else {
        // Waveform: grid with zero baseline and division ticks
        draw.fillStyle = '#101010'; draw.fillRect(0, 0, width, height)
        draw.strokeStyle = '#222222'; draw.beginPath()
        draw.moveTo(0, height / 2); draw.lineTo(width, height / 2)
        for (const frac of [0.25, 0.5, 0.75]) { const x = frac * width; draw.moveTo(x, 0); draw.lineTo(x, height) }
        draw.stroke()

        const len = samples.length
        let peak = 0
        for (let i = 0; i < len; i++) { const v = Math.abs(samples[i]); if (v > peak) peak = v }

        if (peak < 0.005) {
          draw.strokeStyle = ink; draw.lineWidth = 1.5; draw.beginPath()
          draw.moveTo(0, height / 2); draw.lineTo(width, height / 2); draw.stroke()
          prevWave.current = null
        } else {
          const sr = node!.context.sampleRate || 48000
          const period = findPeriod(samples, sr)
          const span = Math.min(len - period, Math.max(32, period * 2))

          let bestOffset = 0
          const ref = prevWave.current
          if (ref && ref.length === span) {
            // Phase lock: find offset within [0, period) that best matches previous frame
            let maxCorr = -Infinity
            const checkLen = Math.min(span, 240)
            for (let off = 0; off < period; off += 2) {
              let corr = 0
              for (let j = 0; j < checkLen; j += 2) {
                corr += ref[j] * samples[off + j]
              }
              if (corr > maxCorr) {
                maxCorr = corr
                bestOffset = off
              }
            }
            // Refine by +/- 1 sample
            for (const off of [bestOffset - 1, bestOffset + 1]) {
              if (off >= 0 && off < period) {
                let corr = 0
                for (let j = 0; j < checkLen; j += 2) {
                  corr += ref[j] * samples[off + j]
                }
                if (corr > maxCorr) {
                  maxCorr = corr
                  bestOffset = off
                }
              }
            }
          } else {
            // First frame: align on rising zero crossing
            for (let i = 1; i < period; i++) {
              if (samples[i - 1] <= 0 && samples[i] > 0) {
                bestOffset = i
                break
              }
            }
          }

          draw.strokeStyle = ink; draw.lineWidth = 1.5; draw.beginPath()
          const saved = new Float32Array(span)
          for (let i = 0; i < span; i++) {
            saved[i] = samples[bestOffset + i]
            const x = (i / (span - 1)) * width
            const s = Math.max(-1, Math.min(1, saved[i] * 1.35))
            const y = height / 2 - s * (height / 2 - 4)
            if (i) draw.lineTo(x, y); else draw.moveTo(x, y)
          }
          draw.stroke()
          prevWave.current = saved
        }
      }
    }
    wake.current = () => { if (!frame) frame = requestAnimationFrame(render) }
    wake.current()
    return () => { cancelAnimationFrame(frame); frame = 0; wake.current = () => {}; observer.disconnect() }
  }, [view, analyser])
  useEffect(() => { if (active) wake.current() }, [active])
  return <figure className={'lab-scope lab-scope-' + view}>
    <figcaption>
      <span>{view[0].toUpperCase() + view.slice(1)}</span>
      {view === 'waveform' && <button type="button" className={'lab-scope-freeze' + (frozen ? ' active' : '')} title={frozen ? 'Resume live waveform' : 'Freeze waveform to inspect static shape'} onClick={() => setFrozen(!frozen)}>{frozen ? 'Resume' : 'Freeze'}</button>}
    </figcaption>
    <canvas ref={canvas} role="img" aria-label={`Live ${view}`} />
  </figure>
}
