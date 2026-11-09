import { useEffect, useRef, useState } from 'react'

type MotionPoint = { time: number; semitones: number; gain: number }
export default function ReferenceReconstruction({ studioPlaying, onPlay }: { studioPlaying: boolean; onPlay: () => void }) {
  const reconstructed = useRef<HTMLAudioElement>(null)
  const mapped = useRef<HTMLAudioElement>(null)
  const steady = useRef<HTMLAudioElement>(null)
  const [motion, setMotion] = useState<MotionPoint[]>([])
  const [position, setPosition] = useState(0)
  useEffect(() => {
    const clips = [reconstructed.current, mapped.current, steady.current]
    const abort = new AbortController()
    void fetch('/audio/bmw_steady_mapping_curve.json?v=3', { signal: abort.signal }).then(response => {
      if (!response.ok) throw Error('Motion plot unavailable')
      return response.json()
    }).then(data => { if (Array.isArray(data) && data.every(p => Number.isFinite(p.time) && Number.isFinite(p.semitones))) setMotion(data) }).catch(() => {})
    return () => { abort.abort(); clips.forEach(clip => clip?.pause()) }
  }, [])
  useEffect(() => {
    if (studioPlaying) { reconstructed.current?.pause(); mapped.current?.pause(); steady.current?.pause() }
  }, [studioPlaying])
  const duration = motion.at(-1)?.time || 14.408
  const path = motion.map((p, i) => `${i ? 'L' : 'M'}${45 + p.time / duration * 660},${145 - (p.semitones + 12) / 30 * 120}`).join(' ')
  return <section className="reference-reconstruction" aria-labelledby="reference-reconstruction-title">
    <h3 id="reference-reconstruction-title">BMW reconstruction comparison <small>Full recording · steady source · mapped source</small></h3>
    <div className="reference-reconstruction-clips">
      <label>BMW spectral reconstruction<audio ref={reconstructed} aria-label="BMW M spectral reconstruction" controls preload="none" src="/audio/bmw_m_resynthesis.wav" onPlay={() => { mapped.current?.pause(); steady.current?.pause(); onPlay() }} /></label>
      <label>Clean BMW-derived source · reconstructed motion<audio ref={mapped} aria-label="BMW steady source with reference-fitted motion" controls preload="none" src="/audio/bmw_steady_mapped.wav?v=3" onTimeUpdate={event => setPosition(event.currentTarget.currentTime)} onPlay={() => { reconstructed.current?.pause(); steady.current?.pause(); onPlay() }} /></label>
    </div>
    <label>Clean BMW-derived steady tone<audio ref={steady} aria-label="BMW-derived steady spectral reconstruction" controls preload="none" src="/audio/bmw_derived_steady_preview.wav?v=2" onPlay={() => { reconstructed.current?.pause(); mapped.current?.pause(); onPlay() }} /></label>
    <p>Clean harmonic interpretation of the recording’s tonal balance. Captured noise and closely spaced sidebands removed. No acceleration curve in the steady version; not BMW’s original source.</p>
    {motion.length > 0 && <svg className="reference-motion-plot" viewBox="0 0 750 175" role="img" aria-label="Pitch contour estimated from the BMW recording">
      <path d="M45 20V145H705" fill="none" stroke="#34434d" />
      <path d={path} fill="none" stroke="var(--accent)" strokeWidth="2.5" />
      <line x1={45 + Math.min(1, position / duration) * 660} x2={45 + Math.min(1, position / duration) * 660} y1="20" y2="145" stroke="#dce5e8" opacity=".5" />
      <text x="1" y="24">+18 st</text><text x="3" y="145">−12 st</text><text x="45" y="165">0 s</text><text x="655" y="165">{duration.toFixed(1)} s</text>
    </svg>}
    <p>Recorded spectral movement estimates the pitch contour; brightness and level follow separate smoothed envelopes. Timed approximation only: no vehicle telemetry or OEM input mapping is available.</p>
  </section>
}
