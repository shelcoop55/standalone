import pytest
import pandas as pd
from src.core.config import FRAME_WIDTH
from src.core.geometry import GeometryEngine
from src.io.ingestion import load_panel_data
from src.analytics.yield_analysis import get_true_defect_coordinates
from src.plotting.renderers.maps import create_still_alive_figure

def test_geometry_engine():
    ctx = GeometryEngine.calculate_layout(7, 7, 5.0, 3.5)
    assert ctx.panel_width > 0
    assert ctx.effective_gap_x > 0
    # Expected width: 510 - 2*13.5 - 3.0 - 4*5.0 = 510 - 27 - 3 - 20 = 460
    assert ctx.panel_width == 460.0

def test_ingestion_sample_data():
    # Load sample data (empty files list)
    panel_data = load_panel_data([], 7, 7, 470, 470, 3.0, 3.0)
    assert panel_data
    assert len(panel_data.get_all_layer_nums()) > 0
    df = panel_data.get_combined_dataframe()
    assert not df.empty
    assert 'Verification' in df.columns

def test_analytics_yield():
    panel_data = load_panel_data([], 7, 7, 470, 470, 3.0, 3.0)
    true_defects = get_true_defect_coordinates(panel_data)
    assert isinstance(true_defects, dict)
    if true_defects:
        key = next(iter(true_defects))
        val = true_defects[key]
        assert 'first_killer_layer' in val
        assert 'defect_summary' in val

def test_plotting_map():
    panel_data = load_panel_data([], 7, 7, 470, 470, 3.0, 3.0)
    true_defects = get_true_defect_coordinates(panel_data)
    fig = create_still_alive_figure(7, 7, true_defects)
    assert fig is not None
    # Check if we can create json (validates plotly object)
    json_str = fig.to_json()
    assert json_str

def test_analytics_stress():
    from src.analytics.stress import aggregate_stress_data
    panel_data = load_panel_data([], 7, 7, 470, 470, 3.0, 3.0)
    # Get a valid key
    layers = panel_data.get_all_layer_nums()
    if layers:
        sides = panel_data.get_sides_for_layer(layers[0])
        keys = [(layers[0], sides[0])]
        stress = aggregate_stress_data(panel_data, keys, 7, 7)
        assert stress.total_defects >= 0
