import streamlit as st
import pandas as pd
import re
from typing import List, Any, Dict
from src.core.models import PanelData, BuildUpLayer
from src.core.config import FILENAME_PATTERN
from src.io.validation import validate_schema
from src.io.sample_generator import generate_sample_data

@st.cache_resource(show_spinner="Loading Data...")
def load_panel_data(
    uploaded_files: List[Any],
    panel_rows: int,
    panel_cols: int,
    panel_width: float,
    panel_height: float,
    gap_x: float,
    gap_y: float
) -> PanelData:
    """
    Loads defect data from multiple build-up layer files.
    Uses st.cache_resource to store the immutable PanelData object as a singleton.
    """
    # 1. Fallback to Sample Data
    if not uploaded_files:
        return generate_sample_data(panel_rows, panel_cols, panel_width, panel_height, gap_x, gap_y)

    panel_data = PanelData()
    temp_data: Dict[int, Dict[str, List[pd.DataFrame]]] = {}

    for uploaded_file in uploaded_files:
        file_name = uploaded_file.name
        match = re.match(FILENAME_PATTERN, file_name, re.IGNORECASE)

        if not match:
            st.warning(f"Skipping file: '{file_name}'. Name must follow 'BU-XXF' or 'BU-XXB' format.")
            continue

        layer_num, side = int(match.group(1)), match.group(2).upper()

        try:
            # OPTIMIZATION: Use calamine engine for faster loading
            # Note: uploaded_file is a BytesIO-like object from Streamlit
            df = pd.read_excel(uploaded_file, sheet_name='Defects', engine='calamine')

            df.rename(columns={'VERIFICATION': 'Verification'}, inplace=True)
            df['SOURCE_FILE'] = file_name
            df['SIDE'] = side

            # --- Validation Layer ---
            # This handles column check, type conversion, and dropping bad rows
            df = validate_schema(df, file_name)

            # --- Post-Validation Enrichment ---
            # Determine HAS_VERIFICATION_DATA based on if 'Verification' was present/filled
            has_verif = 'Verification' in df.columns
            if not has_verif:
                 df['Verification'] = 'Under Verification'

            df['HAS_VERIFICATION_DATA'] = has_verif

            # --- OPTIMIZATION: Column Pruning ---
            # Drop unnecessary columns to save memory.
            # Keep only columns essential for logic and plotting.
            allowed_cols = {
                'DEFECT_TYPE', 'UNIT_INDEX_X', 'UNIT_INDEX_Y',
                'Verification', 'X_COORDINATES', 'Y_COORDINATES',
                'DEFECT_ID', 'SOURCE_FILE', 'SIDE', 'HAS_VERIFICATION_DATA',
                # Ensure downstream compatibility and preserve useful metadata
                'QUADRANT', 'Description', 'Comments', 'Remark'
            }
            # Intersect with existing columns to avoid KeyErrors
            cols_to_keep = [c for c in df.columns if c in allowed_cols]
            df = df[cols_to_keep]

            if layer_num not in temp_data: temp_data[layer_num] = {}
            if side not in temp_data[layer_num]: temp_data[layer_num][side] = []
            temp_data[layer_num][side].append(df)

        except Exception as e:
            st.error(f"Error loading '{file_name}': {e}")
            continue

    # Build PanelData
    for layer_num, sides in temp_data.items():
        for side, dfs in sides.items():
            merged_df = pd.concat(dfs, ignore_index=True)
            layer_obj = BuildUpLayer(
                layer_num, side, merged_df,
                panel_rows, panel_cols, panel_width, panel_height, gap_x, gap_y
            )
            panel_data.add_layer(layer_obj)

    return panel_data
