#!/usr/bin/env python3
"""CLI entry point: `kinetix demo.ktx [--preview XX-YY] [--live] [--no-subtitles]`."""

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from kinetix.main import compile_ktx, live_mode


def _parse_time(raw: str) -> float:
    m = re.match(r"(\d{1,2}):(\d{2})", raw)
    if m:
        return int(m.group(1)) * 60 + int(m.group(2))
    return float(raw)


def _parse_range(raw: str) -> tuple[float, float]:
    parts = raw.split("-")
    if len(parts) != 2:
        raise argparse.ArgumentTypeError(f"invalid range: {raw} (use START-END)")
    return (_parse_time(parts[0].strip()), _parse_time(parts[1].strip()))


def main():
    parser = argparse.ArgumentParser(
        prog="kinetix",
        description="KinetiX Pro — declarative video compilation engine (.ktx → .mp4)",
    )
    parser.add_argument("input", help="path to .ktx file")
    parser.add_argument("output", nargs="?", default=None,
                        help="output .mp4 path (default: <input>.mp4)")
    parser.add_argument("--preview", type=str, default=None, metavar="START-END",
                        help="render only a time slice, e.g. --preview 00:30-01:00")
    parser.add_argument("--live", action="store_true",
                        help="open ffplay preview window instead of encoding to file")
    parser.add_argument("--no-subtitles", action="store_true",
                        help="skip SRT subtitle rendering")
    args = parser.parse_args()

    preview = None
    if args.preview:
        preview = _parse_range(args.preview)

    if args.live:
        live_mode(args.input, no_subtitles=args.no_subtitles)
    else:
        compile_ktx(args.input, args.output, preview_range=preview, no_subtitles=args.no_subtitles)


if __name__ == "__main__":
    main()
