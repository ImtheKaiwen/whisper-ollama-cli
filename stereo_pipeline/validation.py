"""Reference-based transcript, timing and overlap validation."""

from __future__ import annotations

import json
import re
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

import numpy as np

from .models import Timeline


def _words(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", text.lower())


def _edit_distance(reference: list[str], hypothesis: list[str]) -> int:
    previous = list(range(len(hypothesis) + 1))
    for row, ref_word in enumerate(reference, 1):
        current = [row] + [0] * len(hypothesis)
        for column, hyp_word in enumerate(hypothesis, 1):
            current[column] = min(
                current[column - 1] + 1,
                previous[column] + 1,
                previous[column - 1] + (ref_word != hyp_word),
            )
        previous = current
    return previous[-1]


class ReferenceTranscriptValidator:
    """Compare pipeline output with speaker-labelled human transcript JSON."""

    def validate(
        self,
        timeline: Timeline,
        reference_path: str | Path,
        role_map: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        path = Path(reference_path)
        reference = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(reference, list):
            raise ValueError("Referans transkript JSON listesi olmalıdır")
        mapping = role_map or {"agent": "agent", "caller": "customer"}
        speakers: dict[str, Any] = {}
        all_timing_errors: list[tuple[float, float]] = []

        for reference_role, output_speaker in mapping.items():
            ref_segments = [
                item for item in reference if item.get("speaker_role") == reference_role
            ]
            hyp_segments = [
                item for item in timeline.segments if item.speaker == output_speaker
            ]
            ref_tokens: list[str] = []
            ref_timed: list[tuple[str, float]] = []
            for item in ref_segments:
                text = str(item.get("human_transcript", ""))
                if text.startswith("["):
                    continue
                tokens = _words(text)
                ref_tokens.extend(tokens)
                offsets = item.get("word_offsets_ms") or []
                for index, token in enumerate(tokens):
                    if index < len(offsets):
                        start = (float(item["start_ms"]) + float(offsets[index])) / 1000
                    else:
                        start = float(item["start_ms"]) / 1000
                    ref_timed.append((token, start))

            hyp_tokens: list[str] = []
            hyp_timed: list[tuple[str, float]] = []
            for segment in hyp_segments:
                if segment.words:
                    for word in segment.words:
                        tokens = _words(word.text)
                        for token in tokens:
                            hyp_tokens.append(token)
                            hyp_timed.append((token, word.start_seconds))
                else:
                    for token in _words(segment.text):
                        hyp_tokens.append(token)
                        hyp_timed.append((token, segment.start_seconds))

            errors = _edit_distance(ref_tokens, hyp_tokens)
            matcher = SequenceMatcher(a=ref_tokens, b=hyp_tokens, autojunk=False)
            timing_errors: list[tuple[float, float]] = []
            for block in matcher.get_matching_blocks():
                for offset in range(block.size):
                    ref_index = block.a + offset
                    hyp_index = block.b + offset
                    if ref_index < len(ref_timed) and hyp_index < len(hyp_timed):
                        ref_time = ref_timed[ref_index][1]
                        error = hyp_timed[hyp_index][1] - ref_time
                        timing_errors.append((ref_time, error))
                        all_timing_errors.append((ref_time, error))

            timing = self._timing_summary(timing_errors)
            speakers[output_speaker] = {
                "reference_role": reference_role,
                "reference_word_count": len(ref_tokens),
                "transcript_word_count": len(hyp_tokens),
                "word_errors": errors,
                "wer": round(errors / max(1, len(ref_tokens)), 6),
                "matched_words_for_timing": len(timing_errors),
                "timing": timing,
            }

        expected_overlaps = self._reference_overlaps(reference, mapping)
        detected_overlaps = [list(pair) for pair in timeline.overlap_pairs]
        global_timing = self._timing_summary(all_timing_errors)
        asr_drift_detected = bool(global_timing.get("drift_detected", False))
        overlap_matches = len(expected_overlaps) == len(detected_overlaps)
        return {
            "method": "human_reference_json_plus_word_timestamps",
            "reference_path": str(path.resolve()),
            "speaker_metrics": speakers,
            "timing_alignment": global_timing,
            "overlap_validation": {
                "expected_count": len(expected_overlaps),
                "detected_count": len(detected_overlaps),
                "count_matches": overlap_matches,
                "expected_intervals": expected_overlaps,
                "detected_segment_pairs": detected_overlaps,
            },
            "sample_axis_alignment": {
                "equal_length_channels_required": True,
                "drift_detected": False,
                "basis": (
                    "Stereo L/R aynı frame dizisinden çıkarılmış ve aynı resample "
                    "işlemi uygulanmıştır; ayrı saat alanı yoktur."
                ),
            },
            "asr_timestamp_drift_detected": asr_drift_detected,
            "overall_status": (
                "pass" if not asr_drift_detected and overlap_matches else "needs_review"
            ),
            "human_listening_review": {
                "status": "not_performed_by_automated_agent",
                "reason": (
                    "Ses işitme/playback değerlendirmesi mevcut araçlarda yok; "
                    "doğrulama insan transkripti, kelime zamanları ve waveform "
                    "özellikleriyle yapılmıştır."
                ),
                "reviewer_fields": {
                    "agent_channel_correct": None,
                    "customer_channel_correct": None,
                    "transcript_matches_audio": None,
                    "notes": "",
                },
            },
        }

    @staticmethod
    def _timing_summary(errors: list[tuple[float, float]]) -> dict[str, Any]:
        if not errors:
            return {
                "status": "insufficient_matches",
                "drift_detected": None,
            }
        ref_times = np.asarray([item[0] for item in errors], dtype=np.float64)
        offsets = np.asarray([item[1] for item in errors], dtype=np.float64)
        if len(errors) >= 2 and float(np.ptp(ref_times)) > 0:
            slope = float(np.polyfit(ref_times, offsets, 1)[0])
            drift_ms_per_minute = slope * 60_000.0
        else:
            drift_ms_per_minute = 0.0
        absolute_ms = np.abs(offsets) * 1000
        drift_threshold = 250.0
        p95_threshold = 500.0
        p95_absolute_error_ms = float(np.percentile(absolute_ms, 95))
        drift_detected = (
            abs(drift_ms_per_minute) > drift_threshold
            or p95_absolute_error_ms > p95_threshold
        )
        return {
            "status": "measured",
            "matched_word_count": len(errors),
            "median_offset_ms": round(float(np.median(offsets) * 1000), 3),
            "mean_absolute_error_ms": round(float(np.mean(absolute_ms)), 3),
            "p95_absolute_error_ms": round(p95_absolute_error_ms, 3),
            "drift_ms_per_minute": round(drift_ms_per_minute, 3),
            "drift_threshold_ms_per_minute": drift_threshold,
            "p95_error_threshold_ms": p95_threshold,
            "drift_detected": drift_detected,
            "interpretation": (
                "Drift zamanla büyüyen eğimdir; sabit timestamp bias drift değildir."
            ),
        }

    @staticmethod
    def _reference_overlaps(
        reference: list[dict[str, Any]],
        mapping: dict[str, str],
    ) -> list[dict[str, Any]]:
        roles = list(mapping)
        if len(roles) != 2:
            return []
        left = [item for item in reference if item.get("speaker_role") == roles[0]]
        right = [item for item in reference if item.get("speaker_role") == roles[1]]
        overlaps: list[dict[str, Any]] = []
        for first in left:
            for second in right:
                start = max(int(first["start_ms"]), int(second["start_ms"]))
                end = min(
                    int(first["start_ms"]) + int(first["duration_ms"]),
                    int(second["start_ms"]) + int(second["duration_ms"]),
                )
                if start < end:
                    overlaps.append(
                        {
                            "start_ms": start,
                            "end_ms": end,
                            "duration_ms": end - start,
                            "roles": [roles[0], roles[1]],
                            "reference_segment_indexes": [
                                first.get("index"),
                                second.get("index"),
                            ],
                        }
                    )
        return overlaps
