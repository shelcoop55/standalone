
import sys
import os
import pandas as pd
import numpy as np

# Add project root to path
sys.path.append(os.getcwd())

from src.plotting.renderers.charts import create_pareto_figure
from src.enums import Quadrant

def verify_pareto_improvements():
    print("Verifying Pareto Chart Improvements...")
    
    # Mock Data
    data = {
        'DEFECT_TYPE': ['Scratch', 'Dent', 'Scratch', 'Dent', 'Scratch', 'Pit', 'Pit', 'Other', 'Scratch', 'Dent'],
        'QUADRANT': ['Q1', 'Q2', 'Q1', 'Q3', 'Q2', 'Q1', 'Q4', 'Q2', 'Q3', 'Q1'],
        'Verification': ['Type A'] * 10
    }
    df = pd.DataFrame(data)
    
    # Test 1: Single Quadrant (Expect Vital Few Coloring + Line)
    print("\nTest 1: Single Quadrant (Q1)")
    fig_single = create_pareto_figure(df, quadrant_selection='Q1')
    
    # Check for Secondary Y-axis
    if 'yaxis2' in fig_single.layout:
        print("  SUCCESS: Secondary Y-axis (yaxis2) found.")
    else:
        print("  FAIL: yaxis2 missing.")
        
    # Check for Trace Types
    trace_types = [t.type for t in fig_single.data]
    print(f"  Traces: {trace_types}")
    if 'bar' in trace_types and 'scatter' in trace_types:
        print("  SUCCESS: Found Bar and Scatter (Line) traces.")
    else:
        print("  FAIL: Missing required traces.")
        
    # Check for text on bars (Smart Annotations)
    bar_trace = next(t for t in fig_single.data if t.type == 'bar')
    if hasattr(bar_trace, 'text') and bar_trace.text is not None:
         print("  SUCCESS: Bar trace has text annotations.")
    else:
         print("  FAIL: Bar trace missing text annotations.")

    # Test 2: All Quadrants (Expect Stacked Bars + Line)
    print("\nTest 2: All Quadrants (Stacked)")
    fig_all = create_pareto_figure(df, quadrant_selection='All')
    
    # Check for Secondary Y-axis
    if 'yaxis2' in fig_all.layout:
        print("  SUCCESS: Secondary Y-axis (yaxis2) found.")
    else:
         print("  FAIL: yaxis2 missing for Stacked chart.")
         
    # Check Layout Barmode
    if fig_all.layout.barmode == 'stack':
        print("  SUCCESS: Barmode is 'stack'.")
    else:
        print(f"  FAIL: Barmode is {fig_all.layout.barmode}, expected 'stack'.")

if __name__ == "__main__":
    verify_pareto_improvements()
