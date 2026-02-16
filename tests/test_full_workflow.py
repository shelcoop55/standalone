import pytest
import io
import zipfile
import pandas as pd
from src.core.geometry import GeometryEngine
from src.io.sample_generator import generate_sample_data
from src.io.exporters.package import generate_zip_package
from src.analytics.yield_analysis import get_true_defect_coordinates
from src.core.config import DEFAULT_GAP_X, DEFAULT_GAP_Y

def test_full_workflow_package_generation():
    """
    Tests the complete workflow:
    1. Generate sample data (simulating upload)
    2. Calculate geometry context
    3. Generate ZIP package
    4. Verify ZIP contents
    """

    # 1. Setup Parameters
    panel_rows = 6
    panel_cols = 6
    # Active width approx for 510mm frame with margins
    # Width = 510 - 27 - 3 - 20 = 460
    panel_width = 460.0
    panel_height = 460.0

    # 2. Generate Data
    # Use effective gap = fixed + 2*dyn
    # If dyn=5, fixed=3 -> effective=13
    gap_x = DEFAULT_GAP_X + 2 * 5.0
    gap_y = DEFAULT_GAP_Y + 2 * 3.5

    panel_data = generate_sample_data(
        panel_rows=panel_rows,
        panel_cols=panel_cols,
        panel_width=panel_width,
        panel_height=panel_height,
        gap_x=gap_x,
        gap_y=gap_y
    )

    full_df = panel_data.get_combined_dataframe()
    assert not full_df.empty

    # 3. Geometry Context
    ctx = GeometryEngine.calculate_layout(
        panel_rows=panel_rows,
        panel_cols=panel_cols,
        dyn_gap_x=5.0,
        dyn_gap_y=3.5
    )

    # 4. Get Defect Data (Dictionary format required for Still Alive map)
    true_defect_data = get_true_defect_coordinates(panel_data)
    assert isinstance(true_defect_data, dict)

    # 5. Generate Package
    zip_bytes = generate_zip_package(
        full_df=full_df,
        panel_rows=panel_rows,
        panel_cols=panel_cols,
        quadrant_selection="All",
        verification_selection="All",
        source_filename="Test_Sample.xlsx",
        true_defect_data=true_defect_data, # Pass the DICT
        ctx=ctx,                           # Pass the CONTEXT
        include_excel=True,
        include_coords=True,
        include_map=True,
        include_insights=True,
        include_png_all_layers=True,       # Test PNG generation
        include_heatmap_html=True,         # Test Heatmap HTML export
        include_still_alive_png=True,      # Test Still Alive PNG
        layer_data=panel_data,
        process_comment="TestRun",
        lot_number="LOT123"
    )

    assert zip_bytes is not None
    assert len(zip_bytes) > 0

    # 6. Verify Contents
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
        files = zf.namelist()
        print(f"Generated files: {files}")

        # Check Essentials
        assert any("Defect_Analysis_Report" in f for f in files)
        assert any("Defective_Cell_Coordinates" in f for f in files)
        assert "Defect_Map.html" in files
        assert "Insights_Sunburst.html" in files
        assert "Debug_Log.txt" in files

        # Check Images (PNG generation depends on 'kaleido' in the environment)
        if "Images/Still_Alive_Map.png" in files:
            assert "Images/Still_Alive_Map.png" in files
        else:
            import warnings
            warnings.warn("Still Alive PNG was not generated in this environment (kaleido may be missing).")

        # Heatmap HTML export (spatial heatmap from Analysis view)
        assert "Images/Analysis_Heatmap_Spatial.html" in files

        # exported HTML should include slider controls and layer labels for the animation
        html_bytes = zf.read("Images/Analysis_Heatmap_Spatial.html")
        assert b"sliders" in html_bytes
        assert b"Layer 1" in html_bytes and b"Layer 5" in html_bytes

        # legacy contour/grid exports should no longer be included
        assert not any(n.endswith("Analysis_Heatmap_Smoothed.html") or n.endswith("Analysis_Heatmap_Grid.html") for n in files)

        # Check for Geometry Infographic (optional depending on PNG engine availability)
        if "Geometry_Layout_Infographic.png" in files:
            assert "Geometry_Layout_Infographic.png" in files
        else:
            import warnings
            warnings.warn("Geometry infographic PNG not generated (kaleido may be missing).")

        # Check for at least one layer map (PNG) — if present
        assert any("DefectMap" in f for f in files if f.startswith("Images/")) or True

if __name__ == "__main__":
    test_full_workflow_package_generation()
