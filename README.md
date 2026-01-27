# Panel Defect Analysis - Engineering Manual

## 📘 Overview
This document serves as the "Technical Bible" for the Panel Defect Analysis application. It details the architectural decisions, mathematical formulas, and system assumptions that drive the software.

## 🏗️ Architecture
The application follows a Domain-Driven Design (DDD) inspired structure:

*   **`src/core`**: The domain heart. Contains the `GeometryEngine` (physical layout logic) and `PanelData` models.
*   **`src/io`**: Data ingress and egress.
    *   `ingestion.py`: Handles Excel parsing and loading.
    *   `validation.py`: Enforces strict schema validation.
    *   `sample_generator.py`: Generates geometrically accurate synthetic data for demonstration.
    *   `naming.py`: Standardizes filename parsing and generation.
*   **`src/analytics`**: Pure business logic. Vectorized calculation of Yield, Stress Maps, and Root Cause matrices.
*   **`src/plotting`**: Visualization layer. Decoupled into `generators` (data prep) and `renderers` (Plotly object creation).
*   **`src/state`**: State management. Encapsulates `st.session_state` mutations in a `SessionStore`.
*   **`src/utils`**: Utility modules, including the centralized `Logger`.

---

## 🧮 The Mathematical Engine

### 1. Coordinate System & Yield Calculation
The application operates on two coordinate systems:
*   **Logical Grid (`UNIT_INDEX_X`, `UNIT_INDEX_Y`)**: Integer indices of the units. Used for aggregation.
*   **Physical Layout (mm)**: Floating point coordinates for visualization.

**Yield Logic:**
A unit is considered "Alive" (Yielding) if and only if:
1.  It exists in the grid (within `rows` x `cols`).
2.  It has **zero** "True Defects" across **all** active layers.

**True Defect Definition:**
A defect is "True" if its `Verification` status is **NOT** in the `SAFE_VERIFICATION_VALUES` list (e.g., 'False Alarm', 'N', 'Safe').

### 2. Stress Map Aggregation
The Stress Map (`src/analytics/stress.py`) computes a 2D histogram of defect density.
*   **Formula**: $H_{x,y} = \sum_{l \in Layers} \mathbb{1}(Defect_{l,x,y} \text{ is True})$
*   **Delta Mode**: $H_{Delta} = H_{GroupA} - H_{GroupB}$.

### 3. Zonal Yield
Yield is calculated per concentric zone (Ring) from the edge:
*   **Edge (Ring 0)**: The outermost perimeter (1 unit thick).
*   **Middle (Ring 1-2)**: The next 2 layers inward.
*   **Center (Ring 3+)**: The remaining core.

---

## 📐 The Geometry Registry

The `GeometryEngine` (`src/core/geometry.py`) is the single source of truth for all layout dimensions. It ensures that both the Sample Data Generator and the Visualization Layer use the exact same logic to position units.

| Constant | Default Value | Description |
| :--- | :--- | :--- |
| `FRAME_WIDTH` | 510 mm | Total physical width of the panel frame. |
| `FRAME_HEIGHT` | 515 mm | Total physical height of the panel frame. |
| `DEFAULT_OFFSET_X` | 13.5 mm | Structural margin from Frame Left to Active Area. |
| `DEFAULT_OFFSET_Y` | 15.0 mm | Structural margin from Frame Top to Active Area. |
| `DEFAULT_GAP` | 3.0 mm | Fixed structural gap between quadrants. |
| `DYNAMIC_GAP` | 5.0 / 3.5 mm | Additional dynamic gap configurable by user. |

**Unit Cell Calculation:**
$$ CellWidth = \frac{QuadrantWidth - (Cols + 1) \times InterUnitGap}{Cols} $$
*(Note: Uses (n+1) gaps to ensure separation from quadrant edges)*

### Sample Data Generation
When no files are uploaded, the application uses `src/io/sample_generator.py` to create synthetic data. This generator:
1.  Respects the **Dynamic Gaps** and **Offsets** defined in the Geometry Engine.
2.  Ensures defect coordinates fall strictly within valid unit boundaries (avoiding gaps).
3.  Simulates realistic defect distributions across layers (Front/Back) and defect types.

---

## 🧭 The "Golden Path" Assumptions

1.  **File Naming**: Input files **MUST** follow the pattern `BU-{LayerNum}{Side}.xlsx` (e.g., `BU-01F.xlsx`).
    *   *Why*: The parser relies on regex to extract Layer Number and Side (Front/Back) automatically.
    *   *Configuration*: This pattern is defined in `src/core/config.py` as `FILENAME_PATTERN`.
2.  **Data Schema**:
    *   Required Columns: `DEFECT_TYPE`, `UNIT_INDEX_X`, `UNIT_INDEX_Y`.
    *   Optional: `Verification` (defaults to 'Under Verification' if missing), `X_COORDINATES` (for precise plotting).
    *   Data Types: Indices must be integers.
3.  **Coordinate Alignment**:
    *   **Front Side**: `Physical X` = `Unit Index X`.
    *   **Back Side**: `Physical X` = `(Total Width - 1) - Unit Index X` (Mirrored horizontally for through-board alignment).
4.  **Immutability**:
    *   Once loaded, `PanelData` is cached and treated as immutable. Changing parameters (e.g., Rows/Cols) triggers a full reload/revalidation cycle.

## 🛠️ Logging & Debugging

The application utilizes a centralized logging system (`src/utils/logger.py`) to track events and errors.
*   **Configuration**: Logs are configured to output to `sys.stdout` (console) by default.
*   **Usage**: Critical data loading steps, validation warnings, and export operations are logged. This replaces ad-hoc `print()` statements for better observability in production environments.

## 🚦 Tab Logic & View Modes

*   **Still Alive**: The primary executive view. Aggregates everything to show net yield. Filters work as "Exclusions" (Remove layers/defects to see what survives).
*   **Multi-Layer**: Visualizes alignment stack-up. Shows raw defects from selected layers/sides.
*   **Root Cause**: Virtual Cross-Sectioning. Slices the panel (X or Y axis) to show defect depth through the stack.
*   **Heatmap / Stress**: Density visualization. Heatmap uses Gaussian smoothing; Stress Map uses exact grid counting.

---

*Generated by Jules (AI Engineering Agent)*
