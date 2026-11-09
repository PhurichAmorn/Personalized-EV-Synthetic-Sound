"""Render a smooth, unmapped ascending organ line for listening."""
from pathlib import Path
import sys

import numpy as np
from scipy.io.wavfile import write


RATE = 48000
NOTE_SECONDS = 1.2
NOTE_STEP_SECONDS = 0.9
TRANSITION_SECONDS = NOTE_SECONDS - NOTE_STEP_SECONDS
NOTES = (
    130.813, 146.832, 164.814, 174.614, 196.000, 220.000, 246.942,
    261.626, 293.665, 329.628, 349.228, 392.000, 440.000, 493.883,
    523.251, 587.330, 659.255, 698.456, 783.991, 880.000, 987.767, 1046.502,
)
PIPE_STOPS = ((1.0, 0.62), (2.0, 0.22), (3.0, 0.095), (4.0, 0.04),
              (5.0, 0.018), (6.0, 0.008))
DURATION = NOTE_SECONDS + (len(NOTES) - 1) * NOTE_STEP_SECONDS


def smoothstep(value):
    value = np.clip(value, 0.0, 1.0)
    return value * value * (3.0 - 2.0 * value)


def organ_note(frequency, times):
    signal = np.zeros(times.size, dtype=np.float64)
    for ratio, level in PIPE_STOPS:
        signal += level * np.sin(2.0 * np.pi * frequency * ratio * times)
    return signal


def render(output):
    frames = int(RATE * DURATION)
    times = np.arange(frames, dtype=np.float64) / RATE
    mono = np.zeros(frames, dtype=np.float64)

    for index, frequency in enumerate(NOTES):
        start = index * NOTE_STEP_SECONDS
        local = times - start
        active = (local >= 0.0) & (local < NOTE_SECONDS)
        weight = np.zeros(frames, dtype=np.float64)
        weight[active] = 1.0
        if index > 0:
            fade_in = active & (local < TRANSITION_SECONDS)
            weight[fade_in] = np.sin(0.5 * np.pi * smoothstep(local[fade_in] / TRANSITION_SECONDS))
        if index < len(NOTES) - 1:
            fade_out = active & (local >= NOTE_STEP_SECONDS)
            phase = (local[fade_out] - NOTE_STEP_SECONDS) / TRANSITION_SECONDS
            weight[fade_out] = np.cos(0.5 * np.pi * smoothstep(phase))
        mono += organ_note(frequency, times) * weight

    fade_frames = int(0.8 * RATE)
    mono[:fade_frames] *= smoothstep(np.linspace(0.0, 1.0, fade_frames))
    mono[-fade_frames:] *= smoothstep(np.linspace(1.0, 0.0, fade_frames))
    mono *= 0.22

    # Fixed early reflections add a little room without moving pitch or level.
    stereo = np.column_stack((mono, mono))
    dry = stereo.copy()
    for delay_ms, gain, crossfeed in ((17, 0.075, 0.20), (29, 0.045, 0.35), (43, 0.025, 0.50)):
        delay = round(RATE * delay_ms / 1000.0)
        stereo[delay:, 0] += gain * ((1.0 - crossfeed) * dry[:-delay, 0] + crossfeed * dry[:-delay, 1])
        stereo[delay:, 1] += gain * ((1.0 - crossfeed) * dry[:-delay, 1] + crossfeed * dry[:-delay, 0])

    peak = float(np.max(np.abs(stereo)))
    if not np.isfinite(stereo).all() or peak > 1.0:
        raise RuntimeError(f'Invalid rendered audio peak: {peak}')
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    write(output, RATE, stereo.astype(np.float32))
    rms = float(np.sqrt(np.mean(stereo * stereo)))
    print(f'{output}: {DURATION:.1f} s, 48 kHz stereo, C3 ascending through C6')
    print('Legato note overlaps; no vehicle mapping, tremolo, or vibrato.')
    print(f'Peak: {20 * np.log10(max(peak, 1e-12)):.1f} dBFS; RMS: {20 * np.log10(max(rms, 1e-12)):.1f} dBFS')


if __name__ == '__main__':
    render(sys.argv[1] if len(sys.argv) > 1 else 'artifacts/organ_preview.wav')
