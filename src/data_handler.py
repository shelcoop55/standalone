"""
Data Handling Module.
This version calculates defect locations based on a true-to-scale simulation
of a fixed-size 510x510mm physical panel.
"""
import streamlit as st
import pandas as pd
import numpy as np
from typing import List
from io import BytesIO

# Import constants from the configuration file
from .config import PANEL_WIDTH, PANEL_HEIGHT, GAP_SIZE

# --- DERIVED PHYSICAL CONSTANTS ---
# These constants are calculated from the primary dimensions in config.py
QUADRANT_WIDTH = PANEL_WIDTH / 2
QUADRANT_HEIGHT = PANEL_HEIGHT / 2

@st.cache_data
def load_data(
    uploaded_files: List[BytesIO],
    panel_rows: int,
    panel_cols: int,
) -> pd.DataFrame:
    """
    Loads defect data and calculates the true physical plot coordinates (plot_x, plot_y)
    for each defect based on a 510x510mm panel simulation.
    """
    if uploaded_files:
        all_dfs = []
        for uploaded_file in uploaded_files:
            try:
                # Read only the sheet named "Defect"
                df = pd.read_excel(uploaded_file, sheet_name='Defect', engine='openpyxl')
                df['SOURCE_FILE'] = uploaded_file.name
                all_dfs.append(df)
            except ValueError:
                # This error occurs if the "Defect" sheet is not found
                st.error(f"Error in '{uploaded_file.name}': A sheet named 'Defect' was not found. Please ensure the file contains a 'Defect' sheet.")
                continue
            except Exception as e:
                st.error(f"An unexpected error occurred while reading '{uploaded_file.name}': {e}")
                continue

        if not all_dfs:
            st.error("No valid data could be read from the uploaded files.")
            return pd.DataFrame()

        df = pd.concat(all_dfs, ignore_index=True)
        st.sidebar.success(f"{len(uploaded_files)} file(s) loaded successfully!")
        
        # Handle the new 'Verification' column for backward compatibility
        if 'Verification' not in df.columns:
            df['Verification'] = 'T'
        else:
            # Clean up the verification column, filling NaNs with 'T'
            df['Verification'] = df['Verification'].astype(str).fillna('T').str.strip()

        required_columns = ['DEFECT_ID', 'DEFECT_TYPE', 'UNIT_INDEX_X', 'UNIT_INDEX_Y']
        if not all(col in df.columns for col in required_columns):
            st.error(f"One or more uploaded files are missing required columns: {required_columns}")
            return pd.DataFrame()
            
        df = df[required_columns + ['Verification', 'SOURCE_FILE']]
        df.dropna(subset=required_columns, inplace=True)
        df['UNIT_INDEX_X'] = df['UNIT_INDEX_X'].astype(int)
        df['UNIT_INDEX_Y'] = df['UNIT_INDEX_Y'].astype(int)
        df['DEFECT_TYPE'] = df['DEFECT_TYPE'].str.strip()
        
    else:
        # Fallback Path: Generate sample data with UNIT_INDEX coordinates
        st.sidebar.info("No file uploaded. Displaying sample data.")
        total_units_x = 2 * panel_cols
        total_units_y = 2 * panel_rows
        number_of_defects = 150
        defect_data = {
            'DEFECT_ID': range(1001, 1001 + number_of_defects),
            'UNIT_INDEX_X': np.random.randint(0, total_units_x, size=number_of_defects),
            'UNIT_INDEX_Y': np.random.randint(0, total_units_y, size=number_of_defects),
            'DEFECT_TYPE': np.random.choice([ 'Nick', 'Short', 'Missing Feature', 'Cut', 'Fine Short', 'Pad Violation', 'Island', 'Cut/Short', 'Nick/Protrusion' ], size=number_of_defects),
            'Verification': np.random.choice(['T', 'F', 'TA'], size=number_of_defects, p=[0.7, 0.15, 0.15]),
            'SOURCE_FILE': ['Sample Data'] * number_of_defects
        }
        df = pd.DataFrame(defect_data)

    # --- SIMULATION LOGIC ---

    # 1. Assign Quadrant based on UNIT_INDEX and user-defined grid resolution
    conditions = [
        (df['UNIT_INDEX_X'] < panel_cols) & (df['UNIT_INDEX_Y'] < panel_rows),    # Q1 (Bottom-Left)
        (df['UNIT_INDEX_X'] >= panel_cols) & (df['UNIT_INDEX_Y'] < panel_rows),   # Q2 (Bottom-Right)
        (df['UNIT_INDEX_X'] < panel_cols) & (df['UNIT_INDEX_Y'] >= panel_rows),   # Q3 (Top-Left)
        (df['UNIT_INDEX_X'] >= panel_cols) & (df['UNIT_INDEX_Y'] >= panel_rows)    # Q4 (Top-Right)
    ]
    choices = ['Q1', 'Q2', 'Q3', 'Q4']
    df['QUADRANT'] = np.select(conditions, choices, default='Other')
    
    # 2. Calculate the physical size (in mm) of a single grid cell
    cell_width = QUADRANT_WIDTH / panel_cols
    cell_height = QUADRANT_HEIGHT / panel_rows

    # 3. Translate UNIT_INDEX into physical coordinates
    
    # Find the local unit index (e.g., the 2nd column within its own quadrant)
    local_index_x = df['UNIT_INDEX_X'] % panel_cols
    local_index_y = df['UNIT_INDEX_Y'] % panel_rows

    # Calculate the base physical position (bottom-left corner of the cell in mm)
    plot_x_base = local_index_x * cell_width
    plot_y_base = local_index_y * cell_height

    # Determine the physical offset (in mm) for the quadrant itself
    x_offset = np.where(df['UNIT_INDEX_X'] >= panel_cols, QUADRANT_WIDTH + GAP_SIZE, 0)
    y_offset = np.where(df['UNIT_INDEX_Y'] >= panel_rows, QUADRANT_HEIGHT + GAP_SIZE, 0)

    # 4. Calculate the final plot coordinate with scaled jitter
    # The jitter places the defect randomly *inside* its cell, not just on the corner.
    jitter_x = np.random.rand(len(df)) * cell_width * 0.8 + (cell_width * 0.1)
    jitter_y = np.random.rand(len(df)) * cell_height * 0.8 + (cell_height * 0.1)

    df['plot_x'] = plot_x_base + x_offset + jitter_x
    df['plot_y'] = plot_y_base + y_offset + jitter_y
    
    return df