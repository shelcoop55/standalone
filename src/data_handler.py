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
                # 1. If 'Verification' column is missing, create it and mark as "Under Verification".
                # 2. If it exists, fill NaN/Blanks with 'N' (Safe).
                if 'Verification' not in df.columns:
                    df['Verification'] = 'Under Verification'
                else:
                    df['Verification'] = df['Verification'].fillna('N').astype(str).str.strip()
                    # Also handle empty strings that might result from stripping
                    df['Verification'] = df['Verification'].replace('', 'N')

                required_columns = ['DEFECT_ID', 'DEFECT_TYPE', 'UNIT_INDEX_X', 'UNIT_INDEX_Y']
                if not all(col in df.columns for col in required_columns):
                    st.error(f"File '{file_name}' is missing required columns: {required_columns}. It has been skipped.")
                    continue

                df.dropna(subset=required_columns, inplace=True)
                for col in ['UNIT_INDEX_X', 'UNIT_INDEX_Y']: df[col] = df[col].astype(int)
                df['DEFECT_TYPE'] = df['DEFECT_TYPE'].str.strip()

                # --- BACK SIDE COORDINATE FLIP ---
                # Back side data is physically mirrored horizontally relative to the front.
                # Transform coordinates to align with the Front-side view (0,0 is top-left).
                # New_X = (Total_Panel_Width - 1) - Original_X
                if side == 'B':
                    total_width_units = 2 * panel_cols
                    df['UNIT_INDEX_X'] = (total_width_units - 1) - df['UNIT_INDEX_X']

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

        # Define properties for sample layers, including sides for all layers
        sample_layers = {
            1: {
                'F': {'num_defects': 75, 'defect_types': ['Nick', 'Short', 'Cut']},
                'B': {'num_defects': 30, 'defect_types': ['Backside Nick', 'Handling Scratch']}
            },
            2: {
                'F': {'num_defects': 120, 'defect_types': ['Fine Short', 'Pad Violation', 'Island', 'Short']},
                'B': {'num_defects': 40, 'defect_types': ['Backside Scratch', 'Contamination']}
            },
            3: {
                'F': {'num_defects': 50, 'defect_types': ['Missing Feature', 'Cut/Short', 'Nick/Protrusion']},
                'B': {'num_defects': 25, 'defect_types': ['Backside Residue', 'Epoxy Smear']}
            }
        }

        for layer_num, sides in sample_layers.items():
            layer_data[layer_num] = {}
            for side, props in sides.items():
                defect_data = {
                    'DEFECT_ID': range(layer_num * 1000 + (0 if side == 'F' else 500), layer_num * 1000 + (0 if side == 'F' else 500) + props['num_defects']),
                    'UNIT_INDEX_X': np.random.randint(0, total_units_x, size=props['num_defects']),
                    'UNIT_INDEX_Y': np.random.randint(0, total_units_y, size=props['num_defects']),
                    'DEFECT_TYPE': np.random.choice(props['defect_types'], size=props['num_defects']),
                    'Verification': np.random.choice(['T', 'F', 'TA'], size=props['num_defects'], p=[0.7, 0.15, 0.15]),
                    'SOURCE_FILE': [f'Sample Data Layer {layer_num}{side}'] * props['num_defects'],
                    'SIDE': side
                }
                df = pd.DataFrame(defect_data)
                layer_data[layer_num][side] = _add_plotting_coordinates(df, panel_rows, panel_cols)

    return layer_data


def _add_plotting_coordinates(df: pd.DataFrame, panel_rows: int, panel_cols: int) -> pd.DataFrame:
    """Adds QUADRANT and plot_x, plot_y coordinates to a DataFrame."""
    if df.empty:
        return df

    # Calculate quadrant
    conditions = [
        (df['UNIT_INDEX_X'] < panel_cols) & (df['UNIT_INDEX_Y'] < panel_rows),
        (df['UNIT_INDEX_X'] >= panel_cols) & (df['UNIT_INDEX_Y'] < panel_rows),
        (df['UNIT_INDEX_X'] < panel_cols) & (df['UNIT_INDEX_Y'] >= panel_rows),
        (df['UNIT_INDEX_X'] >= panel_cols) & (df['UNIT_INDEX_Y'] >= panel_rows)
    ]
    choices = ['Q1', 'Q2', 'Q3', 'Q4']
    df['QUADRANT'] = np.select(conditions, choices, default='Other')

    # Calculate plotting coordinates
    cell_width = QUADRANT_WIDTH / panel_cols
    cell_height = QUADRANT_HEIGHT / panel_rows

    local_index_x = df['UNIT_INDEX_X'] % panel_cols
    local_index_y = df['UNIT_INDEX_Y'] % panel_rows

    plot_x_base = local_index_x * cell_width
    plot_y_base = local_index_y * cell_height

    x_offset = np.where(df['UNIT_INDEX_X'] >= panel_cols, QUADRANT_WIDTH + GAP_SIZE, 0)
    y_offset = np.where(df['UNIT_INDEX_Y'] >= panel_rows, QUADRANT_HEIGHT + GAP_SIZE, 0)

    jitter_x = np.random.rand(len(df)) * cell_width * 0.8 + (cell_width * 0.1)
    jitter_y = np.random.rand(len(df)) * cell_height * 0.8 + (cell_height * 0.1)

    df['plot_x'] = plot_x_base + x_offset + jitter_x
    df['plot_y'] = plot_y_base + y_offset + jitter_y
    
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

    defect_coords_df = true_defects_df[['UNIT_INDEX_X', 'UNIT_INDEX_Y']].drop_duplicates()

    return set(map(tuple, defect_coords_df.to_numpy()))
