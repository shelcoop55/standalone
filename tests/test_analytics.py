
import pytest
import pandas as pd
import numpy as np
from src.analytics.yield_analysis import get_cross_section_matrix, calculate_yield_killers
from src.analytics.stress import aggregate_stress_data_from_df
from src.core.models import PanelData, BuildUpLayer

@pytest.fixture
def mock_panel_data():
    # Create simple mock data
    df_l1 = pd.DataFrame({
        'UNIT_INDEX_X': [0, 1],
        'UNIT_INDEX_Y': [0, 0],
        'Verification': ['Real Defect', 'False'], # One Real, One False
        'SIDE': ['F', 'F'],
        'LAYER_NUM': [1, 1]
    })
    
    df_l2 = pd.DataFrame({
        'UNIT_INDEX_X': [0],
        'UNIT_INDEX_Y': [0],
        'Verification': ['Real Defect'],
        'SIDE': ['F'],
        'LAYER_NUM': [2]
    })

    # Mock BuildUpLayer objects
    l1 = BuildUpLayer(1, 'F', df_l1, 2, 2)
    l2 = BuildUpLayer(2, 'F', df_l2, 2, 2)
    
    pd_obj = PanelData()
    pd_obj.add_layer(l1)
    pd_obj.add_layer(l2)
    return pd_obj

def test_get_cross_section_matrix_y_axis(mock_panel_data):
    """Test cross section slicing along Y axis (row)."""
    # Slice at Y=0
    # Expected:
    # L1: X=0 (Real), X=1 (False -> Filtered Out). Count at X=0 should be 1.
    # L2: X=0 (Real). Count at X=0 should be 1.
    
    matrix, layer_labels, axis_labels = get_cross_section_matrix(
        mock_panel_data, 'Y', 0, panel_rows=2, panel_cols=2
    )
    
    # Matrix shape: (num_layers, total_cols) -> (2, 4)
    assert matrix.shape == (2, 4)
    assert layer_labels == ['L1', 'L2']
    
    # Check counts
    # L1 (Index 0) at X=0 -> 1
    assert matrix[0, 0] == 1
    # L1 at X=1 -> 0 (False filtered)
    assert matrix[0, 1] == 0
    
    # L2 (Index 1) at X=0 -> 1
    assert matrix[1, 0] == 1

def test_calculate_yield_killers(mock_panel_data):
    """Test KPI calculation."""
    # L1: 1 True Defect (at 0,0)
    # L2: 1 True Defect (at 0,0)
    # Total True Defects = 2.
    # Top Killer Layer: Tie? Or one of them.
    # Worst Unit: (0,0) with 2 defects.
    
    metrics = calculate_yield_killers(mock_panel_data, 2, 2)
    
    assert metrics is not None
    assert metrics.worst_unit == "X:0, Y:0"
    assert metrics.worst_unit_count == 2
    assert "Layer" in metrics.top_killer_layer

def test_aggregate_stress_data_basic():
    """Test stress map aggregation from DF."""
    df = pd.DataFrame({
        'UNIT_INDEX_X': [0, 0, 1],
        'UNIT_INDEX_Y': [0, 0, 1],
        'DEFECT_TYPE': ['TypeA', 'TypeB', 'TypeA']
    })
    
    # 2x2 Panel -> 4x4 Grid (Total Rows/Cols)
    result = aggregate_stress_data_from_df(df, panel_rows=2, panel_cols=2)
    
    # Grid Counts
    # (0,0): 2 defects
    # (1,1): 1 defect
    assert result.grid_counts[0, 0] == 2
    assert result.grid_counts[1, 1] == 1
    assert result.grid_counts[0, 1] == 0
    
    # Hover Text checking
    text_00 = result.hover_text[0, 0]
    assert "Total: 2" in text_00
    assert "TypeA" in text_00
    assert "TypeB" in text_00
