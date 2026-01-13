import pytest
import pandas as pd
from src.data_handler import prepare_multi_layer_data
from src.config import SAFE_VERIFICATION_VALUES

def test_prepare_multi_layer_data():
    """
    Tests that prepare_multi_layer_data correctly:
    1. Aggregates data from multiple layers/sides.
    2. Filters out 'Safe' verification values.
    3. Adds the correct 'Layer_Label'.
    4. Adds the correct 'LAYER_NUM'.
    """

    # Mock Data Setup
    # Layer 1 Front: 1 True Defect, 1 Safe Defect
    df_l1_f = pd.DataFrame({
        'DEFECT_ID': [1, 2],
        'Verification': ['T', 'N'], # 'N' should be filtered out
        'UNIT_INDEX_X': [0, 0],
        'UNIT_INDEX_Y': [0, 0],
        'plot_x': [1, 1],
        'plot_y': [1, 1]
    })

    # Layer 1 Back: 1 True Defect
    df_l1_b = pd.DataFrame({
        'DEFECT_ID': [3],
        'Verification': ['Short'],
        'UNIT_INDEX_X': [1],
        'UNIT_INDEX_Y': [1],
        'plot_x': [2],
        'plot_y': [2]
    })

    # Layer 2 Front: All Safe Defects
    df_l2_f = pd.DataFrame({
        'DEFECT_ID': [4, 5],
        'Verification': ['FALSE', 'F'], # Both safe
        'UNIT_INDEX_X': [2, 2],
        'UNIT_INDEX_Y': [2, 2],
        'plot_x': [3, 3],
        'plot_y': [3, 3]
    })

    layer_data = {
        1: {'F': df_l1_f, 'B': df_l1_b},
        2: {'F': df_l2_f}
    }

    # Execute Function
    result_df = prepare_multi_layer_data(layer_data)

    # Assertions

    # 1. Check Row Count: Should be 2 (1 from L1F, 1 from L1B). L2F is all filtered.
    assert len(result_df) == 2

    # 2. Check Layer Labels
    expected_labels = sorted(['Layer 1 (Front)', 'Layer 1 (Back)'])
    actual_labels = sorted(result_df['Layer_Label'].unique().tolist())
    assert actual_labels == expected_labels

    # 3. Verify 'Safe' values are gone
    # We shouldn't see Defect ID 2 (N), 4 (FALSE), 5 (F)
    assert 2 not in result_df['DEFECT_ID'].values
    assert 4 not in result_df['DEFECT_ID'].values
    assert 5 not in result_df['DEFECT_ID'].values

    # 4. Verify True values are present
    assert 1 in result_df['DEFECT_ID'].values
    assert 3 in result_df['DEFECT_ID'].values

    # 5. Check LAYER_NUM
    assert 'LAYER_NUM' in result_df.columns
    assert sorted(result_df['LAYER_NUM'].unique().tolist()) == [1]

def test_prepare_multi_layer_data_empty():
    """Test with empty input."""
    result = prepare_multi_layer_data({})
    assert result.empty

def test_prepare_multi_layer_data_no_verification_col():
    """Test robustness when Verification column is missing (should default to keep if logic allows, or handle gracefully)."""

    df = pd.DataFrame({'DEFECT_ID': [1], 'Layer_Label': ['Test']})
    layer_data = {1: {'F': df}}

    result = prepare_multi_layer_data(layer_data)
    assert len(result) == 1
    assert result.iloc[0]['Layer_Label'] == 'Layer 1 (Front)'
    assert result.iloc[0]['LAYER_NUM'] == 1
