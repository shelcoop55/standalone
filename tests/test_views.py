import unittest
from unittest.mock import MagicMock
import pandas as pd
from src.views.utils import get_geometry_context
from src.views.manager import _build_layer_labels
from src.state import SessionStore
from src.core.geometry import GeometryContext


class TestViewUtils(unittest.TestCase):
    def test_get_geometry_context(self):
        # Mock SessionStore
        store = MagicMock(spec=SessionStore)
        store.analysis_params = {
            "panel_rows": 5,
            "panel_cols": 5,
            "gap_x": 3.0,
            "gap_y": 3.0,
            "fixed_offset_x": 10.0,
            "fixed_offset_y": 10.0
        }

        ctx = get_geometry_context(store)

        self.assertIsInstance(ctx, GeometryContext)
        # Check gap logic: 3.0 passed as dyn_gap
        # Fixed Offset = 10.0
        # Offset = 10.0 + 3.0 = 13.0
        self.assertAlmostEqual(ctx.offset_x, 13.0)


class TestBuildLayerLabels(unittest.TestCase):
    """Tests for _build_layer_labels (layer dropdown/button labels)."""

    def test_empty_layer_list(self):
        store = MagicMock(spec=SessionStore)
        store.analysis_params = {}
        store.layer_data = {}
        out = _build_layer_labels(store, [])
        self.assertEqual(out, [])

    def test_layer_labels_with_source_file(self):
        store = MagicMock(spec=SessionStore)
        store.analysis_params = {"process_comment": ""}
        df = pd.DataFrame({"SOURCE_FILE": ["BU-01F.xlsx"]})
        store.layer_data = {1: {"F": df}}
        out = _build_layer_labels(store, [1])
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0]["num"], 1)
        self.assertEqual(out[0]["label"], "BU-01")

    def test_layer_labels_fallback_without_source_file(self):
        store = MagicMock(spec=SessionStore)
        store.analysis_params = {}
        # DataFrame with no SOURCE_FILE column (or empty) -> fallback to "Layer N"
        store.layer_data = {2: {"F": pd.DataFrame({"A": [1]})}}
        out = _build_layer_labels(store, [2])
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0]["num"], 2)
        self.assertEqual(out[0]["label"], "Layer 2")

    def test_layer_labels_with_process_comment(self):
        store = MagicMock(spec=SessionStore)
        store.analysis_params = {"process_comment": "Run A"}
        df = pd.DataFrame({"SOURCE_FILE": ["BU-03F.xlsx"]})
        store.layer_data = {3: {"F": df}}
        out = _build_layer_labels(store, [3])
        self.assertEqual(out[0]["label"], "BU-03 (Run A)")


if __name__ == '__main__':
    unittest.main()
