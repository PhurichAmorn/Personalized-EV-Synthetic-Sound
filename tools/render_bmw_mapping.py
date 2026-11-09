"""Approximate recorded BMW motion using a stationary source, not OEM telemetry."""
from pathlib import Path
import json
import numpy as np
from scipy.io.wavfile import read, write
from scipy.signal import stft, savgol_filter, butter, sosfiltfilt
from scipy.ndimage import map_coordinates, gaussian_filter1d
from scipy.interpolate import CubicSpline


def smooth_pitch(time, estimate):
    # Suppress harmonic-fit jitter before interpolation, including rapid octave switches.
    seconds=max(.55,float(np.ptp(estimate))/(10*np.sqrt(2*np.pi)))
    filtered=gaussian_filter1d(estimate,seconds/float(np.median(np.diff(time))),mode='nearest')
    return CubicSpline(time,filtered,bc_type='clamped')


def render():
    root=Path('desktop/public/audio')
    rate, reference=read(root/'bmw_m_reference.wav')
    source_rate, source=read(root/'bmw_derived_steady.wav')
    assert rate==source_rate and source.ndim==1
    reference=reference.astype(float).mean(axis=1)
    f,t,z=stft(reference,fs=rate,nperseg=8192,noverlap=6144)
    magnitude=np.abs(z)
    # Register many spectral features rather than treating the loudest peak as pitch.
    frequencies=np.geomspace(40,1600,384)
    template=np.mean(magnitude[:,(t>=3.7)&(t<=4.7)],axis=1)
    shifts=np.linspace(-12,18,241)
    templates=np.array([np.interp(frequencies/2**(shift/12),f,template) for shift in shifts])
    observed=np.array([np.interp(frequencies,f,frame) for frame in magnitude.T])
    def features(x):
        x=np.log(np.maximum(x,1e-7))
        x=x-gaussian_filter1d(x,12,axis=1)
        return x/np.maximum(np.linalg.norm(x,axis=1,keepdims=True),1e-12)
    scores=features(observed)@features(templates).T
    # A continuous path avoids octave jumps from ambiguous harmonics.
    penalty=.08*(shifts[:,None]-shifts[None,:])**2
    cost=-scores[0]; parents=[]
    for frame in scores[1:]:
        choices=cost[:,None]+penalty
        parent=np.argmin(choices,axis=0)
        cost=choices[parent,np.arange(len(shifts))]-frame
        parents.append(parent)
    path=[int(np.argmin(cost))]
    for parent in parents[::-1]: path.append(int(parent[path[-1]]))
    path=np.array(path[::-1])
    pitch=savgol_filter(shifts[path],9,2)
    pitch=np.clip(pitch,-12,18)
    energy=np.sqrt(np.sum(magnitude*magnitude,axis=0))
    # The quiet recording tail contains weak pitch evidence: hold instead of wandering.
    audible=energy>.12*max(np.percentile(energy,75),1e-12)
    for index in range(1,len(pitch)):
        if not audible[index]: pitch[index]=pitch[index-1]
    gain=savgol_filter(np.clip(energy/max(np.percentile(energy,75),1e-12),0,1.5)**.6,9,2)
    gain=np.clip(gain,0,1.5)
    power=magnitude*magnitude
    brightness=np.sum(power[f>=200],axis=0)/np.maximum(np.sum(power,axis=0),1e-12)
    brightness=np.clip(savgol_filter(brightness,9,2),0,1)
    time=np.arange(len(reference))/rate
    pitch_curve=smooth_pitch(t,pitch)
    semitones=pitch_curve(time)
    pitch=pitch_curve(t)
    ratio=2**(semitones/12)
    positions=np.cumsum(ratio)-ratio[0]
    shifted=map_coordinates(source.astype(float),[positions%len(source)],order=3,mode='grid-wrap')
    low=sosfiltfilt(butter(2,200,fs=rate,output='sos'),shifted)
    high=shifted-low
    # Broad spectral tilt follows the recording separately from pitch and loudness.
    opening=np.interp(time,t,brightness)
    audio=(low+(0.5+2*opening)*high)*np.interp(time,t,gain)
    fade=np.clip(np.minimum(time/.12,(time[-1]-time)/.18),0,1)
    audio*=fade*fade*(3-2*fade)
    audio*=.13/max(np.sqrt(np.mean(audio**2)),1e-12)
    peak=float(np.max(np.abs(audio)))
    if peak>.9: audio*=.9/peak
    assert np.isfinite(audio).all() and np.max(np.abs(audio))<=.901
    maximum_pitch_speed=float(np.max(np.abs(pitch_curve(time,1))))
    assert maximum_pitch_speed<12
    write(root/'bmw_steady_mapped.wav',rate,audio.astype(np.float32))
    controls=[{'time':float(a),'semitones':float(b),'gain':float(c)} for a,b,c in zip(t,pitch,gain)]
    (root/'bmw_steady_mapping_curve.json').write_text(json.dumps(controls))
    report={'method':'Log-spectrum registration, broad Gaussian pitch smoothing and continuous cubic interpolation, spectral tilt and compressed recorded level envelope', 'oem_input_mapping_recovered':False,'reference_waveform_mixed':False,'pitch_range_semitones':[float(pitch.min()),float(pitch.max())], 'maximum_pitch_speed_semitones_per_second':maximum_pitch_speed,'mean_spectral_registration_score':float(np.mean(scores[np.arange(len(path)),path])), 'peak':float(np.max(np.abs(audio)))}
    out=Path('artifacts/bmw_steady');out.mkdir(parents=True,exist_ok=True)
    (out/'mapping_analysis.json').write_text(json.dumps(report,indent=2))
    print(json.dumps(report,indent=2))


if __name__=='__main__': render()
