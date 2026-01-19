import streamlit as st
import pandas as pd
from src.config import GAP_SIZE, BACKGROUND_COLOR, TEXT_COLOR, PANEL_COLOR, PANEL_WIDTH, PANEL_HEIGHT, FRAME_WIDTH, FRAME_HEIGHT, DEFAULT_OFFSET_X, DEFAULT_OFFSET_Y, DEFAULT_GAP_X, DEFAULT_GAP_Y, DEFAULT_PANEL_ROWS, DEFAULT_PANEL_COLS, DYNAMIC_GAP_X, DYNAMIC_GAP_Y, DEFAULT_THEME, PlotTheme
from src.data_handler import load_data, get_true_defect_coordinates
from src.reporting import generate_zip_package
from src.enums import ViewMode, Quadrant
from src.state import SessionStore
from src.views.manager import ViewManager
from src.analysis import get_analysis_tool

def load_css(file_path: str) -> None:
    """Loads a CSS file and injects it into the Streamlit app."""
    try:
        with open(file_path) as f:
            css = f.read()
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
        pass # Handle missing CSS safely

def main() -> None:
    """Main function to configure and run the Streamlit application."""
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

        # --- 1. Analysis Configuration Form ---
        with st.form(key="analysis_form"):
            with st.expander("📁 Data Source & Configuration", expanded=True):
                # Use dynamic key to allow resetting the widget
                uploader_key = f"uploaded_files_{st.session_state['uploader_key']}"
                st.file_uploader(
                    "Upload Build-Up Layers (e.g., BU-01-...)",
                    type=["xlsx", "xls"],
                    accept_multiple_files=True,
                    key=uploader_key
                )
                st.number_input(
                    "Panel Rows", min_value=1, value=DEFAULT_PANEL_ROWS,
                    help="Number of vertical units in a single quadrant.",
                    key="panel_rows"
                )
                st.number_input(
                    "Panel Columns", min_value=1, value=DEFAULT_PANEL_COLS,
                    help="Number of horizontal units in a single quadrant.",
                    key="panel_cols"
                )
                st.text_input(
                    "Lot Number (Optional)",
                    help="Enter the Lot Number to display it on the defect map.",
                    key="lot_number"
                )
                st.text_input(
                    "Process Step / Comment",
                    help="Enter a comment (e.g., Post Etching) to tag these layers.",
                    key="process_comment"
                )

                # --- NEW: Coordinate Origin Inputs (User Facing) ---
                # These default to 0,0 and only affect visual plotting, not structural calculation.
                st.markdown("---")
                st.markdown("##### Plot Origin Configuration")
                c_origin1, c_origin2 = st.columns(2)
                with c_origin1:
                    st.number_input("X Origin (mm)", value=0.0, step=1.0, key="plot_origin_x", help="Shift the visual coordinate system X origin.")
                with c_origin2:
                    st.number_input("Y Origin (mm)", value=0.0, step=1.0, key="plot_origin_y", help="Shift the visual coordinate system Y origin.")


            with st.expander("⚙️ Advanced Configuration", expanded=False):
                # 1. Panel Dimensions (UI Removed - Hardcoded Defaults)
                # Used to be: c_dim1, c_dim2 inputs for Panel Width/Height
                # Now using Frame Width/Height (510/515) internally for calculation.

                # 2. Origins (Structrual Margins) - REMOVED FROM UI
                # We now use DEFAULT_OFFSET_X (13.5) and DEFAULT_OFFSET_Y (15.0) hardcoded in config.py
                # This ensures the panel structure is fixed.

                # 3. Dynamic Gaps
                c_gap1, c_gap2 = st.columns(2)
                with c_gap1:
                    st.number_input("Dynamic Gap X (mm)", value=float(DYNAMIC_GAP_X), step=1.0, min_value=0.0, key="dyn_gap_x", help="Dynamic Horizontal Gap.")
                with c_gap2:
                    st.number_input("Dynamic Gap Y (mm)", value=float(DYNAMIC_GAP_Y), step=1.0, min_value=0.0, key="dyn_gap_y", help="Dynamic Vertical Gap.")

            # Callback for Analysis
            def on_run_analysis():
                # Read from dynamic key
                current_uploader_key = f"uploaded_files_{st.session_state['uploader_key']}"
                files = st.session_state.get(current_uploader_key, [])

                rows = st.session_state.panel_rows
                cols = st.session_state.panel_cols
                lot = st.session_state.lot_number
                comment = st.session_state.process_comment

                # Retrieve Advanced Params
                # Use Hardcoded Defaults for Structural Calculation
                off_x_struct = DEFAULT_OFFSET_X # 13.5
                off_y_struct = DEFAULT_OFFSET_Y # 15.0

                # Retrieve User Visual Origins
                visual_origin_x = st.session_state.get("plot_origin_x", 0.0)
                visual_origin_y = st.session_state.get("plot_origin_y", 0.0)

                # Hardcoded gaps are now used instead of UI inputs
                gap_x_fixed = DEFAULT_GAP_X # 3.0
                gap_y_fixed = DEFAULT_GAP_Y # 3.0
                # Retrieve dynamic gaps from session state
                dyn_gap_x = st.session_state.get("dyn_gap_x", DYNAMIC_GAP_X)
                dyn_gap_y = st.session_state.get("dyn_gap_y", DYNAMIC_GAP_Y)

                # DYNAMIC CALCULATION of Active Panel Dimensions
                # Updated Logic per User Request:
                # 4 Dynamic Gaps total (Left of Q1, Right of Q1, Left of Q2, Right of Q2)
                # Active Width = Frame - 2*Offset - FixedGap - 4*DynGap
                p_width = float(FRAME_WIDTH) - 2 * off_x_struct - gap_x_fixed - 4 * dyn_gap_x
                p_height = float(FRAME_HEIGHT) - 2 * off_y_struct - gap_y_fixed - 4 * dyn_gap_y

                # Calculate EFFECTIVE GAP for Plotting
                # The visual gap between Q1 and Q2 includes the fixed gap (3mm) AND the dynamic gaps adjacent to the center.
                # Center Space = DynGap(Right of Q1) + FixedGap(3mm) + DynGap(Left of Q2)
                effective_gap_x = gap_x_fixed + 2 * dyn_gap_x
                effective_gap_y = gap_y_fixed + 2 * dyn_gap_y

                # Load Data (This will now hit the cache if arguments are same)
                # Pass dynamically calculated width/height and EFFECTIVE GAPS
                data = load_data(files, rows, cols, p_width, p_height, effective_gap_x, effective_gap_y)
                if data:
                    # UPDATE: Store ID and Metadata, NOT the object
                    if not files:
                        store.dataset_id = "sample_data"
                    else:
                        # Simple ID generation based on filenames for tracking
                        store.dataset_id = str(hash(tuple(f.name for f in files)))

                    # Store lightweight metadata for UI logic (keys only)
                    # We need a serializable dict structure: {layer_num: {side: True}}
                    meta = {}
                    for l_num, sides in data.items():
                        meta[l_num] = list(sides.keys())
                    store.layer_data_keys = meta

                    # Logic using the data object (which is local var here, safe)
                    store.selected_layer = max(data.keys())
                    store.active_view = 'layer'

                    # Auto-select side
                    layer_info = data.get(store.selected_layer, {})
                    if 'F' in layer_info:
                        store.selected_side = 'F'
                    elif 'B' in layer_info:
                        store.selected_side = 'B'
                    elif layer_info:
                        store.selected_side = next(iter(layer_info.keys()))

                    # Initialize Multi-Layer Selection defaults
                    store.multi_layer_selection = sorted(data.keys())
                    all_sides = set()
                    for l_data in data.values():
                        all_sides.update(l_data.keys())
                    store.multi_side_selection = sorted(list(all_sides))
                else:
                    store.selected_layer = None

                # Calculate TOTAL OFFSET for Plotting
                # We need to determine where Q1 starts relative to the Frame Origin (0,0).
                # Start = FixedOffset(13.5) + DynGap(Left of Q1)
                total_off_x_struct = off_x_struct + dyn_gap_x
                total_off_y_struct = off_y_struct + dyn_gap_y

                store.analysis_params = {
                    "panel_rows": rows,
                    "panel_cols": cols,
                    "panel_width": p_width,
                    "panel_height": p_height,
                    "gap_x": effective_gap_x, # Use effective gap for plotting logic
                    "gap_y": effective_gap_y,
                    "gap_size": effective_gap_x, # Backwards compatibility
                    "lot_number": lot,
                    "process_comment": comment,
                    # IMPORTANT: Use Structural Offset for drawing the grid in the Frame
                    "offset_x": total_off_x_struct,
                    "offset_y": total_off_y_struct,

                    # Store Visual Origins for Axis Correction
                    "visual_origin_x": visual_origin_x,
                    "visual_origin_y": visual_origin_y,

                    "dyn_gap_x": dyn_gap_x,
                    "dyn_gap_y": dyn_gap_y
                }
                store.report_bytes = None

            c1, c2 = st.columns(2)
            with c1:
                st.form_submit_button("🚀 Run", on_click=on_run_analysis)

            with c2:
                # Reset Button logic integrated into the form area (but form_submit_button is primary action)
                # Since we cannot put a standard button inside a form that triggers a rerun cleanly without submitting the form,
                # we will use another form_submit_button or place it outside if strictly required.
                # However, user asked "inside Data Source & Configuration".
                # Standard st.button inside a form behaves as a submit button.

                def on_reset():
                    store.clear_all()
                    # Re-initialize uploader_key immediately after clearing state
                    # to prevent KeyError on rerun or subsequent access
                    if "uploader_key" not in st.session_state:
                        st.session_state["uploader_key"] = 0

                    # Increment key to recreate file uploader widget (effectively clearing it)
                    st.session_state["uploader_key"] += 1
                    # Rerun will happen automatically after callback

                st.form_submit_button("🔄 Reset", on_click=on_reset, type="secondary")

        # --- 2. Appearance & Style (Expander) ---
        with st.expander("🎨 Appearance & Style", expanded=False):
            # Create PlotTheme inputs and update session state immediately
            bg_color = st.color_picker("Background Color", value=DEFAULT_THEME.background_color, key="style_bg")
            plot_color = st.color_picker("Plot Area Color", value=DEFAULT_THEME.plot_area_color, key="style_plot")
            panel_color = st.color_picker("Panel Color", value=DEFAULT_THEME.panel_background_color, key="style_panel")
            axis_color = st.color_picker("Axis Color", value=DEFAULT_THEME.axis_color, key="style_axis")
            text_color = st.color_picker("Text Color", value=DEFAULT_THEME.text_color, key="style_text")
            unit_color = st.color_picker("Unit Color", value=DEFAULT_THEME.unit_face_color, key="style_unit")

            # Construct Theme Object
            current_theme = PlotTheme(
                background_color=bg_color,
                plot_area_color=plot_color,
                panel_background_color=panel_color,
                axis_color=axis_color,
                text_color=text_color,
                # Use user selection
                unit_face_color=unit_color,
                unit_edge_color=axis_color # Match axis for grid edges
            )

            # Store in session state for Views to access
            st.session_state['plot_theme'] = current_theme

    # --- Main Content Area ---
    # Header removed to save space
    # st.title("📊 Panel Defect Analysis Tool")

    # Render Navigation (Triggers full rerun to update Sidebar context)
    view_manager.render_navigation()

    @st.fragment
    def render_chart_area():
        # Render Main View (Chart Area) - Isolated updates
        view_manager.render_main_view()

    render_chart_area()

if __name__ == '__main__':
    main()
