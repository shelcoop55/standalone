import streamlit as st
import pandas as pd
from src.analysis.base import AnalysisTool
from src.plotting.renderers.maps import create_spatial_grid_heatmap
from src.views.utils import get_geometry_context
from src.core.config import PNG_EXPORT_SCALE, PNG_EXPORT_WIDTH, PNG_EXPORT_HEIGHT

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

        # 6. View mode: Aggregated (one heatmap) or Per layer (one heatmap per layer)
        view_mode = st.session_state.get("heatmap_view_mode", "Aggregated")

        # --- DATA PREPARATION (CACHED) ---
        panel_id = getattr(self.store.layer_data, "id", "static")
        current_theme = st.session_state.get("plot_theme", None)
        ctx = get_geometry_context(self.store)

        if view_mode == "Aggregated":
            combined_heatmap_df = get_filtered_heatmap_data(
                self.store.layer_data,
                panel_id,
                selected_layer_nums,
                side_selection,
                selected_verifs,
                selected_quadrant
            )
            if not combined_heatmap_df.empty:
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

                # --- Downloads that use the currently rendered figure ---
                try:
                    png_bytes = fig.to_image(
                        format="png",
                        engine="kaleido",
                        scale=PNG_EXPORT_SCALE,
                        width=PNG_EXPORT_WIDTH,
                        height=PNG_EXPORT_HEIGHT,
                    )
                    st.download_button(
                        label="Download heatmap (PNG)",
                        data=png_bytes,
                        file_name="heatmap.png",
                        mime="image/png",
                    )
                except Exception:
                    st.warning("PNG export unavailable in this environment.")

                html_str = fig.to_html(full_html=True, include_plotlyjs='cdn')
                st.download_button(
                    label="Download heatmap (HTML, interactive)",
                    data=html_str,
                    file_name="heatmap.html",
                    mime="text/html",
                )
            else:
                st.warning("No data available for the selected filters.")
        else:
            # Per layer: one heatmap per selected layer (Option B)
            any_shown = False
            for layer_num in sorted(selected_layer_nums):
                layer_df = get_filtered_heatmap_data(
                    self.store.layer_data,
                    panel_id,
                    [layer_num],
                    side_selection,
                    selected_verifs,
                    selected_quadrant
                )
                if layer_df.empty:
                    continue
                any_shown = True
                st.subheader(f"Layer {layer_num}")
                fig = create_spatial_grid_heatmap(
                    layer_df,
                    ctx=ctx,
                    bin_size_mm=bin_size_mm,
                    real_defects_only=real_defects_only,
                    use_density=use_density,
                    theme_config=current_theme,
                    zmax_override=zmax_override,
                )
                st.plotly_chart(fig, use_container_width=True)

                # Per-layer downloads
                try:
                    png_bytes = fig.to_image(
                        format="png",
                        engine="kaleido",
                        scale=PNG_EXPORT_SCALE,
                        width=PNG_EXPORT_WIDTH,
                        height=PNG_EXPORT_HEIGHT,
                    )
                    st.download_button(
                        label=f"Download Layer {layer_num} (PNG)",
                        data=png_bytes,
                        file_name=f"heatmap_layer_{layer_num}.png",
                        mime="image/png",
                        key=f"download_heatmap_png_layer_{layer_num}",
                    )
                except Exception:
                    st.warning(f"PNG export unavailable for Layer {layer_num}.")

                html_str = fig.to_html(full_html=True, include_plotlyjs='cdn')
                st.download_button(
                    label=f"Download Layer {layer_num} (HTML)",
                    data=html_str,
                    file_name=f"heatmap_layer_{layer_num}.html",
                    mime="text/html",
                    key=f"download_heatmap_html_layer_{layer_num}",
                )
            if not any_shown:
                st.warning("No data available for the selected filters.")
