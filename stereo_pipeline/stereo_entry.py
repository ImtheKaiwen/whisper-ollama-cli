"""Simple public facade for the complete offline stereo workflow."""

from __future__ import annotations

import json
import logging
import os
import time
from pathlib import Path
from typing import Iterable

from dotenv import load_dotenv

from .activity import EnergySpeechActivityDetector
from .analysis import (
    AnalysisResult,
    ConversationAnalyzer,
    OllamaConversationAnalyzer,
    timeline_to_analysis_input,
)
from .audio import StereoAudioProcessor
from .models import (
    AudioQuality,
    ChannelAudio,
    ProcessingResult,
    SpeechActivityInterval,
    Timeline,
    TranscriptSegment,
)
from .postprocessing import TranscriptSegmentSplitter
from .queueing import QueueDispatch, QueueOptions, QueuePublisher
from .reporting import ResultReporter
from .timeline import TimelineMerger
from .transcription import ChannelTranscriber, FasterWhisperTranscriber


class StereoPipeline:
    """Easy-to-use facade whose individual workflow steps remain public.

    Minimal usage::

        from stereo_pipeline import StereoPipeline

        pipeline = StereoPipeline()
        result = pipeline.analyze("voice.wav")
    """

    def __init__(
        self,
        *,
        audio_processor: StereoAudioProcessor | None = None,
        transcriber: ChannelTranscriber | None = None,
        analyzer: ConversationAnalyzer | None = None,
        activity_detector: EnergySpeechActivityDetector | None = None,
        segment_splitter: TranscriptSegmentSplitter | None = None,
        queue_options: QueueOptions | None = None,
        queue_publisher: QueuePublisher | None = None,
        output_dir: str | Path = "artifacts/stereo_pipeline",
        language: str | None = None,
        logger: logging.Logger | None = None,
    ) -> None:
        load_dotenv()
        self.audio_processor = audio_processor or StereoAudioProcessor()
        self._transcriber = transcriber
        self._analyzer = analyzer
        self.activity_detector = activity_detector or EnergySpeechActivityDetector()
        self.segment_splitter = segment_splitter or TranscriptSegmentSplitter()
        self.queue_options = queue_options or QueueOptions()
        self.queue_publisher = queue_publisher
        self.output_dir = Path(output_dir)
        self.language = language
        self.logger = logger or self._build_logger()

    @staticmethod
    def _build_logger() -> logging.Logger:
        logger = logging.getLogger("stereo_pipeline.facade")
        if not logger.handlers:
            handler = logging.StreamHandler()
            handler.setFormatter(logging.Formatter("[%(levelname)s] %(message)s"))
            logger.addHandler(handler)
        logger.setLevel(logging.INFO)
        logger.propagate = False
        return logger

    def get_transcriber(self) -> ChannelTranscriber:
        """Return the injected transcriber or lazily load Faster-Whisper."""
        if self._transcriber is None:
            configured_language = (
                self.language
                if self.language is not None
                else os.getenv("WHISPER_LANGUAGE", "tr")
            )
            self.logger.info("Faster-Whisper modeli yükleniyor")
            self._transcriber = FasterWhisperTranscriber(
                model_name=os.getenv("WHISPER_MODEL", "tiny"),
                device=os.getenv("WHISPER_DEVICE", "cpu"),
                compute_type=os.getenv("WHISPER_COMPUTE_TYPE", "int8"),
                language=(
                    None
                    if configured_language.lower() == "auto"
                    else configured_language
                ),
            )
        return self._transcriber

    def get_analyzer(self) -> ConversationAnalyzer:
        """Return the injected analyzer or the environment-configured Ollama adapter."""
        if self._analyzer is None:
            self._analyzer = OllamaConversationAnalyzer(
                url=os.getenv("OLLAMA_URL", "http://127.0.0.1:11434"),
                model=os.getenv("OLLAMA_MODEL", "gemma2:2b"),
                timeout_seconds=float(os.getenv("OLLAMA_TIMEOUT_SECONDS", "60")),
                strict_evidence_ids=False,
            )
        return self._analyzer

    def split_channels(
        self,
        stereo_path: str | Path,
    ) -> tuple[ChannelAudio, ChannelAudio]:
        """Validate a stereo file and return synchronized L/R mono channels."""
        self.logger.info("Stereo dosya doğrulanıyor ve kanallara ayrılıyor: %s", stereo_path)
        return self.audio_processor.load(stereo_path)

    def measure_channel_quality(
        self,
        channels: Iterable[ChannelAudio],
    ) -> tuple[AudioQuality, ...]:
        """Measure each channel independently."""
        return tuple(self.audio_processor.quality(channel) for channel in channels)

    def detect_speech_activity(
        self,
        channels: Iterable[ChannelAudio],
    ) -> list[SpeechActivityInterval]:
        """Produce independent per-channel VAD intervals."""
        intervals: list[SpeechActivityInterval] = []
        for channel in channels:
            intervals.extend(self.activity_detector.detect(channel))
        return intervals

    def transcribe_channel(self, channel: ChannelAudio) -> list[TranscriptSegment]:
        """Transcribe and normalize one channel; usable independently."""
        self.logger.info(
            "Whisper transkripsiyonu: channel=%s speaker=%s",
            channel.channel_id,
            channel.speaker,
        )
        raw_segments = self.get_transcriber().transcribe(channel)
        return self.segment_splitter.split(raw_segments)

    def transcribe_channels(
        self,
        channels: Iterable[ChannelAudio],
        *,
        source_path: str | Path,
        queue_payload_dir: str | Path,
    ) -> tuple[dict[str, tuple[TranscriptSegment, ...]], list[QueueDispatch]]:
        """Transcribe both channels and optionally dispatch their mono files."""
        transcripts: dict[str, tuple[TranscriptSegment, ...]] = {}
        dispatches: list[QueueDispatch] = []
        for channel in channels:
            dispatches.append(
                self.push_channel_to_whisper_queue(
                    channel,
                    source_path=source_path,
                    payload_dir=queue_payload_dir,
                )
            )
            transcripts[channel.speaker] = tuple(self.transcribe_channel(channel))
        return transcripts, dispatches

    def merge_transcripts(
        self,
        channel_transcripts: dict[str, tuple[TranscriptSegment, ...]],
        speech_activity: Iterable[SpeechActivityInterval],
    ) -> Timeline:
        """Merge channel transcripts on the original absolute time axis."""
        self.logger.info("Kanal transcriptleri zamanlarına göre birleştiriliyor")
        return TimelineMerger.merge(
            channel_transcripts.values(),
            speech_activity,
        )

    @staticmethod
    def build_full_transcript(timeline: Timeline) -> str:
        """Format the final speaker-labelled transcript."""
        return "\n".join(
            f"[{item.start_seconds:.3f}-{item.end_seconds:.3f}] "
            f"{item.speaker}: {item.text}"
            for item in timeline.segments
        )

    def send_to_analysis(self, timeline: Timeline) -> AnalysisResult:
        """Send only the finalized timeline to the configured analyzer."""
        self.logger.info("Birleştirilmiş transcript analiz servisine gönderiliyor")
        return self.get_analyzer().analyze(timeline)

    def push_channel_to_whisper_queue(
        self,
        channel: ChannelAudio,
        *,
        source_path: str | Path,
        payload_dir: str | Path,
    ) -> QueueDispatch:
        """Optionally save and publish one mono channel for a Whisper worker."""
        queue_name = self.queue_options.whisper_queue_name
        if not self.queue_options.whisper_enabled:
            return QueueDispatch(queue_name=queue_name, status="disabled")
        publisher = self._require_queue_publisher("Whisper")
        output = Path(payload_dir) / f"channel_{channel.channel_id}_{channel.speaker}.wav"
        self.audio_processor.save_mono(channel, output)
        payload = {
            "source_path": str(Path(source_path).resolve()),
            "channel_id": channel.channel_id,
            "speaker": channel.speaker,
            "audio_path": str(output.resolve()),
            "sample_rate": channel.sample_rate,
            "duration_seconds": channel.duration_seconds,
        }
        publisher.publish(queue_name, payload)
        self.logger.info("Kanal Whisper queue'ya gönderildi: %s", queue_name)
        return QueueDispatch(queue_name=queue_name, status="published", payload=payload)

    def push_transcript_to_analysis_queue(
        self,
        timeline: Timeline,
        full_transcript: str,
        *,
        source_path: str | Path,
    ) -> QueueDispatch:
        """Optionally publish the finalized transcript for an analysis worker."""
        queue_name = self.queue_options.analysis_queue_name
        if not self.queue_options.analysis_enabled:
            return QueueDispatch(queue_name=queue_name, status="disabled")
        publisher = self._require_queue_publisher("Analysis")
        payload = {
            "source_path": str(Path(source_path).resolve()),
            "full_transcript": full_transcript,
            "timeline": timeline_to_analysis_input(timeline),
            "overlap_pairs": [list(pair) for pair in timeline.overlap_pairs],
        }
        publisher.publish(queue_name, payload)
        self.logger.info("Final transcript analysis queue'ya gönderildi: %s", queue_name)
        return QueueDispatch(queue_name=queue_name, status="published", payload=payload)

    def _require_queue_publisher(self, label: str) -> QueuePublisher:
        if self.queue_publisher is None:
            raise RuntimeError(
                f"{label} queue etkin fakat queue_publisher yapılandırılmamış"
            )
        return self.queue_publisher

    def write_outputs(
        self,
        result: ProcessingResult,
        output_dir: str | Path,
    ) -> dict[str, Path]:
        """Write all audit and report files; usable independently."""
        directory = Path(output_dir)
        paths = {
            "result": ResultReporter.write_json(result, directory / "result.json"),
            "audit": ResultReporter.write_audit_json(result, directory / "audit.json"),
            "report": ResultReporter.write_markdown(result, directory / "report.md"),
        }
        log_path = directory / "pipeline.log"
        log_path.write_text(
            "\n".join(
                json.dumps(event, ensure_ascii=False)
                for event in result.audit_log
            )
            + "\n",
            encoding="utf-8",
        )
        paths["log"] = log_path
        return paths

    @staticmethod
    def print_analysis_result(analysis: AnalysisResult) -> None:
        """Print the final analysis to the console."""
        print("\n=== Stereo Görüşme Analizi ===")
        for key, value in analysis.to_dict().items():
            print(f"{key}: {value}")

    def analyze(
        self,
        stereo_path: str | Path,
        *,
        output_dir: str | Path | None = None,
        reference_path: str | Path | None = None,
    ) -> ProcessingResult:
        """Run split -> ASR -> merge -> queue hook -> analysis -> log -> print."""
        source = Path(stereo_path)
        resolved_source = str(source.resolve())
        run_output = Path(output_dir) if output_dir else self.output_dir / source.stem
        trace: list[dict[str, object]] = []
        audit: list[dict[str, object]] = []

        def timed(stage: str, started: float, **details: object) -> None:
            trace.append(
                {
                    "stage": stage,
                    "elapsed_ms": round((time.perf_counter() - started) * 1000, 3),
                    **details,
                }
            )

        started = time.perf_counter()
        channels = self.split_channels(source)
        timed("audio.load_and_split", started, sample_rate=channels[0].sample_rate)
        audit.append(
            {
                "step": 1,
                "event": "stereo.input.validated",
                "source_path": resolved_source,
                "channel_map": {
                    str(channel.channel_id): channel.speaker for channel in channels
                },
                "equal_channel_sample_count": len(channels[0].samples)
                == len(channels[1].samples),
            }
        )

        started = time.perf_counter()
        quality = self.measure_channel_quality(channels)
        activity = self.detect_speech_activity(channels)
        timed("audio.quality_and_activity", started, interval_count=len(activity))

        started = time.perf_counter()
        transcripts, whisper_dispatches = self.transcribe_channels(
            channels,
            source_path=source,
            queue_payload_dir=run_output / "queue_payloads",
        )
        timed(
            "asr.transcribe_channels",
            started,
            segment_count=sum(len(items) for items in transcripts.values()),
        )
        for channel, dispatch in zip(channels, whisper_dispatches):
            audit.append(
                {
                    "step": len(audit) + 1,
                    "event": "channel.transcribed",
                    "channel_id": channel.channel_id,
                    "speaker": channel.speaker,
                    "transcript": " ".join(
                        segment.text for segment in transcripts[channel.speaker]
                    ),
                    "segments": [
                        segment.to_dict()
                        for segment in transcripts[channel.speaker]
                    ],
                    "whisper_queue": dispatch.to_dict(),
                }
            )

        started = time.perf_counter()
        timeline = self.merge_transcripts(transcripts, activity)
        full_transcript = self.build_full_transcript(timeline)
        timed(
            "timeline.merge",
            started,
            segment_count=len(timeline.segments),
            overlap_count=len(timeline.overlap_pairs),
        )
        audit.append(
            {
                "step": len(audit) + 1,
                "event": "timeline.concatenated_by_timestamp",
                "full_transcript": full_transcript,
                "overlap_pairs": [list(pair) for pair in timeline.overlap_pairs],
            }
        )

        analysis_dispatch = self.push_transcript_to_analysis_queue(
            timeline,
            full_transcript,
            source_path=source,
        )
        audit.append(
            {
                "step": len(audit) + 1,
                "event": "analysis.queue",
                "dispatch": analysis_dispatch.to_dict(),
            }
        )

        started = time.perf_counter()
        audit.append(
            {
                "step": len(audit) + 1,
                "event": "analysis.request",
                "service": type(self.get_analyzer()).__name__,
                "input": timeline_to_analysis_input(timeline),
            }
        )
        analysis = self.send_to_analysis(timeline)
        timed("analysis.run", started)
        invalid_evidence_ids = tuple(
            getattr(self.get_analyzer(), "last_invalid_evidence_ids", ())
        )
        if invalid_evidence_ids:
            self.logger.warning(
                "Timeline dışında üretilen evidence ID'leri atlandı: %s",
                ", ".join(invalid_evidence_ids),
            )
        audit.append(
            {
                "step": len(audit) + 1,
                "event": "analysis.response",
                "result": analysis.to_dict(),
                "discarded_invalid_evidence_ids": list(invalid_evidence_ids),
            }
        )

        validation: dict[str, object] = {
            "method": "structural_without_reference",
            "equal_channel_sample_count": len(channels[0].samples)
            == len(channels[1].samples),
            "sample_axis_drift_detected": False,
        }
        if reference_path is not None:
            from .validation import ReferenceTranscriptValidator

            validation = ReferenceTranscriptValidator().validate(
                timeline,
                reference_path,
            )
        audit.append(
            {
                "step": len(audit) + 1,
                "event": "validation.completed",
                "result": validation,
            }
        )

        result = ProcessingResult(
            source_path=resolved_source,
            sample_rate=channels[0].sample_rate,
            duration_seconds=channels[0].duration_seconds,
            channel_map={
                channel.channel_id: channel.speaker for channel in channels
            },
            quality=quality,
            channel_transcripts=transcripts,
            timeline=timeline,
            full_transcript=full_transcript,
            analysis_input=tuple(timeline_to_analysis_input(timeline)),
            analysis=analysis.to_dict(),
            validation=validation,
            audit_log=tuple(audit),
            trace=tuple(trace),
        )
        paths = self.write_outputs(result, run_output)
        self.logger.info("Log ve raporlar yazıldı: %s", paths["audit"].parent)
        self.print_analysis_result(analysis)
        return result
