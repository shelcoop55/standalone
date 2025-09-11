"""
Plotting and Visualization Module.
This version draws a true-to-scale simulation of a 510x510mm physical panel.
"""
import plotly.graph_objects as go
import pandas as pd
from typing import List, Dict, Any

from src.config import PANEL_COLOR, GRID_COLOR, defect_style_map, TEXT_COLOR
# --- NEW: Import the physical dimensions from the data handler ---
from src.data_handler import QUADRANT_WIDTH, QUADRANT_HEIGHT, PANEL_WIDTH, PANEL_HEIGHT

def create_grid_shapes(panel_rows: int, panel_cols: int, gap_size: int, quadrant: str = 'All') -> List[Dict[str, Any]]:
    """
    Creates the visual shapes for the panel grid in a fixed 510x510mm coordinate system.
    The grid lines are scaled based on the number of rows/cols to fit the fixed quadrant size.
    """
    shapes = []
    
    # --- NEW LOGIC: Calculate the physical size of each grid cell for drawing ---
    cell_width = QUADRANT_WIDTH / panel_cols
    cell_height = QUADRANT_HEIGHT / panel_rows

    # --- The origins are now defined by the fixed physical dimensions ---
    all_origins = {
        'Q1': (0, 0),
        'Q2': (QUADRANT_WIDTH + gap_size, 0),
        'Q3': (0, QUADRANT_HEIGHT + gap_size),
        'Q4': (QUADRANT_WIDTH + gap_size, QUADRANT_HEIGHT + gap_size)
    }
    
    origins_to_draw = all_origins if quadrant == 'All' else {quadrant: all_origins[quadrant]}
    
    # --- Draw the gap/saw street shapes if showing the full panel ---
    if quadrant == 'All':
        gap_color = '#A8652A' # A color for the gap
        total_width_with_gap = PANEL_WIDTH + gap_size
        total_height_with_gap = PANEL_HEIGHT + gap_size
        
        # Vertical gap
        shapes.append(dict(
            type="rect", x0=QUADRANT_WIDTH, y0=0, x1=QUADRANT_WIDTH + gap_size, y1=total_height_with_gap,
            fillcolor=gap_color, line_width=0, layer='below'
        ))
        # Horizontal gap
        shapes.append(dict(
            type="rect", x0=0, y0=QUADRANT_HEIGHT, x1=total_width_with_gap, y1=QUADRANT_HEIGHT + gap_size,
            fillcolor=gap_color, line_width=0, layer='below'
        ))

    # --- Draw the quadrants and their internal grid lines ---
    for x_start, y_start in origins_to_draw.values():
        # Draw the main quadrant rectangle outline
        shapes.append(dict(
            type="rect",
            x0=x_start, y0=y_start,
            x1=x_start + QUADRANT_WIDTH, y1=y_start + QUADRANT_HEIGHT,
            line=dict(color=GRID_COLOR, width=3),
            fillcolor=PANEL_COLOR,
            layer='below'
        ))
        
        # Draw vertical grid lines based on calculated cell_width
        for i in range(1, panel_cols):
            line_x = x_start + (i * cell_width)
            shapes.append(dict(
                type="line", x0=line_x, y0=y_start, x1=line_x, y1=y_start + QUADRANT_HEIGHT,
                line=dict(color=GRID_COLOR, width=0.5, dash='dot'), opacity=0.5, layer='below'
            ))
        
        # Draw horizontal grid lines based on calculated cell_height
        for i in range(1, panel_rows):
            line_y = y_start + (i * cell_height)
            shapes.append(dict(
                type="line", x0=x_start, y0=line_y, x1=x_start + QUADRANT_WIDTH, y1=line_y,
                line=dict(color=GRID_COLOR, width=0.5, dash='dot'), opacity=0.5, layer='below'
            ))
            
    return shapes

def create_defect_traces(df: pd.DataFrame) -> List[go.Scatter]:
    """
    Creates a list of scatter traces, one for each defect type in the dataframe.
    This function is unchanged as it plots the pre-calculated 'plot_x' and 'plot_y'.
    """
    traces = []
    for dtype, color in defect_style_map.items():
        dff = df[df['DEFECT_TYPE'] == dtype]
        if not dff.empty:
            traces.append(go.Scatter(
                x=dff['plot_x'], y=dff['plot_y'], mode='markers',
                marker=dict(color=color, size=8, line=dict(width=1, color='black')),
                name=dtype,
                customdata=dff[['UNIT_INDEX_X', 'UNIT_INDEX_Y', 'DEFECT_TYPE', 'DEFECT_ID']],
                hovertemplate=(
                    "<b>Type: %{customdata[2]}</b><br>"
                    "Unit Index (X, Y): (%{customdata[0]}, %{customdata[1]})<br>"
                    "Defect ID: %{customdata[3]}"
                    "<extra></extra>"
                )
            ))
    return traces
    
def create_pareto_trace(df: pd.DataFrame) -> go.Bar:
    """
    This function is unchanged. It operates on categorical data only.
    """
    if df.empty:
        return go.Bar(name='Pareto')
    pareto_data = df['DEFECT_TYPE'].value_counts().reset_index()
    pareto_data.columns = ['Defect Type', 'Count']
    return go.Bar(
        x=pareto_data['Defect Type'],
        y=pareto_data['Count'],
        name='Pareto',
        marker_color=[defect_style_map.get(dtype, 'grey') for dtype in pareto_data['Defect Type']]
    )

def create_grouped_pareto_trace(df: pd.DataFrame) -> List[go.Bar]:
    """
    This function is unchanged. It operates on categorical data only.
    """
    if df.empty:
        return []
    grouped_data = df.groupby(['QUADRANT', 'DEFECT_TYPE']).size().reset_index(name='Count')
    top_defects = df['DEFECT_TYPE'].value_counts().index.tolist()
    traces = []
    quadrants = ['Q1', 'Q2', 'Q3', 'Q4']
    for quadrant in quadrants:
        quadrant_data = grouped_data[grouped_data['QUADRANT'] == quadrant]
        pivot = quadrant_data.pivot(index='DEFECT_TYPE', columns='QUADRANT', values='Count').reindex(top_defects).fillna(0)
        if not pivot.empty:
            traces.append(go.Bar(
                name=quadrant,
                x=pivot.index,
                y=pivot[quadrant]
            ))
    return traces