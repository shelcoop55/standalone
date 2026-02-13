"""
Domain Models for Panel Defect Analysis.
Encapsulates logic for Build-Up Layers, Coordinate Transformations, and Defect Data.
"""
from dataclasses import dataclass
import pandas as pd
import numpy as np
import uuid
import logging
from typing import Dict, List, Optional
from src.core.config import PANEL_WIDTH, PANEL_HEIGHT, GAP_SIZE, QUADRANT_WIDTH, QUADRANT_HEIGHT, INTER_UNIT_GAP

logger = logging.getLogger(__name__)

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
        # Change: (n + 1) gaps to account for gap before first and after last unit
        cell_width = (quad_width - (self.panel_cols + 1) * INTER_UNIT_GAP) / self.panel_cols
        cell_height = (quad_height - (self.panel_rows + 1) * INTER_UNIT_GAP) / self.panel_rows

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
        # np.select requires numpy boolean ndarrays; pandas Int32 comparisons yield Series
        conditions_raw = [np.asarray(c, dtype=bool) for c in conditions_raw]
        choices = ['Q1', 'Q2', 'Q3', 'Q4']
        df['QUADRANT'] = np.select(conditions_raw, choices, default='Other')

        local_index_x_raw = df['UNIT_INDEX_X'] % self.panel_cols
        local_index_y = df['UNIT_INDEX_Y'] % self.panel_rows

        # Start at INTER_UNIT_GAP (Gap before first unit)
        plot_x_base_raw = INTER_UNIT_GAP + local_index_x_raw * stride_x
        plot_y_base = INTER_UNIT_GAP + local_index_y * stride_y

        x_offset_raw = np.where(df['UNIT_INDEX_X'] >= self.panel_cols, quad_width + self.gap_x, 0)
        y_offset = np.where(df['UNIT_INDEX_Y'] >= self.panel_rows, quad_height + self.gap_y, 0)

        # --- SPATIAL LOGIC ---
        # Use X/Y Coordinates for relative positioning if available (for both Front and Back).
        # Otherwise, default to random jitter.

        use_spatial_coords = False
        abs_x_mm = None
        abs_y_mm = None

        if 'X_COORDINATES' in df.columns and 'Y_COORDINATES' in df.columns:
            try:
                # ABSOLUTE MAPPING: Convert Microns to Millimeters directly.
                # Assumes X_COORDINATES are relative to the PANEL ORIGIN (Design Coordinates).
                # Range 0-480 (approx).

                # Convert um to mm
                abs_x_mm = df['X_COORDINATES'] / 1000.0
                abs_y_mm = df['Y_COORDINATES'] / 1000.0

                # Ensure they are numeric
                if pd.api.types.is_numeric_dtype(abs_x_mm) and pd.api.types.is_numeric_dtype(abs_y_mm):
                    use_spatial_coords = True
                else:
                    use_spatial_coords = False
            except (TypeError, ValueError, KeyError) as e:
                logger.warning(f"Spatial mapping failed: {e}")
                use_spatial_coords = False
            except Exception as e:
                logger.exception("Spatial mapping failed with unexpected error")
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
        if use_spatial_coords:
            # If using spatial coordinates, they are assumed to be Panel Coordinates.
            # We use them directly. Plotting layer adds Frame Margin.
            df['plot_x'] = offset_x
            df['plot_y'] = offset_y
        else:
            # Relative/Grid-based positioning
            df['plot_x'] = plot_x_base_raw + x_offset_raw + offset_x
            df['plot_y'] = plot_y_base + y_offset + offset_y

        # --- 2. PHYSICAL COORDINATES (Stacked View) ---
        # We now support two modes: Flipped (Aligned) and Raw (Unaligned).

        total_width_units = 2 * self.panel_cols

        # A) FLIPPED MODE (Standard Alignment) - Index Calculation
        if self.is_back:
            df['PHYSICAL_X_FLIPPED'] = (total_width_units - 1) - df['UNIT_INDEX_X']
        else:
            df['PHYSICAL_X_FLIPPED'] = df['UNIT_INDEX_X']

        # Alias PHYSICAL_X for backward compatibility
        df['PHYSICAL_X'] = df['PHYSICAL_X_FLIPPED']

        # B) RAW MODE (No Flip) - Index Calculation
        df['PHYSICAL_X_RAW'] = df['UNIT_INDEX_X']

        # --- PHYSICAL SPATIAL LOGIC ---

        # Base Grid Calculation (Fallback if no spatial coords)
        local_index_x_flipped = df['PHYSICAL_X_FLIPPED'] % self.panel_cols
        plot_x_base_flipped = INTER_UNIT_GAP + local_index_x_flipped * stride_x
        x_offset_flipped = np.where(df['PHYSICAL_X_FLIPPED'] >= self.panel_cols, quad_width + self.gap_x, 0)

        local_index_x_raw_phys = df['PHYSICAL_X_RAW'] % self.panel_cols
        plot_x_base_raw_phys = INTER_UNIT_GAP + local_index_x_raw_phys * stride_x
        x_offset_raw_phys = np.where(df['PHYSICAL_X_RAW'] >= self.panel_cols, quad_width + self.gap_x, 0)

        if use_spatial_coords:
            # Use REAL COORDINATES for Multi-Layer View

            # 1. Raw Physical (Simple)
            # Same as plot_x (Panel Relative)
            df['physical_plot_x_raw'] = abs_x_mm

            # 2. Flipped Physical (Aligned)
            # If Back Side, Flip around vertical center.
            # Center of Panel = (Panel Width + Gap) / 2?
            # Or simpler: Flipped X = Max Width - X
            # Max Width = self.panel_width + self.gap_x

            total_frame_width = self.panel_width + self.gap_x

            # User explicitly requested NO mirroring for Back side data.
            # We treat the provided coordinates as absolute and correct for the desired view.
            df['physical_plot_x_flipped'] = abs_x_mm

        else:
            # Grid-based Jitter Logic
            # Note: offset_x here is the Jitter value (0-cell_width) calculated above in 'else' block

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
        self._cached_combined_df: Optional[pd.DataFrame] = None

    def add_layer(self, layer: BuildUpLayer):
        if layer.layer_num not in self._layers:
            self._layers[layer.layer_num] = {}
        self._layers[layer.layer_num][layer.side] = layer
        self._cached_combined_df = None  # Invalidate cache

    def get_layer(self, layer_num: int, side: str) -> Optional[BuildUpLayer]:
        return self._layers.get(layer_num, {}).get(side)

    def get_all_layer_nums(self) -> List[int]:
        return sorted(self._layers.keys())

    def get_sides_for_layer(self, layer_num: int) -> List[str]:
        return sorted(self._layers.get(layer_num, {}).keys())

    def get_combined_dataframe(self, filter_func=None) -> pd.DataFrame:
        """Returns a concatenated DataFrame of all layers."""
        # Optimization: Return cached result if no filter is applied
        if filter_func is None and self._cached_combined_df is not None:
            return self._cached_combined_df

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
            res = pd.DataFrame()
        else:
            res = pd.concat(dfs, ignore_index=True)

        # Cache result if no filter was applied
        if filter_func is None:
            self._cached_combined_df = res

        return res

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
