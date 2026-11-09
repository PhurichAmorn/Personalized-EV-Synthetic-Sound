"""Render an original legato phrase from our raw source, without reference tracking.

The authored pitch trajectory has zero velocity and acceleration at its knots.
Only pitch and spectral balance vary; no recorded loudness envelope is used.
"""
from pathlib import Path
import json
import numpy as np
from scipy.io.wavfile import read, write
from scipy.ndimage import map_coordinates
from scipy.signal import butter, sosfiltfilt, fftconvolve

PHRASE_SECONDS = 14.4
KNOTS = ((0, 0), (1.0, 0), (4.2, 5), (5.0, 5), (7.8, 1.5), (8.7, 1.5), (11.6, 6), (14.4, 0))


def phrase_curve(time):
    result = np.zeros_like(time, dtype=np.float64)
    for (start, low), (end, high) in zip(KNOTS[:-1], KNOTS[1:]):
        active = (time >= start) & (time < end)
        p = np.clip((time[active]-start)/(end-start), 0, 1)
        ease = p*p*p*(10+p*(-15+6*p))
        result[active] = low + (high-low)*ease
    result[time >= KNOTS[-1][0]] = KNOTS[-1][1]
    return result


def render():
    rate, source = read('desktop/public/audio/original_steady_source.wav')
    room_rate, room = read('desktop/public/audio/original_steady_room_ir.wav')
    if rate != room_rate or source.ndim != 2 or source.shape[1] != 2:
        raise ValueError('Expected stereo source and matching room sample rate')
    source = source.astype(np.float64)
    time = np.arange(round(PHRASE_SECONDS*rate))/rate
    semitones = phrase_curve(time)
    ratio = 2**(semitones/12)
    positions = np.cumsum(ratio)-ratio[0]
    # Continuous source traversal with cubic interpolation; never restart a grain.
    shifted = np.column_stack([map_coordinates(source[:,c], [positions % len(source)], order=3, mode='grid-wrap') for c in range(2)])
    # Open the spectrum gently with the phrase, independently of volume.
    soft = sosfiltfilt(butter(2, 1800, fs=rate, output='sos'), shifted, axis=0)
    open_tone = sosfiltfilt(butter(2, 3600, fs=rate, output='sos'), shifted, axis=0)
    openness = semitones[:,None]/6
    dry = (1-openness)*soft + openness*open_tone
    fade_frames = round(.3*rate)
    fade = np.linspace(0,1,fade_frames)
    fade = fade**3*(10+fade*(-15+6*fade))
    dry[:fade_frames] *= fade[:,None]
    dry[-fade_frames:] *= fade[::-1,None]
    dry_padded = np.pad(dry,((0,len(room)-1),(0,0)))
    wet = np.column_stack([fftconvolve(dry[:,c], room[:,c]) for c in range(2)])
    rms = lambda x: float(np.sqrt(np.mean(x*x)))
    wet *= rms(dry_padded)/max(rms(wet),1e-12)
    output = .76*dry_padded+.24*wet
    output *= .13/max(rms(output[:len(dry)]),1e-12)
    output[-fade_frames:] *= fade[::-1,None]
    peak = float(np.max(np.abs(output)))
    if not np.isfinite(output).all() or peak >= .95:
        raise ValueError(f'Invalid output peak: {peak}')
    write('desktop/public/audio/original_bmw_motion.wav',rate,output.astype(np.float32))
    controls = [{'time':float(t),'semitones':float(p),'gain':1.0} for t,p in zip(time[::1920],semitones[::1920])]
    controls.append({'time':PHRASE_SECONDS,'semitones':0.0,'gain':1.0})
    Path('desktop/public/audio/original_bmw_motion_curve.json').write_text(json.dumps(controls))
    report = {'method':'Authored minimum-jerk legato pitch phrases; continuous cubic source traversal; gentle spectral opening; fixed global gain; room after pitch processing', 'reference_tracking':False,'reference_volume_used':False,'reference_audio_mixed':False,'vehicle_inputs':False,'knots':KNOTS,'semitone_range':[float(semitones.min()),float(semitones.max())],'maximum_pitch_speed_semitones_per_second':float(np.max(np.abs(np.diff(semitones)))*rate),'peak':peak,'control_frames':controls}
    Path('artifacts/bmw_motion').mkdir(parents=True,exist_ok=True)
    Path('artifacts/bmw_motion/analysis.json').write_text(json.dumps(report,indent=2))
    print(json.dumps({k:v for k,v in report.items() if k!='control_frames'},indent=2))


if __name__ == '__main__':
    render()
