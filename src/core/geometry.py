from dataclasses import dataclass
from typing import Dict, Tuple
from src.core.config import (
    FRAME_WIDTH, FRAME_HEIGHT,
    DEFAULT_OFFSET_X, DEFAULT_OFFSET_Y,
    DEFAULT_GAP_X, DEFAULT_GAP_Y,
    INTER_UNIT_GAP
)

@dataclass
class GeometryContext:
    """Derived dimensions and coordinate systems for the panel."""
    # Active Panel Dimensions (Calculated)
    panel_width: float
    panel_height: float

    # Quadrant Dimensions
    quad_width: float
    quad_height: float

    # Unit Cell Dimensions
    cell_width: float
    cell_height: float

    # Strides (Unit + Gap)
    stride_x: float
    stride_y: float

    # Effective gaps used for plotting (Fixed + Dynamic components)
    effective_gap_x: float
    effective_gap_y: float

    # Total Structural offsets (Start of Q1)
    offset_x: float
    offset_y: float

    # Origins of each quadrant (Top-Left corner)
    quadrant_origins: Dict[str, Tuple[float, float]]

    # Visual Origin Shifts (Additive)
    visual_origin_x: float
    visual_origin_y: float

class GeometryEngine:
    """
    Centralized logic for physical panel layout calculations.
    Ensures consistency between data analysis and visualization.
    """

    @staticmethod
    def calculate_layout(
        panel_rows: int,
        panel_cols: int,
        dyn_gap_x: float,
        dyn_gap_y: float,
        fixed_offset_x: float = DEFAULT_OFFSET_X,
        fixed_offset_y: float = DEFAULT_OFFSET_Y,
        fixed_gap_x: float = DEFAULT_GAP_X,
        fixed_gap_y: float = DEFAULT_GAP_Y,
        visual_origin_x: float = 0.0,
        visual_origin_y: float = 0.0
    ) -> GeometryContext:
        """
        Calculates the complete layout context based on configuration.
        """

        # 1. Active Panel Dimensions
        # Active Width = Frame - 2*Offset - FixedGap - 4*DynGap
        # (Logic from original app.py)
        p_width = float(FRAME_WIDTH) - 2 * fixed_offset_x - fixed_gap_x - 4 * dyn_gap_x
        p_height = float(FRAME_HEIGHT) - 2 * fixed_offset_y - fixed_gap_y - 4 * dyn_gap_y

        quad_width = p_width / 2
        quad_height = p_height / 2

        # 2. Effective Gaps
        # Gap between Q1 and Q2 = FixedGap + DynGap(Right Q1) + DynGap(Left Q2)
        effective_gap_x = fixed_gap_x + 2 * dyn_gap_x
        effective_gap_y = fixed_gap_y + 2 * dyn_gap_y

        # 3. Total Offsets (Start Position of Q1)
        # Symmetrical Logic: Start Position of Q1 = FixedOffset + DynGap (Left of Q1)
        total_off_x = fixed_offset_x + dyn_gap_x
        total_off_y = fixed_offset_y + dyn_gap_y

        # 4. Unit Cell Dimensions
        # UnitWidth = (QuadWidth - (Cols + 1) * gap) / Cols
        cell_width = (quad_width - (panel_cols + 1) * INTER_UNIT_GAP) / panel_cols
        cell_height = (quad_height - (panel_rows + 1) * INTER_UNIT_GAP) / panel_rows

        stride_x = cell_width + INTER_UNIT_GAP
        stride_y = cell_height + INTER_UNIT_GAP

        # 5. Quadrant Origins (Structural, before Visual Shift)
        # All relative to the Frame (0,0)
        q1_origin = (total_off_x, total_off_y)
        q2_origin = (total_off_x + quad_width + effective_gap_x, total_off_y)
        q3_origin = (total_off_x, total_off_y + quad_height + effective_gap_y)
        q4_origin = (total_off_x + quad_width + effective_gap_x, total_off_y + quad_height + effective_gap_y)

        origins = {
            'Q1': q1_origin,
            'Q2': q2_origin,
            'Q3': q3_origin,
            'Q4': q4_origin
        }

        return GeometryContext(
            panel_width=p_width,
            panel_height=p_height,
            quad_width=quad_width,
            quad_height=quad_height,
            cell_width=cell_width,
            cell_height=cell_height,
            stride_x=stride_x,
            stride_y=stride_y,
            effective_gap_x=effective_gap_x,
            effective_gap_y=effective_gap_y,
            offset_x=total_off_x,
            offset_y=total_off_y,
            quadrant_origins=origins,
            visual_origin_x=visual_origin_x,
            visual_origin_y=visual_origin_y
        )
