import { roomImpulse } from './plainSource'

/** Welcome sound for the start-up sweep, modelled on the measured "Heaven Choir" reference (GameChestAudio, preview analysed
 * 2026-11-18): a female choir on a steady Dmaj9 chord (D5 strongest; F#5, A5, D6; F#4, A4 below; C#6, E6 shimmer), each note sung by
 * a wide ensemble (+-20-40 cents), fully wide stereo, soft breath above 8 kHz, a 1.5 s swell and a long hall decay. Its pitch does not
 * glide; the lift comes from the swell, and here also from the notes entering low to high. Plain WebAudio, built at once. */
export function playWelcome(volume = .16) { void playRecorded().then(played => { if (!played) synthChoir(volume) }) }

/** A recorded welcome (owner's licensed clip, e.g. Envato "Heaven Choir") if present at public/audio/welcome.wav or .mp3:
 * the first 2.5 s with a fade-out. Git-ignored: a licensed sound file must not go into the public repo. */
async function playRecorded() {
  for (const name of ['welcome.wav', 'welcome.mp3']) {
    try {
      const response = await fetch(`/audio/${name}`); if (!response.ok || !response.headers.get('content-type')?.startsWith('audio')) continue
      const audio = new AudioContext(), buffer = await audio.decodeAudioData(await response.arrayBuffer())
      const source = audio.createBufferSource(), gain = audio.createGain(), now = audio.currentTime, length = Math.min(2.5, buffer.duration)
      source.buffer = buffer; source.connect(gain); gain.connect(audio.destination)
      gain.gain.setValueAtTime(.8, now); gain.gain.setValueAtTime(.8, now + length - .8); gain.gain.linearRampToValueAtTime(0, now + length)
      source.start(now); source.stop(now + length); source.onended = () => void audio.close()
      return true
    } catch { /* missing or unreadable: try the next, then the synth */ }
  }
  return false
}

function synthChoir(volume: number) {
  const audio = new AudioContext(), now = audio.currentTime, swell = .35, release = now + 2.2  // comes in at once (1.2 s felt late)
  const out = audio.createGain(), dry = audio.createGain(), wet = audio.createGain(), reverb = audio.createConvolver(), soft = audio.createBiquadFilter()
  const [l, r] = roomImpulse(audio.sampleRate, 2.5), impulse = audio.createBuffer(2, l.length, audio.sampleRate)
  impulse.copyToChannel(l, 0); impulse.copyToChannel(r, 1); reverb.buffer = impulse
  soft.type = 'lowpass'; soft.frequency.value = 5500; soft.Q.value = .5
  dry.gain.value = .45; wet.gain.value = .9  // the reference's decay is mostly hall
  soft.connect(out); out.connect(dry); out.connect(reverb); reverb.connect(wet); dry.connect(audio.destination); wet.connect(audio.destination)
  out.gain.setValueAtTime(0, now); out.gain.linearRampToValueAtTime(volume, now + swell); out.gain.setValueAtTime(volume, now + 1.3)
  out.gain.exponentialRampToValueAtTime(.0001, release)
  // Voice: harmonics falling as 1/n^1.3, vowel peak at 1.2 kHz, low-pass 5.5 kHz: matched to the reference's octave bands within
  // about 2 dB (spectral centre 1090 vs 1104 Hz, offline numpy render of this design, 2026-11-18).
  const peak = audio.createBiquadFilter(); peak.type = 'peaking'; peak.frequency.value = 1200; peak.Q.value = 1; peak.gain.value = 5; peak.connect(soft)
  const harmonics = 12, real = new Float32Array(harmonics + 1), imag = new Float32Array(harmonics + 1)
  for (let n = 1; n <= harmonics; n++) imag[n] = 1 / n ** 1.3
  const voice = audio.createPeriodicWave(real, imag), stop = release + .05
  // Breath: quiet noise above 7 kHz following the swell (the reference's air band sits about 20 dB down).
  const noise = audio.createBuffer(1, audio.sampleRate * 3, audio.sampleRate), data = noise.getChannelData(0)
  for (let i = 0; i < data.length; i++) data[i] = Math.random() * 2 - 1
  const breath = audio.createBufferSource(), air = audio.createBiquadFilter(), airGain = audio.createGain()
  breath.buffer = noise; air.type = 'highpass'; air.frequency.value = 7000; airGain.gain.value = .08
  breath.connect(air); air.connect(airGain); airGain.connect(out); breath.start(now); breath.stop(stop)
  // Dmaj9, entering low to high over 0.2 s: [Hz, level]. Depth: a low D3-A3-D4 underneath (not in the reference; asked for 2026-11-18).
  const chord: [number, number][] = [[146.8, .55], [220, .3], [293.7, .5], [370, .3], [440, .4], [587.3, 1], [740, .65], [880, .55], [1109, .3], [1174.7, .45], [1318.5, .25]]
  const singers = [[-30, -.9], [-12, -.35], [10, .35], [28, .9]]  // detune cents and pan: a wide ensemble, nothing in the centre
  chord.forEach(([hz, level], k) => {
    const enter = now + .2 * k / (chord.length - 1)
    for (const [cents, pan] of singers) {
      const osc = audio.createOscillator(), vib = audio.createOscillator(), vibDepth = audio.createGain(), gain = audio.createGain(), panner = audio.createStereoPanner()
      osc.setPeriodicWave(voice); osc.frequency.value = hz; osc.detune.value = cents + (k % 3 - 1) * 3
      vib.frequency.value = 4.8 + (cents + 30) / 60; vibDepth.gain.value = hz * .003; vib.connect(vibDepth); vibDepth.connect(osc.frequency)
      gain.gain.setValueAtTime(0, enter); gain.gain.linearRampToValueAtTime(level / singers.length, enter + .25); panner.pan.value = pan
      osc.connect(gain); gain.connect(panner); panner.connect(peak)
      osc.start(enter); vib.start(enter); osc.stop(stop); vib.stop(stop)
    }
  })
  window.setTimeout(() => void audio.close(), (stop - audio.currentTime + 2.6) * 1000)  // after the hall tail
}
