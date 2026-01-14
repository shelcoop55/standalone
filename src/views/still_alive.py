import streamlit as st
import pandas as pd
import numpy as np
from src.state import SessionStore
from src.plotting import create_still_alive_figure
from src.data_handler import get_true_defect_coordinates

def render_still_alive_view(store: SessionStore):
    params = store.analysis_params
    panel_rows = params.get("panel_rows", 7)
    panel_cols = params.get("panel_cols", 7)

    st.header("Still Alive Panel Yield Map")

    # --- Sidebar Controls for "What-If" Simulator ---
    with st.sidebar.expander("🛠️ Yield Simulator (What-If)", expanded=False):
        st.caption("Uncheck layers to simulate yield if they were perfect.")
        all_layers = store.layer_data.get_all_layer_nums()

        # Local state for exclusion
        if 'excluded_layers' not in st.session_state:
            st.session_state.excluded_layers = []

        # Create checkboxes
        excluded = []
        for layer in all_layers:
            # Default is Checked (Include). If unchecked, add to excluded.
            is_included = st.checkbox(f"Include Layer {layer}", value=layer not in st.session_state.excluded_layers)
            if not is_included:
                excluded.append(layer)

        st.session_state.excluded_layers = excluded

    # Get Data with Exclusion
    true_defect_data = get_true_defect_coordinates(store.layer_data, excluded_layers=st.session_state.excluded_layers)

    map_col, summary_col = st.columns([3, 1])

    with map_col:
        fig = create_still_alive_figure(panel_rows, panel_cols, true_defect_data)
        st.plotly_chart(fig, use_container_width=True)

    with summary_col:
        total_cells = (panel_rows * 2) * (panel_cols * 2)
        defective_cell_count = len(true_defect_data)
        alive_cell_count = total_cells - defective_cell_count
        yield_percentage = (alive_cell_count / total_cells) * 100 if total_cells > 0 else 0

        st.subheader("Yield Summary")
        st.metric("Panel Yield", f"{yield_percentage:.2f}%")
        st.metric("Surviving Cells", f"{alive_cell_count:,} / {total_cells:,}")
        st.metric("Defective Cells", f"{defective_cell_count:,}")

        st.divider()

        # --- Edge vs Center Analysis ---
        st.subheader("Zonal Yield")

        # Calculate Zones
        # Center = Inner 30% radius equivalent
        # Edge = Outer ring (first/last row/col)
        # Middle = Rest

        edge_alive = 0
        edge_total = 0
        center_alive = 0
        center_total = 0
        middle_alive = 0
        middle_total = 0

        # Helper to define zone
        total_rows_grid = panel_rows * 2
        total_cols_grid = panel_cols * 2

        for r in range(total_rows_grid):
            for c in range(total_cols_grid):
                is_dead = (c, r) in true_defect_data

                # Edge: Outer boundary
                if r == 0 or r == total_rows_grid - 1 or c == 0 or c == total_cols_grid - 1:
                    edge_total += 1
                    if not is_dead: edge_alive += 1

                # Center: Inner box (approx middle 3rd)
                elif (total_rows_grid // 3 <= r < 2 * total_rows_grid // 3) and \
                     (total_cols_grid // 3 <= c < 2 * total_cols_grid // 3):
                    center_total += 1
                    if not is_dead: center_alive += 1

                # Middle: Everything else
                else:
                    middle_total += 1
                    if not is_dead: middle_alive += 1

        # Render Metrics
        c_yield = (center_alive / center_total * 100) if center_total > 0 else 0
        m_yield = (middle_alive / middle_total * 100) if middle_total > 0 else 0
        e_yield = (edge_alive / edge_total * 100) if edge_total > 0 else 0

        st.metric("Center Yield", f"{c_yield:.1f}%", help="Inner 1/3rd of the panel")
        st.metric("Middle Yield", f"{m_yield:.1f}%")
        st.metric("Edge Yield", f"{e_yield:.1f}%", help="Outer boundary ring")

        st.divider()

        # --- Pick List Download ---
        alive_units = []
        for r in range(total_rows_grid):
            for c in range(total_cols_grid):
                if (c, r) not in true_defect_data:
                    alive_units.append({'PHYSICAL_X': c, 'UNIT_INDEX_Y': r})

        if alive_units:
            df_alive = pd.DataFrame(alive_units)
            csv = df_alive.to_csv(index=False).encode('utf-8')
            st.download_button(
                "📥 Download Pick List",
                data=csv,
                file_name="alive_units_picklist.csv",
                mime="text/csv",
                help="CSV list of coordinate pairs (Physical X, Y) for good units."
            )
