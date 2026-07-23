from __future__ import annotations

import unittest

import numpy as np

from stereo_pipeline.activity import EnergySpeechActivityDetector
from stereo_pipeline.models import ChannelAudio
from stereo_pipeline.timeline import TimelineMerger


class EnergySpeechActivityDetectorTests(unittest.TestCase):
    def test_detects_cross_channel_overlap_from_audio_not_transcript_span(self) -> None:
        sample_rate = 16_000
        left = np.zeros(sample_rate * 3, dtype=np.float32)
        right = np.zeros(sample_rate * 3, dtype=np.float32)
        t = np.arange(sample_rate, dtype=np.float32) / sample_rate
        left[sample_rate // 2 : sample_rate + sample_rate // 2] = (
            0.2 * np.sin(2 * np.pi * 440 * t)
        )
        right[sample_rate : sample_rate * 2] = (
            0.2 * np.sin(2 * np.pi * 660 * t)
        )
        detector = EnergySpeechActivityDetector()
        activity = detector.detect(
            ChannelAudio(0, "agent", left, sample_rate)
        ) + detector.detect(ChannelAudio(1, "customer", right, sample_rate))
        timeline = TimelineMerger.merge([], activity)
        self.assertEqual(len(timeline.overlap_intervals), 1)
        self.assertGreater(timeline.overlap_intervals[0]["duration_seconds"], 0.4)


if __name__ == "__main__":
    unittest.main()
