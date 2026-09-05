# NIA DTR Formatter
<a href="https://github.com/Jookie262/nia-dtr-formatter/releases/download/v.3.0/NIA.DTR.Generator.v3.0.zip">
  <img src="https://img.shields.io/badge/Download-v3.0-075e61?style=for-the-badge"/>
</a>

<br>
Python tools for turning raw attendance scan logs into printable Daily Time Record (DTR) PDFs, including the NIA Regional Office VI form.

<p align="center">
  <a href="#about-the-project">About</a> |
  <a href="#getting-started">Getting Started</a> |
  <a href="#usage">Usage</a> |
  <a href="#documentation">Documentation</a> |
  <a href="#contributing">Contributing</a>
</p>

## About The Project

Attendance exports are useful as source data, but they are not always ready to print or submit as a DTR. This project groups raw employee scans by date, assigns them to AM/PM time slots, calculates daily totals, and produces PDF reports.

### Screenshot
<img width="960" height="564" alt="NIA_DTR_Generator_v3 0_xuuSOv84FT" src="https://github.com/user-attachments/assets/e8deb52a-72fe-4428-9537-39b3530daef8" />

### How it works
https://github.com/user-attachments/assets/6a070107-bf62-421b-8d80-7cd0dae4e104

### Features

- Generate NIA Regional Office VI DTR forms for either half of a month.
- Generate simple, one-page-per-employee DTR PDFs.
- Generate raw scan reports without time-slot classification.
- Select a 12-hour or 24-hour display format in the desktop GUI.
- Filter the output to selected employees or exclude selected employees.
- Preview generated NIA PDFs inside the desktop application when Qt PDF support is available.
- Preserve missing or irregular scan days as blank fields or explanatory notes.

### Built With

- [Python](https://www.python.org/)
- [PyQt6](https://pypi.org/project/PyQt6/) for the desktop interface
- [pandas](https://pandas.pydata.org/) for CSV processing
- [ReportLab](https://www.reportlab.com/) for PDF generation

## Getting Started

### Prerequisites

- Python 3.10 or newer is recommended.
- A CSV attendance export containing at least `Timestamp` and `Name` columns.

### Installation

1. Clone or download this repository.
2. Open a terminal in the project directory.
3. Install the dependencies:

   ```bash
   pip install -r requirements.txt
   ```

4. Confirm the project assets are present. The NIA generator uses files in `img/`, and generated PDFs are written to `output/`.

## Input CSV Format

The required columns are:

| Column | Description |
| --- | --- |
| `Timestamp` | Scan date and time in `D/M/YYYY H:MM` format |
| `Name` | Employee name used to group scans |

Additional columns such as `Index`, `ID`, and `Details` are allowed. Example:

```csv
Index,Timestamp,ID,Name,Details
1,13/8/2026 22:09,1001,Juan Dela Cruz,IN
2,13/8/2026 08:10,1001,Juan Dela Cruz,IN
3,13/8/2026 12:15,1001,Juan Dela Cruz,OUT
4,13/8/2026 13:05,1001,Juan Dela Cruz,IN
5,13/8/2026 17:30,1001,Juan Dela Cruz,OUT
```

Names are trimmed before grouping. The parser expects timestamps such as `13/8/2026 22:09`.

## Usage

### Desktop GUI

Run the graphical application:

```bash
python dtr_gui.py
```

The GUI lets you choose an input CSV, set the NIA pay period, choose an output filename, select employees, generate the PDF, preview it, and open the output folder.

### NIA DTR PDF

Generate the first half of August 2026, covering days 1 through 15:

```bash
python generate_nia_dtr.py sample/sample.csv 2026 8 1 nia_august_first_half.pdf
```

Use `2` as the final argument for days 16 through the end of the month. The output filename is optional and defaults to `NIA_DTR_combined.pdf`.

### Simple DTR PDF

```bash
python generate_simple_dtr.py sample/sample.csv simple_dtr.pdf
```

The output filename is optional and defaults to `DTR_combined.pdf`.

### Raw DTR PDF

```bash
python generate_raw_dtr.py sample/sample.csv raw_dtr.pdf
```

The raw report keeps timestamp and employee entries without AM/PM classification. Its default filename is `raw_dtr_format.pdf`.

### Python API

The generator classes can also be used directly from Python:

```python
from generate_nia_dtr import NIADTRProcessor

processor = NIADTRProcessor()
processor.generate(
    "sample/sample.csv",
    year=2026,
    month=8,
    half=1,
    output_filename="nia_august_first_half.pdf",
)
```

Other available processors are `SimpleDTRProcessor` and `RawDTRProcessor`. See [USAGE_GUIDE.md](USAGE_GUIDE.md) for more examples, including direct access to the shared processing methods.

## How Time Slots Are Assigned

For each employee and date, scans are classified as follows:

- **AM In:** earliest scan before noon.
- **AM Out:** latest scan from noon through 12:30 PM.
- **PM In:** earliest scan from 12:31 PM onward.
- **PM Out:** latest scan from 12:31 PM onward.

Days with fewer or more than four scans are retained. Missing values are left blank or represented with a note in the generated report.

## Project Structure

```text
.
|-- dtr_gui.py                # PyQt6 desktop application
|-- generate_dtr.py           # Shared DTRProcessor base class
|-- generate_nia_dtr.py       # NIA-formatted PDF generator
|-- generate_simple_dtr.py    # Simple DTR PDF generator
|-- generate_raw_dtr.py       # Raw scan PDF generator
|-- sample/sample.csv         # Example attendance export
|-- img/                      # NIA form logo assets
|-- font/                     # Bundled font assets
`-- output/                   # Generated PDF files
```

## Documentation

- [USAGE_GUIDE.md](USAGE_GUIDE.md): practical API examples and common tasks.
- [OOP_ARCHITECTURE.md](OOP_ARCHITECTURE.md): processor hierarchy and shared responsibilities.
- [GUI_INTEGRATION_GUIDE.md](GUI_INTEGRATION_GUIDE.md): notes for integrating the processors with the GUI.
- [REFACTORING_SUMMARY.md](REFACTORING_SUMMARY.md): history of the OOP refactoring.

## Roadmap

- Add automated tests for CSV parsing, time-slot assignment, and PDF generation.
- Add configurable timestamp formats for attendance exports.
- Improve validation and error messages for malformed CSV rows.
- Add more DTR templates where their source requirements are available.

## Contributing

Contributions and suggestions are welcome. To propose a change:

1. Create a feature branch.
2. Make a focused change and update the relevant documentation.
3. Test the affected generator or GUI workflow with a sample CSV.
4. Open a pull request describing the change and its expected behavior.

## License

This project currently has no formal open-source license and is intended for internal use. Review and adapt the generated documents according to your organization's policies and records requirements before relying on them for official submissions.

## Author

Created by Jolou.

<p align="right">(<a href="#nia-dtr-formatter">back to top</a>)</p>
