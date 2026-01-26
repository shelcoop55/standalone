import pytest
from src.core import config
import json
from unittest.mock import patch
import builtins

def test_load_defect_styles_success():
    """
    Tests that the defect styles are loaded correctly from the JSON file.
    """
    # Reload the config module to ensure we are testing the file load
    import importlib
    importlib.reload(config)

    styles = config.load_defect_styles()

    # Check that it's a dictionary and not empty
    assert isinstance(styles, dict)
    assert styles

    # Check for a known key-value pair from the actual file
    # Adjust path for test execution context if needed, but assuming execution from root
    with open("assets/defect_styles.json", 'r') as f:
        expected_styles = json.load(f)
    assert styles == expected_styles

def test_load_defect_styles_fallback(monkeypatch):
    """
    Tests that the fallback mechanism works when the JSON file is not found.
    """
    # Use monkeypatch to simulate a FileNotFoundError
    # We need to mock open where it is used.
    # Since config.py imports builtins or uses open directly, we mock builtins.open

    real_open = builtins.open

    def mock_open_raises_error(file, *args, **kwargs):
        # Only raise error for the specific file we want to fail
        if str(file).endswith("defect_styles.json"):
            raise FileNotFoundError("File not found for testing")
        return real_open(file, *args, **kwargs)

    monkeypatch.setattr("builtins.open", mock_open_raises_error)

    # Reload the config module to trigger the file load with the mocked 'open'
    import importlib
    importlib.reload(config)

    styles = config.load_defect_styles()

    # Check that the returned styles are the hardcoded fallback styles
    assert isinstance(styles, dict)
    assert 'Nick' in styles
    assert styles['Nick'] == '#9B59B6'
    assert styles['Short'] == '#E74C3C'
