from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from stereo_pipeline.audio import StereoAudioProcessor
from stereo_pipeline.pipeline import StereoProcessingPipeline
from stereo_pipeline.reporting import ResultReporter
from tests.fakes import DeterministicTranscriber, EvidenceAnalyzer
from tests.fixture_factory import generate_fixture


class StereoProcessingPipelineTests(unittest.TestCase):
    def test_end_to_end_pipeline_is_traceable_and_analysis_gets_timeline(self) -> None:
        analyzer = EvidenceAnalyzer()
        pipeline = StereoProcessingPipeline(
            StereoAudioProcessor(),
            DeterministicTranscriber(),
            analyzer,
        )
        with tempfile.TemporaryDirectory() as directory:
            fixture = generate_fixture(Path(directory) / "fixture.wav")
            result = pipeline.run(fixture)
            json_path = ResultReporter.write_json(
                result, Path(directory) / "result.json"
            )
            report_path = ResultReporter.write_markdown(
                result, Path(directory) / "report.md"
            )
            parsed = json.loads(json_path.read_text(encoding="utf-8"))
            report = report_path.read_text(encoding="utf-8")

        self.assertIsNotNone(analyzer.received)
        self.assertEqual(len(result.timeline.segments), 2)
        self.assertEqual(len(result.timeline.overlap_pairs), 1)
        self.assertEqual(result.analysis["evidence_segment_ids"], ("customer-0000",))
        self.assertEqual(
            [item["stage"] for item in result.trace],
            [
                "audio.load_and_split",
                "audio.quality",
                "audio.speech_activity",
                "asr.transcribe",
                "asr.transcribe",
                "timeline.merge",
                "analysis.run",
            ],
        )
        self.assertEqual(parsed["timeline"]["segments"][0]["speaker"], "agent")
        self.assertIn("[0.500-1.500] agent:", result.full_transcript)
        self.assertEqual(
            [item["event"] for item in result.audit_log],
            [
                "stereo.input.validated",
                "channel.transcribed",
                "channel.transcribed",
                "timeline.concatenated_by_timestamp",
                "analysis.request",
                "analysis.response",
                "validation.completed",
            ],
        )
        self.assertEqual(
            result.audit_log[1]["logical_source"].split("#")[-1],
            "channel=0",
        )
        self.assertEqual(
            result.audit_log[2]["logical_source"].split("#")[-1],
            "channel=1",
        )
        self.assertIn("customer", report)


if __name__ == "__main__":
    unittest.main()
