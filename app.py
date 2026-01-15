import streamlit as st
import pandas as pd
from src.config import GAP_SIZE, BACKGROUND_COLOR, TEXT_COLOR, PANEL_COLOR
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
    st.set_page_config(layout="wide", page_title="Panel Defect Analysis")
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
            # Update: Collapsed by default as per request
            with st.expander("📁 Data Source & Configuration", expanded=False):
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

            # Callback for Analysis
            def on_run_analysis():
                # Read from dynamic key
                current_uploader_key = f"uploaded_files_{st.session_state['uploader_key']}"
                files = st.session_state.get(current_uploader_key, [])

                rows = st.session_state.panel_rows
                cols = st.session_state.panel_cols
                lot = st.session_state.lot_number
                comment = st.session_state.process_comment

                # Load Data
                data = load_data(files, rows, cols)
                if data:
                    store.layer_data = data
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
                    "gap_size": GAP_SIZE,
                    "lot_number": lot,
                    "process_comment": comment
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
