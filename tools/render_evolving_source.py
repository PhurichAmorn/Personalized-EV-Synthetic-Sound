"""Original five-second source: overlapping low-to-high phrases, not a pitch-cycle effect."""
from pathlib import Path
import numpy as np
if __package__:
    from .source_voice import bowed_tone, organic_motion, source_dimension
else:
    from source_voice import bowed_tone, organic_motion, source_dimension
from scipy.io.wavfile import read, write

RATE=48000
SECONDS=5


def phrase_envelope(local):
    def handoff(value):
        x=np.clip(value,0,1)**.75
        return x*x*x*(10+x*(-15+6*x))
    # Keep both voices present during the two-second equal-power overlap.
    return np.sin(np.pi/2*handoff(local/2.0))*np.cos(np.pi/2*handoff((local-2.5)/2.0))


def phrase_frequency(local):
    position=np.clip(local/4.5,0,1)
    return 160*2**((9/12)*position*position*(3-2*position))


def render():
    output=Path('desktop/public/audio')
    frames=RATE*SECONDS
    duration=4.5
    local=np.arange(round(duration*RATE))/RATE
    frequency=phrase_frequency(local)
    phase=2*np.pi*np.cumsum(frequency)/RATE
    envelope=phrase_envelope(local)
    motion,pressure=organic_motion(local,frequency,117)
    bowed_phase=phase+motion
    phrase_body=bowed_tone(bowed_phase,frequency)*envelope*pressure
    phrase_pad=np.zeros_like(local)
    for voice,(multiple,weight) in enumerate(((.75,.55),(1.5,.35),(2.,.10))):
        motion,bow_pressure=organic_motion(local,frequency*multiple,211+voice)
        phrase_pad+=weight*bowed_tone(phase*multiple+.4*voice+motion,frequency*multiple)*bow_pressure*envelope
    phrase_glass=(.7*np.sin(2*phase)+.2*np.sin(3*phase)+.1*np.sin(4*phase))*envelope
    def wrap_phrases(phrase):
        result=np.zeros(frames)
        for start in (0,round(2.5*RATE)):
            np.add.at(result,(np.arange(len(phrase))+start)%frames,phrase)
        return result
    layers={'body':wrap_phrases(phrase_body), 'pad':wrap_phrases(phrase_pad), 'glass':wrap_phrases(phrase_glass)}
    rms=lambda x:float(np.sqrt(np.mean(x*x)))
    for name,weight in [('body',.095),('pad',.065),('glass',.004)]: layers[name]*=weight/rms(layers[name])
    source_rate,air=read(output/'original_steady_air.wav')
    assert source_rate==RATE and len(air)==frames
    layers={name:source_dimension(signal,RATE) for name,signal in layers.items()}
    layers['air']=air.astype(float)
    scale=.13/rms(sum(layers.values()))
    for name,signal in layers.items():
        signal*=scale
        assert np.isfinite(signal).all() and np.max(abs(signal))<.85
        assert np.max(abs(signal[0]-signal[-1]))<=np.max(abs(np.diff(signal,axis=0)))*1.05
        write(output/f'original_evolving_{name}.wav',RATE,signal.astype(np.float32))
    mixed=sum(layers.values())
    assert np.max(abs(mixed))<.85
    write(output/'original_evolving_source.wav',RATE,mixed.astype(np.float32))
    print(f'Evolving source: 5 seconds, two phrase entrances, 160–{frequency.max():.1f} Hz, peak {np.max(abs(mixed)):.3f}, RMS {rms(mixed):.3f}')


if __name__=='__main__': render()
