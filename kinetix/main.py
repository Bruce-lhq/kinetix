"""KinetiX CLI entry point — resolves relative times and compiles .ktx → .mp4."""

from __future__ import annotations

import sys
from pathlib import Path

from .ast_nodes import AssetType, KinetiXDocument, TimelineEntry
from .parser import parse
from .renderer import render


def _probe_duration(path: str) -> float | None:
    """Probe media file duration without fully loading it."""
    try:
        from moviepy import AudioFileClip, VideoFileClip
        from pathlib import Path
        p = Path(path)
        if not p.exists():
            return None
        ext = p.suffix.lower()
        if ext in ('.mp3', '.wav', '.aac', '.flac', '.m4a'):
            clip = AudioFileClip(str(p))
        else:
            clip = VideoFileClip(str(p))
        dur = clip.duration
        clip.close()
        return dur
    except Exception:
        return None


def resolve_timeline(doc: KinetiXDocument) -> None:
    """Resolve all relative time markers (e.g. prev.end) to absolute seconds.

    Video/image/text entries use layer-based prev.end.
    Audio entries use their own sequential prev.end chain.
    """
    # Separate audio and non-audio entries
    video_layer_end: dict[int, float] = {}
    video_global_end = 0.0
    audio_last_end = 0.0

    for entry in doc.timeline:
        asset = doc.assets.get(entry.asset_id)
        is_audio = asset is not None and asset.type == AssetType.AUDIO

        if is_audio:
            _resolve_entry_time(entry, audio_last_end)
        else:
            layer_end = video_layer_end.get(entry.layer, video_global_end)
            _resolve_entry_time(entry, layer_end)

        # compute duration fallback
        dur = entry.duration
        if dur is None and asset is not None:
            if asset.type == AssetType.VIDEO:
                dur = asset.duration or _probe_duration(asset.path) or 5.0
            elif asset.type == AssetType.IMAGE:
                dur = 5.0
            elif asset.type == AssetType.AUDIO:
                dur = asset.duration or _probe_duration(asset.path) or 5.0
            elif asset.type == AssetType.TEXT:
                dur = 5.0
            entry.duration = dur

        end = entry.start_time + (dur or 5.0)

        if is_audio:
            audio_last_end = max(audio_last_end, end)
        else:
            video_layer_end[entry.layer] = max(video_layer_end.get(entry.layer, 0), end)
            video_global_end = max(video_global_end, end)


def _resolve_entry_time(entry: TimelineEntry, fallback: float) -> None:
    if isinstance(entry.start_time, str) and entry.start_time == 'prev.end':
        entry.start_time = fallback
    elif isinstance(entry.start_time, str):
        entry.start_time = float(entry.start_time)


def compile_ktx(ktx_path: str, output_path: str | None = None) -> None:
    """Main compilation pipeline: parse → resolve → render."""
    source = Path(ktx_path).read_text(encoding="utf-8")

    # 1. Parse
    doc = parse(source)

    # 2. Resolve relative times
    resolve_timeline(doc)

    # 3. Merge keyframe-only entries with their timeline entries
    _merge_keyframe_entries(doc)

    # 4. Render
    if output_path is None:
        output_path = str(Path(ktx_path).with_suffix(".mp4"))
    render(doc, output_path)


def _merge_keyframe_entries(doc: KinetiXDocument) -> None:
    """If keyframes were parsed as separate entries, merge them."""
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
                if e.layer != 0 or e.position is not None or e.transition is not None or e.duration is not None:
                    primary = e
            if primary is None:
                primary = group[0]
            primary.keyframes = all_kf
            merged.append(primary)
    doc.timeline = merged


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: python -m kinetix <file.ktx> [output.mp4]")
        sys.exit(1)

    ktx_path = sys.argv[1]
    output = sys.argv[2] if len(sys.argv) > 2 else None
    compile_ktx(ktx_path, output)


if __name__ == "__main__":
    main()
