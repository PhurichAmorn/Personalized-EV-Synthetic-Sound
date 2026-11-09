"""Build a stationary BMW-derived spectral texture, not the unknown OEM source."""
from pathlib import Path
import json
import numpy as np
from scipy.io.wavfile import read, write
from scipy.signal import stft
from scipy.ndimage import median_filter


def describe(signal, rate):
    if signal.ndim == 2:
        signal = signal.mean(axis=1)
    f, _, z = stft(signal, fs=rate, nperseg=8192, noverlap=6144)
    power = np.mean(np.abs(z)**2, axis=1)
    total = max(float(power.sum()), 1e-20)
    return {'rms_dbfs':float(20*np.log10(max(np.sqrt(np.mean(signal**2)),1e-12))), 'centroid_hz':float(np.sum(f*power)/total), 'energy_below_200_hz':float(power[f<200].sum()/total), 'energy_200_1000_hz':float(power[(f>=200)&(f<1000)].sum()/total), 'energy_above_1000_hz':float(power[f>=1000].sum()/total)}


def clean_spectrum(magnitude, rate, seconds):
    frequencies=np.arange(len(magnitude))*rate/(2*(len(magnitude)-1))
    tonal=np.maximum(magnitude-median_filter(magnitude,size=31),0)
    candidates=np.arange(45*seconds,60*seconds+1)/seconds
    harmonics=np.arange(1,25)
    scores=[np.sum(np.interp(root*harmonics,frequencies,tonal)/np.sqrt(harmonics)) for root in candidates]
    root=float(candidates[np.argmax(scores)])
    amplitudes=[]
    for harmonic in harmonics:
        band=np.abs(frequencies-root*harmonic)<root*.22
        amplitudes.append(float(np.sqrt(np.sum(tonal[band]**2))))
    amplitudes=np.array(amplitudes)*np.exp(-harmonics/10)
    frames=rate*seconds
    spectrum=np.zeros(frames//2+1,dtype=np.complex128)
    # One coherent harmonic family; no captured noise or close detuned sidebands.
    for harmonic,amplitude in zip(harmonics,amplitudes):
        spectrum[round(root*harmonic*seconds)]=amplitude*frames/2*np.exp(-1j*np.pi/2)
    return spectrum,root,int(np.count_nonzero(spectrum))


def render():
    rate, recording = read('desktop/public/audio/bmw_m_reference.wav')
    recording = recording.astype(np.float64).mean(axis=1)
    window = rate
    candidates = []
    # Prefer stable, audible one-second regions; do not let trailing silence win.
    global_rms = np.sqrt(np.mean(recording**2))
    for start in range(0,len(recording)-window,rate//10):
        segment = recording[start:start+window]
        rms = np.sqrt(np.mean(segment**2))
        if rms < .5*global_rms:
            continue
        f, t, z = stft(segment, fs=rate, nperseg=8192, noverlap=7168, boundary=None)
        magnitude = np.abs(z)
        band = (f>=40)&(f<=2000)
        normalized = magnitude[band]/np.maximum(np.linalg.norm(magnitude[band],axis=0),1e-12)
        flux = float(np.mean(np.linalg.norm(np.diff(normalized,axis=1),axis=0)))
        centroid = np.sum(f[band,None]*magnitude[band]**2,axis=0)/np.maximum(np.sum(magnitude[band]**2,axis=0),1e-20)
        score = flux + .25*float(np.std(np.log2(np.maximum(centroid,1))))
        candidates.append((score,start))
    if not candidates:
        raise ValueError('No sufficiently audible source region')
    score,start = min(candidates)
    segment = recording[start:start+window]
    fft = np.fft.rfft(segment*np.hanning(window))
    magnitude = np.abs(fft)
    f = np.fft.rfftfreq(window,1/rate)
    seconds=12;frames=rate*seconds
    spectrum,root,partial_count=clean_spectrum(magnitude,rate,seconds)
    steady=np.fft.irfft(spectrum,n=frames)
    rms=lambda x:float(np.sqrt(np.mean(x*x)))
    steady*=.13/max(rms(steady),1e-12)
    if not np.isfinite(steady).all() or np.max(np.abs(steady))>=.95:
        raise ValueError('Invalid steady-source peak')
    assert abs(rms(steady)-.13)<1e-8
    assert abs(steady[0]-steady[-1])<=np.max(np.abs(np.diff(steady)))*1.01
    sections=[describe(section,rate) for section in np.array_split(steady,3)]
    assert np.ptp([section['energy_below_200_hz'] for section in sections])<.03
    output=Path('desktop/public/audio')
    write(output/'bmw_derived_steady.wav',rate,steady.astype(np.float32))
    time=np.arange(frames)/rate
    fade=np.clip(np.minimum(time/.3,(seconds-time)/.3),0,1)
    fade=fade*fade*(3-2*fade)
    write(output/'bmw_derived_steady_preview.wav',rate,(steady*fade).astype(np.float32))
    source_rate,ours=read(output/'original_steady_source.wav')
    report={'method':'Clean harmonic interpretation: fitted harmonic family, no residual noise or detuned sidebands', 'not_original_oem_source':True,'selected_region_seconds':[start/rate,start/rate+1], 'region_stability_score':score,'partial_count':partial_count,'fundamental_hz':root,'residual_noise_gain':0,'duration_seconds':seconds,'peak':float(np.max(np.abs(steady))),'reference_region':describe(segment,rate),'bmw_derived_steady':describe(steady,rate),'our_steady':describe(ours.astype(float),source_rate)}
    Path('artifacts/bmw_steady').mkdir(parents=True,exist_ok=True)
    Path('artifacts/bmw_steady/analysis.json').write_text(json.dumps(report,indent=2))
    print(json.dumps(report,indent=2))


if __name__=='__main__':
    render()
