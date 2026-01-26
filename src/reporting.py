"""
Reporting Module (Legacy Wrapper).
This module is kept for backward compatibility and as a facade for the new exporter modules.
"""
from src.io.exporters.excel import generate_excel_report, generate_coordinate_list_report
from src.io.exporters.package import generate_zip_package
