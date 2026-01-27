import streamlit as st
import pandas as pd
# Enable Pandas Copy-on-Write for performance
pd.options.mode.copy_on_write = True

from src.core.config import (
    GAP_SIZE, BACKGROUND_COLOR, TEXT_COLOR, PANEL_COLOR,
    FRAME_WIDTH, FRAME_HEIGHT, DEFAULT_OFFSET_X, DEFAULT_OFFSET_Y,
    DEFAULT_GAP_X, DEFAULT_GAP_Y, DEFAULT_PANEL_ROWS, DEFAULT_PANEL_COLS,
    DYNAMIC_GAP_X, DYNAMIC_GAP_Y, DEFAULT_THEME, PlotTheme
)
from src.core.geometry import GeometryEngine
from src.state import SessionStore
from pathlib import Path
from src.views.manager import ViewManager
from src.utils.logger import configure_logging
from src.utils.telemetry import PerformanceMonitor

def load_css(file_path: str) -> None:
    """Loads a CSS file and injects it into the Streamlit app."""
    try:
        css = Path(file_path).read_text()
        css_variables = f'''
        <style>
            :root {{
                --background-color: {BACKGROUND_COLOR};
                --text-color: {TEXT_COLOR};
                --panel-color: {PANEL_COLOR};
                --panel-hover-color: #d48c46;
            }}
            {css}
        </style>
        '''
        st.markdown(css_variables, unsafe_allow_html=True)
    except FileNotFoundError:
        pass

def main() -> None:
    """Main function to configure and run the Streamlit application."""
    configure_logging()
    st.set_page_config(layout="wide", page_title="Panel Defect Analysis", initial_sidebar_state="expanded")
    load_css("assets/styles.css")

    # --- Initialize Session State & View Manager ---
    store = SessionStore()
    view_manager = ViewManager(store)

    if "uploader_key" not in st.session_state:
        st.session_state["uploader_key"] = 0

    # --- Sidebar Control Panel ---
    with st.sidebar:
        st.title("🎛️ Control Panel")

        # --- 1. Analysis Configuration Form (Execution Boundary) ---
        with st.form(key="analysis_form"):
            with st.expander("📁 Data Source & Configuration", expanded=True):
                uploader_key = f"uploaded_files_{st.session_state['uploader_key']}"
                st.file_uploader(
                    "Upload Build-Up Layers (e.g., BU-01-...)",
                    type=["xlsx", "xls"],
                    accept_multiple_files=True,
                    key=uploader_key
                )

                st.number_input(
                    "Panel Rows", min_value=1, value=DEFAULT_PANEL_ROWS,
                    key="panel_rows_input"
                )
                st.number_input(
                    "Panel Columns", min_value=1, value=DEFAULT_PANEL_COLS,
                    key="panel_cols_input"
                )
                st.text_input("Lot Number", key="lot_input")
                st.text_input("Process Step / Comment", key="comment_input")

                st.markdown("---")
                st.markdown("##### Plot Origin Configuration")
                c_origin1, c_origin2 = st.columns(2)
                with c_origin1:
                    st.number_input("X Origin (mm)", value=0.0, step=1.0, key="origin_x_input")
                with c_origin2:
                    st.number_input("Y Origin (mm)", value=0.0, step=1.0, key="origin_y_input")

            with st.expander("⚙️ Advanced Configuration", expanded=False):
                c_gap1, c_gap2 = st.columns(2)
                with c_gap1:
                    st.number_input("Dynamic Gap X (mm)", value=float(DYNAMIC_GAP_X), step=1.0, min_value=0.0, key="dgx_input")
                with c_gap2:
                    st.number_input("Dynamic Gap Y (mm)", value=float(DYNAMIC_GAP_Y), step=1.0, min_value=0.0, key="dgy_input")

                st.checkbox("Show Debug Telemetry", value=False, key="show_telemetry", help="Displays performance metrics at the bottom of the page.")

            # Submit Button
            submitted = st.form_submit_button("🚀 Run Analysis")

            if submitted:
                # 1. Retrieve Input Values
                p_rows = st.session_state.panel_rows_input
                p_cols = st.session_state.panel_cols_input
                lot = st.session_state.lot_input
                comment = st.session_state.comment_input
                ox = st.session_state.origin_x_input
                oy = st.session_state.origin_y_input
                dgx = st.session_state.dgx_input
                dgy = st.session_state.dgy_input

                # 2. Calculate Geometry (Centralized Logic)
                layout_ctx = GeometryEngine.calculate_layout(
                    panel_rows=p_rows,
                    panel_cols=p_cols,
                    dyn_gap_x=dgx,
                    dyn_gap_y=dgy,
                    visual_origin_x=ox,
                    visual_origin_y=oy
                )

                # 3. Update Analysis Params in Store
                store.analysis_params = {
                    "panel_rows": p_rows,
                    "panel_cols": p_cols,
                    "panel_width": layout_ctx.panel_width,
                    "panel_height": layout_ctx.panel_height,
                    "gap_x": layout_ctx.effective_gap_x,
                    "gap_y": layout_ctx.effective_gap_y,
                    "lot_number": lot,
                    "process_comment": comment,
                    # Structural Offsets for Grid
                    "offset_x": layout_ctx.offset_x,
                    "offset_y": layout_ctx.offset_y,
                    # Visual Offsets for Traces
                    "visual_origin_x": layout_ctx.visual_origin_x,
                    "visual_origin_y": layout_ctx.visual_origin_y,
                    # Fixed Offsets for Inner Border
                    "fixed_offset_x": DEFAULT_OFFSET_X,
                    "fixed_offset_y": DEFAULT_OFFSET_Y,
                    "dyn_gap_x": dgx,
                    "dyn_gap_y": dgy
                }
                store.report_bytes = None

                # 4. Trigger Data Load
                # Determine Dataset ID based on files
                current_uploader_key = f"uploaded_files_{st.session_state['uploader_key']}"
                files = st.session_state.get(current_uploader_key, [])

                if not files:
                    store.dataset_id = "sample_data"
                else:
                    store.dataset_id = str(hash(tuple(f.name for f in files)))

                # Access layer_data to trigger the cached load and verify data
                data = store.layer_data
                if data:
                    # Update Metadata
                    meta = {}
                    for l_num in data.get_all_layer_nums():
                        meta[l_num] = data.get_sides_for_layer(l_num)
                    store.layer_data_keys = meta

                    # Set Defaults
                    store.selected_layer = max(meta.keys())
                    store.active_view = 'layer'

                    # Auto-select side
                    info = meta[store.selected_layer]
                    if 'F' in info:
                        store.selected_side = 'F'
                    elif 'B' in info:
                        store.selected_side = 'B'
                    else:
                        store.selected_side = info[0]

                    # Reset Multi-Selections
                    store.multi_layer_selection = sorted(meta.keys())
                    all_sides = set()
                    for sides in meta.values():
                        all_sides.update(sides)
                    store.multi_side_selection = sorted(list(all_sides))
                else:
                    store.selected_layer = None

        # --- Reset Button ---
        def on_reset():
            store.reset_data_source()

        st.button("🔄 Reset", on_click=on_reset, type="secondary")

        # --- 2. Appearance & Style (Expander) ---
        with st.expander("🎨 Appearance & Style", expanded=False):
            bg_color = st.color_picker("Background Color", value=DEFAULT_THEME.background_color, key="style_bg")
            plot_color = st.color_picker("Plot Area Color", value=DEFAULT_THEME.plot_area_color, key="style_plot")
            panel_color = st.color_picker("Panel Color", value=DEFAULT_THEME.panel_background_color, key="style_panel")
            axis_color = st.color_picker("Axis Color", value=DEFAULT_THEME.axis_color, key="style_axis")
            text_color = st.color_picker("Text Color", value=DEFAULT_THEME.text_color, key="style_text")
            unit_color = st.color_picker("Unit Color", value=DEFAULT_THEME.unit_face_color, key="style_unit")
            gap_color = st.color_picker("Gap Color", value=DEFAULT_THEME.inner_gap_color, key="style_gap")

            current_theme = PlotTheme(
                background_color=bg_color,
                plot_area_color=plot_color,
                panel_background_color=panel_color,
                axis_color=axis_color,
                text_color=text_color,
                unit_face_color=unit_color,
                unit_edge_color=axis_color,
                inner_gap_color=gap_color
            )
            st.session_state['plot_theme'] = current_theme

    # --- Main Content Area ---
    view_manager.render_navigation()

    @st.fragment
    def render_chart_area():
        view_manager.render_main_view()

    render_chart_area()

    # --- Telemetry UI ---
    if st.session_state.get("show_telemetry", False):
        st.divider()
        with st.expander("⏱️ Performance Metrics (Debug)", expanded=True):
            logs = PerformanceMonitor.get_logs()
            if logs:
                st.dataframe(pd.DataFrame(logs), use_container_width=True)
            else:
                st.info("No logs captured yet.")

            if st.button("Clear Logs"):
                PerformanceMonitor.clear_logs()
                st.rerun()

if __name__ == '__main__':
    main()
