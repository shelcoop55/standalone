import streamlit as st
import pandas as pd
from src.analysis.base import AnalysisTool
from src.plotting import create_defect_sunburst, create_defect_sankey

class InsightsTool(AnalysisTool):
    @property
    def name(self) -> str:
        return "Insights & Sankey"

    def render_sidebar(self):
        pass

    def render_main(self):
        st.header("Insights & Sankey View")

        # User requirement: "When user have selected Insight View He will See First two only [Layer/Verif]"
        # This implies aggregation across selected layers? Or still single layer?
        # The prompt says "First two only because those are the one which is reuired".
        # This strongly implies multi-layer context.
        # But Sunburst/Sankey are typically dense.
        # If I aggregate all selected layers, it might be messy.
        # However, I should respect the selection.

        selected_layer_nums = self.store.multi_layer_selection or self.store.layer_data.get_all_layer_nums()
        side_pills = st.session_state.get("analysis_side_pills", ["Front", "Back"])
        selected_verifs = st.session_state.get("multi_verification_selection", [])
        selected_quadrant = st.session_state.get("analysis_quadrant_selection", "All")

        # Collect Data
        dfs = []
        for layer_num in selected_layer_nums:
            sides = []
            if "Front" in side_pills: sides.append('F')
            if "Back" in side_pills: sides.append('B')

            for s in sides:
                layer = self.store.layer_data.get_layer(layer_num, s)
                if layer and not layer.data.empty:
                    dfs.append(layer.data)

        if dfs:
            combined_df = pd.concat(dfs, ignore_index=True)

            # 1. Filter Verif
            if 'Verification' in combined_df.columns and selected_verifs:
                 combined_df = combined_df[combined_df['Verification'].astype(str).isin(selected_verifs)]

            # 2. Filter Quadrant
            if selected_quadrant != "All" and 'QUADRANT' in combined_df.columns:
                 combined_df = combined_df[combined_df['QUADRANT'] == selected_quadrant]

            if not combined_df.empty:
                st.caption(f"Analyzing {len(combined_df)} defects from selected context.")
                st.plotly_chart(create_defect_sunburst(combined_df), use_container_width=True)
                sankey = create_defect_sankey(combined_df)
                if sankey: st.plotly_chart(sankey, use_container_width=True)
            else:
                st.warning("No data after filtering.")
        else:
            st.warning("No data selected.")
