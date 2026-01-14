import streamlit as st
import pandas as pd
import matplotlib.colors as mcolors
from src.state import SessionStore
from src.enums import ViewMode, Quadrant
from src.plotting import create_defect_map_figure, create_pareto_figure
from src.config import SAFE_VERIFICATION_VALUES, PLOT_AREA_COLOR, PANEL_COLOR

def render_layer_view(store: SessionStore, view_mode: str, quadrant_selection: str, verification_selection: any):
    params = store.analysis_params
    panel_rows, panel_cols = params.get("panel_rows", 7), params.get("panel_cols", 7)
    lot_number = params.get("lot_number")

    selected_layer_num = store.selected_layer
    if selected_layer_num:
        layer_info = store.layer_data.get(selected_layer_num, {})
        side_df = layer_info.get(store.selected_side)

        if side_df is not None and not side_df.empty:
            # Handle list-based verification (from multiselect) or single string
            if isinstance(verification_selection, list):
                if not verification_selection:
                    # Case: Empty Selection -> Standard UX is show nothing, but in this app context,
                    # previously 'All' was default. If user deselects everything, it's safer to show nothing (filtering everything out)
                    # OR we can assume it means "Show All" if that's preferred.
                    # Given the manager.py sets default to ALL options, an empty list means explicit Deselect All.
                    # Thus, we should return empty DF (or filter out everything).
                    # But wait, manager.py says "default to all if empty or first load".
                    # If I explicitly click 'x' on all tags, list becomes [].
                    # Let's stick to strict filtering: [] -> matches nothing.
                    filtered_df = side_df[side_df['Verification'].isin([])]
                else:
                    filtered_df = side_df[side_df['Verification'].isin(verification_selection)]
            else:
                 # Legacy single select support
                 filtered_df = side_df[side_df['Verification'] == verification_selection] if verification_selection != 'All' else side_df

            display_df = filtered_df[filtered_df['QUADRANT'] == quadrant_selection] if quadrant_selection != Quadrant.ALL.value else filtered_df

            if view_mode == ViewMode.DEFECT.value:
                fig = create_defect_map_figure(display_df, panel_rows, panel_cols, quadrant_selection, lot_number)
                st.plotly_chart(fig, use_container_width=True)
            elif view_mode == ViewMode.PARETO.value:
                fig = create_pareto_figure(display_df, quadrant_selection)
                st.plotly_chart(fig, use_container_width=True)
            elif view_mode == ViewMode.SUMMARY.value:
                # Pass necessary context to the summary view
                render_summary_view(
                    display_df=display_df,
                    quadrant_selection=quadrant_selection,
                    panel_rows=panel_rows,
                    panel_cols=panel_cols,
                    layer_info=layer_info,
                    selected_layer_num=selected_layer_num,
                    filtered_df=filtered_df # Passed for Quarterly breakdown logic
                )

def render_summary_view(
    display_df: pd.DataFrame,
    quadrant_selection: str,
    panel_rows: int,
    panel_cols: int,
    layer_info: dict,
    selected_layer_num: int,
    filtered_df: pd.DataFrame
):
    """
    Renders the detailed Statistical Summary Dashboard.
    Logic restored from user request.
    """
    st.header(f"Statistical Summary for Layer {selected_layer_num}, Quadrant: {quadrant_selection}")

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
        # layer_info values are DFs (or objects we can extract DFs from)
        full_layer_dfs = []
        for val in layer_info.values():
            if hasattr(val, 'data'): # Handle BuildUpLayer object
                full_layer_dfs.append(val.data)
            else:
                full_layer_dfs.append(val)

        full_layer_df = pd.concat(full_layer_dfs, ignore_index=True)
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
        full_layer_dfs = []
        for val in layer_info.values():
            if hasattr(val, 'data'):
                full_layer_dfs.append(val.data)
            else:
                full_layer_dfs.append(val)
        full_layer_df = pd.concat(full_layer_dfs, ignore_index=True)

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

        # We need the full layer df for per-quadrant yield calc
        full_layer_df_static = full_layer_df.copy()

        for quad in quadrants:
            quad_view_df = filtered_df[filtered_df['QUADRANT'] == quad]
            total_quad_defects = len(quad_view_df)

            # For yield calculations
            yield_df = full_layer_df_static[full_layer_df_static['QUADRANT'] == quad]

            # Logic: True defect if NOT in safe list
            true_yield_defects = yield_df[~yield_df['Verification'].str.upper().isin(safe_values_upper)]
            combined_defective_cells = len(true_yield_defects[['UNIT_INDEX_X', 'UNIT_INDEX_Y']].drop_duplicates())
            yield_estimate = (total_cells_per_quad - combined_defective_cells) / total_cells_per_quad if total_cells_per_quad > 0 else 0

            # For the displayed metric, only count true defects on the selected side
            selected_side_yield_df = quad_view_df[~quad_view_df['Verification'].str.upper().isin(safe_values_upper)]
            defective_cells_selected_side = len(selected_side_yield_df[['UNIT_INDEX_X', 'UNIT_INDEX_Y']].drop_duplicates())

            # Count "Safe" (Non-Defects) and "True" (Defects) for the breakdown
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
