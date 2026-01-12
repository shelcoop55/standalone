"""
Documentation and Defect Definitions Module.

This module contains:
1. The full technical documentation for ICS & Core Defects.
2. A dictionary mapping verification codes to short descriptions for UI tooltips.
"""

# Dictionary for Hover Tooltips (Code -> Short Description)
VERIFICATION_DESCRIPTIONS = {
    # Copper Related Defects (CU)
    "CU10": "Copper Void (Nick)",
    "CU14": "Copper Void on Copper Ground",
    "CU18": "Short on the Surface (AOI)",
    "CU17": "Plating Under Resist (Fine Short)",
    "CU22": "Copper Residue",
    "CU16": "Open on the Surface (AOI)",
    "CU54": "Copper Distribution Not Even / Nodule",
    "CU25": "Rough Trace",
    "CU15": "Fine Short (Burr)",
    "CU94": "Global Copper Thickness Out of Spec – Copper Sting",
    "CU19": "Eless Remaining (Chemical Copper Residue)",
    "CU20": "Circle Defect",
    "CU41": "Copper Coloration or Spots",
    "CU80": "Risk to Via Integrity (Core)",

    # Base Material Defects (BM)
    "BM31": "Base Material Defect (Irregular Shape)",
    "BM01": "Base Material Defect (Crack)",
    "BM10": "Base Material Defect (Round Shape)",
    "BM34": "Measling / Crazing (White Spots)",

    # General Defects (GE)
    "GE01": "Scratch",
    "GE32": "ABF Wrinkle",
    "GE57": "Foreign Material",
    "GE22": "Process Residue",

    # Hole Related Defects (HO)
    "HO31": "Via Not Completely Filled",
    "HO12": "Hole Shift"
}

# Full Documentation Text
TECHNICAL_DOCUMENTATION = """
# 📘 ICS & CORE DEFECTS – TECHNICAL DOCUMENTATION
**Descriptions, Inspection Criteria, Accept/Reject Rules**

---

## 1. COPPER RELATED DEFECTS (CU)

### CU10 – Copper Void (Nick)
**Description:** Localized missing copper on trace or pad, typically appearing as a “nick.”
**Inspection Criteria:**
*   Compare missing copper width to total trace width.
*   For pads, evaluate missing copper area relative to pad size.
*   Confirm no impact to future drill or CAM defined features.

**Reject Conditions:**
*   Missing copper ≥ 50% of trace width.
*   Pad copper loss > 25% or ink exposure visible.
*   Future drill area over etched.
*   For core: trace loss ≥ 50%.

**Accept Conditions:**
*   Missing copper < 50% of trace width.
*   Pad loss < 25% with no ink exposure.
*   Located on dummy copper with no functional impact.

---

### CU14 – Copper Void on Copper Ground
**Description:** Void or missing copper on large copper areas; may resemble ABF under white light.
**Inspection Criteria:**
*   Must be verified under UV light.
*   Cross check CAM data for future hole positions.
*   Evaluate maximum defect length relative to interface.

**Reject Conditions:**
*   Void located in via/pad area.
*   Void at pad center.
*   Void near laser hole area (BU/inner layers).
*   Void > 60 µm in any direction.

**Accept Conditions:**
*   No interference with future holes, discs, or traces.
*   Defect length < 50% of interface width on VRS screen.

---

### CU18 – Short on Surface (AOI)
**Description:** Copper short where copper height matches surrounding copper; no residue visible.
**Inspection Criteria:**
*   Evaluate isolation between traces/pads.
*   Confirm copper height uniformity.
*   Check for FM induced shorting.

**Reject Conditions:**
*   Isolation loss ≥ 50%.
*   Short caused by foreign material.
*   Copper plating covers disk.
*   Traces electrically connected.

**Accept Conditions:**
*   No short present.
*   No isolation loss.

---

### CU17 – Plating Under Resist (Fine Short)
**Description:** Short caused by copper plating beneath dry film.
**Inspection Criteria:**
*   Must be confirmed under UV light.
*   Circuit outline should be visible under UV.

**Reject Conditions:**
*   Short area not on same surface level as trace.
*   Clear evidence of plating under resist.

**Accept Conditions:**
*   No plating under resist.
*   No short detected.

---

### CU22 – Copper Residue
**Description:** Residual copper remaining between traces or on ABF.
**Inspection Criteria:**
*   Evaluate under UV light.
*   Measure residue width relative to spacing.

**Reject Conditions:**
*   Residue ≥ 50% of spacing.
*   Residue with visible FM.
*   Residue bridging or nearly bridging traces.

**Accept Conditions:**
*   Residue < 50% of spacing.
*   No AOS repair required if < 50%.

---

### CU16 – Open on Surface (AOI)
**Description:** Open trace caused by missing copper; ABF color may differ in open area.
**Inspection Criteria:**
*   Confirm under UV light.
*   Evaluate ABF color consistency.
*   Check for alternative conductive paths.

**Reject Conditions:**
*   True opening from ABF bottom.
*   No alternative conductivity.

**Accept Conditions:**
*   No open.
*   Alternative conductive path exists.

---

### CU54 – Copper Nodule / Uneven Distribution
**Description:** Nodules or uneven copper distribution on EP/IP layers.
**Inspection Criteria:**
*   Inspect under white, red, and UV light.
*   Nodule must be visible in at least one lighting mode.
*   Measure nodule size relative to via diameter.

**Reject Conditions:**
*   Nodule > 2 via diameters on big copper.
*   Nodule > 120 µm with FM.
*   Nodule extends to adjacent trace.
*   Copper residue on nodule ≥ 50%.

**Accept Conditions:**
*   Nodule < 2 via diameters.
*   No FM present.
*   < 120 µm and ≤ 3 nodules per land.

---

### CU25 – Rough Trace
**Description:** Copper residue causing rough or uneven trace edges.
**Inspection Criteria:**
*   Measure residue width relative to spacing.

**Reject Conditions:**
*   Residue ≥ 50% of spacing.

**Accept Conditions:**
*   Residue < 50%.

---

### CU15 – Fine Short (Burr)
**Description:** Burr protrusion that may connect or nearly connect traces.
**Inspection Criteria:**
*   Measure burr length relative to spacing.

**Reject Conditions:**
*   Burr ≥ 50% of spacing.
*   Burr connects traces.

**Accept Conditions:**
*   Burr < 50%.

---

### CU94 – Copper Sting
**Description:** Raised copper protrusion (“thorn”) caused by excessive copper thickness.
**Inspection Criteria:**
*   Visual check for copper standing above trace or plane.

**Reject Conditions:**
*   Any copper protrusion above surface level.

**Accept Conditions:**
*   No raised copper.

---

### CU19 – Eless Remaining
**Description:** Chemical copper residue remaining on ABF.
**Inspection Criteria:**
*   Must be confirmed under UV light.

**Reject Conditions:**
*   Any chemical copper residue present.

**Accept Conditions:**
*   No residue.

---

### CU20 – Circle Defect
**Description:** Circular defect on pad surface.
**Inspection Criteria:**
*   Inspect pad area for circular marks.

**Reject Conditions:**
*   Circle defect on pad.

**Accept Conditions:**
*   No defect.

---

### CU41 – Copper Coloration / Spots
**Description:** Discoloration or staining on copper.
**Inspection Criteria:**
*   Check for associated damage (scratch, FM, BM).

**Reject Conditions:**
*   Coloration + scratch.
*   Coloration + FM or BM.

**Accept Conditions:**
*   Small coloration with no additional effects.

---

## 2. BASE MATERIAL DEFECTS (BM)

### BM31 – Irregular Shape in ABF
**Description:** Foreign material embedded in ABF with irregular geometry.
**Reject Conditions:**
*   Any irregular FM shape in ABF.

**Accept Conditions:**
*   No irregular shape.

---

### BM01 – Crack
**Description:** Crack in ABF material.
**Reject Conditions:**
*   Crack on trace or pad.
*   Crack with copper residue.

**Accept Conditions:**
*   Small crack with no copper residue.

---

### BM10 – Round Shape Defect
**Description:** Circular shape caused by lamination Tool Vac.
**Reject Conditions:**
*   Round shape on trace.

**Accept Conditions:**
*   No round shape.

---

### BM34 – Measling / Crazing
**Description:** White circular spots in base material.
**Reject Conditions:**
*   Any white spot on trace or pad.

**Accept Conditions:**
*   None (always reject).

---

## 3. GENERAL DEFECTS (GE)

### GE01 – Scratch
**Inspection Criteria:**
*   Measure scratch length.
*   Evaluate impact on trace geometry.

**Reject Conditions:**
*   BU/Inner: scratch causing open, short, shape change, or lift.
*   EP: scratch > 2 mm.

**Accept Conditions:**
*   Scratch on large copper with no line damage.

---

### GE32 – ABF Wrinkle
**Reject Conditions:**
*   Any ABF wrinkle on pad.

**Accept Conditions:**
*   No wrinkle.

---

### GE57 – Foreign Material
**Reject Conditions:**
*   Transparent white FM.
*   Black FM.
*   White FM.
*   Embedded FM.
*   FM attached to copper or ABF.

**Accept Conditions:**
*   Removable FM not attached to copper.

---

### GE22 – Process Residue
**Reject Conditions:**
*   Residue under trace, pad, or copper.
*   Residue lower than copper.
*   Dry film residue (overflow).
*   Void outline with black stain (DFS rework).

**Accept Conditions:**
*   No residue.

---

## 4. HOLE RELATED DEFECTS (HO)

### HO31 – Via Not Completely Filled
**Inspection Criteria:**
*   Inspect under multiple lighting modes.
*   Look for shadow or black center.

**Reject Conditions:**
*   Shadow in via.
*   Black center.
*   CU10 adjacent to via.
*   Unverifiable → send to lab.

**Accept Conditions:**
*   Black ring but bright center.
*   No abnormality.

---

### HO12 – Hole Shift
**Inspection Criteria:**
*   Measure breakout percentage.
*   Evaluate excess circumference angle.

**Reject Conditions:**
*   Breakout > 33% (1/3D).
*   Excess circumference > 25% (> 90°).

**Accept Conditions:**
*   Breakout ≤ 33%.
*   Excess circumference ≤ 25%.

---

## 5. CORE DEFECTS

### CU80 – Risk to Via Integrity
**Description:** Deep dimples or vacuum plug issues affecting via reliability.
**Reject Conditions:**
*   Uneven copper in holes.
*   48 cards per lot scrapped → block lot.

**Accept Conditions:**
*   Minor scratches/dents without exposed plug ink.
"""
