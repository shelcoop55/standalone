import pytest
from src.legacy_utils import get_bu_name_from_filename

def test_get_bu_name_from_filename():
    """Tests the extraction of BU names from filenames."""

    # Standard format: BU-XX... (Assumes filename only, no path)
    assert get_bu_name_from_filename("BU-01F.xlsx") == "BU-01"
    assert get_bu_name_from_filename("BU-02B.xls") == "BU-02"

    # Sample data format: Sample Data Layer X...
    assert get_bu_name_from_filename("Sample Data Layer 1") == "BU-01"
    assert get_bu_name_from_filename("Sample Data Layer 2F") == "BU-02"
    assert get_bu_name_from_filename("Sample Data Layer 10B") == "BU-10"

    # Fallback behavior: Returns original filename if no match
    assert get_bu_name_from_filename("random_file.txt") == "random_file.txt"
    assert get_bu_name_from_filename("Layer 1 data") == "Layer 1 data"
