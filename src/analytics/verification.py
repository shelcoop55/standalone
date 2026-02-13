"""
Shared helpers for verification / true-defect logic.
Centralizes the definition of "true defect" (Verification not in SAFE_VERIFICATION_VALUES).
"""
import pandas as pd
from src.core.config import SAFE_VERIFICATION_VALUES


def _safe_values_upper():
    return {v.upper() for v in SAFE_VERIFICATION_VALUES}


def is_true_defect_value(value) -> bool:
    """Return True if the verification value represents a true defect (not safe)."""
    if pd.isna(value):
        return True
    return str(value).strip().upper() not in _safe_values_upper()


def is_true_defect_mask(series: pd.Series) -> pd.Series:
    """Boolean mask: True where the value is a true defect (not in SAFE_VERIFICATION_VALUES)."""
    safe_upper = _safe_values_upper()
    return ~series.astype(str).str.upper().str.strip().isin(safe_upper)


def filter_true_defects(df: pd.DataFrame, col: str = "Verification") -> pd.DataFrame:
    """Return subset of df where col is not in SAFE_VERIFICATION_VALUES (true defects only)."""
    if df.empty or col not in df.columns:
        return df
    return df[is_true_defect_mask(df[col])].copy()
