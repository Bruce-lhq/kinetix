"""Renderer — builds moviepy Clip objects from the KinetiX AST."""

from __future__ import annotations

import sys
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
from .subtitles import parse_srt


def _load_image_cover(path: str, canvas_size: tuple[int, int]) -> np.ndarray:
    """Load image, crop to match aspect ratio, resize to exactly canvas_size."""
    from PIL import Image as PILImage, ImageOps
    img = PILImage.open(path)
    if img.mode == 'RGBA':
        img = img.convert('RGB')
    img = ImageOps.fit(img, canvas_size, method=PILImage.LANCZOS)
    return np.array(img)


# ---------------------------------------------------------------------------
# Anchor → position resolver
# ---------------------------------------------------------------------------
#
# anchor = (x, y)  where x, y ∈ [-1, 1]  (screen coordinates, y↓)
#   (-1, -1) → top-left        ( 0, -1) → top-center
#   (-1,  0) → center-left     ( 0,  0) → center
#   ( 1,  1) → bottom-right
#
# pos_x = (x + 1) / 2 * (cw - clip_w)
# pos_y = (y + 1) / 2 * (ch - clip_h)


def _resolve_anchor(anchor: str, canvas_size: tuple[int, int], clip_size: tuple[int, int]):
    """Return (x, y) pixel position for anchor string like '(0, 0)' or 'center'."""
    cw, ch = canvas_size
    w, h = clip_size
    try:
        # Try coordinate format: "(ax, ay)"
        parts = anchor.strip("() ").split(",")
        ax = float(parts[0].strip())
        ay = float(parts[1].strip())
        px = int((ax + 1) / 2 * (cw - w))
        py = int((ay + 1) / 2 * (ch - h))
        return (px, py)
    except (ValueError, IndexError):
        pass
    # Fallback: named anchors (backward compat)
    named = {
        "center":       lambda: ((cw - w) // 2, (ch - h) // 2),
        "top":          lambda: ((cw - w) // 2, 0),
        "bottom":       lambda: ((cw - w) // 2, ch - h),
        "top-left":     lambda: (0, 0),
        "top-right":    lambda: (cw - w, 0),
        "bottom-left":  lambda: (0, ch - h),
        "bottom-right": lambda: (cw - w, ch - h),
        "left":         lambda: (0, (ch - h) // 2),
        "right":        lambda: (cw - w, (ch - h) // 2),
    }
    fn = named.get(anchor.lower(), named["center"])
    return fn()


def _trim_to_preview(clip, p_start: float, p_end: float):
    """Trim and shift a clip to fit the preview window. Returns None if no overlap."""
    c_start = clip.start
    c_end = clip.start + clip.duration
    overlap_start = max(c_start, p_start)
    overlap_end = min(c_end, p_end)
    if overlap_start >= overlap_end:
        return None
    trim_in = overlap_start - c_start
    clip = clip.subclipped(trim_in, trim_in + (overlap_end - overlap_start))
    clip = clip.with_start(overlap_start - p_start)
    return clip


# ---------------------------------------------------------------------------
# Progress bar
# ---------------------------------------------------------------------------

class ProgressBar:
    """Simple ASCII progress bar: [████████░░░░░░] 53%  step/total"""

    def __init__(self, total: int, width: int = 30, prefix: str = ""):
        self.total = total
        self.width = width
        self.prefix = prefix
        self.current = 0

    def update(self, current: int | None = None):
        if current is not None:
            self.current = current
        else:
            self.current += 1
        pct = self.current / self.total if self.total else 0
        filled = int(self.width * pct)
        bar = "█" * filled + "░" * (self.width - filled)
        msg = f"\r{self.prefix}[{bar}] {pct:5.1%} {self.current}/{self.total}"
        sys.stderr.write(msg)
        sys.stderr.flush()

    def finish(self):
        sys.stderr.write("\n")
        sys.stderr.flush()


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def render(doc: KinetiXDocument, output_path: str = "output.mp4",
           preview_range: tuple[float, float] | None = None,
           no_subtitles: bool = False) -> None:
    """Compile a KinetiXDocument to an mp4 file.

    If preview_range=(start_s, end_s), only clips overlapping that window are
    rendered — useful for quick debugging of a specific section.
    """
    size = doc.output.size
    fps = doc.output.fps
    p_start, p_end = preview_range if preview_range else (0.0, float("inf"))
    is_preview = preview_range is not None

    video_clips = []
    audio_clips = []
    total = len(doc.timeline)
    pbar = ProgressBar(total, prefix="build clips ")

    for i, entry in enumerate(doc.timeline):
        asset = doc.assets.get(entry.asset_id)
        if asset is None:
            continue
        pbar.update(i + 1)

        # --- Preview filtering ---
        if is_preview:
            e_start = entry.start_time if isinstance(entry.start_time, (int, float)) else 0
            e_dur = entry.duration or 5.0
            e_end = e_start + e_dur
            if e_end <= p_start or e_start >= p_end:
                continue  # clip entirely outside preview window

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

    pbar.finish()

    # --- Subtitles (loaded before preview trim so they shift correctly) ---
    sub_clips = []
    if doc.subtitle_path and not no_subtitles:
        srt_path = Path(doc.subtitle_path)
        if srt_path.exists():
            sub_clips = _build_subtitle_clips(parse_srt(str(srt_path)), size)
            print(f"[info] {len(sub_clips)} subtitles loaded")
        else:
            print(f"[warn] subtitle file not found: {srt_path}")

    video_clips.extend(sub_clips)

    if is_preview:
        # Shift & trim ALL clips (including subtitles) to preview window
        video_clips[:] = [_trim_to_preview(c, p_start, p_end) for c in video_clips]
        audio_clips[:] = [_trim_to_preview(c, p_start, p_end) for c in audio_clips]
        video_clips = [c for c in video_clips if c is not None]
        audio_clips = [c for c in audio_clips if c is not None]

    if not video_clips:
        print("[error] no video/image clips to render")
        return

    video_clips.sort(key=lambda c: c.layer_order)

    n_vid = len(video_clips)
    n_aud = len(audio_clips)
    label = f"[preview {p_start:.1f}s-{p_end:.1f}s]" if is_preview else ""
    print(f"[compose] {n_vid} video + {n_aud} audio clips {label}")

    composite = CompositeVideoClip(video_clips, size=size)
    if audio_clips:
        composite = composite.with_audio(CompositeAudioClip(audio_clips))
    composite = composite.with_duration(composite.duration)

    print("[render] writing video...")
    composite.write_videofile(output_path, fps=fps, codec="libx264", audio_codec="aac",
                              logger="bar")
    print(f"[done] → {output_path}")


# ---------------------------------------------------------------------------
# Clip builders
# ---------------------------------------------------------------------------

def _build_text_clip(asset: Asset, entry: TimelineEntry, canvas_size: tuple[int, int]):
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
    for kf in entry.keyframes:
        clip = _apply_keyframes(clip, kf)
    clip = _apply_fade(clip, entry)
    clip.layer_order = entry.layer
    return clip


def _build_video_clip(asset: Asset, entry: TimelineEntry, canvas_size: tuple[int, int]):
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
        frame = _load_image_cover(str(path), canvas_size)
        base = ImageClip(frame).with_duration(dur)

    # --- speed ---
    if entry.speed is not None and entry.speed > 0 and entry.speed != 1.0:
        base = base.with_effects([vfx.MultiplySpeed(entry.speed)])

    # --- crop ---
    if entry.crop is not None:
        x, y, w, h = entry.crop
        base = base.with_effects([vfx.Crop(x1=x, y1=y, x2=x + w, y2=y + h)])

    # --- time trim (subclipped to trim_start..trim_end, then duration caps) ---
    if entry.trim_start is not None or entry.trim_end is not None:
        t0 = entry.trim_start or 0.0
        t1 = entry.trim_end or base.duration
        t1 = min(t1, base.duration)
        base = base.subclipped(t0, t1)
    elif entry.duration is not None and asset.type == AssetType.VIDEO:
        actual_dur = min(entry.duration, base.duration)
        base = base.subclipped(0, actual_dur)
    elif entry.duration is not None:
        base = base.with_duration(entry.duration)

    # --- start time ---
    base = base.with_start(entry.start_time)

    # --- keyframe animations (BEFORE anchor so scale affects clip size) ---
    for kf in entry.keyframes:
        base = _apply_keyframes(base, kf)

    # --- position (anchor or explicit pos) ---
    if entry.position is not None:
        base = base.with_position(entry.position)
    elif entry.anchor not in ("(0, 0)", "center"):
        try:
            clip_w, clip_h = base.size
            pos = _resolve_anchor(entry.anchor, canvas_size, (clip_w, clip_h))
            base = base.with_position(pos)
        except Exception:
            pass

    # --- fade / transition ---
    base = _apply_fade(base, entry)

    # --- mute ---
    if entry.mute:
        base = base.without_audio()

    base.layer_order = entry.layer
    return base


def _build_audio_clip(asset: Asset, entry: TimelineEntry):
    path = Path(asset.path)
    if not path.exists():
        print(f"[warn] file not found: {path}, skipping")
        return None

    clip = AudioFileClip(str(path))

    # trim
    if entry.trim_start is not None or entry.trim_end is not None:
        t0 = entry.trim_start or 0.0
        t1 = entry.trim_end or clip.duration
        clip = clip.subclipped(t0, min(t1, clip.duration))
    elif entry.duration is not None:
        clip = clip.subclipped(0, min(entry.duration, clip.duration))

    clip = clip.with_start(entry.start_time)

    if entry.speed is not None and entry.speed > 0 and entry.speed != 1.0:
        clip = clip.with_effects([vfx.MultiplySpeed(entry.speed)])

    if entry.volume is not None:
        factor = 10 ** (entry.volume / 20.0)
        clip = clip.multiplied_by(factor)

    return clip


def _build_subtitle_clips(subs, canvas_size: tuple[int, int]):
    from moviepy import TextClip
    clips = []
    font = "/System/Library/Fonts/STHeiti Medium.ttc"
    for sub in subs:
        dur = sub.end - sub.start
        if dur <= 0:
            continue
        text = sub.text.replace("\n", " ")
        tc = TextClip(
            text=text,
            font=font,
            font_size=42,
            color="white",
            stroke_color="black",
            stroke_width=1,
            size=(canvas_size[0] - 80, None),
            method="caption",
            text_align="center",
        )
        tc = tc.with_duration(dur).with_start(sub.start)
        tc = tc.with_position(("center", canvas_size[1] - 100))
        tc.layer_order = 999
        clips.append(tc)
    return clips


# ---------------------------------------------------------------------------
# Fade / transition
# ---------------------------------------------------------------------------

def _apply_fade(clip, entry: TimelineEntry):
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
    return clip.resized(lambda t: _lerp(t, frames))


def _apply_opacity_keyframes(clip, frames: list[tuple[float, Any]]):
    frames.sort(key=lambda p: p[0])
    return clip.with_opacity(lambda t: _lerp(t, frames))


def _apply_pos_keyframes(clip, frames: list[tuple[float, Any]]):
    frames.sort(key=lambda p: p[0])
    return clip.with_position(lambda t: _lerp_tuple(t, frames))


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
            return (v0[0] + (v1[0] - v0[0]) * ratio, v0[1] + (v1[1] - v0[1]) * ratio)
    return frames[-1][1]
