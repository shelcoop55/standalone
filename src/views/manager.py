import streamlit as st
from typing import List, Optional
import pandas as pd
from src.state import SessionStore
from src.utils import get_bu_name_from_filename
from src.enums import ViewMode, Quadrant
from src.views.still_alive import render_still_alive_main
from src.views.multi_layer import render_multi_layer_view
from src.views.layer_view import render_layer_view
from src.analysis import get_analysis_tool

class ViewManager:
    """
    Manages view routing and navigation components.
    Decouples UI layout from application logic.
    """
    def __init__(self, store: SessionStore):
        self.store = store

    def render_navigation(self):
        """
        Renders the top navigation controls.
        Specific logic for 'Layer Inspection' view where we show Layer/Side/Quadrant/Verification controls.
        """
        if not self.store.layer_data:
            return

        if self.store.active_view == 'layer':
            self._render_layer_inspection_controls()
            st.divider()
        else:
            self._render_analysis_page_controls()
            st.divider()

    def _render_layer_inspection_controls(self):
        """Renders the top control row for Layer Inspection."""

        # Prepare Data for Dropdowns
        layer_keys = sorted(self.store.layer_data.keys())
        if not layer_keys:
            return

        # Layer Options
        layer_options = []
        layer_option_map = {}
        for num in layer_keys:
            # Try to get BU name
            bu_name = ""
            try:
                first_side_key = next(iter(self.store.layer_data[num]))
                source_file = self.store.layer_data[num][first_side_key]['SOURCE_FILE'].iloc[0]
                bu_name = get_bu_name_from_filename(str(source_file))
            except (IndexError, AttributeError, StopIteration):
                pass
            label = f"Layer {num}: {bu_name}" if bu_name else f"Layer {num}"
            layer_options.append(label)
            layer_option_map[label] = num

        # Determine Current Layer Index
        current_layer_idx = 0
        if self.store.selected_layer:
             for i, opt in enumerate(layer_options):
                 if layer_option_map[opt] == self.store.selected_layer:
                     current_layer_idx = i
                     break

        # Prepare Data for Side Toggle
        # Default options
        side_options = ["Front", "Back"]
        current_side_label = "Front" if self.store.selected_side == 'F' else "Back"

        # Prepare Data for Verification
        active_df = pd.DataFrame()
        if self.store.selected_layer:
            layer_info = self.store.layer_data.get(self.store.selected_layer, {})
            active_df = layer_info.get(self.store.selected_side, pd.DataFrame())

        ver_options = ['All'] + sorted(active_df['Verification'].unique().tolist()) if not active_df.empty and 'Verification' in active_df.columns else ['All']
        current_ver = self.store.verification_selection
        current_ver_idx = ver_options.index(current_ver) if current_ver in ver_options else 0

        # --- Layout: 4 Columns ---
        col1, col2, col3, col4 = st.columns(4)

        # 1. Layer Selection
        with col1:
            def on_layer_change():
                label = st.session_state.layer_selector_top
                layer_num = layer_option_map[label]
                self.store.set_layer_view(layer_num)
                # Auto-select side logic
                layer_info = self.store.layer_data.get(layer_num, {})
                if 'F' in layer_info:
                    self.store.selected_side = 'F'
                elif 'B' in layer_info:
                    self.store.selected_side = 'B'
                elif layer_info:
                     self.store.selected_side = next(iter(layer_info.keys()))

            st.selectbox(
                "Select Layer",
                options=layer_options,
                index=current_layer_idx,
                key="layer_selector_top",
                on_change=on_layer_change,
                label_visibility="collapsed"
            )

        # 2. Side Selection (Front/Back)
        with col2:
            def on_side_change():
                label = st.session_state.side_selector_top
                self.store.selected_side = 'F' if label == "Front" else 'B'

            if hasattr(st, "pills"):
                 st.pills(
                     "Side",
                     side_options,
                     selection_mode="single",
                     default=current_side_label,
                     key="side_selector_top",
                     on_change=on_side_change,
                     label_visibility="collapsed"
                 )
            else:
                 st.radio(
                     "Side",
                     side_options,
                     horizontal=True,
                     key="side_selector_top",
                     on_change=on_side_change,
                     index=side_options.index(current_side_label),
                     label_visibility="collapsed"
                 )

        # 3. Quadrant Selection
        with col3:
            quad_options = Quadrant.values()
            curr_quad = self.store.quadrant_selection
            curr_quad_idx = quad_options.index(curr_quad) if curr_quad in quad_options else 0

            st.selectbox(
                "Quadrant",
                options=quad_options,
                index=curr_quad_idx,
                key="quadrant_selection",
                label_visibility="collapsed",
                on_change=lambda: setattr(self.store, 'quadrant_selection', st.session_state.quadrant_selection)
            )

        # 4. Verification Filter
        with col4:
            st.selectbox(
                "Verification",
                options=ver_options,
                index=current_ver_idx,
                key="verification_selection",
                label_visibility="collapsed",
                on_change=lambda: setattr(self.store, 'verification_selection', st.session_state.verification_selection)
            )

        # --- Tabs for View Mode ---
        st.markdown("") # Spacer
        tab_labels = ["Defect View", "Summary View", "Pareto View"]
        tab_map = {
            "Defect View": ViewMode.DEFECT.value,
            "Summary View": ViewMode.SUMMARY.value,
            "Pareto View": ViewMode.PARETO.value
        }

        current_view = self.store.view_mode
        current_tab = "Defect View"
        for label, val in tab_map.items():
            if val == current_view:
                current_tab = label
                break

        def on_tab_change():
             label = st.session_state.view_mode_selector
             self.store.view_mode = tab_map[label]

        if hasattr(st, "pills"):
            st.pills(
                "",
                tab_labels,
                selection_mode="single",
                default=current_tab,
                key="view_mode_selector",
                on_change=on_tab_change,
                label_visibility="collapsed"
            )
        else:
             st.radio(
                "",
                tab_labels,
                horizontal=True,
                key="view_mode_selector",
                index=tab_labels.index(current_tab),
                on_change=on_tab_change,
                label_visibility="collapsed"
            )

    def _render_analysis_page_controls(self):
        """Renders the Tabs and Context Filters for the Unified Analysis Page."""

        # 1. Top Level Tabs
        tabs = [
            "Heatmap", "Stress Map", "Root Cause", "Insights", "Still Alive", "Multi-Layer"
        ]

        current_tab = "Heatmap"
        if self.store.active_view == 'still_alive':
            current_tab = "Still Alive"
        elif self.store.active_view == 'multi_layer_defects':
            current_tab = "Multi-Layer"
        elif self.store.active_view == 'analysis_dashboard':
             sub_map_rev = {
                 ViewMode.HEATMAP.value: "Heatmap",
                 ViewMode.STRESS.value: "Stress Map",
                 ViewMode.ROOT_CAUSE.value: "Root Cause",
                 ViewMode.INSIGHTS.value: "Insights"
             }
             current_tab = sub_map_rev.get(self.store.analysis_subview, "Heatmap")

        def on_analysis_tab_change():
             sel = st.session_state.analysis_tab_selector
             if not sel:
                 return
             if sel == "Still Alive":
                 self.store.active_view = 'still_alive'
             elif sel == "Multi-Layer":
                 self.store.active_view = 'multi_layer_defects'
             else:
                 self.store.active_view = 'analysis_dashboard'
                 sub_map = {
                     "Heatmap": ViewMode.HEATMAP.value,
                     "Stress Map": ViewMode.STRESS.value,
                     "Root Cause": ViewMode.ROOT_CAUSE.value,
                     "Insights": ViewMode.INSIGHTS.value
                 }
                 self.store.analysis_subview = sub_map[sel]

        st.subheader("Analysis View")
        if hasattr(st, "pills"):
             st.pills(
                 "Analysis Modules",
                 tabs,
                 selection_mode="single",
                 default=current_tab,
                 key="analysis_tab_selector",
                 on_change=on_analysis_tab_change,
                 label_visibility="collapsed"
             )
        else:
             st.radio(
                 "Analysis Modules",
                 tabs,
                 horizontal=True,
                 key="analysis_tab_selector",
                 index=tabs.index(current_tab),
                 on_change=on_analysis_tab_change,
                 label_visibility="collapsed"
             )

        st.divider()

        # 2. Filter Rows (Context Aware)
        # Order: Layer -> Side -> Verification (Inspection)

        all_layers = sorted(self.store.layer_data.keys())

        full_df = self.store.layer_data.get_combined_dataframe()
        all_verifications = []
        if not full_df.empty and 'Verification' in full_df.columns:
            all_verifications = sorted(full_df['Verification'].dropna().astype(str).unique().tolist())

        # Move Verification Filter to Sidebar
        with st.sidebar:
             st.divider()
             st.markdown("### Analysis Filters")
             default_ver = st.session_state.get('multi_verification_selection', all_verifications)
             st.multiselect(
                 "Filter Verification Status",
                 options=all_verifications,
                 default=default_ver,
                 key="multi_verification_selection"
             )

        col_f1, col_f2 = st.columns([2, 1])

        # Filter 1: Multi-Select Layer
        with col_f1:
             st.multiselect(
                 "Select Layers",
                 options=all_layers,
                 default=self.store.multi_layer_selection if self.store.multi_layer_selection else all_layers,
                 key="analysis_layer_select",
                 on_change=lambda: setattr(self.store, 'multi_layer_selection', st.session_state.analysis_layer_select)
             )

        # Filter 2: Side Radio (Front/Back) - MOVED to Middle as requested
        with col_f2:
             st.radio(
                 "Side",
                 ["Front", "Back", "Both"],
                 index=2, # Default Both
                 horizontal=True,
                 key="analysis_side_select"
             )

        # 3. Context Specific Row
        current_tab_val = current_tab

        if current_tab_val == "Heatmap":
             st.slider("Smoothing (Sigma)", min_value=1, max_value=20, value=5, key="heatmap_sigma")

        elif current_tab_val == "Stress Map":
             st.radio("Mode", ["Cumulative", "Delta Difference"], horizontal=True, key="stress_map_mode")

        elif current_tab_val == "Root Cause":
             c1, c2 = st.columns(2)
             with c1:
                 st.radio("Slice Axis", ["X (Column)", "Y (Row)"], horizontal=True, key="rca_axis")
             with c2:
                 max_idx = (self.store.analysis_params.get('panel_cols', 7) * 2) - 1
                 st.slider("Slice Index", 0, max_idx, 0, key="rca_index")


    def render_main_view(self):
        """Dispatches the rendering to the appropriate view function."""

        if not self.store.layer_data:
             st.info("Please upload data and run analysis to proceed.")
             return

        if self.store.active_view == 'still_alive':
            render_still_alive_main(self.store)

        elif self.store.active_view == 'multi_layer_defects':
            render_multi_layer_view(
                self.store,
                self.store.multi_layer_selection,
                self.store.multi_side_selection
            )

        elif self.store.active_view == 'analysis_dashboard':
            tool = get_analysis_tool(self.store.analysis_subview, self.store)
            tool.render_main()

        elif self.store.active_view == 'layer':
            render_layer_view(
                self.store,
                self.store.view_mode,
                self.store.quadrant_selection,
                self.store.verification_selection
            )
        else:
            st.warning(f"Unknown view: {self.store.active_view}")
