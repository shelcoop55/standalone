
import pandas as pd

def test_categorical_value_counts():
    print("Testing Categorical Value Counts...")
    
    # Create categorical data
    cats = ['A', 'B', 'C', 'Excluded1', 'Excluded2']
    data = pd.Series(['A', 'A', 'B', 'C'], dtype=pd.CategoricalDtype(categories=cats))
    
    # Filter out 'Excluded1' and 'Excluded2' (conceptually, they are just not in data)
    # But strictly speaking, the data just doesn't have them.
    
    print("\n--- Value Counts (Default) ---")
    vc = data.value_counts()
    print(vc)
    
    print("\n--- Value Counts (index) ---")
    print(vc.index.tolist())
    
    if 'Excluded1' in vc.index:
        print("\nISSUE CONFIRMED: Unused categories appear in value_counts.")
    else:
        print("\nNO ISSUE: Unused categories do NOT appear.")

    # With Observed=False (explicit, though default might be different depending on pandas version)
    # Pandas < 1.something vs > 1.something behavior differs?
    
if __name__ == "__main__":
    test_categorical_value_counts()
