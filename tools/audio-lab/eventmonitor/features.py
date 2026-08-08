from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import librosa
import numpy as np

FEATURE_PIPELINE_VERSION = "1.0.0"


@dataclass(frozen=True)
class FeaturePipelineConfig:
    version: str = FEATURE_PIPELINE_VERSION
    target_sample_rate: int = 16_000
    clip_duration_seconds: float = 5.0
    n_fft: int = 1_024
    hop_length: int = 320
    n_mels: int = 64
    fmin_hz: float = 20.0
    fmax_hz: float = 8_000.0
    peak_normalization: bool = True

    def __post_init__(self) -> None:
        if self.version != FEATURE_PIPELINE_VERSION:
            raise ValueError(f"Nicht unterstützte Feature-Pipeline-Version: {self.version}")
        if self.target_sample_rate <= 0 or self.clip_duration_seconds <= 0:
            raise ValueError("Samplerate und Clip-Länge müssen positiv sein.")
        if self.n_fft <= 0 or self.hop_length <= 0 or self.n_mels <= 0:
            raise ValueError("FFT-, Hop- und Mel-Parameter müssen positiv sein.")
        if not 0 <= self.fmin_hz < self.fmax_hz <= self.target_sample_rate / 2:
            raise ValueError("Der Frequenzbereich muss innerhalb der Nyquist-Grenze liegen.")

    @property
    def fingerprint(self) -> str:
        canonical = json.dumps(asdict(self), sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(canonical.encode()).hexdigest()

    def save(self, path: str | Path) -> Path:
        destination = Path(path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(json.dumps(asdict(self), indent=2), encoding="utf-8")
        return destination

    @classmethod
    def load(cls, path: str | Path) -> FeaturePipelineConfig:
        return cls(**json.loads(Path(path).read_text(encoding="utf-8")))


@dataclass(frozen=True)
class ExtractedFeatures:
    values: np.ndarray
    names: tuple[str, ...]
    pipeline_version: str
    pipeline_fingerprint: str

    def metadata(self) -> dict[str, Any]:
        return {
            "pipeline_version": self.pipeline_version,
            "pipeline_fingerprint": self.pipeline_fingerprint,
            "feature_count": len(self.names),
            "feature_names": list(self.names),
        }


def preprocess_audio(
    audio: np.ndarray, sample_rate: int, config: FeaturePipelineConfig
) -> np.ndarray:
    samples = np.asarray(audio, dtype=np.float32)
    if samples.ndim == 2:
        samples = samples.mean(axis=1)
    elif samples.ndim != 1:
        raise ValueError("Audio muss ein Mono- oder Stereo-Signal sein.")
    if sample_rate <= 0 or samples.size == 0:
        raise ValueError("Audio und Samplerate müssen gültig sein.")
    samples = np.nan_to_num(samples, nan=0.0, posinf=1.0, neginf=-1.0)
    if sample_rate != config.target_sample_rate:
        samples = librosa.resample(
            samples, orig_sr=sample_rate, target_sr=config.target_sample_rate, res_type="soxr_hq"
        )
    target_samples = round(config.target_sample_rate * config.clip_duration_seconds)
    if len(samples) > target_samples:
        offset = (len(samples) - target_samples) // 2
        samples = samples[offset : offset + target_samples]
    elif len(samples) < target_samples:
        missing = target_samples - len(samples)
        samples = np.pad(samples, (missing // 2, missing - missing // 2))
    if config.peak_normalization:
        peak = float(np.max(np.abs(samples)))
        if peak > 1e-8:
            samples = samples / peak
    return np.asarray(samples, dtype=np.float32)


def _summary(name: str, values: np.ndarray) -> tuple[list[float], list[str]]:
    return [float(np.mean(values)), float(np.std(values))], [f"{name}_mean", f"{name}_std"]


def extract_features(
    audio: np.ndarray,
    sample_rate: int,
    config: FeaturePipelineConfig | None = None,
) -> ExtractedFeatures:
    config = config or FeaturePipelineConfig()
    samples = preprocess_audio(audio, sample_rate, config)
    mel = librosa.feature.melspectrogram(
        y=samples,
        sr=config.target_sample_rate,
        n_fft=config.n_fft,
        hop_length=config.hop_length,
        n_mels=config.n_mels,
        fmin=config.fmin_hz,
        fmax=config.fmax_hz,
        power=2.0,
    )
    log_mel = librosa.power_to_db(mel, ref=1.0, top_db=80.0)
    values = [*np.mean(log_mel, axis=1), *np.std(log_mel, axis=1)]
    names = [f"log_mel_{index:02d}_mean" for index in range(config.n_mels)] + [
        f"log_mel_{index:02d}_std" for index in range(config.n_mels)
    ]
    descriptors = {
        "zero_crossing_rate": librosa.feature.zero_crossing_rate(
            samples, frame_length=config.n_fft, hop_length=config.hop_length
        ),
        "rms": librosa.feature.rms(
            y=samples, frame_length=config.n_fft, hop_length=config.hop_length
        ),
        "spectral_centroid": librosa.feature.spectral_centroid(
            y=samples,
            sr=config.target_sample_rate,
            n_fft=config.n_fft,
            hop_length=config.hop_length,
        ),
        "spectral_bandwidth": librosa.feature.spectral_bandwidth(
            y=samples,
            sr=config.target_sample_rate,
            n_fft=config.n_fft,
            hop_length=config.hop_length,
        ),
        "spectral_rolloff": librosa.feature.spectral_rolloff(
            y=samples,
            sr=config.target_sample_rate,
            n_fft=config.n_fft,
            hop_length=config.hop_length,
        ),
        "spectral_flatness": librosa.feature.spectral_flatness(
            y=samples, n_fft=config.n_fft, hop_length=config.hop_length
        ),
    }
    for name, descriptor in descriptors.items():
        summary, summary_names = _summary(name, descriptor)
        values.extend(summary)
        names.extend(summary_names)
    vector = np.asarray(values, dtype=np.float32)
    if not np.all(np.isfinite(vector)):
        raise ValueError("Die Feature-Berechnung hat ungültige Werte erzeugt.")
    return ExtractedFeatures(vector, tuple(names), config.version, config.fingerprint)
