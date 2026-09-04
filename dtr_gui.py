"""PyQt6 desktop application for generating NIA-format DTR PDFs."""

import calendar
import os
import sys
import traceback
from datetime import date

from PyQt6.QtCore import QObject, QThread, Qt, QUrl, pyqtSignal
from PyQt6.QtGui import QCloseEvent, QDesktopServices, QIcon
from PyQt6.QtWidgets import (
    QApplication, QFileDialog, QFormLayout, QFrame, QGridLayout, QGroupBox, QHBoxLayout,
    QLabel, QLineEdit, QMainWindow, QMessageBox, QPushButton, QSpinBox,
    QSizePolicy, QSplitter, QStatusBar, QVBoxLayout, QWidget, QComboBox,
)

from generate_nia_dtr import NIADTRProcessor

try:
    from PyQt6.QtPdf import QPdfDocument
    from PyQt6.QtPdfWidgets import QPdfView
except ImportError:
    QPdfDocument = None
    QPdfView = None


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(BASE_DIR, "output")


class GenerationWorker(QObject):
    """Run PDF generation away from the Qt event loop."""

    finished = pyqtSignal(str, int, str, bool)
    failed = pyqtSignal(str, str)

    def __init__(self, csv_path, year, month, half, output_name, time_format, copies):
        super().__init__()
        self.csv_path = csv_path
        self.year = year
        self.month = month
        self.half = half
        self.output_name = output_name
        self.time_format = time_format
        self.copies = copies

    def run(self):
        try:
            processor = NIADTRProcessor()
            output_name = self.output_name
            if self.copies == 1:
                output_name = f"{os.path.splitext(output_name)[0]}_preview.pdf"
            output_path = processor.generate(
                self.csv_path, self.year, self.month, self.half, output_name,
                self.time_format, copies=self.copies
            )
            grouped = processor.load_and_group(self.csv_path)
            period = processor.period_label(
                processor.get_period_dates(self.year, self.month, self.half)
            )
            self.finished.emit(
                os.path.abspath(output_path), len(grouped), period, self.copies == 1
            )
        except Exception as error:
            self.failed.emit(str(error), traceback.format_exc())


class PreviewPanel(QFrame):
    """PDF preview that uses Qt PDF support when available."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.document = None
        self.view = None
        self.setObjectName("previewPanel")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)

        heading = QLabel("Preview")
        heading.setObjectName("panelTitle")
        layout.addWidget(heading)

        if QPdfDocument is None:
            empty = QLabel("Install PyQt6 PDF support to preview generated forms.")
            empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(empty, 1)
            return

        self.document = QPdfDocument(self)
        self.view = QPdfView(self)
        self.view.setDocument(self.document)
        self.view.setPageMode(QPdfView.PageMode.MultiPage)
        layout.addWidget(self.view, 1)
        self.show_message("Choose a CSV file and generate a form to preview it here.")

    def show_message(self, text):
        if self.view is None:
            return
        self.view.setEnabled(False)
        self.view.setToolTip(text)

    def load(self, path):
        if self.document is None:
            return
        self.document.load(path)
        self.view.setEnabled(True)
        self.view.setToolTip(path)


class DTRApp(QMainWindow):
    MONTH_NAMES = [calendar.month_name[index] for index in range(1, 13)]
    HALF_CHOICES = ["1st half (days 1-15)", "2nd half (16-end of month)"]
    TIME_CHOICES = ["24-hour clock", "12-hour clock"]

    def __init__(self):
        super().__init__()
        self.worker_thread = None
        self.worker = None
        self.setWindowTitle("NIA DTR Formatter")
        self.setMinimumSize(1050, 800)
        self.resize(1200, 780)
        self._set_icon()
        self._build_ui()
        self._apply_styles()

    def _set_icon(self):
        icon_path = os.path.join(BASE_DIR, "img", "nia_icon.ico")
        if os.path.isfile(icon_path):
            self.setWindowIcon(QIcon(icon_path))

    def _build_ui(self):
        root = QWidget()
        root.setObjectName("root")
        root_layout = QVBoxLayout(root)
        root_layout.setContentsMargins(28, 24, 28, 18)
        root_layout.setSpacing(16)

        header = QHBoxLayout()
        title = QLabel("NIA Daily Time Record")
        title.setObjectName("title")
        subtitle = QLabel("Regional Office No. VI | Panay River Basin Integrated Development Project")
        subtitle.setObjectName("subtitle")
        header_text = QVBoxLayout()
        header_text.addWidget(title)
        header_text.addWidget(subtitle)
        header.addLayout(header_text)
        header.addStretch()
        root_layout.addLayout(header)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setChildrenCollapsible(False)
        splitter.addWidget(self._build_options())
        splitter.addWidget(PreviewPanel())
        splitter.setSizes([390, 760])
        root_layout.addWidget(splitter, 1)
        self.preview = splitter.widget(1)

        self.setCentralWidget(root)
        self.setStatusBar(QStatusBar())
        self.statusBar().showMessage("Ready to generate an NIA DTR form")

    def _build_options(self):
        panel = QFrame()
        panel.setObjectName("optionsPanel")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(22, 20, 22, 20)
        layout.setSpacing(16)

        heading = QLabel("Form settings")
        heading.setObjectName("panelTitle")
        layout.addWidget(heading)

        source_group = QGroupBox("Attendance source")
        source_layout = QVBoxLayout(source_group)
        source_row = QHBoxLayout()
        self.csv_edit = QLineEdit()
        self.csv_edit.setPlaceholderText("Select an attendance CSV")
        self.csv_edit.setReadOnly(True)
        browse = QPushButton("Browse")
        browse.setObjectName("secondaryButton")
        browse.clicked.connect(self.browse_csv)
        source_row.addWidget(self.csv_edit, 1)
        source_row.addWidget(browse)
        source_layout.addLayout(source_row)
        self.file_hint = QLabel("CSV columns: Index, Timestamp, ID, Name, Details")
        self.file_hint.setObjectName("hint")
        source_layout.addWidget(self.file_hint)
        layout.addWidget(source_group)

        period_group = QGroupBox("Pay period")
        period_form = QGridLayout(period_group)
        period_form.setContentsMargins(0, 0, 0, 0)
        period_form.setVerticalSpacing(12)
        period_form.setHorizontalSpacing(0)
        period_form.setColumnStretch(0, 1)
        period_form.setColumnStretch(1, 1)
        period_form.setColumnStretch(2, 1)
        period_form.setColumnStretch(3, 1)
        today = date.today()
        self.month_combo = QComboBox()
        self.month_combo.addItems(self.MONTH_NAMES)
        self.month_combo.setCurrentIndex(today.month - 1)
        self.month_combo.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.year_spin = QSpinBox()
        self.year_spin.setRange(2000, 2100)
        self.year_spin.setValue(today.year)
        self.year_spin.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.half_combo = QComboBox()
        self.half_combo.addItems(self.HALF_CHOICES)
        self.half_combo.setCurrentIndex(0 if today.day <= 15 else 1)
        self.half_combo.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.time_combo = QComboBox()
        self.time_combo.addItems(self.TIME_CHOICES)
        self.time_combo.setCurrentIndex(0)
        self.time_combo.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        period_form.addWidget(self.month_combo, 0, 0, 1, 2)
        period_form.addWidget(self.year_spin, 0, 2, 1, 2)
        period_form.addWidget(self.half_combo, 1, 0, 1, 4)
        period_form.addWidget(self.time_combo, 2, 0, 1, 4)
        layout.addWidget(period_group)

        output_group = QGroupBox("Output")
        output_form = QGridLayout(output_group)
        output_form.setContentsMargins(0, 0, 0, 0)
        output_form.setColumnStretch(1, 1)
        self.output_edit = QLineEdit("nia_dtr_format.pdf")
        self.output_edit.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        output_form.addWidget(self.output_edit, 0, 0, 1, 2)
        output_hint = QLabel("Saved in the output folder beside this application.")
        output_hint.setObjectName("hint")
        output_form.addWidget(output_hint, 1, 0, 1, 2)
        layout.addWidget(output_group)

        action_row = QHBoxLayout()
        self.preview_button = QPushButton("Preview PDF")
        self.preview_button.setObjectName("secondaryButton")
        self.preview_button.clicked.connect(lambda: self.generate(1))
        action_row.addWidget(self.preview_button)
        self.print_button = QPushButton("Print PDF")
        self.print_button.setObjectName("primaryButton")
        self.print_button.clicked.connect(lambda: self.generate(3))
        action_row.addWidget(self.print_button)
        layout.addLayout(action_row)
        self.open_button = QPushButton("Open output folder")
        self.open_button.setObjectName("secondaryButton")
        self.open_button.clicked.connect(self.open_output_folder)
        layout.addWidget(self.open_button)
        layout.addStretch()
        return panel

    def _apply_styles(self):
        self.setStyleSheet(
            """
            QWidget#root { background: #f4f1eb; }
            QMainWindow { background: #f4f1eb; }
            QLabel#title { color: #173f3a; font-size: 28px; font-weight: 700; }
            QLabel#subtitle, QLabel#hint { color: #6d7773; }
            QLabel#panelTitle { color: #173f3a; font-size: 18px; font-weight: 700; }
            QFrame#optionsPanel, QFrame#previewPanel { background: #fffdf9; border: 1px solid #ddd8cf; border-radius: 8px; }
            QGroupBox { color: #344742; font-weight: 700; border: 1px solid #e2ddd4; border-radius: 6px; margin-top: 10px; padding: 16px 12px 12px; }
            QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 4px; }
            QLineEdit, QComboBox, QSpinBox { background: #ffffff; border: 1px solid #c9cec8; border-radius: 4px; padding: 8px; color: #26312e; }
            QPushButton { border-radius: 4px; padding: 10px 14px; font-weight: 700; }
            QPushButton#primaryButton { background: #c45d35; color: white; min-height: 44px; }
            QPushButton#primaryButton:hover { background: #a94c2c; }
            QPushButton#secondaryButton { background: #e6eee9; color: #174b44; }
            QPushButton#secondaryButton:hover { background: #d2e2da; }
            QSplitter::handle { background: #d6d0c5; width: 8px; }
            QStatusBar { color: #52615b; }
            """
        )

    def browse_csv(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Select attendance CSV file", "", "CSV files (*.csv);;All files (*.*)"
        )
        if path:
            self.csv_edit.setText(path)
            self.file_hint.setText(f"Selected: {os.path.basename(path)}")
            self.statusBar().showMessage("CSV file selected")

    def _validated_values(self):
        csv_path = self.csv_edit.text().strip()
        if not csv_path:
            raise ValueError("Select an attendance CSV file first.")
        if not os.path.isfile(csv_path):
            raise ValueError("The selected CSV file could not be found.")
        filename = os.path.basename(self.output_edit.text().strip() or "nia_dtr_format.pdf")
        if not filename.lower().endswith(".pdf"):
            filename += ".pdf"
        return (csv_path, self.year_spin.value(), self.month_combo.currentIndex() + 1,
            self.half_combo.currentIndex() + 1, filename,
            "24" if self.time_combo.currentIndex() == 0 else "12")

    def generate(self, copies):
        try:
            values = self._validated_values()
        except ValueError as error:
            QMessageBox.warning(self, "Check form settings", str(error))
            return

        self.preview_button.setEnabled(False)
        self.print_button.setEnabled(False)
        action = "preview" if copies == 1 else "print"
        self.statusBar().showMessage(f"Generating {action} PDF...")
        self.worker_thread = QThread(self)
        self.worker = GenerationWorker(*values, copies)
        self.worker.moveToThread(self.worker_thread)
        self.worker_thread.started.connect(self.worker.run)
        self.worker.finished.connect(self.on_success)
        self.worker.failed.connect(self.on_failure)
        self.worker.finished.connect(self.worker_thread.quit)
        self.worker.failed.connect(self.worker_thread.quit)
        self.worker_thread.finished.connect(self.worker.deleteLater)
        self.worker_thread.finished.connect(self.worker_thread.deleteLater)
        self.worker_thread.start()

    def on_success(self, path, count, period, is_preview):
        self.preview_button.setEnabled(True)
        self.print_button.setEnabled(True)
        action = "Preview" if is_preview else "Printable"
        self.statusBar().showMessage(f"Generated {action.lower()} PDF for {count} personnel records")
        if is_preview:
            self.preview.load(path)
        QMessageBox.information(
            self, "DTR generated",
            f"{action} DTR created successfully for {period}.\n\nSaved to:\n{path}"
        )

    def on_failure(self, message, detail):
        self.preview_button.setEnabled(True)
        self.print_button.setEnabled(True)
        self.statusBar().showMessage("Generation failed")
        print(detail)
        QMessageBox.critical(self, "Generation failed", f"Could not generate the NIA DTR.\n\n{message}")

    def open_output_folder(self):
        os.makedirs(OUTPUT_DIR, exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(OUTPUT_DIR))

    def closeEvent(self, event: QCloseEvent):
        if self.worker_thread and self.worker_thread.isRunning():
            self.worker_thread.quit()
            self.worker_thread.wait()
        event.accept()


def main():
    app = QApplication(sys.argv)
    window = DTRApp()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
