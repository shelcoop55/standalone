import streamlit as st
import pandas as pd
from src.analysis.base import AnalysisTool
from src.plotting import create_density_contour_map
from src.config import PANEL_WIDTH, PANEL_HEIGHT, GAP_SIZE, QUADRANT_WIDTH, QUADRANT_HEIGHT

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

        # 4. Smoothing (Context Specific)
        smoothing = st.session_state.get("heatmap_sigma", 5) # Slider from manager.py
        saturation = 0 # Removed from context UI, default 0 or add if needed.

        # 5. View Mode
        view_mode = "Continuous"

        # 6. Quadrant Filter
        selected_quadrant = st.session_state.get("analysis_quadrant_selection", "All")

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
                             df = df[df['Verification'].astype(str).isin(selected_verifs)]

                        # Apply Quadrant Filter
                        # The dataframe should have 'QUADRANT' column.
                        if selected_quadrant != "All" and 'QUADRANT' in df.columns:
                             df = df[df['QUADRANT'] == selected_quadrant]

                        if not df.empty:
                             dfs_to_concat.append(df)

        combined_heatmap_df = pd.DataFrame()
        if dfs_to_concat:
            combined_heatmap_df = pd.concat(dfs_to_concat, ignore_index=True)

        if not combined_heatmap_df.empty:
            flip_back = st.session_state.get("flip_back_side", True)
            contour_fig = create_density_contour_map(
                combined_heatmap_df, panel_rows, panel_cols,
                show_points=False,
                smoothing_factor=smoothing * 5, # Scale slider 1-20 to meaningful param
                saturation_cap=saturation,
                show_grid=False,
                view_mode=view_mode,
                flip_back=flip_back,
                quadrant_selection=selected_quadrant
            )

            # --- INTERACTIVITY: CLICK TO ZOOM ---
            # Enable selection events to capture clicks
            selection = st.plotly_chart(contour_fig, use_container_width=True, on_select="rerun", selection_mode="points")

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
                        # Q1: Left-Bottom (in Plotly Y is usually Up, need to check if 0 is bottom or top)
                        # src/plotting.py origins:
                        # Q1: (0, 0)
                        # Q2: (QUAD_W + GAP, 0)
                        # Q3: (0, QUAD_H + GAP)
                        # Q4: (QUAD_W + GAP, QUAD_H + GAP)

                        # Note: Y-Axis in Plotly usually points UP by default for Scatter/Contour unless reversed.
                        # Our data_handler uses logic where Y=0 is one edge.
                        # Let's assume standard Euclidean: 0,0 is bottom-left.

                        is_left = click_x < QUADRANT_WIDTH
                        is_right = click_x > (QUADRANT_WIDTH + GAP_SIZE)

                        is_bottom = click_y < QUADRANT_HEIGHT
                        is_top = click_y > (QUADRANT_HEIGHT + GAP_SIZE)

                        if is_left and is_bottom: clicked_quad = "Q1"
                        elif is_right and is_bottom: clicked_quad = "Q2"
                        elif is_left and is_top: clicked_quad = "Q3"
                        elif is_right and is_top: clicked_quad = "Q4"

                        if clicked_quad:
                            st.session_state["analysis_quadrant_selection"] = clicked_quad
                            st.rerun()

        else:
            st.warning("No data available for the selected filters.")
