"""Generate timeline topology diagram (matplotlib Gantt chart).

Outputs a PNG showing all assets as horizontal bars on a time axis,
vertically stacked by layer with color-coded asset types.
"""

from __future__ import annotations

import matplotlib
matplotlib.use("Agg")  # headless

import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np

from .ast_nodes import AssetType, KinetiXDocument

_TYPE_COLOR = {
    AssetType.VIDEO: "#4A90D9",
    AssetType.IMAGE: "#50C878",
    AssetType.AUDIO: "#E8833A",
    AssetType.TEXT:  "#9B59B6",
}
_TYPE_LABEL = {
    AssetType.VIDEO: "Video",
    AssetType.IMAGE: "Image",
    AssetType.AUDIO: "Audio",
    AssetType.TEXT:  "Text",
}

BAR_HEIGHT = 0.55
GAP = 0.4


def generate_timeline_graph(doc: KinetiXDocument, output_path: str = "timeline") -> str:
    """Generate a timeline PNG. Returns the output file path."""
    entries = []
    for e in doc.timeline:
        st = e.start_time if isinstance(e.start_time, (int, float)) else 0
        dur = e.duration or 1.0
        asset = doc.assets.get(e.asset_id)
        atype = asset.type if asset else AssetType.VIDEO
        entries.append((e.asset_id, st, st + dur, e.layer, atype))

    if not entries:
        fig, ax = plt.subplots(figsize=(12, 2))
        ax.text(0.5, 0.5, "No timeline entries", ha="center", va="center",
                transform=ax.transAxes, fontsize=16, color="#888")
        fig.savefig(output_path + ".png", dpi=150, bbox_inches="tight", facecolor="#1a1a2e")
        plt.close(fig)
        return output_path + ".png"

    min_t = min(e[1] for e in entries)
    max_t = max(e[2] for e in entries)
    span = max(max_t - min_t, 1.0)
    max_layer = max(e[3] for e in entries)

    # Build visual layers: each (asset, layer) pair gets its own row
    # Entries sorted: layer (bottom first), then start time
    entries.sort(key=lambda x: (x[3], x[1]))

    rows = len(entries)
    fig_height = max(rows * (BAR_HEIGHT + GAP) + 1.5, 4)

    fig, ax = plt.subplots(figsize=(16, fig_height))
    fig.patch.set_facecolor("#1a1a2e")
    ax.set_facecolor("#1a1a2e")

    # Draw bars
    for i, (name, start, end, layer, atype) in enumerate(entries):
        color = _TYPE_COLOR.get(atype, "#666666")
        y = rows - 1 - i  # top row first
        ax.barh(y, end - start, BAR_HEIGHT, left=start, color=color,
                edgecolor="white", linewidth=0.5, alpha=0.85)

        # Label
        dur_s = end - start
        label = f"{name}  [{dur_s:.1f}s]"
        ax.text(start + (end - start) / 2, y, label,
                ha="center", va="center", fontsize=7,
                color="white", fontweight="bold")

    # Layer indicators on left
    layer_positions: dict[int, float] = {}
    for i, (_, _, _, layer, _) in enumerate(entries):
        y = rows - 1 - i
        if layer not in layer_positions:
            layer_positions[layer] = y

    for layer, y_pos in layer_positions.items():
        ax.text(min_t - span * 0.02, y_pos, f"L{layer}",
                ha="right", va="center", fontsize=8,
                color="#aaaaaa", fontweight="bold")

    # Styling
    ax.set_xlim(min_t - span * 0.08, max_t + span * 0.05)
    ax.set_ylim(-0.5, rows - 0.5)
    ax.invert_yaxis()

    # Time axis
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_visible(False)
    ax.spines["bottom"].set_color("#555555")
    ax.tick_params(colors="#aaaaaa", labelsize=8)
    ax.set_xlabel("Time (seconds)", color="#aaaaaa", fontsize=10)
    ax.set_yticks([])

    # Grid
    ax.xaxis.grid(True, color="#333333", linewidth=0.5, alpha=0.5)
    ax.set_axisbelow(True)

    # Legend
    legend_patches = []
    seen_types = set()
    for _, _, _, _, atype in entries:
        if atype not in seen_types:
            seen_types.add(atype)
            legend_patches.append(
                mpatches.Patch(color=_TYPE_COLOR.get(atype, "#666"),
                               label=_TYPE_LABEL.get(atype, "?"))
            )
    if legend_patches:
        ax.legend(handles=legend_patches, loc="upper right",
                  fontsize=8, facecolor="#222244", edgecolor="#444466",
                  labelcolor="white")

    # Title
    fig.suptitle("KinetiX Timeline Topology", fontsize=14,
                 color="white", fontweight="bold", y=0.98)

    fig.savefig(output_path + ".png", dpi=150, bbox_inches="tight",
                facecolor=fig.get_facecolor())
    plt.close(fig)
    return output_path + ".png"
