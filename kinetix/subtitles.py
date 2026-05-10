"""SRT subtitle parser and renderer."""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass
class Subtitle:
    index: int
    start: float  # seconds
    end: float    # seconds
    text: str


def parse_srt(path: str) -> list[Subtitle]:
    """Parse an .srt file into a list of Subtitle objects."""
    with open(path, encoding="utf-8") as f:
        content = f.read()
    blocks = re.split(r"\n\s*\n", content.strip())
    subs = []
    for block in blocks:
        lines = block.strip().splitlines()
        if len(lines) < 3:
            continue
        try:
            idx = int(lines[0].strip())
        except ValueError:
            continue
        m = re.match(
            r"(\d{2}):(\d{2}):(\d{2})[,.](\d{3})"
            r"\s*-->\s*"
            r"(\d{2}):(\d{2}):(\d{2})[,.](\d{3})",
            lines[1].strip(),
        )
        if not m:
            continue
        start = _ts(m.group(1), m.group(2), m.group(3), m.group(4))
        end = _ts(m.group(5), m.group(6), m.group(7), m.group(8))
        text = "\n".join(lines[2:]).strip()
        subs.append(Subtitle(index=idx, start=start, end=end, text=text))
    return subs


def _ts(h, m, s, ms):
    return int(h) * 3600 + int(m) * 60 + int(s) + int(ms) / 1000.0
