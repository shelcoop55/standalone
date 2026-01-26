import unittest
from src.plotting.renderers.maps import create_defect_map_figure, create_still_alive_figure
from src.core.geometry import GeometryContext, GeometryEngine
import pandas as pd

class TestPlottingImports(unittest.TestCase):
    def test_imports(self):
        # Create Dummy Data
        df = pd.DataFrame({
            "UNIT_INDEX_X": [0],
            "UNIT_INDEX_Y": [0],
            "DEFECT_TYPE": ["A"],
            "DEFECT_ID": [101],
            "Verification": ["Unverified"],
            "HAS_VERIFICATION_DATA": [False],
            "plot_x": [10.0],
            "plot_y": [10.0]
        })

        ctx = GeometryEngine.calculate_layout(7, 7, 3.0, 3.0)

        fig = create_defect_map_figure(df, 7, 7, ctx)
        self.assertIsNotNone(fig)

        # Test Still Alive
        true_defects = {(0,0): {"first_killer_layer": 1, "defect_summary": "L1"}}
        fig2 = create_still_alive_figure(7, 7, true_defects, ctx)
        self.assertIsNotNone(fig2)

if __name__ == '__main__':
    unittest.main()
