import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple, Any
from src.core.models import PanelData
from src.analytics.models import YieldKillerMetrics
from src.analytics.verification import is_true_defect_mask, filter_true_defects

def get_true_defect_coordinates(
    panel_data: PanelData,
    excluded_layers: Optional[List[int]] = None,
    excluded_defect_types: Optional[List[str]] = None,
    included_sides: Optional[List[str]] = None
) -> Dict[Tuple[int, int], Dict[str, Any]]:
    """
    Aggregates all "True" defects to find unique defective cell coordinates.
    Optimized implementation using vectorized pandas operations.

    Returns:
        Dict mapping (physical_x, physical_y) -> {
            'first_killer_layer': int,
            'defect_summary': str
        }
    """
    if not panel_data:
        return {}

    all_layers_df = panel_data.get_combined_dataframe()

    if all_layers_df.empty or 'Verification' not in all_layers_df.columns:
        return {}

    # 1. Filter Logic
    mask = pd.Series(True, index=all_layers_df.index)

    if excluded_layers:
        mask &= ~all_layers_df['LAYER_NUM'].isin(excluded_layers)

    if included_sides:
        mask &= all_layers_df['SIDE'].isin(included_sides)

    if excluded_defect_types:
        mask &= ~all_layers_df['Verification'].isin(excluded_defect_types)

    # Filter for True Defects (Safe Values)
    mask &= is_true_defect_mask(all_layers_df['Verification'])

    true_defects_df = all_layers_df[mask].copy()

    if true_defects_df.empty:
        return {}

    if 'PHYSICAL_X' not in true_defects_df.columns:
        true_defects_df['PHYSICAL_X'] = true_defects_df['UNIT_INDEX_X']

    # 2. Aggregation Logic (Vectorized)

    # A. First Killer Layer
    # Sort by LAYER_NUM to ensure first() gets the lowest layer
    true_defects_df.sort_values('LAYER_NUM', inplace=True)
    first_killer = true_defects_df.groupby(['PHYSICAL_X', 'UNIT_INDEX_Y'])['LAYER_NUM'].first()

    # B. Defect Summary string "L1: 5, L2: 3"
    # Count defects per (Unit, Layer)
    layer_counts = true_defects_df.groupby(['PHYSICAL_X', 'UNIT_INDEX_Y', 'LAYER_NUM']).size().reset_index(name='count')

    # Format strings per layer
    layer_counts['summary_part'] = "L" + layer_counts['LAYER_NUM'].astype(str) + ": " + layer_counts['count'].astype(str)

    # Aggregate strings per Unit
    # Note: 'join' on groupby can be slow but faster than python loop over rows
    defect_summary = layer_counts.groupby(['PHYSICAL_X', 'UNIT_INDEX_Y'])['summary_part'].agg(', '.join)

    # 3. Combine Results
    result_df = pd.DataFrame({
        'first_killer_layer': first_killer,
        'defect_summary': defect_summary
    })

    # Convert to Dict for compatibility
    return result_df.to_dict('index')

def calculate_yield_killers(panel_data: PanelData, panel_rows: int, panel_cols: int) -> Optional[YieldKillerMetrics]:
    """
    Calculates the 'Yield Killer' KPIs: Worst Layer, Worst Unit, Side Bias.
    """
    if not panel_data: return None

    def true_defect_filter(df):
        return filter_true_defects(df)

    combined_df = panel_data.get_combined_dataframe(filter_func=true_defect_filter)

    if combined_df.empty: return None

    # 1. Worst Layer
    layer_counts = combined_df['LAYER_NUM'].value_counts()
    top_killer_layer_id = layer_counts.idxmax()
    top_killer_count = layer_counts.max()
    top_killer_label = f"Layer {top_killer_layer_id}"

    # 2. Worst Unit (Use RAW COORDINATES - UNIT_INDEX_X as per request)
    unit_counts = combined_df.groupby(['UNIT_INDEX_X', 'UNIT_INDEX_Y']).size()
    worst_unit_coords = unit_counts.idxmax() # Tuple (x, y)
    worst_unit_count = unit_counts.max()
    worst_unit_label = f"X:{worst_unit_coords[0]}, Y:{worst_unit_coords[1]}"

    # 3. Side Bias
    side_counts = combined_df['SIDE'].value_counts()
    f_count = side_counts.get('F', 0)
    b_count = side_counts.get('B', 0)

    diff = abs(f_count - b_count)
    if f_count > b_count:
        bias = "Front Side"
    elif b_count > f_count:
        bias = "Back Side"
    else:
        bias = "Balanced"

    return YieldKillerMetrics(
        top_killer_layer=top_killer_label,
        top_killer_count=int(top_killer_count),
        worst_unit=worst_unit_label,
        worst_unit_count=int(worst_unit_count),
        side_bias=bias,
        side_bias_diff=int(diff)
    )

def prepare_multi_layer_data(panel_data: PanelData) -> pd.DataFrame:
    """
    Aggregates and filters defect data from all layers for the Multi-Layer Defect View.
    """
    if not panel_data:
        return pd.DataFrame()

    return panel_data.get_combined_dataframe(filter_func=filter_true_defects)

def get_cross_section_matrix(
    panel_data: PanelData,
    slice_axis: str,
    slice_index: int,
    panel_rows: int,
    panel_cols: int
) -> Tuple[np.ndarray, List[str], List[str]]:
    """
    Constructs the 2D cross-section matrix for Root Cause Analysis based on a single slice.
    """
    sorted_layers = panel_data.get_all_layer_nums()
    num_layers = len(sorted_layers)
    if num_layers == 0:
        return np.zeros((0,0)), [], []

    total_cols = panel_cols * 2
    total_rows = panel_rows * 2

    if slice_axis == 'Y':
        width_dim = total_cols
        axis_labels = [str(i) for i in range(width_dim)]
    else:
        width_dim = total_rows
        axis_labels = [str(i) for i in range(width_dim)]

    matrix = np.zeros((num_layers, width_dim), dtype=int)
    layer_labels = [f"L{num}" for num in sorted_layers]

    for i, layer_num in enumerate(sorted_layers):
        sides = panel_data._layers[layer_num] # Direct access to dict (via compatibility property?)
        # PanelData has _layers. And __getitem__ proxy.
        # Let's use get_layer method or direct access if protected.
        # PanelData in src/core/models.py has _layers.
        # Best to use iterate sides.

        # We can do:
        sides_map = panel_data.get(layer_num) # This returns {side: df} via proxy logic I wrote in models.py
        # But wait, models.py: get returns getitem proxy?
        # Yes: return {side: layer_obj.data ...}

        # BUT I need the layer_obj itself? No, just the DF.

        if sides_map is None: continue

        for side, df in sides_map.items():
            if df.empty: continue

            df_copy = filter_true_defects(df)

            if df_copy.empty: continue

            if slice_axis == 'Y':
                relevant_defects = df_copy[df_copy['UNIT_INDEX_Y'] == slice_index]
            else:
                relevant_defects = df_copy[df_copy['UNIT_INDEX_X'] == slice_index]

            if relevant_defects.empty: continue

            if slice_axis == 'Y':
                counts = relevant_defects.groupby('UNIT_INDEX_X').size()
                for x_idx, count in counts.items():
                    if 0 <= x_idx < width_dim:
                        matrix[i, int(x_idx)] += count
            else:
                counts = relevant_defects.groupby('UNIT_INDEX_Y').size()
                for y_idx, count in counts.items():
                    if 0 <= y_idx < width_dim:
                        matrix[i, int(y_idx)] += count

    return matrix, layer_labels, axis_labels
