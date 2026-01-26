import pandas as pd
import numpy as np
from typing import List, Tuple, Optional
from src.core.models import PanelData
from src.core.config import SAFE_VERIFICATION_VALUES
from src.analytics.models import StressMapData

def aggregate_stress_data(
    panel_data: PanelData,
    selected_keys: List[Tuple[int, str]],
    panel_rows: int,
    panel_cols: int,
    verification_filter: Optional[List[str]] = None,
    quadrant_filter: str = "All"
) -> StressMapData:
    """
    Aggregates data for the Cumulative Stress Map using specific (Layer, Side) keys.
    """
    if not panel_data:
        return StressMapData(
            np.zeros((panel_rows*2, panel_cols*2), int),
            np.empty((panel_rows*2, panel_cols*2), object), 0, 0
        )

    # OPTIMIZATION: Vectorized Aggregation
    dfs_to_agg = []
    for layer_num, side in selected_keys:
        layer = panel_data.get_layer(layer_num, side)
        if layer and not layer.data.empty:
            dfs_to_agg.append(layer.data)

    if not dfs_to_agg:
        return StressMapData(
            np.zeros((panel_rows*2, panel_cols*2), int),
            np.empty((panel_rows*2, panel_cols*2), object), 0, 0
        )

    combined_df = pd.concat(dfs_to_agg, ignore_index=True)

    # Filter True Defects (Standard)
    safe_values_upper = {v.upper() for v in SAFE_VERIFICATION_VALUES}
    if 'Verification' in combined_df.columns:
        # Verification is already normalized to upper in ingestion
        is_true = ~combined_df['Verification'].astype(str).isin(safe_values_upper)
        combined_df = combined_df[is_true]

    # Filter by Specific Selection (if provided)
    if verification_filter and 'Verification' in combined_df.columns and not combined_df.empty:
        combined_df = combined_df[combined_df['Verification'].astype(str).isin(verification_filter)]

    # Filter by Quadrant (if provided)
    if quadrant_filter != "All" and 'QUADRANT' in combined_df.columns and not combined_df.empty:
        combined_df = combined_df[combined_df['QUADRANT'] == quadrant_filter]

    return aggregate_stress_data_from_df(combined_df, panel_rows, panel_cols)

def aggregate_stress_data_from_df(
    df: pd.DataFrame,
    panel_rows: int,
    panel_cols: int
) -> StressMapData:
    """
    Core logic to aggregate a DataFrame into a StressMapData object.
    Accepts a pre-filtered DataFrame.
    """
    total_cols = panel_cols * 2
    total_rows = panel_rows * 2

    grid_counts = np.zeros((total_rows, total_cols), dtype=int)
    hover_text = np.empty((total_rows, total_cols), dtype=object)
    hover_text[:] = "No Defects" # Default

    if df.empty:
         return StressMapData(grid_counts, hover_text, 0, 0)

    # Vectorized Histogram
    # Use RAW COORDINATES (UNIT_INDEX_X)
    if 'UNIT_INDEX_X' not in df.columns or 'UNIT_INDEX_Y' not in df.columns:
        return StressMapData(grid_counts, hover_text, 0, 0)

    x_coords = df['UNIT_INDEX_X'].values
    y_coords = df['UNIT_INDEX_Y'].values

    # Filter out of bounds
    valid_mask = (x_coords >= 0) & (x_coords < total_cols) & (y_coords >= 0) & (y_coords < total_rows)
    x_coords = x_coords[valid_mask]
    y_coords = y_coords[valid_mask]

    if len(x_coords) == 0:
        return StressMapData(grid_counts, hover_text, 0, 0)

    # 1. Grid Counts
    hist, _, _ = np.histogram2d(
        y_coords, x_coords,
        bins=[total_rows, total_cols],
        range=[[0, total_rows], [0, total_cols]]
    )
    grid_counts = hist.astype(int)
    total_defects_acc = int(grid_counts.sum())
    max_count_acc = int(grid_counts.max()) if total_defects_acc > 0 else 0

    # 2. Hover Text (Group By Optimization)
    valid_df = df[valid_mask]

    if 'DEFECT_TYPE' in valid_df.columns:
        # Optimization: Avoid iterating through every cell group if possible

        # 1. Count by Cell + Type
        type_counts = valid_df.groupby(['UNIT_INDEX_Y', 'UNIT_INDEX_X', 'DEFECT_TYPE'], observed=True).size().reset_index(name='Count')

        # 2. Sort by Count descending within each cell (Y, X)
        type_counts.sort_values(['UNIT_INDEX_Y', 'UNIT_INDEX_X', 'Count'], ascending=[True, True, False], inplace=True)

        # 3. Calculate Total per Cell
        cell_totals = type_counts.groupby(['UNIT_INDEX_Y', 'UNIT_INDEX_X'])['Count'].sum()

        # 4. Get Top 3 per Cell
        top_3 = type_counts.groupby(['UNIT_INDEX_Y', 'UNIT_INDEX_X']).head(3)

        # 5. Count how many types per cell
        types_per_cell = type_counts.groupby(['UNIT_INDEX_Y', 'UNIT_INDEX_X']).size()

        # 6. Build Tooltip parts
        # Iterate over the groups of 'top_3' (simplified dataset)
        top_3_dict = {}
        for (y, x), group in top_3.groupby(['UNIT_INDEX_Y', 'UNIT_INDEX_X']):
             lines = [f"{row.DEFECT_TYPE}: {row.Count}" for row in group.itertuples()]
             top_3_dict[(y, x)] = lines

        for (y, x), total in cell_totals.items():
            lines = top_3_dict.get((y,x), [])
            tooltip = f"<b>Total: {total}</b><br>" + "<br>".join(lines)

            total_types = types_per_cell.get((y,x), 0)
            if total_types > 3:
                tooltip += f"<br>... (+{total_types - 3} types)"

            hover_text[y, x] = tooltip
    else:
        # Fallback if no Defect Type
        # Just show total count
        grouped = valid_df.groupby(['UNIT_INDEX_Y', 'UNIT_INDEX_X']).size()
        for (gy, gx), count in grouped.items():
            hover_text[gy, gx] = f"<b>Total: {count}</b>"

    return StressMapData(
        grid_counts=grid_counts,
        hover_text=hover_text,
        total_defects=total_defects_acc,
        max_count=max_count_acc
    )
