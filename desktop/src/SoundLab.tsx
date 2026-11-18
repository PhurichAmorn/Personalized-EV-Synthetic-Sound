import { useEffect, useRef, useState, type RefObject } from 'react'
import type { State } from './App'
import type { GranularMode } from './granularPlayer'
import { clamp, LabPlayer } from './labEngine'
import { isLiveRecipe, liveSound } from './levels'
import { liveStems } from './voiceCache'
import { simulatedDrive, SIMULATED_DRIVE_SECONDS } from './simulatedDrive'
import { drawColumn } from './OverlayGraphs'

const logX = (hz: number) => Math.log(hz / 40) / Math.log(300)  // 40 Hz-12 kHz

/** Sound Lab = small listening bench: pick one of your saved sounds, hear it on the simulated 22 s drive (looped) in Rising or Evolving, watch the graphs.
 * Picking here also sets the GS sound (same list as the dashboard). Nothing is edited or saved. */
export default function SoundLab({ state, onCommand, onStart, stopToken }: { state: State; onCommand: (name: string, payload?: Record<string, unknown>) => Promise<unknown> | void; onStart: () => void; stopToken: number }) {
  const [player] = useState(() => new LabPlayer())
  const analyser = useRef<AnalyserNode | null>(null)
  const [mode, setMode] = useState<GranularMode>('rise')
  const [volume, setVolume] = useState(.7)
  const [playing, setPlaying] = useState(false)
  const [error, setError] = useState('')
  const my = state.mySound, recipe = my && isLiveRecipe(my.recipe) ? my.recipe : null
  const stop = () => { player.stop(); setPlaying(false) }
  useEffect(() => () => player.close(), [player])
  useEffect(() => { if (stopToken) stop() }, [stopToken])  // something else started playing
  useEffect(() => { if (playing) stop() }, [my?.id, mode])  // another sound or motion: press play again
  useEffect(() => { player.volume = volume }, [volume])
  const play = async () => {
    if (!recipe) return
    onStart(); setError('')
    try {
      const { plain, fx, travel } = liveSound(recipe)
      analyser.current = null
      const started = await player.play(my!.id, liveStems(recipe), fx, plain.rootHz, 'simulated', () => ({ input: undefined, stale: false }), time => simulatedDrive(time % SIMULATED_DRIVE_SECONDS), mode, travel)
      analyser.current = player.analyser
      if (started) setPlaying(true)
    } catch (problem) { stop(); setError(problem instanceof Error ? problem.message : 'Could not play the sound.') }
  }
  return <section className="lab" aria-label="Listening bench">
    <header className="lab-head"><div><small>LISTENING BENCH</small><h2>Sound Lab</h2></div>
      <div className="lab-transport">
        {!!state.mySounds?.length && <select className="vehicle-selector" aria-label="Sound to listen to" value={my?.session ?? ''} onChange={event => onCommand('mySound', { id: event.target.value })}>{state.mySounds.map(s => <option key={s.session} value={s.session}>{s.created.slice(5, 16).replace('T', ' ')} · {s.label || 'sound'}</option>)}</select>}
        <span className="lab-seg">{(['rise', 'evolving'] as const).map(item => <button key={item} type="button" className={mode === item ? 'active' : ''} onClick={() => setMode(item)}>{item === 'rise' ? 'Rising' : 'Evolving'}</button>)}</span>
        <button type="button" disabled={!recipe} onClick={() => void (playing ? stop() : play())}>{playing ? 'Stop' : 'Play'}</button>
        <label className="lab-volume">Vol<input type="range" min="0" max="1" step=".01" value={volume} onChange={event => setVolume(+event.target.value)} /></label>
      </div>
    </header>
    {!recipe && <p className="lab-note">No saved sound yet. Finish a Personalize session first.</p>}
    {error && <p className="lab-error" role="alert">{error}</p>}
    <p className="lab-note">Plays your saved sound over the simulated drive (speed climbs, lifts, brakes), looping. Choosing here also sets the GS sound.</p>
    <div className="lab-right" style={{ position: 'static' }}>
      {(['spectrogram', 'spectrum', 'waveform'] as const).map(view => <Scope key={view} analyser={analyser} active={playing} view={view} />)}
    </div>
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
