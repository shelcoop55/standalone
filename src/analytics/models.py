from dataclasses import dataclass
import numpy as np

@dataclass
class StressMapData:
    """Container for stress map aggregation results."""
    grid_counts: np.ndarray          # 2D array of total defect counts
    hover_text: np.ndarray           # 2D array of hover text strings
    total_defects: int               # Total defects in selection
    max_count: int                   # Max count in any single cell

@dataclass
class YieldKillerMetrics:
    """Container for Root Cause Analysis KPIs."""
    top_killer_layer: str
    top_killer_count: int
    worst_unit: str  # Format "X:col, Y:row"
    worst_unit_count: int
    side_bias: str   # "Front Side", "Back Side", or "Balanced"
    side_bias_diff: int
