"""
Main Application File for the Defect Analysis Streamlit Dashboard.
This version implements a true-to-scale simulation of a 510x510mm physical panel.
It includes the Defect Map, Pareto Chart, Summary View, and the new Still Alive map.
"""
import streamlit as st
import plotly.graph_objects as go
import pandas as pd
import matplotlib.colors as mcolors

# Import our modularized functions
from src.config import (
    BACKGROUND_COLOR, PLOT_AREA_COLOR, GRID_COLOR, TEXT_COLOR, PANEL_COLOR, GAP_SIZE,
    ALIVE_CELL_COLOR, DEFECTIVE_CELL_COLOR, SAFE_VERIFICATION_VALUES
)
from src.data_handler import (
    load_data, get_true_defect_coordinates,
    QUADRANT_WIDTH, QUADRANT_HEIGHT, PANEL_WIDTH, PANEL_HEIGHT
)
from src.plotting import (
    create_grid_shapes, create_defect_traces,
    create_pareto_trace, create_grouped_pareto_trace,
    create_verification_status_chart, create_still_alive_map,
    create_defect_sankey, create_defect_sunburst,
    create_still_alive_figure, create_defect_map_figure, create_pareto_figure,
    create_unit_grid_heatmap, create_density_contour_map, create_hexbin_density_map
)
from src.reporting import generate_excel_report, generate_coordinate_list_report, generate_zip_package
from src.enums import ViewMode, Quadrant
from src.utils import get_bu_name_from_filename
from src.documentation import TECHNICAL_DOCUMENTATION

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
    if 'report_bytes' not in st.session_state: st.session_state.report_bytes = None
    if 'layer_data' not in st.session_state: st.session_state.layer_data = {}
    if 'selected_layer' not in st.session_state: st.session_state.selected_layer = None
    if 'selected_side' not in st.session_state: st.session_state.selected_side = 'F'
    if 'analysis_params' not in st.session_state: st.session_state.analysis_params = {}
    if 'active_view' not in st.session_state: st.session_state.active_view = 'layer'

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

        is_still_alive_view = st.session_state.active_view == 'still_alive'

        if st.session_state.get('layer_data'):

            # IMPROVEMENT: Add a Reset Button to clear the analysis
            if st.button("🔄 Reset Analysis", type="secondary", help="Clears all loaded data and resets the tool."):
                st.session_state.clear()
                st.rerun()

            # --- Get the active dataframe based on selected layer and side ---
            active_df = pd.DataFrame()
            selected_layer_num = st.session_state.get('selected_layer')
            if selected_layer_num:
                layer_info = st.session_state.layer_data.get(selected_layer_num, {})
                active_df = layer_info.get(st.session_state.selected_side, pd.DataFrame())

            with st.expander("📊 Analysis Controls", expanded=True):
                view_mode = st.radio("Select View", ViewMode.values(), help="Choose the primary analysis view.", disabled=is_still_alive_view)
                quadrant_selection = st.selectbox("Select Quadrant", Quadrant.values(), help="Filter data to a specific quadrant.", disabled=is_still_alive_view)

                verification_options = ['All'] + sorted(active_df['Verification'].unique().tolist()) if not active_df.empty else ['All']
                verification_selection = st.radio("Filter by Verification Status", options=verification_options, index=0, help="Select a single verification status to filter by.", disabled=is_still_alive_view)

            st.divider()

            with st.expander("📥 Reporting", expanded=True):
                st.subheader("Generate Report")
                col_rep1, col_rep2 = st.columns(2)
                with col_rep1:
                    include_excel = st.checkbox("Excel Report", value=True)
                    include_coords = st.checkbox("Coordinate List", value=True)
                with col_rep2:
                    include_map = st.checkbox("Defect Map (HTML)", value=True)
                    include_insights = st.checkbox("Insights Charts", value=True)

                # New Export Options
                st.markdown("**Export Images (All Layers):**")
                col_img1, col_img2 = st.columns(2)
                with col_img1:
                    include_png_all = st.checkbox("Defect Maps (PNG)", value=False, help="Export PNG images of the defect map for ALL layers (Front & Back).")
                with col_img2:
                    include_pareto_png = st.checkbox("Pareto Charts (PNG)", value=False, help="Export PNG images of the Pareto chart for ALL layers (Front & Back).")

                if st.button("Generate Download Package", disabled=is_still_alive_view, help="Generate a ZIP file with all selected items."):
                    with st.spinner("Generating Package..."):
                        layer_info = st.session_state.layer_data.get(st.session_state.selected_layer, {})
                        if layer_info:
                            all_sides_df = pd.concat(layer_info.values(), ignore_index=True)
                            report_df = all_sides_df
                            if verification_selection != 'All': report_df = report_df[report_df['Verification'] == verification_selection]
                            if quadrant_selection != Quadrant.ALL.value: report_df = report_df[report_df['QUADRANT'] == quadrant_selection]

                            params = st.session_state.analysis_params
                            source_filenames = report_df['SOURCE_FILE'].unique().tolist()

                            true_defect_coords = get_true_defect_coordinates(st.session_state.layer_data)

                            zip_bytes = generate_zip_package(
                                full_df=report_df,
                                panel_rows=params.get("panel_rows", 7),
                                panel_cols=params.get("panel_cols", 7),
                                quadrant_selection=quadrant_selection,
                                verification_selection=verification_selection,
                                source_filename=", ".join(source_filenames),
                                true_defect_coords=true_defect_coords,
                                include_excel=include_excel,
                                include_coords=include_coords,
                                include_map=include_map,
                                include_insights=include_insights,
                                include_png_all_layers=include_png_all,
                                include_pareto_png=include_pareto_png,
                                layer_data=st.session_state.layer_data # Pass all data for bulk export
                            )
                            st.session_state.report_bytes = zip_bytes
                            st.rerun()

                # IMPROVEMENT: Add Lot Number to filename if available
                # Use session_state directly as 'params' is local to the block above
                params_local = st.session_state.get('analysis_params', {})
                lot_num_str = f"_{params_local.get('lot_number', '')}" if params_local.get('lot_number') else ""
                zip_filename = f"defect_package_layer_{st.session_state.selected_layer}{lot_num_str}.zip"

                st.download_button("Download Package (ZIP)", data=st.session_state.report_bytes or b"", file_name=zip_filename, mime="application/zip", disabled=st.session_state.report_bytes is None)

                st.markdown("---")
                if st.button("Defect Documentation", use_container_width=True):
                    st.session_state.active_view = 'documentation'
                    st.rerun()
        else:
            with st.expander("📊 Analysis Controls", expanded=True):
                st.radio("Select View", ViewMode.values(), disabled=True)
                st.selectbox("Select Quadrant", Quadrant.values(), disabled=True)
                st.radio("Filter by Verification Status", ["All"], disabled=True)
            st.divider()
            with st.expander("📥 Reporting", expanded=True):
                st.button("Generate Report for Download", disabled=True)
                st.download_button("Download Full Report", b"", disabled=True)
                st.markdown("---")
                if st.button("Defect Documentation", use_container_width=True):
                     st.session_state.active_view = 'documentation'
                     st.rerun()

    st.title("📊 Panel Defect Analysis Tool")
    st.markdown("<br>", unsafe_allow_html=True)

    if submitted:
        st.session_state.layer_data = load_data(uploaded_files, panel_rows, panel_cols)
        if st.session_state.layer_data:
            st.session_state.selected_layer = max(st.session_state.layer_data.keys())
            st.session_state.active_view = 'layer'

            # Ensure valid side selection after loading new data
            layer_info = st.session_state.layer_data.get(st.session_state.selected_layer, {})
            if 'F' in layer_info:
                st.session_state.selected_side = 'F'
            elif 'B' in layer_info:
                st.session_state.selected_side = 'B'
            elif layer_info:
                # Fallback to whatever side is available if neither F nor B (unlikely but safe)
                st.session_state.selected_side = next(iter(layer_info.keys()))

        else:
            st.session_state.selected_layer = None
        st.session_state.analysis_params = {"panel_rows": panel_rows, "panel_cols": panel_cols, "gap_size": GAP_SIZE, "lot_number": lot_number}
        st.session_state.report_bytes = None
        st.rerun()

    if st.session_state.active_view == 'documentation':
        if st.button("⬅️ Back to Analysis"):
            # Restore previous view or default to layer view
            if st.session_state.get('layer_data'):
                st.session_state.active_view = 'layer'
            else:
                 st.session_state.active_view = 'layer' # Will fall back to empty state
            st.rerun()

        st.markdown(TECHNICAL_DOCUMENTATION)
        return # Stop execution to show only documentation

    if st.session_state.get('layer_data'):
        params = st.session_state.analysis_params
        panel_rows, panel_cols = params.get("panel_rows", 7), params.get("panel_cols", 7)
        lot_number = params.get("lot_number", "")

        with st.expander("Select View", expanded=True):
            layer_keys = sorted(st.session_state.layer_data.keys())
            bu_names = {}
            for num in layer_keys:
                # Get a representative BU name from the first side ('F' or 'B') found
                first_side_key = next(iter(st.session_state.layer_data[num]))
                bu_names[num] = get_bu_name_from_filename(st.session_state.layer_data[num][first_side_key]['SOURCE_FILE'].iloc[0])

            # --- Layer Selection Buttons ---
            num_buttons = len(layer_keys) + 1
            cols = st.columns(num_buttons)
            for i, layer_num in enumerate(layer_keys):
                with cols[i]:
                    bu_name = bu_names.get(layer_num, f"Layer {layer_num}")
                    is_active = st.session_state.active_view == 'layer' and st.session_state.selected_layer == layer_num
                    if st.button(bu_name, key=f"layer_btn_{layer_num}", use_container_width=True, type="primary" if is_active else "secondary"):
                        st.session_state.active_view = 'layer'
                        st.session_state.selected_layer = layer_num

                        # Default to 'F' side when switching layers, if available; otherwise 'B'
                        layer_info = st.session_state.layer_data.get(layer_num, {})
                        if 'F' in layer_info:
                            st.session_state.selected_side = 'F'
                        elif 'B' in layer_info:
                            st.session_state.selected_side = 'B'
                        elif layer_info:
                             st.session_state.selected_side = next(iter(layer_info.keys()))

                        st.rerun()
            with cols[num_buttons - 1]:
                is_active = st.session_state.active_view == 'still_alive'
                if st.button("Still Alive", key="still_alive_btn", use_container_width=True, type="primary" if is_active else "secondary"):
                    st.session_state.active_view = 'still_alive'
                    st.rerun()

            # --- Side Selection Buttons (only if a layer is selected) ---
            selected_layer_num = st.session_state.get('selected_layer')
            if selected_layer_num and st.session_state.active_view == 'layer':
                layer_info = st.session_state.layer_data.get(selected_layer_num, {})
                # Show side buttons even if only one side is available, so the user knows what they are looking at
                if len(layer_info) >= 1:
                    side_cols = st.columns(max(len(layer_info), 2)) # Use at least 2 columns for spacing if only 1 side
                    sorted_sides = sorted(layer_info.keys())
                    for i, side in enumerate(sorted_sides):
                        with side_cols[i]:
                            side_name = "Front" if side == 'F' else "Back"
                            is_side_active = st.session_state.selected_side == side
                            if st.button(side_name, key=f"side_btn_{side}", use_container_width=True, type="primary" if is_side_active else "secondary"):
                                st.session_state.selected_side = side
                                st.rerun()

        st.divider()

        if st.session_state.active_view == 'still_alive':
            st.header("Still Alive Panel Yield Map")
            map_col, summary_col = st.columns([2.5, 1])
            with map_col:
                true_defect_coords = get_true_defect_coordinates(st.session_state.layer_data)

                # REFACTORED: Use the new helper function
                fig = create_still_alive_figure(panel_rows, panel_cols, true_defect_coords)
                st.plotly_chart(fig, use_container_width=True)

            with summary_col:
                total_cells = (panel_rows * 2) * (panel_cols * 2)
                defective_cell_count = len(true_defect_coords)
                alive_cell_count = total_cells - defective_cell_count
                yield_percentage = (alive_cell_count / total_cells) * 100 if total_cells > 0 else 0
                st.subheader("Yield Summary")
                st.metric("Panel Yield", f"{yield_percentage:.2f}%")
                st.metric("Surviving Cells", f"{alive_cell_count:,} / {total_cells:,}")
                st.metric("Defective Cells", f"{defective_cell_count:,}")
                st.divider()

                st.subheader("Download Report")

                # Button for the coordinate list report
                coordinate_report_bytes = generate_coordinate_list_report(true_defect_coords)
                st.download_button(
                    label="Download Coordinate List",
                    data=coordinate_report_bytes,
                    file_name="still_alive_coordinate_list.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )

                # NEW: Button for Still Alive Map Image
                # Generate on the fly for direct download
                try:
                    # Scale=2 for higher resolution
                    img_bytes = fig.to_image(format="png", engine="kaleido", scale=2)
                    st.download_button(
                        label="Download Map Image (PNG)",
                        data=img_bytes,
                        file_name="Still_Alive_Map.png",
                        mime="image/png"
                    )
                except Exception as e:
                    st.warning("Image generation not available.")

                st.divider()
                st.subheader("Legend")
                legend_html = f'''
                <div style="display: flex; flex-direction: column; align-items: flex-start;">
                    <div style="display: flex; align-items: center; margin-bottom: 10px;">
                        <div style="width: 20px; height: 20px; background-color: {ALIVE_CELL_COLOR}; margin-right: 10px; border: 1px solid black;"></div>
                        <span>Defect-Free Cell</span>
                    </div>
                    <div style="display: flex; align-items: center;">
                        <div style="width: 20px; height: 20px; background-color: {DEFECTIVE_CELL_COLOR}; margin-right: 10px; border: 1px solid black;"></div>
                        <span>Defective Cell</span>
                    </div>
                </div>
                '''
                st.markdown(legend_html, unsafe_allow_html=True)
        
        elif st.session_state.active_view == 'layer':
            selected_layer_num = st.session_state.get('selected_layer')
            layer_info = st.session_state.layer_data.get(selected_layer_num, {})

            if not selected_layer_num or not layer_info:
                st.info("Please select a build-up layer to view its defect map.")
                return

            # Get the dataframe for the selected side
            side_df = layer_info.get(st.session_state.selected_side)
            if side_df is None or side_df.empty:
                side_name = "Front" if st.session_state.selected_side == 'F' else "Back"
                st.warning(f"No defect data found for Layer {selected_layer_num} - {side_name} Side.")
                return

            filtered_df = side_df[side_df['Verification'] == verification_selection] if verification_selection != 'All' else side_df
            display_df = filtered_df[filtered_df['QUADRANT'] == quadrant_selection] if quadrant_selection != Quadrant.ALL.value else filtered_df

            if view_mode == ViewMode.DEFECT.value:
                # REFACTORED: Use new helper
                fig = create_defect_map_figure(display_df, panel_rows, panel_cols, quadrant_selection, lot_number)
                st.plotly_chart(fig, use_container_width=True)

            elif view_mode == ViewMode.PARETO.value:
                # REFACTORED: Use new helper
                st.subheader(f"Defect Pareto - Layer {st.session_state.selected_layer} - Quadrant: {quadrant_selection}")
                fig = create_pareto_figure(display_df, quadrant_selection)
                st.plotly_chart(fig, use_container_width=True)

            elif view_mode == ViewMode.HEATMAP.value:
                st.header(f"True Defect Heatmap Analysis - Layer {st.session_state.selected_layer}")
                st.info("These heatmaps visualize the density of 'True Defects' across the ENTIRE panel, ignoring quadrant filters.")

                # Always use the full side dataframe for heatmaps, ignoring quadrant selection
                full_side_df = side_df

                # 1. Grid Density Map
                st.subheader("1. Unit Grid Density (Yield Loss)")
                st.markdown("Visualizes defect counts per logical unit cell. Darker cells indicate higher yield loss.")
                fig_grid = create_unit_grid_heatmap(full_side_df, panel_rows, panel_cols)
                st.plotly_chart(fig_grid, use_container_width=True)

                st.divider()

                # 2. Contour / Hotspot Map
                st.subheader("2. Smoothed Defect Density (Hotspots)")
                st.markdown("Identifies high-density clusters using physical coordinates. Good for seeing 'clouds' of defects.")
                fig_hex = create_density_contour_map(full_side_df, panel_rows, panel_cols)
                st.plotly_chart(fig_hex, use_container_width=True)

                st.divider()

                # 3. High-Res Coordinate Density
                st.subheader("3. Coordinate Density Raster")
                st.markdown("A pixelated view of defect accumulation based on precise X/Y coordinates.")
                fig_raster = create_hexbin_density_map(full_side_df, panel_rows, panel_cols)
                st.plotly_chart(fig_raster, use_container_width=True)

            elif view_mode == ViewMode.INSIGHTS.value:
                st.header(f"Insights & Flow Analysis - Layer {st.session_state.selected_layer} - Quadrant: {quadrant_selection}")

                # 1. Sunburst Chart
                st.subheader("1. Defect Composition Hierarchy")
                st.markdown("Breakdown: Defect Type → Verification Status")
                sunburst_fig = create_defect_sunburst(display_df)
                st.plotly_chart(sunburst_fig, use_container_width=True)

                st.divider()

                # 2. Sankey Diagram (Only if verification data exists)
                st.subheader("2. Defect Verification Flow")
                st.markdown("Flow from **Defect Type** to **Verification Status**. Helps tune AOI sensitivity.")
                sankey_fig = create_defect_sankey(display_df)
                if sankey_fig:
                    st.plotly_chart(sankey_fig, use_container_width=True)
                else:
                    st.info("Sankey diagram requires Verification data. Please upload data with a 'Verification' column.")

            elif view_mode == ViewMode.SUMMARY.value:
                st.header(f"Statistical Summary for Layer {st.session_state.selected_layer}, Quadrant: {quadrant_selection}")
                if display_df.empty:
                    st.info("No defects to summarize in the selected quadrant.")
                    return
                # Helper set for safe values check
                safe_values_upper = {v.upper() for v in SAFE_VERIFICATION_VALUES}

                if quadrant_selection != Quadrant.ALL.value:
                    total_defects = len(display_df)
                    total_cells = panel_rows * panel_cols
                    defect_density = total_defects / total_cells if total_cells > 0 else 0

                    # For yield calculations, we need the full layer data (all sides)
                    full_layer_df = pd.concat(layer_info.values(), ignore_index=True)
                    yield_df = full_layer_df[full_layer_df['QUADRANT'] == quadrant_selection]

                    # Logic: True defect if NOT in safe list
                    true_yield_defects = yield_df[~yield_df['Verification'].str.upper().isin(safe_values_upper)]
                    combined_defective_cells = len(true_yield_defects[['UNIT_INDEX_X', 'UNIT_INDEX_Y']].drop_duplicates())
                    yield_estimate = (total_cells - combined_defective_cells) / total_cells if total_cells > 0 else 0

                    # For the displayed metric, only count true defects on the selected side
                    selected_side_yield_df = display_df[display_df['QUADRANT'] == quadrant_selection]
                    true_defects_selected_side = selected_side_yield_df[~selected_side_yield_df['Verification'].str.upper().isin(safe_values_upper)]
                    defective_cells_selected_side = len(true_defects_selected_side[['UNIT_INDEX_X', 'UNIT_INDEX_Y']].drop_duplicates())

                    st.markdown("### Key Performance Indicators (KPIs)")
                    col1, col2, col3, col4 = st.columns(4)
                    col1.metric("Total Defect Count", f"{total_defects:,}")
                    col2.metric("True Defective Cells", f"{defective_cells_selected_side:,}")
                    col3.metric("Defect Density", f"{defect_density:.2f} defects/cell")
                    col4.metric("Yield Estimate", f"{yield_estimate:.2%}")
                    st.divider()
                    st.markdown("### Top Defect Types")

                    # Check if verification data exists (using the flag from the first row)
                    has_verification = display_df['HAS_VERIFICATION_DATA'].iloc[0] if not display_df.empty and 'HAS_VERIFICATION_DATA' in display_df.columns else False

                    if has_verification:
                         # Group by both Defect Type and Verification Status
                        top_offenders = display_df.groupby(['DEFECT_TYPE', 'Verification']).size().reset_index(name='Count')
                        top_offenders.rename(columns={'DEFECT_TYPE': 'Defect Type'}, inplace=True)
                        top_offenders = top_offenders.sort_values(by='Count', ascending=False).reset_index(drop=True)
                    else:
                        # Standard grouping by Defect Type only
                        top_offenders = display_df['DEFECT_TYPE'].value_counts().reset_index()
                        top_offenders.columns = ['Defect Type', 'Count']

                    top_offenders['Percentage'] = (top_offenders['Count'] / total_defects) * 100
                    theme_cmap = mcolors.LinearSegmentedColormap.from_list("theme_cmap", [PLOT_AREA_COLOR, PANEL_COLOR])
                    st.dataframe(top_offenders.style.format({'Percentage': '{:.2f}%'}).background_gradient(cmap=theme_cmap, subset=['Count']), use_container_width=True)
                else:
                    st.markdown("### Panel-Wide KPIs (Filtered)")
                    total_defects = len(display_df)
                    total_cells = (panel_rows * panel_cols) * 4
                    defect_density = total_defects / total_cells if total_cells > 0 else 0

                    # For yield calculations, we need the full layer data (all sides)
                    full_layer_df = pd.concat(layer_info.values(), ignore_index=True)
                    # Logic: True defect if NOT in safe list
                    true_yield_defects = full_layer_df[~full_layer_df['Verification'].str.upper().isin(safe_values_upper)]
                    combined_defective_cells = len(true_yield_defects[['UNIT_INDEX_X', 'UNIT_INDEX_Y']].drop_duplicates())
                    yield_estimate = (total_cells - combined_defective_cells) / total_cells if total_cells > 0 else 0

                    # For the displayed metric, only count true defects on the selected side
                    true_defects_selected_side = display_df[~display_df['Verification'].str.upper().isin(safe_values_upper)]
                    defective_cells_selected_side = len(true_defects_selected_side[['UNIT_INDEX_X', 'UNIT_INDEX_Y']].drop_duplicates())

                    col1, col2, col3, col4 = st.columns(4)
                    col1.metric("Filtered Defect Count", f"{total_defects:,}")
                    col2.metric("True Defective Cells", f"{defective_cells_selected_side:,}")
                    col3.metric("Filtered Defect Density", f"{defect_density:.2f} defects/cell")
                    col4.metric("Filtered Yield Estimate", f"{yield_estimate:.2%}")
                    st.divider()
                    st.markdown("### Quarterly KPI Breakdown")
                    kpi_data = []
                    quadrants = ['Q1', 'Q2', 'Q3', 'Q4']
                    total_cells_per_quad = panel_rows * panel_cols
                    for quad in quadrants:
                        quad_view_df = filtered_df[filtered_df['QUADRANT'] == quad]
                        total_quad_defects = len(quad_view_df)

                        # For yield calculations, we need the full layer data (all sides)
                        full_layer_df = pd.concat(layer_info.values(), ignore_index=True)
                        yield_df = full_layer_df[full_layer_df['QUADRANT'] == quad]
                        # Logic: True defect if NOT in safe list
                        true_yield_defects = yield_df[~yield_df['Verification'].str.upper().isin(safe_values_upper)]
                        combined_defective_cells = len(true_yield_defects[['UNIT_INDEX_X', 'UNIT_INDEX_Y']].drop_duplicates())
                        yield_estimate = (total_cells_per_quad - combined_defective_cells) / total_cells_per_quad if total_cells_per_quad > 0 else 0

                        # For the displayed metric, only count true defects on the selected side
                        selected_side_yield_df = quad_view_df[~quad_view_df['Verification'].str.upper().isin(safe_values_upper)]
                        defective_cells_selected_side = len(selected_side_yield_df[['UNIT_INDEX_X', 'UNIT_INDEX_Y']].drop_duplicates())

                        # Count "Safe" (Non-Defects) and "True" (Defects) for the breakdown
                        # Since labels can be anything, we aggregate into two main buckets: "True Defect" and "Non-Defect (Safe)"
                        safe_count = len(quad_view_df[quad_view_df['Verification'].str.upper().isin(safe_values_upper)])
                        true_count = total_quad_defects - safe_count

                        kpi_data.append({
                            "Quadrant": quad,
                            "Total Points": total_quad_defects,
                            "True Defects": true_count,
                            "Non-Defects (Safe)": safe_count,
                            "True Defective Cells": defective_cells_selected_side,
                            "Yield": f"{yield_estimate:.2%}"
                        })
                    if kpi_data:
                        kpi_df = pd.DataFrame(kpi_data)
                        st.dataframe(kpi_df, use_container_width=True)
                    else:
                        st.info("No data to display for the quarterly breakdown based on current filters.")
    else:
        st.header("Welcome to the Panel Defect Analysis Tool!")
        st.info("To get started, upload an Excel file or use the default sample data, then click 'Run Analysis'.")

if __name__ == '__main__':
    main()