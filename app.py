"""
Main Application File for the Defect Analysis Streamlit Dashboard.
This version implements a true-to-scale simulation of a 510x510mm physical panel.
It includes the Defect Map, Pareto Chart, Summary View, Still Alive map, Stress Map Analysis, and Root Cause Analysis.
"""
import streamlit as st
import plotly.graph_objects as go
import pandas as pd
import matplotlib.colors as mcolors
import numpy as np

# Import our modularized functions
from src.config import (
    BACKGROUND_COLOR, PLOT_AREA_COLOR, GRID_COLOR, TEXT_COLOR, PANEL_COLOR, GAP_SIZE,
    ALIVE_CELL_COLOR, DEFECTIVE_CELL_COLOR, SAFE_VERIFICATION_VALUES
)
from src.data_handler import (
    load_data, get_true_defect_coordinates, prepare_multi_layer_data, aggregate_stress_data,
    calculate_yield_killers, get_cross_section_matrix,
    QUADRANT_WIDTH, QUADRANT_HEIGHT, PANEL_WIDTH, PANEL_HEIGHT
)
from src.plotting import (
    create_grid_shapes, create_defect_traces,
    create_pareto_trace, create_grouped_pareto_trace,
    create_verification_status_chart, create_still_alive_map,
    create_defect_sankey, create_defect_sunburst,
    create_still_alive_figure, create_defect_map_figure, create_pareto_figure,
    create_unit_grid_heatmap, create_density_contour_map,
    create_multi_layer_defect_map, create_stress_heatmap, create_delta_heatmap,
    create_cross_section_heatmap
)
from src.reporting import generate_excel_report, generate_coordinate_list_report, generate_zip_package
from src.enums import ViewMode, Quadrant
from src.utils import get_bu_name_from_filename
from src.documentation import TECHNICAL_DOCUMENTATION
from src.state import SessionStore
from src.analysis import get_analysis_tool
from src.views.still_alive import render_still_alive_main, render_still_alive_sidebar
from src.views.multi_layer import render_multi_layer_view
from src.views.layer_view import render_layer_view

def load_css(file_path: str) -> None:
    """Loads a CSS file and injects it into the Streamlit app."""
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

def main() -> None:
    """Main function to configure and run the Streamlit application."""
    st.set_page_config(layout="wide", page_title="Panel Defect Analysis")
    load_css("assets/styles.css")

    # --- Initialize Session State ---
    store = SessionStore()

    # --- Sidebar Control Panel ---
    with st.sidebar:
        st.title("🎛️ Control Panel")
        with st.form(key="analysis_form"):
            with st.expander("📁 Data Source & Configuration", expanded=True):
                uploaded_files = st.file_uploader("Upload Build-Up Layers (e.g., BU-01-...)", type=["xlsx", "xls"], accept_multiple_files=True)
                panel_rows = st.number_input("Panel Rows", min_value=1, value=7, help="Number of vertical units in a single quadrant.")
                panel_cols = st.number_input("Panel Columns", min_value=1, value=7, help="Number of horizontal units in a single quadrant.")
                lot_number = st.text_input("Lot Number (Optional)", help="Enter the Lot Number to display it on the defect map.")
            submitted = st.form_submit_button("🚀 Run Analysis")

        st.divider()

        is_still_alive_view = store.active_view == 'still_alive'
        is_multi_layer_view = store.active_view == 'multi_layer_defects'
        is_analysis_dashboard = store.active_view == 'analysis_dashboard'

        if store.layer_data:

            if st.button("🔄 Reset Analysis", type="secondary", help="Clears all loaded data and resets the tool."):
                store.clear_all()
                st.rerun()

            # Define controls state for downstream widgets (Reporting)
            disable_layer_controls = is_analysis_dashboard or is_still_alive_view or is_multi_layer_view

            # --- Still Alive Controls ---
            if is_still_alive_view:
                render_still_alive_sidebar(store)

            # --- Multi-Layer Filters ---
            selected_layers_multi = []
            selected_sides_multi = []

            if is_multi_layer_view:
                with st.expander("🛠️ Multi-Layer Filters", expanded=True):
                    all_layers = sorted(store.layer_data.keys())
                    all_sides = set()
                    for l_data in store.layer_data.values():
                        all_sides.update(l_data.keys())

                    side_map = {'F': 'Front', 'B': 'Back'}
                    side_map_rev = {'Front': 'F', 'Back': 'B'}
                    available_side_labels = sorted([side_map.get(s, s) for s in all_sides])

                    selected_layers_multi = st.multiselect("Select Layers", options=all_layers, default=all_layers)
                    selected_sides_labels = st.multiselect("Select Sides", options=available_side_labels, default=available_side_labels)
                    selected_sides_multi = [side_map_rev.get(label, label) for label in selected_sides_labels]

            # Common Layer-Side Logic for Analysis Views
            available_options = []
            option_map = {}
            all_layer_nums = sorted(store.layer_data.keys())
            for num in all_layer_nums:
                sides = sorted(store.layer_data[num].keys())
                for side in sides:
                    side_label = "Front" if side == 'F' else "Back"
                    label = f"Layer {num} ({side_label})"
                    available_options.append(label)
                    option_map[label] = (num, side)

            # Default selection for filters
            default_selection_keys = [option_map[k] for k in available_options]

            # --- Analysis Tools (Strategy Pattern) ---
            with st.expander("🔍 Analysis Tools", expanded=True):
                st.caption("Advanced Defect Analysis")

                # Subview Selection
                analysis_options = [ViewMode.HEATMAP.value, ViewMode.STRESS.value, ViewMode.ROOT_CAUSE.value, ViewMode.INSIGHTS.value]

                if store.analysis_subview not in analysis_options:
                     store.analysis_subview = ViewMode.HEATMAP.value

                subview_val = st.radio("Select Module", analysis_options, index=analysis_options.index(store.analysis_subview))
                store.analysis_subview = subview_val

                if st.button("🚀 Show Analysis Dashboard", use_container_width=True):
                    store.active_view = 'analysis_dashboard'
                    st.rerun()

                st.divider()

                # Delegate Control Rendering
                tool_instance = get_analysis_tool(subview_val, store)
                tool_instance.render_sidebar()

            # --- Layer Inspection Controls (Legacy) ---
            active_df = pd.DataFrame()
            selected_layer_num = store.selected_layer
            if selected_layer_num:
                layer_info = store.layer_data.get(selected_layer_num, {})
                active_df = layer_info.get(store.selected_side, pd.DataFrame())

            # Only show Layer Inspection if in Layer View
            if store.active_view == 'layer':
                with st.expander("📊 Layer Inspection", expanded=True):
                    # Simplified View Options (Removed Heatmap/Insights from here as they moved to Analysis)
                    layer_view_options = [ViewMode.DEFECT.value, ViewMode.PARETO.value, ViewMode.SUMMARY.value]
                    view_mode = st.radio("Select View", layer_view_options)

                    quadrant_selection = st.selectbox("Select Quadrant", Quadrant.values())
                    verification_options = ['All'] + sorted(active_df['Verification'].unique().tolist()) if not active_df.empty else ['All']
                    verification_selection = st.radio("Filter by Verification Status", options=verification_options, index=0)
            else:
                # Default values to prevent errors if variables referenced
                view_mode = ViewMode.DEFECT.value
                quadrant_selection = Quadrant.ALL.value
                verification_selection = 'All'

            st.divider()

            # --- Reporting ---
            with st.expander("📥 Reporting", expanded=True):
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

                if st.button("Generate Download Package", disabled=disable_layer_controls):
                    with st.spinner("Generating Package..."):
                        # Prepare data
                        full_df = store.layer_data.get_combined_dataframe()
                        true_defect_coords = get_true_defect_coordinates(store.layer_data)

                        # Generate ZIP
                        store.report_bytes = generate_zip_package(
                            full_df=full_df,
                            panel_rows=panel_rows,
                            panel_cols=panel_cols,
                            quadrant_selection=quadrant_selection,
                            verification_selection=verification_selection,
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
                st.download_button("Download Package (ZIP)", data=store.report_bytes or b"", file_name=zip_filename, mime="application/zip", disabled=store.report_bytes is None)

    # --- Main Content Area ---
    st.title("📊 Panel Defect Analysis Tool")
    st.markdown("<br>", unsafe_allow_html=True)

    if submitted:
        store.layer_data = load_data(uploaded_files, panel_rows, panel_cols)
        if store.layer_data:
            store.selected_layer = max(store.layer_data.keys())
            store.active_view = 'layer'
            layer_info = store.layer_data.get(store.selected_layer, {})
            if 'F' in layer_info:
                store.selected_side = 'F'
            elif 'B' in layer_info:
                store.selected_side = 'B'
            elif layer_info:
                store.selected_side = next(iter(layer_info.keys()))
        else:
            store.selected_layer = None
        store.analysis_params = {"panel_rows": panel_rows, "panel_cols": panel_cols, "gap_size": GAP_SIZE, "lot_number": lot_number}
        store.report_bytes = None
        st.rerun()

    if store.layer_data:
        params = store.analysis_params
        panel_rows, panel_cols = params.get("panel_rows", 7), params.get("panel_cols", 7)

        # --- View Selection Bar ---
        with st.expander("Select View", expanded=True):
            layer_keys = sorted(store.layer_data.keys())
            bu_names = {}
            for num in layer_keys:
                first_side_key = next(iter(store.layer_data[num]))
                bu_names[num] = get_bu_name_from_filename(store.layer_data[num][first_side_key]['SOURCE_FILE'].iloc[0])

            # Total buttons = layers + 2 (Still Alive, Multi-Layer) - Analysis moved to Sidebar
            num_buttons = len(layer_keys) + 2
            cols = st.columns(num_buttons)

            # Layer Buttons
            for i, layer_num in enumerate(layer_keys):
                with cols[i]:
                    bu_name = bu_names.get(layer_num, f"Layer {layer_num}")
                    is_active = store.active_view == 'layer' and store.selected_layer == layer_num
                    if st.button(bu_name, key=f"layer_btn_{layer_num}", use_container_width=True, type="primary" if is_active else "secondary"):
                        store.set_layer_view(layer_num)
                        # Auto select side
                        layer_info = store.layer_data.get(layer_num, {})
                        if 'F' in layer_info:
                            store.selected_side = 'F'
                        elif 'B' in layer_info:
                            store.selected_side = 'B'
                        elif layer_info:
                             store.selected_side = next(iter(layer_info.keys()))
                        st.rerun()

            # Still Alive
            with cols[num_buttons - 2]:
                is_active = store.active_view == 'still_alive'
                if st.button("Still Alive", key="still_alive_btn", use_container_width=True, type="primary" if is_active else "secondary"):
                    store.active_view = 'still_alive'
                    st.rerun()

            # Multi-Layer
            with cols[num_buttons - 1]:
                is_active = store.active_view == 'multi_layer_defects'
                if st.button("Multi-Layer Defects", key="multi_layer_defects_btn", use_container_width=True, type="primary" if is_active else "secondary"):
                    store.active_view = 'multi_layer_defects'
                    st.rerun()

            # Side Selection (Only for Layer View)
            if store.active_view == 'layer' and store.selected_layer:
                layer_info = store.layer_data.get(store.selected_layer, {})
                if len(layer_info) >= 1:
                    side_cols = st.columns(max(len(layer_info), 2))
                    for i, side in enumerate(sorted(layer_info.keys())):
                        with side_cols[i]:
                            side_name = "Front" if side == 'F' else "Back"
                            is_side_active = store.selected_side == side
                            if st.button(side_name, key=f"side_btn_{side}", use_container_width=True, type="primary" if is_side_active else "secondary"):
                                store.selected_side = side
                                st.rerun()

        st.divider()

        # --- View Logic ---
        if store.active_view == 'still_alive':
            render_still_alive_main(store)

        elif store.active_view == 'multi_layer_defects':
            render_multi_layer_view(store, selected_layers_multi, selected_sides_multi)

        elif store.active_view == 'analysis_dashboard':
            # Delegate to Strategy
            tool = get_analysis_tool(store.analysis_subview, store)
            tool.render_main()

        elif store.active_view == 'layer':
            render_layer_view(store, view_mode, quadrant_selection, verification_selection)

    else:
        st.header("Welcome to the Panel Defect Analysis Tool!")
        st.info("To get started, upload an Excel file or use the default sample data, then click 'Run Analysis'.")

if __name__ == '__main__':
    main()
