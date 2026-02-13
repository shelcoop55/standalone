import streamlit as st
import pandas as pd
from src.analysis.base import AnalysisTool
from src.plotting.renderers.maps import create_spatial_grid_heatmap
from src.views.utils import get_geometry_context

@st.cache_data
def get_filtered_heatmap_data(
    _panel_data,
    panel_data_id: str,
    selected_layer_nums: list,
    side_selection: list,
    selected_verifs: list,
    selected_quadrant: str
) -> pd.DataFrame:
    """
    Cached helper to filter and aggregate heatmap data.
    args:
        _panel_data: The PanelData object (not hashed).
        panel_data_id: Unique ID of the dataset (hashed).
        selected_layer_nums: List of layer numbers to include.
        side_selection: List of strings ["Front", "Back"].
        selected_verifs: List of verification codes to include.
        selected_quadrant: Quadrant filter ("All", "Q1", etc.).
    """
    dfs_to_concat = []

    for layer_num in selected_layer_nums:
        # PanelData.get() returns dict of {side: DataFrame}
        layer_dict = _panel_data.get(layer_num, {})

        sides_to_process = []
        if "Front" in side_selection: sides_to_process.append('F')
        if "Back" in side_selection: sides_to_process.append('B')

        for side in sides_to_process:
            if side in layer_dict:
                df = layer_dict[side]
                if not df.empty:
                    # Apply Verification Filter
                    if 'Verification' in df.columns and selected_verifs:
                         df = df[df['Verification'].astype(str).isin(selected_verifs)]

                    # Apply Quadrant Filter
                    if selected_quadrant != "All" and 'QUADRANT' in df.columns:
                         df = df[df['QUADRANT'] == selected_quadrant]

                    if not df.empty:
                         dfs_to_concat.append(df)

    if dfs_to_concat:
        return pd.concat(dfs_to_concat, ignore_index=True)
    return pd.DataFrame()


class HeatmapTool(AnalysisTool):
    @property
    def name(self) -> str:
        return "Heatmap Analysis"

    def render_sidebar(self):
        # Legacy sidebar rendering, kept empty or redirecting to new UI
        pass

    def render_main(self):
        # Header removed to save space
        # st.header("Heatmap Analysis")
        # st.info("Visualizing smoothed defect density across selected layers.")

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

        # 4. Defect set, bin size, color scale - from manager.py
        defect_set_choice = st.session_state.get("heatmap_defect_set", "Real defects only (verification rules)")
        real_defects_only = defect_set_choice == "Real defects only (verification rules)"
        bin_size_mm = float(st.session_state.get("heatmap_bin_size_mm", 10))
        use_density = st.session_state.get("heatmap_color_scale", "Defects per mm²") == "Defects per mm²"
        zmax_override = (
            float(st.session_state.get("heatmap_zmax_density", 1.0))
            if use_density
            else float(st.session_state.get("heatmap_zmax_count", 10))
        )

        # 5. Quadrant Filter
        selected_quadrant = st.session_state.get("analysis_quadrant_selection", "All")

        # --- DATA PREPARATION (CACHED) ---
        # We pass self.store.layer_data.id if available, else a dummy or we assume static.
        # PanelData in models.py has .id attribute.
        panel_id = getattr(self.store.layer_data, "id", "static")

        combined_heatmap_df = get_filtered_heatmap_data(
            self.store.layer_data,
            panel_id,
            selected_layer_nums,
            side_selection,
            selected_verifs,
            selected_quadrant
        )

        if not combined_heatmap_df.empty:
            current_theme = st.session_state.get("plot_theme", None)
            ctx = get_geometry_context(self.store)
            fig = create_spatial_grid_heatmap(
                combined_heatmap_df,
                ctx=ctx,
                bin_size_mm=bin_size_mm,
                real_defects_only=real_defects_only,
                use_density=use_density,
                theme_config=current_theme,
                zmax_override=zmax_override,
            )
            st.plotly_chart(fig, use_container_width=True)

        else:
            st.warning("No data available for the selected filters.")
