"""Generate multi-track timeline (剪映-style).

Tracks: Video (by layer), Text, Audio (one continuous row).
Transition-connected clips share the same track, with overlap region highlighted.
"""

from __future__ import annotations

import matplotlib
matplotlib.use("Agg")

import matplotlib.pyplot as plt
import matplotlib.patches as mpatches

from .ast_nodes import AssetType, KinetiXDocument, TimelineEntry

_COLORS = {
    AssetType.VIDEO: "#5B9BD5",
    AssetType.IMAGE: "#70AD47",
    AssetType.AUDIO: "#ED7D31",
    AssetType.TEXT:  "#9B59B6",
}
_DARK = "#0d0d18"
_BAR_H = 0.7


def generate_timeline_graph(doc: KinetiXDocument, output_path: str = "timeline") -> str:
    entries: list[dict] = []
    for e in doc.timeline:
        st = e.start_time if isinstance(e.start_time, (int, float)) else 0
        dur = e.duration or 1.0
        a = doc.assets.get(e.asset_id)
        at = a.type if a else AssetType.VIDEO
        entries.append({
            "id": e.asset_id, "start": st, "end": st + dur,
            "layer": e.layer, "type": at,
            "transition": e.transition,
            "transition_dur": e.transition_dur,
        })

    if not entries:
        return _empty(output_path)

    t0 = min(e["start"] for e in entries)
    t1 = max(e["end"] for e in entries)
    span = max(t1 - t0, 1.0)

    # ---- Row layout ----
    video_layers: dict[int, list] = {}
    text_clips, audio_clips = [], []
    for e in entries:
        if e["type"] == AssetType.AUDIO:
            audio_clips.append(e)
        elif e["type"] == AssetType.TEXT:
            text_clips.append(e)
        else:
            video_layers.setdefault(e["layer"], []).append(e)

    # Build rows bottom-up: Audio → Text → Video (higher layer = top)
    rows: list[tuple[str, str, list]] = []
    for sub in _split_overlapping(audio_clips):
        rows.append(("audio", "", sub))
    for sub in _split_overlapping(text_clips):
        rows.append(("text", "", sub))
    for ly in sorted(video_layers):
        label = f"L{ly}" if len(video_layers) > 1 else ""
        for sub in _lay_out_video_track(video_layers[ly]):
            rows.append(("video", label, sub))

    n_rows = len(rows)
    row_h = 1.2

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
            ax.axhline(y=(i - 0.5) * row_h, color="#444466", linewidth=2.5, linestyle="-")
        last_track = track

        if track == "audio":
            ax.axhspan(y - row_h / 2, y + row_h / 2,
                       facecolor="#2a1a14", alpha=0.3, zorder=0)

        # track label
        names = {"video": "Video", "text": "Text", "audio": "Audio"}
        ax.text(left_m, y, names[track], ha="right", va="center",
                fontsize=11, fontweight="bold", color="#aaaaaa")
        if flabel:
            ax.text(left_m + span * 0.006, y, flabel, ha="right", va="center",
                    fontsize=7, color="#555577")

        # bars & transition overlaps
        for j, clip in enumerate(clips):
            name = clip["id"]
            start = clip["start"]
            end = clip["end"]
            atype = clip["type"]
            w = end - start
            color = _COLORS.get(atype, "#666")
            ax.barh(y, w, _BAR_H, left=start, color=color,
                    edgecolor="#ffffff44", linewidth=0.5, zorder=3)

            # Transition overlap: darken the overlapping tail with the NEXT clip
            if j + 1 < len(clips):
                nxt = clips[j + 1]
                if nxt["start"] < end:
                    xfade_start = nxt["start"]
                    xfade_w = end - nxt["start"]
                    ax.barh(y, xfade_w, _BAR_H, left=xfade_start,
                            color="#000000", alpha=0.35, zorder=4,
                            edgecolor="#ffcc00", linewidth=1.2, linestyle="--")
                    # Small label
                    xfade_mid = xfade_start + xfade_w / 2
                    ax.text(xfade_mid, y + _BAR_H / 2 + 0.08,
                            f"↔{xfade_w:.1f}s", ha="center", va="bottom",
                            fontsize=5.5, color="#ffcc00", zorder=5)

            mid = start + w / 2
            if w > span * 0.008:
                ax.text(mid, y, f"{name}  {w:.1f}s",
                        ha="center", va="center", fontsize=7,
                        color="white", fontweight="bold", zorder=6)
            elif w > span * 0.003:
                ax.text(mid, y, name, ha="center", va="center",
                        fontsize=6.5, color="white", zorder=6)

    # ---- Axis ----
    ax.set_xlim(left_m, right_m)
    ax.set_ylim(-1.2, n_rows * row_h)
    for s in ["top", "right", "left"]:
        ax.spines[s].set_visible(False)
    ax.spines["bottom"].set_color("#444444")
    ax.tick_params(colors="#888888", labelsize=9)
    ax.set_yticks([])

    # time ruler — use explicit ticks so grid and labels align
    interval = _tick(span)
    ticks = _tick_list(t0, t1, interval)
    ax.set_xticks(ticks)
    ax.set_xticklabels([_fmt(tv) for tv in ticks])
    ax.xaxis.grid(True, color="#333344", linewidth=0.4, linestyle="--", alpha=0.5)
    ax.set_axisbelow(True)

    # ---- Legend ----
    seen = set()
    patches = []
    for e in entries:
        t = e["type"]
        if t not in seen:
            seen.add(t)
            patches.append(mpatches.Patch(
                color=_COLORS.get(t, "#666"),
                label={AssetType.VIDEO: "Video", AssetType.IMAGE: "Image",
                       AssetType.AUDIO: "Audio", AssetType.TEXT: "Text"}.get(t, "?")))
    # Add transition legend
    patches.append(mpatches.Patch(
        facecolor="#000000", alpha=0.35, edgecolor="#ffcc00",
        linewidth=1.2, linestyle="--", label="Transition"))
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


def _split_overlapping(clips):
    """Greedy split: put overlapping clips onto separate sub-tracks."""
    if not clips:
        return []
    sorted_clips = sorted(clips, key=lambda c: c["start"])
    tracks = []
    for clip in sorted_clips:
        placed = False
        for track in tracks:
            if clip["start"] >= track[-1]["end"]:
                track.append(clip)
                placed = True
                break
        if not placed:
            tracks.append([clip])
    return tracks


def _lay_out_video_track(clips):
    """Layout video clips: transition-connected clips share a track."""
    if not clips:
        return []
    sorted_clips = sorted(clips, key=lambda c: c["start"])

    # Step 1: build transition chains (sequential clips with overlap on same layer)
    chains: list[list] = []
    current_chain = [sorted_clips[0]]
    for i in range(1, len(sorted_clips)):
        prev = current_chain[-1]
        curr = sorted_clips[i]
        # Same chain if curr starts before prev ends (overlapping = transitional)
        if curr["start"] < prev["end"]:
            current_chain.append(curr)
        else:
            chains.append(current_chain)
            current_chain = [curr]
    chains.append(current_chain)

    # Step 2: flatten — each chain is one track, non-chain clips go through _split_overlapping
    result = []
    for chain in chains:
        if len(chain) == 1:
            # Single clip: try to place it on an existing track, or create new
            placed = False
            for track in result:
                if chain[0]["start"] >= track[-1]["end"]:
                    track.append(chain[0])
                    placed = True
                    break
            if not placed:
                result.append(chain)
        else:
            result.append(chain)
    return result


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
