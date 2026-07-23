"""Synthetic stereo fixture generation with a known shared time axis."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import soundfile as sf


def generate_fixture(path: str | Path, sample_rate: int = 16_000) -> Path:
    duration = 3.0
    samples = int(duration * sample_rate)
    time_axis = np.arange(samples, dtype=np.float64) / sample_rate
    left = np.zeros(samples, dtype=np.float32)
    right = np.zeros(samples, dtype=np.float32)

    left_active = (time_axis >= 0.5) & (time_axis < 1.5)
    right_active = (time_axis >= 1.2) & (time_axis < 2.3)
    left[left_active] = 0.25 * np.sin(2 * np.pi * 440 * time_axis[left_active])
    right[right_active] = 0.20 * np.sin(2 * np.pi * 660 * time_axis[right_active])

    stereo = np.column_stack((left, right))
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    sf.write(output, stereo, sample_rate, subtype="PCM_16")
    return output
