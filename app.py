"""
Main Application File for the Defect Analysis Streamlit Dashboard.
This version implements a true-to-scale simulation of a 510x510mm physical panel.
It includes the Defect Map, Pareto Chart, and a Summary View.
CORRECTED: Re-implements the zoom-to-quadrant functionality.
"""
import streamlit as st
import plotly.graph_objects as go
import pandas as pd
import matplotlib.colors as mcolors

# Import our modularized functions
from src.config import BACKGROUND_COLOR, PLOT_AREA_COLOR, GRID_COLOR, TEXT_COLOR, PANEL_COLOR, GAP_SIZE
from src.data_handler import load_data, QUADRANT_WIDTH, QUADRANT_HEIGHT, PANEL_WIDTH, PANEL_HEIGHT
from src.plotting import (
    create_grid_shapes, create_defect_traces,
    create_pareto_trace, create_grouped_pareto_trace
)
from src.reporting import generate_excel_report
from src.enums import ViewMode, Quadrant

def load_css(file_path: str) -> None:
    """Loads a CSS file and injects it into the Streamlit app."""
    with open(file_path) as f:
        css = f.read()
        # Define CSS variables from Python config
        css_variables = f"""
        <style>
            :root {{
                --background-color: {BACKGROUND_COLOR};
                --text-color: {TEXT_COLOR};
                --panel-color: {PANEL_COLOR};
                --panel-hover-color: #d48c46;
            }}
            {css}
        </style>
        """
        st.markdown(css_variables, unsafe_allow_html=True)

# ==============================================================================
# --- STREAMLIT APP MAIN LOGIC ---
# ==============================================================================

def main() -> None:
    """
    Main function to configure and run the Streamlit application.
    """
    # --- App Configuration ---
    st.set_page_config(layout="wide", page_title="Panel Defect Analysis")

    # --- Apply Custom CSS for a Professional UI ---
    load_css("assets/styles.css")

    # --- Initialize Session State ---
    if 'report_bytes' not in st.session_state: st.session_state.report_bytes = None
    if 'full_df' not in st.session_state: st.session_state.full_df = None
    if 'analysis_params' not in st.session_state: st.session_state.analysis_params = {}

    # --- Sidebar Control Panel ---
    with st.sidebar:
        st.title("🎛️ Control Panel")
        with st.form(key="analysis_form"):
            with st.expander("📁 Data Source & Configuration", expanded=True):
                uploaded_files = st.file_uploader("Upload Your Defect Data (Excel)", type=["xlsx", "xls"], accept_multiple_files=True)
                panel_rows = st.number_input("Panel Rows", min_value=1, value=7, help="Number of vertical units in a single quadrant.")
                panel_cols = st.number_input("Panel Columns", min_value=1, value=7, help="Number of horizontal units in a single quadrant.")
                lot_number = st.text_input("Lot Number (Optional)", help="Enter the Lot Number to display it on the defect map.")
            submitted = st.form_submit_button("🚀 Run Analysis")

        st.divider()
        with st.expander("📊 Analysis Controls", expanded=True):
            view_mode = st.radio("Select View", ViewMode.values(), help="Choose the primary analysis view.", disabled=st.session_state.get('full_df') is None)
            quadrant_selection = st.selectbox("Select Quadrant", Quadrant.values(), help="Filter data to a specific quadrant of the panel.", disabled=st.session_state.get('full_df') is None)

            # --- New Verification Filter ---
            verification_options = []
            df = st.session_state.get('full_df')
            # Check if df exists, is not empty, and has the 'Verification' column
            if df is not None and not df.empty and 'Verification' in df.columns:
                verification_options = sorted(df['Verification'].unique().tolist())

            verification_selection = st.multiselect(
                "Filter by Verification Status",
                options=verification_options,
                default=verification_options,
                help="Filter defects by their verification status (e.g., T, F, T-).",
                disabled=not verification_options  # Disable if no options are available
            )

        st.divider()
        with st.expander("📥 Reporting", expanded=True):
            report_disabled = st.session_state.get('full_df') is None or st.session_state.full_df.empty

            if st.button("Generate Report for Download", disabled=report_disabled):
                with st.spinner("Generating Excel report..."):
                    # Re-apply filters here to get the correct df for the report
                    full_df = st.session_state.full_df

                    # 1. Apply Verification Status Filter
                    report_df = full_df[full_df['Verification'].isin(verification_selection)]

                    # 2. Apply Quadrant Filter
                    report_df = report_df[report_df['QUADRANT'] == quadrant_selection] if quadrant_selection != Quadrant.ALL.value else report_df

                    params = st.session_state.analysis_params
                    source_filenames = report_df['SOURCE_FILE'].unique().tolist()

                    excel_bytes = generate_excel_report(
                        full_df=report_df,
                        panel_rows=params.get("panel_rows", 7),
                        panel_cols=params.get("panel_cols", 7),
                        source_filename=", ".join(source_filenames)
                    )
                    st.session_state.report_bytes = excel_bytes
                    st.rerun()

            st.download_button(
                label="Download Full Report",
                data=st.session_state.report_bytes if st.session_state.report_bytes is not None else b"",
                file_name="full_defect_report.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                disabled=st.session_state.report_bytes is None,
                help="Click 'Generate Report' first to enable download."
            )

    st.title("📊 Panel Defect Analysis Tool")
    st.markdown("<br>", unsafe_allow_html=True)

    if submitted:
        with st.spinner("Loading and analyzing data..."):
            full_df = load_data(uploaded_files, panel_rows, panel_cols)
            st.session_state.full_df = full_df
            st.session_state.analysis_params = {"panel_rows": panel_rows, "panel_cols": panel_cols, "gap_size": GAP_SIZE, "lot_number": lot_number}
            # Reset report bytes on new analysis
            st.session_state.report_bytes = None
            st.rerun()

    if st.session_state.full_df is not None:
        full_df = st.session_state.full_df
        params = st.session_state.analysis_params
        panel_rows, panel_cols = params.get("panel_rows", 7), params.get("panel_cols", 7)
        lot_number = params.get("lot_number", "")

        if full_df.empty:
            st.error("The loaded data is empty or invalid. Please check the source file and try again.")
            return

        # --- Apply Filters ---
        # 1. Apply Verification Status Filter first on the full dataset
        filtered_df = full_df[full_df['Verification'].isin(verification_selection)]

        # 2. Apply Quadrant Filter on the already-filtered data
        display_df = filtered_df[filtered_df['QUADRANT'] == quadrant_selection] if quadrant_selection != Quadrant.ALL.value else filtered_df

        # --- VIEW 1: DEFECT MAP ---
        if view_mode == ViewMode.DEFECT.value:
            fig = go.Figure()
            defect_traces = create_defect_traces(display_df)
            for trace in defect_traces: fig.add_trace(trace)
            
            plot_shapes = create_grid_shapes(panel_rows, panel_cols, quadrant_selection)

            # --- *** FIX STARTS HERE: Define ranges for all quadrants and conditionally set them *** ---
            
            # 1. Define the physical axis ranges for each quadrant
            q1_x_range = [0, QUADRANT_WIDTH]
            q1_y_range = [0, QUADRANT_HEIGHT]
            q2_x_range = [QUADRANT_WIDTH + GAP_SIZE, PANEL_WIDTH + GAP_SIZE]
            q2_y_range = [0, QUADRANT_HEIGHT]
            q3_x_range = [0, QUADRANT_WIDTH]
            q3_y_range = [QUADRANT_HEIGHT + GAP_SIZE, PANEL_HEIGHT + GAP_SIZE]
            q4_x_range = [QUADRANT_WIDTH + GAP_SIZE, PANEL_WIDTH + GAP_SIZE]
            q4_y_range = [QUADRANT_HEIGHT + GAP_SIZE, PANEL_HEIGHT + GAP_SIZE]

            # 2. Set the plot's axis range and tick visibility based on the user's selection
            if quadrant_selection == Quadrant.ALL.value:
                x_axis_range = [-GAP_SIZE, PANEL_WIDTH + GAP_SIZE]
                y_axis_range = [-GAP_SIZE, PANEL_HEIGHT + GAP_SIZE]
                show_ticks = True
            else:
                show_ticks = False # Hide tick labels in zoom view for clarity
                if quadrant_selection == Quadrant.Q1.value:
                    x_axis_range, y_axis_range = q1_x_range, q1_y_range
                elif quadrant_selection == Quadrant.Q2.value:
                    x_axis_range, y_axis_range = q2_x_range, q2_y_range
                elif quadrant_selection == Quadrant.Q3.value:
                    x_axis_range, y_axis_range = q3_x_range, q3_y_range
                else: # Q4
                    x_axis_range, y_axis_range = q4_x_range, q4_y_range
            
            # --- *** FIX ENDS HERE *** ---

            cell_width = QUADRANT_WIDTH / panel_cols
            cell_height = QUADRANT_HEIGHT / panel_rows
            x_tick_vals_q1 = [(i * cell_width) + (cell_width / 2) for i in range(panel_cols)]
            x_tick_vals_q2 = [(QUADRANT_WIDTH + GAP_SIZE) + (i * cell_width) + (cell_width / 2) for i in range(panel_cols)]
            x_tick_vals = x_tick_vals_q1 + x_tick_vals_q2
            y_tick_vals_q1 = [(i * cell_height) + (cell_height / 2) for i in range(panel_rows)]
            y_tick_vals_q3 = [(QUADRANT_HEIGHT + GAP_SIZE) + (i * cell_height) + (cell_height / 2) for i in range(panel_rows)]
            y_tick_vals = y_tick_vals_q1 + y_tick_vals_q3
            x_tick_text = list(range(panel_cols * 2))
            y_tick_text = list(range(panel_rows * 2))

            fig.update_layout(
                title=dict(text=f"Panel Defect Map - Quadrant: {quadrant_selection} ({len(display_df)} Defects)", font=dict(color=TEXT_COLOR), x=0.5, xanchor='center'),
                xaxis=dict(title="Unit Column Index", title_font=dict(color=TEXT_COLOR), tickfont=dict(color=TEXT_COLOR), tickvals=x_tick_vals if show_ticks else [], ticktext=x_tick_text if show_ticks else [], range=x_axis_range, showgrid=False, zeroline=False, showline=True, linewidth=3, linecolor=GRID_COLOR, mirror=True),
                yaxis=dict(title="Unit Row Index", title_font=dict(color=TEXT_COLOR), tickfont=dict(color=TEXT_COLOR), tickvals=y_tick_vals if show_ticks else [], ticktext=y_tick_text if show_ticks else [], range=y_axis_range, scaleanchor="x", scaleratio=1, showgrid=False, zeroline=False, showline=True, linewidth=3, linecolor=GRID_COLOR, mirror=True),
                plot_bgcolor=PLOT_AREA_COLOR, paper_bgcolor=BACKGROUND_COLOR, shapes=plot_shapes,
                legend=dict(title_font=dict(color=TEXT_COLOR), font=dict(color=TEXT_COLOR), x=1.02, y=1, xanchor='left', yanchor='top'),
                hoverlabel=dict(bgcolor="#4A4A4A", font_size=14, font_family="sans-serif"),
                height=800
            )
            
            if lot_number and quadrant_selection == Quadrant.ALL.value:
                fig.add_annotation(x=PANEL_WIDTH + GAP_SIZE, y=PANEL_HEIGHT + GAP_SIZE, text=f"<b>Lot #: {lot_number}</b>", showarrow=False, font=dict(size=14, color=TEXT_COLOR), align="right", xanchor="right", yanchor="bottom")
            
            st.plotly_chart(fig, use_container_width=True)

        # --- VIEW 2: PARETO CHART ---
        elif view_mode == ViewMode.PARETO.value:
            st.subheader(f"Defect Pareto - Quadrant: {quadrant_selection}")
            fig = go.Figure()
            
            if quadrant_selection == Quadrant.ALL.value:
                # Show grouped pareto for the full panel view
                pareto_traces = create_grouped_pareto_trace(display_df)
                for trace in pareto_traces:
                    fig.add_trace(trace)
                fig.update_layout(barmode='stack')
            else:
                # Show a simple pareto for a single quadrant
                pareto_trace = create_pareto_trace(display_df)
                fig.add_trace(pareto_trace)

            fig.update_layout(
                xaxis=dict(title="Defect Type", categoryorder='total descending', title_font=dict(color=TEXT_COLOR), tickfont=dict(color=TEXT_COLOR)),
                yaxis=dict(title="Count", title_font=dict(color=TEXT_COLOR), tickfont=dict(color=TEXT_COLOR)),
                plot_bgcolor=PLOT_AREA_COLOR, paper_bgcolor=BACKGROUND_COLOR,
                legend=dict(title_font=dict(color=TEXT_COLOR), font=dict(color=TEXT_COLOR)),
                height=600
            )
            st.plotly_chart(fig, use_container_width=True)
        
        # --- VIEW 3: SUMMARY ---
        elif view_mode == ViewMode.SUMMARY.value:
            # Replaced with the provided Summary View block (clean)
            st.header(f"Statistical Summary for Quadrant: {quadrant_selection}")

            if display_df.empty:
                st.info("No defects to summarize in the selected quadrant.")
                return

            if quadrant_selection != Quadrant.ALL.value:
                total_defects = len(display_df)
                total_cells = panel_rows * panel_cols
                defective_cells = len(display_df[['UNIT_INDEX_X', 'UNIT_INDEX_Y']].drop_duplicates())
                defect_density = total_defects / total_cells if total_cells > 0 else 0
                yield_estimate = (total_cells - defective_cells) / total_cells if total_cells > 0 else 0

                st.markdown("### Key Performance Indicators (KPIs)")
                col1, col2, col3 = st.columns(3)
                col1.metric("Total Defect Count", f"{total_defects:,}")
                col2.metric("Defect Density", f"{defect_density:.2f} defects/cell")
                col3.metric("Yield Estimate", f"{yield_estimate:.2%}")

                st.divider()
                st.markdown("### Top Defect Types")
                top_offenders = display_df['DEFECT_TYPE'].value_counts().reset_index()
                top_offenders.columns = ['Defect Type', 'Count']
                top_offenders['Percentage'] = (top_offenders['Count'] / total_defects) * 100

                theme_cmap = mcolors.LinearSegmentedColormap.from_list("theme_cmap", [PLOT_AREA_COLOR, PANEL_COLOR])

                st.dataframe(
                    top_offenders.style.format({'Percentage': '{:.2f}%'}).background_gradient(cmap=theme_cmap, subset=['Count']),
                    width='stretch'
                )

            else:
                st.markdown("### Quarterly KPI Breakdown")

                kpi_data = []
                quadrants = ['Q1', 'Q2', 'Q3', 'Q4']
                for quad in quadrants:
                    quad_df = full_df[full_df['QUADRANT'] == quad]
                    total_defects = len(quad_df)
                    density = total_defects / (panel_rows * panel_cols) if (panel_rows * panel_cols) > 0 else 0
                    kpi_data.append({"Quadrant": quad, "Total Defects": total_defects, "Defect Density": f"{density:.2f}"})

                kpi_df = pd.DataFrame(kpi_data)
                st.dataframe(kpi_df, width='stretch')

                st.divider()
                st.markdown("### Defect Distribution by Quadrant")
                fig = go.Figure()
                grouped_traces = create_grouped_pareto_trace(full_df)
                for trace in grouped_traces: 
                    fig.add_trace(trace)

                fig.update_layout(
                    title=dict(text="Defect Count by Type and Quadrant", font=dict(color=TEXT_COLOR)),
                    barmode='group',
                    xaxis=dict(title="Defect Type", title_font=dict(color=TEXT_COLOR), tickfont=dict(color=TEXT_COLOR)),
                    yaxis=dict(title="Count", title_font=dict(color=TEXT_COLOR), tickfont=dict(color=TEXT_COLOR)),
                    plot_bgcolor=PLOT_AREA_COLOR,
                    paper_bgcolor=BACKGROUND_COLOR,
                    legend=dict(font=dict(color=TEXT_COLOR)),
                    height=600
                )
                st.plotly_chart(fig, use_container_width=True)


    else:
        st.header("Welcome to the Panel Defect Analysis Tool!")
        st.info("To get started, upload an Excel file or use the default sample data, then click 'Run Analysis'.")

if __name__ == '__main__':
    main()
