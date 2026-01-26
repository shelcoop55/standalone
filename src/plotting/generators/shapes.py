from typing import Dict, List, Any, Optional
from src.core.config import (
    PANEL_WIDTH, PANEL_HEIGHT, GAP_SIZE,
    PANEL_BACKGROUND_COLOR, GRID_COLOR, UNIT_EDGE_COLOR, UNIT_FACE_COLOR,
    INTER_UNIT_GAP, PlotTheme
)

def get_rounded_rect_path(x0: float, y0: float, x1: float, y1: float, r: float) -> str:
    """Generates an SVG path string for a rounded rectangle."""
    # Ensure radius doesn't exceed dimensions
    width = x1 - x0
    height = y1 - y0
    r = min(r, width / 2, height / 2)

    return (
        f"M {x0+r} {y0} "
        f"L {x1-r} {y0} "
        f"Q {x1} {y0} {x1} {y0+r} "
        f"L {x1} {y1-r} "
        f"Q {x1} {y1} {x1-r} {y1} "
        f"L {x0+r} {y1} "
        f"Q {x0} {y1} {x0} {y1-r} "
        f"L {x0} {y0+r} "
        f"Q {x0} {y0} {x0+r} {y0} "
        "Z"
    )

def _draw_quadrant_grids(origins_to_draw: Dict, panel_rows: int, panel_cols: int, fill: bool = True, panel_width: float = PANEL_WIDTH, panel_height: float = PANEL_HEIGHT, theme_config: Optional[PlotTheme] = None) -> List[Dict[str, Any]]:
    """Creates the shapes for the quadrant outlines and individual unit rectangles."""
    shapes = []
    quad_width = panel_width / 2
    quad_height = panel_height / 2

    # Determine colors
    if theme_config:
        bg_color = theme_config.panel_background_color
        edge_color = theme_config.unit_edge_color
        face_color = theme_config.unit_face_color
        border_color = theme_config.axis_color
    else:
        bg_color = PANEL_BACKGROUND_COLOR
        edge_color = UNIT_EDGE_COLOR
        face_color = UNIT_FACE_COLOR
        border_color = GRID_COLOR

    # Calculate Unit Dimensions accounting for inter-unit gaps
    # Formula: UnitWidth = (QuadWidth - (Cols + 1) * gap) / Cols (Gap before first and after last)
    unit_width = (quad_width - (panel_cols + 1) * INTER_UNIT_GAP) / panel_cols
    unit_height = (quad_height - (panel_rows + 1) * INTER_UNIT_GAP) / panel_rows

    for x_start, y_start in origins_to_draw.values():
        if fill:
            # 1. Draw the Background Copper Rect for the whole quadrant (SQUARE per request)
            shapes.append(dict(
                type="rect",
                x0=x_start,
                y0=y_start,
                x1=x_start + quad_width,
                y1=y_start + quad_height,
                fillcolor=bg_color,
                line=dict(color=border_color, width=3),
                layer='below'
            ))

            # 2. Draw individual Unit Rects (Peach)
            for r in range(panel_rows):
                for c in range(panel_cols):
                    # Calculate position (Start at Gap)
                    ux = x_start + INTER_UNIT_GAP + c * (unit_width + INTER_UNIT_GAP)
                    uy = y_start + INTER_UNIT_GAP + r * (unit_height + INTER_UNIT_GAP)

                    shapes.append(dict(
                        type="rect",
                        x0=ux, y0=uy,
                        x1=ux + unit_width, y1=uy + unit_height,
                        line=dict(color=edge_color, width=1),
                        fillcolor=face_color,
                        layer='below'
                    ))
        else:
            # For overlay mode (e.g. heatmap), we might still want the grid structure visible
             for r in range(panel_rows):
                for c in range(panel_cols):
                    ux = x_start + INTER_UNIT_GAP + c * (unit_width + INTER_UNIT_GAP)
                    uy = y_start + INTER_UNIT_GAP + r * (unit_height + INTER_UNIT_GAP)
                    shapes.append(dict(
                        type="rect",
                        x0=ux, y0=uy,
                        x1=ux + unit_width, y1=uy + unit_height,
                        line=dict(color=edge_color, width=1),
                        fillcolor="rgba(0,0,0,0)", # Transparent
                        layer='below'
                    ))

    return shapes

def create_grid_shapes(
    panel_rows: int,
    panel_cols: int,
    quadrant: str = 'All',
    fill: bool = True,
    offset_x: float = 0.0,
    offset_y: float = 0.0,
    gap_x: float = GAP_SIZE,
    gap_y: float = GAP_SIZE,
    panel_width: float = PANEL_WIDTH,
    panel_height: float = PANEL_HEIGHT,
    theme_config: Optional[PlotTheme] = None,
    visual_origin_x: float = 0.0,
    visual_origin_y: float = 0.0,
    fixed_offset_x: float = 0.0,
    fixed_offset_y: float = 0.0
) -> List[Dict[str, Any]]:
    """
    Creates the visual shapes for the panel grid.
    Visual Origin does NOT affect the grid (it is fixed).

    Includes:
    1. Outer Copper Frame (0-510)
    2. Inner Black Gap (FixedOffset to 510-FixedOffset)
    3. Quadrants (Offset to ...)
    """
    quad_width = panel_width / 2
    quad_height = panel_height / 2

    # Visual Origin logic removed from GRID shape calculation to keep it fixed to frame.
    # The grid is physically located at 0-510.

    # 1. Outer Copper Frame
    gap_color = theme_config.panel_background_color if theme_config else PANEL_BACKGROUND_COLOR
    border_color = theme_config.axis_color if theme_config else GRID_COLOR

    shapes = []

    if quadrant == 'All':
        # Draw BIG Copper Frame
        path_frame = get_rounded_rect_path(0, 0, 510, 515, 20.0)
        shapes.append(dict(
            type="path",
            path=path_frame,
            fillcolor=gap_color,
            line=dict(color=border_color, width=3),
            layer='below'
        ))

        # Draw INNER Black Rect (The Dynamic Gap)
        # Only if we have valid fixed offsets
        if fixed_offset_x > 0 and fixed_offset_y > 0:
            x0_inner = fixed_offset_x
            y0_inner = fixed_offset_y
            x1_inner = 510 - fixed_offset_x
            y1_inner = 515 - fixed_offset_y

            # Get color from theme or default to black
            fill_col = theme_config.inner_gap_color if theme_config and hasattr(theme_config, 'inner_gap_color') else "black"

            # Using basic rect for inner gap
            shapes.append(dict(
                type="rect",
                x0=x0_inner, y0=y0_inner,
                x1=x1_inner, y1=y1_inner,
                fillcolor=fill_col,
                line=dict(width=0),
                layer='below'
            ))

    # Grid uses fixed structural offsets (offset_x/y passed in are Start of Q1)
    all_origins = {
        'Q1': (0+offset_x , 0+offset_y),
        'Q2': (quad_width + gap_x + offset_x, 0+offset_y),
        'Q3': (0+offset_x, quad_height + gap_y + offset_y),
        'Q4': (quad_width + gap_x + offset_x, quad_height + gap_y + offset_y)
    }
    origins_to_draw = all_origins if quadrant == 'All' else {quadrant: all_origins[quadrant]}

    shapes.extend(_draw_quadrant_grids(origins_to_draw, panel_rows, panel_cols, fill=fill, panel_width=panel_width, panel_height=panel_height, theme_config=theme_config))
    return shapes
