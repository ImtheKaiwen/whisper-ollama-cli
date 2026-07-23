"""Deterministic test doubles for model-dependent boundaries."""

from __future__ import annotations

from stereo_pipeline.analysis import AnalysisResult
from stereo_pipeline.models import ChannelAudio, Timeline, TranscriptSegment


class DeterministicTranscriber:
    def transcribe(self, channel: ChannelAudio) -> list[TranscriptSegment]:
        if channel.speaker == "agent":
            return [
                TranscriptSegment(
                    segment_id="agent-0000",
                    speaker="agent",
                    channel_id=0,
                    start_seconds=0.50,
                    end_seconds=1.50,
                    text="Size nasıl yardımcı olabilirim?",
                    language="tr",
                    language_probability=1.0,
                )
            ]
        return [
            TranscriptSegment(
                segment_id="customer-0000",
                speaker="customer",
                channel_id=1,
                start_seconds=1.20,
                end_seconds=2.30,
                text="Paket bütçemi aşıyor.",
                language="tr",
                language_probability=1.0,
            )
        ]


class EvidenceAnalyzer:
    def __init__(self) -> None:
        self.received: Timeline | None = None

    def analyze(self, timeline: Timeline) -> AnalysisResult:
        self.received = timeline
        return AnalysisResult(
            emotion="endişeli",
            need="daha uygun paket",
            topic="bütçe",
            intent="alternatife açık",
            objection_type="budget",
            conversation_stage="objection_handling",
            recommended_action="Bütçe aralığını sor.",
            confidence=0.9,
            evidence_segment_ids=("customer-0000",),
        )
