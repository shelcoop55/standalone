import streamlit as st
import pandas as pd
from src.analysis.base import AnalysisTool
from src.plotting.renderers.maps import create_density_contour_map, create_unit_grid_heatmap
from src.core.config import PANEL_WIDTH, PANEL_HEIGHT, GAP_SIZE, QUADRANT_WIDTH, QUADRANT_HEIGHT
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

        # 4. Bin size (mm) and gradient (color scale) - from manager.py
        bin_size_mm = float(st.session_state.get("heatmap_bin_size_mm", 15))
        gradient_min = int(st.session_state.get("heatmap_gradient_min", 0))
        gradient_max = int(st.session_state.get("heatmap_gradient_max", 0))  # 0 = Auto

        # New: Toggle for Heatmap Type
        heatmap_type = st.radio(
            "Visualization Type",
            ["Smoothed Contour", "Unit Grid"],
            horizontal=True,
            key="heatmap_viz_type_toggle"
        )

        # 5. View Mode
        view_mode = "Continuous"

        # 6. Quadrant Filter
        selected_quadrant = st.session_state.get("analysis_quadrant_selection", "All")

        # 7. Layout Params
        ctx = get_geometry_context(self.store)
        gap_size = ctx.effective_gap_x # Local alias for compatibility with click logic

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
            # Retrieve Theme
            current_theme = st.session_state.get('plot_theme', None)

            if heatmap_type == "Unit Grid":
                # Render Unit Grid Heatmap (Uses 'Inferno')
                fig = create_unit_grid_heatmap(
                    combined_heatmap_df,
                    panel_rows,
                    panel_cols,
                    theme_config=current_theme
                )
                selection = st.plotly_chart(fig, use_container_width=True, on_select="rerun", selection_mode="points")
            else:
                # Render Smoothed Contour (Uses 'Plasma')
                flip_back = st.session_state.get("flip_back_side", True)
                fig = create_density_contour_map(
                    combined_heatmap_df, panel_rows, panel_cols,
                    ctx=ctx,
                    show_points=False,
                    bin_size_mm=bin_size_mm,
                    zmin=gradient_min,
                    zmax=gradient_max if gradient_max > 0 else None,
                    show_grid=False,
                    view_mode=view_mode,
                    flip_back=flip_back,
                    quadrant_selection=selected_quadrant,
                    theme_config=current_theme
                )

                # --- INTERACTIVITY: CLICK TO ZOOM ---
                # Enable selection events to capture clicks
                selection = st.plotly_chart(fig, use_container_width=True, on_select="rerun", selection_mode="points")

            if selection and selection.selection and selection.selection["points"]:
                # Only process if we are in "All" mode (Drill Down)
                if selected_quadrant == "All":
                    point = selection.selection["points"][0]
                    # Get Physical Coordinates of the click
                    click_x = point.get("x")
                    click_y = point.get("y")

                    if click_x is not None and click_y is not None:
                        # Determine Quadrant
                        clicked_quad = None

                        # Logic matches create_grid_shapes / config.py
                        # Adjusted for Dynamic Offsets and Gap
                        # And Visual Shift!
                        # The click coordinate is already shifted visually if the plot is shifted.
                        # We need to map it back to structure?
                        # Grid shape logic uses `offset_x` (structural).
                        # But grid shape drawing does NOT shift.
                        # Wait, my previous step said "Visual Origin does NOT affect the grid".
                        # So the Grid is physically located at 0-510.
                        # The axis is 0-510.
                        # So `click_x` is relative to the Frame (0-510).
                        # So we compare against structural `offset_x`.

                        # `offset_x` is Structural Start of Q1.

                        # Correct logic:
                        offset_x, offset_y = ctx.offset_x, ctx.offset_y
                        quad_width, quad_height = ctx.quad_width, ctx.quad_height

                        is_left = (click_x >= offset_x) and (click_x < offset_x + quad_width)
                        is_right = (click_x > offset_x + quad_width + gap_size)

                        is_bottom = (click_y >= offset_y) and (click_y < offset_y + quad_height)
                        is_top = (click_y > offset_y + quad_height + gap_size)

                        if is_left and is_bottom: clicked_quad = "Q1"
                        elif is_right and is_bottom: clicked_quad = "Q2"
                        elif is_left and is_top: clicked_quad = "Q3"
                        elif is_right and is_top: clicked_quad = "Q4"

                        if clicked_quad:
                            st.session_state["analysis_quadrant_selection"] = clicked_quad
                            st.rerun()

        else:
            st.warning("No data available for the selected filters.")
