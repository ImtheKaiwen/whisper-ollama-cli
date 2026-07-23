"""Automatic ASR segment normalization without reference-text correction."""

from __future__ import annotations

from .models import TranscriptSegment


class TranscriptSegmentSplitter:
    """Split long Whisper segments where word timestamps contain long silence."""

    def __init__(self, max_word_gap_seconds: float = 0.8) -> None:
        self.max_word_gap_seconds = max_word_gap_seconds

    def split(self, segments: list[TranscriptSegment]) -> list[TranscriptSegment]:
        output: list[TranscriptSegment] = []
        for segment in segments:
            if len(segment.words) < 2:
                output.append(segment)
                continue
            groups = []
            current = [segment.words[0]]
            for word in segment.words[1:]:
                if word.start_seconds - current[-1].end_seconds > self.max_word_gap_seconds:
                    groups.append(current)
                    current = [word]
                else:
                    current.append(word)
            groups.append(current)
            if len(groups) == 1:
                output.append(segment)
                continue
            for index, words in enumerate(groups):
                text = " ".join(word.text for word in words).strip()
                output.append(
                    TranscriptSegment(
                        segment_id=f"{segment.segment_id}-u{index:03d}",
                        speaker=segment.speaker,
                        channel_id=segment.channel_id,
                        start_seconds=words[0].start_seconds,
                        end_seconds=words[-1].end_seconds,
                        text=text,
                        language=segment.language,
                        language_probability=segment.language_probability,
                        words=tuple(words),
                    )
                )
        return output
