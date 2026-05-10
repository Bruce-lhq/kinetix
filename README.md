# KinetiX (K-TeX)

声明式视频编译引擎 — 用纯文本 `.ktx` 文件描述视频，编译输出 `.mp4`。

```bash
pip install -r requirements.txt
kinetix demo.ktx                 # 全量编译
kinetix demo.ktx output.mp4      # 指定输出
kinetix demo.ktx --preview 01:00-02:00   # 快速预览片段
kinetix demo.ktx --no-subtitles          # 跳过字幕
```

## 架构

```
kinetix/
  ast_nodes.py   数据结构 (Asset, TimelineEntry, KeyframeTrack, …)
  parser.py      .ktx → AST  (正则解析)
  main.py        AST 时间轴求解 + 编译管线入口
  renderer.py    AST → moviepy Clips → .mp4  (渲染合成)
  text_card.py   PIL 文字卡片生成
  subtitles.py   SRT 字幕解析
  cli.py         命令行入口 (argparse)
```

管线: `parse(.ktx)` → `resolve_timeline(AST)` → `_merge_keyframe_entries(AST)` → `render(AST, .mp4)`

## .ktx 格式速查

### 资产声明

```yaml
[v1]:  clips/video.mp4              # 视频 (mp4/mov/avi)
[img]: clips/photo.jpg              # 图片 (jpg/png)
[bgm]: clips/music.mp3              # 音频 (mp3/wav/m4a)
[t1]:  text("第一行\n第二行", font: songti)  # 文字卡片
```

### 文字卡片

```yaml
[t]: text("内容", font: songti, size: 64)
```

| 参数 | 默认 | 说明 |
|------|------|------|
| `font` | `heiti` | `songti` / `heiti` |
| `size` | 自动 | 字号 px |

### 时间线

```yaml
# 基本放置
[v1] @ 00:00 | duration: 10s | layer: 0

# prev.end = 紧接上一个同类型片段结束（音频/视频独立链式计算）
[v2] @ prev.end | layer: 0 | transition: "crossfade", dur: 0.5s

# 叠加层 (layer 1 在 layer 0 上方)
[img] @ 00:05 | duration: 4s | layer: 1 | anchor: (1, -1) | transition: "crossfade", dur: 0.3s

# 音轨
[a1] @ 00:00 | layer: 0
[a2] @ prev.end | layer: 0

# 拆分（同一资产多次引用，各裁不同时间段）
[v_part1] @ 00:00 | layer: 0 | trim_start: 0s | trim_end: 5s
[v_part2] @ prev.end | layer: 0 | trim_start: 5s | trim_end: 10s
```

### 时间线属性一览

| 属性 | 值 | 说明 |
|------|-----|------|
| `duration` | `10s` | 覆盖资产时长 |
| `layer` | `0`, `1`, … | 层级，0=底，数字越大越靠前 |
| `pos` | `(x, y)` | 绝对像素位置（左上角坐标） |
| `anchor` | `(0, 0)` | 相对锚点坐标，见下表 |
| `crop` | `(x, y, w, h)` | 画面裁剪，裁出矩形区域 |
| `trim_start` | `2s` | 从第N秒开始播放（时间裁剪） |
| `trim_end` | `8s` | 播放到第N秒截止（时间裁剪） |
| `transition` | `"crossfade"` | 入场过渡叠化 |
| `fadein` | `1s` | 淡入 |
| `fadeout` | `0.5s` | 淡出 |
| `mute` | `true` | 静音视频自带音轨 |
| `speed` | `2` | 播放倍速 |
| `volume` | `-28` | 音量 dB 调整 |

### Anchor 坐标系

```yaml
anchor: (x, y)   # x, y ∈ [-1, 1]，屏幕坐标（y 正方向向下）
```

| 坐标 | 位置 |
|------|------|
| `(-1, -1)` | 左上角 |
| `( 0, -1)` | 顶部居中 |
| `( 1, -1)` | 右上角 |
| `(-1,  0)` | 左侧居中 |
| `( 0,  0)` | 正中（默认） |
| `( 1,  0)` | 右侧居中 |
| `(-1,  1)` | 左下角 |
| `( 0,  1)` | 底部居中 |
| `( 1,  1)` | 右下角 |

> `anchor` 基于应用 keyframe scale 后的实际 clip 尺寸计算。`pos` 和 `anchor` 不可同时使用——`pos` 优先。

### 关键帧

```yaml
[img1]:
  scale: { 0s: 1.05, 10s: 1.0 }             # Ken Burns 推镜
  pos: { 0s: (0, 0), 5s: (100, 200) }       # 位移插值
  opacity: { 0s: 0.0, 1s: 1.0, 4s: 1.0, 5s: 0.0 }  # 淡入淡出
```

`scale: 1.0` = 精确填满画布。所有图片/视频自动 cover 裁剪到输出分辨率。

### 字幕

```yaml
Subtitles: path/to/subtitles.srt
```

支持标准 SRT 格式。渲染时自动叠在画面底部（layer=999），预览模式下会自动跟随时间轴偏移。`--no-subtitles` 可跳过。

### 输出配置

```yaml
Format: mp4, Res: 1080p, FPS: 30
```

Res 可选: `480p` `720p` `1080p` `4k`

## 完整示例

```yaml
# assets
[v1]: video.mp4
[img1]: logo.png
[a1]: bgm.mp3
[title]: text("Hello\nWorld")

# timeline
[title] @ 00:00 | duration: 3s | layer: 0 | fadein: 1s
[v1]   @ prev.end | layer: 0 | mute: true | trim_start: 0s | trim_end: 10s
[img1] @ prev.end | duration: 5s | layer: 0 | anchor: (1, -1) | transition: "crossfade", dur: 0.5s

[img1]:
  scale: { 0s: 0.5, 5s: 1.2 }

[a1]   @ 00:00 | layer: 0 | volume: -20

Subtitles: subtitles.srt
Format: mp4, Res: 1080p, FPS: 30
```

## CLI 参考

```
kinetix <input.ktx> [output.mp4] [options]

Options:
  --preview START-END   仅渲染时间段 (例: --preview 00:30-01:00)
  --no-subtitles        跳过 SRT 字幕
```

## 支持的文件格式

| 类型 | 扩展名 |
|------|--------|
| 视频 | `.mp4` `.mov` `.avi` `.mkv` |
| 图片 | `.jpg` `.jpeg` `.png` `.bmp` `.gif` |
| 音频 | `.mp3` `.wav` `.aac` `.flac` `.m4a` |
