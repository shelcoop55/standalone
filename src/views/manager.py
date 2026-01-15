import streamlit as st
from typing import List, Optional
import pandas as pd
from src.state import SessionStore
from src.utils import get_bu_name_from_filename
from src.enums import ViewMode, Quadrant
from src.views.still_alive import render_still_alive_main
from src.views.multi_layer import render_multi_layer_view
from src.views.layer_view import render_layer_view
from src.documentation import render_documentation
from src.analysis import get_analysis_tool
import streamlit.components.v1 as components

class ViewManager:
    """
    Manages view routing and navigation components.
    Decouples UI layout from application logic.
    """
    def __init__(self, store: SessionStore):
        self.store = store

    def render_navigation(self):
        # Inject Keyboard Shortcuts
        with open("src/components/keyboard_shortcuts.html", "r") as f:
            components.html(f.read(), height=0, width=0)

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
            # Use BU name if available (cleaner look), else fallback to Layer Num
            label = bu_name if bu_name else f"Layer {num}"
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

        # Calculate available verification options
        ver_options = []
        if not active_df.empty and 'Verification' in active_df.columns:
            ver_options = sorted(active_df['Verification'].dropna().astype(str).unique().tolist())

        # Move Verification Filter to Sidebar (Unified)
        with st.sidebar:
             st.divider()
             st.markdown("### Analysis Filters")
             # Reuse 'multi_verification_selection' to keep state between views
             # Default to all if empty or first load

             # CRITICAL: Intersection logic to prevent crash when switching views with incompatible options.
             # Streamlit ignores 'default' if 'key' is in session_state, so we must sanitize session_state directly.
             if 'multi_verification_selection' in st.session_state:
                 current_selection = st.session_state['multi_verification_selection']
                 valid_selection = [x for x in current_selection if x in ver_options]
                 st.session_state['multi_verification_selection'] = valid_selection

             # Determine default if no state exists yet
             default_ver = ver_options # Default to all

             st.multiselect(
                 "Filter Verification Status",
                 options=ver_options,
                 default=default_ver,
                 key="multi_verification_selection"
             )

        # Update Store with Multi-Select for Layer View as well
        # Note: Layer view logic needs to handle list instead of string now
        # We don't need to manually set it here, 'multi_verification_selection' key updates session state
        # But we should ensure consistency if the underlying logic uses a different store variable
        # For Layer View, we previously used 'verification_selection' (single).
        # Now we will use 'multi_verification_selection'.
        self.store.verification_selection = st.session_state.get('multi_verification_selection', ver_options)


        # --- Layout: Rows of Buttons ---

        # Header removed to save space
        if layer_options:
            l_cols = st.columns(len(layer_options), gap="small")
            for i, (label, col) in enumerate(zip(layer_options, l_cols)):
                 layer_num = layer_option_map[label]
                 is_active = (layer_num == self.store.selected_layer)

                 def on_layer_click(n):
                     def cb():
                         self.store.set_layer_view(n)
                         # Auto-select side logic
                         info = self.store.layer_data.get(n, {})
                         if 'F' in info:
                             self.store.selected_side = 'F'
                         elif 'B' in info:
                             self.store.selected_side = 'B'
                         elif info:
                             self.store.selected_side = next(iter(info.keys()))
                     return cb

                 col.button(
                     label,
                     key=f"layer_btn_{i}",
                     type="primary" if is_active else "secondary",
                     use_container_width=True,
                     on_click=on_layer_click(layer_num)
                 )

        c1, c2 = st.columns([1, 2], gap="medium")

        # Side Selection
        with c1:
            # Header removed
            s_cols = st.columns(len(side_options), gap="small")
            for i, (label, col) in enumerate(zip(side_options, s_cols)):
                code = 'F' if label == "Front" else 'B'
                is_active = (code == self.store.selected_side)

                def on_side_click(c):
                    def cb():
                        self.store.selected_side = c
                    return cb

                col.button(
                    label,
                    key=f"side_btn_{i}",
                    type="primary" if is_active else "secondary",
                    use_container_width=True,
                    on_click=on_side_click(code)
                )

        # Quadrant Selection
        with c2:
            # Header removed
            quad_options = Quadrant.values()
            q_cols = st.columns(len(quad_options), gap="small")
            for i, (label, col) in enumerate(zip(quad_options, q_cols)):
                is_active = (label == self.store.quadrant_selection)

                def on_quad_click(l):
                    def cb():
                        self.store.quadrant_selection = l
                    return cb

                col.button(
                    label,
                    key=f"quad_btn_{i}",
                    type="primary" if is_active else "secondary",
                    use_container_width=True,
                    on_click=on_quad_click(label)
                )

        # --- Tabs for View Mode (Full Width Buttons) ---
        st.markdown("") # Spacer
        tab_labels = ["Defect View", "Summary View", "Pareto View"]
        tab_map = {
            "Defect View": ViewMode.DEFECT.value,
            "Summary View": ViewMode.SUMMARY.value,
            "Pareto View": ViewMode.PARETO.value
        }

        # Determine active view
        current_view = self.store.view_mode

        # Create columns for full-width buttons
        cols = st.columns(len(tab_labels), gap="small")

        for i, label in enumerate(tab_labels):
            mapped_val = tab_map[label]
            is_active = (mapped_val == current_view)

            # Using callback to update state
            def make_callback(v):
                def cb():
                    self.store.view_mode = v
                return cb

            cols[i].button(
                label,
                key=f"view_mode_btn_{i}",
                type="primary" if is_active else "secondary",
                use_container_width=True,
                on_click=make_callback(mapped_val)
            )

    def _render_analysis_page_controls(self):
        """Renders the Tabs and Context Filters for the Unified Analysis Page."""

        # --- PREPARE DATA ---
        all_layers = sorted(self.store.layer_data.keys())
        full_df = self.store.layer_data.get_combined_dataframe()
        all_verifications = []
        if not full_df.empty and 'Verification' in full_df.columns:
            all_verifications = sorted(full_df['Verification'].dropna().astype(str).unique().tolist())

        # Move Verification Filter to Sidebar (Persistent)
        with st.sidebar:
             st.divider()
             st.markdown("### Analysis Filters")
             # Sanitize selection against available options
             if 'multi_verification_selection' in st.session_state:
                 current_selection = st.session_state['multi_verification_selection']
                 valid_selection = [x for x in current_selection if x in all_verifications]
                 st.session_state['multi_verification_selection'] = valid_selection

             default_ver = all_verifications # Default to all

             st.multiselect(
                 "Filter Verification Status",
                 options=all_verifications,
                 default=default_ver,
                 key="multi_verification_selection"
             )

        # --- ROW 1: GLOBAL FILTERS (Layer -> Side -> Quadrant) ---
        # Headers removed as per request to save space

        # We will try to pack everything into one logical row using columns.
        # Since button widths vary, we can't easily predict the exact column split.
        # We'll group them: [Layer Group] [Side Group] [Quadrant Group]
        # Layout: 4 parts for Layers, 1 for Side, 1 for Quadrant (Total 6)?
        # Or let Streamlit handle it.

        # Prepare Layer Buttons: [ALL, BU-XX, BU-YY...]
        layer_buttons_data = []

        # Logic to get BU Name or Layer Num
        for num in all_layers:
            bu_name = ""
            try:
                first_side_key = next(iter(self.store.layer_data[num]))
                source_file = self.store.layer_data[num][first_side_key]['SOURCE_FILE'].iloc[0]
                bu_name = get_bu_name_from_filename(str(source_file))
            except: pass

            label = bu_name if bu_name else f"Layer {num}"
            layer_buttons_data.append({'num': num, 'label': label})

        # Calculate Total Buttons for Row 1
        # [ALL] + [Layers...] + [Front, Back, Both] + [All, Q1, Q2, Q3, Q4]
        # This is a lot for one row, but user requested wrapping.
        # Streamlit st.columns doesn't wrap.
        # We'll split into 3 chunks to organize: Layers | Sides | Quadrants

        c_layers, c_sides, c_quads = st.columns([3, 1, 1], gap="small")

        # --- Layers Group ---
        with c_layers:
            # We need to emulate a wrapping row for Layers if there are many.
            # Since st.columns doesn't wrap, we might need multiple rows if count is high.
            # Or just use one very dense st.columns list.
            # Let's try putting all layer buttons in one st.columns call.

            # "ALL" button removed as per request to save space
            btns = [d['label'] for d in layer_buttons_data]
            l_cols = st.columns(len(btns), gap="small")

            current_selection = self.store.multi_layer_selection if self.store.multi_layer_selection else all_layers

            # Layer Buttons
            for i, d in enumerate(layer_buttons_data):
                num = d['num']
                is_sel = num in current_selection
                def on_click_layer(n):
                    def cb():
                        new_sel = list(self.store.multi_layer_selection) if self.store.multi_layer_selection else list(all_layers)
                        if n in new_sel:
                            if len(new_sel) > 1: new_sel.remove(n)
                        else: new_sel.append(n)
                        self.store.multi_layer_selection = sorted(new_sel)
                    return cb

                l_cols[i].button(d['label'], key=f"an_btn_l_{num}", type="primary" if is_sel else "secondary", use_container_width=True, on_click=on_click_layer(num))

        # --- Sides Group ---
        with c_sides:
            side_opts = ["Front", "Back", "Both"]
            current_sides = st.session_state.get("analysis_side_pills", ["Front", "Back"])
            s_cols = st.columns(len(side_opts), gap="small")

            def set_sides(l): st.session_state["analysis_side_pills"] = l

            # Front
            is_f = ("Front" in current_sides) and ("Back" not in current_sides)
            s_cols[0].button("Front", key="an_side_f", type="primary" if is_f else "secondary", use_container_width=True, on_click=lambda: set_sides(["Front"]))
            # Back
            is_b = ("Back" in current_sides) and ("Front" not in current_sides)
            s_cols[1].button("Back", key="an_side_b", type="primary" if is_b else "secondary", use_container_width=True, on_click=lambda: set_sides(["Back"]))
            # Both
            is_both = ("Front" in current_sides) and ("Back" in current_sides)
            s_cols[2].button("Both", key="an_side_both", type="primary" if is_both else "secondary", use_container_width=True, on_click=lambda: set_sides(["Front", "Back"]))

        # --- Quadrants Group ---
        with c_quads:
            quad_opts = ["All", "Q1", "Q2", "Q3", "Q4"]
            current_quad = st.session_state.get("analysis_quadrant_selection", "All")
            q_cols = st.columns(len(quad_opts), gap="small")

            def set_quad(q): st.session_state["analysis_quadrant_selection"] = q

            for i, q_label in enumerate(quad_opts):
                is_active = (current_quad == q_label)
                q_cols[i].button(q_label, key=f"an_quad_{q_label}", type="primary" if is_active else "secondary", use_container_width=True, on_click=lambda q=q_label: set_quad(q))

        st.divider()

        # --- ROW 2: ANALYSIS MODULES (Tabs) ---
        tabs = ["Still Alive", "Heatmap", "Stress Map", "Root Cause", "Insights", "Multi-Layer", "Documentation"]

        # Logic to determine active tab text
        current_tab_text = "Heatmap"
        if self.store.active_view == 'still_alive': current_tab_text = "Still Alive"
        elif self.store.active_view == 'multi_layer_defects': current_tab_text = "Multi-Layer"
        elif self.store.active_view == 'documentation': current_tab_text = "Documentation"
        elif self.store.active_view == 'analysis_dashboard':
             sub_map_rev = {
                 ViewMode.HEATMAP.value: "Heatmap",
                 ViewMode.STRESS.value: "Stress Map",
                 ViewMode.ROOT_CAUSE.value: "Root Cause",
                 ViewMode.INSIGHTS.value: "Insights"
             }
             current_tab_text = sub_map_rev.get(self.store.analysis_subview, "Heatmap")

        t_cols = st.columns(len(tabs), gap="small")
        for i, label in enumerate(tabs):
            is_active = (label == current_tab_text)
            def on_tab(sel):
                def cb():
                    if sel == "Still Alive": self.store.active_view = 'still_alive'
                    elif sel == "Multi-Layer": self.store.active_view = 'multi_layer_defects'
                    elif sel == "Documentation": self.store.active_view = 'documentation'
                    else:
                         self.store.active_view = 'analysis_dashboard'
                         sub_map = {"Heatmap": ViewMode.HEATMAP.value, "Stress Map": ViewMode.STRESS.value, "Root Cause": ViewMode.ROOT_CAUSE.value, "Insights": ViewMode.INSIGHTS.value}
                         self.store.analysis_subview = sub_map[sel]
                return cb
            t_cols[i].button(label, key=f"an_tab_{i}", type="primary" if is_active else "secondary", use_container_width=True, on_click=on_tab(label))

        st.divider()

        # --- ROW 3: CONTEXT FILTERS ---
        if current_tab_text == "Heatmap":
             st.slider("Smoothing (Sigma)", min_value=1, max_value=20, value=5, key="heatmap_sigma")

        elif current_tab_text == "Stress Map":
             st.radio("Mode", ["Cumulative", "Delta Difference"], horizontal=True, key="stress_map_mode")

        elif current_tab_text == "Root Cause":
             c1, c2 = st.columns(2)
             with c1: st.radio("Slice Axis", ["X (Column)", "Y (Row)"], horizontal=True, key="rca_axis")
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

        elif self.store.active_view == 'documentation':
             render_documentation()

        else:
            st.warning(f"Unknown view: {self.store.active_view}")
