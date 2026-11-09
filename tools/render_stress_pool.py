"""Controlled abrasive-sound probes for frozen Audiobox evaluation; never auto-played."""
from pathlib import Path
import hashlib,json
import numpy as np
from scipy.io.wavfile import read,write
from scipy.signal import butter,sosfilt,resample_poly
from tools.prepare_gs_baseline import match_loudness,integrated_loudness

ROOT=Path('artifacts/audiobox_stress_pool_2026-11-06')
RATE=48000


def candidates(base,rate=RATE):
    time=np.arange(len(base))/rate
    # All alterations share the reference's slow driving envelope.
    envelope=np.sqrt(np.mean(base**2,axis=1))
    envelope=sosfilt(butter(2,8,fs=rate,output='sos'),envelope)
    envelope=np.maximum(envelope,0)[:,None]
    def carrier(frequency):
        phase=2*np.pi*np.cumsum(np.broadcast_to(frequency,(len(base),)))/rate
        return np.column_stack([np.sin(phase),np.sin(phase+.12)])
    rng=np.random.default_rng(61106)
    noise=sosfilt(butter(3,[350,6500],btype='bandpass',fs=rate,output='sos'),rng.standard_normal(base.shape),axis=0)
    noise/=np.sqrt(np.mean(noise**2))
    clicks=base.copy()
    for position in np.arange(.45,len(base)/rate,.47):
        start=round(position*rate)
        clicks[start:start+6]+=.22*np.array([1,-.8,.6,-.4,.2,-.1])[:,None]
    dropouts=base.copy()
    for position in np.arange(.6,len(base)/rate,.63):
        start=round(position*rate);dropouts[start:start+round(.035*rate)]=0
    return [
        ('clean','Clean reference','Unmodified excerpt of the controlled Bowed ensemble Rise render.',base),
        ('shrill','Shrill upper tone','Strong 2.8–4.8 kHz whistle over the driving sound.',.65*base+2*envelope*carrier(2800+2000*time/(len(base)/rate))),
        ('ufo','UFO pitch oscillation','Wide six-Hz pitch wobble on a synthetic carrier.',.45*base+2.3*envelope*carrier(430*2**(.9*np.sin(2*np.pi*6*time)))),
        ('flutter','Fast rough flutter','Deep 65-Hz amplitude modulation of the same driving sound.',base*(.1+.9*(.5+.5*np.sin(2*np.pi*65*time)))[:,None]),
        ('noise','Noise contamination','Prominent seeded 350–6500 Hz noise, following the driving envelope.',.45*base+1.4*envelope*noise),
        ('clicks','Intermittent clicks','Repeated six-sample transients added to the reference.',clicks),
        ('distortion','Crunchy distortion','Intentional hard saturation before final level matching; output WAV does not clip.',np.clip(base*8,-.065,.065)),
        ('dropouts','Signal dropouts','Abrupt 35-ms holes in the reference.',dropouts),
        ('high_whistle','Very high whistle · 10 kHz','Tests a limitation of the model’s 16-kHz input; audibility depends on listener and playback.',base+1.8*envelope*carrier(10000)),
    ]


def main():
    ROOT.mkdir(parents=True,exist_ok=True)
    rate,base=read('artifacts/audiobox_family_eval_2026-11-06/bowed_rise.wav')
    assert rate==RATE and base.shape[1]==2
    base=base[2*RATE:12*RATE].astype(float)
    rendered=[]
    for key,label,description,audio in candidates(base):
        fade=round(.04*RATE)
        audio=audio.copy()
        audio[:fade]*=np.linspace(0,1,fade)[:,None];audio[-fade:]*=np.linspace(1,0,fade)[:,None]
        assert np.isfinite(audio).all()
        audio=match_loudness(audio,-28)
        rendered.append((key,label,description,audio))
    peak=max(float(np.max(abs(resample_poly(audio,4,1,axis=0)))) for *_,audio in rendered)
    target=-28-max(0,20*np.log10(peak/.35))
    clips=[]
    for key,label,description,audio in rendered:
        audio=match_loudness(audio,target)
        peak=float(np.max(abs(resample_poly(audio,4,1,axis=0))))
        assert peak<.351 and abs(integrated_loudness(audio)-target)<.05
        path=ROOT/f'{key}.wav';write(path,RATE,audio.astype(np.float32))
        clips.append({'id':key,'label':label,'description':description,'path':str(path),'seconds':len(audio)/RATE,'lufs':integrated_loudness(audio),'peak_4x':peak,'sha256':hashlib.sha256(path.read_bytes()).hexdigest()})
    manifest={'version':1,'rate':RATE,'target_lufs':target,'seed':61106,'method':'Nine controlled ten-second probes; original reference is an offline Rise approximation, not a dashboard recording. Equal integrated loudness with shared headroom; no physical SPL guarantee. No automatic playback. Intentional defect labels are hypotheses, not human-validated badness.','clips':clips}
    (ROOT/'clips.json').write_text(json.dumps(manifest,indent=2))
    print(f'{len(clips)} probes prepared, common target {target:.2f} LUFS; true-peak estimate <= .35')


if __name__=='__main__':main()
