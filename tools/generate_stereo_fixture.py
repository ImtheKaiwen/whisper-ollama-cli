"""Create the deterministic L=agent/R=customer timing fixture used in tests."""

from __future__ import annotations

import argparse

from tests.fixture_factory import generate_fixture


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        default="tests/fixtures/synthetic_overlap.wav",
    )
    args = parser.parse_args()
    output = generate_fixture(args.output)
    print(output.resolve())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
