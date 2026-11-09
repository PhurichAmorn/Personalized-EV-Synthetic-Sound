"""Offline diagnostics for continuous EV audio; no aesthetic score or model inference."""
import time
import numpy as np
from scipy.ndimage import uniform_filter1d
from scipy.signal import hilbert,resample_poly,stft,welch

POLICY='continuous-ev-v1'
THRESHOLDS={
    'impulse_curvature_floor':.005,'impulse_percentile_multiplier':8,
    'loop_curvature_floor':.0005,'dropout_min_ms':3,'dropout_max_ms':100,
    'high_band_start_hz':6000,'high_band_energy_share':.08,
    'whistle_start_hz':2500,'whistle_peak_share':.08,
    'broad_upper_energy_share':.35,'spectral_active_fraction':.25,
    'modulation_min_seconds':6,
}
MODULATION_BANDS={'fluct_0.5-20':(.5,20),'grain_20-30':(20,30),'rough_30-150':(30,150)}


def _runs(mask):
    changes=np.diff(np.r_[False,mask,False].astype(np.int8))
    return np.flatnonzero(changes==1),np.flatnonzero(changes==-1)


def modulation_depth(audio,rate,skip_seconds=2.):
    """Relative envelope modulation (rms of env/local_mean-1) per band, plus peak modulation rate in 2-200 Hz."""
    mono=audio.mean(1) if audio.ndim==2 else audio
    envelope=np.abs(hilbert(mono))[round(skip_seconds*rate):]
    relative=envelope/np.maximum(uniform_filter1d(envelope,rate),1e-9)-1  # 1 s mean removes the drive level ramp.
    freqs,power=welch(relative,fs=rate,nperseg=2*rate);step=freqs[1]-freqs[0]
    result={name:float(np.sqrt(power[(freqs>=lo)&(freqs<hi)].sum()*step)) for name,(lo,hi) in MODULATION_BANDS.items()}
    window=(freqs>=2)&(freqs<=200);result['peak_hz']=float(freqs[window][np.argmax(power[window])])
    return result


def check_signal(samples,sample_rate,*,loop=False,expected_active=None):
    """Check normalized mono/stereo audio. Intent mask distinguishes expected sound from idle.

    `review` means a heuristic fired, not that a listener must dislike the sound.
    Rendered clips are not assumed to loop. No repairs are applied to the input.
    """
    started=time.perf_counter()
    raw=np.asarray(samples)
    if raw.dtype.kind not in 'fi' or raw.ndim not in (1,2):raise ValueError('Expected real mono/stereo samples')
    audio=np.asarray(raw,dtype=np.float64)
    if audio.ndim==1:audio=audio[:,None]
    if not len(audio) or audio.shape[1] not in (1,2):raise ValueError('Expected nonempty mono/stereo audio')
    if not isinstance(sample_rate,(int,np.integer)) or sample_rate<1000 or sample_rate>384000:raise ValueError('Invalid sample rate')
    if expected_active is not None:
        expected_active=np.asarray(expected_active)
        if expected_active.shape!=(len(audio),) or expected_active.dtype.kind!='b':raise ValueError('Expected a sample-aligned boolean activity mask')
    findings=[];metrics={}
    def add(code,severity,**details):findings.append({'code':code,'severity':severity,**details})
    def finish():
        decision='reject' if any(f['severity']=='reject' for f in findings) else 'review' if findings else 'pass'
        return {'policy':POLICY,'decision':decision,'loop_checked':bool(loop),'intent_provided':expected_active is not None,'seconds':len(audio)/sample_rate,'channels':audio.shape[1],'thresholds':dict(THRESHOLDS),'metrics':metrics,'findings':findings,'elapsed_ms':(time.perf_counter()-started)*1000}
    nonfinite=int(np.count_nonzero(~np.isfinite(audio)))
    if nonfinite:
        add('nonfinite_samples','reject',count=nonfinite);return finish()
    peak=float(np.max(abs(audio)));metrics['sample_peak']=peak
    metrics['rms']=float(np.sqrt(np.mean(audio*audio)))
    if peak>1.000001:add('sample_overload','reject',peak=peak)
    if peak>0:
        true_peak=float(np.max(abs(resample_poly(audio,4,1,axis=0))))
        metrics['peak_4x_estimate']=true_peak
        if true_peak>1.000001:add('estimated_inter_sample_overload','reject',peak=true_peak)
    if expected_active is not None and np.any(expected_active) and np.max(abs(audio[expected_active]))<1e-7:
        add('missing_expected_audio','reject')
    if loop and peak<1e-7:add('silent_loop','reject')
    if peak<1e-9:return finish()
    if len(audio)<4:return finish()
    difference=np.diff(audio,axis=0)
    curvature=np.max(abs(np.diff(audio,n=2,axis=0)),axis=1)
    curvature_limit=max(THRESHOLDS['impulse_curvature_floor'],THRESHOLDS['impulse_percentile_multiplier']*float(np.percentile(curvature,99)))
    hits=np.flatnonzero(curvature>curvature_limit)+1
    if len(hits):
        events=hits[np.r_[True,np.diff(hits)>round(.002*sample_rate)]]
        add('impulse_transients','review',count=len(events),times_seconds=(events[:12]/sample_rate).tolist(),curvature_limit=curvature_limit)
    flat=(abs(difference)<max(peak*1e-7,1e-10))&(abs(audio[1:])>peak*.8)
    plateau_samples=0;rail_samples=0
    for channel in range(audio.shape[1]):
        starts,ends=_runs(flat[:,channel])
        for start,end in zip(starts,ends):
            if end-start>=3:
                plateau_samples+=int(end-start+1)
                if np.max(abs(audio[start:end+1,channel]))>=.9999:rail_samples+=int(end-start+1)
    metrics['flat_top_fraction']=plateau_samples/audio.size
    if rail_samples:add('full_scale_flat_tops','reject',samples=rail_samples)
    elif plateau_samples/audio.size>.01:add('flat_topped_signal','review',fraction=plateau_samples/audio.size)
    if loop:
        seam=float(np.max(abs(audio[0]-audio[-1])))
        ordinary=float(np.percentile(abs(difference),99.9))
        limit=max(.005,8*ordinary)
        metrics['loop_seam_step']=seam;metrics['loop_seam_limit']=limit
        seam_curvature=float(max(np.max(abs(audio[0]-2*audio[-1]+audio[-2])),np.max(abs(audio[1]-2*audio[0]+audio[-1]))))
        curvature_seam_limit=max(THRESHOLDS['loop_curvature_floor'],8*float(np.percentile(curvature,99.9)))
        metrics['loop_seam_curvature']=seam_curvature
        if seam>limit or seam_curvature>curvature_seam_limit:add('loop_discontinuity','reject',step=seam,limit=limit,curvature=seam_curvature,curvature_limit=curvature_seam_limit)
    quiet=np.max(abs(audio),axis=1)<max(1e-9,peak*1e-7)
    starts,ends=_runs(quiet)
    gaps=[];context=max(1,round(.01*sample_rate))
    for start,end in zip(starts,ends):
        length=end-start
        if start<context or end+context>=len(audio) or not THRESHOLDS['dropout_min_ms']/1000*sample_rate<=length<=THRESHOLDS['dropout_max_ms']/1000*sample_rate:continue
        if expected_active is not None and not np.all(expected_active[start:end]):continue
        before=np.sqrt(np.mean(audio[start-context:start]**2));after=np.sqrt(np.mean(audio[end:end+context]**2))
        if min(before,after)>max(1e-6,metrics['rms']*.05):gaps.append({'start_seconds':start/sample_rate,'duration_ms':length/sample_rate*1000})
    if gaps:add('short_dropout','review',count=len(gaps),intervals=gaps[:12])
    if len(audio)>=THRESHOLDS['modulation_min_seconds']*sample_rate:
        metrics['modulation']=modulation_depth(audio,sample_rate)  # monitor only: listener votes judge wobble taste.
    # Channel power is retained: averaging waveforms would hide anti-phase stereo problems.
    if len(audio)>=512:
        size=min(2048,len(audio))
        frequencies,_,spectrum=stft(audio.astype(np.float32),fs=sample_rate,nperseg=size,noverlap=size//2,axis=0,boundary=None,padded=False)
        power=np.mean(abs(spectrum)**2,axis=1)
        total=power.sum(axis=0);active=total>max(float(total.max())*1e-6,1e-18)
        if np.any(active):
            power=power[:,active];total=total[active]
            def flag_band(start_hz,share_limit,code):
                selected=frequencies>=start_hz
                share=power[selected].sum(axis=0)/total
                fraction=float(np.mean(share>share_limit))
                metrics[code+'_max_share']=float(share.max())
                if fraction>=THRESHOLDS['spectral_active_fraction'] and power.shape[1]*size/(2*sample_rate)>=.25:add(code,'review',active_frame_fraction=fraction,max_energy_share=float(share.max()))
                return selected,share
            flag_band(THRESHOLDS['high_band_start_hz'],THRESHOLDS['high_band_energy_share'],'high_frequency_energy')
            selected,upper_share=flag_band(THRESHOLDS['whistle_start_hz'],THRESHOLDS['broad_upper_energy_share'],'strong_upper_band')
            if np.any(selected):
                local=power[selected]
                peak_bins=np.argmax(local,axis=0);indices=np.arange(local.shape[1])
                padded=np.pad(local,((1,1),(0,0)))
                narrow=sum(padded[peak_bins+1+offset,indices] for offset in (-1,0,1))/total
                fraction=float(np.mean(narrow>THRESHOLDS['whistle_peak_share']))
                if fraction>=THRESHOLDS['spectral_active_fraction'] and local.shape[1]*size/(2*sample_rate)>=.25:add('prominent_upper_tone','review',active_frame_fraction=fraction,max_energy_share=float(narrow.max()))
    return finish()
