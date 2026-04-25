#!/usr/bin/env python3
"""Run the full ingest pipeline on a local PDF for debugging.

Usage:
    uv run python scripts/pipeline_local.py path/to/paper.pdf
"""

import sys


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: python scripts/pipeline_local.py <path_to_pdf>")
        sys.exit(1)

    pdf_path = sys.argv[1]
    print(f"TODO: Process {pdf_path}")
    # TODO: Implement local pipeline runner


if __name__ == "__main__":
    main()
