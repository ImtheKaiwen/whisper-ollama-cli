from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import numpy as np
import soundfile as sf

from stereo_pipeline.audio import StereoAudioError, StereoAudioProcessor
from tests.fixture_factory import generate_fixture


class StereoAudioProcessorTests(unittest.TestCase):
    def test_split_preserves_channel_identity_length_and_alignment(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            fixture = generate_fixture(Path(directory) / "fixture.wav")
            left, right = StereoAudioProcessor().load(fixture)

        self.assertEqual(left.speaker, "agent")
        self.assertEqual(right.speaker, "customer")
        self.assertEqual(len(left.samples), 48_000)
        self.assertEqual(len(left.samples), len(right.samples))
        self.assertLess(np.max(np.abs(left.samples[:8_000])), 1e-6)
        self.assertGreater(np.max(np.abs(left.samples[8_000:24_000])), 0.2)
        self.assertLess(np.max(np.abs(right.samples[:19_200])), 1e-6)
        self.assertGreater(np.max(np.abs(right.samples[19_200:36_800])), 0.15)

    def test_resample_keeps_both_channels_at_equal_duration(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            fixture = generate_fixture(Path(directory) / "fixture.wav", sample_rate=48_000)
            left, right = StereoAudioProcessor().load(fixture)

        self.assertEqual(left.sample_rate, 16_000)
        self.assertEqual(len(left.samples), 48_000)
        self.assertEqual(len(left.samples), len(right.samples))

    def test_rejects_mono_input(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "mono.wav"
            sf.write(path, np.zeros(16_000, dtype=np.float32), 16_000)
            with self.assertRaises(StereoAudioError):
                StereoAudioProcessor().load(path)

    def test_quality_and_correlation_are_channel_specific(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            fixture = generate_fixture(Path(directory) / "fixture.wav")
            left, right = StereoAudioProcessor().load(fixture)
            left_quality = StereoAudioProcessor.quality(left)
            right_quality = StereoAudioProcessor.quality(right)
            correlation = StereoAudioProcessor.channel_correlation(left, right)

        self.assertGreater(left_quality.rms_dbfs, right_quality.rms_dbfs)
        self.assertAlmostEqual(correlation, 0.0, places=3)


if __name__ == "__main__":
    unittest.main()
