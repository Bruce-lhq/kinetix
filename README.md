<p align="center">
  <a href="README.md"><img src="https://img.shields.io/badge/English-444" alt="English"></a>
  <a href="README_zh.md"><img src="https://img.shields.io/badge/中文版-444" alt="中文版"></a>
</p>

<p align="center">
  <img src="test_assets/logo.svg" width="180" alt="KinetiX logo">
</p>

<h1 align="center">KinetiX</h1>

<p align="center">
  <a href="LICENSE"><img src="https://img.shields.io/badge/License-MIT-yellow.svg" alt="License: MIT"></a>
  <a href="pyproject.toml"><img src="https://img.shields.io/badge/python-3.10%2B-blue.svg" alt="Python 3.10+"></a>
</p>

<p align="center">
  <strong>The LaTeX of Video</strong> — a declarative video compilation engine.
</p>

<p align="center">
  Goodbye drag-and-drop, hello code-first.<br>
  No AI magic — pure logic-driven timelines.<br>
  Ditch the GUI, embrace hacker workflows.
</p>

<p align="center">
  <img src="demo.gif" width="640" alt="KinetiX demo">
</p>

## Quick Start

**Prerequisites:** Python ≥ 3.10. [ffmpeg](https://ffmpeg.org/) (optional, for `--live` preview only).

```bash
pip install kinetix-video                # core engine
pip install kinetix-video[template,svg]  # + Jinja2 templates & SVG support
```

Grab the [demo.ktx](demo.ktx) and test assets, then:

```bash
kinetix demo.ktx                # compile to demo.mp4
```

To hack on the source:

```bash
git clone git@github.com:Bruce-lhq/kinetix-video.git
cd kinetix-video
pip install -e .
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

## Template Variables

`.ktx` files support Jinja2-style `{{ variables }}` for batch video generation:

```yaml
[t1]: text("Hi {{ user.name }}, score: {{ score }}", font: heiti, size: 56)
[v1]: {{ bg_video }}
[v1] @ 00:00 | duration: {{ duration }}s
```

```bash
# From CLI — single vars
kinetix template.ktx --var user.name=Alice --var score=95

# From CLI — JSON file
kinetix template.ktx --data vars.json

# From Python
from kinetix.main import compile_template
compile_template("template.ktx", {"user": {"name": "Alice"}, "score": 95})
```

## VS Code Extension

Syntax highlighting + frame snapshot preview for `.ktx` files.

```bash
cp -r vscode-ktx ~/.vscode/extensions/ktx-syntax-0.2.0/
```

Then `Cmd+Shift+P` → `Developer: Reload Window`. Open any `.ktx` file:

| Feature | How |
|---------|-----|
| Syntax highlighting | Automatic on `.ktx` files |
| Snapshot preview | `Ctrl+Shift+K` → enter time → frame renders in side panel |
| Command palette | `Cmd+Shift+P` → `KinetiX: Snapshot Frame at Time` |

The snapshot command renders a single frame at any timecode (e.g. `5`, `1:30`, `00:05`) as a full-resolution PNG for quick visual inspection.

## .ktx Syntax

### Asset Declarations

```yaml
[v1]:  clips/video.mp4 [tag1, tag2]     # video with tags
[img]: clips/photo.jpg [overlay]        # image
[bgm]: clips/music.mp3                  # audio
[t1]:  text("Line 1\nLine 2", font: songti, bg_opacity: 0.5)
```

Supported formats: `.mp4` `.mov` `.avi` `.mkv` | `.jpg` `.jpeg` `.png` `.bmp` `.gif` `.svg` | `.mp3` `.wav` `.aac` `.flac` `.m4a`

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
| `fadein` / `fadeout` | `1s` | Fade in/out (video + audio) |
| `mute` | `true` | Mute video track |
| `speed` | `2` | Playback speed (affects timeline) |
| `volume` | `-28` | Volume in dB |
| `role` | `voice` / `bgm` / `sfx` | Audio role (for ducking) |

> `trim_start` + `duration` can be combined without `trim_end`: the clip will span `[trim_start, trim_start + duration]`.

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
[t]: text("Content", font: songti, size: 64, bg_opacity: 0.3, color: "#FFFFFF", stroke_width: 2, stroke_color: "#00000060")
```

Parameters can appear in any order. Defaults:

| Parameter | Default | Description |
|-----------|---------|-------------|
| `font` | `heiti` | `songti` / `heiti` |
| `size` | Auto | Font size in px |
| `bg_opacity` | `0.0` | 0=transparent, 1=solid background |
| `color` | `#FFFFFF` | Text color |
| `bg` | `#000000` | Background color |
| `stroke_width` | `0` | Text outline width in px |
| `stroke_color` | `#000000` | Stroke color (supports alpha: `#00000060`) |

Auto word-wrap with `\n` for hard line breaks. Text clips render at natural size (transparent RGBA), centered on canvas by default. Use `opacity` keyframes for true transparent fade-in/out.

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

See the full [`demo.ktx`](demo.ktx) in the repo — a multi-scene promotional clip with text overlays, easing keyframes, and live preview support. Run it with:

```bash
kinetix demo.ktx              # compile to demo.mp4
kinetix demo.ktx --live       # real-time preview via ffplay
kinetix demo.ktx --graph      # generate timeline topology PNG
```

Minimal example showing all core features:

```yaml
Define Style("cinematic"):
  layer: 0
  transition: "crossfade", dur: 2.4s

[v1]: test_assets/v_chaos.mp4
[v2]: test_assets/v_order.mp4
[logo]: test_assets/logo.png
[bgm]: test_assets/bgm_epic.mp3
[t1]: text("Goodbye drag-and-drop, hello code-first editing", font: songti, size: 64,
           stroke_width: 2, stroke_color: "#00000060")

[bgm] @ 00:00 | volume: -10 | trim_start: 24s | duration: 16s | fadein: 1s | fadeout: 3s
[v1]  @ 00:00 | style: "cinematic" | mute: true | duration: 7.5s
[t1]  @ 1s    | duration: 3s
[v2]  @ v1.end - 2.4s | style: "cinematic" | mute: true | duration: 7.5s
[logo] @ v2.end - 2.5s | layer: 1 | duration: 5s

[v1]:
  scale: { 0s: 1.0, 7.5s: 1.12, curve: "ease_in" }

[t1]:
  scale: { 0s: 0.85, 3s: 1.0, curve: "ease_out" }
  opacity: { 0s: 0.0, 0.6s: 1.0, 2.4s: 1.0, 3s: 0.0, curve: "ease_in_out" }

[logo]:
  scale: { 0s: 0.22, 1.8s: 0.35, curve: "ease_out" }
  rotate: { 0s: -18, 1.8s: 0, curve: "ease_out" }
  opacity: { 0s: 0.0, 1.0s: 1.0, curve: "ease_out" }

Format: mp4, Res: 1080p, FPS: 30
```

## Architecture

```
parse(.ktx) → apply_styles → resolve_timeline → render(.mp4) | live_preview(ffplay) | graph(.png)
```

Generate a timeline topology graph with `kinetix demo.ktx --graph`:

![Timeline graph](demo_timeline.png)

## Roadmap & Contributing

KinetiX is a lean, focused MVP right now — a timeline engine that does one thing well. The fun stuff is planned. If any of these excite you, PRs are wide open.

### Template-driven video ✅

Jinja2-style `{{ variables }}` in `.ktx` files, with a Python API to feed data in.

```yaml
[t1]: text("Hi {{ user.name }}, your score is {{ score }}", font: heiti, size: 56)
```

Batch-render thousands of personalized clips from a CSV. Think: marketing, recruiting, onboarding — every SaaS company's dream.

### Plugin system

Expose a hook interface so developers can ship custom effects without touching KinetiX core.

```yaml
[v1] | plugin: "edge_glow", radius: 5, intensity: 1.2
```

CV researchers get a timeline engine; KinetiX gets their visual algorithms. Everyone wins.

### Hardware-accelerated render backend

Right now KinetiX renders frame-by-frame via moviepy on CPU. The goal: a compiler that translates `.ktx` directly into an FFmpeg filtergraph, hitting NVENC / VideoToolbox for native-speed GPU encodes. C++ and Rust performance nerds, this one's for you.

### Web playground

Monaco editor on the left, Wasm-powered preview on the right. Write `.ktx` in the browser, see the result instantly. No Python install required. Frontend hackers, assemble.

### Procedural math animations (Manim)

Support `manim("scene.py")` as an asset type. KinetiX pre-renders the Manim scene into a cached `.mp4` under `.kinetix_cache/`, then treats it like any other video clip. Math educators, this one's for you.

### Native LLM bindings

```python
kinetix.ask("speed up this video by 2x and add a fade-out at the end")
```

A programmatic API that lets LLMs read and mutate the KinetiX AST in memory. If you're building AI agents, this is your playground.

---

Something click? Open an issue, start a discussion, or send a PR. The core is intentionally small — that's where you come in.

## License

[MIT](LICENSE)
