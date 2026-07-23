from __future__ import annotations

import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path

from StereoPipeline import StereoPipeline as CompatibilityStereoPipeline
from stereo_pipeline import StereoPipeline
from stereo_pipeline.queueing import InMemoryQueuePublisher, QueueOptions
from tests.fakes import DeterministicTranscriber, EvidenceAnalyzer
from tests.fixture_factory import generate_fixture


class StereoPipelineFacadeTests(unittest.TestCase):
    def test_minimal_analyze_runs_every_stage_and_writes_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = generate_fixture(root / "voice.wav")
            output = root / "run"
            pipeline = StereoPipeline(
                transcriber=DeterministicTranscriber(),
                analyzer=EvidenceAnalyzer(),
                output_dir=output,
            )

            printed = StringIO()
            with redirect_stdout(printed):
                result = pipeline.analyze(source)

            self.assertIn("Stereo Görüşme Analizi", printed.getvalue())
            self.assertIn("topic: bütçe", printed.getvalue())
            self.assertEqual(
                [item["event"] for item in result.audit_log],
                [
                    "stereo.input.validated",
                    "channel.transcribed",
                    "channel.transcribed",
                    "timeline.concatenated_by_timestamp",
                    "analysis.queue",
                    "analysis.request",
                    "analysis.response",
                    "validation.completed",
                ],
            )
            self.assertEqual(result.analysis["topic"], "bütçe")
            run_output = output / source.stem
            self.assertTrue((run_output / "result.json").is_file())
            self.assertTrue((run_output / "audit.json").is_file())
            self.assertTrue((run_output / "report.md").is_file())
            self.assertTrue((run_output / "pipeline.log").is_file())
            self.assertFalse((run_output / "queue_payloads").exists())

    def test_public_steps_can_be_used_independently(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            source = generate_fixture(Path(directory) / "voice.wav")
            pipeline = StereoPipeline(
                transcriber=DeterministicTranscriber(),
                analyzer=EvidenceAnalyzer(),
            )

            channels = pipeline.split_channels(source)
            quality = pipeline.measure_channel_quality(channels)
            activity = pipeline.detect_speech_activity(channels)
            agent_segments = pipeline.transcribe_channel(channels[0])
            customer_segments = pipeline.transcribe_channel(channels[1])
            timeline = pipeline.merge_transcripts(
                {
                    "agent": tuple(agent_segments),
                    "customer": tuple(customer_segments),
                },
                activity,
            )
            transcript = pipeline.build_full_transcript(timeline)
            analysis = pipeline.send_to_analysis(timeline)

            self.assertEqual(len(channels), 2)
            self.assertEqual(len(quality), 2)
            self.assertTrue(activity)
            self.assertIn("agent:", transcript)
            self.assertIn("customer:", transcript)
            self.assertEqual(analysis.topic, "bütçe")

    def test_optional_queue_hooks_publish_only_when_enabled(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = generate_fixture(root / "voice.wav")
            publisher = InMemoryQueuePublisher()
            pipeline = CompatibilityStereoPipeline(
                transcriber=DeterministicTranscriber(),
                analyzer=EvidenceAnalyzer(),
                queue_options=QueueOptions(
                    whisper_enabled=True,
                    analysis_enabled=True,
                ),
                queue_publisher=publisher,
                output_dir=root / "run",
            )

            with redirect_stdout(StringIO()):
                pipeline.analyze(source)

            self.assertEqual(
                [queue for queue, _ in publisher.messages],
                ["stereo.whisper", "stereo.whisper", "stereo.analysis"],
            )
            whisper_payloads = [
                payload
                for queue, payload in publisher.messages
                if queue == "stereo.whisper"
            ]
            self.assertEqual(
                [payload["channel_id"] for payload in whisper_payloads],
                [0, 1],
            )
            self.assertTrue(
                all(Path(payload["audio_path"]).is_file() for payload in whisper_payloads)
            )
            analysis_payload = publisher.messages[-1][1]
            self.assertIn("full_transcript", analysis_payload)
            self.assertEqual(len(analysis_payload["timeline"]), 2)


if __name__ == "__main__":
    unittest.main()
