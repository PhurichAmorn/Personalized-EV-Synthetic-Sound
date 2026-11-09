"""Prepare level-matched source/Rise clips for the standalone model evaluation."""
from pathlib import Path
import json,hashlib,sys
import numpy as np
from scipy.io.wavfile import read,write
from scipy.signal import lfilter,fftconvolve,resample_poly
from tools.prepare_gs_baseline import integrated_loudness,match_loudness
from audio.signal_checks import check_signal

PROJECT=Path(__file__).resolve().parents[1]
ROOT=Path('artifacts/audiobox_family_eval_2026-11-06')
RATE=48000


def load(name,root=None):
    return np.fromfile(Path(root or ROOT)/name,dtype='<f4').reshape(-1,2).astype(float)


def finalize(root=None):
    """Thread-safe for distinct roots; source discovery calls it in-process (no stdout: that is the sidecar channel)."""
    root=Path(root or ROOT)
    manifest=json.loads((root/'render_manifest.json').read_text())
    ir_rate,ir=read(PROJECT/'desktop/public/audio/original_steady_room_ir.wav')
    assert ir_rate==RATE and ir.shape[1]==2
    # WebAudio's default convolver normalization, stereo impulse, 48 kHz context.
    power=np.sqrt(np.mean(ir.astype(float)**2))
    impulse=ir.astype(float)*(.00125*44100/RATE/max(power,.000125))
    clips=[]
    for family in manifest['families']:
        name=family['id']
        direct,filtered,controls=(load(f'{name}_{suffix}.f32',root) for suffix in ['direct','filtered','automation'])
        state=np.zeros((2,2));cutoff=1300.
        for start in range(0,len(filtered),480):
            end=min(start+480,len(filtered))
            cutoff+=(controls[start,1]-cutoff)*(1-np.exp(-(end-start)/(.15*RATE)))
            w=2*np.pi*cutoff/RATE;c=np.cos(w);alpha=np.sin(w)/(2*.5)
            b=np.array([(1-c)/2,1-c,(1-c)/2])/(1+alpha)
            a=np.array([1,-2*c/(1+alpha),(1-alpha)/(1+alpha)])
            filtered[start:end],state=lfilter(b,a,filtered[start:end],axis=0,zi=state)
        bus=direct+filtered
        time=np.arange(len(bus))/RATE
        chorus=np.empty_like(bus)
        for channel,(delay,frequency) in enumerate([(.018,.28),(.023,.33)]):
            position=np.arange(len(bus))-(delay+.0012*np.sin(2*np.pi*frequency*time))*RATE
            delayed=np.interp(position,np.arange(len(bus)),bus[:,channel],left=0,right=0)
            chorus[:,channel]=.75*bus[:,channel]+.25*delayed
        driven=chorus*controls[:,0,None]
        wet=np.column_stack([fftconvolve(driven[:,c],impulse[:,c]) for c in range(2)])
        drive=.68*np.pad(driven,((0,len(impulse)-1),(0,0)))+.32*wet
        # Same output startup ramp and listening gain, before comparison normalization.
        drive[:len(driven)]*=np.minimum(1,np.maximum(0,(time+.02)/.3))[:,None]*.7
        drive[len(driven):]*=.7
        source=load(f'{name}_source.f32',root)
        for scene,audio in [('source',source),(manifest.get('mode','rise'),drive)]:
            pre_normalization_check=check_signal(audio,RATE)
            audio=audio.copy()
            fade=round(.03*RATE)
            audio[:fade]*=np.linspace(0,1,fade)[:,None]
            audio[-fade:]*=np.linspace(1,0,fade)[:,None]
            audio=match_loudness(audio,-24)
            peak=float(np.max(abs(resample_poly(audio,4,1,axis=0))))
            assert np.isfinite(audio).all() and peak<.9
            path=root/f'{name}_{scene}.wav'
            write(path,RATE,audio.astype(np.float32))
            clips.append({'family':name,'label':family['label'],'scene':scene,'path':str(path),'seconds':len(audio)/RATE,'lufs':integrated_loudness(audio),'peak_4x':peak,'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'signal_check':check_signal(audio,RATE),'pre_normalization_check':pre_normalization_check,'source_loop_check':check_signal(load(f'{name}_source.f32',root),RATE,loop=True) if scene=='source' else None})
    manifest['clips']=clips
    manifest['normalization']='Each clip matched to -24 LUFS using project BS.1770 implementation, not certified metering; no physical SPL claim.'
    (root/'clips.json').write_text(json.dumps(manifest,indent=2))
    assert len(clips)==2*len(manifest['families'])
    return clips


if __name__=='__main__':
    clips=finalize(sys.argv[1] if len(sys.argv)>1 else None)
    print(f'Prepared {len(clips)} stereo clips at -24 LUFS; max 4x peak',max(c['peak_4x'] for c in clips))
