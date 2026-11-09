"""Render six recipe previews under identical pilot driving inputs.

Run: .venv/bin/python tools/render_recipe_review.py [output directory]
WAVs use unnormalized PCM16; metrics are digital signal proxies, not ISO loudness.
"""

import csv
from pathlib import Path
import sys

import numpy as np
from scipy.io.wavfile import write

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from audio import SoundEngine
from experiment.recipes import RECIPE_NAMES, recipe_controls, recipe_profile


SCENARIOS = {
    'start': lambda t: (0, 0, 0, 0, 'starting' if t < .7 else 'ready'),
    'low': lambda t: (40, 35, .35, .5, 'ready'),
    'high': lambda t: (110, 45, .45, 0, 'ready'),
    'accelerate': lambda t: (20 + 40 * t, 85, .8, 3, 'ready'),
    'regen': lambda t: (100 - 20 * t, 0, -.5, -2, 'ready'),
}


def render_review(output_dir):
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    rate, frames, blocks = 48000, 480, 200
    rows = []
    for mode, ids in RECIPE_NAMES.items():
        for recipe_id in ids:
            for position, value in (('low', 0.), ('base', .5), ('high', 1.)):
                profile = recipe_profile(recipe_id, {group: value for group in recipe_controls(recipe_id)})
                sections = []
                for name, inputs in SCENARIOS.items():
                    engine = SoundEngine(rate)
                    samples = np.empty(blocks * frames, dtype=np.float32)
                    for index in range(blocks):
                        engine.set_driving_parameters(*inputs(index / 100), profile)
                        block = samples[index * frames:(index + 1) * frames].reshape(frames, 1)
                        engine._callback(block, frames, None, None)
                    assert np.isfinite(samples).all() and np.max(np.abs(samples)) < .5
                    steady = samples[-rate:] * np.hanning(rate)
                    spectrum = np.abs(np.fft.rfft(steady)) ** 2
                    frequencies = np.fft.rfftfreq(rate, 1 / rate)
                    upper = spectrum[(frequencies >= 600) & (frequencies <= 900)].sum() / max(spectrum.sum(), 1e-12)
                    rows.append({'recipe': recipe_id, 'mode': mode, 'position': position, 'scenario': name,
                                 'peak_dbfs': f'{20 * np.log10(max(np.max(np.abs(samples)), 1e-9)):.1f}',
                                 'rms_dbfs': f'{20 * np.log10(max(np.sqrt(np.mean(samples ** 2)), 1e-9)):.1f}',
                                 'upper_600_900_share': f'{upper:.3f}'})
                    fade = np.linspace(0, 1, rate // 100)
                    samples[:len(fade)] *= fade
                    samples[-len(fade):] *= fade[::-1]
                    sections.extend((samples, np.zeros(rate // 10, dtype=np.float32)))
                audio = np.concatenate(sections)
                write(output_dir / f'{recipe_id}_{position}.wav', rate, (audio * 32767).astype(np.int16))
    with (output_dir / 'metrics.csv').open('w', newline='') as report:
        writer = csv.DictWriter(report, rows[0])
        writer.writeheader()
        writer.writerows(rows)
    return rows


if __name__ == '__main__':
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else Path('artifacts/recipe_review')
    render_review(target)
    print(f'Eighteen WAVs and metrics.csv: {target}')
