#!/usr/bin/env python3
"""Render a single frame from a .ktx file at a given time as PNG.
Usage: python snapshot.py <file.ktx> <time> [output.png]
"""
import sys
from pathlib import Path

# Ensure kinetix is importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from kinetix.main import _prepare
from kinetix.renderer import _build_all_clips
from moviepy import CompositeVideoClip, CompositeAudioClip


def snapshot(ktx_path: str, time_s: float, output_png: str) -> str:
    doc = _prepare(ktx_path)
    size = doc.output.size

    video_clips, audio_clips = _build_all_clips(doc, size)
    if not video_clips:
        print("[error] no clips to render", file=sys.stderr)
        sys.exit(1)

    video_clips.sort(key=lambda c: c.layer_order)
    comp = CompositeVideoClip(video_clips, size=size)
    if audio_clips:
        comp = comp.with_audio(CompositeAudioClip(audio_clips))

    t = min(time_s, comp.duration - 0.001) if comp.duration else time_s
    frame = comp.get_frame(t)
    comp.close()

    from PIL import Image
    img = Image.fromarray(frame)
    img.save(output_png)
    return output_png


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python snapshot.py <file.ktx> <time> [output.png]", file=sys.stderr)
        sys.exit(1)

    ktx_file = sys.argv[1]
    time_val = float(sys.argv[2])
    out = sys.argv[3] if len(sys.argv) > 3 else f"{Path(ktx_file).stem}_snapshot.png"
    result = snapshot(ktx_file, time_val, out)
    print(result)
