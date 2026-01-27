import plotly.graph_objects as go
import pandas as pd
import numpy as np
from typing import Dict, Tuple, Any, List, Optional
from src.core.geometry import GeometryContext
from src.core.config import (
    PANEL_WIDTH, PANEL_HEIGHT, GAP_SIZE,
    ALIVE_CELL_COLOR, DEFECTIVE_CELL_COLOR, FALLBACK_COLORS,
    PlotTheme, TEXT_COLOR, SAFE_VERIFICATION_VALUES, UNIT_EDGE_COLOR, INTER_UNIT_GAP,
    GRID_COLOR, PANEL_BACKGROUND_COLOR, BACKGROUND_COLOR, PLOT_AREA_COLOR
)
from src.enums import Quadrant
from src.plotting.utils import apply_panel_theme
from src.plotting.generators.shapes import create_grid_shapes, get_rounded_rect_path
from src.plotting.generators.traces import create_defect_traces
from src.analytics.models import StressMapData
from src.documentation import VERIFICATION_DESCRIPTIONS
from src.utils.telemetry import track_performance

@track_performance("Plot: Multi-Layer Map")
def create_multi_layer_defect_map(
    df: pd.DataFrame,
    panel_rows: int,
    panel_cols: int,
    ctx: GeometryContext,
    flip_back: bool = True,
    theme_config: Optional[PlotTheme] = None
) -> go.Figure:
    """
    Creates a defect map visualizing defects from ALL layers simultaneously.
    """
    fig = go.Figure()

    if not df.empty:
        if 'LAYER_NUM' not in df.columns: df['LAYER_NUM'] = 0
        unique_layer_nums = sorted(df['LAYER_NUM'].unique())
        layer_colors = {num: FALLBACK_COLORS[i % len(FALLBACK_COLORS)] for i, num in enumerate(unique_layer_nums)}
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

                coord_str = ""
                if 'X_COORDINATES' in dff.columns and 'Y_COORDINATES' in dff.columns:
                    # Vectorized String Formatting
                    x_mm = (dff['X_COORDINATES'] / 1000).map('{:.2f}'.format)
                    y_mm = (dff['Y_COORDINATES'] / 1000).map('{:.2f}'.format)
                    dff['RAW_COORD_STR'] = "(" + x_mm + ", " + y_mm + ") mm"

                    custom_data_cols = ['UNIT_INDEX_X', 'UNIT_INDEX_Y', 'DEFECT_TYPE', 'DEFECT_ID', 'Verification', 'Description', 'SOURCE_FILE', 'RAW_COORD_STR']
                    coord_str = "<br>Raw Coords: %{customdata[7]}"
                else:
                    custom_data_cols = ['UNIT_INDEX_X', 'UNIT_INDEX_Y', 'DEFECT_TYPE', 'DEFECT_ID', 'Verification', 'Description', 'SOURCE_FILE']

                hovertemplate = (f"<b>Layer: {layer_num}</b><br>"
                                 "Side: " + side_name + "<br>"
                                 "Status: %{customdata[4]}<br>"
                                 "Type: %{customdata[2]}<br>"
                                 "Unit Index: (%{customdata[0]}, %{customdata[1]})<br>"
                                 "File: %{customdata[6]}"
                                 + coord_str +
                                 "<extra></extra>")

                if flip_back:
                    x_col_name = 'physical_plot_x_flipped'
                else:
                    x_col_name = 'physical_plot_x_raw'
                x_coords = dff[x_col_name]

                # SHIFT LOGIC (Additive)
                if 'X_COORDINATES' in dff.columns:
                     final_x = x_coords + ctx.visual_origin_x
                     final_y = dff['plot_y'] + ctx.visual_origin_y
                else:
                     final_x = (x_coords + ctx.offset_x) + ctx.visual_origin_x
                     final_y = (dff['plot_y'] + ctx.offset_y) + ctx.visual_origin_y

                fig.add_trace(go.Scattergl(
                    x=final_x, y=final_y, mode='markers',
                    marker=dict(color=layer_color, symbol=symbol, size=9, line=dict(width=1, color='black')),
                    name=trace_name, customdata=dff[custom_data_cols], hovertemplate=hovertemplate
                ))

    # Add Grid (FIXED - No Visual Shift)
    fig.update_layout(shapes=create_grid_shapes(panel_rows, panel_cols, ctx, quadrant='All', theme_config=theme_config))

    quad_width = ctx.quad_width
    quad_height = ctx.quad_height
    cell_width, cell_height = ctx.cell_width, ctx.cell_height
    offset_x, offset_y = ctx.offset_x, ctx.offset_y
    gap_x, gap_y = ctx.effective_gap_x, ctx.effective_gap_y # Use effective gap which includes dyn

    # Calculate Axis Ticks (FIXED - No Visual Shift)
    # Using ctx geometry
    # Q2 starts at offset_x + quad_width + (effective_gap_x - 2*dyn_gap?)
    # Wait, effective_gap_x = fixed + 2*dyn.
    # The Gap between Q1 and Q2 is effective_gap_x.
    # Q1 ends at offset_x + quad_width.
    # Q2 starts at offset_x + quad_width + effective_gap_x.

    x_tick_vals_q1 = [(i * cell_width) + (cell_width / 2) + offset_x for i in range(panel_cols)]
    x_tick_vals_q2 = [(quad_width + gap_x) + (i * cell_width) + (cell_width / 2) + offset_x for i in range(panel_cols)]
    y_tick_vals_q1 = [(i * cell_height) + (cell_height / 2) + offset_y for i in range(panel_rows)]
    y_tick_vals_q3 = [(quad_height + gap_y) + (i * cell_height) + (cell_height / 2) + offset_y for i in range(panel_rows)]
    x_tick_text = list(range(panel_cols * 2))
    y_tick_text = list(range(panel_rows * 2))

    apply_panel_theme(fig, "Multi-Layer Combined Defect Map (True Defects Only)", theme_config=theme_config)

    # FIXED AXIS RANGES (0-510)
    x_range = [0, 510]
    y_range = [0, 515]

    fig.update_layout(
        xaxis=dict(title="Unit Column Index", tickvals=x_tick_vals_q1 + x_tick_vals_q2, ticktext=x_tick_text, range=x_range, constrain='domain'),
        yaxis=dict(title="Unit Row Index", tickvals=y_tick_vals_q1 + y_tick_vals_q3, ticktext=y_tick_text, range=y_range),
        legend=dict(title=dict(text="Build-Up Layer"))
    )

    return fig

@track_performance("Plot: Defect Map")
def create_defect_map_figure(
    df: pd.DataFrame,
    panel_rows: int,
    panel_cols: int,
    ctx: GeometryContext,
    quadrant_selection: str = Quadrant.ALL.value,
    lot_number: Optional[str] = None,
    title: Optional[str] = None,
    theme_config: Optional[PlotTheme] = None
) -> go.Figure:
    """
    Creates the full Defect Map Figure (Traces + Grid + Layout).
    """
    quad_width = ctx.quad_width
    quad_height = ctx.quad_height
    offset_x, offset_y = ctx.offset_x, ctx.offset_y
    gap_x, gap_y = ctx.effective_gap_x, ctx.effective_gap_y
    panel_width, panel_height = ctx.panel_width, ctx.panel_height

    # Traces with Visual Shift (Additive)
    fig = go.Figure(data=create_defect_traces(df, ctx))
    # Grid FIXED
    fig.update_layout(shapes=create_grid_shapes(panel_rows, panel_cols, ctx, quadrant_selection, theme_config=theme_config))

    # Ticks FIXED
    cell_width, cell_height = ctx.cell_width, ctx.cell_height
    x_tick_vals_q1 = [(i * cell_width) + (cell_width / 2) + offset_x for i in range(panel_cols)]
    x_tick_vals_q2 = [(quad_width + gap_x) + (i * cell_width) + (cell_width / 2) + offset_x for i in range(panel_cols)]
    y_tick_vals_q1 = [(i * cell_height) + (cell_height / 2) + offset_y for i in range(panel_rows)]
    y_tick_vals_q3 = [(quad_height + gap_y) + (i * cell_height) + (cell_height / 2) + offset_y for i in range(panel_rows)]
    x_tick_text, y_tick_text = list(range(panel_cols * 2)), list(range(panel_rows * 2))

    # Ranges FIXED
    x_axis_range = [0, 510]
    y_axis_range = [0, 515]
    show_ticks = True

    if quadrant_selection != Quadrant.ALL.value:
        show_ticks = False
        # Calculate unshifted quadrant boundaries
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
        t_col = theme_config.text_color if theme_config else TEXT_COLOR
        # Annotation fixed
        fig.add_annotation(x=(panel_width + gap_x + offset_x), y=(panel_height + gap_y + offset_y), text=f"<b>Lot #: {lot_number}</b>", showarrow=False, font=dict(size=14, color=t_col), align="right", xanchor="right", yanchor="bottom")

    return fig

def _create_still_alive_map_shapes(
    panel_rows: int,
    panel_cols: int,
    true_defect_data: Dict[Tuple[int, int], Dict[str, Any]],
    ctx: GeometryContext,
    theme_config: Optional[PlotTheme] = None
) -> Tuple[List[Dict[str, Any]], List[go.Scatter]]:
    """
    Creates the shapes for the 'Still Alive' map AND invisible scatter points for tooltips.
    """
    shapes = []
    traces = []

    quad_width = ctx.quad_width
    quad_height = ctx.quad_height
    offset_x, offset_y = ctx.offset_x, ctx.offset_y
    gap_x, gap_y = ctx.effective_gap_x, ctx.effective_gap_y

    # Grid Fixed
    total_cols, total_rows = panel_cols * 2, panel_rows * 2
    all_origins = ctx.quadrant_origins

    # Calculate Unit Dimensions with gaps (n+1)
    unit_width = ctx.cell_width
    unit_height = ctx.cell_height

    # Prepare lists for scatter trace (Tooltips)
    hover_x = []
    hover_y = []
    hover_text = []
    hover_colors = []

    # 0a. Draw Outer Copper Frame (Standard)
    border_color = theme_config.axis_color if theme_config else GRID_COLOR
    bg_color = theme_config.panel_background_color if theme_config else PANEL_BACKGROUND_COLOR
    path_frame = get_rounded_rect_path(0, 0, 510, 515, 20.0)
    shapes.append(dict(
        type="path",
        path=path_frame,
        fillcolor=bg_color,
        line=dict(color=border_color, width=3),
        layer='below'
    ))

    # 0b. Inner Black Rect - skipped as per create_grid_shapes logic

    # 0c. Draw Quadrant Backgrounds (Copper)
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

            # Position with Gaps (Start at Gap)
            x0 = x_origin + INTER_UNIT_GAP + local_col * (unit_width + INTER_UNIT_GAP)
            y0 = y_origin + INTER_UNIT_GAP + local_row * (unit_height + INTER_UNIT_GAP)

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
            hoverinfo='text',
            showlegend=False
        ))

    return shapes, traces

def create_still_alive_figure(
    panel_rows: int,
    panel_cols: int,
    true_defect_data: Dict[Tuple[int, int], Dict[str, Any]],
    ctx: GeometryContext,
    theme_config: Optional[PlotTheme] = None
) -> go.Figure:
    """
    Creates the Still Alive Map Figure (Shapes + Layout + Tooltips).
    """
    # Shapes are FIXED (Grid is fixed)

    map_shapes, hover_traces = _create_still_alive_map_shapes(panel_rows, panel_cols, true_defect_data, ctx, theme_config=theme_config)

    # Add Dummy Traces for Legend (Since shapes don't show in legend)
    hover_traces.append(go.Scatter(
        x=[None], y=[None],
        mode='markers',
        marker=dict(size=10, color=ALIVE_CELL_COLOR, symbol='square'),
        name='Alive (Yield)'
    ))
    hover_traces.append(go.Scatter(
        x=[None], y=[None],
        mode='markers',
        marker=dict(size=10, color=DEFECTIVE_CELL_COLOR, symbol='square'),
        name='Defective (Kill)'
    ))

    fig = go.Figure(data=hover_traces) # Add hover traces + Legend items

    quad_width = ctx.quad_width
    quad_height = ctx.quad_height
    offset_x, offset_y = ctx.offset_x, ctx.offset_y
    gap_x, gap_y = ctx.effective_gap_x, ctx.effective_gap_y
    panel_width, panel_height = ctx.panel_width, ctx.panel_height

    cell_width, cell_height = ctx.cell_width, ctx.cell_height
    x_tick_vals_q1 = [(i * cell_width) + (cell_width / 2) + offset_x for i in range(panel_cols)]
    x_tick_vals_q2 = [(quad_width + gap_x) + (i * cell_width) + (cell_width / 2) + offset_x for i in range(panel_cols)]
    y_tick_vals_q1 = [(i * cell_height) + (cell_height / 2) + offset_y for i in range(panel_rows)]
    y_tick_vals_q3 = [(quad_height + gap_y) + (i * cell_height) + (cell_height / 2) + offset_y for i in range(panel_rows)]
    x_tick_text = list(range(panel_cols * 2))
    y_tick_text = list(range(panel_rows * 2))

    apply_panel_theme(fig, f"Still Alive Map ({len(true_defect_data)} Defective Cells)", theme_config=theme_config)

    # Fixed Ranges
    x_range = [0, 510]
    y_range = [0, 515]

    fig.update_layout(
        xaxis=dict(
            title="Unit Column Index", range=x_range, constrain='domain',
            tickvals=x_tick_vals_q1 + x_tick_vals_q2, ticktext=x_tick_text
        ),
        yaxis=dict(
            title="Unit Row Index", range=y_range,
            tickvals=y_tick_vals_q1 + y_tick_vals_q3, ticktext=y_tick_text
        ),
        shapes=map_shapes, margin=dict(l=20, r=20, t=80, b=20),
    )
    return fig

def create_stress_heatmap(
    data: StressMapData,
    panel_rows: int,
    panel_cols: int,
    ctx: GeometryContext,
    view_mode: str = "Continuous",
    theme_config: Optional[PlotTheme] = None
) -> go.Figure:
    """
    Creates the Cumulative Stress Heatmap with defect counts in cells.
    """
    quad_width = ctx.quad_width
    quad_height = ctx.quad_height
    offset_x, offset_y = ctx.offset_x, ctx.offset_y
    gap_x, gap_y = ctx.effective_gap_x, ctx.effective_gap_y
    panel_width, panel_height = ctx.panel_width, ctx.panel_height

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

        col_indices = np.arange(cols)
        row_indices = np.arange(rows)

        # Use pre-calculated geometry from context
        u_w = ctx.cell_width
        u_h = ctx.cell_height
        stride_x = ctx.stride_x
        stride_y = ctx.stride_y

        # Local Indices (0..n within quadrant)
        l_cols = col_indices % panel_cols
        l_rows = row_indices % panel_rows

        # Calculate Base within Quadrant
        x_base = INTER_UNIT_GAP + l_cols * stride_x + (u_w / 2)
        y_base = INTER_UNIT_GAP + l_rows * stride_y + (u_h / 2)

        quad_offset_x = np.where(col_indices >= panel_cols, quad_width + gap_x, 0)
        quad_offset_y = np.where(row_indices >= panel_rows, quad_height + gap_y, 0)

        # SHIFT LOGIC: Heatmap (Grid) is FIXED.
        eff_offset_x = offset_x
        eff_offset_y = offset_y

        x_vals = eff_offset_x + quad_offset_x + x_base
        y_vals = eff_offset_y + quad_offset_y + y_base

        # Broadcast to 2D Grid
        x_coords, y_coords = np.meshgrid(x_vals, y_vals)

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

        # Add Grid Shapes for Quarterly view (FIXED)
        fig.update_layout(shapes=create_grid_shapes(panel_rows, panel_cols, ctx, quadrant='All', fill=False, theme_config=theme_config))

        # Ranges (FIXED)
        fig.update_layout(
            xaxis=dict(title="Physical X", range=[0, 510], constrain='domain', showticklabels=False),
            yaxis=dict(title="Physical Y", range=[0, 515], showticklabels=False)
        )

    else:
        # Continuous Mode (Indices) - No physical shift needed as it is unit index based
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

def create_delta_heatmap(
    data_a: StressMapData,
    data_b: StressMapData,
    panel_rows: int,
    panel_cols: int,
    ctx: GeometryContext,
    view_mode: str = "Continuous",
    theme_config: Optional[PlotTheme] = None
) -> go.Figure:
    """
    Creates a Delta Heatmap (Group A - Group B).
    """
    quad_width = ctx.quad_width
    quad_height = ctx.quad_height
    offset_x, offset_y = ctx.offset_x, ctx.offset_y
    gap_x, gap_y = ctx.effective_gap_x, ctx.effective_gap_y
    panel_width, panel_height = ctx.panel_width, ctx.panel_height

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

        col_indices = np.arange(cols)
        row_indices = np.arange(rows)

        # Robust Centers Calculation
        u_w = ctx.cell_width
        u_h = ctx.cell_height
        stride_x = ctx.stride_x
        stride_y = ctx.stride_y

        l_cols = col_indices % panel_cols
        l_rows = row_indices % panel_rows

        x_base = INTER_UNIT_GAP + l_cols * stride_x + (u_w / 2)
        y_base = INTER_UNIT_GAP + l_rows * stride_y + (u_h / 2)

        quad_offset_x = np.where(col_indices >= panel_cols, quad_width + gap_x, 0)
        quad_offset_y = np.where(row_indices >= panel_rows, quad_height + gap_y, 0)

        # SHIFT LOGIC (Visual Origin): Heatmap represents GRID. Grid is fixed.
        eff_offset_x = offset_x
        eff_offset_y = offset_y

        x_vals = eff_offset_x + quad_offset_x + x_base
        y_vals = eff_offset_y + quad_offset_y + y_base

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

        fig.update_layout(shapes=create_grid_shapes(panel_rows, panel_cols, ctx, quadrant='All', fill=False, theme_config=theme_config))

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

@track_performance("Plot: Density Contour (Heatmap)")
def create_density_contour_map(
    df: pd.DataFrame,
    panel_rows: int,
    panel_cols: int,
    ctx: GeometryContext,
    show_points: bool = False,
    smoothing_factor: int = 30,
    saturation_cap: int = 0,
    show_grid: bool = True,
    view_mode: str = "Continuous",
    flip_back: bool = False,
    quadrant_selection: str = 'All',
    theme_config: Optional[PlotTheme] = None
) -> go.Figure:
    """
    2. Smoothed Density Contour Map (OPTIMIZED).
    """
    if df.empty:
        return go.Figure()

    quad_width = ctx.quad_width
    quad_height = ctx.quad_height
    offset_x, offset_y = ctx.offset_x, ctx.offset_y
    gap_x, gap_y = ctx.effective_gap_x, ctx.effective_gap_y
    panel_width, panel_height = ctx.panel_width, ctx.panel_height

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
        # SHIFT LOGIC (Additive): Shift data points for aggregation
        visual_origin_x = ctx.visual_origin_x
        visual_origin_y = ctx.visual_origin_y

        if 'X_COORDINATES' in q_df.columns:
            x_c = q_df[x_col].values + visual_origin_x
            y_c = q_df['plot_y_corrected'].values + visual_origin_y
        else:
            x_c = (q_df[x_col].values + offset_x) + visual_origin_x
            y_c = (q_df['plot_y_corrected'].values + offset_y) + visual_origin_y

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
                        sub_x = sub_df[x_col] + visual_origin_x
                        sub_y = sub_df['plot_y_corrected'] + visual_origin_y
                    else:
                        sub_x = (sub_df[x_col] + offset_x) + visual_origin_x
                        sub_y = (sub_df['plot_y_corrected'] + offset_y) + visual_origin_y
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

    # Custom Hover Template
    if driver_text_t is not None:
        hovertemplate = 'X: %{x:.1f}mm<br>Y: %{y:.1f}mm<br>Density: %{z:.0f}<br>Top Cause: %{text}<extra></extra>'
        text_arg = driver_text_t
    else:
        hovertemplate = 'X: %{x:.1f}mm<br>Y: %{y:.1f}mm<br>Density: %{z:.0f}<extra></extra>'
        text_arg = None

    fig.add_trace(go.Contour(
        z=Z,
        x=x_centers, # Fixed
        y=y_centers, # Fixed
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
            px = df_true[x_col] + ctx.visual_origin_x
            py = df_true['plot_y_corrected'] + ctx.visual_origin_y
        else:
            px = (df_true[x_col] + offset_x) + ctx.visual_origin_x
            py = (df_true['plot_y_corrected'] + offset_y) + ctx.visual_origin_y

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
        # Create full grid shapes
        shapes = create_grid_shapes(panel_rows, panel_cols, ctx, quadrant='All', fill=False, theme_config=theme_config)
    else:
        # Minimalist mode (e.g. for export): Only draw the panel outline/frame if needed, or nothing.
        # Ideally, we still want the outer boundary but not the internal quadrant crossbars if "clean" is requested.
        # But 'create_grid_shapes' does everything.
        # If show_grid=False is passed (for export), we skip shapes entirely or add a simple frame.
        pass

    # 4. Axis Labels
    total_cols = panel_cols * 2
    total_rows = panel_rows * 2

    cell_width = ctx.cell_width
    cell_height = ctx.cell_height

    eff_offset_x = offset_x
    eff_offset_y = offset_y

    x_tick_vals = []
    x_tick_text = []
    for i in range(total_cols):
        offset = gap_x if i >= panel_cols else 0
        center_mm = (i * cell_width) + (cell_width / 2) + offset + eff_offset_x
        x_tick_vals.append(center_mm)
        x_tick_text.append(str(i))

    y_tick_vals = []
    y_tick_text = []
    for i in range(total_rows):
        offset = gap_y if i >= panel_rows else 0
        center_mm = (i * cell_height) + (cell_height / 2) + offset + eff_offset_y
        y_tick_vals.append(center_mm)
        y_tick_text.append(str(i))

    # Axis Ranges (Dynamic Auto-Scale)
    # Calculate the physical extent of the panel including gaps and offsets
    # We add a small margin (e.g., 5mm) to ensure the edge units aren't cut off
    max_extent_x = offset_x + panel_width + gap_x + 5.0
    max_extent_y = offset_y + panel_height + gap_y + 5.0

    x_axis_range = [0, max_extent_x]
    y_axis_range = [0, max_extent_y]

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

def create_cross_section_heatmap(
    matrix: np.ndarray,
    layer_labels: List[str],
    axis_labels: List[str],
    slice_desc: str,
    theme_config: Optional[PlotTheme] = None
) -> go.Figure:
    """
    Constructs the 2D cross-section matrix for Root Cause Analysis based on a single slice.
    """
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

    # Map to Global Indices (Vectorized)
    u_x = df_true['UNIT_INDEX_X'].astype(int)
    u_y = df_true['UNIT_INDEX_Y'].astype(int)

    # Calculate offsets based on Quadrant
    # Q2/Q4 add col offset to X
    x_offset = np.where(df_true['QUADRANT'].isin(['Q2', 'Q4']), panel_cols, 0)
    # Q3/Q4 add row offset to Y
    y_offset = np.where(df_true['QUADRANT'].isin(['Q3', 'Q4']), panel_rows, 0)

    heatmap_df = pd.DataFrame({
        'Global_X': u_x + x_offset,
        'Global_Y': u_y + y_offset
    })
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
