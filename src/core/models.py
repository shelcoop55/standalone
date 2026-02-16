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
        # Plotting coordinates are now applied lazily by src.core.layout

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
        """Returns the raw dataframe."""
        return self.raw_df



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

    def get(self, key, default=None):
        """Mimics dict.get() for backward compatibility."""
        if key in self._layers:
            return self[key]
        return default

    def __contains__(self, key):
        return key in self._layers

    def get(self, key, default=None):
        if key in self._layers:
            return self[key] # Use the __getitem__ proxy logic
        return default
