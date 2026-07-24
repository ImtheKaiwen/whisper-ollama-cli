"""Simple executable entry point for offline stereo call analysis."""

from __future__ import annotations

import argparse

from dotenv import load_dotenv

from StereoPipeline import (
    QueueOptions,
    StereoPipeline,
    build_queue_publisher_from_env,
)


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
    load_dotenv()
    args = build_parser().parse_args()
    queue_options = QueueOptions.from_env()
    pipeline = StereoPipeline(
        queue_options=queue_options,
        queue_publisher=build_queue_publisher_from_env(queue_options),
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
