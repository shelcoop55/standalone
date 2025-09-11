# Agent Instructions

This document provides technical instructions for AI agents working on this codebase.

## Project Overview

This is an interactive web application built with Streamlit for visualizing and analyzing semiconductor wafer defect data. The application is designed to be modular, configurable, and maintainable.

- **`app.py`**: The main entry point for the Streamlit application. This file is responsible for the overall UI layout (sidebar, main content), orchestrating calls to the other modules, and handling user interaction.
- **`src/`**: This directory contains the core application logic, separated by concern.
  - **`config.py`**: Handles application configuration. It loads the defect color theme from the JSON file and defines global styling constants.
  - **`data_handler.py`**: Contains all functions for loading, cleaning, and processing data. This includes handling uploaded files, generating sample data, and calculating quadrant/plot coordinates.
  - **`plotting.py`**: Contains all functions that generate Plotly graph objects. Each function is responsible for creating a specific visual component, like the main grid, defect traces, or the mini-map.
  - **`reporting.py`**: Responsible for generating the downloadable, multi-sheet Excel report using `xlsxwriter`.
- **`assets/`**: Contains static assets.
  - **`defect_styles.json`**: **(Primary Configuration File)** Defines the color map for different defect types. This is the main file to edit for style customizations.
  - **`screenshot.png`**: A placeholder for a screenshot of the application for the README.
- **`data/`**: A directory for storing input data files. It is ignored by git except for the `.gitkeep` file.

## Key Architectural Decisions

- **Modularity**: The logic is split into different files in `src/` to separate concerns (UI vs. data vs. plotting). This makes the code easier to read, test, and maintain.
- **External Configuration**: Defect styles are defined in `assets/defect_styles.json` instead of being hardcoded in Python. This allows for easy customization by non-developers and avoids the need to change the source code for simple style edits.
- **Streamlit Caching**: The main data loading function (`load_data` in `data_handler.py`) uses `@st.cache_data`. This is critical for performance, as it prevents the application from reloading and reprocessing the data on every user interaction.
- **Professional Theming**: A significant amount of effort has gone into making the UI look professional. This includes a custom dark theme, custom CSS for buttons and metrics, themed plots, and a well-formatted downloadable report. When adding new features, they should adhere to this established theme.

## How to Run & Develop

1.  **Install dependencies:**
    ```bash
    pip install -r requirements.txt
    ```
2.  **Run the application:**
    ```bash
    streamlit run app.py
    ```
The app will open in your web browser. When no file is uploaded, it automatically uses sample data and displays a welcome message. This is the default state for development and exploration. To test with a real file, use the file uploader in the sidebar. The `sample_defect_data.xlsx` file in the root can be used for testing.
