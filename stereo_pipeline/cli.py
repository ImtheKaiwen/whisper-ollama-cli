"""Command-line entry point for offline stereo processing."""

from __future__ import annotations

import argparse
import os
from pathlib import Path

from dotenv import load_dotenv

from .analysis import OllamaConversationAnalyzer
from .audio import StereoAudioProcessor
from .pipeline import StereoProcessingPipeline
from .reporting import ResultReporter
from .transcription import FasterWhisperTranscriber


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Stereo WAV -> timeline -> analiz")
    parser.add_argument("input", help="Sol=agent, sağ=customer stereo ses dosyası")
    parser.add_argument("--output-dir", default="artifacts/stereo_run")
    parser.add_argument("--left-speaker", default="agent")
    parser.add_argument("--right-speaker", default="customer")
    parser.add_argument(
        "--reference-json",
        help="İnsan transkripti/zamanlarıyla WER ve drift doğrulaması",
    )
    parser.add_argument(
        "--language",
        default=None,
        help="Whisper dili (ör. tr, en); otomatik algılama için auto",
    )
    return parser


def main() -> int:
    load_dotenv()
    args = build_parser().parse_args()
    processor = StereoAudioProcessor(
        channel_map={0: args.left_speaker, 1: args.right_speaker}
    )
    configured_language = (
        args.language
        if args.language is not None
        else os.getenv("WHISPER_LANGUAGE", "tr")
    )
    transcriber = FasterWhisperTranscriber(
        model_name=os.getenv("WHISPER_MODEL", "tiny"),
        device=os.getenv("WHISPER_DEVICE", "cpu"),
        compute_type=os.getenv("WHISPER_COMPUTE_TYPE", "int8"),
        language=None if configured_language.lower() == "auto" else configured_language,
    )
    analyzer = OllamaConversationAnalyzer(
        url=os.getenv("OLLAMA_URL", "http://127.0.0.1:11434"),
        model=os.getenv("OLLAMA_MODEL", "gemma2:2b"),
        timeout_seconds=float(os.getenv("OLLAMA_TIMEOUT_SECONDS", "60")),
    )
    result = StereoProcessingPipeline(processor, transcriber, analyzer).run(
        args.input,
        reference_path=args.reference_json,
    )
    output_dir = Path(args.output_dir)
    ResultReporter.write_json(result, output_dir / "result.json")
    ResultReporter.write_audit_json(result, output_dir / "audit.json")
    ResultReporter.write_markdown(result, output_dir / "report.md")
    print(f"Tamamlandı: {output_dir.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
