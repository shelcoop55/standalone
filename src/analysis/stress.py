import streamlit as st
import pandas as pd
from src.analysis.base import AnalysisTool
from src.enums import ViewMode
from src.plotting.renderers.maps import create_stress_heatmap, create_delta_heatmap
from src.analytics.stress import aggregate_stress_data
from src.core.config import GAP_SIZE, PANEL_WIDTH, PANEL_HEIGHT

class StressMapTool(AnalysisTool):
    @property
    def name(self) -> str:
        return "Stress Map"

    def render_sidebar(self):
        pass

    def render_main(self):
        # Header removed to save space
        # st.header("Cumulative Stress Map Analysis")
        # st.info("Aggregates defects into a master grid. Includes Back-Side alignment.")

        params = self.store.analysis_params
        panel_rows, panel_cols = params.get("panel_rows", 7), params.get("panel_cols", 7)
        panel_uid = self.store.layer_data.id

        # READ INPUTS
        # 1. Mode (Cumulative vs Delta)
        # manager.py stores "stress_map_mode"
        mode_new = st.session_state.get('stress_map_mode', 'Cumulative')

        # 2. Filters
        selected_layer_nums = self.store.multi_layer_selection or self.store.layer_data.get_all_layer_nums()
        side_selection = st.session_state.get("analysis_side_pills", ["Front", "Back"])
        selected_verifs = st.session_state.get("multi_verification_selection", [])

        # 3. View Mode
        view_mode = "Continuous"

        # 4. Quadrant Filter
        selected_quadrant = st.session_state.get("analysis_quadrant_selection", "All")

        # Construct Keys (Layer, Side) based on filters
        keys = []
        for layer_num in selected_layer_nums:
            sides_to_process = []
            if "Front" in side_selection: sides_to_process.append('F')
            if "Back" in side_selection: sides_to_process.append('B')

            for side in sides_to_process:
                 # Check if exists in data
                 if self.store.layer_data.get_layer(layer_num, side):
                     keys.append((layer_num, side))

        # Layout Params
        offset_x = params.get("offset_x", 0.0)
        offset_y = params.get("offset_y", 0.0)
        # Use dynamic gaps from params (set in app.py)
        gap_x = params.get("gap_x", GAP_SIZE)
        gap_y = params.get("gap_y", GAP_SIZE)

        # Use panel dimensions from params
        p_width = params.get("panel_width", PANEL_WIDTH)
        p_height = params.get("panel_height", PANEL_HEIGHT)
        visual_origin_x = params.get("visual_origin_x", 0.0)
        visual_origin_y = params.get("visual_origin_y", 0.0)
        fixed_offset_x = params.get("fixed_offset_x", 0.0)
        fixed_offset_y = params.get("fixed_offset_y", 0.0)

        fig = None

        if mode_new == "Cumulative":
             stress_data = aggregate_stress_data(
                self.store.layer_data, keys, panel_rows, panel_cols, panel_uid,
                verification_filter=selected_verifs,
                quadrant_filter=selected_quadrant
            )
             fig = create_stress_heatmap(
                 stress_data, panel_rows, panel_cols, view_mode=view_mode,
                 offset_x=offset_x, offset_y=offset_y, gap_x=gap_x, gap_y=gap_y,
                 panel_width=p_width, panel_height=p_height,
                 visual_origin_x=visual_origin_x, visual_origin_y=visual_origin_y,
                 fixed_offset_x=fixed_offset_x, fixed_offset_y=fixed_offset_y
             )

        elif mode_new == "Delta Difference":
            # Delta Difference logic: "Front vs Back" for selected layers
            keys_f = [k for k in keys if k[1] == 'F']
            keys_b = [k for k in keys if k[1] == 'B']

            stress_data_a = aggregate_stress_data(
                self.store.layer_data, keys_f, panel_rows, panel_cols, panel_uid,
                verification_filter=selected_verifs,
                quadrant_filter=selected_quadrant
            )
            stress_data_b = aggregate_stress_data(
                self.store.layer_data, keys_b, panel_rows, panel_cols, panel_uid,
                verification_filter=selected_verifs,
                quadrant_filter=selected_quadrant
            )

            st.info("Delta Difference Mode: Calculating (Front Side - Back Side) for selected layers.")
            fig = create_delta_heatmap(
                stress_data_a, stress_data_b, panel_rows, panel_cols, view_mode=view_mode,
                offset_x=offset_x, offset_y=offset_y, gap_x=gap_x, gap_y=gap_y,
                panel_width=p_width, panel_height=p_height,
                visual_origin_x=visual_origin_x, visual_origin_y=visual_origin_y,
                fixed_offset_x=fixed_offset_x, fixed_offset_y=fixed_offset_y
            )

        if fig:
            st.plotly_chart(fig, use_container_width=True)
