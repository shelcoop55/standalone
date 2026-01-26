import plotly.graph_objects as go
from typing import Optional
from src.core.config import PlotTheme, BACKGROUND_COLOR, PLOT_AREA_COLOR, TEXT_COLOR, GRID_COLOR

def apply_panel_theme(fig: go.Figure, title: str = "", height: int = 800, theme_config: Optional[PlotTheme] = None) -> go.Figure:
    """
    Applies the standard engineering styling to any figure.
    This centralized function replaces redundant layout code in specific plotting functions.
    """
    # Use theme values if provided, else fall back to global constants
    if theme_config:
        bg_color = theme_config.background_color
        plot_color = theme_config.plot_area_color
        text_color = theme_config.text_color
        axis_color = theme_config.axis_color
    else:
        bg_color = BACKGROUND_COLOR
        plot_color = PLOT_AREA_COLOR
        text_color = TEXT_COLOR
        axis_color = GRID_COLOR # Default fallback

    fig.update_layout(
        title=dict(text=title, font=dict(color=text_color, size=18), x=0.5, xanchor='center'),
        plot_bgcolor=plot_color,
        paper_bgcolor=bg_color,
        height=height,
        font=dict(color=text_color),
        # Default Axis Styling (can be overridden)
        xaxis=dict(
            showgrid=False, zeroline=False, showline=True,
            linewidth=2, linecolor=axis_color, mirror=True,
            title_font=dict(color=text_color), tickfont=dict(color=text_color)
        ),
        yaxis=dict(
            showgrid=False, zeroline=False, showline=True,
            linewidth=2, linecolor=axis_color, mirror=True,
            title_font=dict(color=text_color), tickfont=dict(color=text_color),
            scaleanchor="x", scaleratio=1
        ),
        legend=dict(
            title_font=dict(color=text_color), font=dict(color=text_color),
            bgcolor=bg_color, bordercolor=axis_color, borderwidth=1,
            x=1.02, y=1, xanchor='left', yanchor='top'
        ),
        hoverlabel=dict(bgcolor="#4A4A4A", font_size=14, font_family="sans-serif")
    )
    return fig

def hex_to_rgba(hex_color: str, opacity: float = 0.5) -> str:
    """Helper to convert hex color to rgba string for Plotly without matplotlib dependency."""
    try:
        hex_color = hex_color.lstrip('#')
        if len(hex_color) == 6:
            r = int(hex_color[0:2], 16)
            g = int(hex_color[2:4], 16)
            b = int(hex_color[4:6], 16)
            return f'rgba({r}, {g}, {b}, {opacity})'
        return f'rgba(128, 128, 128, {opacity})'
    except ValueError:
        return f'rgba(128, 128, 128, {opacity})' # Fallback grey
