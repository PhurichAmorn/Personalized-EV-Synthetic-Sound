"""Render level-matched fixed acceleration sweeps for sound-direction auditions."""
from pathlib import Path

import numpy as np
from scipy.io.wavfile import write


RATE = 24000
DURATION = 12
TARGET_RMS = 0.13


def render(directory):
    frames = RATE * DURATION
    time = np.arange(frames) / RATE
    position = np.clip((time - 1.0) / 9.0, 0.0, 1.0)
    root_pitch = 110.0 + 88.0 * position

    def tone(ratio, detune=1.0):
        return np.sin(2 * np.pi * np.cumsum(root_pitch * ratio * detune) / RATE)

    cinematic_progress = np.clip(time / (DURATION - 0.8), 0.0, 1.0)
    cinematic_progress = cinematic_progress ** 1.6
    cinematic_rise = cinematic_progress ** 2 * (3.0 - 2.0 * cinematic_progress)
    cinematic_root = 190.0 + 85.0 * cinematic_rise

    cinematic_phase = 2 * np.pi * np.cumsum(cinematic_root) / RATE

    def cinematic_tone(ratio):
        return np.sin(cinematic_phase * ratio)

    cinematic = (
        0.56 * cinematic_tone(1.0)
        + (0.05 + 0.025 * cinematic_rise) * cinematic_tone(2.0)
        + 0.012 * cinematic_rise * cinematic_tone(3.0)
        + 0.004 * cinematic_rise * cinematic_tone(4.0)
    ) * (0.75 + 0.25 * cinematic_rise)
    concepts = {
        "smooth": 0.72 * tone(1.0) + 0.22 * tone(2.0) + 0.06 * tone(3.0),
        "warm": 0.25 * tone(0.5) + 0.56 * tone(1.0) + 0.34 * tone(2.0) + 0.15 * tone(3.0),
        "future": cinematic,
    }
    fade = np.clip(np.minimum(time / 0.8, (DURATION - time) / 0.8), 0.0, 1.0)
    fade = fade * fade * (3.0 - 2.0 * fade)
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    rms_values = []
    for name, signal in concepts.items():
        signal = signal * fade
        if name == "future":
            # Delayed gliding tones create moving interference; keep the baseline dry.
            signal = np.column_stack((signal, signal))
        rms = np.sqrt(np.mean(signal * signal))
        signal = signal * (TARGET_RMS / rms)
        if not np.isfinite(signal).all() or np.max(np.abs(signal)) > 1.0:
            raise RuntimeError(f"Invalid rendered audio: {name}")
        rms_values.append(float(np.sqrt(np.mean(signal * signal))))
        write(directory / f"direction_{name}.wav", RATE, signal.astype(np.float32))
    assert max(rms_values) - min(rms_values) < 1e-6, rms_values


if __name__ == "__main__":
    render("desktop/public/audio")
