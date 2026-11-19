"""C40 (docs/S3A-DESIGN.md): a bar chart of the counts of one county answer, in the look of
the R charts (analysis_r/theme.R: white, one blue, a grey grid on the value axis only, a bold
title, a grey subtitle and foot line, 1600 by 1000 pixels). A value under the floor is never
drawn as a height: its bar is left out and its label says so."""
import json
import os
import textwrap
from pathlib import Path

BLUE, GREY30, GRID = "#1f5fa8", "#4d4d4d", "#e0e0e0"


def draw(bars, floor, title, subtitle, foot, path):
    """`bars`: [(label, value)] in order. Writes a PNG to `path`."""
    os.environ.setdefault("MPLCONFIGDIR", "/tmp/matplotlib")
    from matplotlib.backends.backend_agg import FigureCanvasAgg
    from matplotlib.figure import Figure

    hidden = [1 <= n < floor for _, n in bars]
    wrap = 14 if len(bars) > 6 else 22
    labels = [textwrap.fill(f"{label} (fewer than {floor})" if h else str(label), wrap)
              for (label, _), h in zip(bars, hidden)]
    heights = [0 if h else n for (_, n), h in zip(bars, hidden)]
    fig = Figure(figsize=(16, 10), dpi=100, facecolor="white")
    FigureCanvasAgg(fig)
    ax = fig.add_subplot()
    ax.set_facecolor("white")
    xs = list(range(len(bars)))
    rects = ax.bar(xs, heights, width=0.62, color=BLUE, zorder=2)
    top = max(heights) if heights else 0
    for rect, n, h in zip(rects, heights, hidden):
        if not h:
            ax.annotate(f"{n:,}", (rect.get_x() + rect.get_width() / 2, n), xytext=(0, 6),
                        textcoords="offset points", ha="center", va="bottom", fontsize=15,
                        color="black")
    ax.set_xticks(xs)
    ax.set_xticklabels(labels, fontsize=14, color=GREY30)
    ax.set_ylim(0, max(top * 1.15, 1))
    ax.yaxis.set_major_formatter(__import__("matplotlib.ticker", fromlist=["x"]).StrMethodFormatter("{x:,.0f}"))
    ax.tick_params(axis="y", labelsize=14, colors=GREY30, length=0)
    ax.tick_params(axis="x", length=0)
    ax.grid(axis="y", color=GRID, linewidth=1, zorder=0)
    for side in ("top", "right", "left", "bottom"):
        ax.spines[side].set_visible(False)
    fig.text(0.015, 0.965, textwrap.fill(title, 80), fontsize=21, fontweight="bold",
             color="black", va="top")
    fig.text(0.015, 0.915, subtitle, fontsize=16, color=GREY30, va="top")
    fig.text(0.015, 0.02, textwrap.fill(foot, 150), fontsize=13, color=GREY30, va="bottom")
    fig.subplots_adjust(left=0.07, right=0.98, top=0.86, bottom=0.12)
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, facecolor="white")
    record = {"title": title, "subtitle": subtitle, "foot": foot,  # C40 point 6
              "bars": [{"label": f"{label} (fewer than {floor})" if h else str(label),
                        "value": None if h else n, "hidden": h}
                       for (label, n), h in zip(bars, hidden)]}
    Path(path).with_name("chart.json").write_text(json.dumps(record, indent=2) + "\n",
                                                  encoding="utf-8")
