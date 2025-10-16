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
    ALIVE_CELL_COLOR, DEFECTIVE_CELL_COLOR
)
from src.data_handler import (
    load_data, get_true_defect_coordinates,
    QUADRANT_WIDTH, QUADRANT_HEIGHT, PANEL_WIDTH, PANEL_HEIGHT
)
from src.plotting import (
    create_grid_shapes, create_defect_traces,
    create_pareto_trace, create_grouped_pareto_trace,
    create_verification_status_chart, create_still_alive_map
)
from src.reporting import generate_excel_report, generate_coordinate_list_report
from src.enums import ViewMode, Quadrant
from src.utils import get_bu_name_from_filename

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
                if st.button("Generate Report for Download", disabled=is_still_alive_view, help="Reporting is disabled for the Still Alive view."):
                    with st.spinner("Generating Excel report..."):
                        # For reporting, we want to combine both Front and Back data if available
                        layer_info = st.session_state.layer_data.get(st.session_state.selected_layer, {})
                        if layer_info:
                            all_sides_df = pd.concat(layer_info.values(), ignore_index=True)

                            report_df = all_sides_df
                            if verification_selection != 'All': report_df = report_df[report_df['Verification'] == verification_selection]
                            if quadrant_selection != Quadrant.ALL.value: report_df = report_df[report_df['QUADRANT'] == quadrant_selection]

                            params = st.session_state.analysis_params
                            source_filenames = report_df['SOURCE_FILE'].unique().tolist()

                            excel_bytes = generate_excel_report(
                                full_df=report_df,
                                panel_rows=params.get("panel_rows", 7),
                                panel_cols=params.get("panel_cols", 7),
                                source_filename=", ".join(source_filenames),
                                quadrant_selection=quadrant_selection,
                                verification_selection=verification_selection
                            )
                            st.session_state.report_bytes = excel_bytes
                            st.rerun()

                st.download_button("Download Full Report", data=st.session_state.report_bytes or b"", file_name=f"defect_report_layer_{st.session_state.selected_layer}.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", disabled=st.session_state.report_bytes is None)
        else:
            with st.expander("📊 Analysis Controls", expanded=True):
                st.radio("Select View", ViewMode.values(), disabled=True)
                st.selectbox("Select Quadrant", Quadrant.values(), disabled=True)
                st.radio("Filter by Verification Status", ["All"], disabled=True)
            st.divider()
            with st.expander("📥 Reporting", expanded=True):
                st.button("Generate Report for Download", disabled=True)
                st.download_button("Download Full Report", b"", disabled=True)

    st.title("📊 Panel Defect Analysis Tool")
    st.markdown("<br>", unsafe_allow_html=True)

    if submitted:
        st.session_state.layer_data = load_data(uploaded_files, panel_rows, panel_cols)
        if st.session_state.layer_data:
            st.session_state.selected_layer = max(st.session_state.layer_data.keys())
            st.session_state.active_view = 'layer'
        else:
            st.session_state.selected_layer = None
        st.session_state.analysis_params = {"panel_rows": panel_rows, "panel_cols": panel_cols, "gap_size": GAP_SIZE, "lot_number": lot_number}
        st.session_state.report_bytes = None
        st.rerun()

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
                        # Default to 'F' side when switching layers, if available
                        if 'F' in st.session_state.layer_data.get(layer_num, {}):
                            st.session_state.selected_side = 'F'
                        st.rerun()
            with cols[num_buttons - 1]:
                is_active = st.session_state.active_view == 'still_alive'
                if st.button("Still Alive", key="still_alive_btn", use_container_width=True, type="primary" if is_active else "secondary"):
                    st.session_state.active_view = 'still_alive'
                    st.rerun()

            # --- Side Selection Radio Toggle (only if a layer is selected and has multiple sides) ---
            selected_layer_num = st.session_state.get('selected_layer')
            if selected_layer_num and st.session_state.active_view == 'layer':
                layer_info = st.session_state.layer_data.get(selected_layer_num, {})
                if len(layer_info) > 1:  # More than one side available
                    sorted_sides = sorted(layer_info.keys())
                    side_options = {s: "Front" if s == 'F' else "Back" for s in sorted_sides}

                    selected_side = st.radio(
                        "Select Side",
                        options=list(side_options.keys()),
                        format_func=lambda s: side_options[s],
                        index=list(side_options.keys()).index(st.session_state.selected_side),
                        horizontal=True,
                        key="side_selector"
                    )

                    if selected_side != st.session_state.selected_side:
                        st.session_state.selected_side = selected_side
                        st.rerun()

        st.divider()

        if st.session_state.active_view == 'still_alive':
            st.header("Still Alive Panel Yield Map")
            map_col, summary_col = st.columns([2.5, 1])
            with map_col:
                true_defect_coords = get_true_defect_coordinates(st.session_state.layer_data)
                fig = go.Figure()
                map_shapes = create_still_alive_map(panel_rows, panel_cols, true_defect_coords)
                # Define axis ticks and labels for clarity
                cell_width, cell_height = QUADRANT_WIDTH / panel_cols, QUADRANT_HEIGHT / panel_rows
                x_tick_vals_q1 = [(i * cell_width) + (cell_width / 2) for i in range(panel_cols)]
                x_tick_vals_q2 = [(QUADRANT_WIDTH + GAP_SIZE) + (i * cell_width) + (cell_width / 2) for i in range(panel_cols)]
                y_tick_vals_q1 = [(i * cell_height) + (cell_height / 2) for i in range(panel_rows)]
                y_tick_vals_q3 = [(QUADRANT_HEIGHT + GAP_SIZE) + (i * cell_height) + (cell_height / 2) for i in range(panel_rows)]
                x_tick_text = list(range(panel_cols * 2))
                y_tick_text = list(range(panel_rows * 2))

                fig.update_layout(
                    title=dict(text=f"Still Alive Map ({len(true_defect_coords)} Defective Cells)", font=dict(color=TEXT_COLOR), x=0.5, xanchor='center'),
                    xaxis=dict(
                        title="Unit Column Index", range=[-GAP_SIZE, PANEL_WIDTH + (GAP_SIZE * 2)],
                        tickvals=x_tick_vals_q1 + x_tick_vals_q2, ticktext=x_tick_text,
                        showgrid=False, zeroline=False, showline=True, linewidth=2, linecolor=GRID_COLOR, mirror=True,
                        title_font=dict(color=TEXT_COLOR), tickfont=dict(color=TEXT_COLOR)
                    ),
                    yaxis=dict(
                        title="Unit Row Index", range=[-GAP_SIZE, PANEL_HEIGHT + (GAP_SIZE * 2)],
                        tickvals=y_tick_vals_q1 + y_tick_vals_q3, ticktext=y_tick_text,
                        scaleanchor="x", scaleratio=1, showgrid=False, zeroline=False, showline=True, linewidth=2, linecolor=GRID_COLOR, mirror=True,
                        title_font=dict(color=TEXT_COLOR), tickfont=dict(color=TEXT_COLOR)
                    ),
                    plot_bgcolor=PLOT_AREA_COLOR, paper_bgcolor=BACKGROUND_COLOR, shapes=map_shapes, height=800, margin=dict(l=20, r=20, t=80, b=20)
                )
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
                fig = go.Figure(data=create_defect_traces(display_df))
                fig.update_layout(shapes=create_grid_shapes(panel_rows, panel_cols, quadrant_selection))
                cell_width, cell_height = QUADRANT_WIDTH / panel_cols, QUADRANT_HEIGHT / panel_rows
                x_tick_vals_q1 = [(i * cell_width) + (cell_width / 2) for i in range(panel_cols)]
                x_tick_vals_q2 = [(QUADRANT_WIDTH + GAP_SIZE) + (i * cell_width) + (cell_width / 2) for i in range(panel_cols)]
                y_tick_vals_q1 = [(i * cell_height) + (cell_height / 2) for i in range(panel_rows)]
                y_tick_vals_q3 = [(QUADRANT_HEIGHT + GAP_SIZE) + (i * cell_height) + (cell_height / 2) for i in range(panel_rows)]
                x_tick_text, y_tick_text = list(range(panel_cols * 2)), list(range(panel_rows * 2))
                x_axis_range, y_axis_range, show_ticks = [-GAP_SIZE, PANEL_WIDTH + (GAP_SIZE * 2)], [-GAP_SIZE, PANEL_HEIGHT + (GAP_SIZE * 2)], True
                if quadrant_selection != Quadrant.ALL.value:
                    show_ticks = False
                    ranges = {'Q1': ([0, QUADRANT_WIDTH], [0, QUADRANT_HEIGHT]), 'Q2': ([QUADRANT_WIDTH + GAP_SIZE, PANEL_WIDTH + GAP_SIZE], [0, QUADRANT_HEIGHT]), 'Q3': ([0, QUADRANT_WIDTH], [QUADRANT_HEIGHT + GAP_SIZE, PANEL_HEIGHT + GAP_SIZE]), 'Q4': ([QUADRANT_WIDTH + GAP_SIZE, PANEL_WIDTH + GAP_SIZE], [QUADRANT_HEIGHT + GAP_SIZE, PANEL_HEIGHT + GAP_SIZE])}
                    x_axis_range, y_axis_range = ranges[quadrant_selection]
                fig.update_layout(
                    title=dict(text=f"Panel Defect Map - Layer {st.session_state.selected_layer} - Quadrant: {quadrant_selection} ({len(display_df)} Defects)", font=dict(color=TEXT_COLOR), x=0.5, xanchor='center'),
                    xaxis=dict(title="Unit Column Index", title_font=dict(color=TEXT_COLOR), tickfont=dict(color=TEXT_COLOR), tickvals=x_tick_vals_q1 + x_tick_vals_q2 if show_ticks else [], ticktext=x_tick_text if show_ticks else [], range=x_axis_range, showgrid=False, zeroline=False, showline=True, linewidth=3, linecolor=GRID_COLOR, mirror=True),
                    yaxis=dict(title="Unit Row Index", title_font=dict(color=TEXT_COLOR), tickfont=dict(color=TEXT_COLOR), tickvals=y_tick_vals_q1 + y_tick_vals_q3 if show_ticks else [], ticktext=y_tick_text if show_ticks else [], range=y_axis_range, scaleanchor="x", scaleratio=1, showgrid=False, zeroline=False, showline=True, linewidth=3, linecolor=GRID_COLOR, mirror=True),
                    plot_bgcolor=PLOT_AREA_COLOR, paper_bgcolor=BACKGROUND_COLOR, legend=dict(title_font=dict(color=TEXT_COLOR), font=dict(color=TEXT_COLOR), x=1.02, y=1, xanchor='left', yanchor='top'),
                    hoverlabel=dict(bgcolor="#4A4A4A", font_size=14, font_family="sans-serif"), height=800
                )
                if lot_number and quadrant_selection == Quadrant.ALL.value:
                    fig.add_annotation(x=PANEL_WIDTH + GAP_SIZE, y=PANEL_HEIGHT + GAP_SIZE, text=f"<b>Lot #: {lot_number}</b>", showarrow=False, font=dict(size=14, color=TEXT_COLOR), align="right", xanchor="right", yanchor="bottom")
                st.plotly_chart(fig, use_container_width=True)
            elif view_mode == ViewMode.PARETO.value:
                st.subheader(f"Defect Pareto - Layer {st.session_state.selected_layer} - Quadrant: {quadrant_selection}")
                fig = go.Figure()
                if quadrant_selection == Quadrant.ALL.value:
                    for trace in create_grouped_pareto_trace(display_df): fig.add_trace(trace)
                    fig.update_layout(barmode='stack')
                else:
                    fig.add_trace(create_pareto_trace(display_df))
                fig.update_layout(xaxis=dict(title="Defect Type", categoryorder='total descending'), plot_bgcolor=PLOT_AREA_COLOR, paper_bgcolor=BACKGROUND_COLOR, height=600)
                st.plotly_chart(fig, use_container_width=True)
            elif view_mode == ViewMode.SUMMARY.value:
                st.header(f"Statistical Summary for Layer {st.session_state.selected_layer}, Quadrant: {quadrant_selection}")
                if display_df.empty:
                    st.info("No defects to summarize in the selected quadrant.")
                    return
                if quadrant_selection != Quadrant.ALL.value:
                    total_defects = len(display_df)
                    total_cells = panel_rows * panel_cols
                    defect_density = total_defects / total_cells if total_cells > 0 else 0

                    # For yield calculations, we need the full layer data (all sides)
                    full_layer_df = pd.concat(layer_info.values(), ignore_index=True)
                    quad_yield_df = full_layer_df[full_layer_df['QUADRANT'] == quadrant_selection]
                    true_yield_defects = quad_yield_df[quad_yield_df['Verification'] == 'T']
                    defective_cells = len(true_yield_defects[['UNIT_INDEX_X', 'UNIT_INDEX_Y']].drop_duplicates())
                    yield_estimate = (total_cells - defective_cells) / total_cells if total_cells > 0 else 0

                    st.markdown("### Key Performance Indicators (KPIs)")
                    col1, col2, col3, col4 = st.columns(4)
                    col1.metric("Total Defect Count", f"{total_defects:,}")
                    col2.metric("True Defective Cells", f"{defective_cells:,}")
                    col3.metric("Defect Density", f"{defect_density:.2f} defects/cell")
                    col4.metric("Yield Estimate", f"{yield_estimate:.2%}")
                    st.divider()
                    st.markdown("### Top Defect Types")
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
                    true_yield_defects = full_layer_df[full_layer_df['Verification'] == 'T']
                    defective_cells = len(true_yield_defects[['UNIT_INDEX_X', 'UNIT_INDEX_Y']].drop_duplicates())
                    yield_estimate = (total_cells - defective_cells) / total_cells if total_cells > 0 else 0

                    col1, col2, col3, col4 = st.columns(4)
                    col1.metric("Filtered Defect Count", f"{total_defects:,}")
                    col2.metric("True Defective Cells", f"{defective_cells:,}")
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
                        quad_yield_df = full_layer_df[full_layer_df['QUADRANT'] == quad]
                        true_yield_defects = quad_yield_df[quad_yield_df['Verification'] == 'T']
                        defective_cells = len(true_yield_defects[['UNIT_INDEX_X', 'UNIT_INDEX_Y']].drop_duplicates())
                        yield_estimate = (total_cells_per_quad - defective_cells) / total_cells_per_quad if total_cells_per_quad > 0 else 0

                        verification_counts = quad_view_df['Verification'].value_counts()
                        kpi_data.append({"Quadrant": quad, "Total Defects": total_quad_defects, "True (T)": int(verification_counts.get('T', 0)), "False (F)": int(verification_counts.get('F', 0)), "Acceptable (TA)": int(verification_counts.get('TA', 0)), "True Defective Cells": defective_cells, "Yield": f"{yield_estimate:.2%}"})
                    if kpi_data:
                        kpi_df = pd.DataFrame(kpi_data)
                        kpi_df = kpi_df[['Quadrant', 'Total Defects', 'True (T)', 'False (F)', 'Acceptable (TA)', 'True Defective Cells', 'Yield']]
                        st.dataframe(kpi_df, use_container_width=True)
                    else:
                        st.info("No data to display for the quarterly breakdown based on current filters.")
    else:
        st.header("Welcome to the Panel Defect Analysis Tool!")
        st.info("To get started, upload an Excel file or use the default sample data, then click 'Run Analysis'.")

if __name__ == '__main__':
    main()