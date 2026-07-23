"""Offline stereo processing orchestration with traceable stages."""

from __future__ import annotations

import time
from pathlib import Path

from .analysis import ConversationAnalyzer, timeline_to_analysis_input
from .activity import EnergySpeechActivityDetector
from .audio import StereoAudioProcessor
from .models import ProcessingResult
from .timeline import TimelineMerger
from .postprocessing import TranscriptSegmentSplitter
from .transcription import ChannelTranscriber


class StereoProcessingPipeline:
    def __init__(
        self,
        audio_processor: StereoAudioProcessor,
        transcriber: ChannelTranscriber,
        analyzer: ConversationAnalyzer,
        activity_detector: EnergySpeechActivityDetector | None = None,
        segment_splitter: TranscriptSegmentSplitter | None = None,
    ) -> None:
        self.audio_processor = audio_processor
        self.transcriber = transcriber
        self.analyzer = analyzer
        self.activity_detector = activity_detector or EnergySpeechActivityDetector()
        self.segment_splitter = segment_splitter or TranscriptSegmentSplitter()

    def run(
        self,
        source_path: str | Path,
        reference_path: str | Path | None = None,
    ) -> ProcessingResult:
        trace: list[dict[str, object]] = []
        audit_log: list[dict[str, object]] = []
        resolved_source = str(Path(source_path).resolve())

        def stage(name: str, started: float, **details: object) -> None:
            trace.append(
                {
                    "stage": name,
                    "elapsed_ms": round((time.perf_counter() - started) * 1000, 3),
                    **details,
                }
            )

        started = time.perf_counter()
        left, right = self.audio_processor.load(source_path)
        stage(
            "audio.load_and_split",
            started,
            sample_rate=left.sample_rate,
            samples=len(left.samples),
            speakers=[left.speaker, right.speaker],
        )
        audit_log.append(
            {
                "step": 1,
                "event": "stereo.input.validated",
                "source_path": resolved_source,
                "sample_rate": left.sample_rate,
                "duration_seconds": left.duration_seconds,
                "channel_map": {
                    str(left.channel_id): left.speaker,
                    str(right.channel_id): right.speaker,
                },
                "equal_channel_sample_count": len(left.samples) == len(right.samples),
            }
        )

        started = time.perf_counter()
        quality = (
            self.audio_processor.quality(left),
            self.audio_processor.quality(right),
        )
        correlation = self.audio_processor.channel_correlation(left, right)
        stage("audio.quality", started, channel_correlation=round(correlation, 6))
        started = time.perf_counter()
        speech_activity = (
            self.activity_detector.detect(left) + self.activity_detector.detect(right)
        )
        stage(
            "audio.speech_activity",
            started,
            interval_count=len(speech_activity),
        )

        channel_transcripts: list[list] = []
        for channel in (left, right):
            started = time.perf_counter()
            raw_segments = self.transcriber.transcribe(channel)
            segments = self.segment_splitter.split(raw_segments)
            channel_transcripts.append(segments)
            stage(
                "asr.transcribe",
                started,
                speaker=channel.speaker,
                raw_segment_count=len(raw_segments),
                segment_count=len(segments),
            )
            audit_log.append(
                {
                    "step": len(audit_log) + 1,
                    "event": "channel.transcribed",
                    "source_path": resolved_source,
                    "channel_id": channel.channel_id,
                    "speaker": channel.speaker,
                    "logical_source": f"{resolved_source}#channel={channel.channel_id}",
                    "segment_count": len(segments),
                    "transcript": " ".join(item.text for item in segments),
                    "segments": [item.to_dict() for item in segments],
                }
            )

        started = time.perf_counter()
        timeline = TimelineMerger.merge(channel_transcripts, speech_activity)
        stage(
            "timeline.merge",
            started,
            segment_count=len(timeline.segments),
            overlap_count=len(timeline.overlap_pairs),
        )
        full_transcript = "\n".join(
            f"[{item.start_seconds:.3f}-{item.end_seconds:.3f}] "
            f"{item.speaker}: {item.text}"
            for item in timeline.segments
        )
        analysis_input = tuple(timeline_to_analysis_input(timeline))
        audit_log.append(
            {
                "step": len(audit_log) + 1,
                "event": "timeline.concatenated_by_timestamp",
                "ordering_rule": "start_seconds,end_seconds,channel_id,segment_id",
                "audio_concatenation_performed": False,
                "reason": "Sessizlik ve overlap kaybolmasın diye yalnız transcript timeline birleştirilir.",
                "full_transcript": full_transcript,
                "overlap_pairs": [list(pair) for pair in timeline.overlap_pairs],
            }
        )
        audit_log.append(
            {
                "step": len(audit_log) + 1,
                "event": "analysis.request",
                "service": type(self.analyzer).__name__,
                "input": list(analysis_input),
            }
        )

        started = time.perf_counter()
        analysis = self.analyzer.analyze(timeline)
        stage(
            "analysis.run",
            started,
            evidence_count=len(analysis.evidence_segment_ids),
        )
        audit_log.append(
            {
                "step": len(audit_log) + 1,
                "event": "analysis.response",
                "service": type(self.analyzer).__name__,
                "result": analysis.to_dict(),
            }
        )

        validation: dict[str, object] = {
            "method": "structural_without_reference",
            "equal_channel_sample_count": len(left.samples) == len(right.samples),
            "timeline_is_monotonic": list(timeline.segments)
            == sorted(
                timeline.segments,
                key=lambda item: (
                    item.start_seconds,
                    item.end_seconds,
                    item.channel_id,
                    item.segment_id,
                ),
            ),
            "sample_axis_drift_detected": False,
            "note": "Referans verilmedi; ASR timestamp drift'i ölçülmedi.",
        }
        if reference_path is not None:
            from .validation import ReferenceTranscriptValidator

            validation = ReferenceTranscriptValidator().validate(
                timeline,
                reference_path,
            )
        audit_log.append(
            {
                "step": len(audit_log) + 1,
                "event": "validation.completed",
                "result": validation,
            }
        )

        return ProcessingResult(
            source_path=resolved_source,
            sample_rate=left.sample_rate,
            duration_seconds=left.duration_seconds,
            channel_map={left.channel_id: left.speaker, right.channel_id: right.speaker},
            quality=quality,
            channel_transcripts={
                left.speaker: tuple(channel_transcripts[0]),
                right.speaker: tuple(channel_transcripts[1]),
            },
            timeline=timeline,
            full_transcript=full_transcript,
            analysis_input=analysis_input,
            analysis=analysis.to_dict(),
            validation=validation,
            audit_log=tuple(audit_log),
            trace=tuple(trace),
        )
