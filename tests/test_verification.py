"""
Tests for shared verification / true-defect helpers (src.analytics.verification).
"""
import unittest
import pandas as pd
from src.analytics.verification import (
    is_true_defect_value,
    is_true_defect_mask,
    filter_true_defects,
)


class TestIsTrueDefectValue(unittest.TestCase):
    """Tests for is_true_defect_value (single-value check)."""

    def test_safe_values_return_false(self):
        for safe in ("N", "GE57", "TA", "FALSE", "F", "FALSE ALARM", "n", "ge57", "  N  "):
            self.assertFalse(is_true_defect_value(safe))

    def test_true_defect_values_return_true(self):
        for defect in ("T", "Y", "True", "Real Defect", "unknown", ""):
            self.assertTrue(is_true_defect_value(defect))

    def test_nan_treated_as_true_defect(self):
        self.assertTrue(is_true_defect_value(pd.NA))
        self.assertTrue(is_true_defect_value(float("nan")))


class TestIsTrueDefectMask(unittest.TestCase):
    """Tests for is_true_defect_mask (series -> boolean series)."""

    def test_mixed_series(self):
        s = pd.Series(["N", "T", "GE57", "Y", "F"])
        mask = is_true_defect_mask(s)
        self.assertEqual(mask.tolist(), [False, True, False, True, False])

    def test_empty_series(self):
        s = pd.Series([], dtype=object)
        mask = is_true_defect_mask(s)
        self.assertEqual(len(mask), 0)


class TestFilterTrueDefects(unittest.TestCase):
    """Tests for filter_true_defects (dataframe filter)."""

    def test_empty_dataframe_returned_unchanged(self):
        df = pd.DataFrame()
        out = filter_true_defects(df)
        self.assertTrue(out.empty)

    def test_missing_verification_column_returned_unchanged(self):
        df = pd.DataFrame({"A": [1, 2], "B": [3, 4]})
        out = filter_true_defects(df, col="Verification")
        self.assertEqual(len(out), 2)
        self.assertEqual(list(out.columns), ["A", "B"])

    def test_all_safe_returns_empty(self):
        df = pd.DataFrame({"Verification": ["N", "GE57", "F"], "X": [1, 2, 3]})
        out = filter_true_defects(df)
        self.assertEqual(len(out), 0)

    def test_all_true_defects_returns_all_rows(self):
        df = pd.DataFrame({"Verification": ["T", "Y", "Real"], "X": [1, 2, 3]})
        out = filter_true_defects(df)
        self.assertEqual(len(out), 3)
        self.assertEqual(out["X"].tolist(), [1, 2, 3])

    def test_mixed_keeps_only_true_defects(self):
        df = pd.DataFrame({
            "Verification": ["N", "T", "GE57", "Y", "F"],
            "UNIT_INDEX_X": [0, 1, 2, 3, 4],
        })
        out = filter_true_defects(df)
        self.assertEqual(len(out), 2)
        self.assertEqual(out["UNIT_INDEX_X"].tolist(), [1, 3])
        self.assertEqual(out["Verification"].tolist(), ["T", "Y"])


if __name__ == "__main__":
    unittest.main()
