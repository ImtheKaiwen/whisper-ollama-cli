"""Transcription interface and faster-whisper adapter."""

from __future__ import annotations

from typing import Protocol

from faster_whisper import WhisperModel

from .models import ChannelAudio, TranscriptSegment, WordTimestamp


class ChannelTranscriber(Protocol):
    def transcribe(self, channel: ChannelAudio) -> list[TranscriptSegment]:
        """Transcribe one named mono channel without changing its time axis."""


class FasterWhisperTranscriber:
    """A single reusable Whisper model shared sequentially by both channels."""

    def __init__(
        self,
        model_name: str = "tiny",
        device: str = "cpu",
        compute_type: str = "int8",
        language: str | None = "tr",
        beam_size: int = 3,
        initial_prompt: str | None = None,
    ) -> None:
        self.model = WhisperModel(model_name, device=device, compute_type=compute_type)
        self.language = language
        self.beam_size = beam_size
        self.initial_prompt = initial_prompt

    def transcribe(self, channel: ChannelAudio) -> list[TranscriptSegment]:
        generator, info = self.model.transcribe(
            channel.samples,
            task="transcribe",
            language=self.language,
            beam_size=self.beam_size,
            word_timestamps=True,
            condition_on_previous_text=False,
            vad_filter=True,
            vad_parameters={"min_silence_duration_ms": 500},
            initial_prompt=self.initial_prompt,
        )
        output: list[TranscriptSegment] = []
        for index, segment in enumerate(generator):
            text = segment.text.strip()
            if not text:
                continue
            words = tuple(
                WordTimestamp(
                    text=word.word.strip(),
                    start_seconds=float(word.start),
                    end_seconds=float(word.end),
                )
                for word in (segment.words or [])
                if word.word.strip()
            )
            output.append(
                TranscriptSegment(
                    segment_id=f"{channel.speaker}-{index:04d}",
                    speaker=channel.speaker,
                    channel_id=channel.channel_id,
                    start_seconds=float(segment.start),
                    end_seconds=float(segment.end),
                    text=text,
                    language=str(info.language or ""),
                    language_probability=float(info.language_probability or 0.0),
                    words=words,
                )
            )
        return output
