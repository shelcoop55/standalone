import pandas as pd
import numpy as np
from src.core.models import PanelData, BuildUpLayer
from src.core.config import (
    DEFAULT_OFFSET_X, DEFAULT_OFFSET_Y,
    INTER_UNIT_GAP, DEFAULT_GAP_X, DEFAULT_GAP_Y
)

# --- DEFECT DEFINITIONS FOR SAMPLE GENERATION ---
DEFECT_DEFINITIONS = [
    ("CU10", "Copper Void (Nick)"), ("CU14", "Copper Void on Copper Ground"),
    ("CU18", "Short on the Surface (AOI)"), ("CU17", "Plating Under Resist (Fine Short)"),
    ("CU22", "Copper Residue"), ("CU16", "Open on the Surface (AOI)"),
    ("CU54", "Copper Distribution Not Even / Nodule"), ("CU25", "Rough Trace"),
    ("CU15", "Fine Short (Burr)"), ("CU94", "Global Copper Thickness Out of Spec"),
    ("CU19", "Eless Remaining"), ("CU20", "Circle Defect"),
    ("CU41", "Copper Coloration or Spots"), ("CU80", "Risk to Via Integrity"),
    ("BM31", "Base Material Defect"), ("BM01", "Base Material Defect (Crack)"),
    ("GE01", "Scratch"), ("GE32", "ABF Wrinkle"), ("GE57", "Foreign Material"),
    ("HO31", "Via Not Completely Filled"), ("HO12", "Hole Shift")
]
SIMPLE_DEFECT_TYPES = ['Nick', 'Short', 'Cut', 'Island', 'Space', 'Minimum Line', 'Deformation', 'Protrusion']
FALSE_ALARMS = ["N", "FALSE"]

def generate_sample_data(
    panel_rows: int,
    panel_cols: int,
    panel_width: float,
    panel_height: float,
    gap_x: float,
    gap_y: float
) -> PanelData:
    """
    Generates synthetic sample data for demonstration.

    Args:
        panel_rows: Number of rows per quadrant
        panel_cols: Number of columns per quadrant
        panel_width: Total active width of the panel (sum of 2 quadrants)
        panel_height: Total active height of the panel (sum of 2 quadrants)
        gap_x: Effective horizontal gap between quadrants (Fixed + 2*Dynamic)
        gap_y: Effective vertical gap between quadrants (Fixed + 2*Dynamic)
    """
    panel_data = PanelData()
    panel_data.id = "sample_data" # Specific ID for sample

    total_units_x = 2 * panel_cols
    total_units_y = 2 * panel_rows
    np.random.seed(55)

    layers_to_generate = [1, 2, 3, 4, 5]
    # Reduced counts by ~60% as per requirements
    layer_counts = {1: (32, 40), 2: (80, 120), 3: (20, 24), 4: (16, 32), 5: (40, 80)}

    quad_w = panel_width / 2
    quad_h = panel_height / 2

    # Calculate Unit Cell Dimensions
    cell_w = (quad_w - (panel_cols + 1) * INTER_UNIT_GAP) / panel_cols
    cell_h = (quad_h - (panel_rows + 1) * INTER_UNIT_GAP) / panel_rows

    stride_x = cell_w + INTER_UNIT_GAP
    stride_y = cell_h + INTER_UNIT_GAP

    # Calculate Dynamic Gaps (derived from effective gap)
    # effective_gap = fixed_gap + 2 * dyn_gap
    dyn_gap_x = max(0, (gap_x - DEFAULT_GAP_X) / 2)
    dyn_gap_y = max(0, (gap_y - DEFAULT_GAP_Y) / 2)

    # Base Offsets (Start of Q1)
    base_offset_x = DEFAULT_OFFSET_X + dyn_gap_x
    base_offset_y = DEFAULT_OFFSET_Y + dyn_gap_y

    for layer_num in layers_to_generate:
        false_alarm_rate = np.random.uniform(0.5, 0.6)
        for side in ['F', 'B']:
            low, high = layer_counts.get(layer_num, (40, 60))
            num_points = np.random.randint(low, high)

            rand_x_coords_mm = []
            rand_y_coords_mm = []
            final_unit_x = []
            final_unit_y = []

            for _ in range(num_points):
                ux = np.random.randint(0, total_units_x)
                uy = np.random.randint(0, total_units_y)
                final_unit_x.append(ux)
                final_unit_y.append(uy)

                qx = 1 if ux >= panel_cols else 0
                qy = 1 if uy >= panel_rows else 0
                lx = ux % panel_cols
                ly = uy % panel_rows

                # Calculate Quadrant Offset
                # Q2/Q4 start at: Base + QuadWidth + EffectiveGap
                # This formula (qx * (quad_w + gap_x)) handles the jump correctly
                quad_shift_x = qx * (quad_w + gap_x)
                quad_shift_y = qy * (quad_h + gap_y)

                # Calculate Local Offset within Quadrant
                # Starts after the first margin gap
                local_off_x = INTER_UNIT_GAP + lx * stride_x
                local_off_y = INTER_UNIT_GAP + ly * stride_y

                x_start = base_offset_x + quad_shift_x + local_off_x
                y_start = base_offset_y + quad_shift_y + local_off_y

                rx = np.random.uniform(x_start, x_start + cell_w)
                ry = np.random.uniform(y_start, y_start + cell_h)
                rand_x_coords_mm.append(rx)
                rand_y_coords_mm.append(ry)

            defect_data = {
                'DEFECT_ID': range(num_points),
                'UNIT_INDEX_X': np.array(final_unit_x, dtype='int32'),
                'UNIT_INDEX_Y': np.array(final_unit_y, dtype='int32'),
                'DEFECT_TYPE': [np.random.choice(SIMPLE_DEFECT_TYPES) for _ in range(num_points)],
                'Verification': [np.random.choice(FALSE_ALARMS) if np.random.rand() < false_alarm_rate else DEFECT_DEFINITIONS[np.random.randint(len(DEFECT_DEFINITIONS))][0] for _ in range(num_points)],
                'SOURCE_FILE': [f'Sample Data Layer {layer_num}{side}'] * num_points,
                'SIDE': side,
                'HAS_VERIFICATION_DATA': [True] * num_points,
                'X_COORDINATES': np.array(rand_x_coords_mm) * 1000,
                'Y_COORDINATES': np.array(rand_y_coords_mm) * 1000
            }

            df = pd.DataFrame(defect_data)

            layer_obj = BuildUpLayer(layer_num, side, df, panel_rows, panel_cols, panel_width, panel_height, gap_x, gap_y)
            panel_data.add_layer(layer_obj)

    return panel_data
