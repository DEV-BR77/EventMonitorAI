from __future__ import annotations

import numpy as np


def calculate_spectrogram(
    audio: np.ndarray,
    sample_rate: int,
    window_size: int = 1024,
    hop_size: int = 256,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Return frame times, frequencies and a normalized dB spectrogram."""
    samples = np.asarray(audio, dtype=np.float32)
    if samples.ndim == 2:
        samples = samples.mean(axis=1)
    if samples.size == 0:
        return np.array([]), np.array([]), np.empty((0, 0))
    if samples.size < window_size:
        samples = np.pad(samples, (0, window_size - samples.size))

    frame_count = 1 + (samples.size - window_size) // hop_size
    frames = np.lib.stride_tricks.sliding_window_view(samples, window_size)[::hop_size]
    frames = frames[:frame_count] * np.hanning(window_size)
    magnitude = np.abs(np.fft.rfft(frames, axis=1))
    power_db = 20 * np.log10(np.maximum(magnitude, 1e-10))
    power_db -= power_db.max()
    power_db = np.maximum(power_db, -100.0)
    times = (np.arange(frame_count) * hop_size + window_size / 2) / sample_rate
    frequencies = np.fft.rfftfreq(window_size, 1 / sample_rate)
    return times, frequencies, power_db


def spectrogram_records(
    times: np.ndarray,
    frequencies: np.ndarray,
    power_db: np.ndarray,
    start_seconds: float = 0.0,
    max_time_bins: int = 220,
    max_frequency_bins: int = 96,
) -> list[dict[str, float]]:
    """Downsample a spectrogram into browser-friendly Vega-Lite records."""
    if not times.size or not frequencies.size or not power_db.size:
        return []
    time_step = max(1, int(np.ceil(times.size / max_time_bins)))
    frequency_step = max(1, int(np.ceil(frequencies.size / max_frequency_bins)))
    selected_times = times[::time_step] + start_seconds
    selected_frequencies = frequencies[::frequency_step]
    selected_power = power_db[::time_step, ::frequency_step]
    return [
        {
            "time": round(float(time_value), 4),
            "frequency": round(float(frequency_value), 2),
            "level": round(float(selected_power[time_index, frequency_index]), 2),
        }
        for time_index, time_value in enumerate(selected_times)
        for frequency_index, frequency_value in enumerate(selected_frequencies)
    ]
