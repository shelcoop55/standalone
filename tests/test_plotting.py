import pytest
import pandas as pd
import plotly.graph_objects as go
from src.plotting import (
    create_grid_shapes,
    create_defect_traces,
    create_pareto_trace,
    create_grouped_pareto_trace,
    create_still_alive_map
)
from src.config import ALIVE_CELL_COLOR, DEFECTIVE_CELL_COLOR, PANEL_COLOR

@pytest.fixture
def sample_plot_df() -> pd.DataFrame:
    """A fixture to create a sample DataFrame for plotting tests."""
    data = {
        'DEFECT_ID': [101, 102, 103, 104],
        'DEFECT_TYPE': ['Nick', 'Short', 'Cut', 'Nick'],
        'Verification': ['Under Verification', 'Under Verification', 'Under Verification', 'Under Verification'],
        'HAS_VERIFICATION_DATA': [False, False, False, False],
        'UNIT_INDEX_X': [0, 1, 0, 1],
        'UNIT_INDEX_Y': [0, 0, 1, 1],
        'QUADRANT': ['Q1', 'Q2', 'Q3', 'Q4'],
        'plot_x': [10, 20, 10, 20],
        'plot_y': [10, 10, 20, 20],
    }
    return pd.DataFrame(data)

def test_create_grid_shapes_with_fill(sample_plot_df):
    """Tests that the grid shapes are created with a fill color by default."""
    shapes = create_grid_shapes(panel_rows=1, panel_cols=1, quadrant='All', fill=True)
    # Find the main quadrant background rectangle
    quadrant_rect = next((s for s in shapes if s.get('type') == 'rect' and 'fillcolor' in s and s['fillcolor'] == PANEL_COLOR), None)
    assert quadrant_rect is not None, "A filled quadrant rectangle should be present"

def test_create_grid_shapes_without_fill(sample_plot_df):
    """Tests that the grid shapes can be created without a fill color."""
    shapes = create_grid_shapes(panel_rows=1, panel_cols=1, quadrant='All', fill=False)
    # Ensure no shape has the panel fill color
    quadrant_rect = next((s for s in shapes if s.get('type') == 'rect' and 'fillcolor' in s and s['fillcolor'] == PANEL_COLOR), None)
    assert quadrant_rect is None, "No filled quadrant rectangle should be present"

def test_create_defect_traces_smoke(sample_plot_df):
    """Smoke test to ensure create_defect_traces runs without errors."""
    traces = create_defect_traces(sample_plot_df)
    assert isinstance(traces, list)
    assert all(isinstance(t, go.Scatter) for t in traces)

def test_create_pareto_trace_smoke(sample_plot_df):
    """Smoke test to ensure create_pareto_trace runs without errors."""
    trace = create_pareto_trace(sample_plot_df)
    assert isinstance(trace, go.Bar)

def test_create_grouped_pareto_trace_smoke(sample_plot_df):
    """Smoke test to ensure create_grouped_pareto_trace runs without errors."""
    traces = create_grouped_pareto_trace(sample_plot_df)
    assert isinstance(traces, list)
    assert all(isinstance(t, go.Bar) for t in traces)

def test_create_still_alive_map():
    """
    Tests that the still alive map correctly colors cells and generates the grid.
    """
    # Use a 2x2 grid per quadrant to ensure internal grid lines are generated.
    panel_rows, panel_cols = 2, 2
    total_cells = (panel_rows * 2) * (panel_cols * 2)

    # Define some cells as having "True" defects.
    true_defect_coords = {(0, 0), (1, 1), (3, 2)}

    shapes = create_still_alive_map(panel_rows, panel_cols, true_defect_coords)

    assert isinstance(shapes, list)

    # Test colored cells
    colored_cells = [s for s in shapes if s.get('type') == 'rect' and s.get('line', {}).get('width') == 0]
    assert len(colored_cells) == total_cells
    defective_count = sum(1 for s in colored_cells if s['fillcolor'] == DEFECTIVE_CELL_COLOR)
    assert defective_count == len(true_defect_coords)

    # Test grid lines (they have a width > 0)
    grid_lines = [s for s in shapes if s.get('type') == 'line']
    assert len(grid_lines) > 0, "Grid lines should be drawn over the colored cells"