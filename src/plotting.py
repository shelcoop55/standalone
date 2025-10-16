"""
Plotting and Visualization Module.
This version draws a true-to-scale simulation of a 510x510mm physical panel.
UPDATED: Now includes an outer border frame and has been refactored for clarity.
"""
import plotly.graph_objects as go
import pandas as pd
from typing import List, Dict, Any, Set, Tuple

from src.config import (
    PANEL_COLOR, GRID_COLOR, defect_style_map, TEXT_COLOR,
    PANEL_WIDTH, PANEL_HEIGHT, GAP_SIZE,
    ALIVE_CELL_COLOR, DEFECTIVE_CELL_COLOR, FALLBACK_COLORS
)
from src.data_handler import QUADRANT_WIDTH, QUADRANT_HEIGHT

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
    Generates scatter plot traces for each defect type in the dataframe.
    It dynamically assigns colors to defect types not present in the predefined
    style map by using a fallback color list. This ensures all defects are plotted.
    """
    traces = []
    has_verification = 'Verification' in df.columns

    # Get all unique defect types from the current data
    unique_defect_types = df['DEFECT_TYPE'].unique()

    # Create a mutable copy of the defect style map
    local_style_map = defect_style_map.copy()

    # Assign fallback colors to new defect types
    fallback_color_index = 0
    for dtype in unique_defect_types:
        if dtype not in local_style_map:
            color = FALLBACK_COLORS[fallback_color_index % len(FALLBACK_COLORS)]
            local_style_map[dtype] = color
            fallback_color_index += 1
            print(f"INFO: New defect type '{dtype}' found. Assigned fallback color '{color}'.")

    # Generate traces for each defect type using the updated map
    for dtype, color in local_style_map.items():
        dff = df[df['DEFECT_TYPE'] == dtype]
        if not dff.empty:
            custom_data_cols = ['UNIT_INDEX_X', 'UNIT_INDEX_Y', 'DEFECT_TYPE', 'DEFECT_ID']
            hovertemplate = ("<b>Type: %{customdata[2]}</b><br>"
                             "Unit Index (X, Y): (%{customdata[0]}, %{customdata[1]})<br>"
                             "Defect ID: %{customdata[3]}")
            if has_verification:
                custom_data_cols.append('Verification')
                hovertemplate += "<br>Verification: %{customdata[4]}"
            hovertemplate += "<extra></extra>"

            traces.append(go.Scatter(
                x=dff['plot_x'],
                y=dff['plot_y'],
                mode='markers',
                marker=dict(color=color, size=8, line=dict(width=1, color='black')),
                name=dtype,
                customdata=dff[custom_data_cols],
                hovertemplate=hovertemplate
            ))

    return traces
    
def create_pareto_trace(df: pd.DataFrame) -> go.Bar:
    # ... (omitted for brevity, same as before)
    if df.empty: return go.Bar(name='Pareto')
    pareto_data = df['DEFECT_TYPE'].value_counts().reset_index()
    pareto_data.columns = ['Defect Type', 'Count']
    return go.Bar(x=pareto_data['Defect Type'], y=pareto_data['Count'], name='Pareto', marker_color=[defect_style_map.get(dtype, 'grey') for dtype in pareto_data['Defect Type']])

def create_grouped_pareto_trace(df: pd.DataFrame) -> List[go.Bar]:
    # ... (omitted for brevity, same as before)
    if df.empty: return []
    grouped_data = df.groupby(['QUADRANT', 'DEFECT_TYPE']).size().reset_index(name='Count')
    top_defects = df['DEFECT_TYPE'].value_counts().index.tolist()
    traces = []
    quadrants = ['Q1', 'Q2', 'Q3', 'Q4']
    for quadrant in quadrants:
        quadrant_data = grouped_data[grouped_data['QUADRANT'] == quadrant]
        pivot = quadrant_data.pivot(index='DEFECT_TYPE', columns='QUADRANT', values='Count').reindex(top_defects).fillna(0)
        if not pivot.empty:
            traces.append(go.Bar(name=quadrant, x=pivot.index, y=pivot[quadrant]))
    return traces

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

def create_still_alive_map(panel_rows: int, panel_cols: int, true_defect_coords: Set[Tuple[int, int]]) -> List[Dict[str, Any]]:
    """
    Creates the shapes for the 'Still Alive' map by drawing colored cells and an overlay grid.
    """
    shapes = []
    total_cols, total_rows = panel_cols * 2, panel_rows * 2
    all_origins = {'Q1': (0, 0), 'Q2': (QUADRANT_WIDTH + GAP_SIZE, 0), 'Q3': (0, QUADRANT_HEIGHT + GAP_SIZE), 'Q4': (QUADRANT_WIDTH + GAP_SIZE, QUADRANT_HEIGHT + GAP_SIZE)}
    cell_width, cell_height = QUADRANT_WIDTH / panel_cols, QUADRANT_HEIGHT / panel_rows

    # 1. Draw the colored cells first (without borders)
    for row in range(total_rows):
        for col in range(total_cols):
            quadrant_col, local_col = divmod(col, panel_cols)
            quadrant_row, local_row = divmod(row, panel_rows)
            quad_key = f"Q{quadrant_row * 2 + quadrant_col + 1}"
            x_origin, y_origin = all_origins[quad_key]
            x0, y0 = x_origin + local_col * cell_width, y_origin + local_row * cell_height
            fill_color = DEFECTIVE_CELL_COLOR if (col, row) in true_defect_coords else ALIVE_CELL_COLOR
            shapes.append({'type': 'rect', 'x0': x0, 'y0': y0, 'x1': x0 + cell_width, 'y1': y0 + cell_height, 'fillcolor': fill_color, 'line': {'width': 0}, 'layer': 'below'})

    # 2. Draw grid lines over the colored cells by calling create_grid_shapes with fill=False
    shapes.extend(create_grid_shapes(panel_rows, panel_cols, quadrant='All', fill=False))

    return shapes