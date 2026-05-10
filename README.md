# KinetiX

声明式视频编译引擎 — 用纯文本 `.ktx` 文件描述多轨视频，编译输出 `.mp4`。
A declarative video composition engine — write timelines in `.ktx`, compile to `.mp4`.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](pyproject.toml)

## Quick Start

**Prerequisites:** Python ≥ 3.10. [ffmpeg](https://ffmpeg.org/) (optional, for `--live` preview only).

```bash
git clone git@github.com:Bruce-lhq/kinetix.git
cd kinetix
pip install -e .
kinetix demo.ktx                # compile to demo.mp4
kinetix demo.ktx --graph        # generate timeline topology PNG
kinetix demo.ktx --live         # live preview via ffplay
```

## CLI

```bash
kinetix <input.ktx> [output.mp4] [options]

Options:
  --live                Live preview via ffplay (no encoding)
  --preview START-END   Render a time slice, e.g. --preview 00:30-01:00
  --graph               Generate timeline topology PNG (no video render)
  --no-subtitles        Skip SRT subtitle rendering
```

## .ktx Syntax

### Asset Declarations

```yaml
[v1]:  clips/video.mp4 [tag1, tag2]     # video with tags
[img]: clips/photo.jpg [overlay]        # image
[bgm]: clips/music.mp3                  # audio
[t1]:  text("Line 1\nLine 2", font: songti, bg_opacity: 0.5)
```

Supported formats: `.mp4` `.mov` `.avi` `.mkv` | `.jpg` `.jpeg` `.png` `.bmp` `.gif` | `.mp3` `.wav` `.aac` `.flac` `.m4a`

### Style Macros

```yaml
Define Style("intro"):
  fadein: 1s
  layer: 0
  transition: "crossfade", dur: 0.5s
  filter: "blackwhite"

[v1] @ 00:00 | style: "intro" | mute: true
```

Style properties: `fadein` `fadeout` `transition` `volume` `mute` `layer` `anchor` `filter` `speed`. Entry values override style defaults.

### Timeline

```yaml
# Expression time — anchor to any named clip
[v2] @ v1.end - 1s | layer: 0
[a1] @ v1.start + 2s | layer: 0

# prev.end chains (audio/video tracked independently)
[v3] @ prev.end | layer: 0

# Split: same asset, different segments
[v_part1] @ 00:00 | trim_start: 0s | trim_end: 5s
[v_part2] @ prev.end | trim_start: 5s | trim_end: 10s

# Audio ducking roles
[voice] @ 00:00 | role: voice
[bgm]   @ 00:00 | role: bgm | volume: -20
```

### Timeline Properties

| Property | Value | Description |
|----------|-------|-------------|
| `duration` | `10s` | Override asset duration |
| `layer` | `0`, `1`, … | Z-order (0 = bottom) |
| `pos` | `(x, y)` or `(50vw, 30vh)` | Pixel or relative position |
| `anchor` | `(0, 0)` | Relative anchor point |
| `style` | `"intro"` | Reference a Style macro |
| `crop` | `(x, y, w, h)` | Frame crop |
| `trim_start` | `2s` | Start time trim |
| `trim_end` | `8s` | End time trim |
| `filter` | `"blackwhite"` | Global filter |
| `transition` | `"crossfade"` | Entrance transition |
| `fadein` / `fadeout` | `1s` | Fade in/out |
| `mute` | `true` | Mute video track |
| `speed` | `2` | Playback speed (affects timeline) |
| `volume` | `-28` | Volume in dB |
| `role` | `voice` / `bgm` / `sfx` | Audio role (for ducking) |

### Position Units (CSS-like)

`pos` supports mixed units that auto-scale when you change output resolution:

| Unit | Meaning | Example |
|------|---------|---------|
| `vw` | % of canvas width | `50vw` = half canvas width |
| `vh` | % of canvas height | `30vh` = 30% canvas height |
| `pw` | % of asset width | `10pw` = 10% of image/video width |
| `ph` | % of asset height | `5ph` |
| `px` / number | Absolute pixels | `200px` = 200px |

```yaml
[img] @ 00:05 | pos: (50vw, 30vh)    # relative
[img] @ 00:05 | pos: (100, 200)      # absolute pixels
```

### Anchor Coordinates

```yaml
anchor: (x, y)   # x, y ∈ [-1, 1], screen coords (y↓)
```

| Coord | Position | Coord | Position | Coord | Position |
|-------|----------|-------|----------|-------|----------|
| `(-1,-1)` | Top-left | `(0,-1)` | Top-center | `(1,-1)` | Top-right |
| `(-1, 0)` | Mid-left | `(0, 0)` | **Center** | `(1, 0)` | Mid-right |
| `(-1, 1)` | Bot-left | `(0, 1)` | Bot-center | `(1, 1)` | Bot-right |

> Keyframe `scale` is applied before anchor. `pos` takes priority over `anchor`.

### Keyframes & Easing

```yaml
[img1]:
  scale:  { 0s: 0.5, 5s: 1.2, curve: "ease_in_out" }
  pos:    { 0s: (0,0), 5s: (200,100) }
  opacity:{ 0s: 0.0, 1s: 1.0, 4s: 1.0, 5s: 0.0 }
  rotate: { 0s: 0, 5s: 90 }
```

Easing curves: `linear` (default) | `ease_in` | `ease_out` | `ease_in_out`

### Filters

| Value | Effect |
|-------|--------|
| `blackwhite` | Grayscale |
| `invert` | Invert colors |
| `mirror_x` | Horizontal flip |
| `mirror_y` | Vertical flip |
| `painting` | Oil-painting effect |

### Text Cards

```yaml
[t]: text("Content", font: songti, size: 64, bg_opacity: 0.3, color: "#FFFFFF")
```

| Parameter | Default | Description |
|-----------|---------|-------------|
| `font` | `heiti` | `songti` / `heiti` |
| `size` | Auto | Font size in px |
| `bg_opacity` | `0.0` | 0=transparent, 1=solid background |
| `color` | `#FFFFFF` | Text color |
| `bg` | `#000000` | Background color |

Auto word-wrap with `\n` for hard line breaks.

### Subtitles

```yaml
Subtitles: subtitles.srt
```

Standard SRT format, rendered at the bottom of the frame.

### Output Config

```yaml
Format: mp4, Res: 1080p, FPS: 30
```

Res options: `480p` `720p` `1080p` `4k`

## Complete Example

This is the [`demo.ktx`](demo.ktx) included in the repo — run it with `kinetix demo.ktx`:

```yaml
Define Style("intro"):
  fadein: 1s
  layer: 0
  transition: "crossfade", dur: 0.5s

[v1]: test_assets/video1.mp4 [hero]
[v2]: test_assets/video2.mp4
[img1]: test_assets/logo.png [overlay]
[a1]: test_assets/bgm.wav

[v1]  @ 00:00 | layer: 0 | style: "intro" | mute: true | speed: 2
[v2]  @ prev.end | layer: 0 | transition: "crossfade", dur: 1s
[img1] @ v1.end - 1s | duration: 3s | layer: 1 | anchor: (1, -1) | filter: "blackwhite"
[a1]  @ 00:00 | volume: -20 | role: bgm

[img1]:
  scale: { 0s: 0.3, 3s: 1.0, curve: "ease_in_out" }

Format: mp4, Res: 1080p, FPS: 30
```

## Architecture

```
parse(.ktx) → apply_styles → resolve_timeline → render(.mp4) | live_preview(ffplay) | graph(.png)
```

## License

[MIT](LICENSE)
