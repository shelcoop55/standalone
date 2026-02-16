
import sys
import os
import streamlit as st
from unittest.mock import MagicMock

# Add project root to path
sys.path.append(os.getcwd())

def verify_persistence():
    print("Verifying persistence logic...")
    
    # Simulate session state
    st.session_state = {
        "heatmap_bin_size_mm": 25,
        "heatmap_color_scale": "Count per bin",
        "heatmap_zmax_count": 8
    }
    
    # We can't easily mock the entire streamlit funcs in a script without running streamlit,
    # but we can verify that our code PATTERN is correct by inspection or by mocking st.slider
    
    # Mock st.slider to capture 'value' arg
    st.slider = MagicMock()
    st.radio = MagicMock()
    
    # Import manager (this will execute imports, which is fine)
    from src.views.manager import ViewManager
    
    # Create instance
    store = MagicMock()
    vm = ViewManager(store)
    
    # We need to trigger the code block. 
    # It's inside _render_analysis_page_controls -> if 'Heatmap'
    
    # Mock attributes to enter the Heatmap block
    vm.store.active_view = 'analysis_dashboard'
    vm.store.analysis_subview = 'heatmap_view' # Value from ViewMode enum?
    # actually manager.py uses:
    # sub_map_rev = { ViewMode.HEATMAP.value: "Heatmap", ... }
    # So we need to match ViewMode.HEATMAP.value
    from src.enums import ViewMode
    vm.store.analysis_subview = ViewMode.HEATMAP.value
    
    # Call the function
    try:
        vm._render_analysis_page_controls()
    except Exception as e:
        # It might fail due to other UI dependencies we didn't mock (like columns)
        # But let's see if we hit the sliders first
        pass
        
    # Check if st.slider was called with our session state values
    
    # Bin Size
    # Expected: value=25
    calls = st.slider.call_args_list
    bin_call = None
    for c in calls:
        if "Bin size" in c[0][0]:
            bin_call = c
            break
            
    if bin_call:
        kwargs = bin_call[1]
        print(f"Bin Size Slider Value: {kwargs.get('value')}")
        if kwargs.get('value') == 25:
            print("SUCCESS: Bin size persistence verified.")
        else:
            print(f"FAIL: Expected 25, got {kwargs.get('value')}")
    else:
        print("FAIL: Bin size slider not found in calls.")

    # Color Scale Max (Count)
    # Expected: value=8
    zmax_call = None
    for c in calls:
        if "Color scale max" in c[0][0]:
            zmax_call = c
            break
            
    if zmax_call:
        kwargs = zmax_call[1]
        print(f"Zmax Slider Value: {kwargs.get('value')}")
        if kwargs.get('value') == 8:
            print("SUCCESS: Zmax persistence verified.")
        else:
            print(f"FAIL: Expected 8, got {kwargs.get('value')}")
    else:
        print("FAIL: Zmax slider not found in calls.")

if __name__ == "__main__":
    verify_persistence()
