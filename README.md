# Wafer Defect Analysis Dashboard

This is a professional, interactive web application built with Streamlit for visualizing and analyzing semiconductor wafer defect data. The dashboard is designed for ease of use, with a clean user interface and powerful analysis features.

This application is built from modular Python files located in the `src/` directory, making the code clean, maintainable, and easy to debug.

![App Screenshot](assets/screenshot.png)
*(Please replace `assets/screenshot.png` with an actual screenshot of the application.)*

## Features

- **Interactive Defect Map**: Visualize the spatial distribution of different defect types on a 2x2 panel grid.
- **Contextual Mini-Map**: When zoomed into a single quadrant, a mini-map provides context of your location on the full panel.
- **Pareto Analysis**: Quickly identify the most common defects across the entire panel or within a specific quadrant.
- **Statistical Summary**: View key performance indicators (KPIs) like defect density and estimated yield.
- **Dynamic Configuration**: Interactively configure the dimensions of the wafer map to match your data.
- **Quadrant Filtering**: Isolate and analyze data from one of the four quadrants (Q1-Q4).
- **Professional Theming**: A polished, dark-themed UI designed for a professional look and feel.
- **Customizable Defect Colors**: Easily change the colors for each defect type by editing a simple configuration file.
- **Comprehensive Reporting**: Generate a multi-sheet, presentation-ready Excel report with a single click. The report includes a summary, themed charts, and a full defect list with conditional formatting.

## How to Run This Application

1.  **Clone the repository:**
    ```bash
    git clone <your-repository-url>
    cd <repository-directory>
    ```

2.  **Install the required libraries:**
    ```bash
    pip install -r requirements.txt
    ```

3.  **Run the Streamlit app:**
    ```bash
    streamlit run app.py
    ```
The application will open in your default web browser. You can either use the built-in sample data to explore the features or upload your own data.

## How to Use

1.  **Launch the application.** It will start with sample data.
2.  **Upload Your Data**: In the sidebar's `Data Source` section, click `Browse files` to upload your Excel data file. The file must contain the columns: `DEFECT_TYPE`, `UNIT_INDEX_X`, and `UNIT_INDEX_Y`.
3.  **Configure Panel Size**: In the `Configuration` section, set the `Panel Rows` and `Panel Columns` to match your physical panel's dimensions.
4.  **Analyze**: Use the `Analysis Controls` to switch between `Defect View`, `Pareto View`, and `Summary View`, and to filter by quadrant.
5.  **Download Report**: In the `Reporting` section, click the `Download Full Report` button.

## Configuration

You can easily customize the colors used for each defect type in the plots.

1.  Open the `assets/defect_styles.json` file.
2.  This file contains a simple JSON object mapping defect names to colors.
3.  You can change the hex color codes for existing defects or add new defect types.

**Example `defect_styles.json`:**
```json
{
    "Nick": "#9B59B6",
    "Short": "#E74C3C",
    "Missing Feature": "#2ECC71",
    "Cut": "#1ABC9C"
}
```
