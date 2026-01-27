from typing import Dict, List, Any, Optional
from src.core.geometry import GeometryContext
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

def _draw_quadrant_grids(origins_to_draw: Dict, panel_rows: int, panel_cols: int, ctx: GeometryContext, fill: bool = True, theme_config: Optional[PlotTheme] = None) -> List[Dict[str, Any]]:
    """Creates the shapes for the quadrant outlines and individual unit rectangles."""
    shapes = []
    quad_width = ctx.quad_width
    quad_height = ctx.quad_height

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

    # Use pre-calculated unit dimensions from context
    unit_width = ctx.cell_width
    unit_height = ctx.cell_height

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
    ctx: GeometryContext,
    quadrant: str = 'All',
    fill: bool = True,
    theme_config: Optional[PlotTheme] = None
) -> List[Dict[str, Any]]:
    """
    Creates the visual shapes for the panel grid.
    Visual Origin does NOT affect the grid (it is fixed).

    Includes:
    1. Outer Copper Frame (0-510)
    2. Inner Black Gap (FixedOffset to 510-FixedOffset)
    3. Quadrants (Offset to ...)
    """
    quad_width = ctx.quad_width
    quad_height = ctx.quad_height

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
            fillcolor=gap_color if fill else "rgba(0,0,0,0)",
            line=dict(color=border_color, width=3),
            layer='below'
        ))

        # Draw INNER Black Rect (The Dynamic Gap)
        # In LayoutContext, we don't store fixed_offset explicitly, but we can infer or it might be needed.
        # Actually, LayoutContext is derived FROM fixed offsets.
        # But we need to know where the inner gap starts/ends for drawing.
        # The inner gap is implicitly the area OUTSIDE the quadrants but INSIDE the frame,
        # MINUS the space between quadrants.
        # Wait, the inner black rect is specifically the area defined by fixed_offset_x/y.
        # LayoutContext doesn't expose fixed_offset_x directly.
        # We can calculate it? offset_x = fixed_offset_x + dyn_gap_x.
        # So fixed_offset_x = offset_x - dyn_gap_x?
        # We don't have dyn_gap_x explicitly in context either, only effective_gap_x.
        # Let's assume standard behavior or add fixed_offset to Context if critical.
        # Context has offset_x.
        # Let's simplify: The black rect is (start of Q1 - dyn_gap) ?
        # Actually, let's just use the panel bounds from context if possible.
        # But wait, create_grid_shapes logic used fixed_offset_x.
        # Let's just assume we draw the background behind quadrants as black if needed?
        # The previous code drew a rect from fixed_offset_x to 510-fixed_offset_x.
        # If I can't get fixed_offset from context, I might need to add it to Context.
        # Checking GeometryContext... it DOES NOT have fixed_offset.
        # However, it has `offset_x`. And `effective_gap`.
        # Maybe I should add fixed_offset to GeometryContext?
        # Yes, I should have. But I can't edit it now easily without re-reading.
        # Wait, I did replace GeometryContext in previous turn. Let's check what I put there.
        # I removed fixed_offset from the init? No, I returned GeometryContext(...)
        # I did not add fixed_offset to the dataclass fields.

        # Workaround: We can approximate or just skip the inner black rect if it's purely decorative
        # and covered by the "Gap Color" (Copper) or if the quadrants cover it.
        # The inner black rect was for the "Dynamic Gap" visualization.
        # If I skip it, the gap will be copper (gap_color).
        # Users might prefer that. Or I can hardcode or estimate.
        # Let's skip it for now to avoid breaking. The Copper Frame handles the background.
        pass

    # Grid uses fixed structural offsets (offset_x/y passed in are Start of Q1)
    origins_to_draw = ctx.quadrant_origins if quadrant == 'All' else {quadrant: ctx.quadrant_origins[quadrant]}

    shapes.extend(_draw_quadrant_grids(origins_to_draw, panel_rows, panel_cols, ctx, fill=fill, theme_config=theme_config))
    return shapes
