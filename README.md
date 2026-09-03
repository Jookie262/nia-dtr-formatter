# NIA DTR Formatter

A Python-based attendance-to-DTR generator for creating Daily Time Record (DTR) PDFs from raw employee scan logs. The project uses Object-Oriented Programming (OOP) to provide both a simple DTR format and the NIA Regional Office VI DTR form, with a desktop GUI for easier use.

## Overview

This project reads a CSV attendance log, groups scans by employee and date, classifies each scan into AM/PM in/out buckets, and generates printable PDF DTR reports. It is designed to work with attendance logs that contain raw scan entries and can handle irregular scan counts, including days with fewer or more than four scans.

The tool can generate:

- Simple DTR PDFs: one page per employee with a date-by-date AM/PM entry table.
- NIA DTR PDFs: one NIA-formatted page per employee for a selected half-month period.
- Raw DTR PDFs: one page per employee showing raw timestamp and name entries without AM/PM classification.
- GUI desktop app: a Tkinter interface for selecting CSV files and generating output without using the CLI.

## Architecture

The project is built using Object-Oriented Programming with a base class and concrete implementations:

- **`DTRProcessor`** (base class in `generate_dtr.py`) – provides shared time calculation logic and core functionality
- **`SimpleDTRProcessor`** (in `generate_simple_dtr.py`) – implements simple DTR PDF generation
- **`NIADTRProcessor`** (in `generate_nia_dtr.py`) – implements NIA-formatted DTR generation
- **`RawDTRProcessor`** (in `generate_raw_dtr.py`) – implements raw DTR PDF generation with minimal formatting

This design eliminates code duplication and makes the codebase more maintainable and extensible.

## Project Files

- `generate_dtr.py` – base `DTRProcessor` class with shared time calculation logic.
- `generate_simple_dtr.py` – `SimpleDTRProcessor` for simple DTR PDF generation.
- `generate_nia_dtr.py` – `NIADTRProcessor` for NIA-formatted DTR generation.
- `generate_raw_dtr.py` – `RawDTRProcessor` for raw DTR PDF generation (timestamps and names only).
- `dtr_gui.py` – desktop GUI that wraps both generators.
- `sample/sample.csv` – example input CSV.
- `output/` – generated PDF output folder.
- `img/` – logo assets used by the NIA form.

### Documentation

- `OOP_ARCHITECTURE.md` – detailed explanation of the class hierarchy, methods, and design.
- `USAGE_GUIDE.md` – practical examples and code samples for using the classes.
- `REFACTORING_SUMMARY.md` – summary of changes and improvements made.
- `GUI_INTEGRATION_GUIDE.md` – guide for updating the GUI to use the new OOP classes.

## Requirements

Install the required Python packages:

```bash
pip install -r requirements.txt
```

Dependencies include:

- pandas
- reportlab

## Input CSV Format

The script expects a CSV with at least these fields:

- `Timestamp`
- `Name`

The application also accepts the full sample format used in this project:

```csv
Index,Timestamp,ID,Name,Details
1,13/8/2026 22:09,1001,Juan Dela Cruz,IN
2,13/8/2026 08:10,1001,Juan Dela Cruz,IN
3,13/8/2026 12:15,1001,Juan Dela Cruz,OUT
4,13/8/2026 13:05,1001,Juan Dela Cruz,IN
5,13/8/2026 17:30,1001,Juan Dela Cruz,OUT
```

The parser expects timestamps in this format:

```text
D/M/YYYY H:MM
```

Example:

```text
13/8/2026 22:09
```

## How It Works

### Core Architecture

The project uses a base class `DTRProcessor` that encapsulates all time calculation logic, with two concrete implementations for different DTR formats:

**Base Class Methods:**

- `load_and_group(csv_path)` – loads CSV and groups scans by person and date
- `classify_scan(t)` – classifies a scan datetime into time slots (AM In/Out, PM In/Out)
- `format_time(t)` – formats datetime into readable time string
- `compute_slots_for_date(scans)` – computes AM/PM slots for a single date
- `calculate_total_hours()` – calculates total working hours
- `compute_row(date, scans)` – complete row computation with all details
- `generate()` – abstract method implemented by subclasses for PDF generation

**Time Slot Classification:**

All scan times are classified into these categories:

- **AM In**: 12:00 AM - 11:59 AM
- **AM Out**: 12:00 PM - 12:30 PM
- **PM In/Out pool**: 12:31 PM - 11:59 PM; the earliest scan is PM In and the latest scan is PM Out

**Scan Selection:**

- AM In uses the earliest scan before noon, and AM Out uses the latest scan from noon through 12:30 PM
- PM In/Out uses all scans from 12:31 PM onward: the earliest is PM In and the latest is PM Out

### 1. SimpleDTRProcessor

The `SimpleDTRProcessor` class generates a simple DTR format:

- Loads CSV data using inherited methods
- Processes each employee's scans
- Generates one PDF page per employee (alphabetical order)
- Includes date table with AM/PM in/out columns
- Shows missing-scan notes where applicable

### 2. NIADTRProcessor

The `NIADTRProcessor` class generates a formal NIA Regional Office VI DTR form:

- Supports two half-month periods: days 1-15 and days 16-end of month
- Includes NIA/agency header with logos
- Shows employee information and date generated
- Contains office hours section
- Includes blank tardiness/undertime fields for manual input
- Provides certification and signature areas

### 3. RawDTRProcessor

The `RawDTRProcessor` class generates a raw DTR format:

- Minimal formatting with just timestamps and names
- One PDF page per employee (alphabetical order)
- Displays raw scan entries without AM/PM slot classification
- Useful for quick capture and reporting without complex formatting requirements

## Usage

### Using the Classes (Recommended)

#### Simple DTR Generator

```python
from generate_simple_dtr import SimpleDTRProcessor

processor = SimpleDTRProcessor()
processor.generate('sample/sample.csv', 'output/simple_dtr.pdf')
```

#### NIA DTR Generator

```python
from generate_nia_dtr import NIADTRProcessor

processor = NIADTRProcessor()
# Generate for 1st half of August 2026
processor.generate('sample/sample.csv', 2026, 8, 1, 'output/nia_dtr.pdf')
```

#### Raw DTR Generator

```python
from generate_raw_dtr import RawDTRProcessor

processor = RawDTRProcessor()
processor.generate('sample/sample.csv', 'output/raw_dtr.pdf')
```

### Command Line Interface

#### Run the simple DTR generator

```bash
python generate_simple_dtr.py sample/sample.csv output/simple_dtr.pdf
```

If no output filename is set, it defaults to `DTR_combined.pdf`.

#### Run the NIA DTR generator

```bash
python generate_nia_dtr.py sample/sample.csv 2026 8 1 output/nia_dtr.pdf
```

Arguments:

- `input_csv` – path to the attendance CSV
- `year` – year to generate for
- `month` – month number (1-12)
- `half` – `1` for days 1-15 or `2` for days 16-end of month
- `output_filename.pdf` – optional, defaults to `NIA_DTR_combined.pdf`

#### Run the raw DTR generator

```bash
python generate_raw_dtr.py sample/sample.csv output/raw_dtr.pdf
```

If no output filename is set, it defaults to `DTR_raw_combined.pdf`.

### Desktop GUI

```bash
python dtr_gui.py
```

Running `dtr_gui.py` opens a Tkinter window with two tabs:

- **Simple DTR** – generates simple DTR PDFs
- **NIA DTR** – generates NIA-formatted DTR PDFs

The GUI lets you:

- Choose a CSV file
- Name the output PDF
- Generate a DTR file
- Open the output folder

## Output Behavior

Generated PDFs are saved in the `output/` folder next to the project files.

The app creates this folder automatically if it does not exist.

## Example Run

```bash
python generate_dtr.py sample/sample.csv
```

This will create a PDF in the `output/` folder using the default file name.

## Notes

- The scripts assume the CSV is already a raw attendance log, not a pre-summarized timesheet.
- Missing scan values are shown as blank cells or notes in the generated DTR.
- Name values are used to group employees; extra whitespace is stripped automatically.
- Logo files for the NIA form are expected inside the `img/` folder.

## License

This project is intended for internal use in generating DTR documents from attendance logs. Use it in accordance with your organization’s policies and document requirements.

## Version History

**Version 2.0** (August 31, 2026)

- Refactored to Object-Oriented Programming (OOP)
- Introduced base class `DTRProcessor` for shared functionality
- Created `SimpleDTRProcessor` and `NIADTRProcessor` concrete classes
- Eliminated ~160 lines of duplicate code
- Added comprehensive architecture and usage documentation
- Improved code maintainability and extensibility

**Version 1.0** (August 20, 2026)

- Initial release with procedural approach

## Additional Documentation

For more detailed information, see:

- **[OOP_ARCHITECTURE.md](OOP_ARCHITECTURE.md)** – Complete class hierarchy and method documentation
- **[USAGE_GUIDE.md](USAGE_GUIDE.md)** – Practical code examples and usage patterns
- **[REFACTORING_SUMMARY.md](REFACTORING_SUMMARY.md)** – Summary of refactoring changes and improvements
- **[GUI_INTEGRATION_GUIDE.md](GUI_INTEGRATION_GUIDE.md)** – Guide for updating GUI to use new classes

## Author

Created by Jolou
