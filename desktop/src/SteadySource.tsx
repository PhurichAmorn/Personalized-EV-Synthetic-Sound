import { useEffect, useRef, useState, useImperativeHandle, type Ref } from 'react'
import SoundWaveform from './SoundWaveform'
import SourceCharacterPanel from './SourceCharacterPanel'
import { sourceAudioBuffers } from './sourceDesigner'
import { simulatedDrive, SIMULATED_DRIVE_SECONDS } from './simulatedDrive'
import { smoothParameter, driveEnvelopeTarget, createChorus } from './audioAutomation'
import { climbTargets } from './sourceClimb'
import { GranularPlayer, type GranularMode } from './granularPlayer'
import { drivingSoundTargets, responseRiseSeconds, type SoundResponse, type DrivingInput } from './drivingSoundMapping'

type Voice = { sources: (AudioBufferSourceNode | GranularPlayer)[]; gains: GainNode[]; filter: BiquadFilterNode; level: GainNode; dry: GainNode; wet: GainNode; drive: GainNode; expression: GainNode; driveTarget?: number; response?: SoundResponse; granularMode?: GranularMode; authored?: boolean; sourceRevision?: number }
export type SourceHandle = { start: (refresh?: boolean) => void; stop: () => void; auditionContext: () => Record<string, unknown>; audition: (urls: string[], input: 'driving' | 'simulated', label: string) => Promise<boolean | string> }
const STEMS = ['body', 'pad', 'glass', 'air']
const granularWorklets = new WeakMap<AudioContext, Promise<void>>()  // processor modules are registered per AudioContext
export default function SteadySource({ blocked, onPlay, driving, onPlayingChange, onError, compact = false, headless = false, ref, granularMode, onModeChange }: { granularMode: GranularMode; onModeChange: (mode: GranularMode) => void; ref?: Ref<SourceHandle>; compact?: boolean; headless?: boolean; blocked: boolean; onPlay: () => void; driving?: DrivingInput; onError?: (message: string) => void; onPlayingChange?: (playing: boolean) => void }) {
  const context = useRef<AudioContext | null>(null)
  const buffers = useRef<AudioBuffer[] | null>(null)
  const voice = useRef<Voice | null>(null)
  const externalSourceUrls = useRef<string[] | null>(null)
  const [externalLabel, setExternalLabel] = useState('')
  const auditionPending = useRef<((ready: boolean | string) => void) | null>(null)
  const [auditionRequest, setAuditionRequest] = useState(0)
  const generatedSource = useRef<Float32Array[][] | null>(null)
  const generatedBuffers = useRef<AudioBuffer[] | null>(null)
  const [sourceRevision, setSourceRevision] = useState(0)
  const [trialRequested, setTrialRequested] = useState(false)
  const [sourceReplayRequested, setSourceReplayRequested] = useState(false)
  const analyser = useRef<AnalyserNode | null>(null)
  const request = useRef(0)
  const startRequested = useRef(false)
  const refreshRequested = useRef(false)
  const recorder = useRef<MediaRecorder | null>(null)
  const [recording, setRecording] = useState(false)
  const [capture, setCapture] = useState<{ url: string; extension: string } | null>(null)
  useEffect(() => () => { if (capture) URL.revokeObjectURL(capture.url) }, [capture])
  const stopRecording = () => { if (recorder.current?.state === 'recording') recorder.current.stop() }
  const record = () => {
    if (recording) { stopRecording(); return }
    const audio = context.current, current = voice.current
    if (!audio || !current) return
    try {
      if (typeof MediaRecorder === 'undefined') throw Error('Audio recording is unavailable in this browser.')
      const destination = audio.createMediaStreamDestination()
      const next = new MediaRecorder(destination.stream)
      current.level.connect(destination)
      const chunks: Blob[] = []
      next.ondataavailable = event => { if (event.data.size) chunks.push(event.data) }
      const release = () => { try { current.level.disconnect(destination) } catch { /* Source may already have stopped. */ } destination.stream.getTracks().forEach(track => track.stop()); recorder.current = null; setRecording(false) }
      next.onstop = () => {
        if (chunks.length) setCapture({ url: URL.createObjectURL(new Blob(chunks, { type: next.mimeType })), extension: next.mimeType.includes('mp4') ? 'mp4' : next.mimeType.includes('ogg') ? 'ogg' : 'webm' })
        release()
      }
      next.onerror = () => { setError('Recording failed. Try recording again.'); if (next.state !== 'inactive') next.stop() }
      next.start(); recorder.current = next; setRecording(true)
    } catch (problem) { setError(problem instanceof Error ? problem.message : 'Could not record audio.') }
  }
  const [playing, setPlaying] = useState(false)
  const [loading, setLoading] = useState(false)
  const [volume, setVolume] = useState(.7)
  const [spatial, setSpatial] = useState(true)
  const [climb, setClimb] = useState(0)
  const [method, setMethod] = useState<'granular' | 'sample'>('granular')
  const [inputMode, setInputMode] = useState<'driving' | 'manual' | 'simulated'>('driving')
  const [response, setResponse] = useState<SoundResponse>('exponential')
  const [evolvingSource, setEvolvingSource] = useState<'transformed' | 'authored'>('transformed')
  const [preferredStyle, setPreferredStyle] = useState<GranularMode | 'none' | null>(null)
  const [simulationTime, setSimulationTime] = useState(0)
  const simulationStart = useRef(0)
  const settingsRef = useRef({ method, inputMode, response, granularMode, evolvingSource, sourceRevision })
  settingsRef.current = { method, inputMode, response, granularMode, evolvingSource, sourceRevision }
  const [stale, setStale] = useState(false)
  const inputRef = useRef(driving)
  const receivedAt = useRef(performance.now())
  const playingCallback = useRef(onPlayingChange)
  playingCallback.current = onPlayingChange
  useEffect(() => { inputRef.current = driving; receivedAt.current = performance.now(); setStale(false) }, [driving])
  useEffect(() => { playingCallback.current?.(playing) }, [playing])
  useEffect(() => () => playingCallback.current?.(false), [])
  const [error, setError] = useState('')
  const errorCallback = useRef(onError)
  errorCallback.current = onError
  useEffect(() => { errorCallback.current?.(error) }, [error])
  const controls = useRef({ climb, spatial, volume })
  controls.current = { climb, spatial, volume }
  const stop = (preserveAudition = false) => {
    startRequested.current = false
    stopRecording()
    request.current++
    const old = voice.current, audio = context.current
    voice.current = null
    if (old && audio) {
      old.level.gain.cancelAndHoldAtTime(audio.currentTime)
      old.level.gain.linearRampToValueAtTime(0, audio.currentTime + .08)
      old.sources.forEach(source => source.stop(audio.currentTime + .09))
    }
    if (!preserveAudition) setPlaying(false)
    setLoading(false)
  }
  useEffect(() => { if (blocked) stop() }, [blocked])
  useEffect(() => {
    setPlaying(false); setLoading(false)
    return () => {
      auditionPending.current?.(false); auditionPending.current = null
      if (recorder.current) { recorder.current.onstop = null; recorder.current.ondataavailable = null; if (recorder.current.state === 'recording') recorder.current.stop(); recorder.current.stream.getTracks().forEach(track => track.stop()) }
      request.current++
      voice.current?.sources.forEach(source => source.stop(context.current?.currentTime ?? 0))
      void context.current?.close()
      context.current = null; buffers.current = null; voice.current = null; analyser.current = null
    }
  }, [])
  const applyGesture = (current: Voice, value: number, immediate = false) => {
    const { inputMode, response, granularMode, evolvingSource, sourceRevision } = settingsRef.current
    const audio = context.current
    if (!audio) return
    const input = inputMode === 'simulated' ? simulatedDrive(audio.currentTime - simulationStart.current) : inputRef.current
    const target = inputMode !== 'manual' ? drivingSoundTargets(input ?? { running: false, starting: false, speedKmh: 0, throttle: 0, motorLoad: null }, inputMode === 'driving' && performance.now() - receivedAt.current > 750, response, granularMode) : { ...climbTargets(value), driveGain: 1, loopHold: 0, cycleSpeed: 1 }
    const set = (param: AudioParam, value: number, smoothing = .15) => {
      if (immediate) param.setValueAtTime(value, audio.currentTime)
      else smoothParameter(param, value, audio.currentTime, smoothing)
    }
    const authored = granularMode === 'evolving' && evolvingSource === 'authored'
    if ((current.authored !== authored || current.sourceRevision !== sourceRevision) && buffers.current) {
      current.sources.forEach((source, index) => {
        if (source instanceof GranularPlayer) source.setSource(!authored && generatedBuffers.current ? generatedBuffers.current[index] : buffers.current![index + (authored ? 4 : 0)])
      })
    }
    current.sourceRevision = sourceRevision
    current.authored = authored
    current.sources.forEach((source, index) => {
      if (source instanceof GranularPlayer) {
        set(source.evolution, index < 3 && granularMode === 'evolving' && !authored ? 1 : 0, .05)
        set(source.cycleSpeed, index < 3 && !authored ? target.cycleSpeed : 1)
        set(source.loopHold, index < 3 ? target.loopHold : 0, .05)
      }
    })
    current.granularMode = granularMode
    const tonalRate = target.rate
    // Driving transposes the tonal layers together; manual mode retains the anchored comparison.
    set(current.sources[0].playbackRate, inputMode !== 'manual' ? tonalRate : 1, .35)
    if (current.driveTarget !== target.driveGain || current.response !== response) {
      const envelope = driveEnvelopeTarget(target.driveGain, inputMode !== 'manual' ? responseRiseSeconds[response] : 1.4, target.driveGain < (current.driveTarget ?? 0))
      if (immediate) {
        current.drive.gain.setValueAtTime(0, audio.currentTime)
        current.expression.gain.setValueAtTime(0, audio.currentTime)
      }
      smoothParameter(current.drive.gain, envelope.gain, audio.currentTime, envelope.smoothing)
      smoothParameter(current.expression.gain, envelope.gain, audio.currentTime, envelope.smoothing)
      current.driveTarget = target.driveGain
      current.response = response
    }
    set(current.sources[1].playbackRate, tonalRate, .35)
    set(current.sources[2].playbackRate, tonalRate, .35)
    ;[target.bodyGain, target.padGain, target.glassGain, target.airGain].forEach((gain, i) => set(current.gains[i].gain, gain))
    set(current.filter.frequency, target.cutoff)
  }
  useEffect(() => { if (voice.current) applyGesture(voice.current, climb) }, [climb, driving, inputMode, response, granularMode, evolvingSource, sourceRevision])
  useEffect(() => {
    if (!playing || inputMode !== 'driving') return
    const timer = window.setInterval(() => { setStale(performance.now() - receivedAt.current > 750); if (voice.current) applyGesture(voice.current, controls.current.climb) }, 100)
    return () => window.clearInterval(timer)
  }, [playing, inputMode, response, granularMode])
  const play = async (refresh = false) => {
    if ((playing || loading) && !refresh) { stop(); return }
    if (refresh) {
      const previousContext = context.current
      stop(true)
      context.current = null; analyser.current = null; buffers.current = null
      if (previousContext) window.setTimeout(() => { void previousContext.close() }, 120)
    }
    const token = ++request.current
    setLoading(true); setError(''); onPlay()
    try {
      if (!context.current) {
        context.current = new AudioContext()
        analyser.current = context.current.createAnalyser(); analyser.current.fftSize = 2048
        analyser.current.connect(context.current.destination)
      }
      const audio = context.current
      await audio.resume()
      let decoded = buffers.current
      if (!decoded) {
        decoded = await Promise.all([...['steady', 'evolving'].flatMap(kind => STEMS.map(name => `/audio/original_${kind}_${name}.wav?v=17`)), '/audio/original_steady_room_ir.wav?v=2'].map(async url => {
          const response = await fetch(url, { cache: 'no-store' })
          if (!response.ok) throw Error('Source audio is unavailable.')
          return audio.decodeAudioData(await response.arrayBuffer())
        }))
      }
      // Always load, and per context: the method can switch to granular during the awaits above, and a stale
      // play() must not leave the old context's module promise in place for a new context.
      let worklet = granularWorklets.get(audio)
      if (!worklet) { worklet = audio.audioWorklet.addModule(`/audio/granular-processor.mjs?v=9&refresh=${Date.now()}`); granularWorklets.set(audio, worklet) }
      try { await worklet } catch (problem) { granularWorklets.delete(audio); throw problem }
      if (token !== request.current) return
      buffers.current = decoded
      generatedBuffers.current = generatedSource.current ? [...sourceAudioBuffers(audio, generatedSource.current), decoded[3]] : null
      if (externalSourceUrls.current) {
        const external = await Promise.all(externalSourceUrls.current.map(async url => {
          const response = await fetch(url); if (!response.ok) throw Error('Could not load candidate audio.'); return audio.decodeAudioData(await response.arrayBuffer())
        }))
        if (token !== request.current) return false
        generatedBuffers.current = external
      }
      const { method: selectedMethod, granularMode: selectedMode, evolvingSource: selectedSource } = settingsRef.current
      const bus = audio.createGain(), level = audio.createGain(), dry = audio.createGain(), wet = audio.createGain(), drive = audio.createGain(), expression = audio.createGain()
      const filter = audio.createBiquadFilter(), convolver = audio.createConvolver()
      filter.type = 'lowpass'; filter.Q.value = .5
      convolver.buffer = decoded[8]
      const chorus = createChorus(audio)
      bus.connect(chorus.input); chorus.output.connect(drive); drive.connect(expression); expression.connect(dry); dry.connect(level); expression.connect(convolver); convolver.connect(wet); wet.connect(level); level.connect(analyser.current!)
      filter.connect(bus)
      dry.gain.value = controls.current.spatial ? .68 : 1; wet.gain.value = controls.current.spatial ? .32 : 0
      const gains = STEMS.map(() => audio.createGain())
      const selectedBuffers = selectedMode === 'evolving' && selectedSource === 'authored' ? decoded.slice(4, 8) : generatedBuffers.current ?? decoded.slice(0, 4)
      const sources = STEMS.map((_, i) => {
        let source: AudioBufferSourceNode | GranularPlayer
        if (selectedMethod === 'granular') source = new GranularPlayer(audio, selectedBuffers[i])
        else { source = audio.createBufferSource(); source.buffer = selectedBuffers[i]; source.loop = true }
        source.connect(gains[i]); gains[i].connect(i === 1 || i === 2 ? filter : bus)
        return source
      })
      let remaining = sources.length
      sources.forEach(source => { source.onended = () => {
        source.disconnect()
        if (--remaining === 0) { gains.forEach(gain => gain.disconnect()); filter.disconnect(); bus.disconnect(); chorus.dispose(); dry.disconnect(); wet.disconnect(); convolver.disconnect(); level.disconnect(); drive.disconnect(); expression.disconnect() }
      } })
      const current = { sources, gains, filter, level, dry, wet, drive, expression, granularMode: selectedMode, sourceRevision: settingsRef.current.sourceRevision, authored: selectedMode === 'evolving' && selectedSource === 'authored' }
      simulationStart.current = audio.currentTime; setSimulationTime(0)
      voice.current = current; applyGesture(current, controls.current.climb, true)
      const when = audio.currentTime + .02
      level.gain.setValueAtTime(0, audio.currentTime); level.gain.linearRampToValueAtTime(controls.current.volume, when + .3)
      sources.forEach(source => source.start(when))
      setPlaying(true); setLoading(false)
      return true
    } catch (problem) {
      if (token === request.current) { stop(); playingCallback.current?.(false); const message = problem instanceof Error ? problem.message : 'Could not play the source.'; setError(message); return message }
    }
  }
  useEffect(() => {
    if (!playing || inputMode !== 'simulated') return
    const timer = window.setInterval(() => {
      const elapsed = Math.min(SIMULATED_DRIVE_SECONDS, (context.current?.currentTime ?? 0) - simulationStart.current)
      setSimulationTime(elapsed)
      if (voice.current) applyGesture(voice.current, controls.current.climb)
      if (elapsed >= SIMULATED_DRIVE_SECONDS) stop()
    }, 50)
    return () => window.clearInterval(timer)
  }, [playing, inputMode, response, granularMode, evolvingSource])
  useEffect(() => {
    if (!trialRequested && !auditionPending.current && voice.current && inputMode === 'simulated') void play(true)
  }, [granularMode, evolvingSource, inputMode])
  useEffect(() => {
    if (sourceReplayRequested) { setSourceReplayRequested(false); if (settingsRef.current.inputMode === 'simulated' && !blocked) void play(true) }
  }, [sourceReplayRequested, sourceRevision])
  useEffect(() => {
    if (trialRequested && granularMode === 'rise' && inputMode === 'simulated' && method === 'granular') { setTrialRequested(false); void play(true) }
  }, [trialRequested, granularMode, inputMode, method])
  useEffect(() => {
    if (startRequested.current && method === 'granular') {
      startRequested.current = false
      const refresh = refreshRequested.current
      refreshRequested.current = false
      void play(refresh)
    }
  }, [method])
  useEffect(() => {
    if (!auditionRequest || !auditionPending.current) return
    const done = auditionPending.current
    void play(true).then(ready => { if (auditionPending.current === done) auditionPending.current = null; done(ready === true ? true : typeof ready === 'string' ? ready : false) })
  }, [auditionRequest])
  useImperativeHandle(ref, () => ({ start: (refresh = false) => {
    setInputMode('driving')
    if (method !== 'granular') {
      stop(refresh)
      startRequested.current = true
      refreshRequested.current = refresh
      setMethod('granular')
    } else if (refresh || (!voice.current && !loading)) void play(refresh)
  }, stop, auditionContext: () => ({ volume: controls.current.volume, candidateId: externalSourceUrls.current?.[0].split('/')[3] ?? null, input: settingsRef.current.inputMode === 'simulated' ? 'simulated' : 'live', style: settingsRef.current.granularMode, response: settingsRef.current.response, spatial: controls.current.spatial }), audition: (urls, input, label) => {
    if (urls.length !== 4 || !urls.every(url => /^\/audio\/source-search-cache\/[a-f0-9]{32}\/stem-[0-2]\.wav$/.test(url) || url === '/audio/original_steady_air.wav?v=17')) return Promise.resolve(false)
    auditionPending.current?.(false)
    stop(); externalSourceUrls.current = urls; setExternalLabel(label); setMethod('granular'); setInputMode(input); setEvolvingSource('transformed'); setSpatial(true); setResponse('exponential')
    return new Promise(resolve => { auditionPending.current = resolve; setAuditionRequest(value => value + 1) })
  } }))
  if (headless) return null
  const displayedInput = inputMode === 'simulated' ? simulatedDrive(simulationTime) : driving
  const target = inputMode !== 'manual' && displayedInput ? drivingSoundTargets(displayedInput, false, response, granularMode) : climbTargets(climb)
  const displayedPitch = target.semitones
  return <section className="reference-reconstruction steady-source-panel" aria-labelledby="steady-source-title">
    <h3 id="steady-source-title">Original granular template <small>{compact ? 'Controlled by START · power and speed' : inputMode === 'driving' ? 'Live driving inputs · fixed mapping' : inputMode === 'simulated' ? 'Simulated style comparison' : 'Manual comparison'}</small></h3>
    <div className="sound-editor-transport">
      <label hidden={compact}>Granular mode <select className="sound-preset-select" aria-label="Sound Lab granular mode" disabled={method !== 'granular'} value={granularMode} onChange={event => onModeChange(event.target.value as GranularMode)}><option value="steady">Steady</option><option value="rise">Rise</option><option value="evolving">Evolving</option></select></label>
      <label>Sound response <select className="sound-preset-select" aria-label="Throttle sound response" disabled={!!externalLabel} value={response} onChange={event => setResponse(event.target.value as SoundResponse)}><option value="exponential">Exponential</option><option value="linear">Linear</option><option value="logarithmic">Logarithmic</option></select></label>
    </div>
    {!compact && granularMode === 'evolving' && <label>Evolving source <select className="sound-preset-select" aria-label="Evolving source arrangement" value={evolvingSource} disabled={method !== 'granular' || !!externalLabel} onChange={event => setEvolvingSource(event.target.value as 'transformed' | 'authored')}><option value="transformed">Shared source · transformed rises</option><option value="authored">Previous authored rising source</option></select></label>}
    {!compact && inputMode === 'simulated' && <div className="sound-editor-transport" aria-label="Style comparison">
      <span>Same 22-second drive · {simulationTime.toFixed(1)} s · 0–120 km/h and stop</span>
      <button type="button" disabled={loading} onClick={() => void play(true)}>Replay drive</button>
      <button type="button" onClick={() => setPreferredStyle(granularMode)}>Prefer {granularMode}</button>
      <button type="button" onClick={() => setPreferredStyle('none')}>No preference</button>
      {preferredStyle && <span role="status">{preferredStyle === 'none' ? 'No style preference' : `Preferred style: ${preferredStyle}`} · this visit only</span>}
    </div>}
    <div className="sound-editor-transport" hidden={compact}>
      <select className="sound-preset-select" aria-label="Source playback method" disabled={!!externalLabel} value={method} onChange={event => { stop(); if (event.target.value === 'sample' && inputMode === 'simulated') setInputMode('manual'); setMethod(event.target.value as 'granular' | 'sample') }}>
        <option value="granular">Granular synthesis</option><option value="sample">Ordinary sample playback</option>
      </select>
      <button type="button" className="sound-play" onClick={() => void play()}>{playing ? 'Stop source' : loading ? 'Cancel loading' : 'Play source'}</button>
      <button type="button" disabled={!playing} onClick={record}>{recording ? 'Stop recording' : 'Record acceleration'}</button>
      {capture && <a href={capture.url} download={`ev-acceleration.${capture.extension}`}>Download recording</a>}
      <select className="sound-preset-select" aria-label="Sound control input" disabled={!!externalLabel} value={inputMode} onChange={event => setInputMode(event.target.value as 'driving' | 'manual' | 'simulated')}><option value="driving">Driving inputs</option><option value="manual">Manual comparison</option><option value="simulated" disabled={method !== 'granular'}>Simulated style comparison</option></select>
      {inputMode === 'manual' ? <label className="sound-slider sound-climb-slider"><span>Resting → full expression<output>{Math.round(climb * 100)}%</output></span><input type="range" min="0" max="1" step=".005" value={climb} onChange={event => setClimb(Number(event.target.value))} /><small>Upper voices +{target.semitones.toFixed(1)} semitones · foundation anchored</small></label> : <span className="source-driving-readout">{stale && playing && inputMode === 'driving' ? 'Telemetry stale · sound muted' : displayedInput ? `${displayedInput.speedKmh.toFixed(0)} km/h · Pedal ${Math.round(displayedInput.throttle * 100)}% · Load ${displayedInput.motorLoad === null ? 'unavailable' : Math.round(displayedInput.motorLoad * 100) + '%'} · Pitch ${displayedPitch >= 0 ? '+' : ''}${displayedPitch.toFixed(1)} st` : 'Waiting for driving inputs'}</span>}
      <label className="sound-check"><input type="checkbox" disabled={!!externalLabel} checked={spatial} onChange={event => {
        const enabled = event.target.checked; setSpatial(enabled)
        if (voice.current && context.current) {
          smoothParameter(voice.current.dry.gain, enabled ? .68 : 1, context.current.currentTime, .1)
          smoothParameter(voice.current.wet.gain, enabled ? .32 : 0, context.current.currentTime, .1)
        }
      }} />Spatial reverb</label>
      <label className="sound-slider"><span>Source listening volume<output>{Math.round(volume * 100)}%</output></span><input type="range" min="0" max="1" step=".01" value={volume} onChange={event => {
        const value = Number(event.target.value); setVolume(value)
        if (voice.current && context.current) smoothParameter(voice.current.level.gain, value, context.current.currentTime, .03)
      }} /></label>
      <a href={`/audio/original_${granularMode === 'evolving' && evolvingSource === 'authored' ? 'evolving' : 'steady'}_source.wav?v=17`} download>{generatedSource.current || externalSourceUrls.current ? 'Download original source' : 'Download source'}</a>
      {granularMode !== 'evolving' && <a href="/audio/original_steady_spatial.wav?v=9" download>Download spatial version</a>}
    </div>
    {externalLabel && <p>Source discovery audition: {externalLabel} <button type="button" onClick={() => { stop(); externalSourceUrls.current = null; setExternalLabel(''); generatedBuffers.current = null; setSourceRevision(value => value + 1) }}>Leave candidate audition</button></p>}
    <SoundWaveform analyser={analyser} active={playing} />
    <SourceCharacterPanel hidden={compact} sharedSource={granularMode !== 'evolving' || evolvingSource !== 'authored'} blocked={loading || method !== 'granular' || !!externalLabel} onTrial={() => {
      setTrialRequested(true); setMethod('granular'); onModeChange('rise'); setInputMode('simulated'); setEvolvingSource('transformed'); setSpatial(true); setResponse('exponential')
    }} onSource={stems => {
      externalSourceUrls.current = null; setExternalLabel('')
      generatedSource.current = stems
      generatedBuffers.current = context.current && buffers.current ? [...sourceAudioBuffers(context.current, stems), buffers.current[3]] : null
      setEvolvingSource('transformed'); setSourceRevision(value => value + 1); if (settingsRef.current.inputMode === 'simulated') setSourceReplayRequested(true)
    }} onReset={() => { externalSourceUrls.current = null; setExternalLabel(''); generatedSource.current = null; generatedBuffers.current = null; setSourceRevision(value => value + 1); if (settingsRef.current.inputMode === 'simulated') setSourceReplayRequested(true) }} />
    <p hidden={compact}>{inputMode !== 'manual' ? 'Steady follows power; Rise follows speed with acceleration expression; Evolving layers overlapping pitch rises on the shared source. Pedal and motor load control brightness and layer balance. Sound mutes when the vehicle stops running or telemetry becomes stale.' : 'Manual comparison keeps the foundation anchored.'} Room timing stays fixed. {method === 'granular' ? 'Granular: audio-thread rendering, 160 ms grains with waveform-aligned overlap, fixed scan speed, no random pitch or scatter.' : 'Sample playback: pitch changes also change source traversal speed.'}</p>
    {error && <p role="alert">{error}</p>}
  </section>
}
