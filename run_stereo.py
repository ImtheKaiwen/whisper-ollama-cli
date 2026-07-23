"""Simple executable entry point for offline stereo call analysis."""

from __future__ import annotations

import argparse

from StereoPipeline import QueueOptions, StereoPipeline


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Stereo ses dosyasını Whisper ve Ollama ile analiz eder."
    )
    parser.add_argument(
        "audio_path",
        nargs="?",
        default="gorusme.wav",
        help="Stereo WAV yolu (varsayılan: gorusme.wav)",
    )
    parser.add_argument(
        "--output-dir",
        default=None,
        help="İsteğe bağlı çıktı klasörü",
    )
    parser.add_argument(
        "--reference-json",
        default=None,
        help="İsteğe bağlı insan etiketli referans JSON yolu",
    )
    parser.add_argument(
        "--language",
        default=None,
        help="Whisper dili (tr, en veya otomatik algılama için auto)",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    pipeline = StereoPipeline(
        queue_options=QueueOptions(
            whisper_enabled=False,
            analysis_enabled=False,
        ),
        language=args.language,
    )
    pipeline.analyze(
        args.audio_path,
        output_dir=args.output_dir,
        reference_path=args.reference_json,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
