"""
DTR Generator - Simple Desktop App

A point-and-click window for generating Daily Time Record PDFs from an
attendance CSV file. No command line or typing required.

Requires generate_dtr.py and generate_nia_dtr.py to be in the same folder
(this app reuses their CSV-reading and PDF-building logic).

The window has two tabs:
    - "Simple DTR": the original generator (generate_dtr.py logic).
    - "NIA DTR": official NIA Regional Office VI form, for a chosen
      half-month period (generate_nia_dtr.py logic).

To run:
    python dtr_gui.py

If double-clicking the file doesn't work on your computer, right-click
the file and choose "Open with" > Python.
"""

from logging import root
import os
import sys
import calendar
import threading
import traceback
from datetime import date
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

# Reuse all the logic already built and tested in generate_dtr.py /
# generate_nia_dtr.py.
import generate_dtr
import generate_nia_dtr


class SimpleDTRTab(tk.Frame):
    """Tab for the original Simple DTR generator (generate_dtr.py logic)."""

    def __init__(self, parent):
        super().__init__(parent)

        self.csv_path = tk.StringVar()
        self.output_name = tk.StringVar(value="simple_dtr_format.pdf")
        self.status_text = tk.StringVar(value="Choose your attendance CSV file to begin.")

        self._build_layout()

    # ------------------------------------------------------------------ UI
    def _build_layout(self):
        pad = {"padx": 16, "pady": 8}

        header = tk.Label(
            self, text="Simple DTR Format",
            font=("Segoe UI", 15, "bold")
        )
        header.pack(pady=(18, 2))

        subheader = tk.Label(
            self, text="Panay River Basin Integrated Development Project",
            font=("Segoe UI", 10), fg="#555555"
        )
        subheader.pack(pady=(0, 16))

        # --- Step 1: choose CSV file ---
        step1 = tk.LabelFrame(self, text=" Step 1: Select attendance CSV file ",
                               font=("Segoe UI", 9, "bold"))
        step1.pack(fill="x", **pad)

        row1 = tk.Frame(step1)
        row1.pack(fill="x", padx=10, pady=10)

        self.file_entry = tk.Entry(row1, textvariable=self.csv_path, state="readonly", width=48)
        self.file_entry.pack(side="left", fill="x", expand=True)

        browse_btn = tk.Button(row1, text="Browse...", command=self.browse_csv, width=12)
        browse_btn.pack(side="left", padx=(8, 0))

        # --- Step 2: output file name ---
        step2 = tk.LabelFrame(self, text=" Step 2: Name your output PDF ",
                               font=("Segoe UI", 9, "bold"))
        step2.pack(fill="x", **pad)

        row2 = tk.Frame(step2)
        row2.pack(fill="x", padx=10, pady=10)

        name_entry = tk.Entry(row2, textvariable=self.output_name, width=48)
        name_entry.pack(side="left", fill="x", expand=True)

        tk.Label(step2, text="Will be saved inside the 'output' folder next to this app.",
                 font=("Segoe UI", 8), fg="#777777").pack(anchor="w", padx=10, pady=(0, 8))

        # --- Step 3: generate ---
        self.generate_btn = tk.Button(
            self, text="Generate DTR PDF", command=self.on_generate,
            font=("Segoe UI", 11, "bold"), bg="#2c3e50", fg="white",
            activebackground="#34495e", activeforeground="white",
            height=2,
        )
        self.generate_btn.pack(fill="x", padx=16, pady=(6, 6))

        self.progress = ttk.Progressbar(self, mode="indeterminate")
        self.progress.pack(fill="x", padx=16, pady=(0, 6))

        status_label = tk.Label(self, textvariable=self.status_text,
                                 font=("Segoe UI", 9), fg="#333333",
                                 wraplength=520, justify="left")
        status_label.pack(fill="x", padx=16, pady=(4, 0))

        open_folder_btn = tk.Button(self, text="Open output folder",
                                     command=self.open_output_folder, width=20)
        open_folder_btn.pack(pady=(10, 0))

        footer_label = tk.Label(
            self, text="Created by Jolou - August 20, 2026 (v.1.0)",
            font=("Segoe UI", 9)
        )

        footer_label.pack(side="bottom", pady=5)

    # ------------------------------------------------------------- actions
    def browse_csv(self):
        path = filedialog.askopenfilename(
            title="Select attendance CSV file",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
        )
        if path:
            self.csv_path.set(path)
            self.status_text.set(f"Selected: {os.path.basename(path)}")

    def open_output_folder(self):
        open_output_folder()

    def on_generate(self):
        csv_path = self.csv_path.get().strip()
        if not csv_path:
            messagebox.showwarning("Missing file", "Please select an attendance CSV file first.")
            return
        if not os.path.isfile(csv_path):
            messagebox.showerror("File not found", "The selected CSV file could not be found.")
            return

        filename = self.output_name.get().strip() or "simple_dtr_format.pdf"
        filename = os.path.basename(filename)
        if not filename.lower().endswith(".pdf"):
            filename += ".pdf"

        # Disable the button and show a busy indicator while working
        self.generate_btn.config(state="disabled")
        self.status_text.set("Generating... please wait.")
        self.progress.start(12)

        # Run in a background thread so the window doesn't freeze
        thread = threading.Thread(target=self._run_generation, args=(csv_path, filename), daemon=True)
        thread.start()

    def _run_generation(self, csv_path, filename):
        try:
            output_dir = "output"
            os.makedirs(output_dir, exist_ok=True)
            output_path = os.path.join(output_dir, filename)

            grouped = generate_dtr.load_and_group(csv_path)
            if not grouped:
                raise ValueError("No personnel records were found in this CSV file.")

            names = generate_dtr.build_combined_pdf(grouped, output_path)
            full_path = os.path.abspath(output_path)

            self.after(0, self._on_success, full_path, len(names))
        except Exception as e:
            error_detail = traceback.format_exc()
            self.after(0, self._on_error, str(e), error_detail)

    def _on_success(self, full_path, count):
        self.progress.stop()
        self.generate_btn.config(state="normal")
        self.status_text.set(f"Done! {count} personnel included.\nSaved to: {full_path}")
        messagebox.showinfo("Success", f"DTR PDF generated successfully!\n\n"
                                        f"{count} personnel included.\n\nSaved to:\n{full_path}")

    def _on_error(self, message, detail):
        self.progress.stop()
        self.generate_btn.config(state="normal")
        self.status_text.set(f"Something went wrong: {message}")
        messagebox.showerror(
            "Error",
            f"Could not generate the DTR PDF.\n\n{message}\n\n"
            f"Please check that your CSV file has the correct columns "
            f"(Index, Timestamp, ID, Name, Details) and try again."
        )
        print(detail)  # full traceback goes to console for troubleshooting


class NIADTRTab(tk.Frame):
    """
    Tab for the NIA (Regional Office VI) format DTR generator
    (generate_nia_dtr.py logic).

    Lets the user pick an attendance CSV, a year/month, and which half of
    the month (1-15 or 16-end), then builds one combined PDF with one
    NIA-format page per person for that period.
    """

    MONTH_NAMES = [calendar.month_name[m] for m in range(1, 13)]
    HALF_CHOICES = ["1st half (days 1-15)", "2nd half (16-end of month)"]

    def __init__(self, parent):
        super().__init__(parent)

        today = date.today()

        self.csv_path = tk.StringVar()
        self.year_var = tk.StringVar(value=str(today.year))
        self.month_var = tk.StringVar(value=self.MONTH_NAMES[today.month - 1])
        self.half_var = tk.StringVar(
            value=self.HALF_CHOICES[0] if today.day <= 15 else self.HALF_CHOICES[1]
        )
        self.output_name = tk.StringVar(value="nia_dtr_format.pdf")
        self.status_text = tk.StringVar(value="Choose your attendance CSV file to begin.")

        self._build_layout()

    # ------------------------------------------------------------------ UI
    def _build_layout(self):
        pad = {"padx": 16, "pady": 8}

        header = tk.Label(
            self, text="NIA DTR Format",
            font=("Segoe UI", 15, "bold")
        )
        header.pack(pady=(18, 2))

        subheader = tk.Label(
            self, text="Panay River Basin Integrated Development Project",
            font=("Segoe UI", 10), fg="#555555"
        )
        subheader.pack(pady=(0, 16))

        # --- Step 1: choose CSV file ---
        step1 = tk.LabelFrame(self, text=" Step 1: Select attendance CSV file ",
                               font=("Segoe UI", 9, "bold"))
        step1.pack(fill="x", **pad)

        row1 = tk.Frame(step1)
        row1.pack(fill="x", padx=10, pady=10)

        self.file_entry = tk.Entry(row1, textvariable=self.csv_path, state="readonly", width=42)
        self.file_entry.pack(side="left", fill="x", expand=True)

        browse_btn = tk.Button(row1, text="Browse...", command=self.browse_csv, width=12)
        browse_btn.pack(side="left", padx=(8, 0))

        # --- Step 2: choose period ---
        step2 = tk.LabelFrame(self, text=" Step 2: Choose the pay period ",
                               font=("Segoe UI", 9, "bold"))
        step2.pack(fill="x", **pad)

        row2 = tk.Frame(step2)
        row2.pack(fill="x", padx=10, pady=10)

        tk.Label(row2, text="Month:").pack(side="left")
        month_combo = ttk.Combobox(row2, textvariable=self.month_var, values=self.MONTH_NAMES,
                                    state="readonly", width=11)
        month_combo.pack(side="left", padx=(4, 14))

        tk.Label(row2, text="Year:").pack(side="left")
        year_spin = tk.Spinbox(row2, textvariable=self.year_var, from_=2000, to=2100, width=6)
        year_spin.pack(side="left", padx=(4, 14))

        tk.Label(row2, text="Period:").pack(side="left")
        half_combo = ttk.Combobox(row2, textvariable=self.half_var, values=self.HALF_CHOICES,
                                   state="readonly", width=22)
        half_combo.pack(side="left", padx=(4, 0))

        # --- Step 3: output file name ---
        step3 = tk.LabelFrame(self, text=" Step 3: Name your output PDF ",
                               font=("Segoe UI", 9, "bold"))
        step3.pack(fill="x", **pad)

        row3 = tk.Frame(step3)
        row3.pack(fill="x", padx=10, pady=10)

        name_entry = tk.Entry(row3, textvariable=self.output_name, width=48)
        name_entry.pack(side="left", fill="x", expand=True)

        tk.Label(step3, text="Will be saved inside the 'output' folder next to this app.",
                 font=("Segoe UI", 8), fg="#777777").pack(anchor="w", padx=10, pady=(0, 8))

        # --- Step 4: generate ---
        self.generate_btn = tk.Button(
            self, text="Generate NIA DTR PDF", command=self.on_generate,
            font=("Segoe UI", 11, "bold"), bg="#2c3e50", fg="white",
            activebackground="#34495e", activeforeground="white",
            height=2,
        )
        self.generate_btn.pack(fill="x", padx=16, pady=(6, 6))

        self.progress = ttk.Progressbar(self, mode="indeterminate")
        self.progress.pack(fill="x", padx=16, pady=(0, 6))

        status_label = tk.Label(self, textvariable=self.status_text,
                                 font=("Segoe UI", 9), fg="#333333",
                                 wraplength=520, justify="left")
        status_label.pack(fill="x", padx=16, pady=(4, 0))

        open_folder_btn = tk.Button(self, text="Open output folder",
                                     command=self.open_output_folder, width=20)
        open_folder_btn.pack(pady=(10, 0))

        footer_label = tk.Label(
            self, text="Created by Jolou - August 20, 2026 (v.1.0)",
            font=("Segoe UI", 9)
        )

        footer_label.pack(side="bottom", pady=5)

    # ------------------------------------------------------------- actions
    def browse_csv(self):
        path = filedialog.askopenfilename(
            title="Select attendance CSV file",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
        )
        if path:
            self.csv_path.set(path)
            self.status_text.set(f"Selected: {os.path.basename(path)}")

    def open_output_folder(self):
        open_output_folder()

    def on_generate(self):
        csv_path = self.csv_path.get().strip()
        if not csv_path:
            messagebox.showwarning("Missing file", "Please select an attendance CSV file first.")
            return
        if not os.path.isfile(csv_path):
            messagebox.showerror("File not found", "The selected CSV file could not be found.")
            return

        try:
            year = int(self.year_var.get())
            month = self.MONTH_NAMES.index(self.month_var.get()) + 1
            half = 1 if self.half_var.get() == self.HALF_CHOICES[0] else 2
        except (ValueError, IndexError):
            messagebox.showerror("Invalid period", "Please choose a valid month, year, and period.")
            return

        filename = self.output_name.get().strip() or "nia_dtr_format.pdf"
        filename = os.path.basename(filename)
        if not filename.lower().endswith(".pdf"):
            filename += ".pdf"

        # Disable the button and show a busy indicator while working
        self.generate_btn.config(state="disabled")
        self.status_text.set("Generating... please wait.")
        self.progress.start(12)

        # Run in a background thread so the window doesn't freeze
        thread = threading.Thread(
            target=self._run_generation, args=(csv_path, year, month, half, filename), daemon=True
        )
        thread.start()

    def _run_generation(self, csv_path, year, month, half, filename):
        try:
            output_dir = "output"
            os.makedirs(output_dir, exist_ok=True)
            output_path = os.path.join(output_dir, filename)

            grouped = generate_dtr.load_and_group(csv_path)
            if not grouped:
                raise ValueError("No personnel records were found in this CSV file.")

            period_dates = generate_nia_dtr.get_period_dates(year, month, half)
            names = generate_nia_dtr.build_combined_pdf(grouped, period_dates, output_path)
            full_path = os.path.abspath(output_path)
            period_lbl = generate_nia_dtr.period_label(period_dates)

            self.after(0, self._on_success, full_path, len(names), period_lbl)
        except Exception as e:
            error_detail = traceback.format_exc()
            self.after(0, self._on_error, str(e), error_detail)

    def _on_success(self, full_path, count, period_lbl):
        self.progress.stop()
        self.generate_btn.config(state="normal")
        self.status_text.set(
            f"Done! {count} personnel included for {period_lbl}.\nSaved to: {full_path}"
        )
        messagebox.showinfo(
            "Success",
            f"NIA DTR PDF generated successfully!\n\n"
            f"Period: {period_lbl}\n{count} personnel included.\n\nSaved to:\n{full_path}",
        )

    def _on_error(self, message, detail):
        self.progress.stop()
        self.generate_btn.config(state="normal")
        self.status_text.set(f"Something went wrong: {message}")
        messagebox.showerror(
            "Error",
            f"Could not generate the NIA DTR PDF.\n\n{message}\n\n"
            f"Please check that your CSV file has the correct columns "
            f"(Index, Timestamp, ID, Name, Details) and try again."
        )
        print(detail)  # full traceback goes to console for troubleshooting


def open_output_folder():
    """Open (or create) the shared 'output' folder next to this app."""
    output_dir = os.path.join(os.getcwd(), "output")
    os.makedirs(output_dir, exist_ok=True)
    try:
        if sys.platform.startswith("win"):
            os.startfile(output_dir)
        elif sys.platform == "darwin":
            os.system(f'open "{output_dir}"')
        else:
            os.system(f'xdg-open "{output_dir}"')
    except Exception:
        messagebox.showinfo("Output folder", f"Output folder is located at:\n{output_dir}")


class DTRApp(tk.Tk):
    def __init__(self):
        super().__init__()

        self.iconbitmap("img/nia_icon.ico")
        self.title("NIA DTR Generator - Panay River Basin Integrated Development Project")
        self.geometry("600x600")
        self.resizable(False, False)

        notebook = ttk.Notebook(self)
        notebook.pack(fill="both", expand=True)

        simple_tab = SimpleDTRTab(notebook)
        nia_tab = NIADTRTab(notebook)

        notebook.add(simple_tab, text="Simple DTR")
        notebook.add(nia_tab, text="NIA DTR")


if __name__ == "__main__":
    app = DTRApp()
    app.mainloop()