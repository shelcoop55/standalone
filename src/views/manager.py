import streamlit as st
from typing import List, Optional
import pandas as pd
from src.state import SessionStore
from src.io.naming import get_bu_name_from_filename
from src.enums import ViewMode, Quadrant
from src.views.still_alive import render_still_alive_main
from src.views.multi_layer import render_multi_layer_view
from src.views.layer_view import render_layer_view
from src.documentation import render_documentation
from src.analysis import get_analysis_tool
from src.io.exporters.package import generate_zip_package
from src.analytics.yield_analysis import get_true_defect_coordinates
from src.core.geometry import GeometryEngine
from src.core.config import DEFAULT_OFFSET_X, DEFAULT_OFFSET_Y
import streamlit.components.v1 as components
from src.views.utils import get_geometry_context
from src.core.layout import apply_layout_to_dataframe

def _build_layer_labels(store: SessionStore, layer_nums: List[int]) -> List[dict]:
    """Build list of {num, label} for layer dropdowns/buttons. Label uses BU name from SOURCE_FILE when available."""
    process_comment = store.analysis_params.get("process_comment", "")
    result = []
    for num in layer_nums:
        bu_name = ""
        try:
            first_side_key = next(iter(store.layer_data[num]))
            source_file = store.layer_data[num][first_side_key]['SOURCE_FILE'].iloc[0]
            bu_name = get_bu_name_from_filename(str(source_file))
        except (IndexError, AttributeError, StopIteration, KeyError):
            pass
        base_label = bu_name if bu_name else f"Layer {num}"
        label = f"{base_label} ({process_comment})" if process_comment else base_label
        result.append({"num": num, "label": label})
    return result


class ViewManager:
    """
    Manages view routing and navigation components.
    Decouples UI layout from application logic.
    """
    def __init__(self, store: SessionStore):
        self.store = store

    def _sync_widget_state(self, key: str):
        """Callback to sync temporary widget state to persistent session state."""
        if f"widget_{key}" in st.session_state:
            st.session_state[key] = st.session_state[f"widget_{key}"]

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
        # "Layer Inspection", "Analysis Page", "Reporting", "Sample Data", "Documentation"
        nav_cols = st.columns(5, gap="small")

        def set_mode(m):
            if m == 'layer': self.store.active_view = 'layer'
            elif m == 'documentation': self.store.active_view = 'documentation'
            elif m == 'reporting': self.store.active_view = 'reporting'
            elif m == 'sample_data': self.store.active_view = 'sample_data'
            else:
                # Analysis default
                if self.store.active_view not in ['multi_layer_defects', 'analysis_dashboard', 'sample_data']:
                     self.store.active_view = 'analysis_dashboard'

        # Layer Inspection Button
        is_layer = self.store.active_view == 'layer'
        nav_cols[0].button("Layer Inspection", type="primary" if is_layer else "secondary", width="stretch", on_click=lambda: set_mode('layer'))

        # Analysis Page Button
        # Analysis includes subviews: dashboard, still_alive, multi_layer
        is_analysis = self.store.active_view in ['analysis_dashboard', 'multi_layer_defects']
        nav_cols[1].button("Analysis Page", type="primary" if is_analysis else "secondary", width="stretch", on_click=lambda: set_mode('analysis'))

        # Reporting Button (3rd)
        is_rep = self.store.active_view == 'reporting'
        nav_cols[2].button("Reporting", type="primary" if is_rep else "secondary", width="stretch", on_click=lambda: set_mode('reporting'))

        # Documentation Button (4th)
        is_doc = self.store.active_view == 'documentation'
        nav_cols[3].button("Documentation", type="primary" if is_doc else "secondary", width="stretch", on_click=lambda: set_mode('documentation'))

        # Sample Data Button (5th) - Colorful
        is_sample = self.store.active_view == 'sample_data'
        nav_cols[4].button("🎨 Sample Data", type="primary" if is_sample else "secondary", width="stretch", on_click=lambda: set_mode('sample_data'))


        # st.divider() # Removed as per user request

        if self.store.active_view == 'layer':
            self._render_layer_inspection_controls()
            # st.divider() # Removed as per user request
        elif self.store.active_view in ['documentation', 'reporting', 'sample_data']:
            # No specific controls for documentation or reporting or sample data
            pass
        else:
            self._render_analysis_page_controls()
            # st.divider() # Removed as per user request

    def _render_layer_inspection_controls(self):
        """Renders the top control row for Layer Inspection."""

        # Prepare Data for Dropdowns
        # Use metadata from store instead of pulling full object if possible,
        # but to get BU name we need the dataframe.
        # Since we have caching, accessing self.store.layer_data is cheap enough now?
        # Yes, it calls load_data which returns cached object.

        layer_keys = sorted(self.store.layer_data.keys())
        if not layer_keys:
            return

        # Layer Options
        layer_buttons_data = _build_layer_labels(self.store, layer_keys)
        layer_options = [d["label"] for d in layer_buttons_data]
        layer_option_map = {d["label"]: d["num"] for d in layer_buttons_data}

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

                 st.multiselect(
                     "Filter Verification Status",
                     options=ver_options,
                     key="multi_verification_selection"
                 )
             else:
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

        with st.expander("Analysis Scope", expanded=True):
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
                         width="stretch",
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
                        width="stretch",
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
                        width="stretch",
                        on_click=on_quad_click(label)
                    )

        # --- Tabs for View Mode (Full Width Buttons) ---
        st.markdown("") # Spacer
        tab_labels = ["Defect View", "Summary View", "Pareto View", "Still Alive"]
        tab_map = {
            "Defect View": ViewMode.DEFECT.value,
            "Summary View": ViewMode.SUMMARY.value,
            "Pareto View": ViewMode.PARETO.value,
            "Still Alive": ViewMode.STILL_ALIVE.value
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
                width="stretch",
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

                 st.multiselect(
                     "Filter Verification Status",
                     options=all_verifications,
                     key="multi_verification_selection"
                 )
             else:
                 default_ver = all_verifications # Default to all

                 st.multiselect(
                     "Filter Verification Status",
                     options=all_verifications,
                     default=default_ver,
                     key="multi_verification_selection"
                 )

             # Toggle for Back Side Alignment - Show only for Heatmap or Multi-Layer
             # Check current active tab text logic from _render_analysis_page_controls
             # We need to replicate that logic or access it.
             # Logic is:
             # current_tab_text = "Heatmap" if analysis_subview is HEATMAP
             # or active_view == 'multi_layer_defects'

             show_alignment = False
             if self.store.active_view == 'multi_layer_defects':
                 show_alignment = True
             elif self.store.active_view == 'analysis_dashboard':
                 if self.store.analysis_subview == ViewMode.HEATMAP.value:
                     show_alignment = True

             if show_alignment:
                 st.markdown("### Alignment")
                 # Default value set to False as per user request
                 st.checkbox("Align Back Side (Flip Units)", value=False, key="flip_back_side", help="If enabled, Back Side units are mirrored horizontally to match Front Side position (Through-Board View).")

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
            layer_buttons_data = _build_layer_labels(self.store, all_layers)

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
                    l_cols[i].button(d['label'], key=f"an_btn_l_{num}", type="primary" if is_sel else "secondary", width="stretch", on_click=on_click_layer(num))

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
                target_cols[0].button("Front", key="an_side_f", type="primary" if is_f else "secondary", width="stretch", on_click=toggle_side("Front"))

                is_b = "Back" in current_sides
                target_cols[1].button("Back", key="an_side_b", type="primary" if is_b else "secondary", width="stretch", on_click=toggle_side("Back"))

            # --- Quadrants Group ---
            if show_quadrant:
                with c_quads:
                    quad_opts = ["All", "Q1", "Q2", "Q3", "Q4"]
                    current_quad = st.session_state.get("analysis_quadrant_selection", "All")
                    q_cols = st.columns(len(quad_opts), gap="small")

                    def set_quad(q): st.session_state["analysis_quadrant_selection"] = q

                    for i, q_label in enumerate(quad_opts):
                        is_active = (current_quad == q_label)
                        q_cols[i].button(q_label, key=f"an_quad_{q_label}", type="primary" if is_active else "secondary", width="stretch", on_click=lambda q=q_label: set_quad(q))

        # st.divider() # Removed as per user request

        # --- ROW 2: ANALYSIS MODULES (Tabs) ---
        # "Documentation" moved to global nav
        tabs = ["Still Alive", "Insights", "Heatmap", "Stress Map", "Root Cause", "Multi-Layer"]

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
            t_cols[i].button(label, key=f"an_tab_{i}", type="primary" if is_active else "secondary", width="stretch", on_click=on_tab(label))

        st.divider()

        # --- ROW 3: CONTEXT FILTERS ---
        if current_tab_text == "Heatmap":
             # Initialize persistent state defaults if missing
             if "heatmap_view_mode" not in st.session_state: st.session_state["heatmap_view_mode"] = "Aggregated"
             if "heatmap_defect_set" not in st.session_state: st.session_state["heatmap_defect_set"] = "Real defects only (verification rules)"
             if "heatmap_bin_size_mm" not in st.session_state: st.session_state["heatmap_bin_size_mm"] = 25  # Default Bin Size: 25mm
             if "heatmap_color_scale" not in st.session_state: st.session_state["heatmap_color_scale"] = "Count per bin"  # Default Scale
             if "heatmap_zmax_density" not in st.session_state: st.session_state["heatmap_zmax_density"] = 1.0
             if "heatmap_zmax_count" not in st.session_state: st.session_state["heatmap_zmax_count"] = 5  # Default Z-Max Count

             if "heatmap_zmax_count" not in st.session_state: st.session_state["heatmap_zmax_count"] = 5  # Default Z-Max Count

             # Enforce Aggregated View Mode (User Request: Remove toggle, default to All/Aggregated)
             st.session_state["heatmap_view_mode"] = "Aggregated"

             st.radio(
                 "Defect set",
                 options=["Real defects only (verification rules)", "All read defects"],
                 index=0 if st.session_state["heatmap_defect_set"] == "Real defects only (verification rules)" else 1,
                 key="widget_heatmap_defect_set",
                 on_change=self._sync_widget_state, args=("heatmap_defect_set",),
                 help="Real defects: excludes safe codes (e.g. GE57, N, TA, FALSE). All read: every defect from coordinates.",
             )
             st.slider(
                 "Bin size (mm)",
                 min_value=5,
                 max_value=50,
                 value=int(st.session_state["heatmap_bin_size_mm"]),
                 step=1,
                 key="widget_heatmap_bin_size_mm",
                 on_change=self._sync_widget_state, args=("heatmap_bin_size_mm",),
                 help="Cell size in mm. Each cell = bin_size × bin_size mm².",
             )
             st.radio(
                 "Color scale",
                 options=["Count per bin", "Defects per mm²"],
                 index=0 if st.session_state["heatmap_color_scale"] == "Count per bin" else 1,
                 key="widget_heatmap_color_scale",
                 on_change=self._sync_widget_state, args=("heatmap_color_scale",),
                 help="Count per bin: defects in each cell. Defects per mm²: density (count / cell area in mm²).",
             )
             heatmap_scale = st.session_state["heatmap_color_scale"]
             if heatmap_scale == "Defects per mm²":
                 st.slider(
                     "Color scale max (Z)",
                     min_value=0.0,
                     max_value=1.0,
                     value=float(st.session_state["heatmap_zmax_density"]),
                     step=0.1,
                     key="widget_heatmap_zmax_density",
                     on_change=self._sync_widget_state, args=("heatmap_zmax_density",),
                     help="Max value for the color bar (defects per mm²).",
                 )
             else:
                 st.slider(
                     "Color scale max (Z)",
                     min_value=0,
                     max_value=10,
                     value=int(st.session_state["heatmap_zmax_count"]),
                     step=1,
                     key="widget_heatmap_zmax_count",
                     on_change=self._sync_widget_state, args=("heatmap_zmax_count",),
                     help="Max value for the color bar (count per bin).",
                 )
        elif current_tab_text == "Stress Map":
             st.radio("Mode", ["Cumulative", "Delta Difference"], horizontal=True, key="stress_map_mode")

        elif current_tab_text == "Root Cause":
             c1, c2 = st.columns(2)
             # Fixed: Zonal Yield (Slice Axis) made vertical (column) instead of row as requested
             with c1: st.radio("Slice Axis", ["X (Column)", "Y (Row)"], horizontal=False, key="rca_axis")
             with c2:
                 max_idx = (self.store.analysis_params.get('panel_cols', 7) * 2) - 1
                 st.slider("Slice Index", 0, max_idx, 0, key="rca_index")


    def render_reporting_view(self):
        """Renders the dedicated Reporting View."""
        st.header("📥 Generate Analysis Reports")
        st.markdown("Use this page to generate and download comprehensive reports, including Excel data, defect maps, and charts.")

        # Quick selection buttons
        st.markdown("**Download selection**")
        sel_col1, sel_col2 = st.columns([1,1])
        with sel_col1:
            if st.button("Select all downloads"):
                for k in [
                    'rep_include_excel','rep_include_coords','rep_include_map','rep_include_insights',
                    'rep_include_png_all','rep_include_pareto','rep_include_heatmap_png','rep_include_heatmap_html',
                    'rep_include_stress_png','rep_include_rca_html','rep_include_still_alive_png'
                ]:
                    st.session_state[k] = True
        with sel_col2:
            if st.button("Clear selection"):
                for k in [
                    'rep_include_excel','rep_include_coords','rep_include_map','rep_include_insights',
                    'rep_include_png_all','rep_include_pareto','rep_include_heatmap_png','rep_include_heatmap_html',
                    'rep_include_stress_png','rep_include_rca_html','rep_include_still_alive_png'
                ]:
                    st.session_state[k] = False
                # restore sensible defaults
                st.session_state['rep_include_excel'] = True
                st.session_state['rep_include_map'] = True
                st.session_state['rep_include_insights'] = True

        col1, col2 = st.columns(2, gap="medium")

        with col1:
            st.subheader("Report Content")
            include_excel = st.checkbox("Excel Report", key="rep_include_excel", help="Includes summary stats, defect lists, and KPI tables.")
            include_coords = st.checkbox("Coordinate List", key="rep_include_coords", help="Includes a list of defective cell coordinates.")

            st.subheader("Visualizations")
            include_map = st.checkbox("Defect Map (HTML)", key="rep_include_map", help="Interactive HTML map of defects.")
            include_insights = st.checkbox("Insights Charts", key="rep_include_insights", help="Interactive Sunburst and Sankey charts.")

        with col2:
            st.subheader("Image Exports")
            st.markdown("*(Optional) Include static images for offline viewing.*")
            include_png_all = st.checkbox("Defect Maps (PNG) - All Layers", key="rep_include_png_all")
            include_pareto_png = st.checkbox("Pareto Charts (PNG) - All Layers", key="rep_include_pareto")
            st.markdown("##### Additional Analysis Charts")
            include_heatmap_png = st.checkbox("Heatmap (PNG)", key="rep_include_heatmap_png")
            # HTML Heatmap removed as per user request
            include_heatmap_html = False 
            include_stress_png = st.checkbox("Stress Map (PNG)", key="rep_include_stress_png")
            include_root_cause_html = st.checkbox("Root Cause (HTML)", key="rep_include_rca_html")

            rca_slice_axis = 'Y'
            if include_root_cause_html:
                rca_choice = st.radio(
                    "RCA Slice Axis",
                    ["Y (Row)", "X (Column)"],
                    horizontal=True,
                    key="rep_rca_axis",
                    help="Select the slicing direction for the Root Cause Analysis animation."
                )
                rca_slice_axis = 'Y' if 'Y' in rca_choice else 'X'

            include_still_alive_png = st.checkbox("Still Alive Map (PNG)", key="rep_include_still_alive_png")

        st.markdown("---")

        if st.button("📦 Generate Download Package", type="primary", width="stretch"):
            with st.spinner("Generating Package..."):
                full_df = self.store.layer_data.get_combined_dataframe()
                
                # FIX: Apply layout to ensures QUADRANT column exists for Excel export
                if not full_df.empty:
                    ctx = get_geometry_context(self.store)
                    # We need panel dims
                    panel_rows = self.store.analysis_params.get("panel_rows", 7)
                    panel_cols = self.store.analysis_params.get("panel_cols", 7)
                    full_df = apply_layout_to_dataframe(full_df, ctx, panel_rows, panel_cols)

                # Get True Defect Coords (returns dict)
                td_result = get_true_defect_coordinates(self.store.layer_data, store=self.store)
                # Pass the full dictionary to the package generator so it can access metadata
                true_defect_data = td_result if td_result else {}

                # Fetch Theme for Reporting (Optional - for now using defaults/user choice in app state)
                # Reporting might need to pass theme if PNGs are generated with it.
                current_theme = st.session_state.get('plot_theme', None)

                # Fetch Layout Parameters from Session Store (Calculated in app.py)
                params = self.store.analysis_params

                # Construct Geometry Context
                # NOTE: "gap_x" in params is the EFFECTIVE gap (Fixed + 2*Dyn).
                # We need "dyn_gap_x" which is the actual dynamic component.
                dyn_gap_x = params.get("dyn_gap_x", 3.0)
                dyn_gap_y = params.get("dyn_gap_y", 3.0)
                fixed_offset_x = params.get("fixed_offset_x", DEFAULT_OFFSET_X)
                fixed_offset_y = params.get("fixed_offset_y", DEFAULT_OFFSET_Y)

                ctx = GeometryEngine.calculate_layout(
                    panel_rows=params.get('panel_rows', 7),
                    panel_cols=params.get('panel_cols', 7),
                    dyn_gap_x=dyn_gap_x,
                    dyn_gap_y=dyn_gap_y,
                    visual_origin_x=params.get("visual_origin_x", 0.0),
                    visual_origin_y=params.get("visual_origin_y", 0.0)
                )

                # Pass current Heatmap UI parameters so exported heatmap matches on-screen
                defect_set_choice = st.session_state.get("heatmap_defect_set", "Real defects only (verification rules)")
                heatmap_real_defects_only = defect_set_choice == "Real defects only (verification rules)"
                heatmap_bin_size_mm = float(st.session_state.get("heatmap_bin_size_mm", 10))
                heatmap_use_density = st.session_state.get("heatmap_color_scale", "Defects per mm²") == "Defects per mm²"
                heatmap_zmax_override = (float(st.session_state.get("heatmap_zmax_density", 1.0)) if heatmap_use_density else float(st.session_state.get("heatmap_zmax_count", 10)))

                self.store.report_bytes = generate_zip_package(
                    full_df=full_df,
                    panel_rows=params.get('panel_rows', 7),
                    panel_cols=params.get('panel_cols', 7),
                    quadrant_selection=self.store.quadrant_selection,
                    verification_selection=self.store.verification_selection,
                    source_filename="Multiple Files",
                    true_defect_data=true_defect_data,
                    ctx=ctx,
                    dyn_gap_x=dyn_gap_x,
                    dyn_gap_y=dyn_gap_y,
                    fixed_offset_x=fixed_offset_x,
                    fixed_offset_y=fixed_offset_y,
                    include_excel=include_excel,
                    include_coords=include_coords,
                    include_map=include_map,
                    include_insights=include_insights,
                    include_png_all_layers=include_png_all,
                    include_pareto_png=include_pareto_png,
                    include_heatmap_png=include_heatmap_png,
                    include_heatmap_html=include_heatmap_html,
                    include_stress_png=include_stress_png,
                    include_root_cause_html=include_root_cause_html,
                    include_still_alive_png=include_still_alive_png,
                    # heatmap UI options
                    heatmap_bin_size_mm=heatmap_bin_size_mm,
                    heatmap_use_density=heatmap_use_density,
                    heatmap_real_defects_only=heatmap_real_defects_only,
                    heatmap_zmax_override=heatmap_zmax_override,
                    rca_slice_axis=rca_slice_axis,
                    layer_data=self.store.layer_data,
                    process_comment=params.get("process_comment", ""),
                    lot_number=params.get("lot_number", ""),
                    theme_config=current_theme
                )
                st.success("Package generated successfully!")

        if self.store.report_bytes:
            from src.io.naming import generate_standard_filename

            zip_filename = generate_standard_filename(
                prefix="Defect_Analysis_Package",
                selected_layer=self.store.selected_layer,
                layer_data=self.store.layer_data,
                analysis_params=self.store.analysis_params,
                extension="zip"
            )

            st.download_button(
                "Download Package (ZIP)",
                data=self.store.report_bytes,
                file_name=zip_filename,
                mime="application/zip",
                type="primary",
                width="stretch"
            )

    def render_main_view(self):
        """Dispatches the rendering to the appropriate view function."""

        if not self.store.layer_data:
             st.info("Please upload data and run analysis to proceed.")
             return

        # Retrieve current theme from session state
        current_theme = st.session_state.get('plot_theme', None)

        if self.store.active_view == 'still_alive':
            render_still_alive_main(self.store, theme_config=current_theme)

        elif self.store.active_view == 'multi_layer_defects':
            render_multi_layer_view(
                self.store,
                self.store.multi_layer_selection,
                self.store.multi_side_selection,
                theme_config=current_theme
            )

        elif self.store.active_view == 'analysis_dashboard':
            tool = get_analysis_tool(self.store.analysis_subview, self.store)
            # Pass theme to analysis tool if it supports it
            if hasattr(tool, 'render_main_with_theme'):
                 tool.render_main_with_theme(theme_config=current_theme)
            else:
                 tool.render_main()

        elif self.store.active_view == 'layer':
            render_layer_view(
                self.store,
                self.store.view_mode,
                self.store.quadrant_selection,
                self.store.verification_selection,
                theme_config=current_theme
            )

        elif self.store.active_view == 'documentation':
             render_documentation()

        elif self.store.active_view == 'reporting':
             self.render_reporting_view()

        elif self.store.active_view == 'sample_data':
             self.render_sample_data_view()

        else:
            st.warning(f"Unknown view: {self.store.active_view}")

    def render_sample_data_view(self):
        """Renders the Sample Data view."""
        st.header("Uploaded Data Preview")
        st.info("Below is a sample of the data currently loaded into the application.")
        
        full_df = self.store.layer_data.get_combined_dataframe()
        if not full_df.empty:
            display_df = full_df.copy()
            
            # Filter columns: remove SOURCE_FILE and keep only up to 'Verification'
            if 'SOURCE_FILE' in display_df.columns:
                display_df = display_df.drop(columns=['SOURCE_FILE'])
            
            # Find column index of 'Verification' (or similar)
            # The exact column name might be 'Verification' or 'HAS_VERIFICATION_DATA' based on screenshots/code
            # The user said "Verifcation Status". In previous code I saw 'Verification'.
            # Let's check for 'Verification' first.
            target_col = 'Verification'
            if target_col not in display_df.columns and 'HAS_VERIFICATION_DATA' in display_df.columns:
                target_col = 'HAS_VERIFICATION_DATA'
            
            if target_col in display_df.columns:
                 # Slice columns up to and including target_col
                 loc_idx = display_df.columns.get_loc(target_col)
                 display_df = display_df.iloc[:, :loc_idx+1]
            
            st.dataframe(display_df.head(100), width="stretch")
            st.caption(f"Showing first 100 rows of {len(display_df)} total records.")
        else:
            st.warning("No data loaded.")
