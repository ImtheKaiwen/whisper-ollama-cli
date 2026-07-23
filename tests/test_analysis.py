from __future__ import annotations

import json
import unittest
from unittest.mock import patch

from stereo_pipeline.analysis import OllamaConversationAnalyzer
from stereo_pipeline.models import Timeline, TranscriptSegment


class _FakeResponse:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def read(self) -> bytes:
        analysis = {
            "emotion": "neutral",
            "need": "card replacement",
            "topic": "card",
            "intent": "request",
            "objection_type": "",
            "conversation_stage": "closing",
            "recommended_action": "replace card",
            "confidence": 0.9,
            "evidence_segment_ids": ["customer-0000", "invented-9999"],
        }
        envelope = {"message": {"content": json.dumps(analysis)}}
        return json.dumps(envelope).encode("utf-8")


def _timeline() -> Timeline:
    return Timeline(
        segments=(
            TranscriptSegment(
                segment_id="customer-0000",
                speaker="customer",
                channel_id=1,
                start_seconds=1.0,
                end_seconds=2.0,
                text="I need a new card.",
            ),
        ),
        overlap_pairs=(),
    )


class OllamaConversationAnalyzerTests(unittest.TestCase):
    @patch("stereo_pipeline.analysis.urllib.request.urlopen")
    def test_lenient_mode_discards_hallucinated_evidence_ids(self, urlopen) -> None:
        urlopen.return_value = _FakeResponse()
        analyzer = OllamaConversationAnalyzer(strict_evidence_ids=False)

        result = analyzer.analyze(_timeline())

        self.assertEqual(result.evidence_segment_ids, ("customer-0000",))
        self.assertEqual(analyzer.last_invalid_evidence_ids, ("invented-9999",))

    @patch("stereo_pipeline.analysis.urllib.request.urlopen")
    def test_strict_mode_still_rejects_invalid_evidence_ids(self, urlopen) -> None:
        urlopen.return_value = _FakeResponse()
        analyzer = OllamaConversationAnalyzer(strict_evidence_ids=True)

        with self.assertRaisesRegex(ValueError, "timeline dışında"):
            analyzer.analyze(_timeline())


if __name__ == "__main__":
    unittest.main()
