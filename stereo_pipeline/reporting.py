"""Machine-readable and human-readable pipeline result writers."""

from __future__ import annotations

import json
from pathlib import Path

from .models import ProcessingResult


class ResultReporter:
    @staticmethod
    def write_json(result: ProcessingResult, path: str | Path) -> Path:
        output = Path(path)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(
            json.dumps(result.to_dict(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return output

    @staticmethod
    def write_audit_json(result: ProcessingResult, path: str | Path) -> Path:
        """Write the ordered processing proof requested for offline acceptance."""
        output = Path(path)
        output.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "schema_version": 1,
            "source_path": result.source_path,
            "pipeline": (
                "stereo -> channel_0 -> channel_1 -> timestamp_merge -> "
                "full_transcript -> ollama -> analysis -> validation"
            ),
            "events": list(result.audit_log),
            "final": {
                "channel_transcripts": {
                    speaker: " ".join(segment.text for segment in segments)
                    for speaker, segments in result.channel_transcripts.items()
                },
                "full_transcript": result.full_transcript,
                "analysis_result": result.analysis,
                "validation": result.validation,
            },
        }
        output.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return output

    @staticmethod
    def write_markdown(result: ProcessingResult, path: str | Path) -> Path:
        output = Path(path)
        output.parent.mkdir(parents=True, exist_ok=True)
        lines = [
            "# Stereo İşleme Raporu",
            "",
            f"- Kaynak: `{result.source_path}`",
            f"- Süre: {result.duration_seconds:.3f} sn",
            f"- Örnekleme: {result.sample_rate} Hz",
            f"- Segment: {len(result.timeline.segments)}",
            f"- Çakışma: {len(result.timeline.overlap_pairs)}",
            "",
            "## Kanal Kalitesi",
            "",
        ]
        for quality in result.quality:
            lines.append(
                f"- {quality.speaker}: RMS {quality.rms_dbfs:.2f} dBFS, "
                f"clipping %{quality.clipping_ratio * 100:.3f}, "
                f"sessizlik %{quality.silence_ratio * 100:.2f}"
            )
        lines.extend(["", "## Ortak Timeline", ""])
        for segment in result.timeline.segments:
            lines.append(
                f"- {segment.start_seconds:.3f}–{segment.end_seconds:.3f} "
                f"**{segment.speaker}**: {segment.text} (`{segment.segment_id}`)"
            )
        lines.extend(["", "## Analiz", ""])
        for key, value in result.analysis.items():
            lines.append(f"- **{key}:** {value}")
        lines.extend(["", "## Doğrulama", ""])
        lines.append(
            "```json\n"
            + json.dumps(result.validation, ensure_ascii=False, indent=2)
            + "\n```"
        )
        lines.extend(["", "## Aşama İzleri", ""])
        for item in result.trace:
            lines.append(
                f"- `{item['stage']}` — {item['elapsed_ms']} ms — "
                f"`{json.dumps(item, ensure_ascii=False)}`"
            )
        output.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return output
