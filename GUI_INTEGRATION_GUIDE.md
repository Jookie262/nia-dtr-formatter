# Integration Guide for dtr_gui.py

This guide shows how to update `dtr_gui.py` to use the new OOP-based `SimpleDTRProcessor` and `NIADTRProcessor` classes.

## Before and After Comparison

### Current Implementation (Procedural)

If your `dtr_gui.py` currently uses procedural functions like this:

```python
import generate_simple_dtr
import generate_nia_dtr
import os

def generate_simple_dtr_button_clicked():
    csv_file = get_csv_file_from_user()
    output_file = get_output_filename_from_user()

    try:
        grouped = generate_simple_dtr.load_and_group(csv_file)
        generate_simple_dtr.build_combined_pdf(grouped, output_file)
        show_success_message(f"PDF generated: {output_file}")
    except Exception as e:
        show_error_message(f"Error: {e}")

def generate_nia_dtr_button_clicked():
    csv_file = get_csv_file_from_user()
    year = get_year_from_user()
    month = get_month_from_user()
    half = get_half_from_user()
    output_file = get_output_filename_from_user()

    try:
        grouped = generate_simple_dtr.load_and_group(csv_file)
        period_dates = generate_nia_dtr.get_period_dates(year, month, half)
        generate_nia_dtr.build_combined_pdf(grouped, period_dates, output_file)
        show_success_message(f"PDF generated: {output_file}")
    except Exception as e:
        show_error_message(f"Error: {e}")
```

---

### Updated Implementation (OOP)

Here's the refactored version using the new classes:

```python
from generate_simple_dtr import SimpleDTRProcessor
from generate_nia_dtr import NIADTRProcessor
import os

# Create processor instances (can be done once at GUI startup)
simple_processor = SimpleDTRProcessor()
nia_processor = NIADTRProcessor()

def generate_simple_dtr_button_clicked():
    csv_file = get_csv_file_from_user()
    output_file = get_output_filename_from_user()

    try:
        simple_processor.generate(csv_file, output_file)
        show_success_message(f"PDF generated: {output_file}")
    except FileNotFoundError:
        show_error_message(f"CSV file not found: {csv_file}")
    except ValueError as e:
        show_error_message(f"CSV format error: {e}")
    except Exception as e:
        show_error_message(f"Unexpected error: {e}")

def generate_nia_dtr_button_clicked():
    csv_file = get_csv_file_from_user()
    year = get_year_from_user()
    month = get_month_from_user()
    half = get_half_from_user()
    output_file = get_output_filename_from_user()

    try:
        nia_processor.generate(csv_file, year, month, half, output_file)
        show_success_message(f"PDF generated: {output_file}")
    except FileNotFoundError:
        show_error_message(f"CSV file not found: {csv_file}")
    except ValueError as e:
        show_error_message(f"CSV format error or invalid date: {e}")
    except Exception as e:
        show_error_message(f"Unexpected error: {e}")
```

---

## Benefits of OOP Integration

1. **Cleaner Code**: Less boilerplate, more focused logic
2. **Better Error Handling**: Catch specific exceptions
3. **Reusable**: Single processor instance for multiple operations
4. **Easier Testing**: Can mock processor objects
5. **Object State**: Can store processor configuration if needed

---

## Advanced GUI Integration

### Option 1: GUI Settings Class

```python
from generate_simple_dtr import SimpleDTRProcessor
from generate_nia_dtr import NIADTRProcessor

class DTRGeneratorSettings:
    def __init__(self):
        self.simple_processor = SimpleDTRProcessor()
        self.nia_processor = NIADTRProcessor()
        self.last_output_dir = "output"
        self.default_filename = "DTR"

class DTRGeneratorGUI:
    def __init__(self):
        self.settings = DTRGeneratorSettings()

    def on_generate_simple(self):
        try:
            csv_file = self.get_csv_from_dialog()
            output = self.get_output_from_dialog(self.settings.last_output_dir)

            self.settings.simple_processor.generate(csv_file, output)
            self.show_success(f"Generated: {output}")

            # Remember the directory
            self.settings.last_output_dir = os.path.dirname(output)
        except Exception as e:
            self.show_error(str(e))

    def on_generate_nia(self):
        try:
            csv_file = self.get_csv_from_dialog()
            year, month, half = self.get_date_from_dialog()
            output = self.get_output_from_dialog(self.settings.last_output_dir)

            self.settings.nia_processor.generate(
                csv_file, year, month, half, output
            )
            self.show_success(f"Generated: {output}")

            # Remember the directory
            self.settings.last_output_dir = os.path.dirname(output)
        except Exception as e:
            self.show_error(str(e))
```

---

### Option 2: Status/Progress Wrapper

```python
from generate_simple_dtr import SimpleDTRProcessor
from generate_nia_dtr import NIADTRProcessor

class DTRProcessorWithProgress(SimpleDTRProcessor):
    def __init__(self, progress_callback=None):
        super().__init__()
        self.progress_callback = progress_callback

    def generate(self, csv_path, output_filename="DTR_combined.pdf"):
        """Generate with progress updates"""
        if self.progress_callback:
            self.progress_callback("Loading CSV file...")

        # Call parent method (would need to refactor for true progress)
        super().generate(csv_path, output_filename)

        if self.progress_callback:
            self.progress_callback("Complete!")

# Usage in GUI
processor = DTRProcessorWithProgress(progress_callback=update_progress_bar)
processor.generate(csv_file, output_file)
```

---

### Option 3: Validation Helper

```python
from generate_dtr import DTRProcessor

def validate_csv_before_processing(csv_path):
    """Validate CSV file before passing to processor"""
    try:
        grouped = DTRProcessor.load_and_group(csv_path)

        if not grouped:
            return False, "No valid data in CSV"

        personnel_count = len(grouped)
        total_scans = sum(len(scans) for dates in grouped.values() for scans in dates.values())

        return True, f"✓ CSV valid: {personnel_count} personnel, {total_scans} scans"

    except FileNotFoundError:
        return False, "CSV file not found"
    except ValueError as e:
        return False, f"CSV format error: {e}"
    except Exception as e:
        return False, f"Error reading CSV: {e}"

# Usage in GUI
is_valid, message = validate_csv_before_processing(csv_file)
if is_valid:
    status_label.setText(message)
    generate_button.setEnabled(True)
else:
    status_label.setText(f"✗ {message}")
    generate_button.setEnabled(False)
```

---

## Migration Checklist

If updating an existing GUI:

- [ ] Import the processor classes
- [ ] Create processor instances at GUI startup
- [ ] Replace `load_and_group()` calls with `processor.generate()`
- [ ] Replace `build_combined_pdf()` calls with `processor.generate()`
- [ ] Update error handling to catch specific exceptions
- [ ] Test with sample data
- [ ] Verify output PDF generation
- [ ] Test error cases (missing file, invalid format)
- [ ] Remove old import statements if no longer needed

---

## Code Example: Complete GUI Integration

Here's a complete minimal example:

```python
import tkinter as tk
from tkinter import filedialog, messagebox
from generate_simple_dtr import SimpleDTRProcessor
from generate_nia_dtr import NIADTRProcessor

class DTRGeneratorApp:
    def __init__(self, root):
        self.root = root
        self.root.title("DTR Generator")

        # Create processors
        self.simple_processor = SimpleDTRProcessor()
        self.nia_processor = NIADTRProcessor()

        # UI Elements
        tk.Button(
            root, text="Generate Simple DTR",
            command=self.generate_simple
        ).pack(pady=10)

        tk.Button(
            root, text="Generate NIA DTR",
            command=self.generate_nia
        ).pack(pady=10)

    def generate_simple(self):
        csv_file = filedialog.askopenfilename(
            title="Select CSV file",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")]
        )
        if not csv_file:
            return

        try:
            self.simple_processor.generate(csv_file, "output.pdf")
            messagebox.showinfo("Success", "PDF generated successfully!")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to generate PDF: {e}")

    def generate_nia(self):
        csv_file = filedialog.askopenfilename(
            title="Select CSV file",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")]
        )
        if not csv_file:
            return

        # In a real GUI, these would come from form fields
        year, month, half = 2026, 7, 1

        try:
            self.nia_processor.generate(
                csv_file, year, month, half, "output.pdf"
            )
            messagebox.showinfo("Success", "PDF generated successfully!")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to generate PDF: {e}")

if __name__ == "__main__":
    root = tk.Tk()
    app = DTRGeneratorApp(root)
    root.mainloop()
```

---

## Summary

- **Old Way**: Multiple function calls with data passing
- **New Way**: Single method call with all parameters
- **Result**: Cleaner, more maintainable GUI code
- **Compatibility**: Both approaches work independently

The refactored code is production-ready and can be integrated into your GUI at any time!
