# Panel Defect Analysis - Engineering Manual

## 📘 Overview
This application provides advanced spatial and statistical analysis of defect data for multi-layer panel manufacturing. It enables traceability, yield estimation, and root-cause diagnostics through interactive dashboards and high-fidelity visualizations.

## 🏗️ Architecture
The system follows a clean, modular architecture:

*   **`src/core`**: Domain logic. Contains `GeometryEngine` and `PanelData` models.
*   **`src/io`**: Data management (Ingestion, Validation, Exporting).
    *   `naming.py`: Handles professional, token-aware filename generation.
*   **`src/analytics`**: Computational modules (Yield, Stress Maps, Root Cause Analysis).
*   **`src/views`**: Streamlit-based presentation layer.
*   **`src/state`**: Centralized state management using `SessionStore`.
*   **`src/plotting`**: High-performance visualization using Plotly.

---

## 🧮 Core Logic

### 1. Yield Calculation
Yield is calculated using a **Geometric Zero-Defect** approach:
*   **Alive Unit**: A cell with zero "True Defects" across all selected layers and sides.
*   **True Defect**: Defined by verification rules (Status NOT in SAFE list: 'False', 'N', 'GE57', etc.).

### 2. Physical Layout & Geometry
The `GeometryEngine` handles multi-quadrant mapping with dynamic gaps and offsets.
*   **Zonal Yield**: Analyzes yield in concentric rings (Edge, Middle, Center) to detect process uniformity issues.
*   **Alignment**: Automatically handles horizontal mirroring for Back-Side inspection data.

### 3. File Naming Convention
Exported reports follow a standardized, intuitive naming convention for maximum traceability:
`[ReportType]_[LotNumber]_[ProcessRequest]_[SourceFile]_[Date].[ext]`

---

## 🧭 System Requirements & Assumptions

1.  **Data Schema**: Input files must contain `DEFECT_TYPE`, `UNIT_INDEX_X`, and `UNIT_INDEX_Y`.
2.  **Naming Pattern**: Input files should typically follow the pattern `BU-{LayerNum}{Side}.xlsx` for automatic metadata extraction.
3.  **Performance**: Large datasets are processed using vectorized Pandas operations and cached Plotly generations to ensure a responsive UI.

## 🛠️ Operation & Exporting

*   **Interactive Analysis**: Real-time filtering by Layer, Side, Quadrant, and Verification status.
*   **Package Export**: Generates a comprehensive ZIP package containing Excel reports, interactive HTML maps, and high-resolution PNGs.
*   **Pick Lists**: Real-time generation of CSV coordinate lists for "Good" units to support downstream sorting.

---
*Professional Engineering Documentation*
