"""Parser for .ktx files — KinetiX Pro.

Grammar:
  [id]: path (dur: Ns)                                  -- asset
  [id]: text("content", font: kaiti)                    -- text card
  Define Style("name"):\n  key: val ...                 -- style block
  [id] @ time | key: val ...                            -- timeline entry
  [id]:\n    prop: {t: v, ..., curve: "ease_in"}        -- keyframe
  Subtitles: path.srt                                    -- external subtitles
  Format: mp4, Res: 1080p, FPS: 30                       -- output
"""

from __future__ import annotations

import re
from pathlib import Path

from .ast_nodes import (
    Asset, AssetType, KeyframeTrack, KinetiXDocument,
    OutputConfig, Style, TimelineEntry,
)

# ---------------------------------------------------------------------------
# Regex patterns
# ---------------------------------------------------------------------------

# [v1]: path/to/file.mp4 (dur: 10s) [foo, bar]
RE_ASSET = re.compile(
    r'^\[(?P<id>\w+)\]\s*:\s*(?P<path>.+?)'
    r'(?:\s+\(dur:\s*(?P<dur>\d+(?:\.\d+)?)s\))?'
    r'(?:\s+\[(?P<tags>.*?)\])?\s*$'
)

# [id]: text("content", font: kaiti, size: 48)
RE_TEXT_ASSET = re.compile(
    r'^\[(?P<id>\w+)\]\s*:\s*text\(["\'](?P<content>.+?)["\']'
    r'(?:\s*,\s*font:\s*(?P<font>\w+))?'
    r'(?:\s*,\s*size:\s*(?P<size>\d+))?'
    r'(?:\s*,\s*bg:\s*"(?P<bg>[^"]+)")?'
    r'(?:\s*,\s*color:\s*"(?P<color>[^"]+)")?'
    r'(?:\s*,\s*bg_opacity:\s*(?P<bg_opacity>[\d.]+))?'
    r'\)\s*$'
)

# Define Style("name"):
RE_STYLE_START = re.compile(r'^Define\s+Style\(\s*"([^"]+)"\s*\)\s*:\s*$')

# Indented property inside style/keyframe block
RE_PROP = re.compile(r'^\s+(?P<key>\w+)\s*:\s*(?P<val>.+)$')

# [v1] @ time | props ...
# time supports: 00:00, prev.end, v1.end - 1s, v1.start + 2s
RE_TIMELINE = re.compile(
    r'^\[(?P<id>\w+)\]\s*@\s*(?P<time>.+?)\s*\|\s*(?P<props>.+)$'
)

# Keyframe block header: [img1]:
RE_KF_HEADER = re.compile(r'^\[(?P<id>\w+)\]\s*:\s*$')

# Keyframe line: scale: { 0s: 0.5, 5s: 1.2, curve: "ease_in" }
RE_KF_LINE = re.compile(
    r'^\s+(?P<prop>\w+)\s*:\s*\{(?P<frames>.+)\}\s*$'
)

# Keyframe value pair or curve spec: 0s: 0.5  /  curve: "ease_in"
RE_KF_PAIR = re.compile(r'(\d+(?:\.\d+)?)s\s*:\s*([^,}\s]+)')
RE_KF_CURVE = re.compile(r'curve\s*:\s*"(\w+)"')

# Output: Format: mp4, Res: 1080p, FPS: 30
RE_OUTPUT = re.compile(r'^Format:\s*(\w+),\s*Res:\s*(\S+),\s*FPS:\s*(\d+)$')

# Subtitles: path
RE_SUBTITLES = re.compile(r'^Subtitles:\s*(.+)$')

# Time helpers
RE_TIME_ABS = re.compile(r'^(\d{1,2}):(\d{2})$')
RE_TIME_OFFSET = re.compile(r'^(\+?)(\d+(?:\.\d+)?)s$')

# Expression time: v1.end - 1s  /  v1.start + 2s  /  v1.end
RE_EXPR = re.compile(
    r'^(\w+)\.(start|end)\s*(?:([+-])\s*(\d+(?:\.\d+)?)s)?$'
)


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

        if not stripped or stripped.startswith('#'):
            i += 1
            continue

        # --- Define Style block ---
        sm = RE_STYLE_START.match(stripped)
        if sm:
            style = _parse_style_block(lines, i)
            doc.styles[style.name] = style
            i += style._block_lines  # type: ignore[attr-defined]
            continue

        # --- Output config ---
        m = RE_OUTPUT.match(stripped)
        if m:
            doc.output = OutputConfig(format=m.group(1), resolution=m.group(2), fps=int(m.group(3)))
            i += 1
            continue

        # --- Subtitles ---
        m = RE_SUBTITLES.match(stripped)
        if m:
            doc.subtitle_path = m.group(1).strip()
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
        m = RE_KF_LINE.match(line)
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

        i += 1

    return doc


# ---------------------------------------------------------------------------
# Style block
# ---------------------------------------------------------------------------

def _parse_style_block(lines: list[str], start_i: int) -> Style:
    """Parse a Define Style(...) block. Returns a Style with _block_lines."""
    m = RE_STYLE_START.match(lines[start_i].strip())
    assert m
    name = m.group(1)
    style = Style(name=name)
    i = start_i + 1
    while i < len(lines):
        stripped = lines[i].strip()
        if not stripped or stripped.startswith('#'):
            i += 1
            continue
        pm = RE_PROP.match(lines[i])  # must be indented
        if not pm:
            break
        k, v = pm.group('key').strip(), pm.group('val').strip()
        _apply_style_prop(style, k, v)
        i += 1
    style._block_lines = i - start_i  # type: ignore[attr-defined]
    return style


def _apply_style_prop(style: Style, key: str, val: str):
    if key == 'fadein':         style.fadein = _parse_dur(val)
    elif key == 'fadeout':      style.fadeout = _parse_dur(val)
    elif key == 'transition':
        trans = val.strip('"\'')
        dur_m = re.search(r',\s*dur:\s*(\d+(?:\.\d+)?)s', trans)
        if dur_m:
            style.transition_dur = float(dur_m.group(1))
            trans = trans[:dur_m.start()].strip().strip('"\'')
        style.transition = trans
    elif key == 'volume':       style.volume = _parse_dur(val)
    elif key == 'mute':         style.mute = val.strip().lower() in ('true', '1', 'yes')
    elif key == 'layer':        style.layer = int(val)
    elif key == 'anchor':       style.anchor = val.strip('"\'')
    elif key == 'filter':       style.filter = val.strip('"\'')
    elif key == 'speed':        style.speed = _parse_dur(val)


# ---------------------------------------------------------------------------
# Asset parsing
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
    path = m.group('path').strip()
    dur = float(m.group('dur')) if m.group('dur') else None
    ext = Path(path).suffix.lower()
    atype = _ASSET_EXT.get(ext, AssetType.VIDEO)
    tags = []
    if m.group('tags'):
        tags = [t.strip().strip('"\'') for t in m.group('tags').split(',') if t.strip()]
    return Asset(id=id_, path=path, type=atype, duration=dur, tags=tags)


def _parse_text_asset(m: re.Match) -> Asset:
    id_ = m.group('id')
    content = m.group('content').replace('\\n', '\n')
    font = m.group('font') or 'default'
    size = int(m.group('size')) if m.group('size') else None
    bg = m.group('bg') or '#000000'
    color_val = m.group('color') or '#FFFFFF'
    bg_opacity = float(m.group('bg_opacity')) if m.group('bg_opacity') else 0.0
    return Asset(
        id=id_, path="__text__", type=AssetType.TEXT,
        text_content=content, text_font=font, text_font_size=size,
        text_bg=bg, text_color=color_val, text_bg_opacity=bg_opacity,
    )


# ---------------------------------------------------------------------------
# Time parsing
# ---------------------------------------------------------------------------

def _parse_time(raw: str) -> float | str:
    """Parse a time string. Returns float (absolute seconds) or str (expression/prev.end)."""
    raw = raw.strip()
    # Expression: v1.end - 1s, v1.start + 2s, v1.end
    if RE_EXPR.match(raw):
        return raw  # keep as string, resolve in main
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


# ---------------------------------------------------------------------------
# Timeline entry
# ---------------------------------------------------------------------------

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
    speed = _parse_dur(kv.get('speed'))
    anchor = kv.get('anchor', '(0, 0)').strip()
    crop = _parse_crop(kv.get('crop'))
    trim_start = _parse_dur(kv.get('trim_start'))
    trim_end = _parse_dur(kv.get('trim_end'))
    style_ref = kv.get('style', '').strip().strip('"\'') or None
    filter_val = kv.get('filter', '').strip().strip('"\'') or None
    track_role = kv.get('role', 'auto').strip().strip('"\'') or 'auto'

    # Inline transition dur
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
        mute=mute,
        speed=speed,
        anchor=anchor,
        crop=crop,
        trim_start=trim_start,
        trim_end=trim_end,
        style_ref=style_ref,
        filter=filter_val,
        track_role=track_role,
    )


# ---------------------------------------------------------------------------
# Value parsers
# ---------------------------------------------------------------------------

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


def _parse_crop(val: str | None) -> tuple[int, int, int, int] | None:
    if val is None:
        return None
    m = re.match(r'\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*\)', val)
    if m:
        return (int(m.group(1)), int(m.group(2)), int(m.group(3)), int(m.group(4)))
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


# ---------------------------------------------------------------------------
# Keyframe attachment
# ---------------------------------------------------------------------------

def _attach_keyframes(doc: KinetiXDocument, asset_id: str, prop: str, frames_str: str):
    pairs = RE_KF_PAIR.findall(frames_str)
    curve_match = RE_KF_CURVE.search(frames_str)
    curve = curve_match.group(1) if curve_match else "linear"

    kf_track = KeyframeTrack(
        property_name=prop,
        keyframes=[(float(t), _parse_kf_value(v)) for t, v in pairs],
        curve=curve,
    )
    for entry in doc.timeline:
        if entry.asset_id == asset_id:
            entry.keyframes.append(kf_track)
            return
    entry = TimelineEntry(asset_id=asset_id, start_time=0, keyframes=[kf_track])
    doc.timeline.append(entry)
