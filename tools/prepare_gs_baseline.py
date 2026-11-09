"""Prepare and finalize controlled baseline auditions; does not replace driving assets."""
from pathlib import Path
import hashlib
import json
import sys
import numpy as np
from scipy.io.wavfile import read,write
from scipy.signal import lfilter,resample_poly,fftconvolve
from scipy.ndimage import map_coordinates

RATE=48000
ROOT=Path('artifacts/gs_baseline_research')
PUBLIC=Path('desktop/public/audio/baseline-v1')


def audio_file(path):
    rate,data=read(path)
    audio=data.astype(float)
    if np.issubdtype(data.dtype,np.integer):audio/=max(abs(np.iinfo(data.dtype).min),np.iinfo(data.dtype).max)
    if rate!=RATE:
        from math import gcd
        factor=gcd(rate,RATE)
        audio=resample_poly(audio,RATE//factor,rate//factor,axis=0)
    if not np.isfinite(audio).all():raise ValueError('Invalid audio')
    return audio


def integrated_loudness(audio):
    """BS.1770 mono/stereo gated energy at 48 kHz; not a certified meter."""
    audio=np.asarray(audio,dtype=float)
    if audio.ndim==1:audio=audio[:,None]
    if audio.shape[1] not in (1,2):raise ValueError('Expected mono or stereo')
    filtered=lfilter([1.53512485958697,-2.69169618940638,1.19839281085285],[1,-1.69065929318241,.73248077421585],audio,axis=0)
    filtered=lfilter([1,-2,1],[1,-1.99004745483398,.99007225036621],filtered,axis=0)
    block=round(.4*RATE);hop=round(.1*RATE)
    energies=np.array([np.mean(filtered[i:i+block]**2,axis=0).sum() for i in range(0,len(audio)-block+1,hop)])
    if not len(energies):return float('-inf')
    levels=-.691+10*np.log10(np.maximum(energies,1e-30))
    absolute=energies[levels>-70]
    if not len(absolute):return float('-inf')
    threshold=-.691+10*np.log10(absolute.mean())-10
    gated=energies[(levels>-70)&(levels>threshold)]
    return float(-.691+10*np.log10(gated.mean()))


def match_loudness(audio,target):
    loudness=integrated_loudness(audio)
    if not np.isfinite(loudness):raise ValueError('Cannot normalize silent audio')
    return audio*10**((target-loudness)/20)


def periodic_loop(signal,rate=RATE):
    frames=5*rate;overlap=round(.5*rate)
    if len(signal)<frames+overlap:raise ValueError('Need 5.5 seconds of source')
    x=np.linspace(0,1,overlap,endpoint=False)
    x=x*x*x*(10+x*(-15+6*x))
    if signal.ndim==2:x=x[:,None]
    join=signal[frames:frames+overlap]*np.cos(np.pi*x/2)+signal[:overlap]*np.sin(np.pi*x/2)
    return np.concatenate([join,signal[overlap:frames]])


def hall_reflections(hall):
    hall=np.asarray(hall,dtype=float).copy()
    direct=int(np.argmax(np.sum(hall[:round(.1*RATE)]**2,axis=1)))
    start=direct+round(.03*RATE)
    progress=np.clip((np.arange(len(hall))-start)/(.04*RATE),0,1)
    gate=progress*progress*(3-2*progress)
    hall*=gate[:,None]
    if np.sum(hall**2)<1e-15:raise ValueError('Hall has no usable reflection field')
    return hall


def prepare():
    ROOT.mkdir(parents=True,exist_ok=True);PUBLIC.mkdir(parents=True,exist_ok=True)
    recorded=audio_file(ROOT/'vsco_cello_C3_v1.wav')
    positions=1.5*RATE+np.arange(round(5.5*RATE))*2**(-7/12)
    cello=periodic_loop(np.column_stack([map_coordinates(recorded[:,channel],[positions],order=3,mode='nearest') for channel in range(2)]))
    procedural=audio_file('desktop/public/audio/original_steady_source.wav')
    for name,audio in [('procedural',procedural),('recorded',cello)]:
        audio=match_loudness(audio,-24)
        if len(audio)!=5*RATE or np.max(abs(audio))>.8:raise ValueError('Invalid prepared loop')
        write(ROOT/f'{name}_loop.wav',RATE,audio.astype(np.float32))
        audio.astype('<f4').tofile(ROOT/f'{name}_loop.f32')
    channels=[audio_file(ROOT/f'hall/great_hall_{c}.wav') for c in 'WXY']
    if len({len(x) for x in channels})!=1:raise ValueError('Unmatched hall channels')
    w,x,y=channels
    # Virtual horizontal cardioids at +/-45 degrees, assuming legacy FuMa WXYZ.
    hall=np.column_stack([np.sqrt(.5)*w+.5/np.sqrt(2)*(x+y),np.sqrt(.5)*w+.5/np.sqrt(2)*(x-y)])
    hall=hall_reflections(hall)
    hall[-round(.02*RATE):]*=np.linspace(1,0,round(.02*RATE))[:,None]
    hall/=np.sqrt(np.mean(np.sum(hall**2,axis=0)))
    write(ROOT/'hall_stereo.wav',RATE,hall.astype(np.float32))
    metadata={'rate':RATE,'loop_seconds':5,'neutral_seconds':10,'drive_seconds':22,'recorded_transposition_semitones':-7,'source_channels':2,'recorded_channel_selection':'original stereo','hall':'C4DM Great Hall x06y06, virtual +/-45 degree cardioid stereo reflection field; direct arrival suppressed; not binaural','hall_license':'CC BY-NC-SA 4.0','hall_seconds':len(hall)/RATE}
    (ROOT/'prepared.json').write_text(json.dumps(metadata,indent=2))
    print(json.dumps(metadata,indent=2))


def finalize():
    hall=audio_file(ROOT/'hall_stereo.wav')
    renderer=json.loads((ROOT/'renders.json').read_text())
    records=[]
    for item in renderer['clips']:
        dry=np.fromfile(ROOT/item['file'],dtype='<f4').astype(float).reshape(-1,2)
        padded=np.pad(dry,((0,len(hall)-1),(0,0)))
        wet=np.column_stack([fftconvolve(dry[:,channel],hall[:,channel]) for channel in range(2)])
        wet*=np.sqrt(np.mean(padded**2))/max(np.sqrt(np.mean(wet**2)),1e-12)
        for space in ['dry','hall']:
            audio=padded.copy() if space=='dry' else .6*padded+.4*wet
            audio[-round(.1*RATE):]*=np.linspace(1,0,round(.1*RATE))[:,None]
            audio=match_loudness(audio,-24)
            records.append((dict(item,space=space),audio))
    # Preserve equal loudness across the whole set if any version needs extra headroom.
    worst=max(float(np.max(abs(resample_poly(audio,4,1,axis=0)))) for _,audio in records)
    target=-24-max(0,20*np.log10(worst/.7))
    manifest={'version':1,'target_lufs':target,'method':'BS.1770 gated mono/stereo implementation; 4x polyphase peak estimate, not certified metering','room':json.loads((ROOT/'prepared.json').read_text())['hall'],'trace':renderer['trace'],'clips':[]}
    for item,audio in records:
        audio=match_loudness(audio,target)
        peak=float(np.max(abs(resample_poly(audio,4,1,axis=0))))
        if peak>.701 or abs(integrated_loudness(audio)-target)>.05:raise ValueError('Comparison level/headroom check failed')
        pcm=np.round(np.clip(audio,-1,1)*32767).astype(np.int16)
        digest=hashlib.sha256(pcm.tobytes()).hexdigest()
        key=f"{item['source']}_{item['renderer']}_{item['scene']}_{item['space']}"
        filename=f'{key}-{digest[:10]}.wav'
        write(PUBLIC/filename,RATE,pcm)
        bins=np.array_split(np.max(abs(audio),axis=1),320)
        manifest['clips'].append({'id':key,'url':f'/audio/baseline-v1/{filename}','seconds':len(audio)/RATE,'lufs':integrated_loudness(pcm.astype(float)/32768),'peak_4x':peak,'sha256_pcm':digest,'waveform':[float(np.max(x)) for x in bins]})
    manifest['recording_provenance']=json.loads((ROOT/'source_candidate.json').read_text())
    manifest['hall_provenance']=json.loads((ROOT/'hall/provenance.json').read_text())
    manifest['source_hashes']={name:hashlib.sha256((ROOT/f'{name}_loop.wav').read_bytes()).hexdigest() for name in ['procedural','recorded']}
    manifest['renderer_sha256']=hashlib.sha256(Path('desktop/public/audio/granular-processor.mjs').read_bytes()).hexdigest()
    manifest['mapping_sha256']=hashlib.sha256(Path('desktop/src/drivingSoundMapping.ts').read_bytes()).hexdigest()
    (PUBLIC/'manifest.json').write_text(json.dumps(manifest,indent=2))
    (PUBLIC/'ATTRIBUTION.txt').write_text('''Baseline comparison research audio\nRecorded cello: VSCO 2 Community Edition, Sam Gossner/Versilian Studios, CC0 1.0.\nOriginal file: Strings/Cello Section/susvib/susvib_C3_v1_1.wav\nhttps://github.com/sgossner/VSCO-2-CE\nChanges: original stereo retained, -7 semitone transposition, five-second loop, processing and level matching.\n\nHall versions contain modified measured responses: Centre for Digital Music, Queen Mary University of London, Great Hall x06y06.\nhttps://isophonics.net/content/room-impulse-response-data-set\nStewart, Rebecca and Sandler, Mark. Database of Omnidirectional and B-Format Impulse Responses. ICASSP 2010.\nLicense: Creative Commons Attribution-NonCommercial-ShareAlike 4.0 International.\nhttps://creativecommons.org/licenses/by-nc-sa/4.0/\nChanges: 96 to 48 kHz, stereo projection assuming FuMa, direct-arrival suppression, 20 ms end taper, 60/40 dry/reflection mix and level matching.\nHall-derived versions are distributed under CC BY-NC-SA 4.0. This does not relicense application code.\nNo physical playback SPL or listening comfort has been certified.\n''')
    print(f'{len(records)} clips prepared at {target:.2f} LUFS; maximum 4x peak {max(x["peak_4x"] for x in manifest["clips"]):.3f}')


if __name__=='__main__':
    if len(sys.argv)>1 and sys.argv[1]=='finalize':finalize()
    else:prepare()
