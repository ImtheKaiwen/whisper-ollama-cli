"""Stable, lossless merging of channel transcripts on one absolute timeline."""

from __future__ import annotations

from collections.abc import Iterable

from .models import SpeechActivityInterval, Timeline, TranscriptSegment


class TimelineMerger:
    @staticmethod
    def merge(
        channels: Iterable[Iterable[TranscriptSegment]],
        speech_activity: Iterable[SpeechActivityInterval] | None = None,
        minimum_overlap_seconds: float = 0.1,
    ) -> Timeline:
        segments = sorted(
            (segment for channel in channels for segment in channel),
            key=lambda item: (
                item.start_seconds,
                item.end_seconds,
                item.channel_id,
                item.segment_id,
            ),
        )
        activity = sorted(
            speech_activity or [],
            key=lambda item: (item.start_seconds, item.end_seconds, item.channel_id),
        )
        overlaps: list[tuple[str, str]] = []
        overlap_intervals: list[dict[str, object]] = []
        if activity:
            for index, current in enumerate(activity):
                for following in activity[index + 1 :]:
                    if following.start_seconds >= current.end_seconds:
                        break
                    if following.channel_id == current.channel_id:
                        continue
                    start = max(current.start_seconds, following.start_seconds)
                    end = min(current.end_seconds, following.end_seconds)
                    if end - start < minimum_overlap_seconds:
                        continue
                    overlaps.append((current.interval_id, following.interval_id))
                    overlap_intervals.append(
                        {
                            "start_seconds": start,
                            "end_seconds": end,
                            "duration_seconds": end - start,
                            "speakers": [current.speaker, following.speaker],
                            "activity_interval_ids": [
                                current.interval_id,
                                following.interval_id,
                            ],
                        }
                    )
            return Timeline(
                tuple(segments),
                tuple(overlaps),
                tuple(activity),
                tuple(overlap_intervals),
            )

        for index, current in enumerate(segments):
            for following in segments[index + 1 :]:
                if following.start_seconds >= current.end_seconds:
                    break
                if following.channel_id != current.channel_id:
                    overlaps.append((current.segment_id, following.segment_id))
        return Timeline(tuple(segments), tuple(overlaps))
