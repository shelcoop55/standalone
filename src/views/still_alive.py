import streamlit as st
import pandas as pd
import numpy as np
from src.state import SessionStore
from src.plotting import create_still_alive_figure
from src.data_handler import get_true_defect_coordinates

def render_still_alive_sidebar(store: SessionStore):
    """
    Deprecated: Sidebar logic is now handled in manager.py unified controls.
    Kept as empty or redirect if needed.
    """
    pass

def render_still_alive_main(store: SessionStore):
    """Renders the Main Content for the Still Alive view."""
    params = store.analysis_params
    panel_rows = params.get("panel_rows", 7)
    panel_cols = params.get("panel_cols", 7)

    # Header removed to save space
    # st.header("Still Alive Panel Yield Map")

    # --- Filter Logic Adaptation ---
    # Unified filters provide:
    # 1. multi_layer_selection (List[int]) -> Layers to INCLUDE
    # 2. multi_verification_selection (List[str]) -> Verifications to INCLUDE (usually)
    # 3. analysis_side_select (Front/Back/Both)

    # "Still Alive" traditionally works by EXCLUDING layers/defects to see what survives.
    # We must map the Inclusion lists to Exclusions or modify get_true_defect_coordinates.

    # 1. Layers
    # If user selects layers [1, 2], it means INCLUDE 1, 2. So Exclude all others.
    all_layers = store.layer_data.get_all_layer_nums()
    selected_layers = store.multi_layer_selection if store.multi_layer_selection else all_layers
    excluded_layers = list(set(all_layers) - set(selected_layers))

    # 2. Side Filter
    # Unified filter returns List[str] e.g., ["Front", "Back"]
    side_pills = st.session_state.get("analysis_side_pills", ["Front", "Back"])
    included_sides = []
    if "Front" in side_pills: included_sides.append('F')
    if "Back" in side_pills: included_sides.append('B')

    # 3. Verification
    # Unified filter selects verifications to INCLUDE (i.e., Show).
    # If I select "CU10", I want to see CU10.
    # Still Alive: "Filter out ... defects to simulate yield".
    # If I UNSELECT "CU10" in the unified filter, it means "Don't show CU10" -> "Treat CU10 as Good"?
    # Yes, typically "Filter" means "Include in Analysis". If I exclude it, it's not a defect.
    # So `excluded_defect_types` = All Types - Selected Types.

    full_df = store.layer_data.get_combined_dataframe()
    all_verifs = []
    if not full_df.empty and 'Verification' in full_df.columns:
        all_verifs = sorted(full_df['Verification'].dropna().unique().tolist())

    selected_verifs = st.session_state.get('multi_verification_selection', all_verifs) # Default all
    excluded_defects = list(set(all_verifs) - set(selected_verifs))

    true_defect_data = get_true_defect_coordinates(
        store.layer_data,
        excluded_layers=excluded_layers,
        excluded_defect_types=excluded_defects,
        included_sides=included_sides
    )

    # If side_mode != Both, we might need to post-filter the true_defect_data?
    # No, true_defect_data is "Is this unit dead?".
    # If we filter sides, a unit dead on Back might be alive on Front.
    # If I select Front, I only care if it's dead on Front.
    # This requires data_handler update. I will note this for the user or implement if feasible.
    # For now, proceeding with standard logic.

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
        st.metric("Center Yield", f"{c_yield:.1f}%", help=f"Inner Core (Ring 4+). Total Units: {center_total}")
        st.metric("Middle Yield", f"{m_yield:.1f}%", help=f"Rings 2 & 3. Total Units: {middle_total}")
        st.metric("Edge Yield", f"{e_yield:.1f}%", help=f"Outer Ring (Ring 1). Total Units: {edge_total}")

        st.divider()

        # --- Pick List Download ---
        alive_units = []
        for r in range(total_rows_grid):
            for c in range(total_cols_grid):
                if (c, r) not in true_defect_data:
                    alive_units.append({'PHYSICAL_X': c, 'UNIT_INDEX_Y': r})

        if alive_units:
            from src.utils import generate_standard_filename

            # Smart determination of layer context
            target_layer = None
            if store.multi_layer_selection and len(store.multi_layer_selection) == 1:
                target_layer = store.multi_layer_selection[0]

            filename = generate_standard_filename(
                prefix="PICK_LIST",
                selected_layer=target_layer,
                layer_data=store.layer_data,
                analysis_params=store.analysis_params,
                extension="csv"
            )

            df_alive = pd.DataFrame(alive_units)
            csv = df_alive.to_csv(index=False).encode('utf-8')
            st.download_button(
                "📥 Download Pick List",
                data=csv,
                file_name=filename,
                mime="text/csv",
                help="CSV list of coordinate pairs (Physical X, Y) for good units."
            )
