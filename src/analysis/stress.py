import streamlit as st
import pandas as pd
from src.analysis.base import AnalysisTool
from src.enums import ViewMode
from src.plotting import create_stress_heatmap, create_delta_heatmap
from src.data_handler import aggregate_stress_data

class StressMapTool(AnalysisTool):
    @property
    def name(self) -> str:
        return "Stress Map"

    def render_sidebar(self):
        pass

    def render_main(self):
        st.header("Cumulative Stress Map Analysis")
        st.info("Aggregates defects into a master grid. Includes Back-Side alignment.")

        params = self.store.analysis_params
        panel_rows, panel_cols = params.get("panel_rows", 7), params.get("panel_cols", 7)
        panel_uid = self.store.layer_data.id

        # READ INPUTS
        # 1. Mode (Cumulative vs Delta)
        # manager.py stores "stress_map_mode"
        mode = st.session_state.get('stress_mode', 'Cumulative') # From sidebar if legacy? No, use new key
        mode_new = st.session_state.get('stress_map_mode', 'Cumulative')

        # 2. Filters
        selected_layer_nums = self.store.multi_layer_selection or self.store.layer_data.get_all_layer_nums()
        side_selection = st.session_state.get("analysis_side_pills", ["Front", "Back"])
        selected_verifs = st.session_state.get("multi_verification_selection", [])

        # 3. View Mode
        view_mode = st.session_state.get("map_view_mode", "Quarterly")

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

        if mode_new == "Cumulative":
            stress_data = aggregate_stress_data(
                self.store.layer_data, keys, panel_rows, panel_cols, panel_uid,
                verification_filter=selected_verifs
            )
            fig = create_stress_heatmap(stress_data, panel_rows, panel_cols, view_mode=view_mode)

        else: # Delta
            # Delta Difference logic: "When user have selected Stressmap he will see ... 4th would be Delta DIfference"
            # How do we define Group A vs Group B with the unified filters?
            # The unified filter row (Layer/Verif/Side) applies globally.
            # It doesn't allow selecting TWO groups.
            # User Prompt: "When user will have selected Stressmap he will see First two and third one would be Cummulative and 4th would be Delta DIfference"
            # It implies radio button [Cumulative, Delta].
            # But if "Delta" is selected, WHERE does he select Group A and Group B?
            # The prompt says "Below this We will have Filter tabs First two will be used in all Layer Selection List -> Verification List".
            # It doesn't mention separate Group selectors for Delta.
            # Assumption: Delta might be "Front vs Back" (Side Bias)?
            # OR logic is needed to split the selection.
            # If the user interface doesn't provide A/B selectors, I can defaults to:
            # Group A = Selected Layers/Side
            # Group B = ...?
            # Or maybe Delta means Front - Back of selection?
            # Given the constraint, I will implement "Front vs Back" Difference for the selected layers if Delta is chosen.
            # This is a reasonable interpretation if no explicit Group A/B selectors are requested in the new UI.

            keys_f = [k for k in keys if k[1] == 'F']
            keys_b = [k for k in keys if k[1] == 'B']

            stress_data_a = aggregate_stress_data(
                self.store.layer_data, keys_f, panel_rows, panel_cols, panel_uid,
                verification_filter=selected_verifs
            )
            stress_data_b = aggregate_stress_data(
                self.store.layer_data, keys_b, panel_rows, panel_cols, panel_uid,
                verification_filter=selected_verifs
            )

            st.info("Delta Difference Mode: Calculating (Front Side - Back Side) for selected layers.")
            fig = create_delta_heatmap(stress_data_a, stress_data_b, panel_rows, panel_cols, view_mode=view_mode)

        st.plotly_chart(fig, use_container_width=True)
