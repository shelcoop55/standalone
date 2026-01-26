from src.state import SessionStore
from src.core.geometry import GeometryContext, GeometryEngine
from src.core.config import DEFAULT_OFFSET_X, DEFAULT_OFFSET_Y, DEFAULT_GAP_X, DEFAULT_GAP_Y

def get_geometry_context(store: SessionStore) -> GeometryContext:
    """
    Constructs the GeometryContext from the current session parameters.
    Ensures correct mapping of stored parameters to GeometryEngine inputs.
    """
    params = store.analysis_params

    # Extract dynamic gaps (User Inputs)
    # Prefer 'dyn_gap_x' if available (stored by new app.py)
    # Fallback to 'gap_x' if it represents the dynamic gap in legacy contexts
    # But strictly speaking, 'gap_x' in store might be effective gap.
    # We should default to a safe small value if dyn_gap_x is missing.
    dyn_gap_x = params.get("dyn_gap_x", params.get("gap_x", 3.0))
    dyn_gap_y = params.get("dyn_gap_y", params.get("gap_y", 3.0))

    # Extract Fixed Offsets/Gaps if customized (or use defaults)
    fixed_off_x = params.get("fixed_offset_x", DEFAULT_OFFSET_X)
    fixed_off_y = params.get("fixed_offset_y", DEFAULT_OFFSET_Y)
    fixed_gap_x = params.get("fixed_gap_x", DEFAULT_GAP_X)
    fixed_gap_y = params.get("fixed_gap_y", DEFAULT_GAP_Y)

    return GeometryEngine.calculate_layout(
        panel_rows=params.get("panel_rows", 7),
        panel_cols=params.get("panel_cols", 7),
        dyn_gap_x=dyn_gap_x,
        dyn_gap_y=dyn_gap_y,
        fixed_offset_x=fixed_off_x,
        fixed_offset_y=fixed_off_y,
        fixed_gap_x=fixed_gap_x,
        fixed_gap_y=fixed_gap_y,
        visual_origin_x=params.get("visual_origin_x", 0.0),
        visual_origin_y=params.get("visual_origin_y", 0.0)
    )
