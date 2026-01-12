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
from src.documentation import VERIFICATION_DESCRIPTIONS

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
    Generates scatter plot traces.

    SWITCHING LOGIC:
    - If real verification data exists (HAS_VERIFICATION_DATA=True), group by 'Verification'.
    - If NO verification data, group by 'DEFECT_TYPE'.
    """
    traces = []
    if df.empty: return traces

    # Check the flag. If mixed (some rows T, some F), default to True if any are True
    has_verification_data = df['HAS_VERIFICATION_DATA'].any() if 'HAS_VERIFICATION_DATA' in df.columns else False

    # Determine what column to group by
    group_col = 'Verification' if has_verification_data else 'DEFECT_TYPE'

    unique_groups = df[group_col].unique()

    # --- COLOR MAPPING ---
    # We need a dynamic color map for whatever column we are grouping by.
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
        # We can reuse the FALLBACK_COLORS or define specific ones if needed.
        # Simple approach: Assign distinct colors from the fallback list.
        fallback_index = 0
        for code in unique_groups:
            # If we want specific colors for 'N' (Green) or 'False Alarm', we could add logic here.
            # For now, purely dynamic to handle ANY code.
            color = FALLBACK_COLORS[fallback_index % len(FALLBACK_COLORS)]
            local_style_map[code] = color
            fallback_index += 1

    # Generate traces
    for group_val, color in local_style_map.items():
        dff = df[df[group_col] == group_val]
        if not dff.empty:
            # Map descriptions if available
            # If group_col is Verification, use that code. Else use Verification col if it exists.

            # We want to create a Description column for customdata
            # Assuming 'Verification' column holds the code (e.g., 'CU22')
            if 'Verification' in dff.columns:
                 dff = dff.copy() # Avoid SettingWithCopyWarning
                 dff['Description'] = dff['Verification'].map(VERIFICATION_DESCRIPTIONS).fillna("Unknown Code")
            else:
                 dff['Description'] = "N/A"

            custom_data_cols = ['UNIT_INDEX_X', 'UNIT_INDEX_Y', 'DEFECT_TYPE', 'DEFECT_ID', 'Verification', 'Description']

            # Hover Template: Verification Status -> Description -> Defect Type -> Unit Index -> Defect ID
            # Requested format: "Description : Short on Surface (AOI)"
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
                name=group_val, # Legend shows 'CU22' or 'Nick' depending on mode
                customdata=dff[custom_data_cols],
                hovertemplate=hovertemplate
            ))

    return traces
    
def create_pareto_trace(df: pd.DataFrame) -> go.Bar:
    if df.empty: return go.Bar(name='Pareto')

    has_verification_data = df['HAS_VERIFICATION_DATA'].any() if 'HAS_VERIFICATION_DATA' in df.columns else False
    group_col = 'Verification' if has_verification_data else 'DEFECT_TYPE'

    pareto_data = df[group_col].value_counts().reset_index()
    pareto_data.columns = ['Label', 'Count']

    # Simple color logic (grey) since we don't have a persistent map for dynamic verification codes in this scope easily,
    # or we can reuse the logic. For simplicity, we use a default color.
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

def create_defect_sankey(df: pd.DataFrame) -> go.Sankey:
    """
    Creates a Sankey diagram mapping Defect Types (Left) to Verification Status (Right).
    Only returns a figure if HAS_VERIFICATION_DATA is true.
    """
    if df.empty:
        return None

    has_verification = df['HAS_VERIFICATION_DATA'].iloc[0] if 'HAS_VERIFICATION_DATA' in df.columns else False
    if not has_verification:
        return None

    # Prepare data for Sankey
    # Group by [DEFECT_TYPE, Verification] and count
    sankey_df = df.groupby(['DEFECT_TYPE', 'Verification']).size().reset_index(name='Count')

    # Create unique labels list
    defect_types = sankey_df['DEFECT_TYPE'].unique().tolist()
    verification_statuses = sankey_df['Verification'].unique().tolist()

    # To differentiate if a label name exists in both columns (unlikely but safe), we can suffix them internally or just combine
    all_labels = defect_types + verification_statuses

    # Map labels to indices
    label_map = {label: i for i, label in enumerate(all_labels)}

    sources = []
    targets = []
    values = []

    for _, row in sankey_df.iterrows():
        sources.append(label_map[row['DEFECT_TYPE']])
        targets.append(label_map[row['Verification']])
        values.append(row['Count'])

    # Colors for nodes
    # We can use a palette.
    node_colors = ["#1f77b4"] * len(defect_types) + ["#ff7f0e"] * len(verification_statuses)

    fig = go.Figure(data=[go.Sankey(
        node=dict(
            pad=15,
            thickness=20,
            line=dict(color="black", width=0.5),
            label=all_labels,
            color=node_colors
        ),
        link=dict(
            source=sources,
            target=targets,
            value=values
        )
    )])

    fig.update_layout(title_text="Defect Type → Verification Flow", font_size=10, height=600, paper_bgcolor='rgba(0,0,0,0)')
    return fig

def create_defect_heatmap(df: pd.DataFrame, panel_rows: int, panel_cols: int, quadrant_selection: str) -> go.Figure:
    """
    Creates a density heatmap (Histogram2dContour) of defect locations.
    """
    if df.empty:
        return go.Figure()

    # Create the density plot
    fig = go.Figure(go.Histogram2dContour(
        x=df['plot_x'],
        y=df['plot_y'],
        colorscale='Hot',
        reversescale=True,
        xaxis='x',
        yaxis='y',
        ncontours=20
    ))

    # Overlay the grid for context
    shapes = create_grid_shapes(panel_rows, panel_cols, quadrant_selection, fill=False)

    # Define axes ranges similar to the main defect map
    x_axis_range = [-GAP_SIZE, PANEL_WIDTH + (GAP_SIZE * 2)]
    y_axis_range = [-GAP_SIZE, PANEL_HEIGHT + (GAP_SIZE * 2)]

    if quadrant_selection != 'All':
         ranges = {
            'Q1': ([0, QUADRANT_WIDTH], [0, QUADRANT_HEIGHT]),
            'Q2': ([QUADRANT_WIDTH + GAP_SIZE, PANEL_WIDTH + GAP_SIZE], [0, QUADRANT_HEIGHT]),
            'Q3': ([0, QUADRANT_WIDTH], [QUADRANT_HEIGHT + GAP_SIZE, PANEL_HEIGHT + GAP_SIZE]),
            'Q4': ([QUADRANT_WIDTH + GAP_SIZE, PANEL_WIDTH + GAP_SIZE], [QUADRANT_HEIGHT + GAP_SIZE, PANEL_HEIGHT + GAP_SIZE])
        }
         x_axis_range, y_axis_range = ranges[quadrant_selection]

    fig.update_layout(
        xaxis=dict(range=x_axis_range, showgrid=False, zeroline=False, showline=True, mirror=True),
        yaxis=dict(range=y_axis_range, showgrid=False, zeroline=False, showline=True, mirror=True, scaleanchor="x", scaleratio=1),
        shapes=shapes,
        plot_bgcolor=PANEL_COLOR,
        height=700,
        title_text="Defect Density Heatmap"
    )
    return fig

def create_defect_sunburst(df: pd.DataFrame) -> go.Figure:
    """
    Creates a Sunburst chart: Quadrant -> Defect Type -> Verification (if avail).
    """
    if df.empty:
        return go.Figure()

    has_verification = df['HAS_VERIFICATION_DATA'].iloc[0] if 'HAS_VERIFICATION_DATA' in df.columns else False

    if has_verification:
        path = ['QUADRANT', 'DEFECT_TYPE', 'Verification']
    else:
        path = ['QUADRANT', 'DEFECT_TYPE']

    # 1. Aggregate
    if has_verification:
        grouped = df.groupby(['QUADRANT', 'DEFECT_TYPE', 'Verification']).size().reset_index(name='Count')
    else:
        grouped = df.groupby(['QUADRANT', 'DEFECT_TYPE']).size().reset_index(name='Count')

    # Build lists
    ids = []
    labels = []
    parents = []
    values = []

    # Root
    total_count = grouped['Count'].sum()
    ids.append("Total")
    labels.append("Total")
    parents.append("")
    values.append(total_count)

    # Level 1: Quadrants
    for quad in grouped['QUADRANT'].unique():
        quad_count = grouped[grouped['QUADRANT'] == quad]['Count'].sum()
        ids.append(f"{quad}")
        labels.append(quad)
        parents.append("Total")
        values.append(quad_count)

        # Level 2: Defect Type
        quad_df = grouped[grouped['QUADRANT'] == quad]
        for dtype in quad_df['DEFECT_TYPE'].unique():
            dtype_count = quad_df[quad_df['DEFECT_TYPE'] == dtype]['Count'].sum()
            ids.append(f"{quad}-{dtype}")
            labels.append(dtype)
            parents.append(f"{quad}")
            values.append(dtype_count)

            # Level 3: Verification (if exists)
            if has_verification:
                dtype_df = quad_df[quad_df['DEFECT_TYPE'] == dtype]
                for ver in dtype_df['Verification'].unique():
                    ver_count = dtype_df[dtype_df['Verification'] == ver]['Count'].sum()
                    ids.append(f"{quad}-{dtype}-{ver}")
                    labels.append(ver)
                    parents.append(f"{quad}-{dtype}")
                    values.append(ver_count)

    fig = go.Figure(go.Sunburst(
        ids=ids,
        labels=labels,
        parents=parents,
        values=values,
        branchvalues="total"
    ))
    fig.update_layout(margin=dict(t=0, l=0, r=0, b=0), height=500)

    return fig