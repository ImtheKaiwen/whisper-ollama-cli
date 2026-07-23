"""Immutable domain models shared by the stereo pipeline."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(frozen=True)
class ChannelAudio:
    channel_id: int
    speaker: str
    samples: Any
    sample_rate: int

    @property
    def duration_seconds(self) -> float:
        return len(self.samples) / self.sample_rate


@dataclass(frozen=True)
class AudioQuality:
    speaker: str
    rms_dbfs: float
    clipping_ratio: float
    silence_ratio: float
    dc_offset: float


@dataclass(frozen=True)
class WordTimestamp:
    text: str
    start_seconds: float
    end_seconds: float


@dataclass(frozen=True)
class TranscriptSegment:
    segment_id: str
    speaker: str
    channel_id: int
    start_seconds: float
    end_seconds: float
    text: str
    language: str = ""
    language_probability: float = 0.0
    words: tuple[WordTimestamp, ...] = field(default_factory=tuple)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class SpeechActivityInterval:
    interval_id: str
    speaker: str
    channel_id: int
    start_seconds: float
    end_seconds: float

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class Timeline:
    segments: tuple[TranscriptSegment, ...]
    overlap_pairs: tuple[tuple[str, str], ...]
    speech_activity: tuple[SpeechActivityInterval, ...] = field(default_factory=tuple)
    overlap_intervals: tuple[dict[str, Any], ...] = field(default_factory=tuple)

    def to_dict(self) -> dict[str, Any]:
        return {
            "segments": [segment.to_dict() for segment in self.segments],
            "overlap_pairs": [list(pair) for pair in self.overlap_pairs],
            "speech_activity": [item.to_dict() for item in self.speech_activity],
            "overlap_intervals": list(self.overlap_intervals),
        }


@dataclass(frozen=True)
class ProcessingResult:
    source_path: str
    sample_rate: int
    duration_seconds: float
    channel_map: dict[int, str]
    quality: tuple[AudioQuality, ...]
    channel_transcripts: dict[str, tuple[TranscriptSegment, ...]]
    timeline: Timeline
    full_transcript: str
    analysis_input: tuple[dict[str, Any], ...]
    analysis: dict[str, Any]
    validation: dict[str, Any]
    audit_log: tuple[dict[str, Any], ...]
    trace: tuple[dict[str, Any], ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_path": self.source_path,
            "sample_rate": self.sample_rate,
            "duration_seconds": self.duration_seconds,
            "channel_map": self.channel_map,
            "quality": [asdict(item) for item in self.quality],
            "channel_transcripts": {
                speaker: [segment.to_dict() for segment in segments]
                for speaker, segments in self.channel_transcripts.items()
            },
            "timeline": self.timeline.to_dict(),
            "full_transcript": self.full_transcript,
            "analysis_input": list(self.analysis_input),
            "analysis": self.analysis,
            "validation": self.validation,
            "audit_log": list(self.audit_log),
            "trace": list(self.trace),
        }
