"""Generate text card images using PIL."""

from __future__ import annotations

import numpy as np
from PIL import Image, ImageDraw, ImageFont

# macOS font paths
_FONTS = {
    "songti": "/System/Library/Fonts/Supplemental/Songti.ttc",
    "heiti": "/System/Library/Fonts/STHeiti Medium.ttc",
    "default": "/System/Library/Fonts/STHeiti Medium.ttc",
}


def render_text_card(
    content: str,
    size: tuple[int, int] = (1920, 1080),
    bg_color: str = "#000000",
    text_color: str = "#FFFFFF",
    font_name: str = "default",
    font_size: int | None = None,
) -> np.ndarray:
    """Render text onto a background image. Returns (H, W, 3) uint8 numpy array."""
    img = Image.new("RGB", size, bg_color)
    draw = ImageDraw.Draw(img)

    lines = content.split("\n")
    font_path = _FONTS.get(font_name, _FONTS["default"])

    # Auto-size: find largest font_size that fits all lines
    if font_size is None:
        font_size = _autosize(draw, lines, font_path, size)

    font = ImageFont.truetype(font_path, font_size)

    # Compute total text block height
    line_spacing = int(font_size * 0.3)
    line_heights = []
    for line in lines:
        bbox = draw.textbbox((0, 0), line, font=font)
        line_heights.append(bbox[3] - bbox[1])
    total_h = sum(line_heights) + line_spacing * (len(lines) - 1)

    # Center vertically and horizontally
    y = (size[1] - total_h) // 2
    for i, line in enumerate(lines):
        bbox = draw.textbbox((0, 0), line, font=font)
        w = bbox[2] - bbox[0]
        x = (size[0] - w) // 2
        draw.text((x, y), line, fill=text_color, font=font)
        y += line_heights[i] + line_spacing

    return np.array(img)


def _autosize(draw: ImageDraw.Draw, lines: list[str], font_path: str, canvas: tuple[int, int]) -> int:
    """Binary search for the largest font size that fits."""
    lo, hi = 12, 200
    margin_x = 100
    max_w = canvas[0] - 2 * margin_x
    max_h = canvas[1] - 100  # 50px margin top/bottom

    best = lo
    while lo <= hi:
        mid = (lo + hi) // 2
        font = ImageFont.truetype(font_path, mid)
        fits = True
        total_h = 0
        spacing = int(mid * 0.3)
        for line in lines:
            bbox = draw.textbbox((0, 0), line, font=font)
            w = bbox[2] - bbox[0]
            h = bbox[3] - bbox[1]
            if w > max_w:
                fits = False
                break
            total_h += h
        if fits:
            total_h += spacing * (len(lines) - 1)
            if total_h > max_h:
                fits = False
        if fits:
            best = mid
            lo = mid + 1
        else:
            hi = mid - 1
    return best
