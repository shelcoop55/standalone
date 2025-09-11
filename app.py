"""
Main Application File for the Defect Analysis Streamlit Dashboard.
This version implements a true-to-scale simulation of a 510x510mm physical panel.
It includes the Defect Map, Pareto Chart, and a Summary View.
"""
import streamlit as st
import plotly.graph_objects as go
import pandas as pd
import matplotlib.colors as mcolors

# Import our modularized functions
from src.config import BACKGROUND_COLOR, PLOT_AREA_COLOR, GRID_COLOR, TEXT_COLOR, PANEL_COLOR
from src.data_handler import load_data, QUADRANT_WIDTH, QUADRANT_HEIGHT, PANEL_WIDTH, PANEL_HEIGHT
from src.plotting import (
    create_grid_shapes, create_defect_traces,
    create_pareto_trace, create_grouped_pareto_trace
)
from src.reporting import generate_excel_report

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
    st.markdown(f"""
        <style>
            .reportview-container {{ background-color: {BACKGROUND_COLOR}; }}
            .sidebar .sidebar-content {{ background-color: #2E2E2E; border-right: 2px solid #4A4A4A; box-shadow: 5px 0px 15px rgba(0,0,0,0.3); }}
            h1 {{ text-align: center; padding-bottom: 20px; }}
            body, h2, h3, .stRadio, .stSelectbox, .stNumberInput {{ color: {TEXT_COLOR}; }}
            .stDownloadButton > button, div[data-testid="stFormSubmitButton"] button {{ background-color: {PANEL_COLOR}; color: #FFFFFF; border: 1px solid #000000; font-weight: bold; }}
            .stDownloadButton > button:hover, div[data-testid="stFormSubmitButton"] button:hover {{ background-color: #d48c46; color: #FFFFFF; border: 1px solid #FFFFFF; }}
            .st-emotion-cache-1g8w9s4 p {{ color: #A0A0A0; font-size: 16px; }}
            .st-emotion-cache-fplge9 div {{ font-size: 32px; color: {PANEL_COLOR}; font-weight: bold; }}
        </style>
    """, unsafe_allow_html=True)

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
                # --- The physical gap is fixed at 10mm as requested ---
                gap_size = 10
            submitted = st.form_submit_button("🚀 Run Analysis")

        st.divider()
        with st.expander("📊 Analysis Controls", expanded=True):
            view_mode = st.radio("Select View",["Defect View", "Pareto View", "Summary View"], help="Choose the primary analysis view.", disabled=st.session_state.get('full_df') is None)
            quadrant_selection = st.selectbox("Select Quadrant", ["All", "Q1", "Q2", "Q3", "Q4"], help="Filter data to a specific quadrant of the panel.", disabled=st.session_state.get('full_df') is None)

        st.divider()
        with st.expander("📥 Reporting", expanded=True):
            st.download_button(
                label="Download Full Report", data=st.session_state.report_bytes if st.session_state.report_bytes is not None else b"",
                file_name="full_defect_report.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                disabled=st.session_state.report_bytes is None
            )

    st.title("📊 Panel Defect Analysis Tool")
    st.markdown("<br>", unsafe_allow_html=True)

    if submitted:
        with st.spinner("Loading and analyzing data..."):
            full_df = load_data(uploaded_files, panel_rows, panel_cols, gap_size)
            st.session_state.full_df = full_df
            st.session_state.analysis_params = {"panel_rows": panel_rows, "panel_cols": panel_cols, "gap_size": gap_size, "lot_number": lot_number}
            if not full_df.empty:
                source_filenames = [f.name for f in uploaded_files] if uploaded_files else ["Sample Data"]
                excel_report_bytes = generate_excel_report(full_df, panel_rows, panel_cols, ", ".join(source_filenames))
                st.session_state.report_bytes = excel_report_bytes
            else:
                st.session_state.report_bytes = None
            st.rerun()

    if st.session_state.full_df is not None:
        full_df = st.session_state.full_df
        params = st.session_state.analysis_params
        panel_rows, panel_cols = params.get("panel_rows", 7), params.get("panel_cols", 7)
        gap_size, lot_number = params.get("gap_size", 10), params.get("lot_number", "")

        if full_df.empty:
            st.error("The loaded data is empty or invalid. Please check the source file and try again.")
            return

        display_df = full_df[full_df['QUADRANT'] == quadrant_selection] if quadrant_selection != "All" else full_df

        # --- VIEW 1: DEFECT MAP ---
        if view_mode == "Defect View":
            fig = go.Figure()
            defect_traces = create_defect_traces(display_df)
            for trace in defect_traces: fig.add_trace(trace)

            total_width = PANEL_WIDTH + gap_size
            total_height = PANEL_HEIGHT + gap_size
            
            plot_shapes = create_grid_shapes(panel_rows, panel_cols, gap_size, quadrant_selection)
            
            cell_width = QUADRANT_WIDTH / panel_cols
            cell_height = QUADRANT_HEIGHT / panel_rows
            x_tick_vals_q1 = [(i * cell_width) + (cell_width / 2) for i in range(panel_cols)]
            x_tick_vals_q2 = [(QUADRANT_WIDTH + gap_size) + (i * cell_width) + (cell_width / 2) for i in range(panel_cols)]
            x_tick_vals = x_tick_vals_q1 + x_tick_vals_q2
            y_tick_vals_q1 = [(i * cell_height) + (cell_height / 2) for i in range(panel_rows)]
            y_tick_vals_q3 = [(QUADRANT_HEIGHT + gap_size) + (i * cell_height) + (cell_height / 2) for i in range(panel_rows)]
            y_tick_vals = y_tick_vals_q1 + y_tick_vals_q3
            x_tick_text = list(range(panel_cols * 2))
            y_tick_text = list(range(panel_rows * 2))

            fig.update_layout(
                title=dict(text=f"Panel Defect Map - Quadrant: {quadrant_selection} ({len(display_df)} Defects)", font=dict(color=TEXT_COLOR), x=0.5, xanchor='center'),
                xaxis=dict(title="Unit Column Index", title_font=dict(color=TEXT_COLOR), tickfont=dict(color=TEXT_COLOR), tickvals=x_tick_vals if quadrant_selection == "All" else [], ticktext=x_tick_text if quadrant_selection == "All" else [], range=[-gap_size, total_width + gap_size], showgrid=False, zeroline=False, showline=True, linewidth=3, linecolor=GRID_COLOR, mirror=True),
                yaxis=dict(title="Unit Row Index", title_font=dict(color=TEXT_COLOR), tickfont=dict(color=TEXT_COLOR), tickvals=y_tick_vals if quadrant_selection == "All" else [], ticktext=y_tick_text if quadrant_selection == "All" else [], range=[-gap_size, total_height + gap_size], scaleanchor="x", scaleratio=1, showgrid=False, zeroline=False, showline=True, linewidth=3, linecolor=GRID_COLOR, mirror=True),
                plot_bgcolor=PLOT_AREA_COLOR, paper_bgcolor=BACKGROUND_COLOR, shapes=plot_shapes,
                legend=dict(title_font=dict(color=TEXT_COLOR), font=dict(color=TEXT_COLOR), x=1.02, y=1, xanchor='left', yanchor='top'),
                hoverlabel=dict(bgcolor="#4A4A4A", font_size=14, font_family="sans-serif"),
                height=800
            )
            
            if lot_number and quadrant_selection == "All":
                fig.add_annotation(x=total_width, y=total_height, text=f"<b>Lot #: {lot_number}</b>", showarrow=False, font=dict(size=14, color=TEXT_COLOR), align="right", xanchor="right", yanchor="bottom")
            
            st.plotly_chart(fig, use_container_width=True)

        # --- VIEW 2: PARETO CHART ---
        elif view_mode == "Pareto View":
            st.subheader(f"Defect Pareto - Quadrant: {quadrant_selection}")
            fig = go.Figure()
            pareto_trace = create_pareto_trace(display_df)
            fig.add_trace(pareto_trace)

            fig.update_layout(
                xaxis=dict(title="Defect Type", categoryorder='total descending', title_font=dict(color=TEXT_COLOR), tickfont=dict(color=TEXT_COLOR)),
                yaxis=dict(title="Count", title_font=dict(color=TEXT_COLOR), tickfont=dict(color=TEXT_COLOR)),
                plot_bgcolor=PLOT_AREA_COLOR, paper_bgcolor=BACKGROUND_COLOR,
                height=800
            )
            st.plotly_chart(fig, use_container_width=True)
        
        # --- VIEW 3: SUMMARY ---
        elif view_mode == "Summary View":
            st.subheader(f"Data Summary - Quadrant: {quadrant_selection}")

            col1, col2 = st.columns(2)
            with col1:
                st.metric("Total Defects in Selection", len(display_df))
            with col2:
                total_units_in_selection = (panel_rows * panel_cols) if quadrant_selection != "All" else (panel_rows * panel_cols * 4)
                if total_units_in_selection > 0:
                    st.metric("Defect Density (Defects per Unit)", f"{len(display_df)/total_units_in_selection:.2f}")

            st.divider()
            
            with st.expander("Defect Counts by Type", expanded=True):
                counts_by_type = display_df['DEFECT_TYPE'].value_counts().reset_index()
                counts_by_type.columns = ['Defect Type', 'Count']
                st.dataframe(counts_by_type, use_container_width=True)

            # Always show full panel counts by quadrant for context
            with st.expander("Defect Counts by Quadrant", expanded=True):
                counts_by_quad = full_df['QUADRANT'].value_counts().reset_index()
                counts_by_quad.columns = ['Quadrant', 'Count']
                st.dataframe(counts_by_quad, use_container_width=True)

    else:
        st.header("Welcome to the Panel Defect Analysis Tool!")
        st.info("To get started, upload an Excel file or use the default sample data, then click 'Run Analysis'.")

if __name__ == '__main__':
    main()