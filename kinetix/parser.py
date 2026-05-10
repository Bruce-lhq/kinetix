"""Parser for .ktx files.

Grammar overview:
  [id]: path (dur: Ns)                     -- asset declaration
  [id]: text("content", font: kaiti)       -- text card asset
  [id] @ time | key: val ...               -- timeline placement
  [id]:\n    prop: {time: val, ...}        -- keyframe animation
  Format: mp4, Res: 1080p, FPS: 30         -- output config
"""

from __future__ import annotations

import re
from pathlib import Path

from .ast_nodes import Asset, AssetType, KeyframeTrack, KinetiXDocument, OutputConfig, TimelineEntry

# ---------------------------------------------------------------------------
# Regex patterns
# ---------------------------------------------------------------------------

# [v1]: assets/video.mp4 (dur: 10s)
# Also handles paths with spaces: 音频/新录音 16.m4a
RE_ASSET = re.compile(
    r'^\[(?P<id>\w+)\]\s*:\s*(?P<path>.+?)'
    r'(?:\s+\(dur:\s*(?P<dur>\d+(?:\.\d+)?)s\))?\s*$'
)

# [id]: text("content", font: kaiti, size: 48)
RE_TEXT_ASSET = re.compile(
    r'^\[(?P<id>\w+)\]\s*:\s*text\(["\'](?P<content>.+?)["\']'
    r'(?:\s*,\s*font:\s*(?P<font>\w+))?'
    r'(?:\s*,\s*size:\s*(?P<size>\d+))?'
    r'\)\s*$'
)

# [v1] @ 00:00 | layer: 0 ...
RE_TIMELINE = re.compile(
    r'^\[(?P<id>\w+)\]\s*@\s*(?P<time>\S+)'
    r'\s*\|\s*(?P<props>.+)$'
)

# Keyframe block header: [img1]:
RE_KF_HEADER = re.compile(r'^\[(?P<id>\w+)\]\s*:\s*$')

# Keyframe line: scale: { 0s: 0.5, 5s: 1.2 }
RE_KF_LINE = re.compile(
    r'^\s+(?P<prop>\w+)\s*:\s*\{(?P<frames>.+)\}\s*$'
)

# Single keyframe pair: 0s: 0.5
RE_KF_PAIR = re.compile(r'(\d+(?:\.\d+)?)s\s*:\s*([^,}\s]+)')

# Output line: Format: mp4, Res: 1080p, FPS: 30
RE_OUTPUT = re.compile(r'^Format:\s*(\w+),\s*Res:\s*(\S+),\s*FPS:\s*(\d+)$')

# Time helpers
RE_TIME_ABS = re.compile(r'^(\d{1,2}):(\d{2})$')
RE_TIME_OFFSET = re.compile(r'^(\+?)(\d+(?:\.\d+)?)s$')


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def parse(source: str) -> KinetiXDocument:
    """Parse a .ktx source string into a KinetiXDocument AST."""
    doc = KinetiXDocument()
    lines = source.splitlines()

    i = 0
    pending_keyframe_id: str | None = None

    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        # skip blanks / comments
        if not stripped or stripped.startswith('#'):
            i += 1
            continue

        # --- Output config ---
        m = RE_OUTPUT.match(stripped)
        if m:
            doc.output = OutputConfig(format=m.group(1), resolution=m.group(2), fps=int(m.group(3)))
            i += 1
            continue

        # --- Text asset ---
        m = RE_TEXT_ASSET.match(stripped)
        if m:
            asset = _parse_text_asset(m)
            doc.assets[asset.id] = asset
            i += 1
            continue

        # --- Asset declaration ---
        m = RE_ASSET.match(stripped)
        if m:
            asset = _parse_asset(m)
            doc.assets[asset.id] = asset
            i += 1
            continue

        # --- Keyframe block header ---
        m = RE_KF_HEADER.match(stripped)
        if m:
            pending_keyframe_id = m.group('id')
            i += 1
            continue

        # --- Keyframe line (indented) ---
        m = RE_KF_LINE.match(line)  # NOT stripped — need leading spaces
        if m and pending_keyframe_id:
            _attach_keyframes(doc, pending_keyframe_id, m.group('prop'), m.group('frames'))
            i += 1
            continue
        else:
            pending_keyframe_id = None

        # --- Timeline entry ---
        m = RE_TIMELINE.match(stripped)
        if m:
            entry = _parse_timeline(m, doc)
            doc.timeline.append(entry)
            i += 1
            continue

        # fallback — skip unknown
        i += 1

    return doc


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_ASSET_EXT: dict[str, AssetType] = {
    '.mp4': AssetType.VIDEO, '.avi': AssetType.VIDEO, '.mov': AssetType.VIDEO,
    '.mkv': AssetType.VIDEO,
    '.png': AssetType.IMAGE, '.jpg': AssetType.IMAGE, '.jpeg': AssetType.IMAGE,
    '.bmp': AssetType.IMAGE, '.gif': AssetType.IMAGE,
    '.mp3': AssetType.AUDIO, '.wav': AssetType.AUDIO, '.aac': AssetType.AUDIO,
    '.flac': AssetType.AUDIO, '.m4a': AssetType.AUDIO,
}


def _parse_asset(m: re.Match) -> Asset:
    id_ = m.group('id')
    path = m.group('path')
    dur = float(m.group('dur')) if m.group('dur') else None
    ext = Path(path).suffix.lower()
    atype = _ASSET_EXT.get(ext, AssetType.VIDEO)
    return Asset(id=id_, path=path, type=atype, duration=dur)


def _parse_text_asset(m: re.Match) -> Asset:
    id_ = m.group('id')
    content = m.group('content').replace('\\n', '\n')
    font = m.group('font') or 'default'
    size = int(m.group('size')) if m.group('size') else None
    return Asset(
        id=id_, path="__text__", type=AssetType.TEXT,
        text_content=content, text_font=font, text_font_size=size,
    )


def _parse_time(raw: str) -> float | str:
    raw = raw.strip()
    m = RE_TIME_ABS.match(raw)
    if m:
        return int(m.group(1)) * 60 + int(m.group(2))
    m = RE_TIME_OFFSET.match(raw)
    if m:
        return float(m.group(2))
    if raw == 'prev.end':
        return 'prev.end'
    try:
        return float(raw)
    except ValueError:
        return raw


def _parse_timeline(m: re.Match, doc: KinetiXDocument) -> TimelineEntry:
    asset_id = m.group('id')
    raw_time = str(_parse_time(m.group('time')))
    props_str = m.group('props')

    kv: dict[str, str] = {}
    for part in props_str.split('|'):
        part = part.strip()
        if ':' not in part:
            continue
        k, v = part.split(':', 1)
        kv[k.strip().lower()] = v.strip()

    layer = int(kv.get('layer', 0))
    duration = _parse_dur(kv.get('duration'))
    position = _parse_pos(kv.get('pos'))
    transition = kv.get('transition')
    transition_dur = _parse_dur(kv.get('transition_dur', '0s')) or 0.0
    fadein = _parse_dur(kv.get('fadein'))
    fadeout = _parse_dur(kv.get('fadeout'))
    volume = _parse_volume(kv.get('volume'))
    mute = kv.get('mute', '').strip().lower() in ('true', '1', 'yes')

    # Inline syntax: transition: "crossfade", dur: 1s
    if transition:
        transition = transition.strip('"\'')
        dur_m = re.search(r',\s*dur:\s*(\d+(?:\.\d+)?)s', transition)
        if dur_m:
            transition_dur = float(dur_m.group(1))
            transition = transition[:dur_m.start()].strip().strip('"\'')

    return TimelineEntry(
        asset_id=asset_id,
        start_time=raw_time,
        layer=layer,
        duration=duration,
        position=position,
        transition=transition,
        transition_dur=transition_dur,
        fadein=fadein,
        fadeout=fadeout,
        volume=volume,
    )


def _parse_dur(val: str | None) -> float | None:
    if val is None:
        return None
    val = val.strip().rstrip('s')
    try:
        return float(val)
    except ValueError:
        return None


def _parse_volume(val: str | None) -> float | None:
    if val is None:
        return None
    try:
        return float(val)
    except ValueError:
        return None


def _parse_pos(val: str | None) -> tuple[int, int] | None:
    if val is None:
        return None
    m = re.match(r'\(\s*(\d+)\s*,\s*(\d+)\s*\)', val)
    if m:
        return (int(m.group(1)), int(m.group(2)))
    return None


def _parse_kf_value(raw: str):
    raw = raw.strip().strip('"\'')
    m = re.match(r'\(\s*([\d.]+)\s*,\s*([\d.]+)\s*\)', raw)
    if m:
        return (float(m.group(1)), float(m.group(2)))
    try:
        return float(raw)
    except ValueError:
        return raw


def _attach_keyframes(doc: KinetiXDocument, asset_id: str, prop: str, frames_str: str):
    pairs = RE_KF_PAIR.findall(frames_str)
    kf_track = KeyframeTrack(
        property_name=prop,
        keyframes=[(float(t), _parse_kf_value(v)) for t, v in pairs],
    )
    for entry in doc.timeline:
        if entry.asset_id == asset_id:
            entry.keyframes.append(kf_track)
            return
    entry = TimelineEntry(asset_id=asset_id, start_time=0, keyframes=[kf_track])
    doc.timeline.append(entry)
