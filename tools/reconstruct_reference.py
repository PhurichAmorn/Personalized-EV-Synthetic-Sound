"""Analyze a recording into a complete complex spectrum, then resynthesize it.

The model retains every STFT bin and phase. It reproduces the recording rather
than estimating the manufacturer's source separation or synthesis patch.
"""
import argparse
from pathlib import Path

import numpy as np
from scipy.io.wavfile import write
from scipy.signal import stft, istft

FFT = 2048
HOP = 512


def analyze(source, model):
    from PySide6.QtCore import QCoreApplication
    from analyze_audio import decode_audio
    app = QCoreApplication.instance() or QCoreApplication([])
    rate, samples = decode_audio(Path(source))
    if samples.ndim != 2 or not np.isfinite(samples).all():
        raise ValueError('Invalid decoded audio')
    spectra = np.stack([
        stft(samples[:, channel].astype(np.float64), fs=rate, window='hann', nperseg=FFT,
             noverlap=FFT-HOP, boundary='zeros', padded=True)[2]
        for channel in range(samples.shape[1])
    ])
    Path(model).parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(model, spectrum=spectra, rate=rate, frames=len(samples), fft=FFT, hop=HOP)
    return rate, samples


def render(model, output):
    with np.load(model, allow_pickle=False) as data:
        spectrum = data['spectrum']
        rate, frames, fft, hop = (int(data[key]) for key in ('rate', 'frames', 'fft', 'hop'))
        if spectrum.ndim != 3 or not 0 < hop <= fft or frames <= 0 or rate <= 0:
            raise ValueError('Invalid spectral model')
        result = np.column_stack([
            istft(channel, fs=rate, window='hann', nperseg=fft,
                  noverlap=fft-hop, input_onesided=True, boundary=True)[1][:frames]
            for channel in spectrum
        ])
    if result.shape[0] != frames or not np.isfinite(result).all():
        raise ValueError('Invalid reconstruction')
    Path(output).parent.mkdir(parents=True, exist_ok=True)
    write(output, rate, result.astype(np.float32))
    return rate, result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    a = sub.add_parser('analyze')
    a.add_argument('source'); a.add_argument('model'); a.add_argument('reference_wav')
    r = sub.add_parser('render')
    r.add_argument('model'); r.add_argument('output')
    args = parser.parse_args()
    if args.command == 'analyze':
        rate, samples = analyze(args.source, args.model)
        Path(args.reference_wav).parent.mkdir(parents=True, exist_ok=True)
        write(args.reference_wav, rate, samples.astype(np.float32))
        print(f'Analyzed {len(samples)/rate:.3f} s, {rate} Hz, {samples.shape[1]} channels; every spectral bin retained.')
    else:
        rate, samples = render(args.model, args.output)
        print(f'Reconstructed {len(samples)/rate:.3f} s from spectral model without reading the source recording.')
