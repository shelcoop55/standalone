import pytest
import pandas as pd
import numpy as np
from src.data_handler import aggregate_stress_data, StressMapData

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
        'PHYSICAL_X': [0] # Calculated by load_data usually
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
        'PHYSICAL_X': [3] # Simulating correct loading logic
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

def test_aggregate_stress_data_dominant_logic():
    """Test dominant layer logic."""
    # Layer 1: 2 defects at (0,0)
    df1 = pd.DataFrame({
        'DEFECT_ID': [1, 2],
        'DEFECT_TYPE': ['A', 'A'],
        'UNIT_INDEX_X': [0, 0], 'UNIT_INDEX_Y': [0, 0],
        'Verification': ['T', 'T'], 'PHYSICAL_X': [0, 0]
    })
    # Layer 2: 1 defect at (0,0)
    df2 = pd.DataFrame({
        'DEFECT_ID': [3],
        'DEFECT_TYPE': ['B'],
        'UNIT_INDEX_X': [0], 'UNIT_INDEX_Y': [0],
        'Verification': ['T'], 'PHYSICAL_X': [0]
    })

    layer_data = {
        1: {'F': df1},
        2: {'F': df2}
    }

    result = aggregate_stress_data(layer_data, [1, 2], 2, 2)

    # Total count at (0,0) = 3
    assert result.grid_counts[0, 0] == 3

    # Dominant Layer should be 1 (count 2 vs 1)
    assert result.dominant_layer[0, 0] == 1
    assert result.dominant_count[0, 0] == 2
