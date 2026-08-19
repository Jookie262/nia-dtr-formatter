# NIA DTR Formatter

A Python-based attendance-to-DTR generator for creating Daily Time Record (DTR) PDFs from raw employee scan logs. The project supports both a simple DTR format and the NIA Regional Office VI DTR form, and it includes a desktop GUI for easier use.

## Overview

This project reads a CSV attendance log, groups scans by employee and date, classifies each scan into AM/PM in/out buckets, and generates printable PDF DTR reports. It is designed to work with attendance logs that contain raw scan entries and can handle irregular scan counts, including days with fewer or more than four scans.

The tool can generate:

- Simple DTR PDFs: one page per employee with a date-by-date AM/PM entry table.
- NIA DTR PDFs: one NIA-formatted page per employee for a selected half-month period.
- GUI desktop app: a Tkinter interface for selecting CSV files and generating output without using the CLI.

## Project Files

- `generate_dtr.py` – core logic for simple DTR generation.
- `generate_nia_dtr.py` – NIA-formatted DTR generation for a half-month period.
- `dtr_gui.py` – desktop GUI that wraps both generators.
- `sample/sample.csv` – example input CSV.
- `output/` – generated PDF output folder.
- `img/` – logo assets used by the NIA form.

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

### 1. Simple DTR generation

The script in `generate_dtr.py`:

- loads the CSV,
- strips and normalizes column names,
- groups entries by employee name and date,
- sorts timestamps per date,
- classifies each scan into time slots:
  - AM In: 12:00 AM to 11:59 AM
  - AM Out: 12:00 PM to 12:29 PM
  - PM In: 12:30 PM to 1:00 PM
  - PM Out: 1:01 PM to 11:59 PM
- chooses the correct scan for each slot depending on the number of scans in the day.

If a day has 5 or more scans, the latest scan in each slot is used. Otherwise, the script keeps the earliest scan for the "In" slots and the latest scan for the "Out" slots.

The generated PDF contains:

- a title/header,
- a table with Date, AM In, AM Out, PM In, and PM Out,
- missing-scan notes where applicable,
- one page per employee.

### 2. NIA DTR generation

The script in `generate_nia_dtr.py` creates a formal NIA Regional Office VI DTR page for a selected period:

- 1st half of the month: days 1 to 15
- 2nd half of the month: days 16 to end of month

It writes one PDF page per employee and includes:

- NIA/agency header with logos,
- employee name,
- date generated,
- office hours section,
- daily table rows for all dates in the selected period,
- blank tardiness/undertime fields for manual input,
- certification and signature areas.

### 3. Desktop app

Running `dtr_gui.py` opens a Tkinter window with two tabs:

- Simple DTR
- NIA DTR

The GUI lets you:

- choose a CSV file,
- name the output PDF,
- generate a DTR file,
- open the output folder.

## Usage

### Run the simple DTR generator from the command line

```bash
python generate_dtr.py sample/sample.csv output/simple_dtr.pdf
```

If no output filename is set, it defaults to:

```text
DTR_combined.pdf
```

### Run the NIA DTR generator from the command line

```bash
python generate_nia_dtr.py sample/sample.csv 2026 8 1 output/nia_dtr.pdf
```

Arguments:

- `input_csv` – path to the attendance CSV
- `year` – year to generate for
- `month` – month number (1-12)
- `half` – `1` for days 1-15 or `2` for days 16-end of month
- `output_filename.pdf` – optional, defaults to `NIA_DTR_combined.pdf`

### Run the GUI

```bash
python dtr_gui.py
```

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

## Author

Created by Jolou

Version: 1.0

Date: August 20, 2026
