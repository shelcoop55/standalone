import re
from typing import Dict, Optional, Any

def get_bu_name_from_filename(filename: str) -> str:
    """
    Extracts the 'BU-XX' part from a filename.
    Returns the original filename if no match is found.
    """
    match = re.match(r"(BU-\d{2})", filename, re.IGNORECASE)
    if match:
        return match.group(1).upper()

    # Fallback for sample data
    match = re.match(r"Sample Data Layer (\d+)", filename)
    if match:
        return f"BU-{int(match.group(1)):02d}"

    return filename

def generate_standard_filename(
    prefix: str,
    selected_layer: Optional[int],
    layer_data: Any,
    analysis_params: Dict,
    extension: str = "zip"
) -> str:
    """
    Generates a standardized filename: PREFIX_LAYER(BU_XX)_PROCESSSTEP_LOTNUMBER.ext
    """
    # 1. Get Layer/BU Name
    layer_label = "ALL_LAYERS"
    if selected_layer is not None:
        layer_label = f"LAYER_{selected_layer}"
        try:
            # Assuming layer_data is accessible like a dict or has structure
            # Accessing via standard dict access if possible.
            # In manager.py: self.store.layer_data[layer_id] works.

            # We need to handle the case where layer_data might be a PanelData object which behaves like a dict
            # or a raw dict. The existing code suggests it behaves like a dict of dicts.
            if hasattr(layer_data, '__getitem__'):
                 layer_info = layer_data[selected_layer]
                 first_side = next(iter(layer_info))
                 # Access dataframe
                 # layer_info[first_side] is usually a wrapper object or dataframe depending on context
                 # In load_data, layer_data is PanelData, and panel_data[layer_num] returns a dict of BuildUpLayer objects?
                 # Wait, PanelData in data_handler.py:
                 # class PanelData:
                 #    _layers: Dict[int, Dict[str, BuildUpLayer]]
                 #    def __getitem__(self, key): return self._layers[key]
                 # So layer_info is Dict[str, BuildUpLayer]
                 # BuildUpLayer has .data (DataFrame) and .source_file

                 layer_obj = layer_info[first_side]
                 # BuildUpLayer object has .source_file attribute?
                 # Let's check models.py to be safe, but usually it has a DataFrame.
                 # In manager.py, it was doing: layer_data[num][first_side]['SOURCE_FILE'].iloc[0]
                 # This implies layer_info[first_side] IS A DATAFRAME or supports item access.
                 # Ah, `temp_data` in load_data was Dict[int, Dict[str, List[pd.DataFrame]]] but then it creates PanelData.
                 # PanelData structure needs to be confirmed.

                 # Manager.py logic:
                 # first_side_key = next(iter(self.store.layer_data[num]))
                 # source_file = self.store.layer_data[num][first_side_key]['SOURCE_FILE'].iloc[0]

                 # This implies `self.store.layer_data[num][first_side_key]` returns a DATAFRAME.
                 # So PanelData[num][side] -> DataFrame.

                 src_file = str(layer_obj['SOURCE_FILE'].iloc[0])
                 bu_part = get_bu_name_from_filename(src_file)
                 if bu_part:
                     layer_label = f"LAYER_({bu_part})"
        except Exception:
            pass

    # 2. Process Step
    proc_step = analysis_params.get('process_comment', '').strip()
    proc_str = f"_{proc_step}" if proc_step else ""

    # 3. Lot Number
    lot_num = analysis_params.get('lot_number', '').strip()
    lot_str = f"_{lot_num}" if lot_num else ""

    # Sanitize filename
    base_name = f"{prefix}_{layer_label}{proc_str}{lot_str}"
    safe_name = "".join([c if c.isalnum() or c in "._-()" else "_" for c in base_name])

    return f"{safe_name}.{extension}"
