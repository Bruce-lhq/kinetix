"""Generate text card images using PIL — Pro edition.

Supports auto word-wrap for long lines, configurable line spacing,
and optional semi-transparent background block behind text.
"""

from __future__ import annotations

import math
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont


def _find_font(candidates: list[str]) -> str | None:
    """Return the first existing font path from candidates, or None."""
    for p in candidates:
        if Path(p).exists():
            return p
    return None


_FONT_CANDIDATES = {
    "songti": [
        "/System/Library/Fonts/Supplemental/Songti.ttc",          # macOS
        "/usr/share/fonts/truetype/noto/NotoSerifCJK-Regular.ttc",  # Linux
        "C:\\Windows\\Fonts\\simsum.ttc",                          # Windows
    ],
    "heiti": [
        "/System/Library/Fonts/STHeiti Medium.ttc",                # macOS
        "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",   # Linux
        "C:\\Windows\\Fonts\\simhei.ttf",                           # Windows
    ],
    "default": [
        "/System/Library/Fonts/STHeiti Medium.ttc",
        "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
        "C:\\Windows\\Fonts\\simhei.ttf",
    ],
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
    natural_size: bool = False,
    stroke_width: int = 0,
    stroke_color: str = "#000000",
) -> np.ndarray:
    """Render text onto a background image.

    Args:
        content: Text with \\n for hard line breaks.
        size: Canvas (W, H) — used as max bounds for natural_size mode.
        bg_color: Background color hex.
        text_color: Text color hex.
        font_name: 'songti' | 'heiti' | 'default'.
        font_size: Auto-sized if None.
        line_spacing: Line height multiplier.
        bg_opacity: 0.0=transparent bg, 1.0=solid box behind text.
        wrap_margin: Left/right margin for word-wrap.
        natural_size: If True, render at text's natural size + padding
                      (caller handles positioning).
        stroke_width: Text outline width in px (0 = no stroke).
        stroke_color: Stroke color hex.
    """
    font_path = _find_font(_FONT_CANDIDATES.get(font_name, _FONT_CANDIDATES["default"]))
    canvas_w, canvas_h = size

    # --- measure text ---
    hard_lines = content.split("\n")
    max_w = canvas_w - 2 * wrap_margin

    # temporary draw for measurement
    temp_img = Image.new("RGBA", size, (0, 0, 0, 0))
    temp_draw = ImageDraw.Draw(temp_img)

    if font_size is None:
        font_size = _autosize(temp_draw, hard_lines, font_path, max_w, canvas_h - 100, line_spacing)

    font = ImageFont.truetype(font_path, font_size) if font_path else ImageFont.load_default(font_size)

    # Account for stroke when measuring bounding boxes
    sw = stroke_width if stroke_width > 0 else 0

    wrapped_lines: list[str] = []
    for line in hard_lines:
        wrapped_lines.extend(_wrap_line(line, font, temp_draw, max_w - 2 * sw))

    line_heights: list[int] = []
    line_widths: list[int] = []
    for line in wrapped_lines:
        bbox = temp_draw.textbbox((0, 0), line, font=font, stroke_width=sw, anchor='lt')
        line_heights.append(bbox[3] - bbox[1])
        line_widths.append(bbox[2] - bbox[0])

    spacing_px = int(font_size * (line_spacing - 1.0))
    total_h = sum(line_heights) + spacing_px * (len(wrapped_lines) - 1)
    max_line_w = max(line_widths) if line_widths else 0
    block_pad = int(font_size * 0.3)

    # --- create output image ---
    if natural_size:
        pad = 4
        out_w = max_line_w + 2 * (block_pad if bg_opacity > 0 else pad)
        out_h = total_h + 2 * (block_pad if bg_opacity > 0 else pad)
        img = Image.new("RGBA", (out_w, out_h), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)

        if bg_opacity > 0:
            alpha = int(bg_opacity * 255)
            draw.rounded_rectangle(
                [2, 2, out_w - 2, out_h - 2], radius=12, fill=(0, 0, 0, alpha),
            )

        _draw_text_lines(draw, wrapped_lines, font, text_color,
                         out_h, total_h, block_pad if bg_opacity > 0 else pad, out_w,
                         line_heights, spacing_px,
                         stroke_width=stroke_width, stroke_color=stroke_color)
        return np.array(img)

    # --- full canvas mode ---
    if bg_opacity > 0:
        # Solid background color + semi-transparent block behind text
        bg_rgba = (*_hex_to_rgb(bg_color), 255)
        img = Image.new("RGBA", size, bg_rgba)
        draw = ImageDraw.Draw(img)

        block_top = (canvas_h - total_h) // 2 - block_pad
        block_left = (canvas_w - max_line_w) // 2 - block_pad
        block_right = block_left + max_line_w + 2 * block_pad
        block_bottom = block_top + total_h + 2 * block_pad
        alpha = int(bg_opacity * 255)
        draw.rounded_rectangle(
            [block_left, block_top, block_right, block_bottom],
            radius=12, fill=(0, 0, 0, alpha),
        )
    else:
        # Transparent background, text only
        img = Image.new("RGBA", size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)

    _draw_text_lines(draw, wrapped_lines, font, text_color,
                     canvas_h, total_h, 0, canvas_w,
                     line_heights, spacing_px,
                     stroke_width=stroke_width, stroke_color=stroke_color)
    return np.array(img)


def _hex_to_rgb(hex_color: str) -> tuple[int, int, int]:
    hex_color = hex_color.lstrip("#")
    return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))


def _draw_text_lines(draw, wrapped_lines, font, text_color, canvas_h, total_h,
                     pad_left, canvas_w, line_heights, spacing_px,
                     stroke_width=0, stroke_color="#000000"):
    """Draw wrapped text lines centered on the image."""
    y = (canvas_h - total_h) // 2 if canvas_h > total_h else 0
    for i, line in enumerate(wrapped_lines):
        bbox = draw.textbbox((0, 0), line, font=font, stroke_width=stroke_width, anchor='lt')
        w = bbox[2] - bbox[0]
        x = pad_left + (canvas_w - 2 * pad_left - w) // 2
        draw.text((x, y), line, fill=text_color, font=font,
                  stroke_width=stroke_width, stroke_fill=stroke_color, anchor='lt')
        y += line_heights[i] + spacing_px


def _wrap_line(text: str, font: ImageFont.FreeTypeFont, draw: ImageDraw.Draw, max_w: int) -> list[str]:
    """Word-wrap a single line into multiple lines fitting max_w."""
    if not text.strip():
        return [text]
    words = text.split(" ")
    lines = []
    current = ""
    for word in words:
        test = f"{current} {word}".strip() if current else word
        bbox = draw.textbbox((0, 0), test, font=font, anchor='lt')
        w = bbox[2] - bbox[0]
        if w <= max_w:
            current = test
        else:
            if current:
                lines.append(current)
            # If a single word is too long, keep it (or could hyphenate)
            bbox2 = draw.textbbox((0, 0), word, font=font, anchor='lt')
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
        bbox = draw.textbbox((0, 0), test, font=font, anchor='lt')
        if bbox[2] - bbox[0] > max_w:
            return result  # truncated at max width
        result = test
    return result


def _autosize(draw: ImageDraw.Draw, hard_lines: list[str],
              font_path: str | None, max_w: int, max_h: int,
              line_spacing: float) -> int:
    lo, hi = 12, 200
    best = lo
    while lo <= hi:
        mid = (lo + hi) // 2
        font = ImageFont.truetype(font_path, mid) if font_path else ImageFont.load_default(mid)

        # word-wrap all lines
        wrapped: list[str] = []
        for line in hard_lines:
            wrapped.extend(_wrap_line(line, font, draw, max_w))

        # measure
        total_h = 0
        fits = True
        for line in wrapped:
            bbox = draw.textbbox((0, 0), line, font=font, anchor='lt')
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
