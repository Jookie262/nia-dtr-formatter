# OOP Architecture - NIA DTR Formatter Project

## Overview

This project has been refactored to use Object-Oriented Programming (OOP) principles, with a base class `DTRProcessor` that handles all shared time calculation logic, and two concrete implementations for different DTR formats.

## Class Structure

### 1. **DTRProcessor** (Base Class) - `generate_dtr.py`

Abstract base class that provides all the common functionality for DTR processing.

**Key Methods:**

- `load_and_group(csv_path)` - Loads CSV and groups scans by person and date
- `classify_scan(t)` - Classifies a scan datetime into time slots (AM In/Out, PM In/Out)
- `format_time(t)` - Formats datetime into readable time string (e.g., "8:30 AM")
- `compute_slots_for_date(scans)` - Computes AM/PM slots for a single date
- `calculate_total_hours(am_in, am_out, pm_in, pm_out)` - Calculates working hours
- `compute_row(date, scans)` - Complete row computation with all details
- `safe_filename(name)` - Makes person names filesystem-safe
- `generate()` - Abstract method to be implemented by subclasses

**Time Slot Logic:**

- **AM In**: 12:00 AM - 11:59 AM
- **AM Out**: 12:00 PM - 12:29 PM
- **PM In**: 12:30 PM - 1:00 PM
- **PM Out**: 1:01 PM - 11:59 PM

**Duplicate Scan Handling:**

- If 5+ scans on a day: Keep the LATEST scan in each slot
- If fewer than 5 scans: Keep EARLIEST for "In" slots, LATEST for "Out" slots

---

### 2. **SimpleDTRProcessor** (Concrete Class) - `generate_simple_dtr.py`

Inherits from `DTRProcessor` and implements simple DTR PDF generation.

**Methods:**

- `build_person_story(name, rows, styles)` - Builds flowable content for one person's page
- `build_combined_pdf(grouped, output_path)` - Builds single PDF with all personnel
- `generate(csv_path, output_filename)` - Main method to generate the PDF

**Output Format:**

- One PDF file with one page per person (alphabetical order)
- Table showing: Date, AM In, AM Out, PM In, PM Out
- Notes section for any missing scans
- Professional header and formatting

**Usage:**

```bash
python generate_simple_dtr.py <input_csv> [output_filename.pdf]
```

---

### 3. **NIADTRProcessor** (Concrete Class) - `generate_nia_dtr.py`

Inherits from `DTRProcessor` and implements NIA-format DTR PDF generation.

**Methods:**

- `get_period_dates(year, month, half)` - Gets dates for a half-month period
- `period_label(period_dates)` - Formats period as a label
- `build_person_story(...)` - Builds NIA-format page for one person
- `build_combined_pdf(...)` - Builds NIA-format PDF
- `generate(csv_path, year, month, half, output_filename)` - Main generation method
- `_load_logo(path, size)` - Static helper to load and format logos

**Output Format:**

- One PDF page per person per period
- Professional NIA Regional Office No. VI header with logos
- Calendar-based layout showing every day in the period (including weekends)
- AM/PM In/Out columns with blank Tardiness/Undertime fields for manual entry
- Official NIA certification statement and signature block

**Usage:**

```bash
python generate_nia_dtr.py <input_csv> <year> <month> <half> [output_filename.pdf]
# half: 1 for days 1-15, 2 for days 16-end of month
```

---

## Design Benefits

1. **Code Reusability**: All time calculation logic is in the base class
2. **Consistency**: Both formats use identical scan classification rules
3. **Maintainability**: Changes to time logic only need to be made once
4. **Extensibility**: Easy to add new DTR formats by creating new subclasses
5. **Separation of Concerns**: Format-specific logic is separate from core processing

---

## File Structure After Refactoring

```
project/
├── generate_dtr.py          ← Base class with shared logic
├── generate_simple_dtr.py   ← SimpleDTRProcessor implementation
├── generate_nia_dtr.py      ← NIADTRProcessor implementation
├── dtr_gui.py               ← GUI (unchanged, can be updated to use classes)
├── sample/
│   └── sample.csv
├── output/                  ← Generated PDFs
└── img/                     ← Logo files for NIA format
    ├── nia_logo.png
    ├── office_president.png
    └── bagong_pilipinas.png
```

---

## Migration from Old to New API

### Old Code (Procedural):

```python
from generate_simple_dtr import load_and_group, compute_row, build_combined_pdf

grouped = load_and_group("input.csv")
output_path = "output/dtr.pdf"
build_combined_pdf(grouped, output_path)
```

### New Code (OOP):

```python
from generate_simple_dtr import SimpleDTRProcessor

processor = SimpleDTRProcessor()
processor.generate("input.csv", "output/dtr.pdf")
```

---

## Backwards Compatibility

The old procedural functions are still available as wrappers for backwards compatibility:

- `compute_row()` in `generate_simple_dtr.py` still works (calls `DTRProcessor.compute_row()`)

This allows gradual migration of existing code like `dtr_gui.py`.

---

## Future Enhancements

Possible extensions:

1. Create a `CustomDTRProcessor` for department-specific formats
2. Add configuration options for time slot boundaries
3. Implement batch processing for multiple months
4. Add data validation and error reporting
5. Create an `ExcelDTRProcessor` for Excel output format
6. Implement logging and performance metrics
