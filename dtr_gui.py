"""
DTR Generator - Simple Desktop App

A point-and-click window for generating Daily Time Record PDFs from an
attendance CSV file. No command line or typing required.

Requires generate_dtr.py to be in the same folder (this app reuses its
CSV-reading and PDF-building logic).

To run:
    python dtr_gui.py

If double-clicking the file doesn't work on your computer, right-click
the file and choose "Open with" > Python.
"""

import os
import sys
import threading
import traceback
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

# Reuse all the logic already built and tested in generate_dtr.py
import generate_dtr


class DTRApp(tk.Tk):
    def __init__(self):
        super().__init__()

        self.title("DTR Generator - Panay River Basin Integrated Development Project")
        self.geometry("560x360")
        self.resizable(False, False)

        self.csv_path = tk.StringVar()
        self.output_name = tk.StringVar(value="DTR_combined.pdf")
        self.status_text = tk.StringVar(value="Choose your attendance CSV file to begin.")

        self._build_layout()

    # ------------------------------------------------------------------ UI
    def _build_layout(self):
        pad = {"padx": 16, "pady": 8}

        header = tk.Label(
            self, text="Daily Time Record (DTR) Generator",
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

    def on_generate(self):
        csv_path = self.csv_path.get().strip()
        if not csv_path:
            messagebox.showwarning("Missing file", "Please select an attendance CSV file first.")
            return
        if not os.path.isfile(csv_path):
            messagebox.showerror("File not found", "The selected CSV file could not be found.")
            return

        filename = self.output_name.get().strip() or "DTR_combined.pdf"
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


if __name__ == "__main__":
    app = DTRApp()
    app.mainloop()