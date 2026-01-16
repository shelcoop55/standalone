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

# Use st.cache_data with a hash function for the files to avoid re-reading
@st.cache_data(show_spinner="Loading Data...")
def load_data(
    uploaded_files: List[Any], # Changed to Any to handle potential Streamlit UploadedFile wrapper changes
    panel_rows: int,
    panel_cols: int,
    panel_width: float = PANEL_WIDTH, # Default to config if not provided
    panel_height: float = PANEL_HEIGHT,
    gap_x: float = GAP_SIZE,
    gap_y: float = GAP_SIZE
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
                # OPTIMIZATION: Use calamine engine for faster loading
                df = pd.read_excel(uploaded_file, sheet_name='Defects', engine='calamine')
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
                    # OPTIMIZATION: Normalize to uppercase once here
                    df['Verification'] = df['Verification'].fillna('N').astype(str).str.strip().str.upper()
                    # Also handle empty strings that might result from stripping
                    df['Verification'] = df['Verification'].replace('', 'N')

                # Store the flag in the DataFrame for use in plotting
                df['HAS_VERIFICATION_DATA'] = has_verification_data

                required_columns = ['DEFECT_ID', 'DEFECT_TYPE', 'UNIT_INDEX_X', 'UNIT_INDEX_Y']
                if not all(col in df.columns for col in required_columns):
                    st.error(f"File '{file_name}' is missing required columns: {required_columns}. It has been skipped.")
                    continue

                df.dropna(subset=required_columns, inplace=True)

                # OPTIMIZATION: Type Hygiene to reduce memory usage
                df['UNIT_INDEX_X'] = df['UNIT_INDEX_X'].astype('int32')
                df['UNIT_INDEX_Y'] = df['UNIT_INDEX_Y'].astype('int32')
                df['DEFECT_ID'] = pd.to_numeric(df['DEFECT_ID'], errors='coerce').fillna(-1).astype('int32')

                # Convert string columns to categorical if cardinality is low
                df['DEFECT_TYPE'] = df['DEFECT_TYPE'].str.strip().astype('category')
                df['Verification'] = df['Verification'].astype('category')
                df['SIDE'] = df['SIDE'].astype('category')
                df['SOURCE_FILE'] = df['SOURCE_FILE'].astype('category')

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
                # Pass gap_x and gap_y to BuildUpLayer
                layer_obj = BuildUpLayer(layer_num, side, merged_df, panel_rows, panel_cols, panel_width, panel_height, gap_x, gap_y)
                panel_data.add_layer(layer_obj)

        if panel_data:
            # Avoid sidebar updates in cached function to prevent st.fragment errors
            pass

    else:
        # Avoid sidebar updates in cached function to prevent st.fragment errors
        # st.sidebar.info("No file uploaded. Displaying sample data for 5 layers (all with Front/Back).")
        total_units_x = 2 * panel_cols
        total_units_y = 2 * panel_rows

        # 4. Define a Seed (Set it once before generation)
        np.random.seed(55)

        # 1. Add two more layers (5 total)
        layers_to_generate = [1, 2, 3, 4, 5]

        # 2. Define custom ranges for data points per layer
        # Ranges: 1 (80-100), 2 (200-300), 3 (50-60), 4 (40-80), 5 (100-200)
        layer_counts = {
            1: (80, 101),
            2: (200, 301),
            3: (50, 61),
            4: (40, 81),
            5: (100, 201)
        }

        for layer_num in layers_to_generate:
            # Random False Alarm Rate for this layer (50% - 60%)
            false_alarm_rate = np.random.uniform(0.5, 0.6)

            for side in ['F', 'B']:
                # Random number of points based on layer
                low, high = layer_counts.get(layer_num, (100, 151))
                num_points = np.random.randint(low, high)

                # Generate random indices
                unit_x = np.random.randint(0, total_units_x, size=num_points)
                unit_y = np.random.randint(0, total_units_y, size=num_points)

                # 3. Define Random X and Y coordinates between 30 and 480 mm
                # The prompt requested "30 and 480 mm".
                # These coordinates are meant to represent the "Raw" coordinates relative to the panel.
                # Since the plotting logic uses `plot_x` derived from `UNIT_INDEX`, we must ensure
                # the `X_COORDINATES` and `Y_COORDINATES` columns reflect valid physical positions.
                # If these are raw micron coordinates, 30mm = 30000um.
                # But looking at previous code "30, 48", it seems units were ambiguous.
                # Let's assume millimeters as per the latest request (30-480mm).
                # We also need to map these to UNIT INDICES to ensure consistency with the plotting logic.

                # Panel is 510x510 or 600x600 depending on config.
                # Default Config is 600x600.
                # So 30-480 is a safe inner range.

                rand_x_coords_mm = np.random.uniform(30, 480, size=num_points)
                rand_y_coords_mm = np.random.uniform(30, 480, size=num_points)

                # Convert mm to microns if that's what the system expects downstream?
                # The plotting tooltip divides by 1000 to show mm. So it expects Microns.
                rand_x_coords = rand_x_coords_mm * 1000
                rand_y_coords = rand_y_coords_mm * 1000

                # --- SYNC UNIT INDICES ---
                # The current logic generates random Unit Indices INDEPENDENTLY of X/Y coords.
                # This causes the mismatch: "Why do I see >600mm?".
                # Because Unit Index 7 might map to 600mm, even if X_COORD says 30mm.
                # To fix: Reverse map the random X/Y to Unit Indices.

                # Calculate Quadrant size using Passed Params
                quad_w = panel_width / 2
                quad_h = panel_height / 2
                cell_w = quad_w / panel_cols
                cell_h = quad_h / panel_rows

                # We need to map global X (0-600) to Unit Index X.
                # NOTE: The plotting logic `models.py` uses `UNIT_INDEX_X` to derive `plot_x`.
                # If we want `plot_x` to be 30-480, we must pick `UNIT_INDEX_X` accordingly.
                # Or better: Just generate Unit Indices that correspond to the valid range.

                # 30mm to 480mm range.
                # Max index = panel_cols * 2 (e.g. 14).
                # Max width = 600mm + Gap.
                # 480mm falls roughly at 80% of width.

                # Let's derive indices from the coords.
                # Handle Gap logic:
                # If x > quad_w (300), it's in Q2/Q4.
                # Actually, simply: unit_x = int(x / cell_w).
                # But we must account for the gap if we want to be precise?
                # Models.py adds gap if index >= panel_cols.
                # So here we just map 0-600 linear range to 0-14 indices roughly.

                # Updated logic to use gap_x and gap_y
                unit_x = (rand_x_coords_mm / (panel_width + gap_x)) * (2 * panel_cols)
                unit_y = (rand_y_coords_mm / (panel_height + gap_y)) * (2 * panel_rows)

                unit_x = unit_x.astype(int)
                unit_y = unit_y.astype(int)

                # Clamp
                unit_x = np.clip(unit_x, 0, (2 * panel_cols) - 1)
                unit_y = np.clip(unit_y, 0, (2 * panel_rows) - 1)

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
                    'HAS_VERIFICATION_DATA': [True] * num_points,
                    'X_COORDINATES': rand_x_coords,
                    'Y_COORDINATES': rand_y_coords
                }

                df = pd.DataFrame(defect_data)
                layer_obj = BuildUpLayer(layer_num, side, df, panel_rows, panel_cols, panel_width, panel_height, gap_x, gap_y)
                panel_data.add_layer(layer_obj)

    return panel_data

def get_true_defect_coordinates(
    panel_data: PanelData,
    excluded_layers: Optional[List[int]] = None,
    excluded_defect_types: Optional[List[str]] = None,
    included_sides: Optional[List[str]] = None
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

    # Filter Included Sides
    if included_sides:
        all_layers_df = all_layers_df[all_layers_df['SIDE'].isin(included_sides)]

    if all_layers_df.empty:
        return {}

    # Filter Excluded Defect Types ("What-If" Logic) - Uses Verification Codes
    if excluded_defect_types:
        if 'Verification' in all_layers_df.columns:
            all_layers_df = all_layers_df[~all_layers_df['Verification'].isin(excluded_defect_types)]

    if all_layers_df.empty:
        return {}

    # Filter for True Defects
    safe_values_upper = {v.upper() for v in SAFE_VERIFICATION_VALUES}
    # Verification is already normalized to upper in load_data
    is_true_defect = ~all_layers_df['Verification'].isin(safe_values_upper)
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
def prepare_multi_layer_data(_panel_data: PanelData, panel_uid: str = "") -> pd.DataFrame:
    """
    Aggregates and filters defect data from all layers for the Multi-Layer Defect View.
    """
    if not _panel_data:
        return pd.DataFrame()

    safe_values_upper = {v.upper() for v in SAFE_VERIFICATION_VALUES}

    def true_defect_filter(df):
        if 'Verification' in df.columns:
            # Verification is already normalized to upper in load_data
            return df[~df['Verification'].isin(safe_values_upper)]
        return df

    return _panel_data.get_combined_dataframe(filter_func=true_defect_filter)

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
        # Use a vectorized approach or simplified tooltip for massive data

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

@st.cache_data
def aggregate_stress_data(
    _panel_data: PanelData,
    selected_keys: List[Tuple[int, str]],
    panel_rows: int,
    panel_cols: int,
    panel_uid: str = "",
    verification_filter: Optional[List[str]] = None,
    quadrant_filter: str = "All"
) -> StressMapData:
    """
    Aggregates data for the Cumulative Stress Map using specific (Layer, Side) keys.
    """
    # OPTIMIZATION: Vectorized Aggregation
    dfs_to_agg = []
    for layer_num, side in selected_keys:
        layer = _panel_data.get_layer(layer_num, side)
        if layer and not layer.data.empty:
            dfs_to_agg.append(layer.data)

    if not dfs_to_agg:
        return StressMapData(np.zeros((panel_rows*2, panel_cols*2), int), np.empty((panel_rows*2, panel_cols*2), object), 0, 0)

    combined_df = pd.concat(dfs_to_agg, ignore_index=True)

    # Filter True Defects (Standard)
    safe_values_upper = {v.upper() for v in SAFE_VERIFICATION_VALUES}
    if 'Verification' in combined_df.columns:
        # Verification is already normalized to upper in load_data
        is_true = ~combined_df['Verification'].astype(str).isin(safe_values_upper)
        combined_df = combined_df[is_true]

    # Filter by Specific Selection (if provided)
    if verification_filter and 'Verification' in combined_df.columns and not combined_df.empty:
        combined_df = combined_df[combined_df['Verification'].astype(str).isin(verification_filter)]

    # Filter by Quadrant (if provided)
    if quadrant_filter != "All" and 'QUADRANT' in combined_df.columns and not combined_df.empty:
        combined_df = combined_df[combined_df['QUADRANT'] == quadrant_filter]

    return aggregate_stress_data_from_df(combined_df, panel_rows, panel_cols)

@st.cache_data
def calculate_yield_killers(_panel_data: PanelData, panel_rows: int, panel_cols: int) -> Optional[YieldKillerMetrics]:
    """
    Calculates the 'Yield Killer' KPIs: Worst Layer, Worst Unit, Side Bias.
    """
    if not _panel_data: return None

    safe_values_upper = {v.upper() for v in SAFE_VERIFICATION_VALUES}

    def true_defect_filter(df):
        if 'Verification' in df.columns:
            # Verification is already normalized to upper in load_data
            return df[~df['Verification'].isin(safe_values_upper)]
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
    slice_index: int,
    panel_rows: int,
    panel_cols: int
) -> Tuple[np.ndarray, List[str], List[str]]:
    """
    Constructs the 2D cross-section matrix for Root Cause Analysis based on a single slice.

    slice_axis: 'Y' (By Row) or 'X' (By Column)
    slice_index: The index of the row or column to slice.
    """
    sorted_layers = _panel_data.get_all_layer_nums()
    num_layers = len(sorted_layers)
    if num_layers == 0:
        return np.zeros((0,0)), [], []

    total_cols = panel_cols * 2
    total_rows = panel_rows * 2

    # If Slicing by Row (Y), we show all Columns (X) -> width = total_cols
    # If Slicing by Column (X), we show all Rows (Y) -> width = total_rows

    if slice_axis == 'Y':
        width_dim = total_cols
        axis_labels = [str(i) for i in range(width_dim)]
    else:
        width_dim = total_rows
        axis_labels = [str(i) for i in range(width_dim)]

    matrix = np.zeros((num_layers, width_dim), dtype=int)
    layer_labels = [f"L{num}" for num in sorted_layers]

    safe_values_upper = {v.upper() for v in SAFE_VERIFICATION_VALUES}

    for i, layer_num in enumerate(sorted_layers):
        sides = _panel_data._layers[layer_num] # Direct access to dict for now
        for side, layer_obj in sides.items():
            df = layer_obj.data
            if df.empty: continue

            # Optimization: Avoid full copy
            if 'Verification' in df.columns:
                is_true = ~df['Verification'].isin(safe_values_upper)
                df_copy = df[is_true].copy() # Filter first then copy
            else:
                df_copy = df.copy()

            if df_copy.empty: continue

            # Filter by Slice
            if slice_axis == 'Y':
                # Fixed Y, variable X
                relevant_defects = df_copy[df_copy['UNIT_INDEX_Y'] == slice_index]
            else:
                # Fixed X, variable Y
                relevant_defects = df_copy[df_copy['UNIT_INDEX_X'] == slice_index]

            if relevant_defects.empty: continue

            # Aggregate
            if slice_axis == 'Y':
                # Group by X to fill columns of matrix
                counts = relevant_defects.groupby('UNIT_INDEX_X').size()
                for x_idx, count in counts.items():
                    if 0 <= x_idx < width_dim:
                        matrix[i, int(x_idx)] += count
            else:
                # Group by Y to fill columns of matrix (which represent Rows in the plot)
                counts = relevant_defects.groupby('UNIT_INDEX_Y').size()
                for y_idx, count in counts.items():
                    if 0 <= y_idx < width_dim:
                        matrix[i, int(y_idx)] += count

    return matrix, layer_labels, axis_labels
