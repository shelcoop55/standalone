"""
Data Handling Module.
This version calculates defect locations based on a true-to-scale simulation
of a fixed-size 510x510mm physical panel.
"""
import streamlit as st
import pandas as pd
import numpy as np
import re
from typing import List, Dict, Set, Tuple, Any, Optional
from io import BytesIO
from dataclasses import dataclass

# Import constants from the configuration file
from .config import PANEL_WIDTH, PANEL_HEIGHT, GAP_SIZE, SAFE_VERIFICATION_VALUES
from .models import PanelData, BuildUpLayer

# --- DERIVED PHYSICAL CONSTANTS ---
# These constants are calculated from the primary dimensions in config.py
QUADRANT_WIDTH = PANEL_WIDTH / 2
QUADRANT_HEIGHT = PANEL_HEIGHT / 2

# --- DEFECT DEFINITIONS ---
# List of (Code, Description) tuples for data generation
DEFECT_DEFINITIONS = [
    # Copper-related (CU)
    ("CU10", "Copper Void (Nick)"),
    ("CU14", "Copper Void on Copper Ground"),
    ("CU18", "Short on the Surface (AOI)"),
    ("CU17", "Plating Under Resist (Fine Short)"),
    ("CU22", "Copper Residue"),
    ("CU16", "Open on the Surface (AOI)"),
    ("CU54", "Copper Distribution Not Even / Nodule"),
    ("CU25", "Rough Trace"),
    ("CU15", "Fine Short (Burr)"),
    ("CU94", "Global Copper Thickness Out of Spec – Copper Sting"),
    ("CU19", "Eless Remaining (Chemical Copper Residue)"),
    ("CU20", "Circle Defect"),
    ("CU41", "Copper Coloration or Spots"),
    ("CU80", "Risk to Via Integrity (Core)"),
    # Base Material (BM)
    ("BM31", "Base Material Defect (Irregular Shape)"),
    ("BM01", "Base Material Defect (Crack)"),
    ("BM10", "Base Material Defect (Round Shape)"),
    ("BM34", "Measling / Crazing (White Spots)"),
    # General (GE)
    ("GE01", "Scratch"),
    ("GE32", "ABF Wrinkle"),
    ("GE57", "Foreign Material"),
    ("GE22", "Process Residue"),
    # Hole-related (HO)
    ("HO31", "Via Not Completely Filled"),
    ("HO12", "Hole Shift")
]

# Simple Defect Types to be used as descriptions/types
SIMPLE_DEFECT_TYPES = [
    'Nick', 'Short', 'Cut', 'Island', 'Space',
    'Minimum Line', 'Line Nick', 'Deformation',
    'Protrusion', 'Added Feature'
]

FALSE_ALARMS = ["N", "FALSE"]

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

@st.cache_data
def load_data(
    uploaded_files: List[BytesIO],
    panel_rows: int,
    panel_cols: int,
) -> PanelData:
    """
    Loads defect data from multiple build-up layer files, validates filenames
    (e.g., BU-01F..., BU-01B...), and processes each layer's data.
    Returns a PanelData object containing all layers.
    """
    panel_data = PanelData()

    if uploaded_files:
        # Temporary storage for concatenation
        temp_data: Dict[int, Dict[str, List[pd.DataFrame]]] = {}

        for uploaded_file in uploaded_files:
            file_name = uploaded_file.name
            match = re.match(r"BU-(\d{2})\s*([FB])", file_name, re.IGNORECASE)

            if not match:
                st.warning(f"Skipping file: '{file_name}'. Name must follow 'BU-XXF' or 'BU-XXB' format (e.g., 'BU-01F-...).")
                continue

            layer_num, side = int(match.group(1)), match.group(2).upper()

            try:
                df = pd.read_excel(uploaded_file, sheet_name='Defects', engine='openpyxl')
                df.rename(columns={'VERIFICATION': 'Verification'}, inplace=True)
                df['SOURCE_FILE'] = file_name
                df['SIDE'] = side

                # --- VERIFICATION LOGIC UPDATE ---
                # Check if we have real verification data
                has_verification_data = 'Verification' in df.columns

                # 1. If 'Verification' column is missing, create it and mark as "Under Verification".
                # 2. If it exists, fill NaN/Blanks with 'N' (Safe).
                if not has_verification_data:
                    df['Verification'] = 'Under Verification'
                else:
                    df['Verification'] = df['Verification'].fillna('N').astype(str).str.strip()
                    # Also handle empty strings that might result from stripping
                    df['Verification'] = df['Verification'].replace('', 'N')

                # Store the flag in the DataFrame for use in plotting
                df['HAS_VERIFICATION_DATA'] = has_verification_data

                required_columns = ['DEFECT_ID', 'DEFECT_TYPE', 'UNIT_INDEX_X', 'UNIT_INDEX_Y']
                if not all(col in df.columns for col in required_columns):
                    st.error(f"File '{file_name}' is missing required columns: {required_columns}. It has been skipped.")
                    continue

                df.dropna(subset=required_columns, inplace=True)
                for col in ['UNIT_INDEX_X', 'UNIT_INDEX_Y']: df[col] = df[col].astype(int)
                df['DEFECT_TYPE'] = df['DEFECT_TYPE'].str.strip()

                # --- COORDINATE HANDLING (RAW vs PHYSICAL) ---
                # RAW: UNIT_INDEX_X from the file (used for Individual Layer View).
                # PHYSICAL: Flipped for Back side to align with Front side (used for Yield/Heatmaps).

                df['PHYSICAL_X'] = df['UNIT_INDEX_X'] # Default to Raw

                if side == 'B':
                    # Back side is mirrored. Calculate Physical X.
                    total_width_units = 2 * panel_cols
                    df['PHYSICAL_X'] = (total_width_units - 1) - df['UNIT_INDEX_X']

                if layer_num not in temp_data: temp_data[layer_num] = {}
                if side not in temp_data[layer_num]: temp_data[layer_num][side] = []

                temp_data[layer_num][side].append(df)

            except ValueError:
                st.error(f"Error in '{file_name}': A sheet named 'Defects' was not found.")
                continue
            except Exception as e:
                st.error(f"An unexpected error occurred while reading '{file_name}': {e}")
                continue
        
        # Build PanelData
        for layer_num, sides in temp_data.items():
            for side, dfs in sides.items():
                merged_df = pd.concat(dfs, ignore_index=True)
                layer_obj = BuildUpLayer(layer_num, side, merged_df, panel_rows, panel_cols)
                panel_data.add_layer(layer_obj)

        if panel_data:
            st.sidebar.success(f"{len(temp_data)} layer(s) loaded successfully!")

    else:
        st.sidebar.info("No file uploaded. Displaying sample data for 3 layers (all with Front/Back).")
        total_units_x = 2 * panel_cols
        total_units_y = 2 * panel_rows

        # 3 Layers
        layers_to_generate = [1, 2, 3]

        for layer_num in layers_to_generate:
            # Random False Alarm Rate for this layer (50% - 60%)
            false_alarm_rate = np.random.uniform(0.5, 0.6)

            for side in ['F', 'B']:
                # Random number of points (100 - 150) for both sides
                num_points = np.random.randint(100, 151)

                # Generate random indices
                unit_x = np.random.randint(0, total_units_x, size=num_points)
                unit_y = np.random.randint(0, total_units_y, size=num_points)

                # Generate Defect Types and Verification statuses
                defect_types = []
                verifications = []

                for _ in range(num_points):
                    # Always use Simple Defect Types for the "Machine" view (DEFECT_TYPE)
                    desc = np.random.choice(SIMPLE_DEFECT_TYPES)
                    defect_types.append(desc)

                    # Decide Verification Status
                    if np.random.rand() < false_alarm_rate:
                        # False Alarm: Machine saw 'desc', verification is 'N' or 'FALSE'
                        verifications.append(np.random.choice(FALSE_ALARMS))
                    else:
                        # True Defect: Verification confirms a specific Code (e.g., CU10)
                        # We pick a random code from the definitions
                        code, _ = DEFECT_DEFINITIONS[np.random.randint(len(DEFECT_DEFINITIONS))]
                        verifications.append(code)

                defect_data = {
                    'DEFECT_ID': range(layer_num * 1000 + (0 if side == 'F' else 500), layer_num * 1000 + (0 if side == 'F' else 500) + num_points),
                    'UNIT_INDEX_X': unit_x,
                    'UNIT_INDEX_Y': unit_y,
                    'DEFECT_TYPE': defect_types,
                    'Verification': verifications,
                    'SOURCE_FILE': [f'Sample Data Layer {layer_num}{side}'] * num_points,
                    'SIDE': side,
                    'HAS_VERIFICATION_DATA': [True] * num_points
                }

                df = pd.DataFrame(defect_data)
                layer_obj = BuildUpLayer(layer_num, side, df, panel_rows, panel_cols)
                panel_data.add_layer(layer_obj)

    return panel_data

def get_true_defect_coordinates(
    panel_data: PanelData,
    excluded_layers: Optional[List[int]] = None
) -> Dict[Tuple[int, int], Dict[str, Any]]:
    """
    Aggregates all "True" defects from all layers and sides to find unique
    defective cell coordinates for the Still Alive map.

    Returns:
        Dict mapping (physical_x, physical_y) -> {
            'first_killer_layer': int,
            'defects': List[str] # List of "L{num}: {count}"
        }
    """
    if not panel_data:
        return {}

    all_layers_df = panel_data.get_combined_dataframe()

    if all_layers_df.empty or 'Verification' not in all_layers_df.columns:
        return {}

    # Filter Excluded Layers ("What-If" Logic)
    if excluded_layers:
        all_layers_df = all_layers_df[~all_layers_df['LAYER_NUM'].isin(excluded_layers)]

    if all_layers_df.empty:
        return {}

    # Filter for True Defects
    safe_values_upper = {v.upper() for v in SAFE_VERIFICATION_VALUES}
    is_true_defect = ~all_layers_df['Verification'].str.upper().isin(safe_values_upper)
    true_defects_df = all_layers_df[is_true_defect].copy()

    if true_defects_df.empty:
        return {}

    if 'PHYSICAL_X' not in true_defects_df.columns:
        true_defects_df['PHYSICAL_X'] = true_defects_df['UNIT_INDEX_X']

    # Aggregate Metadata per Unit
    # We want: First Killer Layer, and a Summary string

    # Group by Unit
    grouped = true_defects_df.groupby(['PHYSICAL_X', 'UNIT_INDEX_Y'])

    result = {}

    for (px, py), group in grouped:
        # Sort by Layer Num to find first killer
        sorted_group = group.sort_values('LAYER_NUM')
        first_killer = sorted_group.iloc[0]['LAYER_NUM']

        # Summarize defects: "L1: 5, L2: 3"
        layer_counts = sorted_group['LAYER_NUM'].value_counts().sort_index()
        summary_parts = [f"L{l}: {c}" for l, c in layer_counts.items()]

        result[(px, py)] = {
            'first_killer_layer': first_killer,
            'defect_summary': ", ".join(summary_parts)
        }

    return result

@st.cache_data
def prepare_multi_layer_data(_panel_data: PanelData) -> pd.DataFrame:
    """
    Aggregates and filters defect data from all layers for the Multi-Layer Defect View.
    """
    if not _panel_data:
        return pd.DataFrame()

    safe_values_upper = {v.upper() for v in SAFE_VERIFICATION_VALUES}

    def true_defect_filter(df):
        if 'Verification' in df.columns:
            return df[~df['Verification'].str.upper().isin(safe_values_upper)]
        return df

    return _panel_data.get_combined_dataframe(filter_func=true_defect_filter)

@st.cache_data
def aggregate_stress_data(
    _panel_data: PanelData,
    selected_keys: List[Tuple[int, str]],
    panel_rows: int,
    panel_cols: int
) -> StressMapData:
    """
    Aggregates data for the Cumulative Stress Map using specific (Layer, Side) keys.
    """
    total_cols = panel_cols * 2
    total_rows = panel_rows * 2

    grid_counts = np.zeros((total_rows, total_cols), dtype=int)
    hover_text = np.empty((total_rows, total_cols), dtype=object)
    hover_text[:] = ""

    cell_defects: Dict[Tuple[int, int], Dict[str, int]] = {}
    safe_values_upper = {v.upper() for v in SAFE_VERIFICATION_VALUES}

    total_defects_acc = 0
    max_count_acc = 0

    for layer_num, side in selected_keys:
        layer = _panel_data.get_layer(layer_num, side)
        if not layer: continue

        df = layer.data
        if df.empty: continue

        # Filter True Defects
        df_true = df.copy()
        if 'Verification' in df_true.columns:
            is_true = ~df_true['Verification'].str.upper().isin(safe_values_upper)
            df_true = df_true[is_true]

        if df_true.empty: continue

        # Use RAW COORDINATES (UNIT_INDEX_X) as per request, do NOT flip.

        # Iterate rows
        for _, row in df_true.iterrows():
            gx = int(row['UNIT_INDEX_X'])
            gy = int(row['UNIT_INDEX_Y'])
            dtype = str(row['DEFECT_TYPE'])

            # Boundary check (safety)
            if 0 <= gx < total_cols and 0 <= gy < total_rows:
                grid_counts[gy, gx] += 1
                total_defects_acc += 1

                # Track Defect Types
                if (gy, gx) not in cell_defects: cell_defects[(gy, gx)] = {}
                cell_defects[(gy, gx)][dtype] = cell_defects[(gy, gx)].get(dtype, 0) + 1


    # Post-process for Hover Text
    for y in range(total_rows):
        for x in range(total_cols):
            count = grid_counts[y, x]
            if count > max_count_acc: max_count_acc = count

            if count > 0:
                # 1. Drill Down Tooltip
                defects_map = cell_defects.get((y, x), {})
                # Sort by count desc
                sorted_defects = sorted(defects_map.items(), key=lambda item: item[1], reverse=True)
                top_3 = sorted_defects[:3]

                tooltip = f"<b>Total: {count}</b><br>"
                tooltip += "<br>".join([f"{d[0]}: {d[1]}" for d in top_3])
                if len(sorted_defects) > 3:
                    tooltip += f"<br>... (+{len(sorted_defects)-3} types)"

                hover_text[y, x] = tooltip
            else:
                hover_text[y, x] = "No Defects"

    return StressMapData(
        grid_counts=grid_counts,
        hover_text=hover_text,
        total_defects=total_defects_acc,
        max_count=max_count_acc
    )

@st.cache_data
def calculate_yield_killers(_panel_data: PanelData, panel_rows: int, panel_cols: int) -> Optional[YieldKillerMetrics]:
    """
    Calculates the 'Yield Killer' KPIs: Worst Layer, Worst Unit, Side Bias.
    """
    if not _panel_data: return None

    safe_values_upper = {v.upper() for v in SAFE_VERIFICATION_VALUES}

    def true_defect_filter(df):
        if 'Verification' in df.columns:
            return df[~df['Verification'].str.upper().isin(safe_values_upper)]
        return df

    combined_df = _panel_data.get_combined_dataframe(filter_func=true_defect_filter)

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

@st.cache_data
def get_cross_section_matrix(
    _panel_data: PanelData,
    slice_axis: str,
    x_range: Tuple[int, int],
    y_range: Tuple[int, int],
    panel_rows: int,
    panel_cols: int
) -> Tuple[np.ndarray, List[str], List[str]]:
    """
    Constructs the 2D cross-section matrix for Root Cause Analysis based on a Region of Interest.
    """
    sorted_layers = _panel_data.get_all_layer_nums()
    num_layers = len(sorted_layers)
    if num_layers == 0:
        return np.zeros((0,0)), [], []

    if slice_axis == 'Y':
        # Projection Axis is X
        start, end = x_range
        width_dim = end - start + 1
        axis_labels = [str(i) for i in range(start, end + 1)]
    else:
        # Projection Axis is Y
        start, end = y_range
        width_dim = end - start + 1
        axis_labels = [str(i) for i in range(start, end + 1)]

    matrix = np.zeros((num_layers, width_dim), dtype=int)
    layer_labels = [f"L{num}" for num in sorted_layers]

    safe_values_upper = {v.upper() for v in SAFE_VERIFICATION_VALUES}

    for i, layer_num in enumerate(sorted_layers):
        sides = _panel_data._layers[layer_num] # Direct access to dict for now
        for side, layer_obj in sides.items():
            df = layer_obj.data
            if df.empty: continue

            df_copy = df.copy()
            if 'Verification' in df_copy.columns:
                is_true = ~df_copy['Verification'].str.upper().isin(safe_values_upper)
                df_copy = df_copy[is_true]

            if df_copy.empty: continue

            # 2. Filter by ROI
            relevant_defects = df_copy[
                (df_copy['UNIT_INDEX_X'] >= x_range[0]) & (df_copy['UNIT_INDEX_X'] <= x_range[1]) &
                (df_copy['UNIT_INDEX_Y'] >= y_range[0]) & (df_copy['UNIT_INDEX_Y'] <= y_range[1])
            ]

            if relevant_defects.empty: continue

            # 3. Aggregate
            if slice_axis == 'Y':
                counts = relevant_defects.groupby('UNIT_INDEX_X').size()
                for x_idx, count in counts.items():
                    if x_range[0] <= x_idx <= x_range[1]:
                        col_idx = int(x_idx) - x_range[0]
                        matrix[i, col_idx] += count
            else:
                counts = relevant_defects.groupby('UNIT_INDEX_Y').size()
                for y_idx, count in counts.items():
                    if y_range[0] <= y_idx <= y_range[1]:
                        col_idx = int(y_idx) - y_range[0]
                        matrix[i, col_idx] += count

    return matrix, layer_labels, axis_labels
