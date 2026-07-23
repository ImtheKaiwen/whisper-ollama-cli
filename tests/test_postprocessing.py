from __future__ import annotations

import unittest

from stereo_pipeline.models import TranscriptSegment, WordTimestamp
from stereo_pipeline.postprocessing import TranscriptSegmentSplitter


class TranscriptSegmentSplitterTests(unittest.TestCase):
    def test_splits_long_segment_on_word_silence_without_reference_text(self) -> None:
        segment = TranscriptSegment(
            "customer-0",
            "customer",
            1,
            1.0,
            5.2,
            "hello yes bye",
            words=(
                WordTimestamp("hello", 1.0, 1.3),
                WordTimestamp("yes", 3.0, 3.2),
                WordTimestamp("bye", 5.0, 5.2),
            ),
        )
        result = TranscriptSegmentSplitter(max_word_gap_seconds=0.8).split([segment])
        self.assertEqual([item.text for item in result], ["hello", "yes", "bye"])
        self.assertEqual(
            [item.segment_id for item in result],
            ["customer-0-u000", "customer-0-u001", "customer-0-u002"],
        )


if __name__ == "__main__":
    unittest.main()
