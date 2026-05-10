# KinetiX — AI Agent 项目指南 (Pro Edition)

> 本文件供 AI 编码助手快速理解项目，指导源码修改后的同步维护。

## 一句话概述

Python 声明式视频编译器: `.ktx` 文本 → 正则解析 AST → moviepy 渲染 `.mp4`。Pro 版支持样式宏、表达式时间轴、物理缓动关键帧、实时预览。

## 项目结构

```
kinetix/
  __init__.py      版本号 (__version__)
  __main__.py      python -m kinetix 入口
  ast_nodes.py     数据类: Asset, Style, KeyframeTrack (含 Easing), TimelineEntry, KinetiXDocument
  parser.py        parse(source) → KinetiXDocument  (正则 + Define Style 块解析)
  main.py          _apply_styles + resolve_timeline (表达式求解 + 音频避让) + compile_ktx
  renderer.py      render / live_preview → moviepy + ffplay, easing + rotate + filter
  text_card.py     PIL 渲染 (自动换行, 行间距, 半透明背景块)
  subtitles.py     parse_srt(path) → list[Subtitle]
  cli.py           argparse CLI (kinetix --live / --preview / --no-subtitles)
pyproject.toml     包配置 (console_scripts)
requirements.txt   moviepy>=2.1, numpy>=1.24, Pillow>=10
README.md          用户文档
```

## 核心数据流

```
.ktx 文本
  → parser.parse() → KinetiXDocument (assets + styles + timeline + output + subtitle_path)
  → main._apply_styles(doc)            (style 属性合并到引用的 entry)
  → main.resolve_timeline(doc)         (prev.end / v1.end-1s / v1.start+2s → 绝对秒数, speed 影响 duration)
  → main._merge_keyframe_entries(doc)  (合并同名 entry 的关键帧)
  → main._compute_audio_ducking(doc)   (识别 voice/bgm 重叠区间)
  → renderer.render() 或 renderer.live_preview()
      video/image → _build_video_clip()  (cover → speed → crop → trim → anchor ← keyframes → filter → fade → mute)
      text        → _build_text_clip()   (PIL + 自动换行 + 半透明背景块)
      audio       → _build_audio_clip()  (trim → speed → volume)
      → CompositeVideoClip + CompositeAudioClip → write_videofile 或 preview()
```

## 关键设计决策

### 渲染层
- 图片 `ImageOps.fit(canvas_size)` cover 裁剪, scale=1.0=满屏
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
- rotate 使用 PIL 逐帧旋转 (PILImage.rotate)

### Anchor
- 屏幕坐标 `(x,y)∈[-1,1]`, y↓
- keyframe scale 先于 anchor 计算 (确保缩放后定位准确)

### 预览
- `--preview START-END`: 过滤窗口内片段 + `_trim_to_preview` 偏移归零, 字幕跟随
- `--live`: 调用 `clip.preview()` 直接推送 ffplay, 无重编码, 延迟极低

### 文本
- PIL 运行时生成, 不落盘
- 自动换行, 行间距可调 (line_spacing), 可选半透明背景块 (bg_opacity)

## 修改源码后的维护清单

当你修改了以下文件，**必须**同步更新对应内容:

### 修改 `parser.py` (新增语法/属性)

1. **ast_nodes.py** — 新增字段到对应 dataclass
2. **renderer.py** — 消费新字段
3. **README.md** — 时间线属性表添加新行
4. **本文件** — 更新核心数据流和设计决策

### 修改 `renderer.py` (新增效果)

1. 确认 moviepy API → 可能需更新 `requirements.txt`
2. **README.md** — 用户可见特性
3. **本文件** — 管线变化

### 修改 `ast_nodes.py` (新增数据结构)

1. **parser.py** — 解析
2. **renderer.py** — 渲染
3. **README.md** + **本文件** — 同步

### 依赖变更

- 新增包 → 追加 `requirements.txt` + 最低版本
- 升级版本 → 更新约束

### 版本号

- `kinetix/__init__.py` → `__version__`, 语义: MAJOR.MINOR.PATCH

## 每次修改后必须执行

1. **更新本文件** — 架构/数据流/设计决策变化时同步
2. **Git 提交**:

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
| 改文字卡片渲染 | `text_card.py` → `render_text_card()` | `_wrap_line()` |
| 改 SRT 字幕 | `subtitles.py` → `parse_srt()` | `_build_subtitle_clips()` |
| 改 CLI | `cli.py` → `main()` | `--live` / `--preview` / `--no-subtitles` |
| 改实时预览 | `renderer.py` → `live_preview()` | `clip.preview()` |
| 改音频避让 | `main.py` → `_compute_audio_ducking()` | `track_role` |
