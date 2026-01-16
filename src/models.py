"""
Domain Models for Panel Defect Analysis.
Encapsulates logic for Build-Up Layers, Coordinate Transformations, and Defect Data.
"""
from dataclasses import dataclass
import pandas as pd
import numpy as np
import uuid
from typing import Dict, List, Optional
from src.config import PANEL_WIDTH, PANEL_HEIGHT, GAP_SIZE, QUADRANT_WIDTH, QUADRANT_HEIGHT, INTER_UNIT_GAP

@dataclass
class BuildUpLayer:
    """
    Represents a single side (Front/Back) of a specific Build-Up Layer.
    Encapsulates raw data and handles coordinate transformations.
    """
    layer_num: int
    side: str  # 'F' or 'B'
    raw_df: pd.DataFrame
    panel_rows: int
    panel_cols: int
    panel_width: float = PANEL_WIDTH
    panel_height: float = PANEL_HEIGHT
    gap_x: float = GAP_SIZE
    gap_y: float = GAP_SIZE

    def __post_init__(self):
        self._validate()
        self._add_plotting_coordinates()

    def _validate(self):
        if self.side not in ['F', 'B']:
            raise ValueError(f"Invalid side '{self.side}'. Must be 'F' or 'B'.")
        if self.raw_df.empty:
            return

    @property
    def is_front(self) -> bool:
        return self.side == 'F'

    @property
    def is_back(self) -> bool:
        return self.side == 'B'

    @property
    def label(self) -> str:
        side_name = "Front" if self.is_front else "Back"
        return f"Layer {self.layer_num} ({side_name})"

    @property
    def data(self) -> pd.DataFrame:
        """Returns the dataframe with both Raw and Physical plotting coordinates."""
        return self.raw_df

    def _add_plotting_coordinates(self):
        """
        Internal method to calculate and append 'plot_x', 'plot_y', and 'physical_plot_x'
        to the internal DataFrame.
        """
        if self.raw_df.empty:
            return

        df = self.raw_df

        # Use Dynamic Dimensions
        quad_width = self.panel_width / 2
        quad_height = self.panel_height / 2

        # Updated Logic: Subtract gaps first to get true unit size
        cell_width = (quad_width - (self.panel_cols - 1) * INTER_UNIT_GAP) / self.panel_cols
        cell_height = (quad_height - (self.panel_rows - 1) * INTER_UNIT_GAP) / self.panel_rows

        # Stride includes the unit width plus the gap
        stride_x = cell_width + INTER_UNIT_GAP
        stride_y = cell_height + INTER_UNIT_GAP

        # --- 1. RAW COORDINATES (Individual View - No Flip) ---
        # Calculate Raw Quadrant
        conditions_raw = [
            (df['UNIT_INDEX_X'] < self.panel_cols) & (df['UNIT_INDEX_Y'] < self.panel_rows),
            (df['UNIT_INDEX_X'] >= self.panel_cols) & (df['UNIT_INDEX_Y'] < self.panel_rows),
            (df['UNIT_INDEX_X'] < self.panel_cols) & (df['UNIT_INDEX_Y'] >= self.panel_rows),
            (df['UNIT_INDEX_X'] >= self.panel_cols) & (df['UNIT_INDEX_Y'] >= self.panel_rows)
        ]
        choices = ['Q1', 'Q2', 'Q3', 'Q4']
        df['QUADRANT'] = np.select(conditions_raw, choices, default='Other')

        local_index_x_raw = df['UNIT_INDEX_X'] % self.panel_cols
        local_index_y = df['UNIT_INDEX_Y'] % self.panel_rows

        plot_x_base_raw = local_index_x_raw * stride_x
        plot_y_base = local_index_y * stride_y

        x_offset_raw = np.where(df['UNIT_INDEX_X'] >= self.panel_cols, quad_width + self.gap_x, 0)
        y_offset = np.where(df['UNIT_INDEX_Y'] >= self.panel_rows, quad_height + self.gap_y, 0)

        # --- SPATIAL LOGIC ---
        # Use X/Y Coordinates for relative positioning if available (for both Front and Back).
        # Otherwise, default to random jitter.

        use_spatial_coords = False
        norm_x = None
        norm_y = None

        if 'X_COORDINATES' in df.columns and 'Y_COORDINATES' in df.columns:
            try:
                # ABSOLUTE MAPPING: Convert Microns to Millimeters directly.
                # Assumes X_COORDINATES are relative to the unit origin (0 to Cell Width).
                # No padding, no relative normalization.

                # Check bounds (optional warning?) - For now, we trust the data.

                # Convert um to mm
                abs_x_mm = df['X_COORDINATES'] / 1000.0
                abs_y_mm = df['Y_COORDINATES'] / 1000.0

                # Ensure they are numeric
                if pd.api.types.is_numeric_dtype(abs_x_mm) and pd.api.types.is_numeric_dtype(abs_y_mm):
                    use_spatial_coords = True
                else:
                    use_spatial_coords = False
            except Exception as e:
                print(f"Spatial mapping failed: {e}")
                use_spatial_coords = False

        if use_spatial_coords:
            # Use absolute mm offsets
            offset_x = abs_x_mm
            offset_y = abs_y_mm
        else:
            # Use Random Jitter (10% to 90% of cell)
            offset_x = np.random.rand(len(df)) * cell_width * 0.8 + (cell_width * 0.1)
            offset_y = np.random.rand(len(df)) * cell_height * 0.8 + (cell_height * 0.1)

        # --- COORDINATE ASSIGNMENT ---
        # If using precise spatial coordinates (absolute mm), we ignore the unit-grid base position.
        # If using Unit Index only, we use the base position + jitter offset.

        if use_spatial_coords:
            # offset_x/y hold the ABSOLUTE mm coordinates
            # We still need to account for GAP if the absolute coordinate crosses the gap boundary?
            # User said "plot based on my coordinates".
            # If coordinates are raw micron values from the machine, they usually ignore the visual gap we insert.
            # So we just use them directly as the 'base' position relative to (0,0).
            # BUT, we must still respect the Gap Logic for Q2/Q4 if we want to separate them visually?
            # If the user provides raw coords (0-600mm), they might already include the gap or not.
            # Usually raw coords are contiguous. We want to insert a gap.

            # Logic:
            # If using spatial coordinates, they are assumed to be Absolute (Frame Origin).
            # Thus, they ALREADY include the gap if they are physically correct.
            # We should NOT add the calculated gap offset again.

            df['plot_x'] = offset_x
            df['plot_y'] = offset_y
        else:
            # Relative/Grid-based positioning
            df['plot_x'] = plot_x_base_raw + x_offset_raw + offset_x
            df['plot_y'] = plot_y_base + y_offset + offset_y

        # --- 2. PHYSICAL COORDINATES (Stacked View) ---
        # We now support two modes: Flipped (Aligned) and Raw (Unaligned).
        # We pre-calculate both to allow fast toggling.

        total_width_units = 2 * self.panel_cols

        # A) FLIPPED MODE (Standard Alignment)
        # If Side is Back, Flip X Index: Physical X = (Total_Cols - 1) - Raw_X
        if self.is_back:
            df['PHYSICAL_X_FLIPPED'] = (total_width_units - 1) - df['UNIT_INDEX_X']
        else:
            df['PHYSICAL_X_FLIPPED'] = df['UNIT_INDEX_X']

        # Alias PHYSICAL_X for backward compatibility (e.g. data_handler.get_true_defect_coordinates)
        df['PHYSICAL_X'] = df['PHYSICAL_X_FLIPPED']

        local_index_x_flipped = df['PHYSICAL_X_FLIPPED'] % self.panel_cols
        plot_x_base_flipped = local_index_x_flipped * stride_x
        x_offset_flipped = np.where(df['PHYSICAL_X_FLIPPED'] >= self.panel_cols, quad_width + self.gap_x, 0)

        # B) RAW MODE (No Flip) - PRE-CALCULATE VARIABLES
        df['PHYSICAL_X_RAW'] = df['UNIT_INDEX_X']
        local_index_x_raw_phys = df['PHYSICAL_X_RAW'] % self.panel_cols
        plot_x_base_raw_phys = local_index_x_raw_phys * stride_x
        x_offset_raw_phys = np.where(df['PHYSICAL_X_RAW'] >= self.panel_cols, quad_width + self.gap_x, 0)

        if use_spatial_coords:
            # For flipped view, we need to flip the absolute coordinate relative to the panel width?
            # Flipping absolute coordinates is complex (need max width).
            # Simplified: Use the grid-based logic for the flipped view for now, OR rely on UNIT_INDEX flipping.
            # If we use offset_x (absolute), it is NOT flipped.
            # If the user wants alignment, we should probably stick to grid logic for this specific "Stack" view,
            # OR implement true mirroring of coordinates: Max_X - Coord_X.
            # Given the constraints and "user request to NOT flip internal spatial offset",
            # we will assume offset_x applies as-is to the flipped grid cell?
            # Actually, `plot_x_base_flipped` puts us in the correct flipped cell.
            # If we add `offset_x` (Absolute), we are adding a massive number (e.g. 165mm) to the flipped base.
            # This BREAKS the flipped view too.

            # Correction: In Flipped Mode, we probably shouldn't use Absolute Coords linearly if they are global.
            # If Absolute Coords are "Global X", then flipping means "Total Width - Global X".
            # If `offset_x` holds Global X.

            # Let's try to flip the Global X.
            # Total Width approx PANEL_WIDTH.
            # df['physical_plot_x_flipped'] = PANEL_WIDTH - offset_x (roughly).
            # But we must respect the Gap.

            # To be safe and ensure the Stack view works without massive regression:
            # We will use the UNIT_INDEX derived position for the "Base" of the flip,
            # and only use the "Relative" part of the spatial coord if we can derive it.
            # BUT we overwrote `offset_x` with Absolute.
            # So we cannot use `offset_x` here for relative jitter.

            # Fallback: For Physical/Flipped views, if using absolute coords,
            # we just use the calculated `plot_x` (Raw) and rely on the plotting layer to handle side-by-side?
            # No, Stack view overlays them.

            # DECISION: For the "Multi-Layer" view (which uses physical_plot_x_flipped),
            # we will disable the Absolute Coordinate override and fall back to Grid Center to avoid complexity
            # and regression, UNLESS we can easily flip.
            # Since `offset_x` is now Absolute, `plot_x_base_flipped + offset_x` is definitely wrong (Double Count).

            # We must NOT add `plot_x_base_flipped`.
            # We just want the Flipped Absolute Coordinate.
            # Flip Logic: X_Flipped = Max_Width - X_Raw.
            # Max_Width = PANEL_WIDTH (approx).
            # We should probably use that.

            # Note: We need to handle the Gap.
            # If X_Raw is in Q2 (e.g. 350), X_Flipped is in Q1 (e.g. 110).
            # Gap handling is tricky.

            # Safe Bet: For now, map Flipped X to `(Total_Units - Unit_Index) * Cell_Width + (Cell_Width/2)`.
            # Ignore fine spatial coords for the Flipped View to ensure robustness.
            # This effectively "snaps" the flipped view to grid centers, but ensures it's visible.

            # Re-calculate a relative offset for visual variance?
            # offset_x_rel = (offset_x % cell_width) ... maybe?
            # Too risky.

            # We'll just use the Grid Base + Centering for flipped/phys views when absolute coords are active.
            df['physical_plot_x_flipped'] = plot_x_base_flipped + x_offset_flipped + (cell_width/2)
            df['physical_plot_x_raw'] = plot_x_base_raw_phys + x_offset_raw_phys + (cell_width/2)

        else:
            # Default Jitter Logic
            # We do NOT flip the internal spatial offset (offset_x) as per user request (from original code).
            df['physical_plot_x_flipped'] = plot_x_base_flipped + x_offset_flipped + offset_x
            df['physical_plot_x_raw'] = plot_x_base_raw_phys + x_offset_raw_phys + offset_x


class PanelData:
    """
    Container for the entire panel's data.
    Replaces Dict[int, Dict[str, DataFrame]].
    """
    def __init__(self):
        # Internal storage: layer_num -> side -> BuildUpLayer
        self._layers: Dict[int, Dict[str, BuildUpLayer]] = {}
        # Unique ID for caching/hashing purposes
        self.id = uuid.uuid4().hex

    def add_layer(self, layer: BuildUpLayer):
        if layer.layer_num not in self._layers:
            self._layers[layer.layer_num] = {}
        self._layers[layer.layer_num][layer.side] = layer

    def get_layer(self, layer_num: int, side: str) -> Optional[BuildUpLayer]:
        return self._layers.get(layer_num, {}).get(side)

    def get_all_layer_nums(self) -> List[int]:
        return sorted(self._layers.keys())

    def get_sides_for_layer(self, layer_num: int) -> List[str]:
        return sorted(self._layers.get(layer_num, {}).keys())

    def get_combined_dataframe(self, filter_func=None) -> pd.DataFrame:
        """Returns a concatenated DataFrame of all layers."""
        dfs = []
        for layer_num in self._layers:
            for side in self._layers[layer_num]:
                layer = self._layers[layer_num][side]
                df = layer.data.copy()
                # Add Metadata
                df['LAYER_NUM'] = layer_num
                df['SIDE'] = side
                df['Layer_Label'] = layer.label

                if filter_func:
                    df = filter_func(df)

                if not df.empty:
                    dfs.append(df)

        if not dfs:
            return pd.DataFrame()
        return pd.concat(dfs, ignore_index=True)

    def __bool__(self):
        return bool(self._layers)

    def __len__(self):
        return len(self._layers)

    # --- Compatibility Interface (mimics Dict behaviour for easier migration) ---
    def __iter__(self):
        return iter(self._layers)

    def keys(self):
        return self._layers.keys()

    def items(self):
        return self._layers.items()

    def values(self):
        return self._layers.values()

    def __getitem__(self, key):
        # Returns the inner dict {side: BuildUpLayer}
        # Ideally we refactor consumers to not need this, but for now:
        # Consumers expect Dict[str, DataFrame].
        # We need to return a proxy that behaves like { 'F': df, 'B': df }
        # This is a bit hacky but allows gradual refactor.

        inner = self._layers[key]
        return {side: layer_obj.data for side, layer_obj in inner.items()}

    def __contains__(self, key):
        return key in self._layers

    def get(self, key, default=None):
        if key in self._layers:
            return self[key] # Use the __getitem__ proxy logic
        return default
