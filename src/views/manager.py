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
from src.reporting import generate_zip_package
from src.data_handler import get_true_defect_coordinates
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

        # --- Top Navigation Bar (Global) ---
        # "Layer Inspection", "Analysis Page", "Reporting", "Documentation"
        nav_cols = st.columns(4, gap="small")

        def set_mode(m):
            if m == 'layer': self.store.active_view = 'layer'
            elif m == 'documentation': self.store.active_view = 'documentation'
            elif m == 'reporting': self.store.active_view = 'reporting'
            else:
                # Analysis default
                if self.store.active_view not in ['still_alive', 'multi_layer_defects', 'analysis_dashboard']:
                     self.store.active_view = 'analysis_dashboard'
                     self.store.analysis_subview = ViewMode.HEATMAP.value
                elif self.store.active_view == 'documentation':
                     # Return to default analysis view if coming back
                     self.store.active_view = 'analysis_dashboard'
                     self.store.analysis_subview = ViewMode.HEATMAP.value

        # Layer Inspection Button
        is_layer = self.store.active_view == 'layer'
        nav_cols[0].button("Layer Inspection", type="primary" if is_layer else "secondary", use_container_width=True, on_click=lambda: set_mode('layer'))

        # Analysis Page Button
        # Analysis includes subviews: dashboard, still_alive, multi_layer
        is_analysis = self.store.active_view in ['analysis_dashboard', 'still_alive', 'multi_layer_defects']
        nav_cols[1].button("Analysis Page", type="primary" if is_analysis else "secondary", use_container_width=True, on_click=lambda: set_mode('analysis'))

        # Documentation Button
        is_doc = self.store.active_view == 'documentation'
        nav_cols[2].button("Documentation", type="primary" if is_doc else "secondary", use_container_width=True, on_click=lambda: set_mode('documentation'))

        # Reporting Button
        is_rep = self.store.active_view == 'reporting'
        nav_cols[3].button("Reporting", type="primary" if is_rep else "secondary", use_container_width=True, on_click=lambda: set_mode('reporting'))

        # st.divider() # Removed as per user request

        if self.store.active_view == 'layer':
            self._render_layer_inspection_controls()
            # st.divider() # Removed as per user request
        elif self.store.active_view in ['documentation', 'reporting']:
            # No specific controls for documentation or reporting
            pass
        else:
            self._render_analysis_page_controls()
            # st.divider() # Removed as per user request

    def _render_layer_inspection_controls(self):
        """Renders the top control row for Layer Inspection."""

        # Prepare Data for Dropdowns
        layer_keys = sorted(self.store.layer_data.keys())
        if not layer_keys:
            return

        # Layer Options
        layer_options = []
        layer_option_map = {}
        process_comment = self.store.analysis_params.get("process_comment", "")

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
            base_label = bu_name if bu_name else f"Layer {num}"
            label = f"{base_label} ({process_comment})" if process_comment else base_label
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

        with st.expander("Filter Options", expanded=True):
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

        # Logic to determine active tab text (Needed early for conditional rendering)
        current_tab_text = "Heatmap"
        if self.store.active_view == 'still_alive': current_tab_text = "Still Alive"
        elif self.store.active_view == 'multi_layer_defects': current_tab_text = "Multi-Layer"
        elif self.store.active_view == 'analysis_dashboard':
             sub_map_rev = {
                 ViewMode.HEATMAP.value: "Heatmap",
                 ViewMode.STRESS.value: "Stress Map",
                 ViewMode.ROOT_CAUSE.value: "Root Cause",
                 ViewMode.INSIGHTS.value: "Insights"
             }
             current_tab_text = sub_map_rev.get(self.store.analysis_subview, "Heatmap")

        with st.expander("Analysis Scope", expanded=True):
            # --- ROW 1: GLOBAL FILTERS (Layer Only) ---
            # Headers removed as per request to save space

            # Prepare Layer Buttons: [BU-XX (Comment)...]
            layer_buttons_data = []
            process_comment = self.store.analysis_params.get("process_comment", "")

            # Logic to get BU Name or Layer Num
            for num in all_layers:
                bu_name = ""
                try:
                    first_side_key = next(iter(self.store.layer_data[num]))
                    source_file = self.store.layer_data[num][first_side_key]['SOURCE_FILE'].iloc[0]
                    bu_name = get_bu_name_from_filename(str(source_file))
                except: pass

                base_label = bu_name if bu_name else f"Layer {num}"
                label = f"{base_label} ({process_comment})" if process_comment else base_label
                layer_buttons_data.append({'num': num, 'label': label})

            # Render Layer Buttons Row
            if layer_buttons_data:
                btns = [d['label'] for d in layer_buttons_data]
                l_cols = st.columns(len(btns), gap="small")
                current_selection = self.store.multi_layer_selection if self.store.multi_layer_selection else all_layers

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

            # --- ROW 2: SIDE + QUADRANT (50% / 50%) ---

            # Show Quadrant only if NOT Root Cause or Multi-Layer
            show_quadrant = current_tab_text not in ["Root Cause", "Multi-Layer"]

            if show_quadrant:
                c_sides, c_quads = st.columns(2, gap="medium")
            else:
                c_sides = st.container() # Just a container if no quadrant column needed
                # To keep buttons left-aligned and reasonable size, we can put them in columns even inside the container
                # or just use 2 columns and leave the second empty?
                # Let's create columns inside the container block later.

            # --- Sides Group ---
            with c_sides:
                # "Front" and "Back" as independent toggles.
                current_sides = st.session_state.get("analysis_side_pills", ["Front", "Back"])
                # Just 2 buttons
                if not show_quadrant:
                     # If we are in container mode (no quadrant), make sure buttons are not full width
                     s_cols = st.columns(4, gap="small") # Use more columns to compress them to left
                     # use first 2 columns
                     target_cols = [s_cols[0], s_cols[1]]
                else:
                     s_cols = st.columns(2, gap="small")
                     target_cols = s_cols

                def toggle_side(side):
                    def cb():
                        new_sides = list(st.session_state.get("analysis_side_pills", ["Front", "Back"]))
                        if side in new_sides:
                            if len(new_sides) > 1: new_sides.remove(side) # Prevent empty
                        else:
                            new_sides.append(side)
                        st.session_state["analysis_side_pills"] = new_sides
                    return cb

                is_f = "Front" in current_sides
                target_cols[0].button("Front", key="an_side_f", type="primary" if is_f else "secondary", use_container_width=True, on_click=toggle_side("Front"))

                is_b = "Back" in current_sides
                target_cols[1].button("Back", key="an_side_b", type="primary" if is_b else "secondary", use_container_width=True, on_click=toggle_side("Back"))

            # --- Quadrants Group ---
            if show_quadrant:
                with c_quads:
                    quad_opts = ["All", "Q1", "Q2", "Q3", "Q4"]
                    current_quad = st.session_state.get("analysis_quadrant_selection", "All")
                    q_cols = st.columns(len(quad_opts), gap="small")

                    def set_quad(q): st.session_state["analysis_quadrant_selection"] = q

                    for i, q_label in enumerate(quad_opts):
                        is_active = (current_quad == q_label)
                        q_cols[i].button(q_label, key=f"an_quad_{q_label}", type="primary" if is_active else "secondary", use_container_width=True, on_click=lambda q=q_label: set_quad(q))

        # st.divider() # Removed as per user request

        # --- ROW 2: ANALYSIS MODULES (Tabs) ---
        # "Documentation" moved to global nav
        tabs = ["Still Alive", "Heatmap", "Stress Map", "Root Cause", "Insights", "Multi-Layer"]

        t_cols = st.columns(len(tabs), gap="small")
        for i, label in enumerate(tabs):
            is_active = (label == current_tab_text)
            def on_tab(sel):
                def cb():
                    if sel == "Still Alive": self.store.active_view = 'still_alive'
                    elif sel == "Multi-Layer": self.store.active_view = 'multi_layer_defects'
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


    def render_reporting_view(self):
        """Renders the dedicated Reporting View."""
        st.header("📥 Generate Analysis Reports")
        st.markdown("Use this page to generate and download comprehensive reports, including Excel data, defect maps, and charts.")

        col1, col2 = st.columns(2, gap="medium")

        with col1:
            st.subheader("Report Content")
            include_excel = st.checkbox("Excel Report", value=True, help="Includes summary stats, defect lists, and KPI tables.")
            include_coords = st.checkbox("Coordinate List", value=True, help="Includes a list of defective cell coordinates.")

            st.subheader("Visualizations")
            include_map = st.checkbox("Defect Map (HTML)", value=True, help="Interactive HTML map of defects.")
            include_insights = st.checkbox("Insights Charts", value=True, help="Interactive Sunburst and Sankey charts.")

        with col2:
            st.subheader("Image Exports")
            st.markdown("*(Optional) Include static images for offline viewing.*")
            include_png_all = st.checkbox("Defect Maps (PNG) - All Layers", value=False)
            include_pareto_png = st.checkbox("Pareto Charts (PNG) - All Layers", value=False)
            st.markdown("##### Additional Analysis Charts")
            include_heatmap_png = st.checkbox("Heatmap (PNG)", value=False)
            include_stress_png = st.checkbox("Stress Map (PNG)", value=False)
            include_root_cause_png = st.checkbox("Root Cause (PNG)", value=False)
            include_still_alive_png = st.checkbox("Still Alive Map (PNG)", value=False)

        st.markdown("---")

        if st.button("📦 Generate Download Package", type="primary", use_container_width=True):
            with st.spinner("Generating Package..."):
                full_df = self.store.layer_data.get_combined_dataframe()
                true_defect_coords = get_true_defect_coordinates(self.store.layer_data)

                self.store.report_bytes = generate_zip_package(
                    full_df=full_df,
                    panel_rows=self.store.analysis_params.get('panel_rows', 7),
                    panel_cols=self.store.analysis_params.get('panel_cols', 7),
                    quadrant_selection=self.store.quadrant_selection,
                    verification_selection=self.store.verification_selection,
                    source_filename="Multiple Files",
                    true_defect_coords=true_defect_coords,
                    include_excel=include_excel,
                    include_coords=include_coords,
                    include_map=include_map,
                    include_insights=include_insights,
                    include_png_all_layers=include_png_all,
                    include_pareto_png=include_pareto_png,
                    include_heatmap_png=include_heatmap_png,
                    include_stress_png=include_stress_png,
                    include_root_cause_png=include_root_cause_png,
                    include_still_alive_png=include_still_alive_png,
                    layer_data=self.store.layer_data
                )
                st.success("Package generated successfully!")

        if self.store.report_bytes:
            params_local = self.store.analysis_params
            lot_num_str = f"_{params_local.get('lot_number', '')}" if params_local.get('lot_number') else ""
            zip_filename = f"defect_package_layer_{self.store.selected_layer}{lot_num_str}.zip"
            st.download_button(
                "Download Package (ZIP)",
                data=self.store.report_bytes,
                file_name=zip_filename,
                mime="application/zip",
                type="primary",
                use_container_width=True
            )

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

        elif self.store.active_view == 'reporting':
             self.render_reporting_view()

        else:
            st.warning(f"Unknown view: {self.store.active_view}")
