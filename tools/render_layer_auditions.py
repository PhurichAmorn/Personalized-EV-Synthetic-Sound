"""Render fixed, unmapped multi-layer sound audition candidates."""
from pathlib import Path

import numpy as np
from scipy.io.wavfile import write


RATE = 24000
DURATION = 12


def smoothstep(value):
    value = np.clip(value, 0.0, 1.0)
    return value * value * (3.0 - 2.0 * value)


def render(directory):
    frames = RATE * DURATION
    time = np.arange(frames, dtype=np.float64) / RATE
    fade = smoothstep(np.minimum(time / 0.8, (DURATION - time) / 0.8))
    base = 0.19 * np.sin(2 * np.pi * 130.81 * time) + 0.045 * np.sin(2 * np.pi * 261.63 * time)
    rise = smoothstep(np.clip((time - 1.0) / 8.0, 0.0, 1.0))
    load_pitch = 174.61 + 52.0 * rise
    load_phase = 2 * np.pi * np.cumsum(load_pitch) / RATE
    load = rise * (0.12 * np.sin(load_phase) + 0.045 * np.sin(2 * load_phase))
    texture_pitch = 580.0 + 90.0 * rise
    texture_phase = 2 * np.pi * np.cumsum(texture_pitch) / RATE
    texture = rise * (0.09 * np.sin(texture_phase) + 0.045 * np.sin(1.31 * texture_phase))
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    for name, signal in (("foundation", base), ("load", base + load), ("texture", base + load + texture)):
        mono = signal * fade
        if not np.isfinite(mono).all() or np.max(np.abs(mono)) > 1.0:
            raise RuntimeError(f"Invalid rendered audio: {name}")
        write(directory / f"layers_{name}.wav", RATE, mono.astype(np.float32))


if __name__ == "__main__":
    render("desktop/public/audio")
