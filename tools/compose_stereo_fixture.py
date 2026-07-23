"""Place two mono WAV files on a shared stereo timeline without time compression."""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import soundfile as sf
import soxr


def load_mono(path: str, target_rate: int) -> np.ndarray:
    audio, source_rate = sf.read(path, dtype="float32", always_2d=True)
    mono = np.mean(audio, axis=1, dtype=np.float32)
    if source_rate != target_rate:
        mono = soxr.resample(mono, source_rate, target_rate, quality="HQ")
    return np.asarray(mono, dtype=np.float32)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--left", required=True)
    parser.add_argument("--right", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--left-offset", type=float, default=0.5)
    parser.add_argument("--right-offset", type=float, default=1.5)
    parser.add_argument("--sample-rate", type=int, default=16_000)
    args = parser.parse_args()

    left = load_mono(args.left, args.sample_rate)
    right = load_mono(args.right, args.sample_rate)
    left_start = round(args.left_offset * args.sample_rate)
    right_start = round(args.right_offset * args.sample_rate)
    length = max(left_start + len(left), right_start + len(right))
    stereo = np.zeros((length, 2), dtype=np.float32)
    stereo[left_start : left_start + len(left), 0] = left
    stereo[right_start : right_start + len(right), 1] = right

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    sf.write(output, stereo, args.sample_rate, subtype="PCM_16")
    print(output.resolve())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
