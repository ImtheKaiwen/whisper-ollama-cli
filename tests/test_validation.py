from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from stereo_pipeline.models import Timeline, TranscriptSegment, WordTimestamp
from stereo_pipeline.validation import ReferenceTranscriptValidator


class ReferenceTranscriptValidatorTests(unittest.TestCase):
    def test_reports_wer_timing_drift_and_reference_overlap(self) -> None:
        timeline = Timeline(
            segments=(
                TranscriptSegment(
                    "agent-0",
                    "agent",
                    0,
                    1.0,
                    2.0,
                    "hello there",
                    words=(
                        WordTimestamp("hello", 1.1, 1.3),
                        WordTimestamp("there", 1.5, 1.8),
                    ),
                ),
                TranscriptSegment(
                    "customer-0",
                    "customer",
                    1,
                    1.7,
                    2.4,
                    "hello",
                    words=(WordTimestamp("hello", 1.8, 2.1),),
                ),
            ),
            overlap_pairs=(("agent-0", "customer-0"),),
        )
        reference = [
            {
                "index": 1,
                "speaker_role": "agent",
                "start_ms": 1000,
                "duration_ms": 1000,
                "human_transcript": "hello there",
                "word_offsets_ms": [100, 500],
            },
            {
                "index": 2,
                "speaker_role": "caller",
                "start_ms": 1700,
                "duration_ms": 700,
                "human_transcript": "hello",
                "word_offsets_ms": [100],
            },
        ]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "reference.json"
            path.write_text(json.dumps(reference), encoding="utf-8")
            result = ReferenceTranscriptValidator().validate(timeline, path)

        self.assertEqual(result["speaker_metrics"]["agent"]["wer"], 0.0)
        self.assertEqual(result["speaker_metrics"]["customer"]["wer"], 0.0)
        self.assertFalse(result["sample_axis_alignment"]["drift_detected"])
        self.assertFalse(result["asr_timestamp_drift_detected"])
        self.assertEqual(result["overlap_validation"]["expected_count"], 1)
        self.assertEqual(result["overlap_validation"]["detected_count"], 1)
        self.assertEqual(result["overall_status"], "pass")


if __name__ == "__main__":
    unittest.main()
