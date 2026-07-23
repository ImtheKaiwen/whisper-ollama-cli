"""Stereo WAV validation, synchronized splitting, resampling and quality checks."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import soundfile as sf
import soxr

from .models import AudioQuality, ChannelAudio


class StereoAudioError(ValueError):
    """Raised when an input cannot satisfy the named-stereo contract."""


class StereoAudioProcessor:
    """Convert a two-channel file into synchronized named mono channels."""

    def __init__(
        self,
        target_sample_rate: int = 16_000,
        channel_map: dict[int, str] | None = None,
    ) -> None:
        self.target_sample_rate = target_sample_rate
        self.channel_map = channel_map or {0: "agent", 1: "customer"}
        if set(self.channel_map) != {0, 1}:
            raise ValueError("channel_map exactly 0 and 1 kanalını içermelidir")

    def load(self, path: str | Path) -> tuple[ChannelAudio, ChannelAudio]:
        source = Path(path)
        if not source.is_file():
            raise FileNotFoundError(source)
        audio, source_rate = sf.read(source, dtype="float32", always_2d=True)
        if audio.shape[1] != 2:
            raise StereoAudioError(
                f"İki kanal bekleniyordu, bulunan kanal sayısı: {audio.shape[1]}"
            )
        if not np.isfinite(audio).all():
            raise StereoAudioError("Ses NaN veya sonsuz örnek içeriyor")

        channels: list[ChannelAudio] = []
        for channel_id in (0, 1):
            samples = np.ascontiguousarray(audio[:, channel_id], dtype=np.float32)
            if source_rate != self.target_sample_rate:
                samples = soxr.resample(
                    samples,
                    source_rate,
                    self.target_sample_rate,
                    quality="HQ",
                ).astype(np.float32, copy=False)
            channels.append(
                ChannelAudio(
                    channel_id=channel_id,
                    speaker=self.channel_map[channel_id],
                    samples=samples,
                    sample_rate=self.target_sample_rate,
                )
            )

        length = min(len(channels[0].samples), len(channels[1].samples))
        if length == 0:
            raise StereoAudioError("Ses dosyası boş")
        # A shared trim removes only a possible one-sample resampler rounding delta.
        return tuple(
            ChannelAudio(
                channel_id=item.channel_id,
                speaker=item.speaker,
                samples=item.samples[:length],
                sample_rate=item.sample_rate,
            )
            for item in channels
        )  # type: ignore[return-value]

    @staticmethod
    def quality(channel: ChannelAudio, silence_threshold: float = 0.002) -> AudioQuality:
        samples = channel.samples
        rms = float(np.sqrt(np.mean(np.square(samples, dtype=np.float64))))
        rms_dbfs = 20.0 * np.log10(max(rms, 1e-12))
        return AudioQuality(
            speaker=channel.speaker,
            rms_dbfs=float(rms_dbfs),
            clipping_ratio=float(np.mean(np.abs(samples) >= 0.999)),
            silence_ratio=float(np.mean(np.abs(samples) < silence_threshold)),
            dc_offset=float(np.mean(samples)),
        )

    @staticmethod
    def channel_correlation(left: ChannelAudio, right: ChannelAudio) -> float:
        if len(left.samples) != len(right.samples):
            raise ValueError("Kanal uzunlukları eşit olmalıdır")
        if np.std(left.samples) < 1e-9 or np.std(right.samples) < 1e-9:
            return 0.0
        return float(np.corrcoef(left.samples, right.samples)[0, 1])

    @staticmethod
    def save_mono(channel: ChannelAudio, path: str | Path) -> None:
        output = Path(path)
        output.parent.mkdir(parents=True, exist_ok=True)
        sf.write(output, channel.samples, channel.sample_rate, subtype="PCM_16")
