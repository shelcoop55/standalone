import streamlit as st
import pandas as pd
from src.state import SessionStore
from src.analytics.yield_analysis import prepare_multi_layer_data
from src.plotting.renderers.maps import create_multi_layer_defect_map
from src.core.config import GAP_SIZE

def render_multi_layer_view(store: SessionStore, selected_layers: list, selected_sides: list, theme_config=None):
    # Header removed to save space
    # st.header("Multi-Layer Combined Defect Map")
    # st.info("Visualizing 'True Defects' from selected layers. Colors indicate the source layer.")

    params = store.analysis_params
    panel_rows, panel_cols = params.get("panel_rows", 7), params.get("panel_cols", 7)
    panel_uid = store.layer_data.id

    combined_df = prepare_multi_layer_data(store.layer_data)

    # --- Unified Filter Adaptation ---
    # selected_layers is passed from manager.py (store.multi_layer_selection)
    # selected_sides logic in manager.py provides: Front, Back, Both.

    # Updated: Now using `analysis_side_pills` which is a LIST of strings ["Front", "Back"]
    side_pills = st.session_state.get("analysis_side_pills", ["Front", "Back"])
    effective_sides = []
    if "Front" in side_pills: effective_sides.append('F')
    if "Back" in side_pills: effective_sides.append('B')

    # Verification Filter
    selected_verifs = st.session_state.get("multi_verification_selection", [])

    if not combined_df.empty:
        # 1. Layer Filter
        if selected_layers:
            combined_df = combined_df[combined_df['LAYER_NUM'].isin(selected_layers)]
        else: combined_df = pd.DataFrame()

        # 2. Side Filter (Using unified radio state)
        if not combined_df.empty and effective_sides:
             combined_df = combined_df[combined_df['SIDE'].isin(effective_sides)]
        elif not effective_sides: combined_df = pd.DataFrame()

        # 3. Verification Filter
        if not combined_df.empty and 'Verification' in combined_df.columns and selected_verifs:
             combined_df = combined_df[combined_df['Verification'].astype(str).isin(selected_verifs)]

    if not combined_df.empty:
        # Pass the Flip Toggle state
        flip_back = st.session_state.get("flip_back_side", True)
        offset_x = params.get("offset_x", 0.0)
        offset_y = params.get("offset_y", 0.0)
        gap_x = params.get("gap_x", GAP_SIZE)
        gap_y = params.get("gap_y", GAP_SIZE)
        panel_width = params.get("panel_width", 410)
        panel_height = params.get("panel_height", 452)
        visual_origin_x = params.get("visual_origin_x", 0.0)
        visual_origin_y = params.get("visual_origin_y", 0.0)
        fixed_offset_x = params.get("fixed_offset_x", 0.0)
        fixed_offset_y = params.get("fixed_offset_y", 0.0)

        fig = create_multi_layer_defect_map(
            combined_df, panel_rows, panel_cols,
            flip_back=flip_back,
            offset_x=offset_x, offset_y=offset_y,
            gap_x=gap_x, gap_y=gap_y,
            panel_width=panel_width, panel_height=panel_height,
            theme_config=theme_config,
            visual_origin_x=visual_origin_x,
            visual_origin_y=visual_origin_y,
            fixed_offset_x=fixed_offset_x,
            fixed_offset_y=fixed_offset_y
        )
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.warning("No data matches current filters.")
