import sys
from pathlib import Path

import numpy as np

AUDIO_LAB_DIR = Path(__file__).resolve().parents[1] / "tools" / "audio-lab"
sys.path.append(str(AUDIO_LAB_DIR))

from eventmonitor.visualization import (  # noqa: E402
    calculate_spectrogram,
    spectrogram_records,
)


def test_spectrogram_identifies_sine_frequency() -> None:
    sample_rate = 16_000
    time = np.arange(sample_rate, dtype=np.float32) / sample_rate
    audio = np.sin(2 * np.pi * 1_000 * time)

    times, frequencies, power_db = calculate_spectrogram(audio, sample_rate)

    peak_frequency = frequencies[np.argmax(power_db.mean(axis=0))]
    assert times.size > 0
    assert abs(float(peak_frequency) - 1_000) < 20
    assert power_db.max() == 0
    assert power_db.min() >= -100


def test_spectrogram_records_are_bounded_for_browser_rendering() -> None:
    times = np.linspace(0, 10, 500)
    frequencies = np.linspace(0, 8_000, 513)
    power = np.zeros((times.size, frequencies.size))

    records = spectrogram_records(times, frequencies, power, start_seconds=5)

    assert len(records) <= 220 * 96
    assert records[0]["time"] >= 5
    assert records[-1]["frequency"] <= 8_000


def test_short_stereo_audio_is_supported() -> None:
    audio = np.ones((100, 2), dtype=np.float32)
    times, frequencies, power_db = calculate_spectrogram(audio, 16_000)
    assert times.shape == (1,)
    assert frequencies.shape == (513,)
    assert power_db.shape == (1, 513)
