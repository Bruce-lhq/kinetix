"""KinetiX CLI entry point — resolves relative times, expressions, and compiles .ktx → .mp4."""

from __future__ import annotations

import re
import sys
from pathlib import Path

from .ast_nodes import AssetType, KinetiXDocument, Style, TimelineEntry
from .graphviz_timeline import generate_timeline_graph
from .parser import parse, RE_EXPR
from .renderer import live_preview, render


# ---------------------------------------------------------------------------
# Expression resolution
# ---------------------------------------------------------------------------

_RE_REF = re.compile(r'^(\w+)\.(start|end)$')
_RE_REF_OP = re.compile(r'^(\w+)\.(start|end)\s*([+-])\s*(\d+(?:\.\d+)?)s$')


def _resolve_asset_paths(doc: KinetiXDocument, base_dir: Path) -> None:
    """Resolve relative asset paths against the .ktx file's directory."""
    for asset in doc.assets.values():
        if asset.path == "__text__":
            continue
        p = Path(asset.path)
        if not p.is_absolute():
            resolved = (base_dir / p).resolve()
            if resolved.exists():
                asset.path = str(resolved)


def resolve_timeline(doc: KinetiXDocument) -> None:
    """Resolve prev.end and expression times (v1.end-1s) to absolute seconds."""
    # Track resolved end times for all entries (indexed by asset_id)
    resolved: dict[str, float] = {}
    video_layer_end: dict[int, float] = {}
    video_global_end = 0.0
    audio_last_end = 0.0

    for idx, entry in enumerate(doc.timeline):
        asset = doc.assets.get(entry.asset_id)
        is_audio = asset is not None and asset.type == AssetType.AUDIO

        # --- Resolve start_time ---
        _resolve_start_time(entry, resolved, video_layer_end, video_global_end, audio_last_end, is_audio)

        # --- Duration ---
        dur = entry.duration
        if dur is None and asset is not None:
            if asset.type in (AssetType.VIDEO, AssetType.AUDIO):
                dur = asset.duration or _probe_duration(asset.path) or 5.0
            else:
                dur = 5.0
            entry.duration = dur

        # Speed adjustment: faster playback = shorter effective duration
        speed = entry.speed if entry.speed and entry.speed > 0 else 1.0
        effective_dur = (dur or 5.0) / speed
        end = entry.start_time + effective_dur
        resolved[entry.asset_id] = max(resolved.get(entry.asset_id, 0.0), end)

        if is_audio:
            audio_last_end = max(audio_last_end, end)
        else:
            video_layer_end[entry.layer] = max(video_layer_end.get(entry.layer, 0.0), end)
            video_global_end = max(video_global_end, end)


def _resolve_start_time(entry: TimelineEntry, resolved: dict[str, float],
                        video_layer_end: dict[int, float], video_global_end: float,
                        audio_last_end: float, is_audio: bool):
    """Resolve a single entry's start_time to a float."""
    st = entry.start_time

    if isinstance(st, (int, float)):
        return

    # prev.end
    if st == 'prev.end':
        if is_audio:
            entry.start_time = audio_last_end
        else:
            entry.start_time = video_layer_end.get(entry.layer, video_global_end)
        return

    # expression: v1.end, v1.start, v1.end - 1s, v1.start + 2s
    m = _RE_REF_OP.match(st)
    if m:
        ref_id, ref_prop, op, offset_str = m.group(1), m.group(2), m.group(3), m.group(4)
        base = resolved.get(ref_id, 0.0)
        offset = float(offset_str)
        entry.start_time = base + offset if op == '+' else base - offset
        return

    m = _RE_REF.match(st)
    if m:
        ref_id, ref_prop = m.group(1), m.group(2)
        entry.start_time = resolved.get(ref_id, 0.0)
        return

    # bare float string
    try:
        entry.start_time = float(st)
    except ValueError:
        entry.start_time = 0.0


# ---------------------------------------------------------------------------
# Style merging
# ---------------------------------------------------------------------------

def _apply_styles(doc: KinetiXDocument) -> None:
    """Merge referenced styles into timeline entries."""
    for entry in doc.timeline:
        if not entry.style_ref:
            continue
        style = doc.styles.get(entry.style_ref)
        if not style:
            print(f"[warn] unknown style '{entry.style_ref}'")
            continue
        if entry.fadein is None and style.fadein is not None:
            entry.fadein = style.fadein
        if entry.fadeout is None and style.fadeout is not None:
            entry.fadeout = style.fadeout
        if style.transition and not entry.transition:
            entry.transition = style.transition
            entry.transition_dur = style.transition_dur
        if entry.volume is None and style.volume is not None:
            entry.volume = style.volume
        if not entry.mute and style.mute:
            entry.mute = True
        if not entry.layer:
            entry.layer = style.layer or entry.layer
        if entry.anchor == "(0, 0)" and style.anchor:
            entry.anchor = style.anchor
        if entry.speed is None and style.speed is not None:
            entry.speed = style.speed
        if entry.filter is None and style.filter:
            entry.filter = style.filter


# ---------------------------------------------------------------------------
# Audio ducking (reserved for future)
# ---------------------------------------------------------------------------

def _compute_audio_ducking(doc: KinetiXDocument) -> None:
    """Identify voice/BGM overlaps and mark ducking regions.
    Currently a no-op — stores ducking metadata for future renderer use.
    """
    voice_entries = [e for e in doc.timeline
                     if e.track_role == "voice" and doc.assets.get(e.asset_id, None)
                     and doc.assets[e.asset_id].type == AssetType.AUDIO]
    bgm_entries = [e for e in doc.timeline
                   if e.track_role == "bgm" and doc.assets.get(e.asset_id, None)
                   and doc.assets[e.asset_id].type == AssetType.AUDIO]

    if not voice_entries or not bgm_entries:
        return

    for bgm in bgm_entries:
        bgm_start = bgm.start_time if isinstance(bgm.start_time, (int, float)) else 0
        bgm_end = bgm_start + (bgm.duration or 0)
        overlaps = [v for v in voice_entries
                    if (v.start_time if isinstance(v.start_time, (int, float)) else 0) < bgm_end
                    and (v.start_time if isinstance(v.start_time, (int, float)) else 0) + (v.duration or 0) > bgm_start]
        if overlaps:
            print(f"[ducking] {len(overlaps)} voice overlaps detected on BGM '{bgm.asset_id}'")


# ---------------------------------------------------------------------------
# Compile
# ---------------------------------------------------------------------------

def compile_ktx(ktx_path: str, output_path: str | None = None,
                preview_range: tuple[float, float] | None = None,
                no_subtitles: bool = False) -> None:
    source = Path(ktx_path).read_text(encoding="utf-8")

    doc = parse(source)
    _resolve_asset_paths(doc, Path(ktx_path).resolve().parent)
    _apply_styles(doc)          # merge style blocks into entries
    resolve_timeline(doc)       # resolve prev.end, v1.end-1s etc.
    _merge_keyframe_entries(doc)
    _compute_audio_ducking(doc)

    if output_path is None:
        base = str(Path(ktx_path).with_suffix(""))
        if preview_range:
            output_path = f"{base}_preview{preview_range[0]:.0f}-{preview_range[1]:.0f}.mp4"
        else:
            output_path = f"{base}.mp4"
    render(doc, output_path, preview_range=preview_range, no_subtitles=no_subtitles)


def live_mode(ktx_path: str, no_subtitles: bool = False) -> None:
    """Parse, resolve, and stream to ffplay without encoding to file."""
    source = Path(ktx_path).read_text(encoding="utf-8")
    doc = parse(source)
    _resolve_asset_paths(doc, Path(ktx_path).resolve().parent)
    _apply_styles(doc)
    resolve_timeline(doc)
    _merge_keyframe_entries(doc)
    live_preview(doc)


def graph_mode(ktx_path: str, output_path: str | None = None) -> str:
    """Parse, resolve, and generate a timeline topology PNG."""
    source = Path(ktx_path).read_text(encoding="utf-8")
    doc = parse(source)
    _resolve_asset_paths(doc, Path(ktx_path).resolve().parent)
    _apply_styles(doc)
    resolve_timeline(doc)
    _merge_keyframe_entries(doc)
    if output_path is None:
        output_path = str(Path(ktx_path).with_suffix("")) + "_timeline"
    else:
        output_path = str(Path(output_path).with_suffix(""))
    result = generate_timeline_graph(doc, output_path)
    print(f"[graph] → {result}")
    return result


def _merge_keyframe_entries(doc: KinetiXDocument) -> None:
    by_id: dict[str, list[TimelineEntry]] = {}
    for entry in doc.timeline:
        by_id.setdefault(entry.asset_id, []).append(entry)

    merged = []
    seen = set()
    for entry in doc.timeline:
        if entry.asset_id in seen:
            continue
        seen.add(entry.asset_id)
        group = by_id[entry.asset_id]
        if len(group) == 1:
            merged.append(entry)
        else:
            primary = None
            all_kf = []
            for e in group:
                all_kf.extend(e.keyframes)
                if any([e.layer != 0, e.position, e.transition, e.duration]):
                    primary = e
            if primary is None:
                primary = group[0]
            primary.keyframes = all_kf
            merged.append(primary)
    doc.timeline = merged


def _probe_duration(path: str) -> float | None:
    try:
        from moviepy import AudioFileClip, VideoFileClip
        p = Path(path)
        if not p.exists():
            return None
        ext = p.suffix.lower()
        clip = AudioFileClip(str(p)) if ext in ('.mp3', '.wav', '.aac', '.flac', '.m4a') else VideoFileClip(str(p))
        dur = clip.duration
        clip.close()
        return dur
    except Exception:
        return None


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: python -m kinetix <file.ktx> [output.mp4]")
        sys.exit(1)
    ktx_path = sys.argv[1]
    output = sys.argv[2] if len(sys.argv) > 2 else None
    compile_ktx(ktx_path, output)


if __name__ == "__main__":
    main()
