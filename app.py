import streamlit as st
import pandas as pd
from src.config import GAP_SIZE, BACKGROUND_COLOR, TEXT_COLOR, PANEL_COLOR, PANEL_WIDTH, PANEL_HEIGHT, FRAME_WIDTH, FRAME_HEIGHT, DEFAULT_OFFSET_X, DEFAULT_OFFSET_Y, DEFAULT_GAP_X, DEFAULT_GAP_Y
from src.data_handler import load_data, get_true_defect_coordinates
from src.reporting import generate_zip_package
from src.enums import ViewMode, Quadrant
from src.state import SessionStore
from src.views.manager import ViewManager
from src.analysis import get_analysis_tool

def load_css(file_path: str) -> None:
    """Loads a CSS file and injects it into the Streamlit app."""
    try:
        with open(file_path) as f:
            css = f.read()
            css_variables = f'''
            <style>
                :root {{
                    --background-color: {BACKGROUND_COLOR};
                    --text-color: {TEXT_COLOR};
                    --panel-color: {PANEL_COLOR};
                    --panel-hover-color: #d48c46;
                }}
                {css}
            </style>
            '''
            st.markdown(css_variables, unsafe_allow_html=True)
    except FileNotFoundError:
        pass # Handle missing CSS safely

def main() -> None:
    """Main function to configure and run the Streamlit application."""
    st.set_page_config(layout="wide", page_title="Panel Defect Analysis", initial_sidebar_state="expanded")
    load_css("assets/styles.css")

    # --- Initialize Session State & View Manager ---
    store = SessionStore()
    view_manager = ViewManager(store)

    if "uploader_key" not in st.session_state:
        st.session_state["uploader_key"] = 0

    # --- Sidebar Control Panel ---
    with st.sidebar:
        st.title("🎛️ Control Panel")

        # --- 1. Analysis Configuration Form ---
        with st.form(key="analysis_form"):
            with st.expander("📁 Data Source & Configuration", expanded=True):
                # Use dynamic key to allow resetting the widget
                uploader_key = f"uploaded_files_{st.session_state['uploader_key']}"
                st.file_uploader(
                    "Upload Build-Up Layers (e.g., BU-01-...)",
                    type=["xlsx", "xls"],
                    accept_multiple_files=True,
                    key=uploader_key
                )
                st.number_input(
                    "Panel Rows", min_value=1, value=7,
                    help="Number of vertical units in a single quadrant.",
                    key="panel_rows"
                )
                st.number_input(
                    "Panel Columns", min_value=1, value=7,
                    help="Number of horizontal units in a single quadrant.",
                    key="panel_cols"
                )
                st.text_input(
                    "Lot Number (Optional)",
                    help="Enter the Lot Number to display it on the defect map.",
                    key="lot_number"
                )
                st.text_input(
                    "Process Step / Comment",
                    help="Enter a comment (e.g., Post Etching) to tag these layers.",
                    key="process_comment"
                )

            with st.expander("⚙️ Advanced Configuration", expanded=False):
                # 1. Panel Dimensions (UI Removed - Hardcoded Defaults)
                # Used to be: c_dim1, c_dim2 inputs for Panel Width/Height
                # Now using Frame Width/Height (510/515) internally for calculation.

                # 2. Origins (Renamed from Offsets)
                c_off1, c_off2 = st.columns(2)
                with c_off1:
                    st.number_input("X Origin (mm)", value=DEFAULT_OFFSET_X, step=1.0, key="offset_x", help="Shift origin X by this amount.")
                with c_off2:
                    st.number_input("Y Origin (mm)", value=DEFAULT_OFFSET_Y, step=1.0, key="offset_y", help="Shift origin Y by this amount.")

                # 3. Gaps
                c_gap1, c_gap2 = st.columns(2)
                with c_gap1:
                    st.number_input("Gap X (mm)", value=float(DEFAULT_GAP_X), step=1.0, min_value=0.0, key="gap_x", help="Horizontal gap between quadrants.")
                with c_gap2:
                    st.number_input("Gap Y (mm)", value=float(DEFAULT_GAP_Y), step=1.0, min_value=0.0, key="gap_y", help="Vertical gap between quadrants.")

            # Callback for Analysis
            def on_run_analysis():
                # Read from dynamic key
                current_uploader_key = f"uploaded_files_{st.session_state['uploader_key']}"
                files = st.session_state.get(current_uploader_key, [])

                rows = st.session_state.panel_rows
                cols = st.session_state.panel_cols
                lot = st.session_state.lot_number
                comment = st.session_state.process_comment

                # Retrieve Advanced Params
                off_x = st.session_state.get("offset_x", DEFAULT_OFFSET_X)
                off_y = st.session_state.get("offset_y", DEFAULT_OFFSET_Y)
                gap_x = st.session_state.get("gap_x", DEFAULT_GAP_X)
                gap_y = st.session_state.get("gap_y", DEFAULT_GAP_Y)

                # DYNAMIC CALCULATION of Active Panel Dimensions
                # Logic: Active_Dim = Total_Frame - (2 * Offset) - Gap
                p_width = float(FRAME_WIDTH) - (2 * off_x) - gap_x
                p_height = float(FRAME_HEIGHT) - (2 * off_y) - gap_y

                # Load Data (This will now hit the cache if arguments are same)
                # Pass dynamically calculated width/height
                data = load_data(files, rows, cols, p_width, p_height, gap_x, gap_y)
                if data:
                    # UPDATE: Store ID and Metadata, NOT the object
                    if not files:
                        store.dataset_id = "sample_data"
                    else:
                        # Simple ID generation based on filenames for tracking
                        store.dataset_id = str(hash(tuple(f.name for f in files)))

                    # Store lightweight metadata for UI logic (keys only)
                    # We need a serializable dict structure: {layer_num: {side: True}}
                    meta = {}
                    for l_num, sides in data.items():
                        meta[l_num] = list(sides.keys())
                    store.layer_data_keys = meta

                    # Logic using the data object (which is local var here, safe)
                    store.selected_layer = max(data.keys())
                    store.active_view = 'layer'

                    # Auto-select side
                    layer_info = data.get(store.selected_layer, {})
                    if 'F' in layer_info:
                        store.selected_side = 'F'
                    elif 'B' in layer_info:
                        store.selected_side = 'B'
                    elif layer_info:
                        store.selected_side = next(iter(layer_info.keys()))

                    # Initialize Multi-Layer Selection defaults
                    store.multi_layer_selection = sorted(data.keys())
                    all_sides = set()
                    for l_data in data.values():
                        all_sides.update(l_data.keys())
                    store.multi_side_selection = sorted(list(all_sides))
                else:
                    store.selected_layer = None

                store.analysis_params = {
                    "panel_rows": rows,
                    "panel_cols": cols,
                    "panel_width": p_width,
                    "panel_height": p_height,
                    "gap_x": gap_x,
                    "gap_y": gap_y,
                    "gap_size": gap_x, # Backwards compatibility
                    "lot_number": lot,
                    "process_comment": comment,
                    "offset_x": off_x,
                    "offset_y": off_y
                }
                store.report_bytes = None

            c1, c2 = st.columns(2)
            with c1:
                st.form_submit_button("🚀 Run", on_click=on_run_analysis)

            with c2:
                # Reset Button logic integrated into the form area (but form_submit_button is primary action)
                # Since we cannot put a standard button inside a form that triggers a rerun cleanly without submitting the form,
                # we will use another form_submit_button or place it outside if strictly required.
                # However, user asked "inside Data Source & Configuration".
                # Standard st.button inside a form behaves as a submit button.

                def on_reset():
                    store.clear_all()
                    # Re-initialize uploader_key immediately after clearing state
                    # to prevent KeyError on rerun or subsequent access
                    if "uploader_key" not in st.session_state:
                        st.session_state["uploader_key"] = 0

                    # Increment key to recreate file uploader widget (effectively clearing it)
                    st.session_state["uploader_key"] += 1
                    # Rerun will happen automatically after callback

                st.form_submit_button("🔄 Reset", on_click=on_reset, type="secondary")

    # --- Main Content Area ---
    # Header removed to save space
    # st.title("📊 Panel Defect Analysis Tool")

    # Render Navigation (Triggers full rerun to update Sidebar context)
    view_manager.render_navigation()

    @st.fragment
    def render_chart_area():
        # Render Main View (Chart Area) - Isolated updates
        view_manager.render_main_view()

    render_chart_area()

if __name__ == '__main__':
    main()
