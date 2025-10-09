"""
Enum Definitions Module.

This module contains Enumeration classes for defining constant sets of values,
such as UI view modes or quadrant identifiers. Using enums instead of raw strings
improves code readability and reduces the risk of typos.
"""
from enum import Enum

class ViewMode(Enum):
    """Enumeration for the different analysis views in the UI."""
    DEFECT = "Defect View"
    PARETO = "Pareto View"
    SUMMARY = "Summary View"

    @classmethod
    def values(cls) -> list[str]:
        """Returns the string values of all enum members."""
        return [item.value for item in cls]

class Quadrant(Enum):
    """Enumeration for the panel quadrants."""
    ALL = "All"
    Q1 = "Q1"
    Q2 = "Q2"
    Q3 = "Q3"
    Q4 = "Q4"

    @classmethod
    def values(cls) -> list[str]:
        """Returns the string values of all enum members."""
        return [item.value for item in cls]
