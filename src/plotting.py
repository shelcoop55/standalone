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
    VERIFICATION_COLOR_SAFE, VERIFICATION_COLOR_DEFECT, NEON_PALETTE
)
from src.data_handler import QUADRANT_WIDTH, QUADRANT_HEIGHT, StressMapData
from src.documentation import VERIFICATION_DESCRIPTIONS
from src.enums import Quadrant

# ==============================================================================
# --- Private Helper Functions for Grid Creation ---
# ==============================================================================

def _draw_border_and_gaps() -> List[Dict[str, Any]]:
    """Creates the shapes for the outer border and inner gaps of the panel."""
    shapes = []
    gap_color = '#A8652A'
    total_width_with_gap = PANEL_WIDTH + GAP_SIZE
    total_height_with_gap = PANEL_HEIGHT + GAP_SIZE

    # Outer border frame
    shapes.extend([
        dict(type="rect", x0=0, y0=total_height_with_gap, x1=total_width_with_gap, y1=total_height_with_gap + GAP_SIZE, fillcolor=gap_color, line_width=0, layer='below'),
        dict(type="rect", x0=0, y0=-GAP_SIZE, x1=total_width_with_gap, y1=0, fillcolor=gap_color, line_width=0, layer='below'),
        dict(type="rect", x0=-GAP_SIZE, y0=-GAP_SIZE, x1=0, y1=total_height_with_gap + GAP_SIZE, fillcolor=gap_color, line_width=0, layer='below'),
        dict(type="rect", x0=total_width_with_gap, y0=-GAP_SIZE, x1=total_width_with_gap + GAP_SIZE, y1=total_height_with_gap + GAP_SIZE, fillcolor=gap_color, line_width=0, layer='below')
    ])

    # Inner gaps
    shapes.extend([
        dict(type="rect", x0=QUADRANT_WIDTH, y0=0, x1=QUADRANT_WIDTH + GAP_SIZE, y1=total_height_with_gap, fillcolor=gap_color, line_width=0, layer='below'),
        dict(type="rect", x0=0, y0=QUADRANT_HEIGHT, x1=total_width_with_gap, y1=QUADRANT_HEIGHT + GAP_SIZE, fillcolor=gap_color, line_width=0, layer='below')
    ])
    return shapes

def _draw_quadrant_grids(origins_to_draw: Dict, panel_rows: int, panel_cols: int, fill: bool = True) -> List[Dict[str, Any]]:
    """Creates the shapes for the quadrant outlines and their internal grid lines."""
    shapes = []
    cell_width = QUADRANT_WIDTH / panel_cols
    cell_height = QUADRANT_HEIGHT / panel_rows

    for x_start, y_start in origins_to_draw.values():
        if fill:
            shapes.append(dict(
                type="rect", x0=x_start, y0=y_start, x1=x_start + QUADRANT_WIDTH, y1=y_start + QUADRANT_HEIGHT,
                line=dict(color=GRID_COLOR, width=2), fillcolor=PANEL_COLOR, layer='below'
            ))
        for i in range(1, panel_cols):
            line_x = x_start + (i * cell_width)
            shapes.append(dict(type="line", x0=line_x, y0=y_start, x1=line_x, y1=y_start + QUADRANT_HEIGHT, line=dict(color=GRID_COLOR, width=1, dash='solid'), opacity=0.5, layer='below'))
        for i in range(1, panel_rows):
            line_y = y_start + (i * cell_height)
            shapes.append(dict(type="line", x0=x_start, y0=line_y, x1=x_start + QUADRANT_WIDTH, y1=line_y, line=dict(color=GRID_COLOR, width=1, dash='solid'), opacity=0.5, layer='below'))
            
    return shapes

# ==============================================================================
# --- Public API Functions ---
# ==============================================================================

def apply_panel_theme(fig: go.Figure, title: str = "", height: int = 800) -> go.Figure:
    """
    Applies the standard engineering styling to any figure.
    This centralized function replaces redundant layout code in specific plotting functions.
    """
    fig.update_layout(
        title=dict(text=title, font=dict(color=TEXT_COLOR, size=18), x=0.5, xanchor='center'),
        plot_bgcolor=PLOT_AREA_COLOR,
        paper_bgcolor=BACKGROUND_COLOR,
        height=height,
        font=dict(color=TEXT_COLOR),
        # Default Axis Styling (can be overridden)
        xaxis=dict(
            showgrid=False, zeroline=False, showline=True,
            linewidth=2, linecolor=GRID_COLOR, mirror=True,
            title_font=dict(color=TEXT_COLOR), tickfont=dict(color=TEXT_COLOR)
        ),
        yaxis=dict(
            showgrid=False, zeroline=False, showline=True,
            linewidth=2, linecolor=GRID_COLOR, mirror=True,
            title_font=dict(color=TEXT_COLOR), tickfont=dict(color=TEXT_COLOR),
            scaleanchor="x", scaleratio=1
        ),
        legend=dict(
            title_font=dict(color=TEXT_COLOR), font=dict(color=TEXT_COLOR),
            bgcolor=BACKGROUND_COLOR, bordercolor=GRID_COLOR, borderwidth=1,
            x=1.02, y=1, xanchor='left', yanchor='top'
        ),
        hoverlabel=dict(bgcolor="#4A4A4A", font_size=14, font_family="sans-serif")
    )
    return fig

def create_grid_shapes(panel_rows: int, panel_cols: int, quadrant: str = 'All', fill: bool = True) -> List[Dict[str, Any]]:
    """
    Creates the visual shapes for the panel grid in a fixed 510x510mm coordinate system.
    """
    all_origins = {
        'Q1': (0, 0), 'Q2': (QUADRANT_WIDTH + GAP_SIZE, 0),
        'Q3': (0, QUADRANT_HEIGHT + GAP_SIZE), 'Q4': (QUADRANT_WIDTH + GAP_SIZE, QUADRANT_HEIGHT + GAP_SIZE)
    }
    origins_to_draw = all_origins if quadrant == 'All' else {quadrant: all_origins[quadrant]}
    shapes = []
    if quadrant == 'All':
        shapes.extend(_draw_border_and_gaps())
    shapes.extend(_draw_quadrant_grids(origins_to_draw, panel_rows, panel_cols, fill=fill))
    return shapes

def create_defect_traces(df: pd.DataFrame) -> List[go.Scatter]:
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

    # Generate traces
    for group_val, color in local_style_map.items():
        dff = df[df[group_col] == group_val]
        if not dff.empty:
            if 'Verification' in dff.columns:
                 dff = dff.copy()
                 dff['Description'] = dff['Verification'].map(VERIFICATION_DESCRIPTIONS).fillna("Unknown Code")
            else:
                 dff['Description'] = "N/A"

            custom_data_cols = ['UNIT_INDEX_X', 'UNIT_INDEX_Y', 'DEFECT_TYPE', 'DEFECT_ID', 'Verification', 'Description']

            hovertemplate = ("<b>Status: %{customdata[4]}</b><br>"
                             "Description : %{customdata[5]}<br>"
                             "Type: %{customdata[2]}<br>"
                             "Unit Index (X, Y): (%{customdata[0]}, %{customdata[1]})<br>"
                             "Defect ID: %{customdata[3]}"
                             "<extra></extra>")

            traces.append(go.Scatter(
                x=dff['plot_x'],
                y=dff['plot_y'],
                mode='markers',
                marker=dict(color=color, size=8, line=dict(width=1, color='black')),
                name=group_val,
                customdata=dff[custom_data_cols],
                hovertemplate=hovertemplate
            ))

    return traces

def create_multi_layer_defect_map(df: pd.DataFrame, panel_rows: int, panel_cols: int) -> go.Figure:
    """
    Creates a defect map visualizing defects from ALL layers simultaneously.

    Logic:
    - Group by Layer Number (Same Color)
    - Distinguish by Side (Different Symbol: Front=Circle, Back=Diamond)
    """
    fig = go.Figure()

    if not df.empty:
        # Ensure LAYER_NUM exists
        if 'LAYER_NUM' not in df.columns:
            # Fallback if column missing (should not happen with new prepare_multi_layer_data)
            df['LAYER_NUM'] = 0

        unique_layer_nums = sorted(df['LAYER_NUM'].unique())

        # Generate colors for layers
        # Reuse NEON_PALETTE + FALLBACK_COLORS
        layer_colors = {}
        for i, num in enumerate(unique_layer_nums):
            layer_colors[num] = FALLBACK_COLORS[i % len(FALLBACK_COLORS)]

        # Symbol Mapping
        # Front = Circle (Standard)
        # Back = Diamond (Distinct, implies flip side)
        symbol_map = {'F': 'circle', 'B': 'diamond'}

        # Group by (Layer, Side) to create traces
        # We iterate through layers first to keep legend organized
        for layer_num in unique_layer_nums:
            layer_color = layer_colors[layer_num]

            # Filter for this layer
            layer_df = df[df['LAYER_NUM'] == layer_num]

            # Iterate through sides present in this layer
            # Sort sides to keep Front before Back usually, or alphabetical
            for side in sorted(layer_df['SIDE'].unique()):
                dff = layer_df[layer_df['SIDE'] == side]

                # Determine Symbol
                symbol = symbol_map.get(side, 'circle') # Default to circle if unknown

                side_name = "Front" if side == 'F' else "Back"
                trace_name = f"Layer {layer_num} ({side_name})"

                # Prepare hover data
                if 'Verification' in dff.columns:
                     dff = dff.copy()
                     dff['Description'] = dff['Verification'].map(VERIFICATION_DESCRIPTIONS).fillna("Unknown Code")
                else:
                     dff['Description'] = "N/A"

                custom_data_cols = ['UNIT_INDEX_X', 'UNIT_INDEX_Y', 'DEFECT_TYPE', 'DEFECT_ID', 'Verification', 'Description', 'SOURCE_FILE']

                hovertemplate = ("<b>Layer: %{data.legendgroup}</b><br>"
                                 "Side: " + side_name + "<br>"
                                 "Status: %{customdata[4]}<br>"
                                 "Type: %{customdata[2]}<br>"
                                 "Coords: (%{customdata[0]}, %{customdata[1]})<br>"
                                 "File: %{customdata[6]}"
                                 "<extra></extra>")

                # USE RAW COORDINATES (Unaligned) as per request
                # x_coords = dff['physical_plot_x'] if 'physical_plot_x' in dff.columns else dff['plot_x']

                # Use raw plot_x (which is based on UNIT_INDEX_X)
                fig.add_trace(go.Scatter(
                    x=dff['plot_x'],
                    y=dff['plot_y'],
                    mode='markers',
                    marker=dict(
                        color=layer_color,
                        symbol=symbol,
                        size=9, # Slightly larger for visibility
                        line=dict(width=1, color='black')
                    ),
                    name=trace_name,
                    # REMOVED legendgroup to allow independent toggling of Front/Back layers
                    # legendgroup=f"Layer {layer_num}",
                    customdata=dff[custom_data_cols],
                    hovertemplate=hovertemplate
                ))

    # Add Grid
    fig.update_layout(shapes=create_grid_shapes(panel_rows, panel_cols, quadrant='All'))

    # Calculate ticks (reused from standard map logic)
    cell_width, cell_height = QUADRANT_WIDTH / panel_cols, QUADRANT_HEIGHT / panel_rows
    x_tick_vals_q1 = [(i * cell_width) + (cell_width / 2) for i in range(panel_cols)]
    x_tick_vals_q2 = [(QUADRANT_WIDTH + GAP_SIZE) + (i * cell_width) + (cell_width / 2) for i in range(panel_cols)]
    y_tick_vals_q1 = [(i * cell_height) + (cell_height / 2) for i in range(panel_rows)]
    y_tick_vals_q3 = [(QUADRANT_HEIGHT + GAP_SIZE) + (i * cell_height) + (cell_height / 2) for i in range(panel_rows)]
    x_tick_text = list(range(panel_cols * 2))
    y_tick_text = list(range(panel_rows * 2))

    apply_panel_theme(fig, "Multi-Layer Combined Defect Map (True Defects Only)")

    fig.update_layout(
        xaxis=dict(
            title="Unit Column Index",
            tickvals=x_tick_vals_q1 + x_tick_vals_q2,
            ticktext=x_tick_text,
            range=[-GAP_SIZE, PANEL_WIDTH + (GAP_SIZE * 2)], constrain='domain'
        ),
        yaxis=dict(
            title="Unit Row Index",
            tickvals=y_tick_vals_q1 + y_tick_vals_q3,
            ticktext=y_tick_text,
            range=[-GAP_SIZE, PANEL_HEIGHT + (GAP_SIZE * 2)]
        ),
        legend=dict(title=dict(text="Build-Up Layer"))
    )

    return fig
    
def create_defect_map_figure(df: pd.DataFrame, panel_rows: int, panel_cols: int, quadrant_selection: str = Quadrant.ALL.value, lot_number: Optional[str] = None, title: Optional[str] = None) -> go.Figure:
    """
    Creates the full Defect Map Figure (Traces + Grid + Layout).
    """
    fig = go.Figure(data=create_defect_traces(df))
    fig.update_layout(shapes=create_grid_shapes(panel_rows, panel_cols, quadrant_selection))

    # Calculate ticks and ranges
    cell_width, cell_height = QUADRANT_WIDTH / panel_cols, QUADRANT_HEIGHT / panel_rows
    x_tick_vals_q1 = [(i * cell_width) + (cell_width / 2) for i in range(panel_cols)]
    x_tick_vals_q2 = [(QUADRANT_WIDTH + GAP_SIZE) + (i * cell_width) + (cell_width / 2) for i in range(panel_cols)]
    y_tick_vals_q1 = [(i * cell_height) + (cell_height / 2) for i in range(panel_rows)]
    y_tick_vals_q3 = [(QUADRANT_HEIGHT + GAP_SIZE) + (i * cell_height) + (cell_height / 2) for i in range(panel_rows)]
    x_tick_text, y_tick_text = list(range(panel_cols * 2)), list(range(panel_rows * 2))
    x_axis_range, y_axis_range, show_ticks = [-GAP_SIZE, PANEL_WIDTH + (GAP_SIZE * 2)], [-GAP_SIZE, PANEL_HEIGHT + (GAP_SIZE * 2)], True

    if quadrant_selection != Quadrant.ALL.value:
        show_ticks = False
        ranges = {
            'Q1': ([0, QUADRANT_WIDTH], [0, QUADRANT_HEIGHT]),
            'Q2': ([QUADRANT_WIDTH + GAP_SIZE, PANEL_WIDTH + GAP_SIZE], [0, QUADRANT_HEIGHT]),
            'Q3': ([0, QUADRANT_WIDTH], [QUADRANT_HEIGHT + GAP_SIZE, PANEL_HEIGHT + GAP_SIZE]),
            'Q4': ([QUADRANT_WIDTH + GAP_SIZE, PANEL_WIDTH + GAP_SIZE], [QUADRANT_HEIGHT + GAP_SIZE, PANEL_HEIGHT + GAP_SIZE])
        }
        x_axis_range, y_axis_range = ranges[quadrant_selection]

    final_title = title if title else f"Panel Defect Map - Quadrant: {quadrant_selection}"

    apply_panel_theme(fig, final_title)

    fig.update_layout(
        xaxis=dict(title="Unit Column Index", tickvals=x_tick_vals_q1 + x_tick_vals_q2 if show_ticks else [], ticktext=x_tick_text if show_ticks else [], range=x_axis_range, constrain='domain'),
        yaxis=dict(title="Unit Row Index", tickvals=y_tick_vals_q1 + y_tick_vals_q3 if show_ticks else [], ticktext=y_tick_text if show_ticks else [], range=y_axis_range)
    )

    if lot_number and quadrant_selection == Quadrant.ALL.value:
        fig.add_annotation(x=PANEL_WIDTH + GAP_SIZE, y=PANEL_HEIGHT + GAP_SIZE, text=f"<b>Lot #: {lot_number}</b>", showarrow=False, font=dict(size=14, color=TEXT_COLOR), align="right", xanchor="right", yanchor="bottom")

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

    grouped_data = df.groupby(['QUADRANT', group_col]).size().reset_index(name='Count')
    top_items = df[group_col].value_counts().index.tolist()

    traces = []
    quadrants = ['Q1', 'Q2', 'Q3', 'Q4']
    for quadrant in quadrants:
        quadrant_data = grouped_data[grouped_data['QUADRANT'] == quadrant]
        pivot = quadrant_data.pivot(index=group_col, columns='QUADRANT', values='Count').reindex(top_items).fillna(0)
        if not pivot.empty:
            traces.append(go.Bar(name=quadrant, x=pivot.index, y=pivot[quadrant]))
    return traces

def create_pareto_figure(df: pd.DataFrame, quadrant_selection: str = Quadrant.ALL.value) -> go.Figure:
    """
    Creates the Pareto Figure (Traces + Layout).
    """
    fig = go.Figure()
    if quadrant_selection == Quadrant.ALL.value:
        for trace in create_grouped_pareto_trace(df): fig.add_trace(trace)
        fig.update_layout(barmode='stack')
    else:
        fig.add_trace(create_pareto_trace(df))

    apply_panel_theme(fig, f"Defect Pareto - Quadrant: {quadrant_selection}", height=600)

    fig.update_layout(
        xaxis=dict(title="Defect Type", categoryorder='total descending'),
        yaxis=dict(showgrid=True) # Override to show grid on Pareto
    )
    return fig

def create_verification_status_chart(df: pd.DataFrame) -> List[go.Bar]:
    # ... (omitted for brevity, same as before)
    if df.empty: return []
    grouped = df.groupby(['DEFECT_TYPE', 'QUADRANT', 'Verification']).size().unstack(fill_value=0)
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
    true_defect_data: Dict[Tuple[int, int], Dict[str, Any]]
) -> Tuple[List[Dict[str, Any]], List[go.Scatter]]:
    """
    Creates the shapes for the 'Still Alive' map AND invisible scatter points for tooltips.

    Returns:
        (shapes, traces)
    """
    shapes = []
    traces = []

    total_cols, total_rows = panel_cols * 2, panel_rows * 2
    all_origins = {'Q1': (0, 0), 'Q2': (QUADRANT_WIDTH + GAP_SIZE, 0), 'Q3': (0, QUADRANT_HEIGHT + GAP_SIZE), 'Q4': (QUADRANT_WIDTH + GAP_SIZE, QUADRANT_HEIGHT + GAP_SIZE)}
    cell_width, cell_height = QUADRANT_WIDTH / panel_cols, QUADRANT_HEIGHT / panel_rows

    # Prepare lists for scatter trace (Tooltips)
    hover_x = []
    hover_y = []
    hover_text = []
    hover_colors = []

    # 1. Draw the colored cells first (without borders)
    for row in range(total_rows):
        for col in range(total_cols):
            quadrant_col, local_col = divmod(col, panel_cols)
            quadrant_row, local_row = divmod(row, panel_rows)
            quad_key = f"Q{quadrant_row * 2 + quadrant_col + 1}"
            x_origin, y_origin = all_origins[quad_key]
            x0, y0 = x_origin + local_col * cell_width, y_origin + local_row * cell_height

            # Determine status
            is_dead = (col, row) in true_defect_data

            if is_dead:
                metadata = true_defect_data[(col, row)]
                first_killer = metadata['first_killer_layer']

                # Color logic: Map Layer Num to Color from Fallback/Neon
                # We reuse FALLBACK_COLORS.
                # Note: This is simplistic. Layer 1 = Index 0, etc.
                color_idx = (first_killer - 1) % len(FALLBACK_COLORS)
                fill_color = FALLBACK_COLORS[color_idx]

                # Add to hover data
                center_x = x0 + cell_width/2
                center_y = y0 + cell_height/2
                hover_x.append(center_x)
                hover_y.append(center_y)

                tooltip = (
                    f"<b>Unit: ({col}, {row})</b><br>"
                    f"First Killer: Layer {first_killer}<br>"
                    f"Details: {metadata['defect_summary']}"
                )
                hover_text.append(tooltip)
                hover_colors.append(fill_color)

            else:
                fill_color = ALIVE_CELL_COLOR

            shapes.append({'type': 'rect', 'x0': x0, 'y0': y0, 'x1': x0 + cell_width, 'y1': y0 + cell_height, 'fillcolor': fill_color, 'line': {'width': 0}, 'layer': 'below'})

    # 2. Draw grid lines over the colored cells
    shapes.extend(create_grid_shapes(panel_rows, panel_cols, quadrant='All', fill=False))

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
    true_defect_data: Dict[Tuple[int, int], Dict[str, Any]]
) -> go.Figure:
    """
    Creates the Still Alive Map Figure (Shapes + Layout + Tooltips).
    """
    map_shapes, hover_traces = create_still_alive_map(panel_rows, panel_cols, true_defect_data)

    fig = go.Figure(data=hover_traces) # Add hover traces

    cell_width, cell_height = QUADRANT_WIDTH / panel_cols, QUADRANT_HEIGHT / panel_rows
    x_tick_vals_q1 = [(i * cell_width) + (cell_width / 2) for i in range(panel_cols)]
    x_tick_vals_q2 = [(QUADRANT_WIDTH + GAP_SIZE) + (i * cell_width) + (cell_width / 2) for i in range(panel_cols)]
    y_tick_vals_q1 = [(i * cell_height) + (cell_height / 2) for i in range(panel_rows)]
    y_tick_vals_q3 = [(QUADRANT_HEIGHT + GAP_SIZE) + (i * cell_height) + (cell_height / 2) for i in range(panel_rows)]
    x_tick_text = list(range(panel_cols * 2))
    y_tick_text = list(range(panel_rows * 2))

    apply_panel_theme(fig, f"Still Alive Map ({len(true_defect_data)} Defective Cells)")

    fig.update_layout(
        xaxis=dict(
            title="Unit Column Index", range=[-GAP_SIZE, PANEL_WIDTH + (GAP_SIZE * 2)], constrain='domain',
            tickvals=x_tick_vals_q1 + x_tick_vals_q2, ticktext=x_tick_text
        ),
        yaxis=dict(
            title="Unit Row Index", range=[-GAP_SIZE, PANEL_HEIGHT + (GAP_SIZE * 2)],
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

def create_defect_sankey(df: pd.DataFrame) -> go.Sankey:
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
    sankey_df = df.groupby(['DEFECT_TYPE', 'Verification']).size().reset_index(name='Count')

    # Calculate Totals for Labels and Sorting
    total_defects = sankey_df['Count'].sum()
    defect_counts = sankey_df.groupby('DEFECT_TYPE')['Count'].sum().sort_values(ascending=False)
    verification_counts = sankey_df.groupby('Verification')['Count'].sum().sort_values(ascending=False)

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

    apply_panel_theme(fig, "Defect Type → Verification Flow Analysis", height=700)

    fig.update_layout(
        font=dict(size=12, color=TEXT_COLOR),
        margin=dict(l=20, r=20, t=60, b=20),
        xaxis=dict(showgrid=False, showline=False), # Sankey doesn't need axes
        yaxis=dict(showgrid=False, showline=False)
    )
    return fig

def create_unit_grid_heatmap(df: pd.DataFrame, panel_rows: int, panel_cols: int) -> go.Figure:
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

    if df_true.empty:
        return go.Figure(layout=dict(
            title=dict(text="No True Defects Found for Heatmap", font=dict(color=TEXT_COLOR)),
            paper_bgcolor=BACKGROUND_COLOR, plot_bgcolor=PLOT_AREA_COLOR
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
        colorbar=dict(title='Defects', title_font=dict(color=TEXT_COLOR), tickfont=dict(color=TEXT_COLOR)),
        hovertemplate='Global Unit: (%{x}, %{y})<br>Defects: %{z}<extra></extra>'
    ))

    # Fix Axis Ranges
    total_global_cols = panel_cols * 2
    total_global_rows = panel_rows * 2

    apply_panel_theme(fig, "1. Unit Grid Density (Yield Loss Map)", height=700)

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
    show_grid: bool = True
) -> go.Figure:
    """
    2. Smoothed Density Contour Map (Weather Map).
    Supports points overlay, variable smoothing, saturation cap, and grid toggle.
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

    fig = go.Figure()

    # 1. Contour Layer
    # Configure saturation
    zmax = saturation_cap if saturation_cap > 0 else None

    fig.add_trace(go.Histogram2dContour(
        x=df_true['plot_x'],
        y=df_true['plot_y'],
        colorscale='Turbo', # Vibrant, engineering style
        reversescale=False,
        ncontours=30,
        nbinsx=smoothing_factor, # Adjustable smoothing
        nbinsy=smoothing_factor,
        zmax=zmax,
        contours=dict(coloring='heatmap', showlabels=True, labelfont=dict(color='white')),
        hoverinfo='x+y+z'
    ))

    # 2. Points Overlay (Hybrid View)
    if show_points:
        # Re-use trace logic or simple scatter
        fig.add_trace(go.Scatter(
            x=df_true['plot_x'],
            y=df_true['plot_y'],
            mode='markers',
            marker=dict(color='white', size=3, opacity=0.5),
            hoverinfo='skip', # Contour has hover
            name='Defects'
        ))

    # 3. Grid Overlay
    shapes = []
    if show_grid:
        shapes = create_grid_shapes(panel_rows, panel_cols, quadrant='All', fill=False)

    # 4. Axis Labels (Mapped to Unit Index)
    # Convert mm ticks to Unit Index
    cell_width = QUADRANT_WIDTH / panel_cols
    cell_height = QUADRANT_HEIGHT / panel_rows

    total_cols = panel_cols * 2
    total_rows = panel_rows * 2

    # Generate ticks at the center of each unit
    x_tick_vals = []
    x_tick_text = []
    for i in range(total_cols):
        # Calculate center of unit i
        # Handle Gap: If i >= panel_cols, add GAP_SIZE
        offset = GAP_SIZE if i >= panel_cols else 0
        center_mm = (i * cell_width) + (cell_width / 2) + offset
        x_tick_vals.append(center_mm)
        x_tick_text.append(str(i))

    y_tick_vals = []
    y_tick_text = []
    for i in range(total_rows):
        offset = GAP_SIZE if i >= panel_rows else 0
        center_mm = (i * cell_height) + (cell_height / 2) + offset
        y_tick_vals.append(center_mm)
        y_tick_text.append(str(i))

    apply_panel_theme(fig, "2. Smoothed Defect Density (Hotspots)", height=700)

    fig.update_layout(
        xaxis=dict(
            title="Unit Column Index (Approx)",
            tickvals=x_tick_vals,
            ticktext=x_tick_text,
            range=[-GAP_SIZE, PANEL_WIDTH + GAP_SIZE*2], constrain='domain'
        ),
        yaxis=dict(
            title="Unit Row Index (Approx)",
            tickvals=y_tick_vals,
            ticktext=y_tick_text,
            range=[-GAP_SIZE, PANEL_HEIGHT + GAP_SIZE*2]
        ),
        shapes=shapes
    )
    return fig


def create_defect_sunburst(df: pd.DataFrame) -> go.Figure:
    """
    Creates a Sunburst chart: Defect Type -> Verification (if avail).
    Hierarchy: Total -> Defect Type -> Verification Status
    """
    if df.empty:
        return go.Figure()

    has_verification = df['HAS_VERIFICATION_DATA'].iloc[0] if 'HAS_VERIFICATION_DATA' in df.columns else False

    # 1. Aggregate
    if has_verification:
        grouped = df.groupby(['DEFECT_TYPE', 'Verification']).size().reset_index(name='Count')
    else:
        grouped = df.groupby(['DEFECT_TYPE']).size().reset_index(name='Count')

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

    # Level 1: Defect Type
    for dtype in grouped['DEFECT_TYPE'].unique():
        dtype_count = grouped[grouped['DEFECT_TYPE'] == dtype]['Count'].sum()
        ids.append(f"{dtype}")
        labels.append(dtype)
        parents.append("Total")
        values.append(dtype_count)

        # Level 2: Verification (if exists)
        if has_verification:
            dtype_df = grouped[grouped['DEFECT_TYPE'] == dtype]
            for ver in dtype_df['Verification'].unique():
                ver_count = dtype_df[dtype_df['Verification'] == ver]['Count'].sum()
                ids.append(f"{dtype}-{ver}")
                labels.append(ver)
                parents.append(f"{dtype}")
                values.append(ver_count)

    fig = go.Figure(go.Sunburst(
        ids=ids,
        labels=labels,
        parents=parents,
        values=values,
        branchvalues="total"
    ))
    # IMPROVEMENT: Fix "Black and White" export by setting dark theme colors
    fig.update_layout(
        margin=dict(t=0, l=0, r=0, b=0),
        height=500,
        paper_bgcolor=BACKGROUND_COLOR,
        font=dict(color=TEXT_COLOR)
    )

    return fig

def create_stress_heatmap(data: StressMapData, panel_rows: int, panel_cols: int) -> go.Figure:
    """
    Creates the Cumulative Stress Heatmap with defect counts in cells.
    """
    if data.total_defects == 0:
        return go.Figure(layout=dict(
            title=dict(text="No True Defects Found in Selection", font=dict(color=TEXT_COLOR)),
            paper_bgcolor=BACKGROUND_COLOR, plot_bgcolor=PLOT_AREA_COLOR
        ))

    # Mask zero values so they appear empty/background color
    z_data = data.grid_counts.astype(float)
    z_data[z_data == 0] = np.nan

    text_data = data.grid_counts.astype(str)
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
        colorbar=dict(title='Defects', title_font=dict(color=TEXT_COLOR), tickfont=dict(color=TEXT_COLOR))
    ))

    total_cols = panel_cols * 2
    total_rows = panel_rows * 2

    apply_panel_theme(fig, "Cumulative Stress Map (Total Defects per Unit)", height=700)

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
    return fig

def create_delta_heatmap(data_a: StressMapData, data_b: StressMapData, panel_rows: int, panel_cols: int) -> go.Figure:
    """
    Creates a Delta Heatmap (Group A - Group B).
    """
    diff_grid = data_a.grid_counts.astype(float) - data_b.grid_counts.astype(float)

    # Text: Show signed difference
    text_data = np.array([f"{int(x):+d}" if x != 0 else "" for x in diff_grid.flatten()]).reshape(diff_grid.shape)

    # Mask zeros for visual clarity
    diff_grid[diff_grid == 0] = np.nan

    fig = go.Figure(data=go.Heatmap(
        z=diff_grid,
        text=text_data,
        texttemplate="%{text}",
        colorscale='RdBu_r', # Red for positive (more in A), Blue for negative (more in B)
        zmid=0,
        xgap=2, ygap=2,
        colorbar=dict(title='Delta (A - B)', title_font=dict(color=TEXT_COLOR), tickfont=dict(color=TEXT_COLOR))
    ))

    total_cols = panel_cols * 2
    total_rows = panel_rows * 2

    apply_panel_theme(fig, "Delta Stress Map (Group A - Group B)", height=700)

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
    return fig

def create_cross_section_heatmap(
    matrix: np.ndarray,
    layer_labels: List[str],
    axis_labels: List[str],
    slice_desc: str
) -> go.Figure:
    """
    Creates the Z-Axis Cross Section Heatmap (Virtual Slice).
    """
    # Inverse Y-axis so Layer 1 is at top (if not already handled by input order)
    # Actually, Heatmap Y-axis 0 is usually bottom. We need to flip visual range or data order.
    # We'll just set 'autorange="reversed"' in layout for Y axis so top of list is top of chart.

    if matrix.size == 0:
         return go.Figure(layout=dict(title=dict(text="No Data for Cross-Section", font=dict(color=TEXT_COLOR))))

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
        colorbar=dict(title='Defects', title_font=dict(color=TEXT_COLOR), tickfont=dict(color=TEXT_COLOR))
    ))

    apply_panel_theme(fig, f"Virtual Cross-Section: {slice_desc}", height=600)

    fig.update_layout(
        xaxis=dict(title="Unit Index (Slice Position)"),
        yaxis=dict(title="Layer Stack", autorange="reversed") # Ensure Layer 1 is at top
    )

    return fig
