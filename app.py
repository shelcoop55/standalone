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

    # --- Sidebar Control Panel ---
    with st.sidebar:
        st.title("🎛️ Control Panel")

        # --- 1. Analysis Configuration Form ---
        with st.form(key="analysis_form"):
            with st.expander("📁 Data Source & Configuration", expanded=True):
                st.file_uploader(
                    "Upload Build-Up Layers (e.g., BU-01-...)",
                    type=["xlsx", "xls"],
                    accept_multiple_files=True,
                    key="uploaded_files"
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
                files = st.session_state.uploaded_files
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

            st.form_submit_button("🚀 Run Analysis", on_click=on_run_analysis)

        st.divider()

        # --- Sidebar Reporting ---

        if store.layer_data:
            if st.button("🔄 Reset Analysis", type="secondary", help="Clears all loaded data and resets the tool."):
                store.clear_all()
                st.rerun()

            st.divider()

            # --- Reporting ---
            with st.expander("📥 Reporting", expanded=False):
                st.subheader("Generate Report")
                col_rep1, col_rep2 = st.columns(2)
                with col_rep1:
                    include_excel = st.checkbox("Excel Report", value=True)
                    include_coords = st.checkbox("Coordinate List", value=True)
                with col_rep2:
                    include_map = st.checkbox("Defect Map (HTML)", value=True)
                    include_insights = st.checkbox("Insights Charts", value=True)

                st.markdown("**Export Images (All Layers):**")
                col_img1, col_img2 = st.columns(2)
                with col_img1:
                    include_png_all = st.checkbox("Defect Maps (PNG)", value=False)
                with col_img2:
                    include_pareto_png = st.checkbox("Pareto Charts (PNG)", value=False)

                if st.button("Generate Download Package"):
                    with st.spinner("Generating Package..."):
                        full_df = store.layer_data.get_combined_dataframe()
                        true_defect_coords = get_true_defect_coordinates(store.layer_data)

                        store.report_bytes = generate_zip_package(
                            full_df=full_df,
                            panel_rows=store.analysis_params.get('panel_rows', 7),
                            panel_cols=store.analysis_params.get('panel_cols', 7),
                            quadrant_selection=store.quadrant_selection,
                            verification_selection=store.verification_selection,
                            source_filename="Multiple Files",
                            true_defect_coords=true_defect_coords,
                            include_excel=include_excel,
                            include_coords=include_coords,
                            include_map=include_map,
                            include_insights=include_insights,
                            include_png_all_layers=include_png_all,
                            include_pareto_png=include_pareto_png,
                            layer_data=store.layer_data
                        )
                        st.success("Package generated successfully!")

                params_local = store.analysis_params
                lot_num_str = f"_{params_local.get('lot_number', '')}" if params_local.get('lot_number') else ""
                zip_filename = f"defect_package_layer_{store.selected_layer}{lot_num_str}.zip"
                st.download_button(
                    "Download Package (ZIP)",
                    data=store.report_bytes or b"",
                    file_name=zip_filename,
                    mime="application/zip",
                    disabled=store.report_bytes is None
                )

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
