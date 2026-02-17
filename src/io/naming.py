from datetime import datetime
import re
from typing import Optional, Any, Dict

def get_bu_name_from_filename(filename: str) -> str:
    """
    Extracts the 'BU-XX' part from a filename.
    Returns the original filename if no match is found.
    """
    match = re.search(r"(BU-\d{2})", filename, re.IGNORECASE)
    if match:
        return match.group(1).upper()

    # Fallback for sample data
    match = re.search(r"Sample Data Layer (\d+)", filename)
    if match:
        return f"BU-{int(match.group(1)):02d}"

    return filename

def generate_standard_filename(
    prefix: str,
    selected_layer: Optional[int] = None,
    layer_data: Any = None,
    analysis_params: Dict = {},
    extension: str = "zip",
    explicit_lot_number: str = "",     # If passed directly
    explicit_process_comment: str = "" # If passed directly
) -> str:
    """
    Generates a standardized filename: [Prefix]_[LotNumber]_[ProcessRequest]_[SourceFile]_[Date].ext
    Example: Defect_Analysis_Package_Lot12345_EtchRun1_WaferMapData_20231026.zip
    """
    parts = [prefix]

    # --- 1. Lot Number (Priority) ---
    lot_num = explicit_lot_number or analysis_params.get('lot_number', '').strip()
    if lot_num:
        parts.append(lot_num)

    # --- 2. Process Request / Comment ---
    proc_comment = explicit_process_comment or analysis_params.get('process_comment', '').strip()
    if proc_comment:
        parts.append(proc_comment)

    # --- 3. Source File Name (Intuitive Context) ---
    source_name = "Multi_Layer" # Default if no specific file found
    
    # Try to extract from provided layer_data
    if selected_layer is not None and layer_data:
        try:
            # Accessing via standard dict access if possible.
            # In manager.py: self.store.layer_data[layer_id] works.
            if hasattr(layer_data, '__getitem__'):
                 layer_info = layer_data[selected_layer]
                 # Try to get first side safely if it's a dict
                 if isinstance(layer_info, dict) and layer_info:
                     first_side = next(iter(layer_info))
                     layer_obj = layer_info[first_side]

                     # Handle if it is a DataFrame directly or an object
                     src_file = "Unknown"
                     if hasattr(layer_obj, 'columns') and 'SOURCE_FILE' in layer_obj.columns:
                          src_file = str(layer_obj['SOURCE_FILE'].iloc[0])
                     elif hasattr(layer_obj, 'source_file'):
                          src_file = layer_obj.source_file
                     elif isinstance(layer_obj, dict) and 'SOURCE_FILE' in layer_obj:
                          src_file = layer_obj['SOURCE_FILE']

                     # Extract base filename without extension
                     import os
                     base = os.path.basename(src_file)
                     name_only, _ = os.path.splitext(base)
                     if name_only and name_only != "Unknown":
                         source_name = name_only

        except Exception:
            pass # Keep default

    parts.append(source_name)

    # --- 4. Date Stamp ---
    date_str = datetime.now().strftime("%Y%m%d")
    parts.append(date_str)

    # Join and Sanitize
    full_name = "_".join(parts)
    
    # Sanitize: Allow alphanumeric, underscores, hyphens, periods.
    # Replace spaces with underscores.
    full_name = full_name.replace(" ", "_")
    safe_name = "".join([c if c.isalnum() or c in "._-" else "_" for c in full_name])

    # Remove consecutive underscores if sanitization caused them
    safe_name = re.sub(r"_+", "_", safe_name)

    return f"{safe_name}.{extension}"
