import unittest
from src.core.geometry import GeometryEngine, GeometryContext
from src.core.config import DEFAULT_GAP_X, DEFAULT_GAP_Y, DEFAULT_OFFSET_X, DEFAULT_OFFSET_Y

class TestGeometryEngine(unittest.TestCase):
    def test_calculate_layout_defaults(self):
        ctx = GeometryEngine.calculate_layout(
            panel_rows=7,
            panel_cols=7,
            dyn_gap_x=3.0,
            dyn_gap_y=3.0
        )
        self.assertIsInstance(ctx, GeometryContext)
        self.assertGreater(ctx.panel_width, 0)
        self.assertGreater(ctx.panel_height, 0)
        self.assertGreater(ctx.cell_width, 0)
        self.assertGreater(ctx.cell_height, 0)

        # Check Effective Gap logic: fixed + 2*dyn
        expected_eff_gap_x = DEFAULT_GAP_X + 2 * 3.0
        self.assertAlmostEqual(ctx.effective_gap_x, expected_eff_gap_x)

        # Check Offset Logic: fixed + dyn
        expected_off_x = DEFAULT_OFFSET_X + 3.0
        self.assertAlmostEqual(ctx.offset_x, expected_off_x)

    def test_calculate_layout_custom(self):
        ctx = GeometryEngine.calculate_layout(
            panel_rows=10,
            panel_cols=5,
            dyn_gap_x=5.0,
            dyn_gap_y=5.0,
            fixed_gap_x=10.0,
            fixed_gap_y=10.0,
            fixed_offset_x=2.0,
            fixed_offset_y=2.0
        )
        # Eff gap = 10 + 2*5 = 20
        self.assertAlmostEqual(ctx.effective_gap_x, 20.0)
        # Offset = 2 + 5 = 7
        self.assertAlmostEqual(ctx.offset_x, 7.0)

if __name__ == '__main__':
    unittest.main()
