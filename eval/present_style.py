"""OneSTOP brand styling for presentation figures (see `Brand Guidelines.pdf`).

Palette: #3CBB54 primary green, #329B46 mid green, #1E513D dark green, #E4EEE6 light green.
Typography: Gabarito for headings, Work Sans for body text. Static instances of both live in
`eval/fonts/` (cut from the Google Fonts variable fonts, since matplotlib only renders a
variable font's default weight).
"""

from __future__ import annotations

from pathlib import Path

import matplotlib as mpl
import matplotlib.pyplot as plt
from matplotlib import font_manager
from matplotlib.patches import Annulus

GREEN, MID, DARK, LIGHT = "#3CBB54", "#329B46", "#1E513D", "#E4EEE6"
INK, MUTED, GRID, SURFACE = "#1E2A24", "#5F6B65", "#D5DED8", "#FFFFFF"

HEADING, BODY = "Gabarito", "Work Sans"
SLIDE = (13.33, 7.5)  # 16:9 at PowerPoint's default slide size, in inches

FONTS = Path(__file__).parent / "fonts"


def apply() -> None:
    for font in FONTS.glob("*.ttf"):
        font_manager.fontManager.addfont(str(font))
    mpl.rcParams.update({
        "font.family": BODY,
        "font.size": 13,
        "text.color": INK,
        "axes.labelcolor": MUTED,
        "axes.edgecolor": GRID,
        "axes.linewidth": 1,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "axes.facecolor": SURFACE,
        "axes.grid": True,
        "axes.axisbelow": True,
        "grid.color": GRID,
        "grid.linewidth": 0.8,
        "xtick.color": MUTED,
        "ytick.color": MUTED,
        "xtick.major.size": 0,
        "ytick.major.size": 0,
        "legend.frameon": False,
        "figure.facecolor": SURFACE,
        "savefig.facecolor": SURFACE,
        "hatch.linewidth": 1.6,
    })


def slide(title: str, subtitle: str, **subplot_kw) -> tuple[plt.Figure, object]:
    """A 16:9 figure laid out like a brand guideline page: title top left, ring motif bottom right."""
    fig, axes = plt.subplots(figsize=SLIDE, **subplot_kw)
    fig.subplots_adjust(left=0.07, right=0.93, top=0.78, bottom=0.14)
    fig.text(0.04, 0.925, title, fontfamily=HEADING, fontweight="bold", fontsize=27, color=DARK, va="center")
    fig.text(0.04, 0.855, subtitle, fontsize=14, color=MUTED, va="center")
    # The light-green quarter ring the guidelines use in the bottom-right corner of each page.
    width, height = fig.get_size_inches()
    fig.add_artist(Annulus((width + 0.05, -0.05), 1.15, 0.5, transform=fig.dpi_scale_trans,
                           facecolor=LIGHT, edgecolor="none", zorder=-1))
    return fig, axes


def save(fig: plt.Figure, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=200)
    plt.close(fig)
    print(f"wrote {path}")
