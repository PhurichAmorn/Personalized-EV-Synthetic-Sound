"""Deterministic low bowed-string-inspired harmonic voice; no instrument samples."""
import numpy as np


def bowed_tone(phase, frequency):
    result=np.zeros_like(phase,dtype=float)
    for harmonic in range(1,25):
        hz=np.asarray(frequency)*harmonic
        resonance=.75+.4*np.exp(-.5*((hz-350)/200)**2)+.18*np.exp(-.5*((hz-700)/280)**2)
        amplitude=np.exp(-.22*(harmonic-1))/harmonic**1.4
        result+=amplitude*resonance/(1+(hz/1500)**4)*np.sin(harmonic*phase)
    return result


def organic_motion(time,frequency,seed):
    """Small irregular bow motion with a repeatable five-second boundary."""
    rng=np.random.default_rng(seed)
    rates=np.array([.2,.4,.6,1.,1.4])
    weights=rng.uniform(.3,1,len(rates))
    phases=rng.uniform(-np.pi,np.pi,len(rates))
    drift=np.zeros_like(time,dtype=float)
    pressure=np.ones_like(time,dtype=float)
    for rate,weight,phase in zip(rates,weights,phases):
        drift+=weight/rate*np.sin(2*np.pi*rate*time+phase)
        pressure+=.018*weight/weights.sum()*np.sin(2*np.pi*rate*time+phase+1.3)
    offset=np.asarray(frequency)*(2**(2.5/1200)-1)*drift/weights.sum()
    offset+=.04*(.85+.15*np.sin(2*np.pi*.4*time+phases[0]))*np.sin(2*np.pi*5.2*time+.35*np.sin(2*np.pi*.6*time+phases[1]))
    return offset,pressure


def source_dimension(signal,rate):
    """Bake dark early reflections into a periodic stereo source, without a hall tail."""
    frequency=np.fft.rfftfreq(len(signal),1/rate)
    spectrum=np.fft.rfft(signal)/(1+(frequency/1600)**4)
    channels=[]
    for taps in (((.026,.15),(.072,.08),(.121,.035)),((.039,.15),(.094,.08),(.147,.035))):
        reflection=sum(gain*np.exp(-2j*np.pi*frequency*delay) for delay,gain in taps)
        channels.append(.88*signal+np.fft.irfft(spectrum*reflection,n=len(signal)))
    return np.column_stack(channels)
