import plotly.graph_objects as go
import pandas as pd
from typing import List, Optional
from src.core.geometry import GeometryContext
from src.core.config import defect_style_map, FALLBACK_COLORS, GAP_SIZE
from src.documentation import VERIFICATION_DESCRIPTIONS

def create_defect_traces(
    df: pd.DataFrame,
    ctx: GeometryContext
) -> List[go.Scatter]:
    """
    Generates scatter plot traces for defect visualization.
    APPLIES VISUAL ORIGIN SHIFT AS ADDITIVE OFFSET.
    """
    traces = []
    if df.empty: return traces

    # Handle Verification Flag Logic
    has_verification_data = df['HAS_VERIFICATION_DATA'].any() if 'HAS_VERIFICATION_DATA' in df.columns else False
    group_col = 'Verification' if has_verification_data else 'DEFECT_TYPE'

    # Pre-calculate unique groups for consistent coloring
    unique_groups = df[group_col].unique()

    local_style_map = {}
    if group_col == 'DEFECT_TYPE':
        local_style_map = defect_style_map.copy()
        fallback_index = 0
        for dtype in unique_groups:
            if dtype not in local_style_map:
                color = FALLBACK_COLORS[fallback_index % len(FALLBACK_COLORS)]
                local_style_map[dtype] = color
                fallback_index += 1
    else:
        fallback_index = 0
        for code in unique_groups:
            color = FALLBACK_COLORS[fallback_index % len(FALLBACK_COLORS)]
            local_style_map[code] = color
            fallback_index += 1

    # Enrich description
    if 'Verification' in df.columns:
        # Avoid SettingWithCopyWarning by operating on a copy if not already
        df = df.copy()
        df['Description'] = df['Verification'].map(VERIFICATION_DESCRIPTIONS).fillna("Unknown Code")
    else:
        df = df.copy()
        df['Description'] = "N/A"

    has_raw_coords = 'X_COORDINATES' in df.columns and 'Y_COORDINATES' in df.columns
    coord_str = ""
    if has_raw_coords:
        df['RAW_COORD_STR'] = df.apply(lambda row: f"({row['X_COORDINATES']/1000:.2f}, {row['Y_COORDINATES']/1000:.2f}) mm", axis=1)
        custom_data_cols = ['UNIT_INDEX_X', 'UNIT_INDEX_Y', 'DEFECT_TYPE', 'DEFECT_ID', 'Verification', 'Description', 'RAW_COORD_STR']
        coord_str = "<br>Raw Coords: %{customdata[6]}"
    else:
        custom_data_cols = ['UNIT_INDEX_X', 'UNIT_INDEX_Y', 'DEFECT_TYPE', 'DEFECT_ID', 'Verification', 'Description']

    grouped = df.groupby(group_col, observed=True)

    for group_val, dff in grouped:
        if group_val not in local_style_map: continue
        color = local_style_map[group_val]

        hovertemplate = ("<b>Status: %{customdata[4]}</b><br>"
                            "Description : %{customdata[5]}<br>"
                            "Type: %{customdata[2]}<br>"
                            "Unit Index (X, Y): (%{customdata[0]}, %{customdata[1]})<br>"
                            "Defect ID: %{customdata[3]}"
                            + coord_str +
                            "<extra></extra>")

        # SHIFT LOGIC (Additive):
        # 1. Structural Position: point + offset_x
        # 2. Visual Offset: (point + offset_x) + visual_origin_x

        # Use context values
        offset_x = ctx.offset_x
        offset_y = ctx.offset_y
        visual_origin_x = ctx.visual_origin_x
        visual_origin_y = ctx.visual_origin_y

        if 'X_COORDINATES' in dff.columns:
            # Absolute: already includes structure (if absolute frame coords) or needs shift.
            # Assuming plot_x is absolute frame position.
            x_vals = dff['plot_x'] + visual_origin_x
            y_vals = dff['plot_y'] + visual_origin_y
        else:
            # Relative/Grid Jitter
            x_vals = (dff['plot_x'] + offset_x) + visual_origin_x
            y_vals = (dff['plot_y'] + offset_y) + visual_origin_y

        traces.append(go.Scattergl(
            x=x_vals, y=y_vals, mode='markers',
            marker=dict(color=color, size=8, line=dict(width=1, color='black')),
            name=str(group_val),
            customdata=dff[custom_data_cols],
            hovertemplate=hovertemplate
        ))

    return traces
