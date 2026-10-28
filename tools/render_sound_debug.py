"""Render independent audio-input sweeps without a vehicle, UI or audio device.

Run: .venv/bin/python tools/render_sound_debug.py [output.wav]
Each section lasts 8 seconds: speed, pedal, signed load, acceleration pulse.
"""
from pathlib import Path
import sys

import numpy as np
from scipy.io.wavfile import write

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from audio import DEBUG_THEMES
from audio import SoundEngine


def render_debug(output):
    rate, frames = 48000, 480
    chunks = []
    profile = DEBUG_THEMES['Comfort / Dynamic Orders']
    for section in range(4):
        engine = SoundEngine(rate)
        for i in range(800):
            t = i / 100
            speed, pedal, load, acceleration = 70, 50, .5, 0
            if section == 0:
                speed = 220 * t / 8
            elif section == 1:
                pedal = 100 * t / 8
            elif section == 2:
                load = -1 + 2 * t / 8
            else:
                acceleration = 8 if 2 <= t < 6 else 0
            engine.set_driving_parameters(speed, pedal, load, acceleration, 'ready', profile)
            block = np.empty((frames, 1), dtype=np.float32)
            engine._callback(block, frames, None, None)
            chunks.append(block[:, 0].copy())
        chunks.append(np.zeros(rate, dtype=np.float32))
    samples = np.concatenate(chunks)
    # Fade only segment boundaries; no level normalization hides the control changes.
    for start in range(0, len(samples), rate * 9):
        fade = np.linspace(0, 1, rate // 50)
        samples[start:start + len(fade)] *= fade
        end = start + rate * 8
        samples[end - len(fade):end] *= fade[::-1]
    assert np.isfinite(samples).all() and np.max(np.abs(samples)) < .5
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    write(output, rate, samples)
    print(f'{output}: A speed 0–8s; B pedal 9–17s; C load 18–26s; D acceleration 27–35s')
    print(f'Peak: {20 * np.log10(max(np.max(np.abs(samples)), 1e-12)):.1f} dBFS')


if __name__ == '__main__':
    render_debug(sys.argv[1] if len(sys.argv) > 1 else 'artifacts/sound_input_debug.wav')
