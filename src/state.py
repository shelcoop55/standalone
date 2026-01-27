"""
State Management Module.
Implements the 'Store' pattern to unify access to Streamlit's session state.
"""
import streamlit as st
from dataclasses import dataclass
from typing import Optional, Dict, List
from src.enums import ViewMode, Quadrant
from src.io.ingestion import load_panel_data
from src.core.models import PanelData

@dataclass
class SessionStore:
    """
    Centralized store for application state.
    Wraps st.session_state to provide typed access and centralized modification logic.
    """

    def __post_init__(self):
        """Initialize default state values if they don't exist."""
        defaults = {
            'report_bytes': None,
            'dataset_id': None,
            'layer_data_metadata': {}, # Store lightweight metadata (keys only)
            'selected_layer': None,
            'selected_side': 'F',
            'analysis_params': {},
            'active_view': 'layer', # Default start view
            'analysis_subview': ViewMode.HEATMAP.value,
            # UI Filter States
            'view_mode': ViewMode.DEFECT.value,
            'quadrant_selection': Quadrant.ALL.value,
            'verification_selection': 'All',
            'multi_layer_selection': [],
            'multi_side_selection': []
        }

        for key, value in defaults.items():
            if key not in st.session_state:
                st.session_state[key] = value

    # --- Properties for Typed Access ---

    @property
    def dataset_id(self) -> Optional[str]:
        return st.session_state.dataset_id

    @dataset_id.setter
    def dataset_id(self, val: Optional[str]):
        st.session_state.dataset_id = val

    @property
    def layer_data(self) -> Optional[PanelData]:
        """
        Retrieves the heavy PanelData object from the global cache (cache_resource) using current inputs.
        Optimized to use dataset_id check to avoid unnecessary cache lookups if no data is loaded.
        """
        if not self.dataset_id:
            return None

        current_uploader_key = f"uploaded_files_{st.session_state.get('uploader_key', 0)}"
        files = st.session_state.get(current_uploader_key, [])

        # Retrieve geometric params from analysis_params
        # Defaults matching config.py if not present
        params = self.analysis_params
        rows = params.get("panel_rows", 7)
        cols = params.get("panel_cols", 7)
        width = params.get("panel_width", 470)
        height = params.get("panel_height", 470)
        gap_x = params.get("gap_x", 3.0)
        gap_y = params.get("gap_y", 3.0)

        # Safety Check: If we expect Real Data (ID set) but files are lost/empty, return None.
        is_sample = self.dataset_id and str(self.dataset_id).startswith("sample")

        if not files and not is_sample:
             return None

        # Call load_panel_data. If inputs haven't changed, it hits cache_resource.
        return load_panel_data(files, rows, cols, width, height, gap_x, gap_y)

    @property
    def layer_data_keys(self) -> Dict:
        """Access lightweight metadata about layers (e.g. available layers/sides)"""
        return st.session_state.layer_data_metadata

    @layer_data_keys.setter
    def layer_data_keys(self, val: Dict):
        st.session_state.layer_data_metadata = val

    @property
    def selected_layer(self) -> Optional[int]:
        return st.session_state.selected_layer

    @selected_layer.setter
    def selected_layer(self, layer_num: Optional[int]):
        st.session_state.selected_layer = layer_num

    @property
    def selected_side(self) -> str:
        return st.session_state.selected_side

    @selected_side.setter
    def selected_side(self, side: str):
        st.session_state.selected_side = side

    @property
    def active_view(self) -> str:
        return st.session_state.active_view

    @active_view.setter
    def active_view(self, view: str):
        st.session_state.active_view = view

    @property
    def analysis_subview(self) -> str:
        return st.session_state.analysis_subview

    @analysis_subview.setter
    def analysis_subview(self, subview: str):
        st.session_state.analysis_subview = subview

    @property
    def analysis_params(self) -> Dict:
        return st.session_state.analysis_params

    @analysis_params.setter
    def analysis_params(self, params: Dict):
        st.session_state.analysis_params = params

    @property
    def report_bytes(self) -> Optional[bytes]:
        return st.session_state.report_bytes

    @report_bytes.setter
    def report_bytes(self, data: Optional[bytes]):
        st.session_state.report_bytes = data

    # --- UI Filter Properties ---
    @property
    def view_mode(self) -> str:
        return st.session_state.view_mode

    @view_mode.setter
    def view_mode(self, val: str):
        st.session_state.view_mode = val

    @property
    def quadrant_selection(self) -> str:
        return st.session_state.quadrant_selection

    @quadrant_selection.setter
    def quadrant_selection(self, val: str):
        st.session_state.quadrant_selection = val

    @property
    def verification_selection(self) -> str:
        return st.session_state.verification_selection

    @verification_selection.setter
    def verification_selection(self, val: str):
        st.session_state.verification_selection = val

    @property
    def multi_layer_selection(self) -> List[int]:
        return st.session_state.multi_layer_selection

    @multi_layer_selection.setter
    def multi_layer_selection(self, val: List[int]):
        st.session_state.multi_layer_selection = val

    @property
    def multi_side_selection(self) -> List[str]:
        return st.session_state.multi_side_selection

    @multi_side_selection.setter
    def multi_side_selection(self, val: List[str]):
        st.session_state.multi_side_selection = val

    # --- Actions ---

    def clear_all(self):
        """Resets the entire session state."""
        st.session_state.clear()

    def reset_data_source(self):
        """Resets the file uploader and data state, triggering a clean restart."""
        # We need to preserve the uploader key increment logic
        current_key_val = st.session_state.get('uploader_key', 0)
        self.clear_all()
        st.session_state['uploader_key'] = current_key_val + 1

    def set_layer_view(self, layer_num: int, side: Optional[str] = None):
        """Helper to switch to a specific layer view."""
        self.active_view = 'layer'
        self.selected_layer = layer_num
        if side:
            self.selected_side = side
