"""
Plotting and Visualization Module.
This version draws a true-to-scale simulation of a 510x510mm physical panel.
UPDATED: Sankey charts with Neon Palette, 3 types of Heatmaps, and polished styling.
"""
import plotly.graph_objects as go
import pandas as pd
from typing import List, Dict, Any, Set, Tuple, Optional
import numpy as np

from src.config import (
    PANEL_COLOR, GRID_COLOR, defect_style_map, TEXT_COLOR, BACKGROUND_COLOR, PLOT_AREA_COLOR,
    PANEL_WIDTH, PANEL_HEIGHT, GAP_SIZE,
    ALIVE_CELL_COLOR, DEFECTIVE_CELL_COLOR, FALLBACK_COLORS, SAFE_VERIFICATION_VALUES,
    VERIFICATION_COLOR_SAFE, VERIFICATION_COLOR_DEFECT, NEON_PALETTE,
    UNIT_FACE_COLOR, UNIT_EDGE_COLOR, AXIS_TEXT_COLOR, PANEL_BACKGROUND_COLOR, INTER_UNIT_GAP,
    PlotTheme
)
from src.data_handler import StressMapData
from src.documentation import VERIFICATION_DESCRIPTIONS
from src.enums import Quadrant


# ==============================================================================
# --- Private Helper Functions for Grid Creation ---
# ==============================================================================

def _get_rounded_rect_path(x0: float, y0: float, x1: float, y1: float, r: float) -> str:
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

def _draw_border_and_gaps(ox: float = 0.0, oy: float = 0.0, gap_x: float = GAP_SIZE, gap_y: float = GAP_SIZE, panel_width: float = PANEL_WIDTH, panel_height: float = PANEL_HEIGHT, theme_config: Optional[PlotTheme] = None) -> List[Dict[str, Any]]:
    """Creates the shapes for the outer border and inner gaps of the panel."""
    shapes = []
    # Main Panel Background (Copper) is used for outer border and major gaps
    gap_color = theme_config.panel_background_color if theme_config else PANEL_BACKGROUND_COLOR
    border_color = theme_config.axis_color if theme_config else GRID_COLOR

    x_start = ox - gap_x
    x_end = ox + panel_width + 2 * gap_x

    y_start = oy - gap_y
    y_end = oy + panel_height + 2 * gap_y

    # Corner Radius
    radius = 15.0 # Match quadrant radius

    # Draw One Big Rounded Rectangle
    path = _get_rounded_rect_path(x_start, y_start, x_end, y_end, radius)

    shapes.append(dict(
        type="path",
        path=path,
        fillcolor=gap_color,
        line=dict(color=border_color, width=3),
        layer='below'
    ))

    return shapes

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
    # Formula: UnitWidth = (QuadWidth - (Cols - 1) * gap) / Cols
    unit_width = (quad_width - (panel_cols - 1) * INTER_UNIT_GAP) / panel_cols
    unit_height = (quad_height - (panel_rows - 1) * INTER_UNIT_GAP) / panel_rows

    for x_start, y_start in origins_to_draw.values():
        if fill:
            # 1. Draw the Background Copper Rect for the whole quadrant (ROUNDED)
            path = _get_rounded_rect_path(x_start, y_start, x_start + quad_width, y_start + quad_height, 15.0)
            shapes.append(dict(
                type="path",
                path=path,
                fillcolor=bg_color,
                line=dict(color=border_color, width=3),
                layer='below'
            ))

            # 2. Draw individual Unit Rects (Peach)
            for r in range(panel_rows):
                for c in range(panel_cols):
                    # Calculate position
                    ux = x_start + c * (unit_width + INTER_UNIT_GAP)
                    uy = y_start + r * (unit_height + INTER_UNIT_GAP)

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
                    ux = x_start + c * (unit_width + INTER_UNIT_GAP)
                    uy = y_start + r * (unit_height + INTER_UNIT_GAP)
                    shapes.append(dict(
                        type="rect",
                        x0=ux, y0=uy,
                        x1=ux + unit_width, y1=uy + unit_height,
                        line=dict(color=edge_color, width=1),
                        fillcolor="rgba(0,0,0,0)", # Transparent
                        layer='below'
                    ))
            
    return shapes

# ==============================================================================
# --- Public API Functions ---
# ==============================================================================

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

def create_grid_shapes(panel_rows: int, panel_cols: int, quadrant: str = 'All', fill: bool = True, offset_x: float = 0.0, offset_y: float = 0.0, gap_x: float = GAP_SIZE, gap_y: float = GAP_SIZE, panel_width: float = PANEL_WIDTH, panel_height: float = PANEL_HEIGHT, theme_config: Optional[PlotTheme] = None) -> List[Dict[str, Any]]:
    """
    Creates the visual shapes for the panel grid in a fixed 510x510mm coordinate system.
    Supports shifting origin via offset_x/y and dynamic gap.
    """
    quad_width = panel_width / 2
    quad_height = panel_height / 2

    all_origins = {
        'Q1': (0+offset_x , 0+offset_y),
        'Q2': (quad_width + gap_x + offset_x, 0+offset_y),
        'Q3': (0+offset_x, quad_height + gap_y + offset_y),
        'Q4': (quad_width + gap_x + offset_x, quad_height + gap_y + offset_y)
    }
    origins_to_draw = all_origins if quadrant == 'All' else {quadrant: all_origins[quadrant]}
    shapes = []
    if quadrant == 'All':
        shapes.extend(_draw_border_and_gaps(offset_x, offset_y, gap_x, gap_y, panel_width, panel_height, theme_config))

    shapes.extend(_draw_quadrant_grids(origins_to_draw, panel_rows, panel_cols, fill=fill, panel_width=panel_width, panel_height=panel_height, theme_config=theme_config))
    return shapes

def create_defect_traces(df: pd.DataFrame, offset_x: float = 0.0, offset_y: float = 0.0, gap_x: float = GAP_SIZE, gap_y: float = GAP_SIZE) -> List[go.Scatter]:
    """
    Generates scatter plot traces.
    """
    traces = []
    if df.empty: return traces

    # Check the flag. If mixed (some rows T, some F), default to True if any are True
    has_verification_data = df['HAS_VERIFICATION_DATA'].any() if 'HAS_VERIFICATION_DATA' in df.columns else False

    # Determine what column to group by
    group_col = 'Verification' if has_verification_data else 'DEFECT_TYPE'

    unique_groups = df[group_col].unique()

    # --- COLOR MAPPING ---
    local_style_map = {}

    if group_col == 'DEFECT_TYPE':
        # Use the standard defect style map + fallback
        local_style_map = defect_style_map.copy()
        fallback_index = 0
        for dtype in unique_groups:
            if dtype not in local_style_map:
                color = FALLBACK_COLORS[fallback_index % len(FALLBACK_COLORS)]
                local_style_map[dtype] = color
                fallback_index += 1
    else:
        # For Verification codes (CU22, N, etc.), generate a map on the fly
        fallback_index = 0
        for code in unique_groups:
            color = FALLBACK_COLORS[fallback_index % len(FALLBACK_COLORS)]
            local_style_map[code] = color
            fallback_index += 1

    # Generate traces using GroupBy (Optimization #4)
    # 1. Pre-calculate Descriptions globally
    if 'Verification' in df.columns:
        # Avoid SettingWithCopyWarning if df is a slice
        df = df.copy()
        df['Description'] = df['Verification'].map(VERIFICATION_DESCRIPTIONS).fillna("Unknown Code")
    else:
        df = df.copy()
        df['Description'] = "N/A"

    # 2. Pre-calculate Raw Coords globally
    has_raw_coords = 'X_COORDINATES' in df.columns and 'Y_COORDINATES' in df.columns
    coord_str = ""
    if has_raw_coords:
        df['RAW_COORD_STR'] = df.apply(lambda row: f"({row['X_COORDINATES']/1000:.2f}, {row['Y_COORDINATES']/1000:.2f}) mm", axis=1)
        custom_data_cols = ['UNIT_INDEX_X', 'UNIT_INDEX_Y', 'DEFECT_TYPE', 'DEFECT_ID', 'Verification', 'Description', 'RAW_COORD_STR']
        coord_str = "<br>Raw Coords: %{customdata[6]}"
    else:
        custom_data_cols = ['UNIT_INDEX_X', 'UNIT_INDEX_Y', 'DEFECT_TYPE', 'DEFECT_ID', 'Verification', 'Description']

    # 3. GroupBy Loop
    grouped = df.groupby(group_col, observed=True)

    for group_val, dff in grouped:
        if group_val not in local_style_map:
            continue

        color = local_style_map[group_val]

        hovertemplate = ("<b>Status: %{customdata[4]}</b><br>"
                            "Description : %{customdata[5]}<br>"
                            "Type: %{customdata[2]}<br>"
                            "Unit Index (X, Y): (%{customdata[0]}, %{customdata[1]})<br>"
                            "Defect ID: %{customdata[3]}"
                            + coord_str +
                            "<extra></extra>")

        # Check if coordinates are Absolute (from CSV) or Relative (Grid Jitter)
        # If 'X_COORDINATES' exists, plot_x is already Absolute. Do NOT add offset.
        if 'X_COORDINATES' in df.columns:
            x_vals = dff['plot_x']
            y_vals = dff['plot_y']
        else:
            # Only add offset for random jitter/grid-based relative coordinates
            x_vals = dff['plot_x'] + offset_x
            y_vals = dff['plot_y'] + offset_y

        traces.append(go.Scattergl(
            x=x_vals,
            y=y_vals,
            mode='markers',
            marker=dict(color=color, size=8, line=dict(width=1, color='black')),
            name=str(group_val),
            customdata=dff[custom_data_cols],
            hovertemplate=hovertemplate
        ))

    return traces

def create_multi_layer_defect_map(
    df: pd.DataFrame,
    panel_rows: int,
    panel_cols: int,
    flip_back: bool = True,
    offset_x: float = 0.0,
    offset_y: float = 0.0,
    gap_x: float = GAP_SIZE,
    gap_y: float = GAP_SIZE,
    panel_width: float = PANEL_WIDTH,
    panel_height: float = PANEL_HEIGHT,
    theme_config: Optional[PlotTheme] = None
) -> go.Figure:
    """
    Creates a defect map visualizing defects from ALL layers simultaneously.
    Supports toggling Back Side alignment (Flip vs Raw).
    """
    fig = go.Figure()

    if not df.empty:
        # Ensure LAYER_NUM exists
        if 'LAYER_NUM' not in df.columns:
            df['LAYER_NUM'] = 0

        unique_layer_nums = sorted(df['LAYER_NUM'].unique())

        # Generate colors
        layer_colors = {}
        for i, num in enumerate(unique_layer_nums):
            layer_colors[num] = FALLBACK_COLORS[i % len(FALLBACK_COLORS)]

        symbol_map = {'F': 'circle', 'B': 'diamond'}

        for layer_num in unique_layer_nums:
            layer_color = layer_colors[layer_num]
            layer_df = df[df['LAYER_NUM'] == layer_num]

            for side in sorted(layer_df['SIDE'].unique()):
                dff = layer_df[layer_df['SIDE'] == side]
                symbol = symbol_map.get(side, 'circle')
                side_name = "Front" if side == 'F' else "Back"
                trace_name = f"Layer {layer_num} ({side_name})"

                if 'Verification' in dff.columns:
                     dff = dff.copy()
                     dff['Description'] = dff['Verification'].map(VERIFICATION_DESCRIPTIONS).fillna("Unknown Code")
                else:
                     dff['Description'] = "N/A"

                # Prepare Custom Data (Include Raw Coords - Convert um to mm)
                coord_str = ""
                if 'X_COORDINATES' in dff.columns and 'Y_COORDINATES' in dff.columns:
                    dff['RAW_COORD_STR'] = dff.apply(lambda row: f"({row['X_COORDINATES']/1000:.2f}, {row['Y_COORDINATES']/1000:.2f}) mm", axis=1)
                    custom_data_cols = ['UNIT_INDEX_X', 'UNIT_INDEX_Y', 'DEFECT_TYPE', 'DEFECT_ID', 'Verification', 'Description', 'SOURCE_FILE', 'RAW_COORD_STR']
                    coord_str = "<br>Raw Coords: %{customdata[7]}"
                else:
                    custom_data_cols = ['UNIT_INDEX_X', 'UNIT_INDEX_Y', 'DEFECT_TYPE', 'DEFECT_ID', 'Verification', 'Description', 'SOURCE_FILE']

                # Fix Hover Template
                hovertemplate = (f"<b>Layer: {layer_num}</b><br>"
                                 "Side: " + side_name + "<br>"
                                 "Status: %{customdata[4]}<br>"
                                 "Type: %{customdata[2]}<br>"
                                 "Unit Index: (%{customdata[0]}, %{customdata[1]})<br>"
                                 "File: %{customdata[6]}"
                                 + coord_str +
                                 "<extra></extra>")

                # Determine X Coordinates based on Flip Toggle
                # We use the pre-calculated columns from models.py
                if flip_back:
                    x_col_name = 'physical_plot_x_flipped'
                else:
                    x_col_name = 'physical_plot_x_raw'

                x_coords = dff[x_col_name]

                # FIX: Check if coordinates are Absolute (from CSV) or Relative
                if 'X_COORDINATES' in dff.columns:
                     final_x = x_coords
                     final_y = dff['plot_y']
                else:
                     final_x = x_coords + offset_x
                     final_y = dff['plot_y'] + offset_y

                # OPTIMIZATION: Use WebGL
                fig.add_trace(go.Scattergl(
                    x=final_x,
                    y=final_y,
                    mode='markers',
                    marker=dict(
                        color=layer_color,
                        symbol=symbol,
                        size=9,
                        line=dict(width=1, color='black')
                    ),
                    name=trace_name,
                    customdata=dff[custom_data_cols],
                    hovertemplate=hovertemplate
                ))

    # Add Grid
    fig.update_layout(shapes=create_grid_shapes(panel_rows, panel_cols, quadrant='All', offset_x=offset_x, offset_y=offset_y, gap_x=gap_x, gap_y=gap_y, panel_width=panel_width, panel_height=panel_height, theme_config=theme_config))

    quad_width = panel_width / 2
    quad_height = panel_height / 2

    # Calculate ticks (reused from standard map logic)
    cell_width, cell_height = quad_width / panel_cols, quad_height / panel_rows
    x_tick_vals_q1 = [(i * cell_width) + (cell_width / 2) + offset_x for i in range(panel_cols)]
    x_tick_vals_q2 = [(quad_width + gap_x) + (i * cell_width) + (cell_width / 2) + offset_x for i in range(panel_cols)]
    y_tick_vals_q1 = [(i * cell_height) + (cell_height / 2) + offset_y for i in range(panel_rows)]
    y_tick_vals_q3 = [(quad_height + gap_y) + (i * cell_height) + (cell_height / 2) + offset_y for i in range(panel_rows)]
    x_tick_text = list(range(panel_cols * 2))
    y_tick_text = list(range(panel_rows * 2))

    apply_panel_theme(fig, "Multi-Layer Combined Defect Map (True Defects Only)", theme_config=theme_config)

    fig.update_layout(
        xaxis=dict(
            title="Unit Column Index",
            tickvals=x_tick_vals_q1 + x_tick_vals_q2,
            ticktext=x_tick_text,
            range=[0, 510], constrain='domain'
        ),
        yaxis=dict(
            title="Unit Row Index",
            tickvals=y_tick_vals_q1 + y_tick_vals_q3,
            ticktext=y_tick_text,
            range=[0, 515]
        ),
        legend=dict(title=dict(text="Build-Up Layer"))
    )

    return fig
    
def create_defect_map_figure(df: pd.DataFrame, panel_rows: int, panel_cols: int, quadrant_selection: str = Quadrant.ALL.value, lot_number: Optional[str] = None, title: Optional[str] = None, offset_x: float = 0.0, offset_y: float = 0.0, gap_x: float = GAP_SIZE, gap_y: float = GAP_SIZE, panel_width: float = PANEL_WIDTH, panel_height: float = PANEL_HEIGHT, theme_config: Optional[PlotTheme] = None) -> go.Figure:
    """
    Creates the full Defect Map Figure (Traces + Grid + Layout).
    """
    # Use Dynamic Dimensions
    quad_width = panel_width / 2
    quad_height = panel_height / 2

    fig = go.Figure(data=create_defect_traces(df, offset_x=offset_x, offset_y=offset_y, gap_x=gap_x, gap_y=gap_y))
    fig.update_layout(shapes=create_grid_shapes(panel_rows, panel_cols, quadrant_selection, offset_x=offset_x, offset_y=offset_y, gap_x=gap_x, gap_y=gap_y, panel_width=panel_width, panel_height=panel_height, theme_config=theme_config))

    # Calculate ticks and ranges with offsets
    cell_width, cell_height = quad_width / panel_cols, quad_height / panel_rows
    x_tick_vals_q1 = [(i * cell_width) + (cell_width / 2) + offset_x for i in range(panel_cols)]
    x_tick_vals_q2 = [(quad_width + gap_x) + (i * cell_width) + (cell_width / 2) + offset_x for i in range(panel_cols)]
    y_tick_vals_q1 = [(i * cell_height) + (cell_height / 2) + offset_y for i in range(panel_rows)]
    y_tick_vals_q3 = [(quad_height + gap_y) + (i * cell_height) + (cell_height / 2) + offset_y for i in range(panel_rows)]
    x_tick_text, y_tick_text = list(range(panel_cols * 2)), list(range(panel_rows * 2))

    # Full Frame View (0 to 510mm) to show Dead Zones
    # offset_x is the start of copper. 0 is the start of Frame.
    # We want to see the full physical context.
    x_axis_range = [0, 510] # Hardcoded Frame Width as per requirement
    y_axis_range = [0, 515] # Hardcoded Frame Height
    show_ticks = True

    if quadrant_selection != Quadrant.ALL.value:
        show_ticks = False
        ranges = {
            'Q1': ([0+offset_x, quad_width+offset_x], [0+offset_y, quad_height+offset_y]),
            'Q2': ([quad_width + gap_x+offset_x, panel_width + gap_x+offset_x], [0+offset_y, quad_height+offset_y]),
            'Q3': ([0+offset_x, quad_width+offset_x], [quad_height + gap_y+offset_y, panel_height + gap_y+offset_y]),
            'Q4': ([quad_width + gap_x+offset_x, panel_width + gap_x+offset_x], [quad_height + gap_y+offset_y, panel_height + gap_y+offset_y])
        }
        x_axis_range, y_axis_range = ranges[quadrant_selection]

    final_title = title if title else f"Panel Defect Map - Quadrant: {quadrant_selection}"

    apply_panel_theme(fig, final_title, theme_config=theme_config)

    fig.update_layout(
        xaxis=dict(title="Unit Column Index", tickvals=x_tick_vals_q1 + x_tick_vals_q2 if show_ticks else [], ticktext=x_tick_text if show_ticks else [], range=x_axis_range, constrain='domain'),
        yaxis=dict(title="Unit Row Index", tickvals=y_tick_vals_q1 + y_tick_vals_q3 if show_ticks else [], ticktext=y_tick_text if show_ticks else [], range=y_axis_range)
    )

    if lot_number and quadrant_selection == Quadrant.ALL.value:
        # Determine text color for annotation
        t_col = theme_config.text_color if theme_config else TEXT_COLOR
        fig.add_annotation(x=panel_width + gap_x + offset_x, y=panel_height + gap_y + offset_y, text=f"<b>Lot #: {lot_number}</b>", showarrow=False, font=dict(size=14, color=t_col), align="right", xanchor="right", yanchor="bottom")

    return fig

def create_pareto_trace(df: pd.DataFrame) -> go.Bar:
    if df.empty: return go.Bar(name='Pareto')

    has_verification_data = df['HAS_VERIFICATION_DATA'].any() if 'HAS_VERIFICATION_DATA' in df.columns else False
    group_col = 'Verification' if has_verification_data else 'DEFECT_TYPE'

    pareto_data = df[group_col].value_counts().reset_index()
    pareto_data.columns = ['Label', 'Count']

    return go.Bar(x=pareto_data['Label'], y=pareto_data['Count'], name='Pareto', marker_color='#4682B4')

def create_grouped_pareto_trace(df: pd.DataFrame) -> List[go.Bar]:
    if df.empty: return []

    has_verification_data = df['HAS_VERIFICATION_DATA'].any() if 'HAS_VERIFICATION_DATA' in df.columns else False
    group_col = 'Verification' if has_verification_data else 'DEFECT_TYPE'

    grouped_data = df.groupby(['QUADRANT', group_col], observed=True).size().reset_index(name='Count')
    top_items = df[group_col].value_counts().index.tolist()

    traces = []
    quadrants = ['Q1', 'Q2', 'Q3', 'Q4']
    for quadrant in quadrants:
        quadrant_data = grouped_data[grouped_data['QUADRANT'] == quadrant]
        pivot = quadrant_data.pivot(index=group_col, columns='QUADRANT', values='Count').reindex(top_items).fillna(0)
        if not pivot.empty:
            traces.append(go.Bar(name=quadrant, x=pivot.index, y=pivot[quadrant]))
    return traces

def create_pareto_figure(df: pd.DataFrame, quadrant_selection: str = Quadrant.ALL.value, theme_config: Optional[PlotTheme] = None) -> go.Figure:
    """
    Creates the Pareto Figure (Traces + Layout).
    """
    fig = go.Figure()
    if quadrant_selection == Quadrant.ALL.value:
        for trace in create_grouped_pareto_trace(df): fig.add_trace(trace)
        fig.update_layout(barmode='stack')
    else:
        fig.add_trace(create_pareto_trace(df))

    apply_panel_theme(fig, f"Defect Pareto - Quadrant: {quadrant_selection}", height=600, theme_config=theme_config)

    fig.update_layout(
        xaxis=dict(title="Defect Type", categoryorder='total descending'),
        yaxis=dict(showgrid=True) # Override to show grid on Pareto
    )
    return fig

def create_verification_status_chart(df: pd.DataFrame) -> List[go.Bar]:
    if df.empty: return []
    grouped = df.groupby(['DEFECT_TYPE', 'QUADRANT', 'Verification'], observed=True).size().unstack(fill_value=0)
    all_defect_types = df['DEFECT_TYPE'].unique()
    all_quadrants = ['Q1', 'Q2', 'Q3', 'Q4']
    all_combinations = pd.MultiIndex.from_product([all_defect_types, all_quadrants], names=['DEFECT_TYPE', 'QUADRANT'])
    grouped = grouped.reindex(all_combinations, fill_value=0)
    for status in ['T', 'F', 'TA']:
        if status not in grouped.columns: grouped[status] = 0
    grouped = grouped.reset_index()
    x_axis_data = [grouped['DEFECT_TYPE'], grouped['QUADRANT']]
    status_map = {'T': {'name': 'True', 'color': '#FF0000'}, 'F': {'name': 'False', 'color': '#2ca02c'}, 'TA': {'name': 'Acceptable', 'color': '#FFBF00'}}
    traces = []
    for status_code, details in status_map.items():
        traces.append(go.Bar(name=details['name'], x=x_axis_data, y=grouped[status_code], marker_color=details['color']))
    return traces

def create_still_alive_map(
    panel_rows: int,
    panel_cols: int,
    true_defect_data: Dict[Tuple[int, int], Dict[str, Any]],
    offset_x: float = 0.0,
    offset_y: float = 0.0,
    gap_x: float = GAP_SIZE,
    gap_y: float = GAP_SIZE,
    panel_width: float = PANEL_WIDTH,
    panel_height: float = PANEL_HEIGHT,
    theme_config: Optional[PlotTheme] = None
) -> Tuple[List[Dict[str, Any]], List[go.Scatter]]:
    """
    Creates the shapes for the 'Still Alive' map AND invisible scatter points for tooltips.
    """
    shapes = []
    traces = []

    quad_width = panel_width / 2
    quad_height = panel_height / 2

    total_cols, total_rows = panel_cols * 2, panel_rows * 2
    all_origins = {
        'Q1': (0 + offset_x, 0 + offset_y),
        'Q2': (quad_width + gap_x + offset_x, 0 + offset_y),
        'Q3': (0 + offset_x, quad_height + gap_y + offset_y),
        'Q4': (quad_width + gap_x + offset_x, quad_height + gap_y + offset_y)
    }

    # Calculate Unit Dimensions with gaps
    unit_width = (quad_width - (panel_cols - 1) * INTER_UNIT_GAP) / panel_cols
    unit_height = (quad_height - (panel_rows - 1) * INTER_UNIT_GAP) / panel_rows

    # Prepare lists for scatter trace (Tooltips)
    hover_x = []
    hover_y = []
    hover_text = []
    hover_colors = []

    # 0. Draw Background Copper first (for the gaps to show through if cells don't touch)
    shapes.extend(_draw_border_and_gaps(offset_x, offset_y, gap_x, gap_y, panel_width, panel_height, theme_config))
    # We also need quadrant backgrounds for the inter-unit gaps
    # Use dynamic colors
    bg_color = theme_config.panel_background_color if theme_config else PANEL_BACKGROUND_COLOR
    edge_color = theme_config.unit_edge_color if theme_config else UNIT_EDGE_COLOR

    for q_key, (qx, qy) in all_origins.items():
         shapes.append(dict(
            type="rect", x0=qx, y0=qy, x1=qx + quad_width, y1=qy + quad_height,
            line=dict(width=0), fillcolor=bg_color, layer='below'
        ))

    # 1. Draw the colored cells (Units)
    for row in range(total_rows):
        for col in range(total_cols):
            quadrant_col, local_col = divmod(col, panel_cols)
            quadrant_row, local_row = divmod(row, panel_rows)
            quad_key = f"Q{quadrant_row * 2 + quadrant_col + 1}"
            x_origin, y_origin = all_origins[quad_key]

            # Position with Gaps
            x0 = x_origin + local_col * (unit_width + INTER_UNIT_GAP)
            y0 = y_origin + local_row * (unit_height + INTER_UNIT_GAP)

            # Determine status
            is_dead = (col, row) in true_defect_data

            if is_dead:
                metadata = true_defect_data[(col, row)]
                first_killer = metadata['first_killer_layer']

                # Color logic: Revert to binary RED for all defects
                fill_color = DEFECTIVE_CELL_COLOR

                # Add to hover data (Keep Autopsy Tooltip)
                center_x = x0 + unit_width/2
                center_y = y0 + unit_height/2
                hover_x.append(center_x)
                hover_y.append(center_y)

                tooltip = (
                    f"<b>Unit: ({col}, {row})</b><br>"
                    f"First Killer: Layer {first_killer}<br>"
                    f"Details: {metadata['defect_summary']}"
                )
                hover_text.append(tooltip)
                # Hover dots should also match the cell color (Red) to be invisible
                hover_colors.append(fill_color)

            else:
                fill_color = ALIVE_CELL_COLOR

            shapes.append({'type': 'rect', 'x0': x0, 'y0': y0, 'x1': x0 + unit_width, 'y1': y0 + unit_height, 'fillcolor': fill_color, 'line': {'width': 1, 'color': edge_color}, 'layer': 'below'})

    # 2. No need to draw grid lines again, the cells themselves form the grid now.

    # 3. Create Scatter Trace for Hover
    if hover_x:
        traces.append(go.Scatter(
            x=hover_x,
            y=hover_y,
            mode='markers',
            marker=dict(size=0, color=hover_colors, opacity=0), # Invisible markers
            text=hover_text,
            hoverinfo='text'
        ))

    return shapes, traces

def create_still_alive_figure(
    panel_rows: int,
    panel_cols: int,
    true_defect_data: Dict[Tuple[int, int], Dict[str, Any]],
    offset_x: float = 0.0,
    offset_y: float = 0.0,
    gap_x: float = GAP_SIZE,
    gap_y: float = GAP_SIZE,
    panel_width: float = PANEL_WIDTH,
    panel_height: float = PANEL_HEIGHT,
    theme_config: Optional[PlotTheme] = None
) -> go.Figure:
    """
    Creates the Still Alive Map Figure (Shapes + Layout + Tooltips).
    """
    map_shapes, hover_traces = create_still_alive_map(panel_rows, panel_cols, true_defect_data, offset_x=offset_x, offset_y=offset_y, gap_x=gap_x, gap_y=gap_y, panel_width=panel_width, panel_height=panel_height, theme_config=theme_config)

    fig = go.Figure(data=hover_traces) # Add hover traces

    quad_width = panel_width / 2
    quad_height = panel_height / 2

    cell_width, cell_height = quad_width / panel_cols, quad_height / panel_rows
    x_tick_vals_q1 = [(i * cell_width) + (cell_width / 2) + offset_x for i in range(panel_cols)]
    x_tick_vals_q2 = [(quad_width + gap_x) + (i * cell_width) + (cell_width / 2) + offset_x for i in range(panel_cols)]
    y_tick_vals_q1 = [(i * cell_height) + (cell_height / 2) + offset_y for i in range(panel_rows)]
    y_tick_vals_q3 = [(quad_height + gap_y) + (i * cell_height) + (cell_height / 2) + offset_y for i in range(panel_rows)]
    x_tick_text = list(range(panel_cols * 2))
    y_tick_text = list(range(panel_rows * 2))

    apply_panel_theme(fig, f"Still Alive Map ({len(true_defect_data)} Defective Cells)", theme_config=theme_config)

    fig.update_layout(
        xaxis=dict(
            title="Unit Column Index", range=[0, 510], constrain='domain',
            tickvals=x_tick_vals_q1 + x_tick_vals_q2, ticktext=x_tick_text
        ),
        yaxis=dict(
            title="Unit Row Index", range=[0, 515],
            tickvals=y_tick_vals_q1 + y_tick_vals_q3, ticktext=y_tick_text
        ),
        shapes=map_shapes, margin=dict(l=20, r=20, t=80, b=20),
        showlegend=False
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

def create_defect_sankey(df: pd.DataFrame, theme_config: Optional[PlotTheme] = None) -> go.Sankey:
    """
    Creates a Sankey diagram mapping Defect Types (Left) to Verification Status (Right).
    IMPROVEMENTS:
    - Smart Labels with Counts/Percentages
    - Neon Color Palette
    - Sorted Nodes
    - Thicker Nodes & Solid Links
    - Narrative Tooltips
    """
    if df.empty:
        return None

    has_verification = df['HAS_VERIFICATION_DATA'].iloc[0] if 'HAS_VERIFICATION_DATA' in df.columns else False
    if not has_verification:
        return None

    # Data Prep: Group by [DEFECT_TYPE, Verification]
    sankey_df = df.groupby(['DEFECT_TYPE', 'Verification'], observed=True).size().reset_index(name='Count')

    # Calculate Totals for Labels and Sorting
    total_defects = sankey_df['Count'].sum()
    defect_counts = sankey_df.groupby('DEFECT_TYPE', observed=True)['Count'].sum().sort_values(ascending=False)
    verification_counts = sankey_df.groupby('Verification', observed=True)['Count'].sum().sort_values(ascending=False)

    # Unique Sorted Labels
    defect_types = defect_counts.index.tolist()
    verification_statuses = verification_counts.index.tolist()

    all_labels_raw = defect_types + verification_statuses

    # Generate Smart Labels: "Scratch (42 - 15%)"
    smart_labels = []

    # Source Labels (Defects)
    for dtype in defect_types:
        count = defect_counts[dtype]
        pct = (count / total_defects) * 100
        smart_labels.append(f"{dtype} ({count} - {pct:.1f}%)")

    # Target Labels (Verification)
    for ver in verification_statuses:
        count = verification_counts[ver]
        pct = (count / total_defects) * 100
        smart_labels.append(f"{ver} ({count} - {pct:.1f}%)")

    # Mapping
    source_map = {label: i for i, label in enumerate(defect_types)}
    offset = len(defect_types)
    target_map = {label: i + offset for i, label in enumerate(verification_statuses)}

    sources = []
    targets = []
    values = []
    link_colors = []
    custom_hovers = []

    # Assign Neon Colors to Source Nodes
    source_colors_hex = []
    for i, dtype in enumerate(defect_types):
        color = NEON_PALETTE[i % len(NEON_PALETTE)]
        source_colors_hex.append(color)

    # Assign Status Colors to Target Nodes
    safe_values_upper = {v.upper() for v in SAFE_VERIFICATION_VALUES}
    target_colors_hex = []
    for status in verification_statuses:
        if status.upper() in safe_values_upper:
            target_colors_hex.append(VERIFICATION_COLOR_SAFE)
        else:
            target_colors_hex.append(VERIFICATION_COLOR_DEFECT)

    node_colors = source_colors_hex + target_colors_hex

    # Build Links
    # We iterate through the SORTED defect types to ensure visual flow order
    for dtype in defect_types:
        dtype_df = sankey_df[sankey_df['DEFECT_TYPE'] == dtype]
        for _, row in dtype_df.iterrows():
            ver = row['Verification']
            count = row['Count']

            s_idx = source_map[dtype]
            t_idx = target_map[ver]

            sources.append(s_idx)
            targets.append(t_idx)
            values.append(count)

            # Link Color: Match Source with High Opacity (0.8) for "Pipe" look
            source_hex = source_colors_hex[s_idx]
            link_colors.append(hex_to_rgba(source_hex, opacity=0.8))

            # Narrative Tooltip
            pct_flow = (count / total_defects) * 100
            hover_text = (
                f"<b>{count} {dtype}s</b> accounted for <b>{pct_flow:.1f}%</b> of total flow<br>"
                f"Resulting in <b>{ver}</b> status."
            )
            custom_hovers.append(hover_text)

    fig = go.Figure(data=[go.Sankey(
        node=dict(
            pad=25,
            thickness=30,    # Much Thicker Nodes
            line=dict(color="black", width=1), # Sharp border
            label=smart_labels,
            color=node_colors,
            hovertemplate='%{label}<extra></extra>'
        ),
        link=dict(
            source=sources,
            target=targets,
            value=values,
            color=link_colors,
            customdata=custom_hovers,
            hovertemplate='%{customdata}<extra></extra>' # Use the narrative text
        ),
        textfont=dict(size=14, color=TEXT_COLOR, family="Roboto")
    )])

    apply_panel_theme(fig, "Defect Type → Verification Flow Analysis", height=700, theme_config=theme_config)

    fig.update_layout(
        font=dict(size=12, color=TEXT_COLOR),
        margin=dict(l=20, r=20, t=60, b=20),
        xaxis=dict(showgrid=False, showline=False), # Sankey doesn't need axes
        yaxis=dict(showgrid=False, showline=False)
    )
    return fig

def create_unit_grid_heatmap(df: pd.DataFrame, panel_rows: int, panel_cols: int, theme_config: Optional[PlotTheme] = None) -> go.Figure:
    """
    1. Grid Density Heatmap (Chessboard).
    Filters for TRUE DEFECTS only.
    """
    if df.empty:
        return go.Figure()

    # Filter for True Defects
    safe_values_upper = {v.upper() for v in SAFE_VERIFICATION_VALUES}
    if 'Verification' in df.columns:
        df_true = df[~df['Verification'].str.upper().isin(safe_values_upper)].copy()
    else:
        df_true = df.copy()

    # Determine colors from theme
    if theme_config:
        bg_color = theme_config.background_color
        plot_color = theme_config.plot_area_color
        text_color = theme_config.text_color
    else:
        bg_color = BACKGROUND_COLOR
        plot_color = PLOT_AREA_COLOR
        text_color = TEXT_COLOR

    if df_true.empty:
        return go.Figure(layout=dict(
            title=dict(text="No True Defects Found for Heatmap", font=dict(color=text_color)),
            paper_bgcolor=bg_color, plot_bgcolor=plot_color
        ))

    # Map to Global Indices
    global_indices = []
    for _, row in df_true.iterrows():
        # USE RAW COORDINATES (UNIT_INDEX_X) as per request (No Flip)
        u_x = int(row['UNIT_INDEX_X'])
        q = row['QUADRANT']
        u_y = int(row['UNIT_INDEX_Y'])

        g_x = u_x + (panel_cols if q in ['Q2', 'Q4'] else 0)
        g_y = u_y + (panel_rows if q in ['Q3', 'Q4'] else 0)
        global_indices.append((g_x, g_y))

    heatmap_df = pd.DataFrame(global_indices, columns=['Global_X', 'Global_Y'])
    heatmap_data = heatmap_df.groupby(['Global_X', 'Global_Y']).size().reset_index(name='Count')

    # Create Heatmap
    # Use 'Reds' or 'Magma' for high impact
    fig = go.Figure(data=go.Heatmap(
        x=heatmap_data['Global_X'],
        y=heatmap_data['Global_Y'],
        z=heatmap_data['Count'],
        colorscale='Magma', # Darker theme
        xgap=2, ygap=2,     # Clear separation
        colorbar=dict(title='Defects', title_font=dict(color=text_color), tickfont=dict(color=text_color)),
        hovertemplate='Global Unit: (%{x}, %{y})<br>Defects: %{z}<extra></extra>'
    ))

    # Fix Axis Ranges
    total_global_cols = panel_cols * 2
    total_global_rows = panel_rows * 2

    apply_panel_theme(fig, "1. Unit Grid Density (Yield Loss Map)", height=700, theme_config=theme_config)

    fig.update_layout(
        xaxis=dict(
            title="Global Unit Column",
            tickmode='linear', dtick=1,
            range=[-0.5, total_global_cols - 0.5],
            constrain='domain'
        ),
        yaxis=dict(
            title="Global Unit Row",
            tickmode='linear', dtick=1,
            range=[-0.5, total_global_rows - 0.5]
        )
    )

    return fig

def create_density_contour_map(
    df: pd.DataFrame,
    panel_rows: int,
    panel_cols: int,
    show_points: bool = False,
    smoothing_factor: int = 30,
    saturation_cap: int = 0,
    show_grid: bool = True,
    view_mode: str = "Continuous",
    flip_back: bool = False,
    quadrant_selection: str = 'All',
    offset_x: float = 0.0,
    offset_y: float = 0.0,
    gap_x: float = GAP_SIZE,
    gap_y: float = GAP_SIZE,
    panel_width: float = PANEL_WIDTH,
    panel_height: float = PANEL_HEIGHT,
    theme_config: Optional[PlotTheme] = None
) -> go.Figure:
    """
    2. Smoothed Density Contour Map (OPTIMIZED).
    Uses Server-Side aggregation (numpy.histogram2d) instead of client-side computation.
    Features:
    - Quadrant-Aware Aggregation (Respects Gap)
    - Hard Boundary Conditions (0-510mm)
    - Weighted Risk Density (Optional: Short=10x) - Placeholder for now.
    - Drill-Down Tooltips (Dominant Defect Driver).
    """
    if df.empty:
        return go.Figure()

    # Filter for True Defects
    safe_values_upper = {v.upper() for v in SAFE_VERIFICATION_VALUES}
    if 'Verification' in df.columns:
        df_true = df[~df['Verification'].str.upper().isin(safe_values_upper)].copy()
    else:
        df_true = df.copy()

    if df_true.empty:
        return go.Figure(layout=dict(title="No True Defects Found"))

    # Determine X Coordinates based on Toggle
    if 'physical_plot_x_flipped' in df_true.columns:
        x_col_name = 'physical_plot_x_flipped' if flip_back else 'physical_plot_x_raw'
    else:
        x_col_name = 'plot_x'

    # Apply Dynamic Gap Correction
    # Since models.py already applies gap_x to 'plot_x' etc, we might not need this.

    df_true['plot_x_corrected'] = df_true[x_col_name]
    df_true['plot_y_corrected'] = df_true['plot_y']

    x_col = 'plot_x_corrected'

    fig = go.Figure()

    # --- SERVER-SIDE AGGREGATION CONFIG ---
    scale_factor = 10.0 / max(1, smoothing_factor)

    # Dynamic Binning
    bins_x = max(10, int((panel_cols * 2) * 2 * scale_factor))
    bins_y = max(10, int((panel_rows * 2) * 2 * scale_factor))

    num_bins = [bins_y, bins_x]

    # Boundary Definitions with Offsets
    x_min, x_max = offset_x, panel_width + gap_x + offset_x
    y_min, y_max = offset_y, panel_height + gap_y + offset_y

    # --- QUADRANT-AWARE AGGREGATION ---
    def aggregate_quadrant(q_df, x_range, y_range):
        if q_df.empty:
            return None, None, None, None, None

        # Apply offsets to data before binning
        if 'X_COORDINATES' in q_df.columns:
            x_c = q_df[x_col].values
            y_c = q_df['plot_y_corrected'].values
        else:
            x_c = q_df[x_col].values + offset_x
            y_c = q_df['plot_y_corrected'].values + offset_y

        # 1. Density (Z)
        H, x_edges, y_edges = np.histogram2d(x_c, y_c, bins=num_bins, range=[x_range, y_range])

        # 2. Dominant Defect Driver (Mode)
        if 'DEFECT_TYPE' in q_df.columns:
            unique_types = q_df['DEFECT_TYPE'].unique()
            if len(unique_types) > 10:
                top_types = q_df['DEFECT_TYPE'].value_counts().nlargest(10).index.tolist()
                unique_types = top_types

            type_grids = []
            type_labels = []

            for dtype in unique_types:
                sub_df = q_df[q_df['DEFECT_TYPE'] == dtype]
                if not sub_df.empty:
                    # Apply offsets here too
                    if 'X_COORDINATES' in sub_df.columns:
                        sub_x = sub_df[x_col]
                        sub_y = sub_df['plot_y_corrected']
                    else:
                        sub_x = sub_df[x_col] + offset_x
                        sub_y = sub_df['plot_y_corrected'] + offset_y
                    h_sub, _, _ = np.histogram2d(sub_x, sub_y, bins=num_bins, range=[x_range, y_range])
                    type_grids.append(h_sub)
                    type_labels.append(dtype)

            if type_grids:
                stack = np.stack(type_grids, axis=0) # Shape: (K, bins_x, bins_y)
                # Find index of max along axis 0
                max_indices = np.argmax(stack, axis=0) # Shape: (bins_x, bins_y)

                # Map indices to labels
                driver_map = np.empty(max_indices.shape, dtype=object)
                for idx, label in enumerate(type_labels):
                    driver_map[max_indices == idx] = label

                driver_map[H == 0] = ""
                driver_text = driver_map.T # Transpose for Plotly
            else:
                driver_text = None
        else:
            driver_text = None

        # Create meshgrid for plotting
        x_centers = (x_edges[:-1] + x_edges[1:]) / 2
        y_centers = (y_edges[:-1] + y_edges[1:]) / 2

        return H.T, x_centers, y_centers, driver_text

    H, x_centers, y_centers, driver_text_t = aggregate_quadrant(
        df_true,
        [x_min, x_max],
        [y_min, y_max]
    )

    if H is None: # Should not happen given check above
        return go.Figure(layout=dict(title="Error in Aggregation"))

    Z = H # Already transposed in helper

    # Masking Gap (Shifted by offset)
    quad_width = panel_width / 2
    quad_height = panel_height / 2

    gap_x_start = quad_width + offset_x
    gap_x_end = quad_width + gap_x + offset_x
    gap_y_start = quad_height + offset_y
    gap_y_end = quad_height + gap_y + offset_y

    mask_x = (x_centers > gap_x_start) & (x_centers < gap_x_end)
    mask_y = (y_centers > gap_y_start) & (y_centers < gap_y_end)

    Z[np.ix_(mask_y, mask_x)] = np.nan
    Z[:, mask_x] = 0
    Z[mask_y, :] = 0

    # Custom Hover Template
    if driver_text_t is not None:
        # We must zero out driver text in gaps too
        driver_text_t[np.ix_(mask_y, mask_x)] = ""
        driver_text_t[:, mask_x] = ""
        driver_text_t[mask_y, :] = ""

        hovertemplate = 'X: %{x:.1f}mm<br>Y: %{y:.1f}mm<br>Density: %{z:.0f}<br>Top Cause: %{text}<extra></extra>'
        text_arg = driver_text_t
    else:
        hovertemplate = 'X: %{x:.1f}mm<br>Y: %{y:.1f}mm<br>Density: %{z:.0f}<extra></extra>'
        text_arg = None

    fig.add_trace(go.Contour(
        z=Z,
        x=x_centers,
        y=y_centers,
        text=text_arg,
        colorscale='Turbo',
        contours=dict(
            coloring='heatmap',
            showlabels=True, # Show density values
            labelfont=dict(color='white')
        ),
        zmin=0,
        zmax=saturation_cap if saturation_cap > 0 else None,
        hoverinfo='x+y+z+text' if text_arg is not None else 'x+y+z',
        hovertemplate=hovertemplate
    ))

    # 2. Points Overlay (Scattergl)
    if show_points:
        if 'X_COORDINATES' in df_true.columns:
            px = df_true[x_col]
            py = df_true['plot_y_corrected']
        else:
            px = df_true[x_col] + offset_x
            py = df_true['plot_y_corrected'] + offset_y

        fig.add_trace(go.Scattergl(
            x=px,
            y=py,
            mode='markers',
            marker=dict(color='white', size=3, opacity=0.5),
            hoverinfo='skip',
            name='Defects'
        ))

    # 3. Grid Overlay
    shapes = []
    if show_grid:
        shapes = create_grid_shapes(panel_rows, panel_cols, quadrant='All', fill=False, offset_x=offset_x, offset_y=offset_y, gap_x=gap_x, gap_y=gap_y, panel_width=panel_width, panel_height=panel_height, theme_config=theme_config)

    # 4. Axis Labels
    total_cols = panel_cols * 2
    total_rows = panel_rows * 2
    quad_width = panel_width / 2
    quad_height = panel_height / 2
    cell_width = quad_width / panel_cols
    cell_height = quad_height / panel_rows

    x_tick_vals = []
    x_tick_text = []
    for i in range(total_cols):
        offset = gap_x if i >= panel_cols else 0
        center_mm = (i * cell_width) + (cell_width / 2) + offset + offset_x
        x_tick_vals.append(center_mm)
        x_tick_text.append(str(i))

    y_tick_vals = []
    y_tick_text = []
    for i in range(total_rows):
        offset = gap_y if i >= panel_rows else 0
        center_mm = (i * cell_height) + (cell_height / 2) + offset + offset_y
        y_tick_vals.append(center_mm)
        y_tick_text.append(str(i))

    # Axis Ranges Full Frame
    x_axis_range = [0, 510]
    y_axis_range = [0, 515]

    if quadrant_selection != 'All':
        # Apply offsets to quadrant ranges
        ranges = {
            'Q1': ([offset_x, offset_x + quad_width], [offset_y, offset_y + quad_height]),
            'Q2': ([offset_x + quad_width + gap_x, offset_x + panel_width + gap_x], [offset_y, offset_y + quad_height]),
            'Q3': ([offset_x, offset_x + quad_width], [offset_y + quad_height + gap_y, offset_y + panel_height + gap_y]),
            'Q4': ([offset_x + quad_width + gap_x, offset_x + panel_width + gap_x], [offset_y + quad_height + gap_y, offset_y + panel_height + gap_y])
        }
        x_axis_range, y_axis_range = ranges[quadrant_selection]

    apply_panel_theme(fig, "Smooth Density Hotspot (Server-Side Aggregated)", height=700, theme_config=theme_config)

    fig.update_layout(
        xaxis=dict(
            title="Unit Column Index (Approx)",
            tickvals=x_tick_vals,
            ticktext=x_tick_text,
            range=x_axis_range, constrain='domain'
        ),
        yaxis=dict(
            title="Unit Row Index (Approx)",
            tickvals=y_tick_vals,
            ticktext=y_tick_text,
            range=y_axis_range
        ),
        shapes=shapes
    )
    return fig


def create_defect_sunburst(df: pd.DataFrame, theme_config: Optional[PlotTheme] = None) -> go.Figure:
    """
    Creates a Sunburst chart: Defect Type -> Verification (if avail).
    Hierarchy: Total -> Defect Type -> Verification Status
    """
    if df.empty:
        return go.Figure()

    has_verification = df['HAS_VERIFICATION_DATA'].iloc[0] if 'HAS_VERIFICATION_DATA' in df.columns else False

    # 1. Aggregate
    if has_verification:
        grouped = df.groupby(['DEFECT_TYPE', 'Verification'], observed=True).size().reset_index(name='Count')
    else:
        grouped = df.groupby(['DEFECT_TYPE'], observed=True).size().reset_index(name='Count')

    # Build lists
    ids = []
    labels = []
    parents = []
    values = []

    # Root
    total_count = grouped['Count'].sum()
    ids.append("Total")
    labels.append(f"Total<br>{total_count}")
    parents.append("")
    values.append(total_count)
    # Root needs hover text too (or defaults)

    # Prepare detailed hover info
    # Format: Type/Status | Count | % of Parent | % of Total
    custom_data = [] # Stores [Label, Count, Pct Parent, Pct Total]

    # Root custom data
    custom_data.append(["Total", total_count, "100%", "100%"])

    # Level 1: Defect Type
    for dtype in grouped['DEFECT_TYPE'].unique():
        dtype_count = grouped[grouped['DEFECT_TYPE'] == dtype]['Count'].sum()
        ids.append(f"{dtype}")
        labels.append(dtype)
        parents.append("Total")
        values.append(dtype_count)

        pct_total = (dtype_count / total_count) * 100
        custom_data.append([dtype, dtype_count, f"{pct_total:.1f}%", f"{pct_total:.1f}%"])

        # Level 2: Verification (if exists)
        if has_verification:
            dtype_df = grouped[grouped['DEFECT_TYPE'] == dtype]
            for ver in dtype_df['Verification'].unique():
                ver_count = dtype_df[dtype_df['Verification'] == ver]['Count'].sum()
                ids.append(f"{dtype}-{ver}")
                labels.append(ver)
                parents.append(f"{dtype}")
                values.append(ver_count)

                pct_parent = (ver_count / dtype_count) * 100
                pct_total_ver = (ver_count / total_count) * 100
                custom_data.append([ver, ver_count, f"{pct_parent:.1f}%", f"{pct_total_ver:.1f}%"])

    fig = go.Figure(go.Sunburst(
        ids=ids,
        labels=labels,
        parents=parents,
        values=values,
        branchvalues="total",
        customdata=custom_data,
        hovertemplate="<b>%{customdata[0]}</b><br>Count: %{customdata[1]}<br>% of Layer: %{customdata[2]}<br>% of Total: %{customdata[3]}<extra></extra>"
    ))

    # Apply standard theme with title and larger square-like layout
    apply_panel_theme(fig, "Defect Distribution", height=700, theme_config=theme_config)

    fig.update_layout(
        margin=dict(t=40, l=10, r=10, b=10), # Adjusted margins for title
        xaxis=dict(visible=False), # Hide axes to remove any white lines
        yaxis=dict(visible=False),
        showlegend=False # Explicitly hide legend as requested
    )

    return fig

def create_stress_heatmap(data: StressMapData, panel_rows: int, panel_cols: int, view_mode: str = "Continuous", offset_x: float = 0.0, offset_y: float = 0.0, gap_size: float = GAP_SIZE, panel_width: float = PANEL_WIDTH, panel_height: float = PANEL_HEIGHT, gap_x: float = GAP_SIZE, gap_y: float = GAP_SIZE, theme_config: Optional[PlotTheme] = None) -> go.Figure:
    """
    Creates the Cumulative Stress Heatmap with defect counts in cells.
    Supports 'Quarterly' view mode by injecting NaNs or splitting.
    """
    # Use gap_x/y if provided, else fallback to gap_size (for compat) or defaults
    # Note: caller should pass gap_x/gap_y

    quad_width = panel_width / 2
    quad_height = panel_height / 2

    # Determine colors from theme
    if theme_config:
        bg_color = theme_config.background_color
        plot_color = theme_config.plot_area_color
        text_color = theme_config.text_color
    else:
        bg_color = BACKGROUND_COLOR
        plot_color = PLOT_AREA_COLOR
        text_color = TEXT_COLOR

    if data.total_defects == 0:
        return go.Figure(layout=dict(
            title=dict(text="No True Defects Found in Selection", font=dict(color=text_color)),
            paper_bgcolor=bg_color, plot_bgcolor=plot_color
        ))

    z_data = data.grid_counts.astype(float)
    text_data = data.grid_counts.astype(str)
    hover_text = data.hover_text

    # Process for View Mode
    if view_mode == "Quarterly":
        rows, cols = z_data.shape
        cell_width = quad_width / panel_cols
        cell_height = quad_height / panel_rows

        col_indices = np.arange(cols)
        row_indices = np.arange(rows)

        # Apply Gaps
        x_gaps = np.where(col_indices >= panel_cols, gap_x, 0)
        y_gaps = np.where(row_indices >= panel_rows, gap_y, 0)

        # 1D Coordinates
        x_vals = (col_indices * cell_width) + (cell_width / 2) + x_gaps + offset_x
        y_vals = (row_indices * cell_height) + (cell_height / 2) + y_gaps + offset_y

        # Broadcast to 2D Grid
        x_coords, y_coords = np.meshgrid(x_vals, y_vals)

        # Now pass x and y to Heatmap. Plotly handles the spacing.
        # Mask zeros
        z_data[z_data == 0] = np.nan
        text_data[data.grid_counts == 0] = ""

        fig = go.Figure(data=go.Heatmap(
            x=x_coords[0, :], # The X coordinates of the columns
            y=y_coords[:, 0], # The Y coordinates of the rows
            z=z_data,
            text=text_data,
            texttemplate="%{text}",
            textfont={"color": "white"},
            colorscale='Magma',
            xgap=2, ygap=2,
            hovertext=hover_text,
            hoverinfo="text",
            colorbar=dict(title='Defects', title_font=dict(color=text_color), tickfont=dict(color=text_color))
        ))

        # Add Grid Shapes for Quarterly view
        fig.update_layout(shapes=create_grid_shapes(panel_rows, panel_cols, quadrant='All', fill=False, offset_x=offset_x, offset_y=offset_y, gap_x=gap_x, gap_y=gap_y, panel_width=panel_width, panel_height=panel_height, theme_config=theme_config))

        # Ranges (NO MARGIN)
        max_x = panel_width + gap_x
        max_y = panel_height + gap_y

        fig.update_layout(
            xaxis=dict(title="Physical X", range=[0, 510], constrain='domain', showticklabels=False),
            yaxis=dict(title="Physical Y", range=[0, 515], showticklabels=False)
        )

    else:
        # Continuous Mode (Indices)
        z_data[z_data == 0] = np.nan
        text_data[data.grid_counts == 0] = ""

        fig = go.Figure(data=go.Heatmap(
            z=z_data,
            text=text_data,
            texttemplate="%{text}",
            textfont={"color": "white"}, # Or smart contrast if needed
            colorscale='Magma',
            xgap=2, ygap=2,
            hovertext=data.hover_text,
            hoverinfo="text",
            colorbar=dict(title='Defects', title_font=dict(color=text_color), tickfont=dict(color=text_color))
        ))

        total_cols = panel_cols * 2
        total_rows = panel_rows * 2

        fig.update_layout(
            xaxis=dict(
                title="Unit Index X",
                tickmode='linear', dtick=1,
                range=[-0.5, total_cols - 0.5],
                constrain='domain'
            ),
            yaxis=dict(
                title="Unit Index Y",
                tickmode='linear', dtick=1,
                range=[-0.5, total_rows - 0.5]
            )
        )

    apply_panel_theme(fig, "Cumulative Stress Map (Total Defects per Unit)", height=700, theme_config=theme_config)
    return fig

def create_delta_heatmap(data_a: StressMapData, data_b: StressMapData, panel_rows: int, panel_cols: int, view_mode: str = "Continuous", offset_x: float = 0.0, offset_y: float = 0.0, gap_size: float = GAP_SIZE, panel_width: float = PANEL_WIDTH, panel_height: float = PANEL_HEIGHT, gap_x: float = GAP_SIZE, gap_y: float = GAP_SIZE, theme_config: Optional[PlotTheme] = None) -> go.Figure:
    """
    Creates a Delta Heatmap (Group A - Group B).
    """
    quad_width = panel_width / 2
    quad_height = panel_height / 2

    # Determine colors from theme
    if theme_config:
        text_color = theme_config.text_color
    else:
        text_color = TEXT_COLOR

    diff_grid = data_a.grid_counts.astype(float) - data_b.grid_counts.astype(float)
    # Text: Show signed difference
    text_data = np.array([f"{int(x):+d}" if x != 0 else "" for x in diff_grid.flatten()]).reshape(diff_grid.shape)
    diff_grid[diff_grid == 0] = np.nan

    if view_mode == "Quarterly":
        rows, cols = diff_grid.shape
        cell_width = quad_width / panel_cols
        cell_height = quad_height / panel_rows

        col_indices = np.arange(cols)
        row_indices = np.arange(rows)

        x_gaps = np.where(col_indices >= panel_cols, gap_x, 0)
        y_gaps = np.where(row_indices >= panel_rows, gap_y, 0)

        x_vals = (col_indices * cell_width) + (cell_width / 2) + x_gaps + offset_x
        y_vals = (row_indices * cell_height) + (cell_height / 2) + y_gaps + offset_y

        fig = go.Figure(data=go.Heatmap(
            x=x_vals,
            y=y_vals,
            z=diff_grid,
            text=text_data,
            texttemplate="%{text}",
            colorscale='RdBu_r',
            zmid=0,
            xgap=2, ygap=2,
            colorbar=dict(title='Delta (A - B)', title_font=dict(color=text_color), tickfont=dict(color=text_color))
        ))

        fig.update_layout(shapes=create_grid_shapes(panel_rows, panel_cols, quadrant='All', fill=False, offset_x=offset_x, offset_y=offset_y, gap_x=gap_x, gap_y=gap_y, panel_width=panel_width, panel_height=panel_height, theme_config=theme_config))
        max_x = panel_width + gap_x
        max_y = panel_height + gap_y

        fig.update_layout(
            xaxis=dict(title="Physical X", range=[0, 510], constrain='domain', showticklabels=False),
            yaxis=dict(title="Physical Y", range=[0, 515], showticklabels=False)
        )

    else:
        fig = go.Figure(data=go.Heatmap(
            z=diff_grid,
            text=text_data,
            texttemplate="%{text}",
            colorscale='RdBu_r', # Red for positive (more in A), Blue for negative (more in B)
            zmid=0,
            xgap=2, ygap=2,
            colorbar=dict(title='Delta (A - B)', title_font=dict(color=text_color), tickfont=dict(color=text_color))
        ))

        total_cols = panel_cols * 2
        total_rows = panel_rows * 2
        fig.update_layout(
            xaxis=dict(
                title="Unit Index X",
                tickmode='linear', dtick=1,
                range=[-0.5, total_cols - 0.5],
                constrain='domain'
            ),
            yaxis=dict(
                title="Unit Index Y",
                tickmode='linear', dtick=1,
                range=[-0.5, total_rows - 0.5]
            )
        )

    apply_panel_theme(fig, "Delta Stress Map (Group A - Group B)", height=700, theme_config=theme_config)
    return fig

def create_cross_section_heatmap(
    matrix: np.ndarray,
    layer_labels: List[str],
    axis_labels: List[str],
    slice_desc: str,
    theme_config: Optional[PlotTheme] = None
) -> go.Figure:
    """
    Creates the Z-Axis Cross Section Heatmap (Virtual Slice).
    """
    # Inverse Y-axis so Layer 1 is at top (if not already handled by input order)
    # Actually, Heatmap Y-axis 0 is usually bottom. We need to flip visual range or data order.
    # We'll just set 'autorange="reversed"' in layout for Y axis so top of list is top of chart.

    # Determine colors from theme
    if theme_config:
        bg_color = theme_config.background_color
        plot_color = theme_config.plot_area_color
        text_color = theme_config.text_color
    else:
        bg_color = BACKGROUND_COLOR
        plot_color = PLOT_AREA_COLOR
        text_color = TEXT_COLOR

    if matrix.size == 0:
         return go.Figure(layout=dict(
             title=dict(text="No Data for Cross-Section", font=dict(color=text_color)),
             paper_bgcolor=bg_color, plot_bgcolor=plot_color
         ))

    # Mask zeros
    z_data = matrix.astype(float)
    z_data[z_data == 0] = np.nan

    text_data = matrix.astype(str)
    text_data[matrix == 0] = ""

    fig = go.Figure(data=go.Heatmap(
        z=z_data,
        x=axis_labels,
        y=layer_labels,
        text=text_data,
        texttemplate="%{text}",
        textfont={"color": "white"},
        colorscale='Magma',
        xgap=2, ygap=2,
        colorbar=dict(title='Defects', title_font=dict(color=text_color), tickfont=dict(color=text_color))
    ))

    apply_panel_theme(fig, f"Virtual Cross-Section: {slice_desc}", height=600, theme_config=theme_config)

    fig.update_layout(
        xaxis=dict(title="Unit Index (Slice Position)", dtick=1), # Force integer ticks (0, 1, 2...)
        yaxis=dict(title="Layer Stack", autorange="reversed") # Ensure Layer 1 is at top
    )

    return fig
