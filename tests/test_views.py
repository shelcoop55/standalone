import unittest
from unittest.mock import MagicMock
from src.views.utils import get_geometry_context
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

if __name__ == '__main__':
    unittest.main()
