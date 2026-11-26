import { useEffect, useRef, useState, useImperativeHandle, type Ref } from 'react'
import type { EngineStageConfig } from './sourceDesigner'
import { simulatedDrive, SIMULATED_DRIVE_SECONDS } from './simulatedDrive'
import { smoothParameter, driveEnvelopeTarget, createChorus } from './audioAutomation'
import { climbTargets } from './sourceClimb'
import { GranularPlayer, type GranularMode } from './granularPlayer'
import { drivingSoundTargets, responseRiseSeconds, type SoundResponse, type DrivingInput } from './drivingSoundMapping'

type Voice = { chorus: ReturnType<typeof createChorus>; sources: (AudioBufferSourceNode | GranularPlayer)[]; gains: GainNode[]; filter: BiquadFilterNode; level: GainNode; dry: GainNode; wet: GainNode; drive: GainNode; expression: GainNode; driveTarget?: number; response?: SoundResponse; granularMode?: GranularMode; authored?: boolean; sourceRevision?: number }
export type SourceHandle = { start: (refresh?: boolean, mode?: GranularMode) => void; stop: () => void; analyser: () => AnalyserNode | null; auditionContext: () => Record<string, unknown>; audition: (urls: string[], input: 'driving' | 'simulated', label: string) => Promise<boolean | string> }
const STEMS = ['body', 'pad', 'glass', 'air']
const granularWorklets = new WeakMap<AudioContext, Promise<void>>()  // processor modules are registered per AudioContext
/** Hidden audio engine for GS (dashboard, overlay, discovery auditions): renders nothing. */
export default function SteadySource({ onPlay, driving, onPlayingChange, onError, ref, granularMode }: { granularMode: GranularMode; ref?: Ref<SourceHandle>; onPlay: () => void; driving?: DrivingInput; onError?: (message: string) => void; onPlayingChange?: (playing: boolean) => void }) {
  const context = useRef<AudioContext | null>(null)
  const buffers = useRef<AudioBuffer[] | null>(null)
  const voice = useRef<Voice | null>(null)
  const externalSourceUrls = useRef<string[] | null>(null)
  const auditionPending = useRef<((ready: boolean | string) => void) | null>(null)
  const [auditionRequest, setAuditionRequest] = useState(0)
  const generatedBuffers = useRef<AudioBuffer[] | null>(null)
  const [sourceRevision, setSourceRevision] = useState(0)
  const engineStage = useRef<EngineStageConfig | null>(null)  // live stage after the player for Engine/Orchestral (stems 0-2, not air)
  const travel = useRef(1)  // pitch climb of the selected style (PITCH_TRAVEL); 1 for the original sound and discovery candidates
  const analyser = useRef<AnalyserNode | null>(null)
  const request = useRef(0)
  const startRequested = useRef(false)
  const refreshRequested = useRef(false)
  const [playing, setPlaying] = useState(false)
  const [loading, setLoading] = useState(false)
  const [volume] = useState(.7)
  const [spatial, setSpatial] = useState(true)
  const [climb] = useState(0)
  const [method, setMethod] = useState<'granular' | 'sample'>('granular')
  const [inputMode, setInputMode] = useState<'driving' | 'manual' | 'simulated'>('driving')
  const [response, setResponse] = useState<SoundResponse>('exponential')
  const [evolvingSource, setEvolvingSource] = useState<'transformed' | 'authored'>('transformed')
  const simulationStart = useRef(0)
  const settingsRef = useRef({ method, inputMode, response, granularMode, evolvingSource, sourceRevision })
  settingsRef.current = { method, inputMode, response, granularMode, evolvingSource, sourceRevision }
  const inputRef = useRef(driving)
  const receivedAt = useRef(performance.now())
  const playingCallback = useRef(onPlayingChange)
  playingCallback.current = onPlayingChange
  useEffect(() => { inputRef.current = driving; receivedAt.current = performance.now() }, [driving])
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
  useEffect(() => {
    setPlaying(false); setLoading(false)
    return () => {
      auditionPending.current?.(false); auditionPending.current = null
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
    const target = inputMode !== 'manual' ? drivingSoundTargets(input ?? { running: false, starting: false, speedKmh: 0, throttle: 0, motorLoad: null }, inputMode === 'driving' && performance.now() - receivedAt.current > 750, response, granularMode, travel.current) : { ...climbTargets(value), driveGain: 1, loopHold: 0, cycleSpeed: 1, stage: 0 }
    const set = (param: AudioParam, value: number, smoothing = .15) => {
      if (immediate) param.setValueAtTime(value, audio.currentTime)
      else smoothParameter(param, value, audio.currentTime, smoothing)
    }
    const authored = granularMode === 'evolving' && evolvingSource === 'authored'
    if ((current.authored !== authored || current.sourceRevision !== sourceRevision) && buffers.current) {
      current.sources.forEach((source, index) => {
        if (source instanceof GranularPlayer) source.setEngine(index < 3 ? engineStage.current : null)
        if (index === 0) {
          current.chorus.setAmount(engineStage.current?.chorus ?? 1, audio.currentTime)
          const room = controls.current.spatial && (engineStage.current?.room ?? true)
          smoothParameter(current.dry.gain, room ? .68 : 1, audio.currentTime, .1); smoothParameter(current.wet.gain, room ? .32 : 0, audio.currentTime, .1)
        }
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
        set(source.stage, index < 3 && !authored ? target.stage : 0, .35)
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
    // Engine style: no air layer. It bypasses the engine stage's 1.2 kHz low-pass, so its breathy hiss stood out while driving.
    ;[target.bodyGain, target.padGain, target.glassGain, engineStage.current ? 0 : target.airGain].forEach((gain, i) => set(current.gains[i].gain, gain))
    set(current.filter.frequency, target.cutoff)
  }
  useEffect(() => { if (voice.current) applyGesture(voice.current, climb) }, [climb, driving, inputMode, response, granularMode, evolvingSource, sourceRevision])
  useEffect(() => {
    if (!playing || inputMode !== 'driving') return
    const timer = window.setInterval(() => { if (voice.current) applyGesture(voice.current, controls.current.climb) }, 100)
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
      generatedBuffers.current = null
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
      const chorus = createChorus(audio); chorus.setAmount(engineStage.current?.chorus ?? 1, audio.currentTime)
      bus.connect(chorus.input); chorus.output.connect(drive); drive.connect(expression); expression.connect(dry); dry.connect(level); expression.connect(convolver); convolver.connect(wet); wet.connect(level); level.connect(analyser.current!)
      filter.connect(bus)
      // Engine style is dry: the bright 2 s room reverb (61% of its energy at 1-4 kHz) sat above the engine's 1.2 kHz low-pass and was heard as air.
      const room = controls.current.spatial && (engineStage.current?.room ?? true)
      dry.gain.value = room ? .68 : 1; wet.gain.value = room ? .32 : 0
      const gains = STEMS.map(() => audio.createGain())
      const selectedBuffers = selectedMode === 'evolving' && selectedSource === 'authored' ? decoded.slice(4, 8) : generatedBuffers.current ?? decoded.slice(0, 4)
      const sources = STEMS.map((_, i) => {
        let source: AudioBufferSourceNode | GranularPlayer
        if (selectedMethod === 'granular') { source = new GranularPlayer(audio, selectedBuffers[i]); source.setEngine(i < 3 ? engineStage.current : null) }
        else { source = audio.createBufferSource(); source.buffer = selectedBuffers[i]; source.loop = true }
        source.connect(gains[i]); gains[i].connect(i === 1 || i === 2 ? filter : bus)
        return source
      })
      let remaining = sources.length
      sources.forEach(source => { source.onended = () => {
        source.disconnect()
        if (--remaining === 0) { gains.forEach(gain => gain.disconnect()); filter.disconnect(); bus.disconnect(); chorus.dispose(); dry.disconnect(); wet.disconnect(); convolver.disconnect(); level.disconnect(); drive.disconnect(); expression.disconnect() }
      } })
      const current = { chorus, sources, gains, filter, level, dry, wet, drive, expression, granularMode: selectedMode, sourceRevision: settingsRef.current.sourceRevision, authored: selectedMode === 'evolving' && selectedSource === 'authored' }
      simulationStart.current = audio.currentTime
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
      if (voice.current) applyGesture(voice.current, controls.current.climb)
      if (elapsed >= SIMULATED_DRIVE_SECONDS) stop()
    }, 50)
    return () => window.clearInterval(timer)
  }, [playing, inputMode, response, granularMode, evolvingSource])
  useEffect(() => {
    if (!auditionPending.current && voice.current && inputMode === 'simulated') void play(true)
  }, [granularMode, evolvingSource, inputMode])
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
  }, stop, analyser: () => analyser.current, auditionContext: () => ({ volume: controls.current.volume, candidateId: externalSourceUrls.current?.[0].split('/')[3] ?? null, input: settingsRef.current.inputMode === 'simulated' ? 'simulated' : 'live', style: settingsRef.current.granularMode, response: settingsRef.current.response, spatial: controls.current.spatial }), audition: (urls, input) => {
    if (urls.length !== 4 || !urls.every(url => /^\/audio\/source-search-cache\/[a-f0-9]{32}\/stem-[0-2]\.wav$/.test(url) || url === '/audio/original_steady_air.wav?v=17')) return Promise.resolve(false)
    auditionPending.current?.(false)
    stop(); travel.current = 1; engineStage.current = null; externalSourceUrls.current = urls; setMethod('granular'); setInputMode(input); setEvolvingSource('transformed'); setSpatial(true); setResponse('exponential')
    return new Promise(resolve => { auditionPending.current = resolve; setAuditionRequest(value => value + 1) })
  } }))
  return null
}
