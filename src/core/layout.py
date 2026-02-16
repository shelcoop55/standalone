
import pandas as pd
import numpy as np
import logging
from src.core.geometry import GeometryContext
from src.core.config import INTER_UNIT_GAP

logger = logging.getLogger(__name__)

def apply_layout_to_dataframe(
    df: pd.DataFrame, 
    ctx: GeometryContext, 
    panel_rows: int, 
    panel_cols: int,
    side: str = 'F'
) -> pd.DataFrame:
    """
    Enriches the dataframe with plotting coordinates based on the GeometryContext.
    Adds: plot_x, plot_y, physical_plot_x_flipped, physical_plot_x_raw
    MODIFIES the dataframe in-place (if possible) or returns a modified copy.
    """
    if df.empty:
        return df

    # Work on a copy to avoid SettingWithCopyMethod on slices
    df = df.copy()

    # Dimensions from Context
    quad_width = ctx.quad_width
    quad_height = ctx.quad_height
    cell_width = ctx.cell_width
    cell_height = ctx.cell_height
    stride_x = ctx.stride_x
    stride_y = ctx.stride_y
    
    # Implicit gaps are part of stride or context
    # In models.py: gap_x = self.gap_x
    # In ctx: effective_gap_x (includes dyn_gap)
    # We need the GAP used for separation logic. 
    # models.py used: x_offset_raw = np.where(..., quad_width + self.gap_x, 0)
    # self.gap_x was passed into BuildUpLayer. It corresponds to fixed_gap_x usually.
    # However, ctx.effective_gap_x is what separates the quadrants visually in the new engine.
    # Let's use ctx.effective_gap_x for the quadrant separation.
    gap_x = ctx.effective_gap_x
    gap_y = ctx.effective_gap_y

    # --- 1. RAW COORDINATES (Individual View - No Flip) ---
    # Calculate Raw Quadrant
    conditions_raw = [
        (df['UNIT_INDEX_X'] < panel_cols) & (df['UNIT_INDEX_Y'] < panel_rows),
        (df['UNIT_INDEX_X'] >= panel_cols) & (df['UNIT_INDEX_Y'] < panel_rows),
        (df['UNIT_INDEX_X'] < panel_cols) & (df['UNIT_INDEX_Y'] >= panel_rows),
        (df['UNIT_INDEX_X'] >= panel_cols) & (df['UNIT_INDEX_Y'] >= panel_rows)
    ]
    # np.select requires numpy boolean ndarrays
    conditions_raw = [np.asarray(c, dtype=bool) for c in conditions_raw]
    choices = ['Q1', 'Q2', 'Q3', 'Q4']
    df['QUADRANT'] = np.select(conditions_raw, choices, default='Other')

    local_index_x_raw = df['UNIT_INDEX_X'] % panel_cols
    local_index_y = df['UNIT_INDEX_Y'] % panel_rows

    # Start at INTER_UNIT_GAP (Gap before first unit)
    plot_x_base_raw = INTER_UNIT_GAP + local_index_x_raw * stride_x
    plot_y_base = INTER_UNIT_GAP + local_index_y * stride_y

    x_offset_raw = np.where(df['UNIT_INDEX_X'] >= panel_cols, quad_width + gap_x, 0)
    y_offset = np.where(df['UNIT_INDEX_Y'] >= panel_rows, quad_height + gap_y, 0)

    # --- SPATIAL LOGIC ---
    use_spatial_coords = False
    abs_x_mm = None
    abs_y_mm = None

    if 'X_COORDINATES' in df.columns and 'Y_COORDINATES' in df.columns:
        try:
            # ABSOLUTE MAPPING: Convert Microns to Millimeters directly.
            # Assumes X_COORDINATES are relative to the PANEL ORIGIN (Design Coordinates).
            abs_x_mm = df['X_COORDINATES'] / 1000.0
            abs_y_mm = df['Y_COORDINATES'] / 1000.0

            # Ensure they are numeric
            if pd.api.types.is_numeric_dtype(abs_x_mm) and pd.api.types.is_numeric_dtype(abs_y_mm):
                use_spatial_coords = True
            else:
                use_spatial_coords = False
        except Exception:
            use_spatial_coords = False

    if use_spatial_coords:
        offset_x = abs_x_mm
        offset_y = abs_y_mm
    else:
        # Use Random Jitter (10% to 90% of cell)
        offset_x = np.random.rand(len(df)) * cell_width * 0.8 + (cell_width * 0.1)
        offset_y = np.random.rand(len(df)) * cell_height * 0.8 + (cell_height * 0.1)

    # --- COORDINATE ASSIGNMENT ---
    if use_spatial_coords:
        df['plot_x'] = offset_x
        df['plot_y'] = offset_y
    else:
        # Relative/Grid-based positioning
        df['plot_x'] = plot_x_base_raw + x_offset_raw + offset_x
        df['plot_y'] = plot_y_base + y_offset + offset_y

    # --- 2. PHYSICAL COORDINATES (Stacked View) ---
    total_width_units = 2 * panel_cols

    # A) FLIPPED MODE (Standard Alignment) - Index Calculation
    # Vectorized check for 'B' side
    if 'SIDE' in df.columns:
        is_back_mask = df['SIDE'] == 'B'
        # Default to False for non-B if any
    else:
        is_back_mask = (side == 'B') # Scalar broadcast

    df['PHYSICAL_X_FLIPPED'] = np.where(
        is_back_mask,
        (total_width_units - 1) - df['UNIT_INDEX_X'],
        df['UNIT_INDEX_X']
    )

    # Alias PHYSICAL_X for backward compatibility
    df['PHYSICAL_X'] = df['PHYSICAL_X_FLIPPED']

    # B) RAW MODE (No Flip) - Index Calculation
    df['PHYSICAL_X_RAW'] = df['UNIT_INDEX_X']

    # --- PHYSICAL SPATIAL LOGIC ---
    local_index_x_flipped = df['PHYSICAL_X_FLIPPED'] % panel_cols
    plot_x_base_flipped = INTER_UNIT_GAP + local_index_x_flipped * stride_x
    x_offset_flipped = np.where(df['PHYSICAL_X_FLIPPED'] >= panel_cols, quad_width + gap_x, 0)

    local_index_x_raw_phys = df['PHYSICAL_X_RAW'] % panel_cols
    plot_x_base_raw_phys = INTER_UNIT_GAP + local_index_x_raw_phys * stride_x
    x_offset_raw_phys = np.where(df['PHYSICAL_X_RAW'] >= panel_cols, quad_width + gap_x, 0)

    if use_spatial_coords:
        # 1. Raw Physical (Simple)
        df['physical_plot_x_raw'] = abs_x_mm
        
        # 2. Flipped Physical (Aligned)
        # Assuming absolute coords are already correct for the side they belong to
        df['physical_plot_x_flipped'] = abs_x_mm
    else:
        # Grid-based Jitter Logic
        df['physical_plot_x_flipped'] = plot_x_base_flipped + x_offset_flipped + offset_x
        df['physical_plot_x_raw'] = plot_x_base_raw_phys + x_offset_raw_phys + offset_x

    return df
