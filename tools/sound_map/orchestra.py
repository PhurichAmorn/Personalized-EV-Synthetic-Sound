"""Offline sound sets (orchestra.ts: layered orchestral; shepard.ts: Shepard-Risset prototypes; octaves.ts: octave-stack sources): add drive gain and room, write WAVs for
listening and measure the guardrail traits.
  node tools/sound_map/build.mjs && python tools/sound_map/orchestra.py [orchestra|shepard|octaves]   -> tools/sound_map/out/<set>/*.wav, report.json"""
import json, os, subprocess, sys
import numpy as np
from scipy.io import wavfile
from scipy.signal import fftconvolve
from mosqito.sq_metrics import sharpness_din_tv, roughness_dw
from score import FS, SPL, fluctuation, prepare
from generate import LIMITS
from drive import convolver, worst, STEP, AUDIBLE

OUT = sys.argv[1] if len(sys.argv) > 1 else 'orchestra'
MODES = {'orchestra': ('rise', 'evolving'), 'shepard': ('rise',), 'octaves': ('rise', 'evolving')}[OUT]

if __name__ == '__main__':
    prepare()
    subprocess.run(['node', f'{OUT}.mjs', OUT], check=True)
    report = []
    for s in json.load(open(f'{OUT}/sounds.json')):
        fx = s['fx']
        for mode in MODES:
            base = f"{OUT}/{s['id']}.{mode}"
            x = np.fromfile(base + '.f32', np.float32).astype(float).reshape(2, -1)
            gains = np.array(json.load(open(base + '.gain.json')))
            ir = convolver(np.fromfile(f"{OUT}/room-{fx.get('size', 2)}.f32", np.float32).astype(float).reshape(2, -1))
            rev = fx.get('reverb', 0)
            y = (1 - rev * .5) * x + rev * np.array([fftconvolve(x[c], ir[c])[:x.shape[1]] for c in (0, 1)])
            audible = np.flatnonzero(gains >= AUDIBLE); start, end = audible[0] * STEP, (audible[-1] + 1) * STEP
            seg = y.mean(0)[start:end]; seg = seg / np.sqrt(np.mean(seg ** 2)) * 20e-6 * 10 ** (SPL / 20)
            S, tS = sharpness_din_tv(seg, FS); R, _, _, _ = roughness_dw(seg, FS)
            m = {'S': worst(np.asarray(S)[tS > .5], np.asarray(tS)[tS > .5])[0], 'R': worst(np.asarray(R), np.arange(len(R)))[0],
                 'F': max(fluctuation(seg[i:i + 3 * FS]) for i in range(0, max(1, len(seg) - 3 * FS + 1), FS))}
            click = None
            if os.path.exists(base + '.wraps.json'):  # click check: sharpest 5 ms of the second difference near a wrap vs the clip's usual
                wraps = json.load(open(base + '.wraps.json')); os.remove(base + '.wraps.json')
                d2 = np.abs(np.diff(y.mean(0), 2)); win = FS // 200; e = d2[:len(d2) // win * win].reshape(-1, win).max(1)
                near = [e[max(0, int(t * FS) // win - 2):int(t * FS) // win + 3].max() for t in wraps]
                click = {'wraps': len(wraps), 'ratio': round(float(max(near) / np.median(e[e > 0])), 2) if near else None}
            g = np.interp(np.arange(y.shape[1]), np.arange(len(gains)) * STEP, gains)  # drive gain per sample
            w = (y * g).T; w = w / np.max(np.abs(w)) * .7
            wavfile.write(base + '.wav', FS, (w * 32767).astype(np.int16)); os.remove(base + '.f32'); os.remove(base + '.gain.json')
            report.append({'id': s['id'], 'name': s['name'], 'mode': mode, **{k: round(float(v), 3) for k, v in m.items()},
                           'passes': all(m[k] <= LIMITS[k] for k in 'SRF'), **({'click': click} if click else {})})
            print(report[-1], flush=True)
    json.dump(report, open(f'{OUT}/report.json', 'w'), indent=1)
