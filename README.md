# Panel Defect Analysis Dashboard

This is a professional, interactive web application built with Streamlit for visualizing and analyzing semiconductor panel defect data. The dashboard is designed for engineers and technicians to easily upload multi-layer build-up data, identify trends, and generate insightful reports.

The application is architected for robustness and flexibility, featuring a modular Python backend located in the `src/` directory, which makes the code clean, maintainable, and easy to extend.

![App Screenshot](assets/screenshot.png)
*(Please replace `assets/screenshot.png` with an actual screenshot of the application.)*

## Key Features

- **Multi-Layer Defect Analysis**: Upload and analyze data from multiple build-up (BU) layers simultaneously (e.g., `BU-01.xlsx`, `BU-02.xlsx`).
- **Interactive Defect Map**: Visualize the spatial distribution of defects on a true-to-scale 2x2 panel grid.
- **"Still Alive" Yield Map**: A powerful view that aggregates "True" defects across all layers to show a final yield map of which panel units are still defect-free.
- **Dynamic Defect Coloring**: New, unknown defect types from an uploaded file are automatically assigned a unique color and plotted, requiring no manual configuration.
- **Pareto Analysis**: Instantly identify the most frequent defect types, with views for individual quadrants or a stacked bar chart for the entire panel.
- **Statistical Summary**: View key performance indicators (KPIs) like defect density, true defective cell counts, and estimated yield, with breakdowns per quadrant.
- **Flexible Configuration**: Interactively configure the panel's row and column dimensions to match the physical layout of your product.
- **Data Filtering**: Isolate and analyze data by quadrant (Q1-Q4) or by verification status (True, False, Acceptable).
- **Professional Theming**: A polished, dark-themed UI designed for a professional manufacturing environment.
- **Comprehensive Reporting**: Generate a multi-sheet, presentation-ready Excel report with a single click. The report includes a summary, themed charts, top defect lists, and a full raw data dump with conditional formatting for critical defects.

## How to Use the Dashboard

1.  **Launch the application.** It will start with sample data for three layers.
2.  **Upload Your Data**:
    - In the sidebar, under the "Data Source & Configuration" expander, click **Browse files**.
    - Select one or more Excel files. The application expects filenames to start with `BU-XX` (e.g., `BU-01-MyData.xlsx`), where `XX` is the layer number.
    - The Excel file must contain a sheet named `Defects` with the columns: `DEFECT_TYPE`, `UNIT_INDEX_X`, and `UNIT_INDEX_Y`.
3.  **Configure Panel Size**: Set the `Panel Rows` and `Panel Columns` to match the dimensions of a single quadrant on your physical panel.
4.  **Run Analysis**: Click the **"Run Analysis"** button to process the data.
5.  **Navigate Views**:
    - Use the buttons at the top of the main view to switch between different build-up layers or the "Still Alive" map.
    - Use the "Analysis Controls" in the sidebar to switch between the `Defect Map`, `Pareto`, and `Summary` views for the selected layer.
6.  **Download Reports**:
    - In the layer views, you can generate and download a comprehensive Excel report for the currently selected filters.
    - In the "Still Alive" view, you can download a simple coordinate list of all defective cells.

## Developer Setup and Installation

Follow these instructions to set up the development environment and run the application locally.

1.  **Clone the repository:**
    ```bash
    git clone <your-repository-url>
    cd <repository-directory>
    ```
2.  **Install Python Version**: This project uses `pyenv` to manage Python versions. Ensure you have the version specified in the `.python-version` file installed.
    ```bash
    # This will automatically read the version from the .python-version file
    pyenv install
    ```
3.  **Install Dependencies**: The project uses two requirements files. `requirements.txt` for the core application and `requirements-dev.txt` for testing and development.
    ```bash
    # Install application dependencies
    pip install -r requirements.txt

    # Install development dependencies
    pip install -r requirements-dev.txt
    ```

4.  **Run the Streamlit App**:
    ```bash
    streamlit run app.py
    ```
The application will open in your default web browser.

## Configuration

### Defect Colors
You can customize the colors used for each defect type in the plots.

1.  Open the `assets/defect_styles.json` file.
2.  This file contains a simple JSON object mapping defect names (strings) to hex color codes (strings).
3.  You can change the hex color codes for existing defects or add new defect types to give them a specific color.

**Example `defect_styles.json`:**
```json
{
    "Nick": "#9B59B6",
    "Short": "#E74C3C",
    "Missing Feature": "#2ECC71",
    "Cut": "#1ABC9C"
}
```
**Note**: If a defect type is found in an uploaded file but is *not* in this JSON file, it will be automatically assigned a color from a fallback palette defined in `src/config.py`.

## Testing

This project uses `pytest` for automated testing. To ensure code quality and prevent regressions, run the test suite after making any changes.

```bash
pytest
```
The tests will run and provide a report on the status of the application's core logic.