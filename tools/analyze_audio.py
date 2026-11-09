"""Summarize audio character over time with the project's existing SciPy stack.

Run: .venv/bin/python tools/analyze_audio.py ../ev-sound-example

Package downloads are unavailable in the current environment, so this tool
uses SciPy for the first baseline. Values describe the mixed recording, not
isolated vehicle synthesis parameters.
"""

from __future__ import annotations

import argparse
import csv
import os
import re
from pathlib import Path

os.environ.setdefault("QT_LOGGING_RULES", "qt.multimedia.ffmpeg.*=false")

import numpy as np
from PySide6.QtCore import QCoreApplication, QEventLoop, QTimer, QUrl
from PySide6.QtMultimedia import QAudioDecoder, QAudioFormat
from scipy.signal import stft

SAMPLE_TYPES = {
    QAudioFormat.SampleFormat.Float: (np.float32, "float"),
    QAudioFormat.SampleFormat.Int16: (np.int16, "int16"),
    QAudioFormat.SampleFormat.Int32: (np.int32, "int32"),
    QAudioFormat.SampleFormat.UInt8: (np.uint8, "uint8"),
}


def decode_audio(path: Path) -> tuple[int, np.ndarray]:
    """Decode supported files through Qt Multimedia's installed FFmpeg backend."""
    decoder = QAudioDecoder()
    loop = QEventLoop()
    blocks: list[np.ndarray] = []
    sample_rate: int | None = None
    channels: int | None = None

    def read_blocks() -> None:
        nonlocal sample_rate, channels
        while decoder.bufferAvailable():
            buffer = decoder.read()
            fmt = buffer.format()
            sample_type = SAMPLE_TYPES.get(fmt.sampleFormat())
            if sample_type is None:
                raise RuntimeError(f"Unsupported decoded sample format: {fmt.sampleFormat()}")
            dtype, kind = sample_type
            if sample_rate is None:
                sample_rate, channels = fmt.sampleRate(), fmt.channelCount()
            elif (sample_rate, channels) != (fmt.sampleRate(), fmt.channelCount()):
                raise RuntimeError("Audio format changed during decoding")
            block = np.frombuffer(buffer.data(), dtype=dtype).copy().reshape(-1, channels)
            if kind == "int16":
                block = block.astype(np.float32) / 32768.0
            elif kind == "int32":
                block = block.astype(np.float32) / 2147483648.0
            elif kind == "uint8":
                block = (block.astype(np.float32) - 128.0) / 128.0
            else:
                block = block.astype(np.float32)
            blocks.append(block)

    decoder.bufferReady.connect(read_blocks)
    decoder.finished.connect(loop.quit)
    decoder.setSource(QUrl.fromLocalFile(str(path.resolve())))
    decoder.start()
    QTimer.singleShot(120_000, loop.quit)
    loop.exec()

    if decoder.isDecoding():
        raise TimeoutError(f"Timed out while decoding {path.name}")
    if not blocks or decoder.error() != QAudioDecoder.Error.NoError:
        raise RuntimeError(decoder.errorString() or "Audio decoding timed out or returned no samples")
    return int(sample_rate), np.concatenate(blocks, axis=0)


def analyze(samples: np.ndarray, sample_rate: int) -> tuple[list[dict[str, float]], dict[str, object]]:
    """Compute frame-level spectral descriptors while preserving stereo power."""
    n_fft = 8192
    hop = 2048
    if len(samples) < n_fft:
        n_fft = max(256, 2 ** int(np.floor(np.log2(len(samples)))))
        hop = max(1, n_fft // 4)

    channel_spectra = [
        stft(samples[:, channel], fs=sample_rate, nperseg=n_fft,
             noverlap=n_fft - hop, boundary=None, padded=False)[2]
        for channel in range(samples.shape[1])
    ]
    power = np.mean(np.abs(np.stack(channel_spectra)) ** 2, axis=0)
    frequencies, times = stft(
        samples[:, 0], fs=sample_rate, nperseg=n_fft,
        noverlap=n_fft - hop, boundary=None, padded=False
    )[:2]
    magnitude = np.sqrt(power)
    total = power.sum(axis=0) + 1e-20
    centroid = (frequencies[:, None] * power).sum(axis=0) / total
    cumulative = np.cumsum(power, axis=0)
    rolloff = frequencies[np.argmax(cumulative >= 0.85 * total, axis=0)]
    flatness = np.exp(np.log(magnitude + 1e-12).mean(axis=0)) / (magnitude.mean(axis=0) + 1e-12)

    peak_band = (frequencies >= 40) & (frequencies <= min(1500, sample_rate / 2))
    candidate_peak = frequencies[peak_band][np.argmax(magnitude[peak_band], axis=0)]
    band_specs = [(20, 200), (200, 1000), (1000, 4000), (4000, sample_rate / 2 + 1)]
    band_ratios = []
    for low, high in band_specs:
        band = (frequencies >= low) & (frequencies < high)
        band_ratios.append(power[band].sum(axis=0) / total if band.any() else np.zeros_like(times))

    normalized = magnitude / (magnitude.sum(axis=0, keepdims=True) + 1e-20)
    flux = np.zeros(len(times))
    if len(times) > 1:
        positive_change = np.maximum(np.diff(normalized, axis=1), 0)
        flux[1:] = np.sqrt(np.sum(positive_change ** 2, axis=0))

    # Windowed RMS uses each channel's energy, so opposing stereo phase cannot cancel.
    sample_energy = np.sum(samples.astype(np.float64) ** 2, axis=1)
    cumulative_energy = np.concatenate(([0.0], np.cumsum(sample_energy)))
    starts = np.arange(len(times)) * hop
    rms = np.sqrt((cumulative_energy[starts + n_fft] - cumulative_energy[starts]) /
                  (n_fft * samples.shape[1]) + 1e-20)
    frame_count = min(len(times), len(rms))
    times, centroid, rolloff, flatness, candidate_peak, flux = (
        array[:frame_count] for array in (times, centroid, rolloff, flatness, candidate_peak, flux)
    )
    band_ratios = [array[:frame_count] for array in band_ratios]
    rms = rms[:frame_count]

    feature_rows = []
    for i, time_s in enumerate(times):
        feature_rows.append({
            "time_s": float(time_s),
            "rms_dbfs": float(20 * np.log10(rms[i] + 1e-12)),
            "spectral_centroid_hz": float(centroid[i]),
            "spectral_rolloff85_hz": float(rolloff[i]),
            "spectral_flatness": float(flatness[i]),
            "candidate_peak_40_1500_hz": float(candidate_peak[i]),
            "spectral_flux": float(flux[i]),
            "band_20_200_pct": float(100 * band_ratios[0][i]),
            "band_200_1000_pct": float(100 * band_ratios[1][i]),
            "band_1000_4000_pct": float(100 * band_ratios[2][i]),
            "band_4000_plus_pct": float(100 * band_ratios[3][i]),
        })

    def thirds(values: np.ndarray) -> list[float]:
        return [float(np.median(part)) for part in np.array_split(values, 3)]

    summary = {
        "duration_s": len(samples) / sample_rate,
        "sample_rate_hz": sample_rate,
        "channels": samples.shape[1],
        "rms_dbfs": float(20 * np.log10(np.sqrt(np.mean(samples.astype(np.float64) ** 2)) + 1e-12)),
        "peak_dbfs": float(20 * np.log10(np.max(np.abs(samples)) + 1e-12)),
        "centroid_median_hz": float(np.median(centroid)),
        "centroid_p90_hz": float(np.percentile(centroid, 90)),
        "centroid_early_mid_late_hz": " / ".join(f"{v:.0f}" for v in thirds(centroid)),
        "rolloff85_median_hz": float(np.median(rolloff)),
        "flatness_median": float(np.median(flatness)),
        "candidate_peak_median_hz": float(np.median(candidate_peak)),
        "flux_p90": float(np.percentile(flux, 90)),
        "band_20_200_early_mid_late_pct": " / ".join(f"{v:.0f}" for v in thirds(band_ratios[0] * 100)),
        "band_200_1000_early_mid_late_pct": " / ".join(f"{v:.0f}" for v in thirds(band_ratios[1] * 100)),
        "band_1000_4000_early_mid_late_pct": " / ".join(f"{v:.0f}" for v in thirds(band_ratios[2] * 100)),
        "band_4000_plus_early_mid_late_pct": " / ".join(f"{v:.0f}" for v in thirds(band_ratios[3] * 100)),
    }
    return feature_rows, summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path, help="Audio file or folder containing MP3/WAV files")
    parser.add_argument("--output", type=Path, default=Path("artifacts/audio-analysis"))
    args = parser.parse_args()
    if not args.input.exists():
        parser.error(f"Input does not exist: {args.input}")

    if QCoreApplication.instance() is None:
        app = QCoreApplication([])
    else:
        app = QCoreApplication.instance()

    files = [args.input] if args.input.is_file() else sorted(
        path for path in args.input.rglob("*") if path.suffix.lower() in {".mp3", ".wav"}
    )
    if not files:
        parser.error(f"No MP3/WAV files found: {args.input}")
    args.output.mkdir(parents=True, exist_ok=True)
    summaries = []
    for path in files:
        try:
            sample_rate, samples = decode_audio(path)
            frames, summary = analyze(samples, sample_rate)
            stem = re.sub(r"[^A-Za-z0-9._-]+", "_", path.stem).strip("._") or "clip"
            frame_path = args.output / f"{stem}.csv"
            with frame_path.open("w", newline="") as stream:
                writer = csv.DictWriter(stream, fieldnames=frames[0].keys())
                writer.writeheader()
                writer.writerows(frames)
            summaries.append({"file": path.name, **summary, "error": ""})
            print(f"Analyzed {path.name}: {summary['duration_s']:.1f}s")
        except Exception as exc:
            summaries.append({"file": path.name, "error": str(exc)})
            print(f"Skipped {path.name}: {exc}")

    fields = list(dict.fromkeys(key for row in summaries for key in row))
    with (args.output / "summary.csv").open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(summaries)
    print(f"Wrote {len(summaries)} clip summaries to {args.output}")
    return int(not summaries or all(row.get("error") for row in summaries))


if __name__ == "__main__":
    raise SystemExit(main())
