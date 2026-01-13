"""
Data Handling Module.
This version calculates defect locations based on a true-to-scale simulation
of a fixed-size 510x510mm physical panel.
"""
import streamlit as st
import pandas as pd
import numpy as np
import re
from typing import List, Dict, Set, Tuple
from io import BytesIO

# Import constants from the configuration file
from .config import PANEL_WIDTH, PANEL_HEIGHT, GAP_SIZE, SAFE_VERIFICATION_VALUES

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


@st.cache_data
def load_data(
    uploaded_files: List[BytesIO],
    panel_rows: int,
    panel_cols: int,
) -> Dict[int, Dict[str, pd.DataFrame]]:
    """
    Loads defect data from multiple build-up layer files, validates filenames
    (e.g., BU-01F..., BU-01B...), and processes each layer's data.
    Returns a nested dictionary mapping layer numbers to sides ('F' or 'B')
    to their corresponding DataFrames.
    """
    layer_data = {}

    if uploaded_files:
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

                if layer_num not in layer_data: layer_data[layer_num] = {}
                if side not in layer_data[layer_num]: layer_data[layer_num][side] = []

                layer_data[layer_num][side].append(df)

            except ValueError:
                st.error(f"Error in '{file_name}': A sheet named 'Defects' was not found.")
                continue
            except Exception as e:
                st.error(f"An unexpected error occurred while reading '{file_name}': {e}")
                continue
        
        # Consolidate dataframes for each layer/side
        for layer_num, sides in layer_data.items():
            for side, dfs in sides.items():
                layer_data[layer_num][side] = _add_plotting_coordinates(
                    pd.concat(dfs, ignore_index=True), panel_rows, panel_cols
                )

        if layer_data:
            st.sidebar.success(f"{len(layer_data)} layer(s) loaded successfully!")

    else:
        st.sidebar.info("No file uploaded. Displaying sample data for 3 layers (all with Front/Back).")
        total_units_x = 2 * panel_cols
        total_units_y = 2 * panel_rows
        layer_data = {}

        # 3 Layers
        layers_to_generate = [1, 2, 3]

        for layer_num in layers_to_generate:
            layer_data[layer_num] = {}

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
                # Ensure PHYSICAL_X is present in sample data
                df['PHYSICAL_X'] = df['UNIT_INDEX_X']
                if side == 'B':
                    total_width_units = 2 * panel_cols
                    df['PHYSICAL_X'] = (total_width_units - 1) - df['UNIT_INDEX_X']

                layer_data[layer_num][side] = _add_plotting_coordinates(df, panel_rows, panel_cols)

    return layer_data


def _add_plotting_coordinates(df: pd.DataFrame, panel_rows: int, panel_cols: int) -> pd.DataFrame:
    """
    Adds plotting coordinates to a DataFrame.
    Calculates both Raw coordinates (for Individual View) and Physical coordinates (for Heatmaps/Yield).
    """
    if df.empty:
        return df

    cell_width = QUADRANT_WIDTH / panel_cols
    cell_height = QUADRANT_HEIGHT / panel_rows

    # --- 1. RAW COORDINATES (Based on UNIT_INDEX_X) ---
    # Used for Individual Layer Map (Back side unflipped)

    # Calculate Raw Quadrant
    conditions_raw = [
        (df['UNIT_INDEX_X'] < panel_cols) & (df['UNIT_INDEX_Y'] < panel_rows),
        (df['UNIT_INDEX_X'] >= panel_cols) & (df['UNIT_INDEX_Y'] < panel_rows),
        (df['UNIT_INDEX_X'] < panel_cols) & (df['UNIT_INDEX_Y'] >= panel_rows),
        (df['UNIT_INDEX_X'] >= panel_cols) & (df['UNIT_INDEX_Y'] >= panel_rows)
    ]
    choices = ['Q1', 'Q2', 'Q3', 'Q4']
    df['QUADRANT'] = np.select(conditions_raw, choices, default='Other')

    # Calculate Raw Plotting Coordinates
    local_index_x_raw = df['UNIT_INDEX_X'] % panel_cols
    local_index_y = df['UNIT_INDEX_Y'] % panel_rows # Y is always consistent

    plot_x_base_raw = local_index_x_raw * cell_width
    plot_y_base = local_index_y * cell_height

    x_offset_raw = np.where(df['UNIT_INDEX_X'] >= panel_cols, QUADRANT_WIDTH + GAP_SIZE, 0)
    y_offset = np.where(df['UNIT_INDEX_Y'] >= panel_rows, QUADRANT_HEIGHT + GAP_SIZE, 0)

    # Common Jitter
    jitter_x = np.random.rand(len(df)) * cell_width * 0.8 + (cell_width * 0.1)
    jitter_y = np.random.rand(len(df)) * cell_height * 0.8 + (cell_height * 0.1)

    df['plot_x'] = plot_x_base_raw + x_offset_raw + jitter_x
    df['plot_y'] = plot_y_base + y_offset + jitter_y


    # --- 2. PHYSICAL COORDINATES (Based on PHYSICAL_X) ---
    # Used for Multi-Layer Map, Still Alive Map, Heatmaps (Back side flipped)

    if 'PHYSICAL_X' not in df.columns:
         df['PHYSICAL_X'] = df['UNIT_INDEX_X']

    # Calculate Physical Quadrant
    conditions_phys = [
        (df['PHYSICAL_X'] < panel_cols) & (df['UNIT_INDEX_Y'] < panel_rows),
        (df['PHYSICAL_X'] >= panel_cols) & (df['UNIT_INDEX_Y'] < panel_rows),
        (df['PHYSICAL_X'] < panel_cols) & (df['UNIT_INDEX_Y'] >= panel_rows),
        (df['PHYSICAL_X'] >= panel_cols) & (df['UNIT_INDEX_Y'] >= panel_rows)
    ]
    df['PHYSICAL_QUADRANT'] = np.select(conditions_phys, choices, default='Other')

    # Calculate Physical Plotting Coordinates
    local_index_x_phys = df['PHYSICAL_X'] % panel_cols
    plot_x_base_phys = local_index_x_phys * cell_width
    x_offset_phys = np.where(df['PHYSICAL_X'] >= panel_cols, QUADRANT_WIDTH + GAP_SIZE, 0)

    # We re-use jitter_x so that the same defect doesn't jump around randomly between views
    df['physical_plot_x'] = plot_x_base_phys + x_offset_phys + jitter_x
    
    return df

def get_true_defect_coordinates(layer_data: Dict[int, Dict[str, pd.DataFrame]]) -> Set[Tuple[int, int]]:
    """
    Aggregates all "True" defects from all layers and sides to find unique
    defective cell coordinates for the Still Alive map.

    Updated Logic:
    A "True Defect" is any defect whose Verification value is NOT in the SAFE_VERIFICATION_VALUES list.
    """
    if not isinstance(layer_data, dict) or not layer_data:
        return set()

    all_dfs = []
    for layer, sides in layer_data.items():
        for side, df in sides.items():
            all_dfs.append(df)

    if not all_dfs:
        return set()

    all_layers_df = pd.concat(all_dfs, ignore_index=True)

    if all_layers_df.empty or 'Verification' not in all_layers_df.columns:
        return set()

    # Filter for True Defects: Value NOT in SAFE_VERIFICATION_VALUES (case-insensitive)
    # We use upper() for comparison
    safe_values_upper = {v.upper() for v in SAFE_VERIFICATION_VALUES}

    # Identify true defects
    is_true_defect = ~all_layers_df['Verification'].str.upper().isin(safe_values_upper)
    true_defects_df = all_layers_df[is_true_defect]

    if true_defects_df.empty:
        return set()

    # Ensure PHYSICAL_X exists (fallback for tests or partial data)
    if 'PHYSICAL_X' not in true_defects_df.columns:
        true_defects_df['PHYSICAL_X'] = true_defects_df['UNIT_INDEX_X']

    # USE PHYSICAL COORDINATES for unique defect location
    defect_coords_df = true_defects_df[['PHYSICAL_X', 'UNIT_INDEX_Y']].drop_duplicates()

    # Rename for consistency in output if needed, but set expects tuples
    return set(map(tuple, defect_coords_df.to_numpy()))

def prepare_multi_layer_data(layer_data: Dict[int, Dict[str, pd.DataFrame]]) -> pd.DataFrame:
    """
    Aggregates and filters defect data from all layers for the Multi-Layer Defect View.

    Logic:
    1. Iterates through all layers and sides in layer_data.
    2. Filters out 'Safe' verification values (False Alarms).
    3. Adds a 'Layer_Label' column (e.g., 'Layer 1 (Front)').
    4. Adds a 'LAYER_NUM' column (int) for color mapping.
    5. Returns a single combined DataFrame.
    """
    combined_data = []
    safe_values_upper = {v.upper() for v in SAFE_VERIFICATION_VALUES}

    if not layer_data:
        return pd.DataFrame()

    for layer_num, sides in layer_data.items():
        for side, df in sides.items():
            if df.empty: continue

            # Create a copy to avoid SettingWithCopy warnings
            df_copy = df.copy()

            # Filter for True Defects
            if 'Verification' in df_copy.columns:
                is_true_defect = ~df_copy['Verification'].str.upper().isin(safe_values_upper)
                df_copy = df_copy[is_true_defect]

            if df_copy.empty: continue

            # Add Layer Label and Layer Num
            side_name = "Front" if side == 'F' else "Back"
            df_copy['Layer_Label'] = f"Layer {layer_num} ({side_name})"
            df_copy['LAYER_NUM'] = layer_num

            combined_data.append(df_copy)

    if combined_data:
        return pd.concat(combined_data, ignore_index=True)
    return pd.DataFrame()
