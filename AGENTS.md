# KinetiX — AI Agent 项目指南 (Pro Edition)

> 本文件供 AI 编码助手快速理解项目，指导源码修改后的同步维护。

## 一句话概述

Python 声明式视频编译器: `.ktx` 文本 → 正则解析 AST → moviepy 渲染 `.mp4`。Pro 版支持样式宏、表达式时间轴、物理缓动关键帧、实时预览。

## 项目结构

```
kinetix/
  __init__.py      版本号 (__version__)
  __main__.py      python -m kinetix 入口 (from .cli import main)
  ast_nodes.py     数据类: Asset, Style, KeyframeTrack (含 Easing), TimelineEntry, KinetiXDocument
  parser.py        parse(source) → KinetiXDocument  (正则 + Define Style 块解析)
  main.py          _apply_styles + resolve_timeline (表达式求解 + 音频避让) + compile_ktx
  template.py      Jinja2 模板渲染 (render_template, --var / --data CLI)
  renderer.py      render / live_preview → moviepy + ffplay, easing + rotate + filter
  text_card.py     PIL 渲染 (自动换行, 行间距, 半透明背景块, anchor='lt')
  subtitles.py     parse_srt(path) → list[Subtitle]
  timeline_graph.py    generate_timeline_graph(doc) → PNG 时间轴拓扑图 (同轨叠化高亮)
  cli.py           argparse CLI (kinetix --live / --preview / --graph / --no-subtitles)
pyproject.toml     包配置 (console_scripts)
requirements.txt   moviepy>=2.1, numpy>=1.24, Pillow>=10
README.md          用户文档
```

## 核心数据流

```
.ktx 文本
  → template.render_template(source, variables)  (Jinja2 模板替换, 可选)
  → parser.parse() → KinetiXDocument (assets + styles + timeline + output + subtitle_path)
  → main._resolve_asset_paths(doc, base_dir)  (相对路径 → 绝对路径)
  → main._apply_styles(doc)            (style 属性合并到引用的 entry)
  → main.resolve_timeline(doc)         (prev.end / v1.end-1s → 绝对秒数, speed 影响 duration)
  → main._merge_keyframe_entries(doc)  (合并同名 entry 的关键帧)
  → main._compute_audio_ducking(doc)   (识别 voice/bgm 重叠区间)
  → renderer.render() / live_preview() / graphviz_timeline.generate_timeline_graph()
```

## 关键设计决策

### 渲染层
- 图片以**原始尺寸加载**（保留 alpha 通道），**始终先 contain 到画布** (`min(cw/iw, ch/ih)`)，关键帧 scale 在此基础上操作
- `.svg` 通过 `cairosvg` 在内存中以 2×画布分辨率渲染为 RGBA 数组（可选依赖 `[svg]`）
- 视频 `resized(cover_scale)` 铺满画布; **无损适配**: 基于原始比例 cover, 确保 4K→1080p 无畸变
- 所有中间处理 (Crop/Resize/Trim) 基于原始素材分辨率比例

### 时间轴
- 音频 prev.end 独立链式计算, 不与视频 layer 混合
- 表达式时间 `v1.end - 1s` 在 resolve 阶段求解, 支持速度倍率修正
- Style 属性合并顺序: entry 显式值 > style 预设值 > 默认值

### 关键帧
- 支持 linear / ease_in / ease_out / ease_in_out 四种缓动
- 缓动基于 Sine 函数: ease_in = 1-cos(t·π/2), ease_out = sin(t·π/2), ease_in_out = (1-cos(t·π))/2
- scale / opacity / pos / rotate 四种属性, 线性插值 + 缓动叠加
- rotate 使用 moviepy 内置 `vfx.Rotate`（保留 mask 透明通道）
- scale 返回绝对像素尺寸 `(max(w*scale, 1), max(h*scale, 1))`，防止 scale=0 导致零尺寸错误

### Anchor / 定位
- 屏幕坐标 `(x,y)∈[-1,1]`, y↓. `(0,0)` = 居中
- 无 `pos` 且 anchor 为默认 `(0,0)` 时，使用 `with_position(('center', 'center'))` **动态居中** — 每帧重算位置，适配关键帧驱动的尺寸变化
- 有 `pos` 时固定位置优先于 anchor
- 图片先 contain 再定位、再应用关键帧（尺寸变化时居中跟随）

### 模板
- `.ktx` 支持 Jinja2 语法 `{{ variables }}`
- `--var key=value` 命令行传参, `--data file.json` 批量加载
- Python API: `compile_template(path, vars_dict)` (→ `kinetix/main.py`)
- `jinja2` 为可选依赖 (`pip install kinetix-video[template]`)
- 无模板语法时零开销跳过, 不依赖 jinja2

### 预览
- `--preview START-END`: 过滤窗口内片段 + `_trim_to_preview` 偏移归零, 字幕跟随
- `--live`: 调用 `clip.preview()` 直接推送 ffplay, 无重编码, 延迟极低

### 文本
- PIL 运行时生成, 不落盘
- 自动换行, 行间距可调 (line_spacing), 可选半透明背景块 (bg_opacity)
- **自然尺寸模式** (`natural_size=True`)：以文本实际尺寸渲染（透明 RGBA），由调用方定位居中
- **全画布模式** (`natural_size=False`)：全画布渲染，文本居中，用于 bg_opacity>0 的背景块场景
- 文本参数（font/size/bg/color/bg_opacity/stroke_width/stroke_color）**顺序无关**，通过两步解析实现
- `stroke_width` / `stroke_color` 支持文字描边，PIL native `draw.text(stroke_width=, stroke_fill=)` 实现
- 文字透明渐现用 `opacity` 关键帧（不要用 `vfx.FadeIn`，后者叠黑色遮罩）

### 音频
- `fadein` / `fadeout` 使用 `afx.AudioFadeIn` / `afx.AudioFadeOut`（`vfx.FadeIn` 不支持 audio clip）
- `trim_start` + `duration` 组合：同时存在时自动计算 `trim_end = trim_start + duration`
- BGM 建议用 `trim_start` 跳过前奏直接从高潮段落切入

## 修改源码后的维护清单

当你修改了以下文件，**必须**同步更新对应内容:

### 修改 `parser.py` (新增语法/属性)

1. **README.md** — 时间线属性表 / 语法速查 添加新行（**最先做**）
2. **ast_nodes.py** — 新增字段到对应 dataclass
3. **renderer.py** — 消费新字段
4. **本文件** — 更新核心数据流和设计决策

### 修改 `renderer.py` (新增效果)

1. 确认 moviepy API → 可能需更新 `requirements.txt`
2. **README.md** — 用户可见特性
3. **本文件** — 管线变化

### 修改 `ast_nodes.py` (新增数据结构)

1. **parser.py** — 解析
2. **renderer.py** — 渲染
3. **README.md** + **本文件** — 同步

### 修改 `text_card.py` (新增文本渲染参数)

1. **ast_nodes.py** → `Asset` 新增字段
2. **parser.py** → `_parse_text_asset()` 解析新参数
3. **renderer.py** → `_build_text_clip()` 传入 `render_text_card()`
4. **README.md** + **本文件** — 文本参数表同步

### 修改 `renderer.py` (音频处理)

1. 音轨效果用 `afx.*`（`from moviepy import afx`），不使用 `vfx.*`
2. `afx.AudioFadeIn(duration)` / `afx.AudioFadeOut(duration)` — 音轨渐强/渐弱
3. 音量用 `10 ** (dB / 20.0)` 转换倍率 → `clip.with_volume_scaled()`

### 依赖变更

- 新增包 → 追加 `requirements.txt` + 最低版本
- 升级版本 → 更新约束

### 版本号

- `kinetix/__init__.py` → `__version__`, 语义: MAJOR.MINOR.PATCH

## 每次修改后必须执行

1. **更新 README.md** — 用户可见的功能/语法/属性/CLI 变化时**必须**同步：新增时间线属性、新语法、新 CLI flag、新滤镜名、缓动名等。
2. **更新本文件** — 架构/数据流/设计决策变化时同步
3. **Git 提交**:

```bash
git add -A
git commit -m "<type>: <简短描述>"
```

类型: `feat:` / `fix:` / `docs:` / `refactor:`

## 快速定位指南

| 我想… | 看这个文件 | 关键函数/类 |
|-------|-----------|------------|
| 加新资产类型 | `ast_nodes.py` → `AssetType` | `parser.py` → `RE_ASSET`, `RE_TEXT_ASSET` |
| 加新时间线属性 | `ast_nodes.py` → `TimelineEntry` | `parser.py` → `_parse_timeline()` |
| 加新 Style 属性 | `ast_nodes.py` → `Style` | `parser.py` → `_apply_style_prop()` |
| 加新缓动曲线 | `renderer.py` → `_apply_easing()` | 添加 math 公式 |
| 加新关键帧属性 | `renderer.py` → `_apply_keyframes()` | 新建 `_apply_xxx_keyframes()` |
| 加新全局滤镜 | `renderer.py` → `_FILTER_MAP` | 映射 vfx 类 |
| 改表达式时间解析 | `main.py` → `_resolve_start_time()` | `RE_EXPR`, `_RE_REF_OP` |
| 改 Style 解析/合并 | `parser.py` → `_parse_style_block()` | `main.py` → `_apply_styles()` |
| 改文字卡片渲染 | `text_card.py` → `render_text_card()` | `_wrap_line()`, `natural_size`, `stroke_width`, `stroke_color` 参数 |
| 改文字描边 | `ast_nodes.py` → `Asset.text_stroke_*` | `parser.py` → `stroke_width/stroke_color`, `renderer.py` 传入 |
| 改旋转效果 | `renderer.py` → `_apply_rotate_keyframes()` | 使用 `vfx.Rotate` |
| 改音频渐变 | `renderer.py` → `_build_audio_clip()` | 使用 `afx.AudioFadeIn` / `afx.AudioFadeOut` |
| 改图片缩放 | `renderer.py` → `_build_video_clip()` (image 分支) | contain 优先, keyframe scale 叠加上层 |
| 改文本定位 | `renderer.py` → `_build_text_clip()` | natural_size 渲染, 动态居中 |
| 改 SRT 字幕 | `subtitles.py` → `parse_srt()` | `_build_subtitle_clips()` |
| 改 CLI | `cli.py` → `main()` | `--live` / `--preview` / `--no-subtitles` |
| 改实时预览 | `renderer.py` → `live_preview()` | `clip.preview()` |
| 改时间轴图 | `graphviz_timeline.py` → `generate_timeline_graph()` | `rows`, y-axis ordering |
| 改音频避让 | `main.py` → `_compute_audio_ducking()` | `track_role` |
| 改路径解析 | `main.py` → `_resolve_asset_paths()` | `compile_ktx` / `live_mode` / `graph_mode` |
| 改模板变量 | `template.py` → `render_template()` | `main.py` → `_prepare()`, `cli.py` → `--var`/`--data` |
| 加 CLI 选项 | `cli.py` → `main()` | `argparse` 参数 → 传入 `compile_ktx`/`live_mode`/`graph_mode` |
