import pytest
import pandas as pd
import plotly.graph_objects as go
from src.plotting import (
    create_grid_shapes,
    create_defect_traces,
    create_pareto_trace,
    create_grouped_pareto_trace,
    create_still_alive_map,
    create_defect_sankey,
    create_defect_sunburst,
    create_multi_layer_defect_map
)
from src.config import ALIVE_CELL_COLOR, DEFECTIVE_CELL_COLOR, PANEL_COLOR, TEXT_COLOR, BACKGROUND_COLOR

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

    # Define some cells as having "True" defects with metadata.
    # Dict[Tuple[int, int], Dict[str, Any]]
    true_defect_coords = {
        (0, 0): {'first_killer_layer': 1, 'defect_summary': 'L1: 1'},
        (1, 1): {'first_killer_layer': 2, 'defect_summary': 'L2: 1'},
        (3, 2): {'first_killer_layer': 1, 'defect_summary': 'L1: 1'}
    }

    shapes, traces = create_still_alive_map(panel_rows, panel_cols, true_defect_coords)

    assert isinstance(shapes, list)
    assert isinstance(traces, list)

    # Test colored cells
    colored_cells = [s for s in shapes if s.get('type') == 'rect' and s.get('line', {}).get('width') == 0]
    assert len(colored_cells) == total_cells
    defective_count = sum(1 for s in colored_cells if s['fillcolor'] == DEFECTIVE_CELL_COLOR)
    assert defective_count == len(true_defect_coords)

    # Test grid lines (they have a width > 0)
    grid_lines = [s for s in shapes if s.get('type') == 'line']
    assert len(grid_lines) > 0, "Grid lines should be drawn over the colored cells"

    # Test Traces (Tooltips)
    assert len(traces) == 1
    assert len(traces[0].x) == len(true_defect_coords)

def test_create_defect_sankey_overlap():
    """
    Tests that create_defect_sankey correctly handles overlapping labels
    between DEFECT_TYPE and Verification columns.
    """
    df = pd.DataFrame({
        'DEFECT_TYPE': ['Short', 'Cut'],
        'Verification': ['Short', 'N'], # 'Short' overlaps
        'HAS_VERIFICATION_DATA': [True, True]
    })

    fig = create_defect_sankey(df)
    assert fig is not None, "Sankey figure should be created"

    # Extract data from the figure
    sankey = fig.data[0]
    node_labels = sankey.node.label
    links = sankey.link

    # We expect 4 distinct nodes: Cut, Short (Defect), Short (Verif), N
    # The actual code now generates labels like "Cut (1 - 50.0%)"
    assert len(node_labels) == 4, f"Expected 4 nodes, got {len(node_labels)}: {node_labels}"

    # Check that the base names exist in the labels (checking substrings)
    labels_str = ",".join(node_labels)
    assert "Cut" in labels_str
    assert "Short" in labels_str
    assert "N" in labels_str

    # We can check strict order of substrings if we want, but verifying they are distinct and present is key
    # Source nodes (Defects) come first: Cut, Short
    # Target nodes (Verif) come second: N, Short

    # Check connections based on above indices logic used in the function
    # Sources and Targets
    sources = list(links.source)
    targets = list(links.target)

    # We expect 2 links
    assert len(sources) == 2

    # Link 1: Cut (Defect) -> N (Verif)
    # Link 2: Short (Defect) -> Short (Verif)

    # Since we can't easily predict the exact indices without replicating sorting logic exactly,
    # we rely on the fact that targets must be offset by number of source nodes.
    # num_sources = 2
    # targets should be >= 2
    assert all(t >= 2 for t in targets)
    assert all(s < 2 for s in sources)

    # Verify colors/template setting for export
    assert fig.layout.paper_bgcolor == BACKGROUND_COLOR
    assert fig.layout.font.color == TEXT_COLOR

def test_create_defect_sunburst_styles(sample_plot_df):
    """
    Tests that the sunburst chart has correct export styles.
    """
    # Enable verification data simulation
    sample_plot_df['HAS_VERIFICATION_DATA'] = True

    fig = create_defect_sunburst(sample_plot_df)

    assert fig.layout.paper_bgcolor == BACKGROUND_COLOR
    assert fig.layout.font.color == TEXT_COLOR

    # Check total label logic
    # We need to dig into the trace data
    trace = fig.data[0]
    # Check if root label contains "Total<br>"
    assert any("Total<br>" in label for label in trace.labels)

def test_create_multi_layer_defect_map():
    """
    Tests the new multi-layer defect map function.
    """
    df = pd.DataFrame({
        'plot_x': [10, 20, 30],
        'plot_y': [10, 20, 30],
        'Layer_Label': ['Layer 1 (Front)', 'Layer 1 (Back)', 'Layer 2 (Front)'],
        'LAYER_NUM': [1, 1, 2],
        'SIDE': ['F', 'B', 'F'], # Required for symbol logic
        'DEFECT_TYPE': ['Type A', 'Type B', 'Type A'],
        'DEFECT_ID': [1, 2, 3],
        'UNIT_INDEX_X': [1, 2, 3],
        'UNIT_INDEX_Y': [1, 2, 3],
        'Verification': ['T', 'T', 'T'],
        'SOURCE_FILE': ['f1', 'f1', 'f2'],
        'physical_plot_x_flipped': [10, 20, 30],
        'physical_plot_x_raw': [10, 20, 30],
        'X_COORDINATES': [10.5, 20.5, 30.5],
        'Y_COORDINATES': [10.5, 20.5, 30.5]
    })

    fig = create_multi_layer_defect_map(df, panel_rows=5, panel_cols=5)

    assert isinstance(fig, go.Figure)

    # Should have 3 traces: L1-B, L1-F, L2-F (Sorted order of sides: B, F)
    assert len(fig.data) == 3

    # Trace 0: Layer 1, Side B
    trace0 = fig.data[0]
    assert "Back" in trace0.name
    assert trace0.marker.symbol == 'diamond' # Back = Diamond

    # Trace 1: Layer 1, Side F
    trace1 = fig.data[1]
    assert "Front" in trace1.name
    assert trace1.marker.symbol == 'circle' # Front = Circle

    # Trace 2: Layer 2, Side F
    trace2 = fig.data[2]
    assert "Front" in trace2.name

    # Check colors: Layer 1 traces should match
    assert trace0.marker.color == trace1.marker.color
    # Layer 2 trace should differ from Layer 1
    assert trace2.marker.color != trace0.marker.color
