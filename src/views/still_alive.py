import streamlit as st
import pandas as pd
import numpy as np
from src.state import SessionStore
from src.plotting import create_still_alive_figure
from src.data_handler import get_true_defect_coordinates

def render_still_alive_sidebar(store: SessionStore):
    """Renders the Sidebar controls for the Still Alive view."""
    # --- Sidebar Controls for "What-If" Simulator ---
    with st.sidebar.expander("🛠️ Yield Simulator (What-If)", expanded=True):
        st.caption("Filter out layers or defects to simulate yield improvements.")

        # 1. Layer Filters
        st.markdown("**Exclude Layers**")
        all_layers = store.layer_data.get_all_layer_nums()

        if 'excluded_layers' not in st.session_state:
            st.session_state.excluded_layers = []

        excluded_layers = []
        for layer in all_layers:
            is_included = st.checkbox(f"Include Layer {layer}", value=layer not in st.session_state.excluded_layers)
            if not is_included:
                excluded_layers.append(layer)

        st.session_state.excluded_layers = excluded_layers

        st.divider()

        # 2. Defect Type Filters
        st.markdown("**Exclude Defect Types**")

        # Get all unique defect types from the *entire* panel data
        # We need a helper to get all unique types efficiently or just iterate once.
        # Since we have store.layer_data (PanelData), let's get a combined df
        # This might be heavy if done every rerun, but Streamlit caches the load_data result.
        # Ideally, we should cache the list of defect types too.

        # Quick aggregation for filters
        full_df = store.layer_data.get_combined_dataframe()
        if not full_df.empty:
            all_defects = sorted(full_df['DEFECT_TYPE'].unique().tolist())
        else:
            all_defects = []

        if 'excluded_defects' not in st.session_state:
            st.session_state.excluded_defects = []

        selected_exclusions = st.multiselect(
            "Select Defects to Exclude",
            options=all_defects,
            default=st.session_state.excluded_defects,
            help="Defects selected here will be ignored in the yield calculation."
        )
        st.session_state.excluded_defects = selected_exclusions


def render_still_alive_main(store: SessionStore):
    """Renders the Main Content for the Still Alive view."""
    params = store.analysis_params
    panel_rows = params.get("panel_rows", 7)
    panel_cols = params.get("panel_cols", 7)

    st.header("Still Alive Panel Yield Map")

    # Get Data with Exclusion
    # Defaults
    excluded_layers = st.session_state.get('excluded_layers', [])
    excluded_defects = st.session_state.get('excluded_defects', [])

    true_defect_data = get_true_defect_coordinates(
        store.layer_data,
        excluded_layers=excluded_layers,
        excluded_defect_types=excluded_defects
    )

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

        # --- Edge vs Center Analysis (User Defined Logic) ---
        st.subheader("Zonal Yield")

        edge_alive = 0
        edge_total = 0
        center_alive = 0
        center_total = 0
        middle_alive = 0
        middle_total = 0

        total_rows_grid = panel_rows * 2
        total_cols_grid = panel_cols * 2

        for r in range(total_rows_grid):
            for c in range(total_cols_grid):
                is_dead = (c, r) in true_defect_data

                # Calculate Ring Index (Distance from nearest edge)
                # 0 = Outer Ring, 1 = Ring 2, etc.
                dist_x = min(c, total_cols_grid - 1 - c)
                dist_y = min(r, total_rows_grid - 1 - r)
                ring_index = min(dist_x, dist_y)

                if ring_index == 0:
                    # Edge: Outer Ring (1 unit thick)
                    edge_total += 1
                    if not is_dead: edge_alive += 1
                elif 1 <= ring_index <= 2:
                    # Middle: Rings 2 and 3 (Indices 1 and 2)
                    middle_total += 1
                    if not is_dead: middle_alive += 1
                else:
                    # Center: The rest (Index 3+)
                    center_total += 1
                    if not is_dead: center_alive += 1

        # Render Metrics
        c_yield = (center_alive / center_total * 100) if center_total > 0 else 0
        m_yield = (middle_alive / middle_total * 100) if middle_total > 0 else 0
        e_yield = (edge_alive / edge_total * 100) if edge_total > 0 else 0

        # Displaying with counts for verification
        col1, col2, col3 = st.columns(3)
        col1.metric("Center Yield", f"{c_yield:.1f}%", help=f"Inner Core (Ring 4+). Total Units: {center_total}")
        col2.metric("Middle Yield", f"{m_yield:.1f}%", help=f"Rings 2 & 3. Total Units: {middle_total}")
        col3.metric("Edge Yield", f"{e_yield:.1f}%", help=f"Outer Ring (Ring 1). Total Units: {edge_total}")

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
