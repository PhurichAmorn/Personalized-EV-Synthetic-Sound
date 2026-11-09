"""Original periodic source material: fixed pitch, no acceleration or vehicle mapping."""
from pathlib import Path
import json
import numpy as np
if __package__:
    from .source_voice import bowed_tone, organic_motion, source_dimension
else:
    from source_voice import bowed_tone, organic_motion, source_dimension
from scipy.io.wavfile import write
from scipy.signal import butter, sosfilt

RATE = 48000
SECONDS = 5
ROOT_HZ = 174.8  # Whole cycles for the root and fifth over the five-second loop.


def render(directory):
    frames = RATE * SECONDS
    time = np.arange(frames, dtype=np.float64) / RATE
    phase = 2 * np.pi * ROOT_HZ * time
    # Low ensemble body, gentle bow-like vibrato, and restrained upper strings.
    motion,pressure=organic_motion(time,ROOT_HZ,117)
    body = bowed_tone(phase+motion,ROOT_HZ)*pressure
    pad = np.zeros(frames)
    for voice, (multiple, weight) in enumerate(((.75,.55),(1.5,.35),(2.,.10))):
        frequency = round(ROOT_HZ*multiple*SECONDS)/SECONDS
        motion,pressure=organic_motion(time,frequency,211+voice)
        voice_phase=2*np.pi*frequency*time+.4*voice+motion
        pad += weight*bowed_tone(voice_phase,frequency)*pressure
    glass = .7*np.sin(2*phase)+.2*np.sin(3*phase)+.1*np.sin(4*phase)
    # Periodic, spectrally shaped noise supplies a quiet air texture, without rumble.
    frequencies = np.fft.rfftfreq(frames, 1 / RATE)
    envelope = np.exp(-.5 * ((frequencies - 1400) / 550) ** 2)
    envelope[frequencies < 350] = 0
    envelope[frequencies > 4500] = 0
    rng = np.random.default_rng(2819)
    spectrum = envelope * np.exp(1j * rng.uniform(-np.pi, np.pi, len(frequencies)))
    spectrum[0] = 0; spectrum[-1] = 0
    air = np.fft.irfft(spectrum, n=frames)
    rms = lambda x: float(np.sqrt(np.mean(x * x)))
    layers = {'body': body / rms(body) * .095, 'pad': pad / rms(pad) * .065, 'glass': glass / rms(glass) * .004, 'air': air / rms(air) * .001}
    layers = {name: source_dimension(signal, RATE) for name, signal in layers.items()}
    source = sum(layers.values())
    scale = .13 / rms(source)
    source *= scale
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    for name, signal in layers.items():
        write(directory / f'original_steady_{name}.wav', RATE, (signal * scale).astype(np.float32))
    if not np.isfinite(source).all() or np.max(np.abs(source)) >= .85:
        raise ValueError('Invalid source level')
    write(directory / 'original_steady_source.wav', RATE, source.astype(np.float32))
    # A fixed stereo room response adds depth without detuning or moving the pitch.
    room_frames = int(2.2 * RATE)
    room_time = np.arange(room_frames) / RATE
    room_rng = np.random.default_rng(462)
    room_filter = butter(2, [180, 2400], btype='bandpass', fs=RATE, output='sos')
    wet = []
    impulses = []
    for channel, early in enumerate((.031, .043)):
        impulse = sosfilt(room_filter, room_rng.standard_normal(room_frames))
        impulse *= np.exp(-np.log(1000) * room_time / 1.8)
        impulse[:int(.022 * RATE)] = 0
        impulse /= np.sqrt(np.sum(impulse * impulse))
        impulse[round(early * RATE)] += .18
        impulse[round((early + .047) * RATE)] += .09
        impulse[round((.067 if channel == 0 else .089) * RATE)] += .07
        impulses.append(impulse)
        # Circular convolution renders the room in its continuous steady state.
        wet.append(np.fft.irfft(np.fft.rfft(source[:, channel]) * np.fft.rfft(impulse, n=frames), n=frames))
    write(directory / 'original_steady_room_ir.wav', RATE, np.column_stack(impulses).astype(np.float32))
    wet = np.column_stack(wet)
    wet *= rms(source) / rms(wet)
    spatial = .68 * source + .32 * wet
    spatial *= .13 / rms(spatial)
    if not np.isfinite(spatial).all() or np.max(np.abs(spatial)) >= .85:
        raise ValueError('Invalid spatial source level')
    write(directory / 'original_steady_spatial.wav', RATE, spatial.astype(np.float32))

    fade = np.clip(np.minimum(time / .3, (SECONDS - time) / .3), 0, 1)
    fade = fade * fade * (3 - 2 * fade)
    write(directory / 'original_steady_preview.wav', RATE, (source * fade[:, None]).astype(np.float32))
    report = {'sample_rate': RATE, 'duration_seconds': SECONDS, 'root_hz': ROOT_HZ, 'pitch_motion': False, 'vehicle_mapping': False, 'rms': rms(source), 'peak': float(np.max(np.abs(source))), 'layers': list(layers), 'seed': 2819, 'room': {'wet_mix': .32, 'decay_seconds': 1.8, 'predelay_seconds': .022, 'seed': 462}, 'source_dimension': 'Stereo early reflections at 26–147 ms, dark returns, no feedback', 'method': 'Original low cello/viola-inspired harmonic ensemble, seeded irregular bow drift and pressure, restrained upper strings, quiet air; no recorded instrument or BMW audio.'}
    Path('artifacts/steady_source').mkdir(parents=True, exist_ok=True)
    Path('artifacts/steady_source/design.json').write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    render('desktop/public/audio')
