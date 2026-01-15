import pytest
import pandas as pd
from unittest.mock import MagicMock
from src.utils import generate_standard_filename

def test_generate_standard_filename_all_layers():
    """Test filename generation for all layers."""
    params = {'process_comment': 'TestProc', 'lot_number': '12345'}
    filename = generate_standard_filename("TEST_PREFIX", None, {}, params, "zip")
    assert filename == "TEST_PREFIX_ALL_LAYERS_TestProc_12345.zip"

def test_generate_standard_filename_single_layer_no_bu():
    """Test filename generation for single layer without BU name."""
    # Mock layer_data structure: dict[int][side]['SOURCE_FILE'] -> Series
    # We need to ensure the object returned by layer_data[1]['F'] supports ['SOURCE_FILE']
    # If it's a dict, it works.
    layer_data = {
        1: {
            'F': {'SOURCE_FILE': pd.Series(["SomeFile.xlsx"])}
        }
    }
    params = {}
    filename = generate_standard_filename("PREFIX", 1, layer_data, params, "csv")
    # Current behavior: falls back to filename if BU pattern not found
    assert filename == "PREFIX_LAYER_(SomeFile.xlsx).csv"

def test_generate_standard_filename_single_layer_with_bu():
    """Test filename generation for single layer with BU name."""
    layer_data = {
        2: {
            'F': {'SOURCE_FILE': pd.Series(["BU-02F_Data.xlsx"])}
        }
    }
    params = {'lot_number': 'LOT99'}
    filename = generate_standard_filename("PREFIX", 2, layer_data, params, "zip")
    assert filename == "PREFIX_LAYER_(BU-02)_LOT99.zip"

def test_generate_standard_filename_sanitization():
    """Test that special characters are sanitized."""
    params = {'process_comment': 'Proc/Step', 'lot_number': 'Lot#1'}
    filename = generate_standard_filename("PRE", None, {}, params, "zip")
    # / becomes _, # becomes _
    # isalnum or ._-()
    # ' ' is not in allowed list?
    # Logic: "".join([c if c.isalnum() or c in "._-()" else "_" for c in base_name])
    # space becomes _
    assert filename == "PRE_ALL_LAYERS_Proc_Step_Lot_1.zip"

def test_generate_standard_filename_with_panel_data_mock():
    """Test with a mock that behaves like PanelData/dict."""
    class MockLayer:
        def __getitem__(self, key):
            if key == 'SOURCE_FILE':
                return pd.Series(["BU-05F.xlsx"])
            return None

    layer_data = {
        5: {'F': MockLayer()}
    }

    params = {}
    filename = generate_standard_filename("PREFIX", 5, layer_data, params, "zip")
    assert filename == "PREFIX_LAYER_(BU-05).zip"
