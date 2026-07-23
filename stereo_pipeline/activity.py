"""Deterministic per-channel energy VAD for offline timing/overlap authority."""

from __future__ import annotations

import numpy as np

from .models import ChannelAudio, SpeechActivityInterval


class EnergySpeechActivityDetector:
    """Find speech regions without sharing state between stereo channels."""

    def __init__(
        self,
        frame_ms: int = 20,
        min_speech_ms: int = 100,
        bridge_silence_ms: int = 120,
        pad_ms: int = 20,
    ) -> None:
        self.frame_ms = frame_ms
        self.min_speech_ms = min_speech_ms
        self.bridge_silence_ms = bridge_silence_ms
        self.pad_ms = pad_ms

    def detect(self, channel: ChannelAudio) -> list[SpeechActivityInterval]:
        frame_samples = max(1, channel.sample_rate * self.frame_ms // 1000)
        frame_count = (len(channel.samples) + frame_samples - 1) // frame_samples
        padded = np.pad(
            channel.samples,
            (0, frame_count * frame_samples - len(channel.samples)),
        )
        frames = padded.reshape(frame_count, frame_samples)
        rms = np.sqrt(np.mean(np.square(frames, dtype=np.float64), axis=1))
        nonzero = rms[rms > 1e-7]
        if nonzero.size == 0:
            return []
        speech_reference = float(np.percentile(nonzero, 90))
        noise_floor = float(np.percentile(rms, 35))
        threshold = max(0.002, noise_floor * 5.0, speech_reference * 0.12)
        active = rms >= threshold
        self._bridge_short_gaps(active, max(0, self.bridge_silence_ms // self.frame_ms))
        runs = self._active_runs(active)
        min_frames = max(1, self.min_speech_ms // self.frame_ms)
        pad_frames = max(0, self.pad_ms // self.frame_ms)
        output: list[SpeechActivityInterval] = []
        for start, end in runs:
            if end - start < min_frames:
                continue
            padded_start = max(0, start - pad_frames)
            padded_end = min(frame_count, end + pad_frames)
            output.append(
                SpeechActivityInterval(
                    interval_id=f"{channel.speaker}-vad-{len(output):04d}",
                    speaker=channel.speaker,
                    channel_id=channel.channel_id,
                    start_seconds=padded_start * self.frame_ms / 1000,
                    end_seconds=min(
                        len(channel.samples) / channel.sample_rate,
                        padded_end * self.frame_ms / 1000,
                    ),
                )
            )
        return output

    @staticmethod
    def _bridge_short_gaps(active: np.ndarray, max_gap: int) -> None:
        if max_gap <= 0:
            return
        index = 0
        while index < len(active):
            if active[index]:
                index += 1
                continue
            start = index
            while index < len(active) and not active[index]:
                index += 1
            if start > 0 and index < len(active) and index - start <= max_gap:
                active[start:index] = True

    @staticmethod
    def _active_runs(active: np.ndarray) -> list[tuple[int, int]]:
        runs: list[tuple[int, int]] = []
        index = 0
        while index < len(active):
            if not active[index]:
                index += 1
                continue
            start = index
            while index < len(active) and active[index]:
                index += 1
            runs.append((start, index))
        return runs
