import pytest
import pandas as pd
import numpy as np
from src.data_handler import aggregate_stress_data, StressMapData, calculate_yield_killers, get_cross_section_matrix, YieldKillerMetrics

@pytest.fixture
def sample_layer_data():
    """
    Creates a sample layer_data dictionary for testing.
    Panel size: 2x2 (Width=4, Height=4 units total).
    """
    # Layer 1: Front side. Defect at (0,0) [Q1]
    df1 = pd.DataFrame({
        'DEFECT_ID': [1],
        'DEFECT_TYPE': ['Short'],
        'UNIT_INDEX_X': [0],
        'UNIT_INDEX_Y': [0],
        'Verification': ['Short'], # True defect
        'PHYSICAL_X': [0], # Calculated by load_data usually
        'SIDE': ['F']
    })

    # Layer 1: Back side. Defect at (0,0) raw [Q1].
    # Physical X for Back side with width 4: (4-1) - 0 = 3.
    # So defect should map to (3,0) [Q2].
    df2 = pd.DataFrame({
        'DEFECT_ID': [2],
        'DEFECT_TYPE': ['Open'],
        'UNIT_INDEX_X': [0],
        'UNIT_INDEX_Y': [0],
        'Verification': ['Open'],
        'PHYSICAL_X': [3], # Simulating correct loading logic
        'SIDE': ['B']
    })

    return {1: {'F': df1, 'B': df2}}

def test_aggregate_stress_data_cumulative(sample_layer_data):
    """Test standard cumulative aggregation."""
    panel_rows = 2
    panel_cols = 2

    result = aggregate_stress_data(sample_layer_data, [1], panel_rows, panel_cols)

    assert isinstance(result, StressMapData)
    assert result.total_defects == 2

    # Check grid counts
    # (0,0) should have 1 defect (Front)
    assert result.grid_counts[0, 0] == 1
    # (0,3) should have 1 defect (Back, physically flipped)
    assert result.grid_counts[0, 3] == 1

    # Check Dominant Layer
    assert result.dominant_layer[0, 0] == 1
    assert result.dominant_count[0, 0] == 1

    # Check Hover Text
    assert "Short" in str(result.hover_text[0, 0])
    assert "Open" in str(result.hover_text[0, 3])

def test_calculate_yield_killers(sample_layer_data):
    """Test KPI calculation."""
    panel_rows = 2
    panel_cols = 2

    metrics = calculate_yield_killers(sample_layer_data, panel_rows, panel_cols)

    assert isinstance(metrics, YieldKillerMetrics)
    # Layer 1 has 2 defects
    assert metrics.top_killer_layer == "Layer 1"
    assert metrics.top_killer_count == 2

    # Side Bias: 1 Front, 1 Back -> Balanced
    assert metrics.side_bias == "Balanced"
    assert metrics.side_bias_diff == 0

def test_get_cross_section_matrix(sample_layer_data):
    """Test Z-Axis slicing."""
    panel_rows = 2
    panel_cols = 2

    # Slice Y (Row) at Index 0.
    # Layer 1 has defects at X=0 and X=3 at Y=0.
    matrix, layer_labels, axis_labels = get_cross_section_matrix(
        sample_layer_data, 'Y', 0, panel_rows, panel_cols
    )

    assert len(layer_labels) == 1 # Only Layer 1
    assert "L1" in layer_labels
    assert matrix.shape == (1, 4) # 1 Layer x 4 Width

    # Check values
    assert matrix[0, 0] == 1
    assert matrix[0, 3] == 1
    assert matrix[0, 1] == 0

    # Slice X (Col) at Index 0.
    # Should see defect at Y=0 for Layer 1.
    matrix_x, _, _ = get_cross_section_matrix(
        sample_layer_data, 'X', 0, panel_rows, panel_cols
    )
    assert matrix_x[0, 0] == 1 # Y=0

    # Slice X (Col) at Index 1 (Empty).
    matrix_x_empty, _, _ = get_cross_section_matrix(
        sample_layer_data, 'X', 1, panel_rows, panel_cols
    )
    assert matrix_x_empty[0, 0] == 0
