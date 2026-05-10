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


@dataclass
class Asset:
    id: str
    path: str
    type: AssetType
    duration: float | None = None

    # Text-specific fields
    text_content: str | None = None
    text_bg: str = "#000000"
    text_color: str = "#FFFFFF"
    text_font: str = "default"
    text_font_size: int | None = None


@dataclass
class KeyframeTrack:
    """A single property animated over time, e.g. scale: {0s: 0.5, 5s: 1.2}."""

    property_name: str
    keyframes: list[tuple[float, Any]]


@dataclass
class TimelineEntry:
    """A single clip placement on the timeline."""

    asset_id: str
    start_time: float | str  # absolute seconds or 'prev.end'
    layer: int = 0
    duration: float | None = None
    position: tuple[int, int] | None = None
    transition: str | None = None
    transition_dur: float = 0.0
    fadein: float | None = None
    fadeout: float | None = None
    volume: float | None = None  # in dB, e.g. -28
    mute: bool = False
    keyframes: list[KeyframeTrack] = field(default_factory=list)


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


@dataclass
class KinetiXDocument:
    """Top-level AST root."""

    assets: dict[str, Asset] = field(default_factory=dict)
    timeline: list[TimelineEntry] = field(default_factory=list)
    output: OutputConfig = field(default_factory=OutputConfig)
