"""Renderer — builds moviepy Clip objects from the KinetiX AST."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from moviepy import (
    AudioFileClip,
    CompositeAudioClip,
    CompositeVideoClip,
    ImageClip,
    VideoFileClip,
    vfx,
)
import numpy as np

from .ast_nodes import Asset, AssetType, KeyframeTrack, KinetiXDocument, TimelineEntry
from .text_card import render_text_card


def _load_image_cover(path: str, canvas_size: tuple[int, int]) -> np.ndarray:
    """Load image, crop to match aspect ratio, resize to exactly canvas_size."""
    from PIL import Image as PILImage, ImageOps
    img = PILImage.open(path)
    if img.mode == 'RGBA':
        img = img.convert('RGB')
    img = ImageOps.fit(img, canvas_size, method=PILImage.LANCZOS)
    return np.array(img)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def render(doc: KinetiXDocument, output_path: str = "output.mp4") -> None:
    """Compile a KinetiXDocument to an mp4 file."""
    size = doc.output.size
    fps = doc.output.fps

    video_clips = []
    audio_clips = []

    for entry in doc.timeline:
        asset = doc.assets.get(entry.asset_id)
        if asset is None:
            print(f"[warn] unknown asset '{entry.asset_id}', skipping")
            continue

        if asset.type == AssetType.AUDIO:
            clip = _build_audio_clip(asset, entry)
            if clip is not None:
                audio_clips.append(clip)
        elif asset.type == AssetType.TEXT:
            clip = _build_text_clip(asset, entry, size)
            if clip is not None:
                video_clips.append(clip)
        else:
            clip = _build_video_clip(asset, entry, size)
            if clip is not None:
                video_clips.append(clip)

    if not video_clips:
        print("[error] no video/image clips to render")
        return

    video_clips.sort(key=lambda c: c.layer_order)

    composite = CompositeVideoClip(video_clips, size=size)

    if audio_clips:
        composite = composite.with_audio(CompositeAudioClip(audio_clips))

    composite = composite.with_duration(composite.duration)
    composite.write_videofile(output_path, fps=fps, codec="libx264", audio_codec="aac")
    print(f"[done] → {output_path}")


# ---------------------------------------------------------------------------
# Clip builders
# ---------------------------------------------------------------------------

def _build_text_clip(asset: Asset, entry: TimelineEntry, canvas_size: tuple[int, int]):
    """Generate a text card image and wrap as an ImageClip."""
    dur = entry.duration or asset.duration or 5.0
    frame = render_text_card(
        content=asset.text_content or "",
        size=canvas_size,
        bg_color=asset.text_bg,
        text_color=asset.text_color,
        font_name=asset.text_font,
        font_size=asset.text_font_size,
    )
    clip = ImageClip(frame).with_duration(dur)
    clip = clip.with_start(entry.start_time)

    # keyframes
    for kf in entry.keyframes:
        clip = _apply_keyframes(clip, kf)

    # fade
    clip = _apply_fade(clip, entry)

    clip.layer_order = entry.layer
    return clip


def _build_video_clip(asset: Asset, entry: TimelineEntry, canvas_size: tuple[int, int]):
    """Build a moviepy video/image clip from an asset + timeline entry."""
    path = Path(asset.path)
    if not path.exists():
        print(f"[warn] file not found: {path}, skipping")
        return None

    # --- base clip ---
    if asset.type == AssetType.VIDEO:
        base = VideoFileClip(str(path))
        # Auto-scale video to cover canvas
        if base.size != list(canvas_size):
            cover_scale = max(canvas_size[0] / base.w, canvas_size[1] / base.h)
            base = base.resized(cover_scale)
    else:
        dur = entry.duration or asset.duration or 5.0
        # Auto-fit image to cover canvas (crop+resize, like CSS object-fit: cover)
        frame = _load_image_cover(str(path), canvas_size)
        base = ImageClip(frame).with_duration(dur)

    # --- duration override ---
    if entry.duration is not None and asset.type == AssetType.VIDEO:
        actual_dur = min(entry.duration, base.duration)
        base = base.subclipped(0, actual_dur)
    elif entry.duration is not None:
        base = base.with_duration(entry.duration)

    # --- start time ---
    base = base.with_start(entry.start_time)

    # --- position ---
    if entry.position is not None:
        base = base.with_position(entry.position)

    # --- keyframe animations ---
    for kf in entry.keyframes:
        base = _apply_keyframes(base, kf)

    # --- fade / transition ---
    base = _apply_fade(base, entry)

    # --- mute video's own audio ---
    if entry.mute:
        base = base.without_audio()

    base.layer_order = entry.layer  # type: ignore[attr-defined]
    return base


def _build_audio_clip(asset: Asset, entry: TimelineEntry):
    path = Path(asset.path)
    if not path.exists():
        print(f"[warn] file not found: {path}, skipping")
        return None

    clip = AudioFileClip(str(path))
    if entry.duration is not None:
        clip = clip.subclipped(0, min(entry.duration, clip.duration))
    clip = clip.with_start(entry.start_time)

    # volume adjustment (dB)
    if entry.volume is not None:
        import math
        factor = 10 ** (entry.volume / 20.0)
        clip = clip.multiplied_by(factor)

    return clip


# ---------------------------------------------------------------------------
# Fade / transition
# ---------------------------------------------------------------------------

def _apply_fade(clip, entry: TimelineEntry):
    """Apply fade in/out or crossfade transition."""
    # Explicit fadein/fadeout take priority
    if entry.fadein and entry.fadein > 0:
        clip = clip.with_effects([vfx.FadeIn(entry.fadein)])
    elif entry.transition == "crossfade" and entry.transition_dur > 0:
        clip = clip.with_effects([vfx.CrossFadeIn(entry.transition_dur)])

    if entry.fadeout and entry.fadeout > 0:
        clip = clip.with_effects([vfx.FadeOut(entry.fadeout)])

    return clip


# ---------------------------------------------------------------------------
# Keyframe interpolation
# ---------------------------------------------------------------------------

def _apply_keyframes(clip, kf: KeyframeTrack):
    frames = kf.keyframes
    if not frames:
        return clip

    prop = kf.property_name
    if prop == "scale":
        return _apply_scale_keyframes(clip, frames)
    elif prop == "opacity":
        return _apply_opacity_keyframes(clip, frames)
    elif prop == "pos":
        return _apply_pos_keyframes(clip, frames)

    print(f"[warn] unsupported keyframe property: {prop}")
    return clip


def _lerp(t: float, frames: list[tuple[float, Any]]) -> float:
    if t <= frames[0][0]:
        return frames[0][1]
    if t >= frames[-1][0]:
        return frames[-1][1]
    for i in range(len(frames) - 1):
        t0, v0 = frames[i]
        t1, v1 = frames[i + 1]
        if t0 <= t <= t1:
            ratio = (t - t0) / (t1 - t0) if t1 != t0 else 0.0
            return v0 + (v1 - v0) * ratio
    return frames[-1][1]


def _apply_scale_keyframes(clip, frames: list[tuple[float, Any]]):
    frames.sort(key=lambda p: p[0])

    def scale_fn(t):
        return _lerp(t, frames)

    return clip.resized(scale_fn)


def _apply_opacity_keyframes(clip, frames: list[tuple[float, Any]]):
    frames.sort(key=lambda p: p[0])

    def opacity_fn(t):
        return _lerp(t, frames)

    return clip.with_opacity(opacity_fn)


def _apply_pos_keyframes(clip, frames: list[tuple[float, Any]]):
    frames.sort(key=lambda p: p[0])

    def pos_fn(t):
        return _lerp_tuple(t, frames)

    return clip.with_position(pos_fn)


def _lerp_tuple(t: float, frames: list[tuple[float, tuple]]) -> tuple:
    if t <= frames[0][0]:
        return frames[0][1]
    if t >= frames[-1][0]:
        return frames[-1][1]
    for i in range(len(frames) - 1):
        t0, v0 = frames[i]
        t1, v1 = frames[i + 1]
        if t0 <= t <= t1:
            ratio = (t - t0) / (t1 - t0) if t1 != t0 else 0.0
            return (
                v0[0] + (v1[0] - v0[0]) * ratio,
                v0[1] + (v1[1] - v0[1]) * ratio,
            )
    return frames[-1][1]
