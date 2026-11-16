"""Rule-based guardrail check: psychoacoustic metrics for every labelled sound, at cruising and peak pitch.
No training: metrics are standard formulas (MoSQITo); thresholds are read off the table, not fitted."""
import json, os, subprocess, sys
import numpy as np
from scipy.signal import lfilter, hilbert, butter, sosfiltfilt
from mosqito.sq_metrics import loudness_zwtv, sharpness_din_st, roughness_dw

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, 'out')


def prepare():
    """Build the synth bundles and render the labelled sounds once; everything runs inside out/."""
    os.makedirs(OUT, exist_ok=True); os.chdir(OUT)
    if not os.path.exists('synth.mjs'): subprocess.run(['node', os.path.join(HERE, 'build.mjs')], check=True)
    if not os.path.exists('manifest.json'): subprocess.run(['node', 'labelled.mjs'], check=True)


FS, SECONDS, SPL = 48000, 4.0, 70.0  # app level (rms .13) taken as 70 dB SPL
PITCHES = {'cruise': (.6, .4), 'peak': (1.06, 1.0)}  # playback rate, pedal (propulsion)


def lowpass(x, cutoff, q, period=None):
    """RBJ biquad low-pass (as WebAudio). With period: cutoff swings +-1100 cents (the engine's drift), in 10 ms blocks."""
    def coef(f):
        w = 2 * np.pi * min(f, FS * .45) / FS; a = np.sin(w) / (2 * q); c = np.cos(w)
        b = np.array([(1 - c) / 2, 1 - c, (1 - c) / 2]); den = np.array([1 + a, -2 * c, 1 - a])
        return b / den[0], den / den[0]
    if not period:
        return lfilter(*coef(cutoff), x)
    out, zi, block = np.empty_like(x), np.zeros(2), FS // 100
    for i in range(0, len(x), block):
        b, a = coef(cutoff * 2 ** (1100 / 1200 * np.sin(2 * np.pi * i / FS / period)))
        out[i:i + block], zi = lfilter(b, a, x[i:i + block], zi=zi)
    return out


def play(loop, fx, rate, pedal):
    """Approximation of the engine at a fixed pedal: pitch shift, pedal-following low-pass, tremolo/pump.
    Skipped: reverb, chorus, vibrato, rasp (granular-only), body EQ."""
    n = int(FS * SECONDS)
    x = np.interp(np.arange(n) * rate % len(loop), np.arange(len(loop)), loop)
    cutoff = np.clip(fx['tone'] * 2 ** (fx.get('follow', 0) * (2 * pedal - 1)), 200, 20000)
    x = lowpass(x, cutoff, fx.get('res', .6), fx.get('driftPeriod', 14) if fx.get('drift') else None)
    if fx.get('tremDepth'):
        t = np.arange(n) / FS * fx['tremRate']
        lfo = 2 * (t % 1) - 1 if fx.get('pump') else np.sin(2 * np.pi * t)
        x *= 1 - fx['tremDepth'] / 2 + fx['tremDepth'] / 2 * lfo
    return x / np.sqrt(np.mean(x ** 2)) * 20e-6 * 10 ** (SPL / 20)  # Pa


def fluctuation(x):
    """Slow loudness swing: envelope modulation depth in the 0.5-20 Hz band (proxy; MoSQITo has no fluctuation strength)."""
    env = np.abs(hilbert(x))
    env = sosfiltfilt(butter(2, [.5, 20], 'bandpass', fs=FS, output='sos'), env)[FS // 2:-FS // 2]
    return float(np.sqrt(2) * env.std() / np.abs(hilbert(x)).mean())


def dissonance(partials, rate):
    """Sethares (1993) sensory dissonance of the partial list, normalised by total amplitude squared."""
    p = np.array([q for q in partials if q[1] > 1e-3]); f, a = p[:, 0] * rate, p[:, 1]
    lo, df = np.minimum.outer(f, f), np.abs(np.subtract.outer(f, f))
    s = .24 / (.0207 * lo + 18.96)
    return float((np.outer(a, a) * (np.exp(-3.5 * s * df) - np.exp(-5.75 * s * df))).sum() / 2 / a.sum() ** 2)


def annoyance(n5, s, r, f):
    """Zwicker & Fastl psychoacoustic annoyance (Fastl & Zwicker, Psychoacoustics, 2007, eq. 16.3)."""
    ws = (s - 1.75) * .25 * np.log10(n5 + 10) if s > 1.75 else 0
    wfr = 2.18 / n5 ** .4 * (.4 * f + .6 * r)
    return float(n5 * (1 + np.sqrt(ws ** 2 + wfr ** 2)))


if __name__ == '__main__':
  prepare()
  rows = []
  for item in json.load(open('manifest.json')):
      loop = np.fromfile(f"audio/{item['id']}.f32", dtype=np.float32).astype(float)
      row = {'id': item['id'], 'name': item['name'], 'label': item['label'], 'why': item['why']}
      for where, (rate, pedal) in PITCHES.items():
          x = play(loop, item['fx'], rate, pedal)
          n = loudness_zwtv(x, FS)[0]; n5 = float(np.percentile(n[len(n) // 4:], 95))
          s = float(sharpness_din_st(x, FS))
          r = float(np.mean(roughness_dw(x[:FS * 2], FS)[0]))
          fl = fluctuation(x)
          row[where] = dict(N5=n5, S=s, R=r, F=fl, D=dissonance(item['partials'], rate), PA=annoyance(n5, s, r, fl * 4))
      rows.append(row); print(item['id'], file=sys.stderr)
  json.dump(rows, open('scores.json', 'w'), indent=1)
  # Self-check: the guardrail rule (generate.LIMITS) must reject both Drops and pass every kept sound.
  from generate import LIMITS
  flagged = {r['id'] for r in rows if any(max(r['cruise'][k], r['peak'][k]) > LIMITS[k] for k in LIMITS)}
  for r in rows: print(f"{r['name'][:22]:24}{r['label']:12}{'REJECT' if r['id'] in flagged else 'pass'}")
  assert {'growl', 'sweep'} <= flagged, 'guardrail missed a dropped sound'
  assert not flagged & {r['id'] for r in rows if r['label'] == 'ok'}, 'guardrail rejected a kept sound'
  print('guardrail check OK')
