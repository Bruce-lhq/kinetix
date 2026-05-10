# KinetiX — AI Agent 项目指南

> 本文件供 AI 编码助手快速理解项目，指导源码修改后的同步维护。

## 一句话概述

Python 声明式视频编译器: `.ktx` 文本 → 正则解析 AST → moviepy 渲染 `.mp4`。

## 项目结构

```
kinetix/
  __init__.py      版本号 (__version__)
  __main__.py      python -m kinetix 入口
  ast_nodes.py     数据类: Asset, TimelineEntry, KeyframeTrack, OutputConfig, KinetiXDocument
  parser.py        parse(source:str) → KinetiXDocument   (正则匹配)
  main.py          resolve_timeline(doc) + compile_ktx(path) 编译管线
  renderer.py      render(doc, output) → moviepy 合成导出
  text_card.py     render_text_card() → PIL 生成文字图片 → numpy
  subtitles.py     parse_srt(path) → list[Subtitle]  SRT 字幕解析
  cli.py           argparse CLI (kinetix 命令)
pyproject.toml     包配置 (console_scripts: kinetix)
requirements.txt   moviepy, numpy, Pillow
README.md          用户文档 (.ktx 格式速查)
```

## 核心数据流

```
.ktx 文本
  → parser.parse() → KinetiXDocument (assets + timeline + output + subtitle_path)
  → main.resolve_timeline()   (prev.end → 绝对秒数, 音频/视频分开求解)
  → main._merge_keyframe_entries()  (合并同名 timeline entry 的关键帧)
  → renderer.render()
      if preview_range: 过滤 + _trim_to_preview() 裁剪偏移
      if subtitle_path:  parse_srt() → _build_subtitle_clips() → TextClip
      video/image → _build_video_clip()  (cover → speed → crop → trim → anchor → keyframes → fade → mute)
      text        → _build_text_clip()   (PIL → ImageClip)
      audio       → _build_audio_clip()  (trim → speed → volume)
      → CompositeVideoClip + CompositeAudioClip → write_videofile
```

## 关键设计决策

- 图片自动 `ImageOps.fit(canvas_size)` cover 裁剪，scale=1.0 = 满屏
- 视频自动 `resized(cover_scale)` 铺满画布
- 音频 prev.end 独立链式计算，不受视频 layer 影响
- Anchor 坐标系统: `(x, y)` x,y∈[-1,1]，屏幕坐标（y↓）；keyframe scale 先于 anchor 执行
- 关键帧只做线性插值 (_lerp / _lerp_tuple)
- 文字卡片运行时 PIL 生成，不落盘
- 预览模式 (`--preview`): 过滤时间窗内片段 + `_trim_to_preview` 裁剪偏移 → 字幕也参与裁剪
- `--no-subtitles`: 跳过 SRT 字幕加载

## 修改源码后的维护清单

当你修改了以下文件，**必须**同步更新对应内容:

### 修改 `parser.py` (新增语法/属性)

1. **ast_nodes.py** — 新增字段到对应 dataclass
2. **renderer.py** — 在 `_build_video_clip` / `_build_audio_clip` 中消费新字段
3. **README.md** — 在"时间线属性一览"表格中添加新行
4. **本文件** — 如涉及架构变化，更新"核心数据流"和"关键设计决策"

### 修改 `renderer.py` (新增效果/输出)

1. 确认 moviepy 版本支持新 API → 可能需更新 `requirements.txt`
2. **README.md** — 如用户可见，添加到格式速查
3. **本文件** — 如涉及管线变化，更新"核心数据流"

### 修改 `ast_nodes.py` (新增数据结构)

1. **parser.py** — 解析新结构
2. **renderer.py** — 渲染新结构
3. **README.md** + **本文件** — 同步更新

### 依赖变更

- 新增 pip 包 → 追加到 `requirements.txt`，注明最低版本
- 升级包版本 → 更新 `requirements.txt` 中的版本约束

### 版本号

- 修改 `kinetix/__init__.py` 中的 `__version__`
- 语义: MAJOR.MINOR.PATCH (功能新增 → MINOR, bug修复 → PATCH)

## 每次修改后必须执行的收尾命令

**每次修改源码后，必须执行以下两步，不可跳过：**

1. **更新本文件** — 如果修改涉及架构/数据流/新增文件/设计决策变化，同步更新 AGENTS.md 相应章节
2. **Git 提交** — 所有修改提交到仓库：

```bash
git add -A
git commit -m "<type>: <简短描述>"
```

提交类型:
- `feat:` 新功能
- `fix:` 修复 bug
- `docs:` 文档更新
- `refactor:` 代码重构

示例: `feat: add crop/trim support to timeline entries`

## 快速定位指南

| 我想… | 看这个文件 | 关键函数/类 |
|-------|-----------|------------|
| 加新资产类型 | `ast_nodes.py` → `AssetType` | `parser.py` → `RE_ASSET`, `RE_TEXT_ASSET` |
| 加新时间线属性 | `ast_nodes.py` → `TimelineEntry` | `parser.py` → `_parse_timeline()` |
| 加新转场/滤镜 | `renderer.py` → `_apply_fade()` | `vfx.*` |
| 加新关键帧属性 | `renderer.py` → `_apply_keyframes()` | 新建 `_apply_xxx_keyframes()` |
| 改文字卡片样式 | `text_card.py` → `render_text_card()` | `_FONTS` dict |
| 改时间轴解析逻辑 | `main.py` → `resolve_timeline()` | `_probe_duration()` |
| 改预览/拆分逻辑 | `renderer.py` → `_trim_to_preview()` | `preview_range` 参数 |
| 改 SRT 字幕解析 | `subtitles.py` → `parse_srt()` | `_build_subtitle_clips()` |
| 改 CLI 参数 | `cli.py` → `main()` | `_parse_time()`, `_parse_range()` |
| 调试解析 | `parser.py` → `parse()` | 在对应 `if m:` 分支加 print |
