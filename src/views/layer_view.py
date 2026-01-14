import streamlit as st
import pandas as pd
from src.state import SessionStore
from src.enums import ViewMode, Quadrant
from src.plotting import create_defect_map_figure, create_pareto_figure

def render_layer_view(store: SessionStore, view_mode: str, quadrant_selection: str, verification_selection: str):
    params = store.analysis_params
    panel_rows, panel_cols = params.get("panel_rows", 7), params.get("panel_cols", 7)
    lot_number = params.get("lot_number")

    selected_layer_num = store.selected_layer
    if selected_layer_num:
        layer_info = store.layer_data.get(selected_layer_num, {})
        side_df = layer_info.get(store.selected_side)

        if side_df is not None and not side_df.empty:
            filtered_df = side_df[side_df['Verification'] == verification_selection] if verification_selection != 'All' else side_df
            display_df = filtered_df[filtered_df['QUADRANT'] == quadrant_selection] if quadrant_selection != Quadrant.ALL.value else filtered_df

            if view_mode == ViewMode.DEFECT.value:
                fig = create_defect_map_figure(display_df, panel_rows, panel_cols, quadrant_selection, lot_number)
                st.plotly_chart(fig, use_container_width=True)
            elif view_mode == ViewMode.PARETO.value:
                fig = create_pareto_figure(display_df, quadrant_selection)
                st.plotly_chart(fig, use_container_width=True)
            elif view_mode == ViewMode.SUMMARY.value:
                render_summary_view(display_df, quadrant_selection)

def render_summary_view(df: pd.DataFrame, quadrant: str):
    """Renders the Summary Dashboard for the current layer."""
    st.subheader(f"Layer Summary - Quadrant: {quadrant}")

    if df.empty:
        st.warning("No data available for summary.")
        return

    # Metrics
    total_defects = len(df)

    # Calculate Yield (Approximate based on defect count vs total units not readily avail here without panel dims, but we have df)
    # We'll just show counts for now.

    col1, col2, col3 = st.columns(3)
    col1.metric("Total Defects", total_defects)

    if 'Verification' in df.columns:
        verified_count = df[df['Verification'] != 'Under Verification'].shape[0]
        col2.metric("Verified Units", verified_count)

    # Top Defect Type
    if not df.empty:
        top_defect = df['DEFECT_TYPE'].mode()
        top_defect_str = top_defect[0] if not top_defect.empty else "N/A"
        col3.metric("Top Defect Type", top_defect_str)

    st.divider()

    # Top 5 Defects Table
    st.markdown("##### Top 5 Defect Types")
    top_5 = df['DEFECT_TYPE'].value_counts().head(5).reset_index()
    top_5.columns = ['Defect Type', 'Count']
    st.dataframe(top_5, use_container_width=True)

    # Simple Bar Chart
    st.markdown("##### Defect Distribution")
    st.bar_chart(df['DEFECT_TYPE'].value_counts())
