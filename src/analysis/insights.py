import streamlit as st
import pandas as pd
from src.analysis.base import AnalysisTool
from src.plotting import create_defect_sunburst, create_defect_sankey, create_trend_chart

class InsightsTool(AnalysisTool):
    @property
    def name(self) -> str:
        return "Insights & Sankey"

    def render_sidebar(self):
        pass

    def render_main(self):
        # Header removed to save space
        # st.header("Insights & Sankey View")

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
                    # Create a copy to avoid modifying the cached object
                    df_layer = layer.data.copy()
                    df_layer['LAYER_NUM'] = layer_num
                    df_layer['SIDE'] = s
                    dfs.append(df_layer)

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

                # --- NEW TREND CHART ---
                st.subheader("Layer-wise Defect Trend")
                trend_chart = create_trend_chart(combined_df)
                st.plotly_chart(trend_chart, use_container_width=True)
                st.divider()

                c1, c2 = st.columns([2, 1], gap="medium")

                with c1:
                    st.plotly_chart(create_defect_sunburst(combined_df), use_container_width=True)

                with c2:
                    st.markdown("##### Defect Statistics")
                    # Calculate Stats
                    total_defects = len(combined_df)
                    stats_data = []

                    if 'DEFECT_TYPE' in combined_df.columns:
                        defect_counts = combined_df['DEFECT_TYPE'].value_counts()

                        for defect_type, count in defect_counts.items():
                            percent_total = (count / total_defects) * 100

                            # False Rate Calculation
                            # False defined as Verification in ['N', 'False', 'GE57']
                            false_criteria = ['N', 'False', 'GE57']

                            sub_df = combined_df[combined_df['DEFECT_TYPE'] == defect_type]
                            if 'Verification' in sub_df.columns:
                                # Normalize to string to be safe
                                false_count = sub_df[sub_df['Verification'].astype(str).isin(false_criteria)].shape[0]
                                false_rate = (false_count / count) * 100
                            else:
                                false_rate = 0.0

                            stats_data.append({
                                "Defect Type": defect_type,
                                "Count": f"{count} ({percent_total:.1f}%)",
                                "False Rate": f"{false_rate:.1f}%"
                            })

                    if stats_data:
                        stats_df = pd.DataFrame(stats_data)
                        st.dataframe(
                            stats_df,
                            hide_index=True,
                            use_container_width=True,
                            column_config={
                                "Defect Type": st.column_config.TextColumn("Type"),
                                "Count": st.column_config.TextColumn("Count (% Total)"),
                                "False Rate": st.column_config.TextColumn("False Rate (N/False/GE57)")
                            }
                        )
                    else:
                        st.info("No defect type data available.")

                sankey = create_defect_sankey(combined_df)
                if sankey:
                    st.plotly_chart(sankey, use_container_width=True)
            else:
                st.warning("No data after filtering.")
        else:
            st.warning("No data selected.")
