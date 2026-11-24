import { useEffect, useRef, useState, type RefObject } from 'react'
import type { State } from './App'
import type { GranularMode } from './granularPlayer'
import { clamp, LabPlayer } from './labEngine'
import { isLiveRecipe, liveSound, type LiveRecipe } from './levels'
import { liveStems } from './voiceCache'
import { simulatedDrive, SIMULATED_DRIVE_SECONDS } from './simulatedDrive'
import { drawColumn } from './OverlayGraphs'
import type { DrivingInput } from './drivingSoundMapping'

type Blocks = Record<string, string | number | boolean | null>
type Options = { bodies: string[]; tops: string[]; partners: Record<string, string[]>; levels: string[]; pitches: number[]; buzz: number[]; names: Record<string, string>; default: Blocks; synthTops: string[] }
type Built = { recipe?: LiveRecipe & { label?: string; blocks?: Blocks; checked?: boolean }; error?: string }
const BUZZ_NAMES = ['Off', 'Some', 'Strong']

const logX = (hz: number) => Math.log(hz / 40) / Math.log(300)  // 40 Hz-12 kHz

/** Sound Lab = listening bench and block builder: build a sound from the session's own blocks (or load your winner's blocks), hear it either on the
 * simulated 22 s sweep (looped) or driven live by the simulator, in Rising or Evolving, and watch the graphs. Nothing is saved. */
export default function SoundLab({ state, onCommand, onStart, stopToken, live }: { state: State; onCommand: (name: string, payload?: Record<string, unknown>) => Promise<unknown> | void; onStart: () => void; stopToken: number; live: () => { input: DrivingInput | undefined; stale: boolean } }) {
  const [player] = useState(() => new LabPlayer())
  const analyser = useRef<AnalyserNode | null>(null)
  const [mode, setMode] = useState<GranularMode>('rise')
  const [volume, setVolume] = useState(.7)
  const [playing, setPlaying] = useState(false)
  const [error, setError] = useState('')
  const [via, setVia] = useState<'sweep' | 'simulator'>('sweep')  // what drives the sound: the simulated 22 s sweep, or the simulator (W/S, controller)
  const [options, setOptions] = useState<Options | null>(null)
  const [blocks, setBlocks] = useState<Blocks>({})
  const [built, setBuilt] = useState<Built>({})
  useEffect(() => { void Promise.resolve(onCommand('blockOptions')).then(o => { if (o) { setOptions(o as Options); setBlocks((o as Options).default) } }) }, [])
  // The block sound is built by the same code a session uses (safe-area table, brightness to low-pass, loudness): the backend returns the live recipe.
  useEffect(() => {
    if (!options) return
    const timer = setTimeout(() => void Promise.resolve(onCommand('blockBuild', { blocks, motion: mode })).then(result => setBuilt((result ?? {}) as Built)).catch(problem => setBuilt({ error: String(problem) })), 200)
    return () => clearTimeout(timer)
  }, [blocks, mode, options])
  const winnerBlocks = (state.mySound && isLiveRecipe(state.mySound.recipe) ? (state.mySound.recipe as { blocks?: Blocks }).blocks : undefined) ?? null
  const recipe = built.recipe ?? null
  const soundId = 'lab-build-' + (built.recipe?.label ?? '')
  const change = (patch: Blocks) => { setBlocks(current => ({ ...current, ...patch, ...(patch.top && !(options?.partners[patch.top as string] ?? []).includes(current.partner as string) ? { partner: null } : {}) })) }
  const stop = () => { player.stop(); setPlaying(false) }
  useEffect(() => () => player.close(), [player])
  useEffect(() => { if (stopToken) stop() }, [stopToken])  // something else started playing
  useEffect(() => { if (playing && built.recipe) void play(via) }, [built.recipe])  // a changed block restarts the sound the same way
  useEffect(() => { player.volume = volume }, [volume])
  const play = async (how: 'sweep' | 'simulator') => {
    if (!recipe) return
    onStart(); setError(''); setVia(how)
    try {
      if (how === 'simulator') await onCommand('vehicleStart')  // the car runs; drive it with W/S or a controller
      const { plain, fx, travel } = liveSound(recipe)
      analyser.current = null
      const started = await player.play(soundId, liveStems(recipe), fx, plain.rootHz, how === 'simulator' ? 'live' : 'simulated', how === 'simulator' ? live : () => ({ input: undefined, stale: false }), time => simulatedDrive(time % SIMULATED_DRIVE_SECONDS), mode, travel)
      analyser.current = player.analyser
      if (started) setPlaying(true)
    } catch (problem) { stop(); setError(problem instanceof Error ? problem.message : 'Could not play the sound.') }
  }
  return <section className="lab" aria-label="Listening bench">
    <div className="lab-fixed">
    <header className="lab-head"><div><small>LISTENING BENCH</small><h2>Sound Lab</h2></div>
      <div className="lab-transport">
        <span className="lab-seg">{(['rise', 'evolving'] as const).map(item => <button key={item} type="button" className={mode === item ? 'active' : ''} onClick={() => setMode(item)}>{item === 'rise' ? 'Rising' : 'Evolving'}</button>)}</span>
        {(['sweep', 'simulator'] as const).map(how => <button key={how} type="button" disabled={!recipe} aria-pressed={playing && via === how} onClick={() => void (playing && via === how ? stop() : play(how))}>{playing && via === how ? 'Stop' : how === 'sweep' ? '▶ Sound sweep' : '▶ Simulator'}</button>)}
        <label className="lab-volume">Vol<input type="range" min="0" max="1" step=".01" value={volume} onChange={event => setVolume(+event.target.value)} /></label>
      </div>
    </header>
    {error && <p className="lab-error" role="alert">{error}</p>}
    <div className="lab-scopes">
      {(['spectrogram', 'spectrum', 'waveform'] as const).map(view => <Scope key={view} analyser={analyser} active={playing} view={view} />)}
    </div>
    </div>
    <section className="lab-builder" aria-label="Build a sound">
      <h3>Build a sound <small>the session's own blocks, safe-area table and loudness</small></h3>
      <p className="lab-note">Sound sweep plays the sound over the simulated drive (speed climbs, lifts, brakes), looping. Simulator plays it driven live by the simulator: drive with W/S or a controller. Change a block and the sound updates.</p>
      <div className="lab-chips"><button type="button" disabled={!winnerBlocks || !options} title={winnerBlocks ? 'Fill the blocks from your latest saved sound' : 'No saved building-block sound yet'} onClick={() => setBlocks({ ...options!.default, ...Object.fromEntries(Object.entries(winnerBlocks!).filter(([key]) => key in options!.default)) })}>Load from winner</button>
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
  </section>
}

/** One live view of the output; Sound Lab shows all three at once (spectrogram, spectrum, waveform), each with its own draw loop. */
function Scope({ analyser, active, view }: { analyser: RefObject<AnalyserNode | null>; active: boolean; view: 'spectrum' | 'spectrogram' | 'waveform' }) {
  const canvas = useRef<HTMLCanvasElement>(null)
  const live = useRef(active)
  live.current = active
  const wake = useRef(() => {})
  useEffect(() => {
    const element = canvas.current, draw = element?.getContext('2d')
    if (!element || !draw) return
    const freq = new Float32Array(2048), samples = new Float32Array(4096)
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
      node!.getFloatFrequencyData(freq); node!.getFloatTimeDomainData(samples)
      const binHz = node!.context.sampleRate / 4096
      if (view === 'spectrogram') {
        drawColumn(element, hz => freq[Math.round(hz / binHz)] ?? -140, 2)  // shared with the overlay graph
      } else {
        draw.fillStyle = '#101010'; draw.fillRect(0, 0, width, height)
        draw.strokeStyle = '#2b2b2b'; draw.beginPath()
        for (const hz of [100, 1000, 10000]) { const x = logX(hz) * width; draw.moveTo(x, 0); draw.lineTo(x, height) }
        draw.stroke()
        draw.strokeStyle = ink; draw.lineWidth = 1.5; draw.beginPath()
        if (view === 'spectrum') for (let x = 0; x < width; x++) {
          const db = freq[Math.round(40 * 300 ** (x / width) / binHz)] ?? -140, y = height - clamp((db + 120) / 110, 0, 1) * height
          if (x) draw.lineTo(x, y); else draw.moveTo(x, y)
        } else {
          let trigger = 0
          for (let i = 1; i < 2048; i++) if (samples[i - 1] <= 0 && samples[i] > 0) { trigger = i; break }
          for (let i = 0; i < 2048; i++) { const x = i / 2047 * width, y = height / 2 - samples[trigger + i] * height * .9; if (i) draw.lineTo(x, y); else draw.moveTo(x, y) }
        }
        draw.stroke()
      }
    }
    wake.current = () => { if (!frame) frame = requestAnimationFrame(render) }
    wake.current()
    return () => { cancelAnimationFrame(frame); frame = 0; wake.current = () => {}; observer.disconnect() }
  }, [view, analyser])
  useEffect(() => { if (active) wake.current() }, [active])
  return <figure className={'lab-scope lab-scope-' + view}>
    <figcaption>{view[0].toUpperCase() + view.slice(1)}</figcaption>
    <canvas ref={canvas} role="img" aria-label={`Live ${view}`} />
  </figure>
}
