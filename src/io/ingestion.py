import streamlit as st
import pandas as pd
import re
import logging
from typing import List, Any, Dict, Optional
from dataclasses import dataclass, field
from src.core.models import PanelData, BuildUpLayer
from src.core.config import FILENAME_PATTERN, ALLOWED_INGESTION_COLUMNS
from src.io.validation import validate_schema
from src.io.sample_generator import generate_sample_data
from src.utils.telemetry import track_performance, PerformanceMonitor, get_dataframe_memory_usage

logger = logging.getLogger(__name__)

@dataclass
class IngestionResult:
    """
    Result of the data ingestion process.
    Contains the constructed PanelData object and lists of any errors or warnings.
    """
    panel_data: Optional[PanelData] = None
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

@st.cache_resource(show_spinner="Loading Data...")
@track_performance("Data Ingestion (Total)")
def load_panel_data(
    uploaded_files: List[Any],
    panel_rows: int,
    panel_cols: int,
    panel_width: float,
    panel_height: float,
    gap_x: float,
    gap_y: float
) -> IngestionResult:
    """
    Loads defect data from multiple build-up layer files.
    Returns an IngestionResult containing the PanelData and any errors/warnings.
    """
    result = IngestionResult()
    
    # 1. Fallback to Sample Data if no files provided
    if not uploaded_files:
        panel_data = generate_sample_data(panel_rows, panel_cols, panel_width, panel_height, gap_x, gap_y)
        result.panel_data = panel_data
        return result

    panel_data = PanelData()
    temp_data: Dict[int, Dict[str, List[pd.DataFrame]]] = {}
    
    # Track which files were successfully processed
    processed_count = 0

    for uploaded_file in uploaded_files:
        file_name = uploaded_file.name
        match = re.match(FILENAME_PATTERN, file_name, re.IGNORECASE)

        if not match:
            msg = f"Skipping file: '{file_name}'. Name must follow 'BU-XXF' or 'BU-XXB' format."
            result.warnings.append(msg)
            logger.warning(msg)
            continue

        layer_num, side = int(match.group(1)), match.group(2).upper()

        try:
            # Try calamine first (faster); fall back to openpyxl if engine unavailable
            try:
                df = pd.read_excel(uploaded_file, sheet_name='Defects', engine='calamine')
            except Exception:
                if hasattr(uploaded_file, 'seek'):
                    uploaded_file.seek(0)
                df = pd.read_excel(uploaded_file, sheet_name='Defects', engine='openpyxl')

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

            # Measure pre-optimization memory
            mem_before = get_dataframe_memory_usage(df)

            # --- OPTIMIZATION: Column Pruning ---
            # Drop unnecessary columns to save memory.
            # Keep only columns essential for logic and plotting.
            allowed_cols = ALLOWED_INGESTION_COLUMNS
            
            # Intersect with existing columns to avoid KeyErrors
            cols_to_keep = [c for c in df.columns if c in allowed_cols]
            df = df[cols_to_keep]

            # Measure post-optimization memory
            mem_after = get_dataframe_memory_usage(df)
            PerformanceMonitor.log_event(
                f"Pruning ({file_name})",
                0.0,
                details=f"Reduced from {mem_before:.2f}MB to {mem_after:.2f}MB"
            )

            if layer_num not in temp_data: temp_data[layer_num] = {}
            if side not in temp_data[layer_num]: temp_data[layer_num][side] = []
            temp_data[layer_num][side].append(df)
            processed_count += 1

        except ValueError as e:
            msg = f"Validation Error in '{file_name}': {e}"
            result.errors.append(msg)
            logger.error(msg)
            continue
        except (KeyError, AttributeError, TypeError, OSError) as e:
            msg = f"Error loading '{file_name}': {e}"
            result.errors.append(msg)
            logger.error(msg)
            continue
        except Exception as e:
            msg = f"Unexpected error loading '{file_name}': {e}"
            result.errors.append(msg)
            logger.exception(f"Critical error loading {file_name}")
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

    result.panel_data = panel_data
    return result
