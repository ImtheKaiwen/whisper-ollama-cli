from __future__ import annotations

import unittest

from stereo_pipeline.models import TranscriptSegment
from stereo_pipeline.timeline import TimelineMerger


class TimelineMergerTests(unittest.TestCase):
    def test_stable_merge_preserves_overlap_and_speaker_labels(self) -> None:
        agent = TranscriptSegment(
            "agent-0", "agent", 0, 1.0, 2.0, "Merhaba"
        )
        customer = TranscriptSegment(
            "customer-0", "customer", 1, 1.5, 2.5, "Merhaba"
        )
        later = TranscriptSegment(
            "agent-1", "agent", 0, 3.0, 4.0, "Devam"
        )

        timeline = TimelineMerger.merge([[later, agent], [customer]])

        self.assertEqual(
            [item.segment_id for item in timeline.segments],
            ["agent-0", "customer-0", "agent-1"],
        )
        self.assertEqual(timeline.overlap_pairs, (("agent-0", "customer-0"),))
        self.assertEqual(timeline.segments[1].speaker, "customer")


if __name__ == "__main__":
    unittest.main()
