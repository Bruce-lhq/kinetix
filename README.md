# KinetiX (K-TeX)

声明式视频编译引擎 — 用纯文本 `.ktx` 文件描述视频，编译输出 `.mp4`。

```bash
pip install -r requirements.txt
python -m kinetix demo.ktx output.mp4
```

## 架构

```
kinetix/
  ast_nodes.py   数据结构 (Asset, TimelineEntry, KeyframeTrack, …)
  parser.py      .ktx → AST  (正则解析)
  main.py        AST 时间轴求解 + 编译管线入口
  renderer.py    AST → moviepy Clips → .mp4  (渲染)
  text_card.py   PIL 文字卡片生成
```

管线: `parse(.ktx)` → `resolve_timeline(AST)` → `render(AST, output.mp4)`

## .ktx 格式速查

### 资产声明

```yaml
[v1]:  clips/video.mp4              # 视频 (mp4/mov/avi)
[img]: clips/photo.jpg              # 图片 (jpg/png)
[bgm]: clips/music.mp3              # 音频 (mp3/wav/m4a)
[t1]:  text("第一行\n第二行", font: songti)  # 文字卡片
```

### 时间线

```yaml
# 基本放置
[v1] @ 00:00 | duration: 10s | layer: 0

# prev.end = 紧接上一个同类型片段结束
[v2] @ prev.end | layer: 0 | transition: "crossfade", dur: 0.5s

# 叠加层 (layer 1 在 layer 0 上方)
[img] @ 00:05 | duration: 4s | layer: 1 | pos: (1350, 50) | transition: "crossfade", dur: 0.3s

# 音轨 (prev.end 按音频链独立计算，不干扰视频 prev.end)
[a1] @ 00:00 | layer: 0
[a2] @ prev.end | layer: 0
```

### 时间线属性一览

| 属性 | 值 | 说明 |
|------|-----|------|
| `duration` | `10s` | 覆盖资产时长 |
| `layer` | `0`, `1`, … | 层级，0=底，数字越大越靠前 |
| `pos` | `(x, y)` | 画面位置 (左上角像素坐标) |
| `transition` | `"crossfade"` | 入场过渡 (目前仅 crossfade) |
| `fadein` | `1s` | 淡入 |
| `fadeout` | `0.5s` | 淡出 |
| `mute` | `true` | 静音视频自带音轨 |
| `volume` | `-28` | 音量调整 (dB) |

### 关键帧 (Ken Burns / 缩放动画)

```yaml
[img1]:
  scale: { 0s: 1.05, 10s: 1.0 }    # 从 105% 缩到 100% (推镜)

[pos_clip]:
  pos: { 0s: (0, 0), 5s: (100, 200) }  # 位移插值
```

`scale: 1.0` = 精确填满画布。所有图片/视频自动 cover 裁剪到输出分辨率。

### 文字卡片字体

| font 值 | 效果 |
|---------|------|
| `songti` | 宋体 |
| `heiti` | 黑体 |
| `default` | 黑体 |

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
[v1]   @ prev.end | layer: 0 | mute: true | transition: "crossfade", dur: 0.5s
[img1]  @ prev.end | duration: 5s | layer: 0 | pos: (100, 50)

[img1]:
  scale: { 0s: 0.5, 5s: 1.2 }

[a1]   @ 00:00 | layer: 0 | volume: -20

Format: mp4, Res: 1080p, FPS: 30
```

## 支持的文件格式

| 类型 | 扩展名 |
|------|--------|
| 视频 | `.mp4` `.mov` `.avi` `.mkv` |
| 图片 | `.jpg` `.jpeg` `.png` `.bmp` `.gif` |
| 音频 | `.mp3` `.wav` `.aac` `.flac` `.m4a` |
