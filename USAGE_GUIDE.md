# Quick Reference - Using the OOP Classes

## Basic Usage Examples

### Example 1: Generate Simple DTR PDF

```python
from generate_simple_dtr import SimpleDTRProcessor

# Create processor instance
processor = SimpleDTRProcessor()

# Generate PDF from CSV
processor.generate("sample/sample.csv", "my_dtr.pdf")
```

---

### Example 2: Generate NIA Format DTR PDF

```python
from generate_nia_dtr import NIADTRProcessor

# Create processor instance
processor = NIADTRProcessor()

# Generate PDF for July 2026, first half (days 1-15)
processor.generate("sample/sample.csv", year=2026, month=7, half=1,
                   output_filename="NIA_July_First_Half.pdf")
```

---

### Example 3: Using Base Class Methods Directly

```python
from generate_dtr import DTRProcessor

# Load and group scans from CSV
grouped = DTRProcessor.load_and_group("sample/sample.csv")

# Process data for a specific person
person_name = list(grouped.keys())[0]
person_scans = grouped[person_name]

# Calculate hours for each date
for date, scans in person_scans.items():
    row_data = DTRProcessor.compute_row(date, scans)
    print(f"{row_data['date']}: {row_data['total']} hours")
    if row_data['note']:
        print(f"  Note: {row_data['note']}")
```

---

### Example 4: Custom Processing

```python
from generate_dtr import DTRProcessor

# Classify individual scans
from datetime import datetime

# Create a datetime object
scan_time = datetime(2026, 7, 15, 8, 30)  # 8:30 AM

# Classify it
slot = DTRProcessor.classify_scan(scan_time)
print(f"8:30 AM is classified as: {slot}")  # Output: "am_in"

# Format the time
formatted = DTRProcessor.format_time(scan_time)
print(formatted)  # Output: "8:30 AM"
```

---

## Updating dtr_gui.py to Use OOP

If your GUI code currently uses the old procedural functions, here's how to update it:

### Before (Procedural):

```python
import generate_simple_dtr
import generate_nia_dtr

# For Simple DTR
grouped = generate_simple_dtr.load_and_group(csv_file)
generate_simple_dtr.build_combined_pdf(grouped, output_file)

# For NIA DTR
grouped = generate_simple_dtr.load_and_group(csv_file)
period_dates = generate_nia_dtr.get_period_dates(year, month, half)
generate_nia_dtr.build_combined_pdf(grouped, period_dates, output_file)
```

### After (OOP):

```python
from generate_simple_dtr import SimpleDTRProcessor
from generate_nia_dtr import NIADTRProcessor

# For Simple DTR
simple_processor = SimpleDTRProcessor()
simple_processor.generate(csv_file, output_file)

# For NIA DTR
nia_processor = NIADTRProcessor()
nia_processor.generate(csv_file, year, month, half, output_file)
```

---

## Common Tasks

### Task 1: Validate CSV Format

```python
from generate_dtr import DTRProcessor

try:
    grouped = DTRProcessor.load_and_group("my_data.csv")
    print(f"✓ CSV is valid. Found {len(grouped)} personnel.")
except ValueError as e:
    print(f"✗ CSV Error: {e}")
except Exception as e:
    print(f"✗ Unexpected error: {e}")
```

---

### Task 2: Check Time Classification

```python
from generate_dtr import DTRProcessor
from datetime import datetime

test_times = [
    datetime(2026, 7, 15, 7, 30),    # 7:30 AM
    datetime(2026, 7, 15, 12, 15),   # 12:15 PM
    datetime(2026, 7, 15, 13, 0),    # 1:00 PM
    datetime(2026, 7, 15, 17, 30),   # 5:30 PM
]

print("Time Classification Test:")
for t in test_times:
    slot = DTRProcessor.classify_scan(t)
    formatted = DTRProcessor.format_time(t)
    print(f"  {formatted} → {slot}")
```

---

### Task 3: Calculate Hours for a Day

```python
from generate_dtr import DTRProcessor
from datetime import datetime, date

# Sample scans for one day
scans = [
    datetime(2026, 7, 15, 8, 0),     # 8:00 AM (AM In)
    datetime(2026, 7, 15, 12, 10),   # 12:10 PM (AM Out)
    datetime(2026, 7, 15, 13, 0),    # 1:00 PM (PM In)
    datetime(2026, 7, 15, 17, 30),   # 5:30 PM (PM Out)
]

row = DTRProcessor.compute_row(date(2026, 7, 15), scans)

print(f"Date: {row['date']}")
print(f"AM: {row['am_in']} - {row['am_out']}")
print(f"PM: {row['pm_in']} - {row['pm_out']}")
print(f"Total Hours: {row['total']}")
if row['note']:
    print(f"Note: {row['note']}")
```

---

### Task 4: Batch Generate PDFs

```python
from generate_simple_dtr import SimpleDTRProcessor
import os

csv_files = [
    "data/january.csv",
    "data/february.csv",
    "data/march.csv",
]

processor = SimpleDTRProcessor()

for csv_file in csv_files:
    if os.path.exists(csv_file):
        month_name = os.path.basename(csv_file).replace(".csv", "")
        output_file = f"{month_name}_dtr.pdf"

        try:
            processor.generate(csv_file, output_file)
            print(f"✓ Generated {output_file}")
        except Exception as e:
            print(f"✗ Failed to generate {output_file}: {e}")
```

---

### Task 5: Extract Time Data for Analysis

```python
from generate_dtr import DTRProcessor
import csv

# Load data
grouped = DTRProcessor.load_and_group("sample/sample.csv")

# Create analysis output
with open("time_analysis.csv", "w", newline="") as f:
    writer = csv.writer(f)
    writer.writerow(["Name", "Date", "Total Hours", "Status"])

    for name in sorted(grouped.keys()):
        for date, scans in sorted(grouped[name].items()):
            row = DTRProcessor.compute_row(date, scans)
            status = "Complete" if not row['note'] else "Incomplete"
            writer.writerow([name, row['date'], row['total'], status])

print("Analysis saved to time_analysis.csv")
```

---

## Class Method Reference

### DTRProcessor (Base Class)

| Method                     | Parameters  | Returns | Description                              |
| -------------------------- | ----------- | ------- | ---------------------------------------- |
| `load_and_group()`         | csv_path    | dict    | Loads CSV and groups by person/date      |
| `classify_scan()`          | datetime    | str     | Returns slot name (am_in/out, pm_in/out) |
| `format_time()`            | datetime    | str     | Formats time as "H:MM AM/PM"             |
| `compute_slots_for_date()` | scans list  | dict    | Computes slots for a single date         |
| `calculate_total_hours()`  | datetimes   | tuple   | Calculates hours and missing info        |
| `compute_row()`            | date, scans | dict    | Complete row with all details            |
| `safe_filename()`          | name        | str     | Makes name filesystem-safe               |

### SimpleDTRProcessor

| Method                 | Parameters                | Description                       |
| ---------------------- | ------------------------- | --------------------------------- |
| `generate()`           | csv_path, output_filename | Generates simple DTR PDF          |
| `build_person_story()` | name, rows, styles        | Creates one person's page content |
| `build_combined_pdf()` | grouped, output_path      | Builds complete PDF document      |

### NIADTRProcessor

| Method                 | Parameters                                   | Description                     |
| ---------------------- | -------------------------------------------- | ------------------------------- |
| `generate()`           | csv_path, year, month, half, output_filename | Generates NIA format PDF        |
| `get_period_dates()`   | year, month, half                            | Returns date list for period    |
| `period_label()`       | period_dates                                 | Returns formatted period string |
| `build_person_story()` | (multiple)                                   | Creates one person's NIA page   |
| `build_combined_pdf()` | (multiple)                                   | Builds NIA format PDF           |
| `_load_logo()`         | path, size                                   | Loads and formats logo image    |

---

## Error Handling

```python
from generate_simple_dtr import SimpleDTRProcessor

processor = SimpleDTRProcessor()

try:
    processor.generate("input.csv", "output.pdf")
except FileNotFoundError:
    print("CSV file not found")
except ValueError as e:
    print(f"CSV format error: {e}")
except Exception as e:
    print(f"Unexpected error: {e}")
```

---

## Tips & Best Practices

1. **Always validate CSV before processing**: Check that the file has the required columns
2. **Use try-except blocks**: Handle file not found and CSV format errors
3. **Reuse processor instances**: Create one instance if processing multiple files
4. **Check for missing data**: The 'note' field indicates incomplete scans
5. **Use meaningful filenames**: Include date/period info in output filename
6. **Test with sample data first**: Use sample/sample.csv before production data
