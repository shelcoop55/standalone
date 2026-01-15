import streamlit as st
import pandas as pd
from src.analysis.base import AnalysisTool
from src.plotting import create_density_contour_map

class HeatmapTool(AnalysisTool):
    @property
    def name(self) -> str:
        return "Heatmap Analysis"

    def render_sidebar(self):
        # Legacy sidebar rendering, kept empty or redirecting to new UI
        pass

    def render_main(self):
        st.header("Heatmap Analysis")
        st.info("Visualizing smoothed defect density across selected layers.")

        params = self.store.analysis_params
        panel_rows, panel_cols = params.get("panel_rows", 7), params.get("panel_cols", 7)

        # READ INPUTS FROM UNIFIED FILTER STATE (set in manager.py)

        # 1. Layers (Multi-Select)
        # manager.py stores this in self.store.multi_layer_selection (List[int])
        selected_layer_nums = self.store.multi_layer_selection or self.store.layer_data.get_all_layer_nums()

        # 2. Side (Pills: List of selected sides)
        # manager.py stores key "analysis_side_pills" in session state (List[str]).
        side_selection = st.session_state.get("analysis_side_pills", ["Front", "Back"])

        # 3. Verification
        # manager.py stores in key "multi_verification_selection"
        # We need to filter by this.
        selected_verifs = st.session_state.get("multi_verification_selection", [])

        # 4. Smoothing (Context Specific)
        smoothing = st.session_state.get("heatmap_sigma", 5) # Slider from manager.py
        saturation = 0 # Removed from context UI, default 0 or add if needed.

        # 5. View Mode
        view_mode = st.session_state.get("map_view_mode", "Quarterly")

        # --- DATA PREPARATION ---
        dfs_to_concat = []

        for layer_num in selected_layer_nums:
            layer_dict = self.store.layer_data.get(layer_num, {})

            sides_to_process = []
            if "Front" in side_selection: sides_to_process.append('F')
            if "Back" in side_selection: sides_to_process.append('B')

            for side in sides_to_process:
                if side in layer_dict:
                    df = layer_dict[side]
                    if not df.empty:
                        # Apply Verification Filter
                        if 'Verification' in df.columns and selected_verifs:
                             # If "All" is selected? No, list is explicit values.
                             # If logic is inclusion:
                             df_filtered = df[df['Verification'].astype(str).isin(selected_verifs)]
                             dfs_to_concat.append(df_filtered)
                        else:
                             dfs_to_concat.append(df)

        combined_heatmap_df = pd.DataFrame()
        if dfs_to_concat:
            combined_heatmap_df = pd.concat(dfs_to_concat, ignore_index=True)

        if not combined_heatmap_df.empty:
            contour_fig = create_density_contour_map(
                combined_heatmap_df, panel_rows, panel_cols,
                show_points=False,
                smoothing_factor=smoothing * 5, # Scale slider 1-20 to meaningful param
                saturation_cap=saturation,
                show_grid=False,
                view_mode=view_mode
            )
            st.plotly_chart(contour_fig, use_container_width=True)
        else:
            st.warning("No data available for the selected filters.")
