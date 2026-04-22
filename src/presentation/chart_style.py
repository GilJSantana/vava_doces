"""Shared chart styling utilities for a minimal high-contrast visual identity."""

from __future__ import annotations

from typing import Iterable

import plotly.graph_objects as go

FONT_FAMILY = "Roboto"
FONT_COLOR = "#1F2937"
CHART_BG = "rgba(0,0,0,0)"

# Solid and distinct colors (Plotly D3-like palette)
COLOR_PALETTE = [
    "#1F77B4",
    "#FF7F0E",
    "#2CA02C",
    "#D62728",
    "#9467BD",
    "#8C564B",
    "#E377C2",
    "#7F7F7F",
    "#BCBD22",
    "#17BECF",
]


def apply_minimal_figure_style(
    fig: go.Figure,
    *,
    showlegend: bool = False,
    hovermode: str = "closest",
    legend_bottom: bool = False,
) -> go.Figure:
    """Apply shared high-contrast style to a Plotly figure."""
    layout_kwargs: dict = {
        "template": "plotly_white",
        "font_family": FONT_FAMILY,
        "font_color": FONT_COLOR,
        "title_font_size": 20,
        "plot_bgcolor": CHART_BG,
        "paper_bgcolor": CHART_BG,
        "showlegend": showlegend,
        "hovermode": hovermode,
        "margin": {"l": 24, "r": 24, "t": 24, "b": 24},
    }

    if showlegend and legend_bottom:
        layout_kwargs["legend"] = {
            "orientation": "h",
            "x": 0,
            "y": -0.18,
            "bgcolor": "rgba(0,0,0,0)",
            "borderwidth": 0,
            "font": {"family": FONT_FAMILY, "color": FONT_COLOR},
        }

    fig.update_layout(**layout_kwargs)
    return fig


def apply_clean_xy_axes(
    fig: go.Figure,
    *,
    x_title: str = "",
    y_title: str = "",
    x_tickprefix: str | None = None,
    y_automargin: bool = True,
) -> go.Figure:
    """Remove gridlines and extra borders from XY axes."""
    xaxis_kwargs = {
        "title_text": x_title,
        "showgrid": False,
        "zeroline": False,
        "showline": False,
    }
    if x_tickprefix is not None:
        xaxis_kwargs["tickprefix"] = x_tickprefix
        xaxis_kwargs["separatethousands"] = True

    fig.update_xaxes(**xaxis_kwargs)
    fig.update_yaxes(
        title_text=y_title,
        automargin=y_automargin,
        showgrid=False,
        zeroline=False,
        showline=False,
    )
    return fig


def build_color_map(labels: Iterable[str]) -> dict[str, str]:
    """Create deterministic label->color map from shared palette."""
    ordered = sorted({str(label).strip() for label in labels if str(label).strip()})
    return {label: COLOR_PALETTE[idx % len(COLOR_PALETTE)] for idx, label in enumerate(ordered)}


def colors_for_labels(labels: Iterable[str], color_map: dict[str, str] | None = None) -> list[str]:
    """Return a color list for labels using the shared palette or a provided map."""
    effective_map = color_map or build_color_map(labels)
    return [effective_map.get(str(label), COLOR_PALETTE[0]) for label in labels]


def apply_bar_colors_by_y(fig: go.Figure, color_map: dict[str, str]) -> None:
    """Apply mapped colors to the first bar trace by its y labels."""
    if not fig.data:
        return
    y_values = getattr(fig.data[0], "y", [])
    colors = colors_for_labels(y_values, color_map)
    fig.update_traces(marker_color=colors, selector={"type": "bar"})

