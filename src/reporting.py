"""
Excel Reporting Module.

This module provides functions for generating professional, multi-sheet Excel
reports from the defect analysis data. It uses xlsxwriter to format the report
with headers, themed charts, and conditional formatting for enhanced readability
and analytical value.
"""
import pandas as pd
import io
from datetime import datetime
from src.config import PANEL_COLOR

def generate_excel_report(
    full_df: pd.DataFrame,
    panel_rows: int,
    panel_cols: int,
    source_filename: str = "Sample Data"
) -> bytes:
    """
    Generates a comprehensive, multi-sheet Excel report.

    The report includes:
    - A summary sheet with KPI metrics and a themed bar chart.
    - A professional header with the report title, source file, and timestamp.
    - Separate sheets for the top defects in each quadrant.
    - A full list of all defects with conditional formatting to highlight critical issues.

    Args:
        full_df (pd.DataFrame): The complete, unfiltered dataframe of defect data.
        panel_rows (int): The number of rows in a single panel.
        panel_cols (int): The number of columns in a single panel.
        source_filename (str): The name of the source data file for the report header.

    Returns:
        bytes: The generated Excel file as an in-memory bytes object.
    """
    output_buffer = io.BytesIO()

    with pd.ExcelWriter(output_buffer, engine='xlsxwriter') as writer:
        workbook = writer.book
        
        # --- Define Professional Formats ---
        title_format = workbook.add_format({'bold': True, 'font_size': 18, 'font_color': PANEL_COLOR, 'valign': 'vcenter'})
        subtitle_format = workbook.add_format({'bold': True, 'font_size': 12, 'valign': 'vcenter'})
        header_format = workbook.add_format({
            'bold': True, 'text_wrap': True, 'valign': 'top', 
            'fg_color': '#DDEBF7', 'border': 1, 'align': 'center'
        })
        cell_format = workbook.add_format({'border': 1})
        percent_format = workbook.add_format({'num_format': '0.00%', 'border': 1})
        density_format = workbook.add_format({'num_format': '0.00', 'border': 1})
        critical_defect_format = workbook.add_format({'bg_color': '#FFC7CE', 'font_color': '#9C0006'})

        # --- Sheet 1: Quarterly Summary ---
        worksheet = workbook.add_worksheet('Quarterly Summary')

        # --- Header ---
        worksheet.set_row(0, 30)
        worksheet.merge_range('A1:D1', 'Panel Defect Analysis Report', title_format)
        worksheet.write('A2', 'Source File:', subtitle_format)
        worksheet.write('B2', source_filename)
        worksheet.write('A3', 'Report Date:', subtitle_format)
        worksheet.write('B3', datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

        kpi_data = []
        quadrants = ['Q1', 'Q2', 'Q3', 'Q4']
        
        for quad in quadrants:
            quad_df = full_df[full_df['QUADRANT'] == quad]
            total_defects = len(quad_df)
            density = total_defects / (panel_rows * panel_cols) if (panel_rows * panel_cols) > 0 else 0
            kpi_data.append({"Quadrant": quad, "Total Defects": total_defects, "Defect Density": density})
        
        total_defects_all = len(full_df)
        density_all = total_defects_all / (4 * panel_rows * panel_cols) if (panel_rows * panel_cols) > 0 else 0
        kpi_data.append({"Quadrant": "Total", "Total Defects": total_defects_all, "Defect Density": density_all})
        
        summary_df = pd.DataFrame(kpi_data)
        
        # --- Write Data Table ---
        start_row = 5
        summary_df.to_excel(writer, sheet_name='Quarterly Summary', startrow=start_row, header=False, index=False)
        
        for col_num, value in enumerate(summary_df.columns.values):
            worksheet.write(start_row - 1, col_num, value, header_format)
            
        for row_num in range(len(summary_df)):
            worksheet.write(row_num + start_row, 0, summary_df.iloc[row_num, 0], cell_format)
            worksheet.write(row_num + start_row, 1, summary_df.iloc[row_num, 1], cell_format)
            worksheet.write(row_num + start_row, 2, summary_df.iloc[row_num, 2], density_format)

        worksheet.autofit()
        
        # --- Themed Chart ---
        chart = workbook.add_chart({'type': 'column'})
        chart.add_series({
            'name':       'Total Defects by Quadrant',
            'categories': ['Quarterly Summary', start_row, 0, start_row + len(quadrants) - 1, 0],
            'values':     ['Quarterly Summary', start_row, 1, start_row + len(quadrants) - 1, 1],
            'fill':       {'color': PANEL_COLOR},
            'border':     {'color': '#000000'},
            'data_labels': {'value': True}
        })
        chart.set_title({'name': 'Defect Count Comparison by Quadrant'})
        chart.set_legend({'position': 'none'})
        chart.set_y_axis({'name': 'Count'})
        chart.set_style(10) # A built-in style that looks clean
        worksheet.insert_chart('E2', chart, {'x_scale': 1.5, 'y_scale': 1.5})

        # --- Create a separate sheet for each quadrant's top offenders ---
        for quad in quadrants:
            quad_df = full_df[full_df['QUADRANT'] == quad]
            if not quad_df.empty:
                sheet_name = f'{quad} Top Defects'
                
                top_offenders = quad_df['DEFECT_TYPE'].value_counts().reset_index()
                top_offenders.columns = ['Defect Type', 'Count']
                top_offenders['Percentage'] = (top_offenders['Count'] / len(quad_df))
                
                # 1. Write the dataframe to the new sheet first
                top_offenders.to_excel(writer, sheet_name=sheet_name, startrow=1, header=False, index=False)
                
                # 2. Get the worksheet object that pandas just created
                worksheet = writer.sheets[sheet_name]

                # 3. Now, format the sheet
                for col_num, value in enumerate(top_offenders.columns.values):
                    worksheet.write(0, col_num, value, header_format)
                worksheet.set_column('C:C', 12, percent_format)
                worksheet.autofit()

        # --- Final Sheet: Full Defect List (with Conditional Formatting) ---
        report_columns = ['UNIT_INDEX_X', 'UNIT_INDEX_Y', 'DEFECT_TYPE', 'QUADRANT', 'SOURCE_FILE']
        final_df = full_df[[col for col in report_columns if col in full_df.columns]]

        # Use a new worksheet for the full list
        full_list_worksheet = workbook.add_worksheet('Full Defect List')
        final_df.to_excel(writer, sheet_name='Full Defect List', startrow=1, header=False, index=False)

        for col_num, value in enumerate(final_df.columns.values):
            full_list_worksheet.write(0, col_num, value, header_format)

        # Apply conditional formatting to the correct worksheet
        full_list_worksheet.conditional_format('A2:E{}'.format(len(final_df) + 1), {
            'type': 'formula',
            'criteria': '=OR($C2="Short", $C2="Cut/Short")',
            'format': critical_defect_format
        })

        full_list_worksheet.autofit()

    excel_bytes = output_buffer.getvalue()
    return excel_bytes

