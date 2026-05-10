"""AST data structures for KinetiX."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class AssetType(Enum):
    VIDEO = "video"
    IMAGE = "image"
    AUDIO = "audio"
    TEXT = "text"


# ---------------------------------------------------------------------------
# Assets (video / image / audio / text)
# ---------------------------------------------------------------------------


@dataclass
class Asset:
    id: str
    path: str
    type: AssetType
    duration: float | None = None
    tags: list[str] = field(default_factory=list)

    # Text-specific
    text_content: str | None = None
    text_bg: str = "#000000"
    text_color: str = "#FFFFFF"
    text_font: str = "default"
    text_font_size: int | None = None
    text_bg_opacity: float = 0.0   # 0=transparent, 1=opaque bg box
    text_stroke_width: int = 0     # text outline stroke width
    text_stroke_color: str = "#000000"


# ---------------------------------------------------------------------------
# Style (macro definition)
# ---------------------------------------------------------------------------


@dataclass
class Style:
    """Predefined property block, referenced via style: name on timeline entries."""
    name: str
    fadein: float | None = None
    fadeout: float | None = None
    transition: str | None = None
    transition_dur: float = 0.0
    volume: float | None = None
    mute: bool = False
    layer: int | None = None
    anchor: str | None = None
    filter: str | None = None        # global filter e.g. "blackwhite", "sepia"
    speed: float | None = None


# ---------------------------------------------------------------------------
# Keyframes
# ---------------------------------------------------------------------------


@dataclass
class KeyframeTrack:
    property_name: str   # "scale", "opacity", "pos", "rotate"
    keyframes: list[tuple[float, Any]]   # [(time_s, value), ...]
    curve: str = "linear"   # "linear" | "ease_in" | "ease_out" | "ease_in_out"


# ---------------------------------------------------------------------------
# Timeline entry
# ---------------------------------------------------------------------------


@dataclass
class TimelineEntry:
    asset_id: str
    start_time: float | str  # absolute s | 'prev.end' | 'v1.end - 2s' (expression)
    layer: int = 0
    duration: float | None = None
    position: tuple[int, int] | str | None = None  # absolute px tuple or "50vw,30vh" string
    transition: str | None = None
    transition_dur: float = 0.0
    fadein: float | None = None
    fadeout: float | None = None
    volume: float | None = None
    mute: bool = False
    speed: float | None = None
    anchor: str = "(0, 0)"
    crop: tuple[int, int, int, int] | None = None
    trim_start: float | None = None
    trim_end: float | None = None
    filter: str | None = None          # per-clip filter override
    style_ref: str | None = None       # style name to apply
    track_role: str = "auto"           # "voice" | "bgm" | "sfx" | "auto"  (for ducking)
    keyframes: list[KeyframeTrack] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Output config
# ---------------------------------------------------------------------------


@dataclass
class OutputConfig:
    format: str = "mp4"
    resolution: str = "1080p"
    fps: int = 30

    @property
    def size(self) -> tuple[int, int]:
        mapping = {
            "480p": (854, 480),
            "720p": (1280, 720),
            "1080p": (1920, 1080),
            "4k": (3840, 2160),
        }
        return mapping.get(self.resolution, (1920, 1080))


# ---------------------------------------------------------------------------
# Top-level document
# ---------------------------------------------------------------------------


@dataclass
class KinetiXDocument:
    assets: dict[str, Asset] = field(default_factory=dict)
    timeline: list[TimelineEntry] = field(default_factory=list)
    styles: dict[str, Style] = field(default_factory=dict)
    output: OutputConfig = field(default_factory=OutputConfig)
    subtitle_path: str | None = None
