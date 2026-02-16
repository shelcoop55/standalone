
import sys
import os
import pandas as pd
import plotly.graph_objects as go

# Add project root to path
sys.path.append(os.getcwd())

from src.plotting.renderers.charts import create_pareto_figure

def verify_pareto_filter():
    print("Verifying Pareto Zero-Count Filter...")
    
    # Create a DataFrame with a Categorical column
    # Define categories including 'GE57' and 'N' which will NOT be present in valid data
    categories = ['Scratch', 'Dent', 'GE57', 'N']
    
    # Data only contains 'Scratch' and 'Dent'
    df = pd.DataFrame({
        'DEFECT_TYPE': pd.Categorical(['Scratch', 'Dent', 'Scratch'], categories=categories),
        'Verification': pd.Categorical(['Real', 'Real', 'Real'], categories=['Real', 'Safe']),
        'QUADRANT': ['Q1', 'Q2', 'Q3'],
        'HAS_VERIFICATION_DATA': [False, False, False]
    })
    
    # Confirm that GE57 and N are unused but present in categories
    print(f"Categories: {df['DEFECT_TYPE'].cat.categories.tolist()}")
    print(f"Present values: {df['DEFECT_TYPE'].unique().tolist()}")
    
    # Generate Figure
    fig = create_pareto_figure(df)
    
    # Inspect x-axis data in the Bar trace
    bar_trace = next(t for t in fig.data if t.type == 'bar')
    x_values = list(bar_trace.x)
    y_values = list(bar_trace.y)
    
    print(f"\nChart X-Axis: {x_values}")
    print(f"Chart Y-Axis: {y_values}")
    
    if 'GE57' in x_values or 'N' in x_values:
        print("\nFAIL: 'GE57' or 'N' still present in chart X-axis!")
    else:
        print("\nSUCCESS: 'GE57' and 'N' are correctly filtered out.")
        
    if 0 in y_values:
         print("\nFAIL: Zero counts present in Y-axis!")
    else:
         print("\nSUCCESS: No zero counts in Y-axis.")

if __name__ == "__main__":
    verify_pareto_filter()
