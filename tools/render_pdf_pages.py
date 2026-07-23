"""Render every PDF page to a PNG for visual QA."""

from __future__ import annotations

import argparse
from pathlib import Path

import fitz


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("pdf")
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()
    output = Path(args.output_dir)
    output.mkdir(parents=True, exist_ok=True)
    document = fitz.open(args.pdf)
    for index, page in enumerate(document):
        pixmap = page.get_pixmap(matrix=fitz.Matrix(1.6, 1.6), alpha=False)
        pixmap.save(output / f"page-{index + 1}.png")
    print(f"{len(document)} page")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
