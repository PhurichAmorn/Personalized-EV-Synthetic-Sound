import { useEffect, useMemo, useRef, useState, type RefObject } from 'react'
import { createPlainVoices, EXTRA_KEYS, EXTRAS_OFF, PLAIN_DEFAULT, PLAIN_PRESETS, PLAIN_RANGES, PLAIN_RATE, spectrum, type PlainParams } from './plainSource'
import { PITCH_TRAVEL, SOURCE_FAMILIES, sourceAudioBuffers, type SourceFamily } from './sourceDesigner'
import { RECIPE_DEFAULT_CONTROLS } from './sourceRecipe'
import { GranularPlayer, type GranularMode } from './granularPlayer'
import { smoothParameter } from './audioAutomation'
import { drivingSoundTargets, type SoundResponse } from './drivingSoundMapping'
import { BLEND_MIX, NO_BRIGHTNESS, CANDIDATE_SOUNDS, CHARACTER, FAIR_FX, PITCH_STEP, STARTING_SOUNDS, SYNTH_TRIES, TUNING_DEFAULT, tunedSound, type Tuning } from './levels'
import { applyFx, buildRig, clamp, driveRig, FX_DEFAULT, FX_OFF, granularWorklet, manualInput, type Fx, type Motion } from './labEngine'
import { simulatedDrive, SIMULATED_DRIVE_SECONDS } from './simulatedDrive'

/** Sound Lab bench: plain base source -> granular player (driving motion) -> transformation effects.
 * Sound B plays an original style's source through the same chain, for comparison. Nothing is saved. */
type Range = { key: string; label: string; min: number; max: number; step: number; log?: boolean; unit?: string; low: string; high: string }
const FX_RANGES: { group: string; items: Range[] }[] = [
  { group: 'Tone', items: [
    { key: 'tone', label: 'Low-pass', min: 600, max: 18000, step: 1, log: true, unit: 'Hz', low: 'Dark', high: 'Open' },
    { key: 'follow', label: 'Tone follows pedal', min: 0, max: 1, step: .01, low: 'Fixed', high: '±1 octave' },
    { key: 'res', label: 'Resonance (filter sings)', min: .6, max: 15, step: .1, low: 'Soft', high: 'Peaky' },
  ] },
  { group: 'Body resonance (fixed pitch)', items: [
    { key: 'bodyHz', label: 'Body frequency', min: 150, max: 3000, step: 1, log: true, unit: 'Hz', low: 'Low', high: 'High' },
    { key: 'bodyDb', label: 'Body strength', min: 0, max: 12, step: .5, unit: 'dB', low: 'Off', high: 'Strong' },
  ] },
  { group: 'Space', items: [
    { key: 'chorus', label: 'Chorus', min: 0, max: 2, step: .05, low: 'Off', high: '50% wet' },
    { key: 'reverb', label: 'Reverb mix', min: 0, max: .6, step: .01, low: 'Dry', high: 'Wet' },
    { key: 'size', label: 'Reverb decay', min: .3, max: 4, step: .1, unit: 's', low: 'Small', high: 'Hall' },
  ] },
  { group: 'Texture', items: [
    { key: 'tremDepth', label: 'Tremolo depth', min: 0, max: .6, step: .01, low: 'Off', high: 'Deep' },
    { key: 'tremRate', label: 'Tremolo rate', min: 1, max: 12, step: .1, unit: 'Hz', low: 'Slow', high: 'Fast' },
    { key: 'pump', label: 'Pulse shape', min: 0, max: 1, step: 1, low: 'Smooth (tremolo)', high: 'Pump (sidechain duck)' },
    { key: 'rasp', label: 'Rasp (cycle alternation)', min: 0, max: .3, step: .01, low: 'Off', high: 'Growl' },
  ] },
  { group: 'Vibrato (pitch wobble, after the player)', items: [
    { key: 'vibDepth', label: 'Depth', min: 0, max: 30, step: .5, unit: 'cents', low: 'Off', high: 'Wide' },
    { key: 'vibRate', label: 'Rate', min: 3, max: 8, step: .1, unit: 'Hz', low: 'Slow', high: 'Fast' },
  ] },
]
/** Original styles as Sound Lab settings. `plain` is the closest slider match, found by searching all slider settings for the
 * smallest spectral distance (Hellinger, 1/6-octave bands) to the style's source at default controls (2026-11-14). Extras searched only where the style has them:
 * vowel for Choir, lowest-note level for Electric, whine for Jet, bell modes for Glass.
 * `fx` is what the original player adds: shared chorus (amount 1), room reverb (32% wet, about 2 s), low-pass 1300-2200 Hz with pedal.
 * `extras` are built into the original source and have no slider. */
// Vibrato: the pad styles carry about 2 cents at 5.2 Hz inside their source, Choir about 5 cents; Electric and Jet none.
const ORIGINAL_FX: Fx = { tone: 1700, follow: .37, bodyHz: 450, bodyDb: 0, chorus: 1, reverb: .32, size: 2, tremRate: 6, tremDepth: 0, rasp: 0, vibDepth: 2, vibRate: 5.2, pump: 0, res: .6 }
const DRIFT = 'Slow pitch drift (0.2 and 0.6 Hz) and loudness sway (1.4 Hz) inside the source (no slider; vibrato is approximated after the player)'
const DETUNE = 'Chord voices slightly detuned (±0.4 Hz): slow beating (chorus approximates it)'
const WARM = 'Warm bump near 450 Hz and a stronger lowest note (body control .7)'
const ECHO = 'Built-in short echo: 3 taps at 26-147 ms, darkened above 1.6 kHz (reverb approximates it)'
const AIR_LAYER = 'Original player also adds a separate noise (air) layer; not played here (air fixed at 0)'
const plainMatch = (p: Partial<PlainParams>): PlainParams => ({ ...EXTRAS_OFF, rootHz: 175, brightness: .5, hollow: 0, bell: 0, air: 0, softTop: 1800, chord: 0, ...p })
const STYLE_MATCH: Partial<Record<SourceFamily, { plain: PlainParams; fx: Fx; distance: number; extras: string[] }>> = {
  bowed: { distance: .10, fx: ORIGINAL_FX, plain: plainMatch({ brightness: .7, softTop: 800, chord: .8 }), extras: ['Harmonics fade with an exponential curve, at most 24 harmonics, cut near 1.7 kHz', DETUNE, DRIFT, WARM, ECHO, AIR_LAYER] },
  rounded: { distance: .07, fx: { ...ORIGINAL_FX, vibDepth: .3 }, plain: plainMatch({ brightness: 1, hollow: .8, softTop: 800 }), extras: ['Only harmonics 1, 3, 5, 7', 'Extra voices are the same note twice plus an octave (no chord), slightly detuned', DRIFT, ECHO, AIR_LAYER] },
  vocal: { distance: .08, fx: { ...ORIGINAL_FX, vibDepth: 5 }, plain: plainMatch({ vowel: .8, brightness: .9, softTop: 1000, chord: 1 }), extras: ['Five singers detuned 0, ±0.4, ±0.8 Hz, each with its own vibrato rate (chorus and vibrato approximate them)', DETUNE, DRIFT, WARM, ECHO, AIR_LAYER] },
  glass: { distance: .075, fx: ORIGINAL_FX, plain: plainMatch({ bellModes: 1, brightness: .8, softTop: 4000, chord: 1 }), extras: ['Each bell mode sways in loudness at 0.4 Hz', DETUNE, DRIFT, WARM, ECHO, AIR_LAYER] },
  airy: { distance: .10, fx: ORIGINAL_FX, plain: plainMatch({ brightness: .6, softTop: 3300, chord: 1 }), extras: ['24 extra soft tones in groups of three (±0.4 Hz apart) around 900 Hz: shimmer', 'Main note plus a weak 2nd harmonic only', DETUNE, DRIFT, ECHO, AIR_LAYER] },
  evolution: { distance: .35, fx: { ...ORIGINAL_FX, vibDepth: 0 }, plain: plainMatch({ rootHz: 79, fundamental: .05, brightness: .8, softTop: 800 }), extras: ['Harmonic levels copied from the IONIQ 5 N Evolution mode: strongest 4th and 2nd, weak 3rd (only partly reachable: no per-harmonic slider)', 'Soft top near 2.5 kHz', ECHO, AIR_LAYER] },
  supersonic: { distance: .06, fx: { ...ORIGINAL_FX, vibDepth: 0 }, plain: plainMatch({ rootHz: 160, whine: 1, brightness: .5, softTop: 800 }), extras: ['Rumble harmonics cut near 600 Hz', ECHO, AIR_LAYER] },
}
/** Clipboard in the app's WebView can refuse silently: try the async API, then the older copy command. */
async function copyText(text: string) {
  try { await navigator.clipboard.writeText(text); return true } catch { /* fall back */ }
  const area = document.createElement('textarea'); area.value = text; area.style.position = 'fixed'; area.style.opacity = '0'
  document.body.appendChild(area); area.select()
  let ok = false
  try { ok = document.execCommand('copy') } catch { ok = false }
  area.remove(); return ok
}
const matchQuality = (d: number) => d <= .12 ? 'good' : d <= .25 ? 'rough' : 'poor'
const STYLES = SOURCE_FAMILIES.filter(item => !['blocks', 'resonant', 'engine', 'orchestra'].includes(item.id))
const MODES: [Motion['mode'], string][] = [['source', 'Source only'], ['steady', 'Steady'], ['rise', 'Rise'], ['evolving', 'Evolving']]
const fmt = (value: number, unit = '') => (Math.abs(value) >= 100 ? value.toFixed(0) : value.toFixed(2)) + (unit ? ' ' + unit : '')

const mixStems = (stems: Float32Array[][]) => Float32Array.from(stems[0][0], (value, i) => stems.reduce((sum, stem, k) => k ? sum + stem[0][i] : sum, value))
type Analysis = { points: [number, number][]; wave: number[]; centroid: number; crest: number }
function analyse(channel: Float32Array): Analysis {
  const { db, binHz, centroid } = spectrum(channel, PLAIN_RATE)
  const points: [number, number][] = []
  for (let i = 0; i < 240; i++) {  // max per log-spaced bin, 40 Hz-12 kHz
    const lo = 40 * 300 ** (i / 240), hi = 40 * 300 ** ((i + 1) / 240)
    let best = -140
    for (let k = Math.floor(lo / binHz); k <= Math.ceil(hi / binHz); k++) best = Math.max(best, db[k] ?? -140)
    points.push([i / 239, best])
  }
  let peak = 0, energy = 0
  for (const value of channel) { peak = Math.max(peak, Math.abs(value)); energy += value * value }
  const wave = Array.from({ length: 300 }, (_, i) => channel[Math.round(i * PLAIN_RATE * .025 / 300)])
  return { points, wave, centroid, crest: 20 * Math.log10(peak / Math.sqrt(energy / channel.length)) }
}

export default function SoundLab({ onStart, stopToken }: { onStart: () => void; stopToken: number }) {
  const [plain, setPlain] = useState<PlainParams>(PLAIN_DEFAULT)
  const [style, setStyle] = useState<SourceFamily>('bowed')
  const [active, setActive] = useState<'A' | 'B'>('A')
  const [motion, setMotion] = useState<Motion>({ mode: 'rise', travel: 1, response: 'exponential', input: 'drive', position: .5, pedal: .6 })
  const [fx, setFx] = useState<Fx>(FX_DEFAULT)
  const [bypass, setBypass] = useState(false)
  const [volume, setVolume] = useState(.7)
  const [playing, setPlaying] = useState(false)
  const [time, setTime] = useState(0)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  // Last copied text stays on screen, so results can be read or copied by hand even if the clipboard refuses.
  const [shared, setShared] = useState<{ label: string; text: string; ok: boolean } | null>(null)
  const share = (label: string, text: string) => void copyText(text).then(ok => setShared({ label, text, ok }))
  const sharedBox = useRef<HTMLDivElement>(null)
  useEffect(() => { if (shared) sharedBox.current?.scrollIntoView({ behavior: 'smooth', block: 'center' }) }, [shared])
  const [sources, setSources] = useState<{ A?: Float32Array[][]; B?: Float32Array[][] }>({})  // stems x channels
  const analysis = useMemo(() => ({ A: sources.A && analyse(mixStems(sources.A)), B: sources.B && analyse(mixStems(sources.B)) }), [sources])
  const audio = useRef<AudioContext | null>(null)
  const analyser = useRef<AnalyserNode | null>(null)
  const rig = useRef<ReturnType<typeof buildRig> | null>(null)
  const live = useRef({ motion, fx: bypass ? FX_OFF : fx, plain, active, sources })
  live.current = { motion, fx: bypass ? FX_OFF : fx, plain, active, sources }
  const builtStyles = useRef(new Map<SourceFamily, Float32Array[][]>())

  // Source A: plain generator (about 0.1 s), debounced while dragging.
  useEffect(() => {
    const timer = window.setTimeout(() => setSources(current => ({ ...current, A: createPlainVoices(plain) })), 120)
    return () => window.clearTimeout(timer)
  }, [plain])
  // Source B: an original style's source (its three tonal stems summed), built off-thread once per style.
  useEffect(() => {
    const cached = builtStyles.current.get(style)
    if (cached) { setSources(current => ({ ...current, B: cached })); return }
    setBusy(true)
    const worker = new Worker(new URL('./sourceDesigner.worker.ts', import.meta.url), { type: 'module' })
    worker.onmessage = ({ data }: MessageEvent<{ stems?: Float32Array[][]; error?: string }>) => {
      worker.terminate(); setBusy(false)
      if (!data.stems) { setError(data.error ?? 'Style source failed.'); return }
      const stems = data.stems.slice(0, 3)  // three tonal layers, each with its own player as in the original player
      builtStyles.current.set(style, stems); setSources(current => ({ ...current, B: stems }))
    }
    worker.onerror = () => { worker.terminate(); setBusy(false); setError('Style source failed.') }
    worker.postMessage({ controls: RECIPE_DEFAULT_CONTROLS, family: style })
    return () => worker.terminate()
  }, [style])

  const buffer = (which: 'A' | 'B') => {
    const data = live.current.sources[which]
    return data && audio.current ? sourceAudioBuffers(audio.current, data) : null
  }
  // Swap the playing source in place (the player cross-fades 160 ms); raw loops restart.
  const installed = useRef<Float32Array[][] | undefined>(undefined)
  useEffect(() => {
    const current = rig.current, data = sources[active]
    if (!current || !data || data === installed.current) return
    installed.current = data
    const next = buffer(active)!
    if (current.granular) current.players.forEach((player, i) => (player as GranularPlayer).setSource(next[i]))
    else void play(true)
  }, [sources, active])

  const stop = () => {
    const current = rig.current, context = audio.current
    rig.current = null; setPlaying(false)
    if (current && context) { current.master.gain.setTargetAtTime(0, context.currentTime, .03); window.setTimeout(current.dispose, 200) }
  }
  useEffect(() => { if (stopToken) stop() }, [stopToken])
  useEffect(() => () => { stop(); void audio.current?.close() }, [])
  const play = async (restart = false) => {
    if (rig.current && !restart) { stop(); return }
    stop(); setError(''); onStart()
    try {
      if (!audio.current) {
        audio.current = new AudioContext()
        analyser.current = audio.current.createAnalyser(); analyser.current.fftSize = 4096; analyser.current.smoothingTimeConstant = .6
        analyser.current.connect(audio.current.destination)
      }
      const context = audio.current
      await context.resume()
      await granularWorklet(context)
      const source = buffer(live.current.active)
      installed.current = live.current.sources[live.current.active]
      if (!source) throw Error('Source is still building. Try again in a moment.')
      const next = buildRig(context, source, live.current.motion.mode, analyser.current!)
      rig.current = next
      applyFx(next, live.current.fx, live.current.plain.rootHz, true)
      next.master.gain.setTargetAtTime(volume, context.currentTime, .05)
      tick(true)
      setPlaying(true)
    } catch (problem) { setError(problem instanceof Error ? problem.message : 'Could not play.') }
  }
  // Mode changes need a different player (raw loop vs granular).
  useEffect(() => { if (rig.current) void play(true) }, [motion.mode])
  useEffect(() => { if (rig.current) applyFx(rig.current, bypass ? FX_OFF : fx, plain.rootHz) }, [fx, bypass, plain.rootHz])
  useEffect(() => { if (rig.current && audio.current) smoothParameter(rig.current.master.gain, volume, audio.current.currentTime, .03) }, [volume])

  // Driving input: replayed 22 s drive (looping) or a manual position.
  const tick = (immediate = false) => {
    const current = rig.current, context = audio.current
    if (!current || !context) return
    const { motion, fx } = live.current, now = context.currentTime
    const t = (now - current.startedAt) % SIMULATED_DRIVE_SECONDS
    setTime(t)
    driveRig(current, motion, fx, motion.input === 'drive' ? simulatedDrive(t) : manualInput(motion.position, motion.pedal), immediate)
  }
  useEffect(() => {
    if (!playing) return
    const timer = window.setInterval(() => tick(), 50)
    return () => window.clearInterval(timer)
  }, [playing])

  // Marks which sliders a preset or style click moved ("was ...").
  const [before, setBefore] = useState<{ label: string; plain: PlainParams; fx: Fx; travel: number } | null>(null)
  const remember = (label: string) => setBefore({ label, plain, fx, travel: motion.travel })
  const [playSoon, setPlaySoon] = useState(false)
  useEffect(() => { if (playSoon) { setPlaySoon(false); void play() } }, [playSoon])
  // Starting sounds: each its own full design; "Same effects" plays every base sound through one transformation.
  const [typeOn, setTypeOn] = useState<string | null>(null)
  const [ownFx, setOwnFx] = useState(true)
  const [typeVotes, setTypeVotes] = useState<Record<string, { vote?: string; note?: string; similar?: string[]; better?: string[] }>>({})
  const [tryOn, setTryOn] = useState('asis')
  const playType = (id: string, own = ownFx, variant = tryOn) => {
    const sound = CANDIDATE_SOUNDS.find(item => item.id === id)!, add = SYNTH_TRIES.find(item => item.id === variant)!
    remember(`Starting sound: ${sound.name}`)
    setPlain({ ...plainMatch({}), ...sound.plain, ...add.plain(sound.plain) }); setFx({ ...(own ? sound.fx : FAIR_FX), ...add.fx }); setBypass(false); setActive('A'); setTryOn(variant)
    setMotion(m => ({ ...m, mode: 'rise', travel: 1, response: 'exponential', input: 'drive' }))
    setTypeOn(id); if (!rig.current) setPlaySoon(true)
  }
  // Change test (05): before / after for each tuning change on one starting sound; the listener marks how big the change sounds.
  const [testStart, setTestStart] = useState('warm')
  const [blendWith, setBlendWith] = useState('sparkle')
  const [testOn, setTestOn] = useState<string | null>(null)
  const [changeVotes, setChangeVotes] = useState<Record<string, { label: string; vote: string }>>({})
  const soundName = (id: string) => STARTING_SOUNDS.find(sound => sound.id === id)!.name
  const other = blendWith === testStart ? STARTING_SOUNDS.find(sound => sound.id !== testStart)!.id : blendWith
  const fraction = (mix: number) => ({ [1 / 3]: '⅓', [1 / 2]: '½', [2 / 3]: '⅔' })[mix]
  const changeRows: [string, string, Partial<Tuning>][] = [
    ['pitch-1', `Pitch −${PITCH_STEP} semitones`, { pitch: -1 }], ['pitch+1', `Pitch +${PITCH_STEP} semitones`, { pitch: 1 }],
    ...([[-1, 'Darker'], [1, 'Brighter (capped at 3.5 kHz)']] as const).filter(([side]) => NO_BRIGHTNESS[testStart] !== side).map(([side, label]) => [`bright${side > 0 ? '+' : '-'}1`, label, { brightness: side }] as [string, string, Partial<Tuning>]),
    ...(CHARACTER[testStart].less ? [['char-1', `Less ${CHARACTER[testStart].label}`, { character: -1 }] as [string, string, Partial<Tuning>]] : []),
    ...(CHARACTER[testStart].more ? [['char+1', `More ${CHARACTER[testStart].label}`, { character: 1 }] as [string, string, Partial<Tuning>]] : []),
    ...BLEND_MIX.map(mix => [`blend-${other}-${mix.toFixed(2)}`, `Blend ${fraction(mix)} with ${soundName(other)}`, { blend: other, mix }] as [string, string, Partial<Tuning>]),
  ]
  const playTuned = (patch: Partial<Tuning>, key: string) => {
    const t: Tuning = { ...TUNING_DEFAULT, start: testStart, ...patch }, sound = tunedSound(t, 260)
    setTypeOn(null); setBefore(null); setPlain(sound.plain); setFx(sound.fx); setBypass(false); setActive('A')
    setMotion(m => ({ ...m, mode: t.kind, travel: sound.travel, response: 'exponential', input: 'drive' }))
    setTestOn(key); if (!rig.current) setPlaySoon(true)
  }
  const copyChanges = () => share('Change test results', STARTING_SOUNDS.map(sound => {
    const rows = Object.entries(changeVotes).filter(([key]) => key.startsWith(sound.id + '|'))
    return rows.length ? `${sound.name}\n` + rows.map(([, { label, vote }]) => `  ${label}: ${vote}`).join('\n') : ''
  }).filter(Boolean).join('\n') || 'No changes marked yet')
  const copyTypes = () => share('Starting sound test results', `Effects: ${ownFx ? 'own' : 'same for all'}\n` + CANDIDATE_SOUNDS.map(t => `${t.name}: ${typeVotes[t.id]?.vote ?? 'not tried'}${typeVotes[t.id]?.similar?.length ? ' · too similar to ' + typeVotes[t.id]!.similar!.join(', ') : ''}${typeVotes[t.id]?.better?.length ? ' · better with ' + typeVotes[t.id]!.better!.join(', ') : ''}${typeVotes[t.id]?.note ? ' · ' + typeVotes[t.id]!.note : ''}`).join('\n'))
  const pickStyle = (family: SourceFamily) => {
    const match = STYLE_MATCH[family]
    remember(STYLES.find(item => item.id === family)?.label ?? family)
    setStyle(family); setActive('B'); setMotion(m => ({ ...m, travel: PITCH_TRAVEL[family] ?? 1 }))
    if (match) { setPlain(match.plain); setFx(match.fx); setBypass(false) }
  }
  const changedCount = before ? (Object.keys(plain) as (keyof PlainParams)[]).filter(k => plain[k] !== before.plain[k]).length + (Object.keys(fx) as (keyof Fx)[]).filter(k => fx[k] !== before.fx[k]).length + (motion.travel !== before.travel ? 1 : 0) : 0
  const match = STYLE_MATCH[style]
  const settings = { source: active === 'A' ? { kind: 'plain', ...plain } : { kind: 'style', family: style }, motion, transform: bypass ? 'bypassed' : fx }
  const copy = () => share('Settings', JSON.stringify(settings, null, 2))
  const current = analysis[active]

  return <section className="lab" aria-labelledby="lab-title">
    <header className="lab-head">
      <div><small>EV SOUND LAB · BENCH</small><h2 id="lab-title">Source + transformation</h2></div>
      <div className="lab-transport">
        <button type="button" className="lab-play" aria-pressed={playing} onClick={() => void play()}>{playing ? '■ Stop' : '▶ Play'}</button>
        <div className="lab-seg" role="group" aria-label="Compare sources">
          <button type="button" aria-pressed={active === 'A'} onClick={() => setActive('A')}>A · Plain</button>
          <button type="button" aria-pressed={active === 'B'} onClick={() => setActive('B')}>B · {STYLES.find(item => item.id === style)?.label}</button>
        </div>
        <button type="button" aria-pressed={bypass} onClick={() => setBypass(value => !value)}>{bypass ? 'Transform off' : 'Transform on'}</button>
        <label className="lab-volume">Vol<input type="range" min="0" max="1" step=".01" value={volume} onChange={event => setVolume(Number(event.target.value))} /></label>
        <button type="button" onClick={copy}>Copy settings</button>
      </div>
    </header>
    {error && <p className="lab-error" role="alert">{error}</p>}
    {shared && <div ref={sharedBox} className="lab-shared" role="status"><p>{shared.ok ? `${shared.label} copied to the clipboard: paste it to Claude.` : `${shared.label}: the clipboard refused. Select the text below and copy it (Cmd+C).`} <button type="button" onClick={() => setShared(null)}>Close</button></p>
      <textarea readOnly value={shared.text} rows={Math.min(12, shared.text.split('\n').length + 1)} onFocus={event => event.currentTarget.select()} /></div>}
    {before && <p className="lab-changed-banner" role="status">{changedCount} setting{changedCount === 1 ? '' : 's'} changed by <b>{before.label}</b> · marked "was" below <button type="button" onClick={() => setBefore(null)}>Clear marks</button></p>}

    <div className="lab-grid">
      <section className="lab-panel" aria-labelledby="lab-source">
        <h3 id="lab-source"><span>01</span>Source <small>steady 5 s loop · no effects</small></h3>
        <p className="lab-label">A · Plain source · starting points</p>
        <div className="lab-chips">{PLAIN_PRESETS.map(preset => <button key={preset.name} type="button" aria-pressed={JSON.stringify(preset.params) === JSON.stringify(plain)} onClick={() => { remember(preset.name); setPlain(preset.params); setActive('A') }}>{preset.name}</button>)}</div>
        {(['core', 'extra'] as const).map(part => <div key={part}>{part === 'extra' && <p className="lab-label">Extras · off by default · to reach Choir, Electric, Jet, Glass</p>}
          {(Object.keys(PLAIN_RANGES) as (keyof PlainParams)[]).filter(key => (EXTRA_KEYS as string[]).includes(key) === (part === 'extra')).map(key => <Slider key={key} range={{ key, ...PLAIN_RANGES[key], log: key === 'rootHz' || key === 'softTop', unit: key === 'rootHz' || key === 'softTop' ? 'Hz' : undefined }} value={plain[key]} was={before?.plain[key]} onChange={value => { setPlain(p => ({ ...p, [key]: value })); setActive('A') }} />)}</div>)}
        <p className="lab-label">B · Original style source (for comparison) {busy && '· building…'}</p>
        <div className="lab-chips">{STYLES.map(item => <button key={item.id} type="button" title={item.description} aria-pressed={active === 'B' && style === item.id} onClick={() => pickStyle(item.id)}>{item.label}</button>)}</div>
        {match && <div className="lab-extras">
          <p><b>{STYLES.find(item => item.id === style)?.label}</b> · closest slider match {match.distance.toFixed(2)} ({matchQuality(match.distance)}) · A now holds that match: switch A/B to compare</p>
          <p className="lab-label">Built into this style · no slider</p>
          <ul>{match.extras.map(item => <li key={item}>{item}</li>)}</ul>
        </div>}
        <SourceGraphs a={analysis.A} b={analysis.B} active={active} />
        {current && <dl className="lab-stats">
          <div><dt>Brightness (centroid)</dt><dd>{fmt(current.centroid, 'Hz')}</dd></div>
          <div><dt>Crest factor</dt><dd>{fmt(current.crest, 'dB')}</dd></div>
          <div><dt>Root</dt><dd>{active === 'A' ? fmt(plain.rootHz, 'Hz') : 'style'}</dd></div>
        </dl>}
      </section>

      <section className="lab-panel" aria-labelledby="lab-motion">
        <h3 id="lab-motion"><span>02</span>Motion <small>granular player · driving map</small></h3>
        <div className="lab-seg lab-seg-wide" role="group" aria-label="Player mode">{MODES.map(([mode, label]) => <button key={mode} type="button" aria-pressed={motion.mode === mode} onClick={() => setMotion(m => ({ ...m, mode }))}>{label}</button>)}</div>
        <div className="lab-seg lab-seg-wide" role="group" aria-label="Driving input">
          <button type="button" disabled={motion.mode === 'source'} aria-pressed={motion.input === 'drive'} onClick={() => setMotion(m => ({ ...m, input: 'drive' }))}>22 s drive (loops)</button>
          <button type="button" disabled={motion.mode === 'source'} aria-pressed={motion.input === 'manual'} onClick={() => setMotion(m => ({ ...m, input: 'manual' }))}>Manual speed</button>
        </div>
        {motion.input === 'manual' && motion.mode !== 'source' && <Slider range={{ key: 'position', label: 'Speed', min: 0, max: 1, step: .005, low: '0 km/h', high: '130 km/h' }} value={motion.position} onChange={position => setMotion(m => ({ ...m, position }))} />}
        {motion.input === 'manual' && motion.mode !== 'source' && <Slider range={{ key: 'pedal', label: 'Pedal (level, tone follow)', min: 0, max: 1, step: .01, low: 'Lifted', high: 'Floored' }} value={motion.pedal} onChange={pedal => setMotion(m => ({ ...m, pedal }))} />}
        <Slider range={{ key: 'travel', label: 'Pitch travel', min: .5, max: 2.5, step: .05, unit: '×', low: 'Narrow', high: 'Wide climb' }} value={motion.travel} was={before?.travel} onChange={travel => setMotion(m => ({ ...m, travel }))} />
        <label className="lab-select">Pedal response<select value={motion.response} onChange={event => setMotion(m => ({ ...m, response: event.target.value as SoundResponse }))}><option value="exponential">Exponential</option><option value="linear">Linear</option><option value="logarithmic">Logarithmic</option></select></label>
        <DriveChart motion={motion} time={playing ? time : null} />
      </section>

      <section className="lab-panel" aria-labelledby="lab-fx">
        <h3 id="lab-fx"><span>03</span>Transformation <small>after the player · live</small></h3>
        {FX_RANGES.map(({ group, items }) => <fieldset key={group} disabled={bypass}><legend>{group}</legend>
          {items.map(range => <Slider key={range.key} range={range} value={fx[range.key as keyof Fx] as number} was={before?.fx[range.key as keyof Fx]} onChange={value => setFx(f => ({ ...f, [range.key]: value }))} />)}
        </fieldset>)}
        <button type="button" onClick={() => setFx(FX_DEFAULT)}>Reset transformation</button>
      </section>

      <section className="lab-panel lab-panel-wide" aria-labelledby="lab-tests">
        <h3 id="lab-tests"><span>04</span>Experiments</h3>
        <p className="lab-label">Starting sounds · the six the search uses · each a full design (base + effects)</p>
        <div className="lab-seg" role="group" aria-label="Effects">
          <button type="button" aria-pressed={ownFx} onClick={() => { setOwnFx(true); if (typeOn) playType(typeOn, true) }}>Own effects</button>
          <button type="button" aria-pressed={!ownFx} onClick={() => { setOwnFx(false); if (typeOn) playType(typeOn, false) }}>Same effects for all (base only differs)</button>
        </div>
        <div className="lab-tests">{CANDIDATE_SOUNDS.map(type => <article key={type.id} className={typeOn === type.id ? 'lab-test-active' : ''}>
          <h4>{type.name}</h4>
          <p className="lab-note">{type.character}</p>
          <p className="lab-listen">{type.settings}</p>
          <button type="button" aria-pressed={typeOn === type.id} onClick={() => playType(type.id, ownFx, 'asis')}>▶ Play on the drive</button>
          <div className="lab-chips">{['Keep', 'Maybe', 'Drop'].map(vote => <button key={vote} type="button" aria-pressed={typeVotes[type.id]?.vote === vote} onClick={() => setTypeVotes(v => ({ ...v, [type.id]: { ...v[type.id], vote } }))}>{vote}</button>)}</div>
          <div className="lab-chips"><span className="lab-note">Too similar to:</span>{CANDIDATE_SOUNDS.filter(other => other.id !== type.id).map(other => { const list = typeVotes[type.id]?.similar ?? [], on = list.includes(other.name)
            return <button key={other.id} type="button" aria-pressed={on} onClick={() => setTypeVotes(v => ({ ...v, [type.id]: { ...v[type.id], similar: on ? list.filter(n => n !== other.name) : [...list, other.name] } }))}>{other.name}</button> })}</div>
          <input className="lab-input" placeholder="Note (optional)" value={typeVotes[type.id]?.note ?? ''} onChange={event => setTypeVotes(v => ({ ...v, [type.id]: { ...v[type.id], note: event.target.value } }))} />
        </article>)}</div>
        <button type="button" onClick={copyTypes}>Copy starting sound results</button>
      </section>

      <section className="lab-panel lab-panel-wide" aria-labelledby="lab-changes">
        <h3 id="lab-changes"><span>05</span>Change test <small>is each tuning change big enough to hear? · play Before, then After, on the 22 s drive</small></h3>
        <div className="lab-chips"><span className="lab-note">Starting sound:</span>{STARTING_SOUNDS.map(sound => <button key={sound.id} type="button" aria-pressed={testStart === sound.id} onClick={() => { setTestStart(sound.id); setTestOn(null) }}>{sound.name}</button>)}</div>
        <div className="lab-chips"><span className="lab-note">Blend with:</span>{STARTING_SOUNDS.filter(sound => sound.id !== testStart).map(sound => <button key={sound.id} type="button" aria-pressed={other === sound.id} onClick={() => setBlendWith(sound.id)}>{sound.name}</button>)}</div>
        <div className="lab-changes">
          {changeRows.map(([id, label, patch]) => { const key = `${testStart}|${id}`, vote = changeVotes[key]?.vote
            return <div key={key} className={'lab-change' + (testOn?.startsWith(key) ? ' lab-test-active' : '')}>
              <strong>{label}</strong>
              <div className="lab-chips">
                <button type="button" aria-pressed={testOn === key + '|before'} onClick={() => playTuned({}, key + '|before')}>▶ Before</button>
                <button type="button" aria-pressed={testOn === key + '|after'} onClick={() => playTuned(patch, key + '|after')}>▶ After</button>
              </div>
              <div className="lab-chips">{["Can't hear", 'Small', 'Clear'].map(option => <button key={option} type="button" aria-pressed={vote === option}
                onClick={() => setChangeVotes(v => ({ ...v, [key]: { label, vote: option } }))}>{option}</button>)}</div>
            </div> })}
        </div>
        <button type="button" onClick={copyChanges}>Copy change test results</button>
      </section>

      <section className="lab-panel lab-panel-wide" aria-labelledby="lab-scope">
        <h3 id="lab-scope"><span>06</span>Scope <small>live output</small></h3>
        <Scope analyser={analyser} active={playing} />
      </section>
    </div>
  </section>
}

function Slider({ range, value, was, onChange }: { range: Range; value: number; was?: number; onChange: (value: number) => void }) {
  const changed = was !== undefined && was !== value
  const toSlider = (v: number) => range.log ? Math.log(v / range.min) / Math.log(range.max / range.min) : v
  const fromSlider = (s: number) => range.log ? Math.round(range.min * (range.max / range.min) ** s) : s
  return <label className={'lab-slider' + (changed ? ' lab-changed' : '')}>
    <span>{range.label}<output>{changed && <s>was {fmt(was!, range.unit)}</s>}{fmt(value, range.unit)}</output></span>
    <input type="range" min={range.log ? 0 : range.min} max={range.log ? 1 : range.max} step={range.log ? .001 : range.step} value={toSlider(value)} onChange={event => onChange(fromSlider(Number(event.target.value)))} />
    <small><i>{range.low}</i><i>{range.high}</i></small>
  </label>
}

const logX = (hz: number) => Math.log(hz / 40) / Math.log(300)  // 40 Hz-12 kHz
function SourceGraphs({ a, b, active }: { a?: Analysis; b?: Analysis; active: 'A' | 'B' }) {
  const line = (points: [number, number][]) => points.map(([x, db], i) => `${i ? 'L' : 'M'}${(x * 300).toFixed(1)},${(clamp(-db - 20, 0, 100) * 1.2).toFixed(1)}`).join('')
  const wave = (values: number[]) => values.map((v, i) => `${i ? 'L' : 'M'}${i},${(40 - v * 52).toFixed(1)}`).join('')
  const shown = active === 'A' ? a : b, other = active === 'A' ? b : a
  return <div className="lab-graphs">
    <figure>
      <figcaption>Source spectrum <small>{active} solid · {active === 'A' ? 'B' : 'A'} faint · dB</small></figcaption>
      <svg viewBox="-24 -6 330 140" role="img" aria-label="Source spectrum from 40 hertz to 12 kilohertz">
        {[100, 1000, 10000].map(hz => <g key={hz}><line x1={logX(hz) * 300} x2={logX(hz) * 300} y1="0" y2="120" className="lab-gridline" /><text x={logX(hz) * 300} y="132">{hz >= 1000 ? hz / 1000 + 'k' : hz}</text></g>)}
        {[-20, -60, -100].map(db => <g key={db}><line x1="0" x2="300" y1={(-db - 20) * 1.2} y2={(-db - 20) * 1.2} className="lab-gridline" /><text x="-22" y={(-db - 20) * 1.2 + 3}>{db}</text></g>)}
        {other && <path d={line(other.points)} className="lab-trace-faint" />}
        {shown && <path d={line(shown.points)} className="lab-trace" />}
      </svg>
    </figure>
    <figure>
      <figcaption>Waveform <small>first 25 ms</small></figcaption>
      <svg viewBox="0 -6 300 92" role="img" aria-label="Source waveform, first 25 milliseconds">
        <line x1="0" x2="300" y1="40" y2="40" className="lab-gridline" />
        {other && <path d={wave(other.wave)} className="lab-trace-faint" />}
        {shown && <path d={wave(shown.wave)} className="lab-trace" />}
      </svg>
    </figure>
  </div>
}

function DriveChart({ motion, time }: { motion: Motion; time: number | null }) {
  const series = useMemo(() => {
    if (motion.mode === 'source') return null
    const rows = Array.from({ length: 221 }, (_, i) => {
      const t = i / 10, input = simulatedDrive(t), target = drivingSoundTargets(input, false, motion.response, motion.mode as GranularMode, motion.travel)
      return { t, speed: input.speedKmh / 130, pitch: (target.semitones + 14) / 34, level: target.driveGain }
    })
    const path = (key: 'speed' | 'pitch' | 'level') => rows.map((row, i) => `${i ? 'L' : 'M'}${(row.t / 22 * 300).toFixed(1)},${(100 - clamp(row[key], 0, 1) * 100).toFixed(1)}`).join('')
    return { speed: path('speed'), pitch: path('pitch'), level: path('level') }
  }, [motion.mode, motion.response, motion.travel])
  if (!series) return <p className="lab-note">Source only: the raw loop at its own pitch, no driving map.</p>
  const pitchNow = drivingSoundTargets(motion.input === 'drive' ? simulatedDrive(time ?? 0) : manualInput(motion.position, motion.pedal), false, motion.response, motion.mode as GranularMode, motion.travel).semitones
  return <figure className="lab-drive">
    <figcaption>Drive replay <small><b className="k-speed">speed</b> <b className="k-pitch">pitch</b> <b className="k-level">level</b> · now {pitchNow >= 0 ? '+' : ''}{pitchNow.toFixed(1)} st</small></figcaption>
    <svg viewBox="-4 -4 308 120" role="img" aria-label="Speed, pitch and level over the 22 second drive">
      {[0, 5, 10, 15, 20].map(s => <g key={s}><line x1={s / 22 * 300} x2={s / 22 * 300} y1="0" y2="100" className="lab-gridline" /><text x={s / 22 * 300} y="113">{s}s</text></g>)}
      <path d={series.speed} className="k-speed" /><path d={series.pitch} className="k-pitch" /><path d={series.level} className="k-level" />
      {time !== null && motion.input === 'drive' && <line x1={time / 22 * 300} x2={time / 22 * 300} y1="0" y2="100" className="lab-playhead" />}
    </svg>
  </figure>
}

function Scope({ analyser, active }: { analyser: RefObject<AnalyserNode | null>; active: boolean }) {
  const canvas = useRef<HTMLCanvasElement>(null)
  const [view, setView] = useState<'spectrum' | 'spectrogram' | 'waveform'>('spectrogram')
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
    const css = getComputedStyle(element), ink = css.getPropertyValue('--fg').trim() || '#f2f2f2', muted = css.getPropertyValue('--muted').trim() || '#9a9a9a'
    const render = () => {
      const node = analyser.current, on = live.current && !!node
      // Idle: draw one "idle" frame, then stop until playback wakes the loop again.
      frame = on ? requestAnimationFrame(render) : 0
      if (on) { node!.getFloatFrequencyData(freq); node!.getFloatTimeDomainData(samples) } else { freq.fill(-140); samples.fill(0) }
      const rate = node?.context.sampleRate ?? 48000, binHz = rate / 4096
      const yOf = (hz: number) => height - logX(hz) * height
      if (view === 'spectrogram') {
        // Scroll left 2 px, paint the new column: log frequency up, brightness = level.
        draw.drawImage(element, 2 * (window.devicePixelRatio || 1), 0, element.width - 2 * (window.devicePixelRatio || 1), element.height, 0, 0, width - 2, height)
        for (let y = 0; y < height; y++) {
          const hz = 40 * 300 ** ((height - y) / height), db = freq[Math.round(hz / binHz)] ?? -140
          const level = clamp((db + 110) / 80, 0, 1)
          draw.fillStyle = `hsl(${30 + 30 * level} 90% ${level * 62}%)`; draw.fillRect(width - 2, y, 2, 1)
        }
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
      // Readouts: level and brightness of what is playing now.
      let energy = 0, weighted = 0, total = 0
      for (const value of samples) energy += value * value
      for (let k = 1; k < freq.length; k++) { const power = 10 ** (freq[k] / 10); weighted += power * k * binHz; total += power }
      draw.fillStyle = 'rgba(16,16,16,.8)'; draw.fillRect(width - 196, 4, 192, 20)
      draw.fillStyle = muted; draw.font = '11px "IBM Plex Mono", monospace'
      draw.fillText(on ? `${(10 * Math.log10(energy / samples.length + 1e-12)).toFixed(1)} dBFS · ${total ? Math.round(weighted / total) : 0} Hz centroid` : 'idle', width - 190, 18)
      if (view !== 'waveform') { draw.fillStyle = muted; for (const hz of [100, 1000, 10000]) draw.fillText(hz >= 1000 ? hz / 1000 + 'k' : String(hz), view === 'spectrum' ? logX(hz) * width + 3 : 4, view === 'spectrum' ? height - 4 : yOf(hz) - 3) }
    }
    wake.current = () => { if (!frame) frame = requestAnimationFrame(render) }
    wake.current()
    return () => { cancelAnimationFrame(frame); frame = 0; wake.current = () => {}; observer.disconnect() }
  }, [view, analyser])
  useEffect(() => { if (active) wake.current() }, [active])
  return <div className="lab-scope">
    <div className="lab-seg" role="group" aria-label="Scope view">{(['spectrogram', 'spectrum', 'waveform'] as const).map(item => <button key={item} type="button" aria-pressed={view === item} onClick={() => setView(item)}>{item[0].toUpperCase() + item.slice(1)}</button>)}</div>
    <canvas ref={canvas} role="img" aria-label={`Live ${view}`} />
  </div>
}
