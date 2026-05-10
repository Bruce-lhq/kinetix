"""Generate multi-track timeline (剪映-style).

Tracks: Video (by layer), Text, Audio (one continuous row).
Each clip = colored horizontal bar at exact time position.
"""

from __future__ import annotations

import matplotlib
matplotlib.use("Agg")

import matplotlib.pyplot as plt
import matplotlib.patches as mpatches

from .ast_nodes import AssetType, KinetiXDocument

_COLORS = {
    AssetType.VIDEO: "#5B9BD5",
    AssetType.IMAGE: "#70AD47",
    AssetType.AUDIO: "#ED7D31",
    AssetType.TEXT:  "#9B59B6",
}
_DARK = "#0d0d18"
_BAR_H = 0.7


def generate_timeline_graph(doc: KinetiXDocument, output_path: str = "timeline") -> str:
    entries = []
    for e in doc.timeline:
        st = e.start_time if isinstance(e.start_time, (int, float)) else 0
        dur = e.duration or 1.0
        a = doc.assets.get(e.asset_id)
        at = a.type if a else AssetType.VIDEO
        entries.append((e.asset_id, st, st + dur, e.layer, at))

    if not entries:
        return _empty(output_path)

    t0 = min(e[1] for e in entries)
    t1 = max(e[2] for e in entries)
    span = max(t1 - t0, 1.0)

    # ---- Row layout ----
    # video: one row per layer (higher = foreground)
    video_layers: dict[int, list] = {}
    text_clips = []
    audio_clips = []
    for e in entries:
        if e[4] == AssetType.AUDIO:
            audio_clips.append(e)
        elif e[4] == AssetType.TEXT:
            text_clips.append(e)
        else:
            video_layers.setdefault(e[3], []).append(e)

    # Build rows bottom-up: Audio → Text → Video (bottom → top)
    rows: list[tuple[str, str, list]] = []
    if audio_clips:
        rows.append(("audio", "", audio_clips))
    if text_clips:
        rows.append(("text", "", text_clips))
    for ly in sorted(video_layers, reverse=True):
        rows.append(("video", f"L{ly}", video_layers[ly]))

    n_rows = len(rows)
    row_h = 1.2
    track_gap = 0.8

    fig_w = max(22, span / 8)
    fig_h = max(n_rows * row_h + 3.0, 5.5)

    fig, ax = plt.subplots(figsize=(fig_w, fig_h))
    fig.patch.set_facecolor(_DARK)
    ax.set_facecolor(_DARK)

    left_m = t0 - span * 0.04
    right_m = t1 + span * 0.03

    last_track = None
    for i, (track, flabel, clips) in enumerate(rows):
        y = i * row_h

        # track separator
        if track != last_track and i > 0:
            ax.axhline(y=y, color="#444466", linewidth=2.5, linestyle="-")
        last_track = track

        # background
        if track == "audio":
            ax.axhspan(y - row_h / 2, y + row_h / 2,
                       facecolor="#2a1a14", alpha=0.3, zorder=0)

        # track label (left side)
        names = {"video": "Video", "text": "Text", "audio": "Audio"}
        ax.text(left_m, y, names[track], ha="right", va="center",
                fontsize=11, fontweight="bold", color="#aaaaaa")
        if flabel:
            ax.text(left_m + span * 0.006, y, flabel, ha="right", va="center",
                    fontsize=7, color="#555577")

        # bars
        for name, start, end, layer, atype in clips:
            w = end - start
            color = _COLORS.get(atype, "#666")
            ax.barh(y, w, _BAR_H, left=start, color=color,
                    edgecolor="#ffffff44", linewidth=0.5, zorder=3)
            mid = start + w / 2
            d = w
            # Always show label when bar is wide enough
            if w > span * 0.008:
                ax.text(mid, y, f"{name}  {d:.1f}s",
                        ha="center", va="center", fontsize=7,
                        color="white", fontweight="bold", zorder=4)
            elif w > span * 0.003:
                ax.text(mid, y, name, ha="center", va="center",
                        fontsize=6.5, color="white", zorder=4)

    # ---- Axis ----
    ax.set_xlim(left_m, right_m)
    ax.set_ylim(-1.2, n_rows * row_h)
    for s in ["top", "right", "left"]:
        ax.spines[s].set_visible(False)
    ax.spines["bottom"].set_color("#444444")
    ax.tick_params(colors="#888888", labelsize=9)
    ax.set_yticks([])
    ax.xaxis.grid(True, color="#222233", linewidth=0.5, alpha=0.5)
    ax.set_axisbelow(True)

    # time ruler
    interval = _tick(span)
    for tv in _tick_list(t0, t1, interval):
        ax.axvline(x=tv, color="#333344", linewidth=0.4, linestyle="--", alpha=0.5)
        ax.text(tv, n_rows * row_h + 0.1, _fmt(tv),
                ha="center", fontsize=8, color="#666666")

    # ---- Legend ----
    seen = set()
    patches = []
    for _, _, _, _, t in entries:
        if t not in seen:
            seen.add(t)
            patches.append(mpatches.Patch(
                color=_COLORS.get(t, "#666"),
                label={AssetType.VIDEO: "Video", AssetType.IMAGE: "Image",
                       AssetType.AUDIO: "Audio", AssetType.TEXT: "Text"}.get(t, "?")))
    ax.legend(handles=patches, loc="upper right", fontsize=10,
              facecolor="#1a1a30", edgecolor="#333355", labelcolor="white")

    # Title
    m, s = divmod(int(span), 60)
    fig.suptitle(f"Timeline  —  {len(entries)} clips  ·  {m}:{s:02d}",
                 fontsize=15, color="white", fontweight="bold", y=0.99)

    fig.savefig(output_path + ".png", dpi=200, bbox_inches="tight",
                facecolor=fig.get_facecolor())
    plt.close(fig)
    return output_path + ".png"


def _tick(span):
    for s in [5, 10, 15, 20, 30, 60, 120]:
        if span / s <= 30:
            return s
    return 60


def _tick_list(t0, t1, step):
    v = int(t0 // step) * step
    r = []
    while v <= t1 + step:
        if v >= t0:
            r.append(v)
        v += step
    return r


def _fmt(s):
    return f"{int(s//60)}:{int(s%60):02d}"


def _empty(output_path):
    fig, ax = plt.subplots(figsize=(5, 2))
    ax.text(0.5, 0.5, "No timeline entries", ha="center", va="center",
            fontsize=14, color="#888", transform=ax.transAxes)
    fig.patch.set_facecolor(_DARK)
    ax.set_facecolor(_DARK)
    ax.set_xticks([])
    ax.set_yticks([])
    fig.savefig(output_path + ".png", dpi=150, bbox_inches="tight",
                facecolor=fig.get_facecolor())
    plt.close(fig)
    return output_path + ".png"
