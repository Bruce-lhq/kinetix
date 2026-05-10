# KinetiX (K-TeX) Pro

声明式视频编译引擎 — 用纯文本 `.ktx` 文件描述视频，编译输出 `.mp4`。

```bash
pip install -r requirements.txt
kinetix demo.ktx                     # 全量编译
kinetix demo.ktx output.mp4          # 指定输出路径
kinetix demo.ktx --live              # 实时预览窗口（无重编码）
kinetix demo.ktx --preview 01:00-02:00  # 快速预览片段
kinetix demo.ktx --no-subtitles      # 跳过字幕
```

## 架构

```
kinetix/
  ast_nodes.py   数据结构 (Asset, Style, KeyframeTrack, Easing, …)
  parser.py      .ktx → AST  (正则 + Define Style 块解析)
  main.py        style 合并 + 表达式时间轴求解 + 音频避让
  renderer.py    easing 插值 + rotate + filter + live preview
  text_card.py   PIL 渲染 (自动换行 / 行间距 / 半透明背景)
  subtitles.py   SRT 字幕解析
  cli.py         argparse CLI
```

管线: `parse(.ktx)` → `apply_styles` → `resolve_timeline` → `render(.mp4)` 或 `live_preview(ffplay)`

## .ktx 格式速查

### 资产声明

```yaml
[v1]:  clips/video.mp4 [tag1, tag2]     # 视频，带标签
[img]: clips/photo.jpg [overlay]        # 图片
[bgm]: clips/music.mp3                  # 音频
[t1]:  text("第一行\n第二行", font: songti, bg_opacity: 0.5)
#       文字卡片：支持 \n 换行，bg_opacity 控制背景半透明块
```

### Style 宏定义

```yaml
Define Style("intro"):
  fadein: 1s
  layer: 0
  transition: "crossfade", dur: 0.5s
  filter: "blackwhite"

# 在时间线条目中引用
[v1] @ 00:00 | style: "intro" | mute: true
```

Style 支持属性: `fadein`, `fadeout`, `transition`, `volume`, `mute`, `layer`, `anchor`, `filter`, `speed`。条目显式值覆盖 Style 预设值。

### 时间线

```yaml
# 表达式时间 — 锚定到任意命名片段
[v2] @ v1.end - 1s | layer: 0
[a1] @ v1.start + 2s | layer: 0

# prev.end 仍然可用（音频/视频独立链式计算）
[v3] @ prev.end | layer: 0

# 拆分：同一资产不同时间段
[v_part1] @ 00:00 | trim_start: 0s | trim_end: 5s
[v_part2] @ prev.end | trim_start: 5s | trim_end: 10s

# 音频避让标记
[voice] @ 00:00 | role: voice
[bgm]   @ 00:00 | role: bgm | volume: -20
```

### 时间线属性一览

| 属性 | 值 | 说明 |
|------|-----|------|
| `duration` | `10s` | 覆盖资产时长 |
| `layer` | `0`, `1`, … | 层级，0=底 |
| `pos` | `(x, y)` 或 `(50vw, 30vh)` | 像素位置或相对单位位置 |
| `anchor` | `(0, 0)` | 相对锚点，见坐标系表 |
| `style` | `"intro"` | 引用 Define Style 宏 |
| `crop` | `(x, y, w, h)` | 画面裁剪 |
| `trim_start` | `2s` | 播放起点（时间裁剪） |
| `trim_end` | `8s` | 播放终点 |
| `filter` | `"blackwhite"` | 全局滤镜 |
| `transition` | `"crossfade"` | 入场叠化 |
| `fadein` / `fadeout` | `1s` | 淡入淡出 |
| `mute` | `true` | 静音视频音轨 |
| `speed` | `2` | 倍速（影响时间轴计算） |
| `volume` | `-28` | 音量 dB |
| `role` | `voice` / `bgm` / `sfx` | 音频角色（避让用） |

### 位置单位 (CSS-like relative units)

`pos` 支持混合单位，改变输出分辨率时比例自动保持：

| 单位 | 含义 | 示例 |
|------|------|------|
| `vw` | 画布宽度的 % | `50vw` = 画布宽度的一半 |
| `vh` | 画布高度的 % | `30vh` = 画布高度的 30% |
| `pw` | 资产原始宽度的 % | `10pw` = 图片/视频宽度的 10% |
| `ph` | 资产原始高度的 % | `5ph` |
| `px` / 纯数字 | 绝对像素 | `200px` = 200px |

```yaml
# 居中 50% 宽, 30% 高
[v1] @ 00:00 | pos: (50vw, 30vh)
# 混合: 水平 10% 资产宽度, 垂直 200px
[img] @ 00:05 | pos: (10pw, 200px)
# 纯数字 = 绝对像素 (向后兼容)
[img] @ 00:05 | pos: (100, 200)
```

> 输出从 1080p 改 4K 时，`50vw` 自动从 960px → 1920px，无需手动调整。

### Anchor 坐标系

```yaml
anchor: (x, y)   # x, y ∈ [-1, 1]，屏幕坐标（y↓）
```

| 坐标 | 位置 | 坐标 | 位置 | 坐标 | 位置 |
|------|------|------|------|------|------|
| `(-1,-1)` | 左上 | `(0,-1)` | 顶中 | `(1,-1)` | 右上 |
| `(-1, 0)` | 左中 | `(0, 0)` | **正中** | `(1, 0)` | 右中 |
| `(-1, 1)` | 左下 | `(0, 1)` | 底中 | `(1, 1)` | 右下 |

> keyframe scale 先于 anchor 计算，`pos` 和 `anchor` 不可同时使用（`pos` 优先）。

### 关键帧 & 缓动

```yaml
[img1]:
  scale:  { 0s: 0.5, 5s: 1.2, curve: "ease_in_out" }   # 缓动缩放
  pos:    { 0s: (0,0), 5s: (200,100) }                   # 位移
  opacity:{ 0s: 0.0, 1s: 1.0, 4s: 1.0, 5s: 0.0 }       # 透明度
  rotate: { 0s: 0, 5s: 90 }                              # 旋转（度）
```

缓动曲线:

| `curve` | 效果 |
|---------|------|
| `linear` | 匀速（默认） |
| `ease_in` | 加速进入，`1-cos(t·π/2)` |
| `ease_out` | 减速停止，`sin(t·π/2)` |
| `ease_in_out` | 平滑 S 曲线，`(1-cos(t·π))/2` |

### 全局滤镜

| `filter` 值 | 效果 |
|-------------|------|
| `blackwhite` | 黑白 |
| `invert` | 反色 |
| `mirror_x` | 水平翻转 |
| `mirror_y` | 垂直翻转 |
| `painting` | 油画效果 |

### 文字卡片参数

```yaml
[t]: text("内容", font: songti, size: 64, bg_opacity: 0.3, color: "#FFFFFF")
```

| 参数 | 默认 | 说明 |
|------|------|------|
| `font` | `heiti` | `songti` / `heiti` |
| `size` | 自动 | 像素字号 |
| `bg_opacity` | `0.0` | 0=透明, 1=实色背景块 |
| `color` | `#FFFFFF` | 文字颜色 hex |
| `bg` | `#000000` | 背景色 hex |

自动支持中文换行，`\n` 强制断行。

### 字幕

```yaml
Subtitles: subtitles.srt
```

标准 SRT 格式，自动叠在画面底部，预览模式下跟随时间轴偏移。`--no-subtitles` 跳过。

### 输出配置

```yaml
Format: mp4, Res: 1080p, FPS: 30
```

Res 可选: `480p` `720p` `1080p` `4k`

## 完整 Pro 示例

```yaml
Define Style("intro"):
  fadein: 1s
  transition: "crossfade", dur: 0.5s

[v1]: video.mp4 [hero, intro]
[img1]: logo.png [overlay]
[t1]: text("Hello\nWorld", font: songti, bg_opacity: 0.4)

[t1]  @ 00:00 | duration: 3s | style: "intro"
[v1]  @ prev.end | style: "intro" | mute: true | speed: 2
[img1]@ v1.end - 1s | duration: 3s | layer: 1 | anchor: (1,-1) | filter: "blackwhite"

[img1]:
  scale: { 0s: 0.3, 3s: 1.0, curve: "ease_in_out" }

Subtitles: subtitles.srt
Format: mp4, Res: 1080p, FPS: 30
```

## CLI 参考

```
kinetix <input.ktx> [output.mp4] [options]

Options:
  --live               打开 ffplay 实时预览窗口（无编码，延迟极低）
  --preview START-END  仅渲染时间片段（例: --preview 00:30-01:00）
  --graph [path]       生成时间轴拓扑图 PNG（不渲染视频）
  --no-subtitles       跳过 SRT 字幕渲染
```

## 支持的文件格式

| 类型 | 扩展名 |
|------|--------|
| 视频 | `.mp4` `.mov` `.avi` `.mkv` |
| 图片 | `.jpg` `.jpeg` `.png` `.bmp` `.gif` |
| 音频 | `.mp3` `.wav` `.aac` `.flac` `.m4a` |
