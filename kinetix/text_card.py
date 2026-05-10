"""Generate text card images using PIL — Pro edition.

Supports auto word-wrap for long lines, configurable line spacing,
and optional semi-transparent background block behind text.
"""

from __future__ import annotations

import math
import numpy as np
from PIL import Image, ImageDraw, ImageFont

_FONTS = {
    "songti": "/System/Library/Fonts/Supplemental/Songti.ttc",
    "heiti":  "/System/Library/Fonts/STHeiti Medium.ttc",
    "default": "/System/Library/Fonts/STHeiti Medium.ttc",
}


def render_text_card(
    content: str,
    size: tuple[int, int] = (1920, 1080),
    bg_color: str = "#000000",
    text_color: str = "#FFFFFF",
    font_name: str = "default",
    font_size: int | None = None,
    line_spacing: float = 1.4,
    bg_opacity: float = 0.0,
    wrap_margin: int = 100,
) -> np.ndarray:
    """Render text onto a background image.

    Args:
        content: Text with \\n for hard line breaks.
        size: Canvas (W, H).
        bg_color: Background color hex.
        text_color: Text color hex.
        font_name: 'songti' | 'heiti' | 'default'.
        font_size: Auto-sized if None.
        line_spacing: Line height multiplier (1.0 = tight, 1.4 = comfortable).
        bg_opacity: 0.0=transparent text bg, 1.0=solid box behind text.
        wrap_margin: Left/right margin for word-wrap.
    """
    img = Image.new("RGBA" if bg_opacity > 0 else "RGB", size, bg_color)
    draw = ImageDraw.Draw(img)
    font_path = _FONTS.get(font_name, _FONTS["default"])

    # split hard breaks, then word-wrap each line
    hard_lines = content.split("\n")
    max_w = size[0] - 2 * wrap_margin

    if font_size is None:
        font_size = _autosize(draw, hard_lines, font_path, max_w, size[1] - 100, line_spacing)

    font = ImageFont.truetype(font_path, font_size)

    # word-wrap
    wrapped_lines: list[str] = []
    for line in hard_lines:
        wrapped_lines.extend(_wrap_line(line, font, draw, max_w))

    # measure line heights
    line_heights = []
    for line in wrapped_lines:
        bbox = draw.textbbox((0, 0), line, font=font)
        line_heights.append(bbox[3] - bbox[1])

    spacing_px = int(font_size * (line_spacing - 1.0))
    total_h = sum(line_heights) + spacing_px * (len(wrapped_lines) - 1)

    # semi-transparent background block
    if bg_opacity > 0:
        block_pad = int(font_size * 0.3)
        block_top = (size[1] - total_h) // 2 - block_pad
        block_bottom = block_top + total_h + 2 * block_pad
        max_line_w = max((draw.textbbox((0, 0), l, font=font)[2] for l in wrapped_lines), default=0)
        block_left = (size[0] - max_line_w) // 2 - block_pad
        block_right = block_left + max_line_w + 2 * block_pad
        alpha = int(bg_opacity * 255)
        overlay = Image.new("RGBA", size, (0, 0, 0, 0))
        overlay_draw = ImageDraw.Draw(overlay)
        overlay_draw.rounded_rectangle(
            [block_left, block_top, block_right, block_bottom],
            radius=12, fill=(0, 0, 0, alpha),
        )
        img = Image.alpha_composite(img.convert("RGBA"), overlay)

    # draw text
    y = (size[1] - total_h) // 2
    for i, line in enumerate(wrapped_lines):
        bbox = draw.textbbox((0, 0), line, font=font)
        w = bbox[2] - bbox[0]
        x = (size[0] - w) // 2
        draw.text((x, y), line, fill=text_color, font=font)
        y += line_heights[i] + spacing_px

    return np.array(img.convert("RGB"))


def _wrap_line(text: str, font: ImageFont.FreeTypeFont, draw: ImageDraw.Draw, max_w: int) -> list[str]:
    """Word-wrap a single line into multiple lines fitting max_w."""
    if not text.strip():
        return [text]
    words = text.split(" ")
    lines = []
    current = ""
    for word in words:
        test = f"{current} {word}".strip() if current else word
        bbox = draw.textbbox((0, 0), test, font=font)
        w = bbox[2] - bbox[0]
        if w <= max_w:
            current = test
        else:
            if current:
                lines.append(current)
            # If a single word is too long, keep it (or could hyphenate)
            bbox2 = draw.textbbox((0, 0), word, font=font)
            if bbox2[2] - bbox2[0] > max_w:
                word = _break_long_word(word, font, draw, max_w)
            current = word
    if current:
        lines.append(current)
    return lines or [text]


def _break_long_word(word: str, font: ImageFont.FreeTypeFont, draw: ImageDraw.Draw, max_w: int) -> str:
    """Break a too-long word by adding forced line breaks."""
    # Just return the word as-is for CJK; for Latin, split roughly in half
    result = ""
    for ch in word:
        test = result + ch
        bbox = draw.textbbox((0, 0), test, font=font)
        if bbox[2] - bbox[0] > max_w:
            return result  # truncated at max width
        result = test
    return result


def _autosize(draw: ImageDraw.Draw, hard_lines: list[str],
              font_path: str, max_w: int, max_h: int,
              line_spacing: float) -> int:
    lo, hi = 12, 200
    best = lo
    while lo <= hi:
        mid = (lo + hi) // 2
        font = ImageFont.truetype(font_path, mid)

        # word-wrap all lines
        wrapped: list[str] = []
        for line in hard_lines:
            wrapped.extend(_wrap_line(line, font, draw, max_w))

        # measure
        total_h = 0
        fits = True
        for line in wrapped:
            bbox = draw.textbbox((0, 0), line, font=font)
            if bbox[2] - bbox[0] > max_w:
                fits = False
                break
            total_h += bbox[3] - bbox[1]
        if fits:
            spacing_px = int(mid * (line_spacing - 1.0))
            total_h += spacing_px * (len(wrapped) - 1)
            if total_h > max_h:
                fits = False
        if fits:
            best = mid
            lo = mid + 1
        else:
            hi = mid - 1
    return best
