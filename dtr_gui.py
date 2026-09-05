"""PyQt6 desktop application for generating NIA-format DTR PDFs."""

import calendar
import os
import sys
import traceback
from datetime import date

from PyQt6.QtCore import (
    QSortFilterProxyModel, QObject, QThread, QTimer, Qt, QUrl, pyqtSignal,
)
from PyQt6.QtGui import (
    QCloseEvent, QDesktopServices, QIcon, QStandardItem, QStandardItemModel,
)
from PyQt6.QtWidgets import (
    QApplication, QFileDialog, QFormLayout, QFrame, QGridLayout, QGroupBox, QHBoxLayout,
    QLabel, QLineEdit, QMainWindow, QMessageBox, QPushButton, QSpinBox,
    QSizePolicy, QSplitter, QScrollArea, QStatusBar, QVBoxLayout, QWidget, QComboBox,
    QStyleFactory, QToolButton,
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

    finished = pyqtSignal(str, int, str)
    failed = pyqtSignal(str, str)

    def __init__(self, csv_path, year, month, half, output_name, time_format,
                 employee_mode, employee_names, copies):
        super().__init__()
        self.csv_path = csv_path
        self.year = year
        self.month = month
        self.half = half
        self.output_name = output_name
        self.time_format = time_format
        self.copies = copies
        self.employee_mode = employee_mode
        self.employee_names = employee_names

    def run(self):
        try:
            processor = NIADTRProcessor()
            output_name = self.output_name
            if self.copies == 1:
                output_name = f"{os.path.splitext(output_name)[0]}_preview.pdf"
            output_path = processor.generate(
                self.csv_path, self.year, self.month, self.half, output_name,
                self.time_format, copies=self.copies,
                employee_mode=self.employee_mode, employee_names=self.employee_names,
            )
            grouped = processor.load_and_group(self.csv_path)
            if self.employee_mode == "selected":
                grouped = {
                    name: grouped[name] for name in self.employee_names if name in grouped
                }
            elif self.employee_mode == "except":
                grouped = {
                    name: data for name, data in grouped.items()
                    if name not in self.employee_names
                }
            period = processor.period_label(
                processor.get_period_dates(self.year, self.month, self.half)
            )
            self.finished.emit(os.path.abspath(output_path), len(grouped), period)
        except Exception as error:
            self.failed.emit(str(error), traceback.format_exc())


class MultiSelectComboBox(QComboBox):
    """A searchable, checkable dropdown for selecting multiple employees."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._reopening = False
        self._source_model = QStandardItemModel(self)
        self._proxy_model = QSortFilterProxyModel(self)
        self._proxy_model.setSourceModel(self._source_model)
        self._proxy_model.setFilterCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self._proxy_model.setFilterKeyColumn(0)
        self.setModel(self._proxy_model)
        self.setEditable(True)
        self.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self.lineEdit().setPlaceholderText("Search and select employees")
        self.lineEdit().textEdited.connect(self._filter_items)
        self.view().pressed.connect(self._toggle_item)

    def set_items(self, items):
        self._source_model.clear()
        for name in items:
            item = QStandardItem(name)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setData(Qt.CheckState.Unchecked, Qt.ItemDataRole.CheckStateRole)
            self._source_model.appendRow(item)
        self._proxy_model.setFilterFixedString("")
        self._update_summary()

    def selected_items(self):
        return [
            self._source_model.item(row).text()
            for row in range(self._source_model.rowCount())
            if self._source_model.item(row).checkState() == Qt.CheckState.Checked
        ]

    def _toggle_item(self, index):
        source_index = self._proxy_model.mapToSource(index)
        item = self._source_model.itemFromIndex(source_index)
        new_state = (
            Qt.CheckState.Unchecked
            if item.checkState() == Qt.CheckState.Checked
            else Qt.CheckState.Checked
        )
        item.setData(new_state, Qt.ItemDataRole.CheckStateRole)
        self._reopening = True
        QTimer.singleShot(0, self._reopen_popup)

    def _filter_items(self, text):
        self._proxy_model.setFilterFixedString(text.strip())

    def showPopup(self):
        self.lineEdit().clear()
        self._proxy_model.setFilterFixedString("")
        super().showPopup()
        self.lineEdit().setFocus()

    def _reopen_popup(self):
        self._reopening = False
        super().showPopup()
        self.lineEdit().setFocus()

    def hidePopup(self):
        super().hidePopup()
        if not self._reopening:
            self._proxy_model.setFilterFixedString("")
            self._update_summary()

    def _update_summary(self):
        selected = self.selected_items()
        if not selected:
            summary = ""
        elif len(selected) == 1:
            summary = selected[0]
        else:
            summary = f"{len(selected)} employees selected"
        self.lineEdit().setText(summary)

    def clear_selection(self):
        for row in range(self._source_model.rowCount()):
            self._source_model.item(row).setData(
                Qt.CheckState.Unchecked, Qt.ItemDataRole.CheckStateRole
            )
        self.lineEdit().clear()
        self._proxy_model.setFilterFixedString("")
        self._update_summary()


class PreviewPanel(QFrame):
    """PDF preview that uses Qt PDF support when available."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.document = None
        self.view = None
        self.document_path = None
        self.setObjectName("previewPanel")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        toolbar = QWidget()
        toolbar.setObjectName("previewToolbar")
        toolbar_layout = QHBoxLayout(toolbar)
        toolbar_layout.setContentsMargins(20, 12, 20, 12)
        toolbar_layout.setSpacing(8)
        heading = QLabel("DOCUMENT PREVIEW")
        heading.setObjectName("panelTitle")
        toolbar_layout.addWidget(heading)
        toolbar_layout.addStretch()
        self.zoom_out = QToolButton()
        self.zoom_out.setText("-")
        self.zoom_out.setToolTip("Zoom out")
        self.zoom_in = QToolButton()
        self.zoom_in.setText("+")
        self.zoom_in.setToolTip("Zoom in")
        self.zoom_label = QLabel("100%")
        self.zoom_label.setObjectName("zoomLabel")
        toolbar_layout.addWidget(self.zoom_out)
        toolbar_layout.addWidget(self.zoom_label)
        toolbar_layout.addWidget(self.zoom_in)
        toolbar_layout.addSpacing(12)
        open_button = QToolButton()
        open_button.setText("Open")
        open_button.setToolTip("Open the generated PDF")
        open_button.clicked.connect(self._open_document)
        toolbar_layout.addWidget(open_button)
        layout.addWidget(toolbar)

        if QPdfDocument is None:
            empty = QLabel("Install PyQt6 PDF support to preview generated forms.")
            empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(empty, 1)
            return

        self.document = QPdfDocument(self)
        self.view = QPdfView(self)
        self.view.setDocument(self.document)
        self.view.setPageMode(QPdfView.PageMode.MultiPage)
        self.view.setZoomMode(QPdfView.ZoomMode.Custom)
        self.view.setZoomFactor(1.0)
        self.zoom_out.clicked.connect(lambda: self._change_zoom(0.9))
        self.zoom_in.clicked.connect(lambda: self._change_zoom(1.1))
        self.view.zoomFactorChanged.connect(self._update_zoom_label)
        layout.addWidget(self.view, 1)
        self.show_message("Choose a CSV file and generate a form to preview it here.")

    def _change_zoom(self, multiplier):
        if self.view is None:
            return
        zoom = max(0.25, min(4.0, self.view.zoomFactor() * multiplier))
        self.view.setZoomFactor(zoom)

    def _update_zoom_label(self, factor):
        self.zoom_label.setText(f"{round(factor * 100)}%")

    def _open_document(self):
        if self.document is not None and self.document.pageCount() > 0 and self.document_path:
            QDesktopServices.openUrl(QUrl.fromLocalFile(self.document_path))

    def show_message(self, text):
        if self.view is None:
            return
        self.view.setEnabled(False)
        self.view.setToolTip(text)

    def load(self, path):
        if self.document is None:
            return
        self.document.load(path)
        self.document_path = path
        self.view.setEnabled(True)
        self.view.setZoomFactor(1.0)


class DTRApp(QMainWindow):
    MONTH_NAMES = [calendar.month_name[index] for index in range(1, 13)]
    HALF_CHOICES = ["1st half (days 1-15)", "2nd half (16-end of month)"]
    TIME_CHOICES = ["24-hour clock", "12-hour clock"]

    def __init__(self):
        super().__init__()
        self.worker_thread = None
        self.worker = None
        self.setWindowTitle("NIA DTR Formatter")
        self.setMinimumSize(1000, 680)
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
        root_layout.setContentsMargins(20, 16, 20, 16)
        root_layout.setSpacing(12)

        header = QHBoxLayout()
        header.setSpacing(0)
        title = QLabel("NIA Daily Time Record Formatter")
        title.setObjectName("title")
        subtitle = QLabel("Regional Office No. VI | Panay River Basin Integrated Development Project")
        subtitle.setObjectName("subtitle")
        header_text = QVBoxLayout()
        header_text.setSpacing(1)
        header_text.addWidget(title)
        header_text.addWidget(subtitle)
        header_text_widget = QWidget()
        header_text_widget.setLayout(header_text)
        header_text_widget.setFixedWidth(590)
        header_text_widget.setObjectName("headerText")
        title.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        subtitle.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        header.addWidget(header_text_widget)
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
        status_bar = QStatusBar()
        status_bar.setSizeGripEnabled(False)
        footer_label = QLabel("v.3.0 • Created by Jolou • September 5, 2026")
        footer_label.setObjectName("footerLabel")
        status_bar.addPermanentWidget(footer_label)
        self.setStatusBar(status_bar)
        self.statusBar().showMessage("Ready to generate an NIA DTR form")

    def _build_options(self):
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll_area.setFrameShape(QFrame.Shape.NoFrame)

        panel = QFrame()
        panel.setObjectName("optionsPanel")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(16)

        heading = QLabel("DOCUMENT SETTINGS")
        heading.setObjectName("panelTitle")
        layout.addWidget(heading)

        source_group = QGroupBox("1   Attendance CSV File")
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

        period_group = QGroupBox("2   Pay Period and Time Format")
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

        employee_group = QGroupBox("3   Employees")
        employee_form = QGridLayout(employee_group)
        employee_form.setContentsMargins(0, 0, 0, 0)
        employee_form.setVerticalSpacing(12)
        self.employee_mode_combo = QComboBox()
        self.employee_mode_combo.addItems([
            "All employees", "Selected employee", "All employees except"
        ])
        self.employee_mode_combo.currentIndexChanged.connect(self._update_employee_selector)
        self.employee_combo = MultiSelectComboBox()
        self.employee_combo.setEnabled(False)
        employee_form.addWidget(self.employee_mode_combo, 0, 0, 1, 2)
        employee_form.addWidget(self.employee_combo, 1, 0, 1, 2)
        layout.addWidget(employee_group)

        output_group = QGroupBox("4   Output File")
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

        self.print_button = QPushButton("GENERATE DTR")
        self.print_button.setObjectName("primaryButton")
        self.print_button.clicked.connect(self.generate)
        layout.addWidget(self.print_button)
        self.open_button = QPushButton("Open output folder")
        self.open_button.setObjectName("secondaryButton")
        self.open_button.clicked.connect(self.open_output_folder)
        layout.addWidget(self.open_button)
        layout.addStretch()
        scroll_area.setWidget(panel)
        return scroll_area

    def _apply_styles(self):
        arrow_path = os.path.join(BASE_DIR, "img", "combobox_arrow.svg").replace("\\", "/")
        self.setStyleSheet(
            """
            QWidget#root, QMainWindow { background: #f5f7f6; }
            QLabel#title { color: #0d5557; font-size: 27px; font-weight: 700; }
            QLabel#subtitle, QLabel#hint { color: #71807f; font-size: 11px; }
            QLabel#headerLogo { min-width: 42px; }
            QLabel#headerVersion { color: #52706d; font-size: 10px; font-weight: 700; }
            QLabel#footerLabel { color: #52706d; font-size: 11px; background: transparent; border: none; }
            QLabel#panelTitle { color: #0e5c5e; font-size: 13px; font-weight: 800; letter-spacing: 1px; }
            QLabel#zoomLabel { color: #516c6b; min-width: 42px; qproperty-alignment: AlignCenter; }
            QFrame#optionsPanel, QFrame#previewPanel { background: #ffffff; border: 1px solid #dce5e3; border-radius: 10px; }
            QWidget#previewToolbar { background: #ffffff; border-bottom: 1px solid #e2e9e7; }
            QGroupBox { color: #0e5c5e; background: #fbfcfc; font-weight: 700; border: 1px solid #e0e8e6; border-radius: 9px; margin-top: 12px; padding: 22px 12px 12px; }
            QGroupBox::title { subcontrol-origin: margin; left: 12px; padding: 0 5px; }
            QLineEdit, QSpinBox { background: #ffffff; border: 1px solid #c9d7d4; border-radius: 5px; padding: 8px; color: #263b3a; min-height: 18px; }
            QLineEdit:focus, QSpinBox:focus { border: 1px solid #118184; }
            QComboBox { background: #ffffff; border: 1px solid #bfd1ce; border-radius: 7px; padding: 9px 36px 9px 11px; color: #23413f; min-height: 18px; }
            QComboBox:hover { border-color: #76aaa5; background: #fcfefe; }
            QComboBox:focus { border: 2px solid #118184; padding: 8px 35px 8px 10px; }
            QComboBox:disabled { color: #91a3a0; background: #eef3f2; border-color: #d8e2e0; }
            QComboBox::drop-down { width: 30px; border: 0; border-left: 1px solid #d7e3e0; border-top-right-radius: 7px; border-bottom-right-radius: 7px; background: #f1f7f5; }
            QComboBox::drop-down:hover { background: #e2f0ec; }
            QComboBox::down-arrow { image: url(__COMBO_ARROW__); width: 10px; height: 6px; }
            QComboBox QAbstractItemView { background: #ffffff; border: 1px solid #b8cfcb; border-radius: 6px; padding: 5px; color: #23413f; selection-background-color: #d9eeea; selection-color: #0b5e60; outline: 0; }
            QComboBox QAbstractItemView::item { min-height: 30px; padding: 6px 9px; border-radius: 4px; }
            QComboBox QAbstractItemView::item:hover { background: #edf7f5; }
            QScrollBar:vertical { background: #f1f6f5; width: 10px; margin: 2px 2px 2px 0; border-radius: 5px; }
            QScrollBar::handle:vertical { background: #9fc5c0; min-height: 34px; border-radius: 5px; }
            QScrollBar::handle:vertical:hover { background: #579b96; }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; background: transparent; }
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: transparent; }
            QScrollBar:horizontal { background: #f1f6f5; height: 10px; margin: 0 2px 2px 2px; border-radius: 5px; }
            QScrollBar::handle:horizontal { background: #9fc5c0; min-width: 34px; border-radius: 5px; }
            QScrollBar::handle:horizontal:hover { background: #579b96; }
            QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0; background: transparent; }
            QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal { background: transparent; }
            QPushButton, QToolButton { border-radius: 5px; padding: 9px 13px; font-weight: 700; }
            QToolButton { background: #ffffff; color: #365b5a; border: 1px solid #e0e8e6; padding: 7px 10px; }
            QToolButton:hover { background: #e9f3f1; }
            QPushButton#primaryButton { background: #087578; color: white; min-height: 45px; letter-spacing: 1px; }
            QPushButton#primaryButton:hover { background: #075e61; }
            QPushButton#secondaryButton { background: #e7f2f0; color: #126163; }
            QPushButton#secondaryButton:hover { background: #d6e9e5; }
            QSplitter::handle { background: #dbe6e3; width: 8px; }
            QScrollArea { background: transparent; }
            QStatusBar { color: #52706d; background: transparent; border: none; }
            QStatusBar::item { border: none; background: transparent; }
            """.replace("__COMBO_ARROW__", arrow_path)
        )

    def browse_csv(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Select attendance CSV file", "", "CSV files (*.csv);;All files (*.*)"
        )
        if path:
            self.csv_edit.setText(path)
            self.file_hint.setText(f"Selected: {os.path.basename(path)}")
            try:
                employee_names = sorted(NIADTRProcessor().load_and_group(path))
            except Exception as error:
                self.employee_combo.set_items([])
                self.file_hint.setText(f"Could not read CSV: {error}")
                self.statusBar().showMessage("CSV file could not be read")
                return
            self.employee_combo.set_items(employee_names)
            self._update_employee_selector()
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
        employee_mode = ("all", "selected", "except")[self.employee_mode_combo.currentIndex()]
        employee_names = self.employee_combo.selected_items()
        if employee_mode != "all" and not employee_names:
            raise ValueError("Select at least one employee for the chosen employee scope.")
        return (csv_path, self.year_spin.value(), self.month_combo.currentIndex() + 1,
            self.half_combo.currentIndex() + 1, filename,
            "24" if self.time_combo.currentIndex() == 0 else "12",
            employee_mode, employee_names)

    def _update_employee_selector(self):
        enabled = self.employee_mode_combo.currentIndex() != 0
        if not enabled:
            self.employee_combo.clear_selection()
        self.employee_combo.setEnabled(enabled)

    def generate(self):
        try:
            values = self._validated_values()
        except ValueError as error:
            QMessageBox.warning(self, "Check form settings", str(error))
            return

        self.print_button.setEnabled(False)
        self.statusBar().showMessage("Generating printable PDF...")
        self.worker_thread = QThread(self)
        self.worker = GenerationWorker(*values, 3)
        self.worker.moveToThread(self.worker_thread)
        self.worker_thread.started.connect(self.worker.run)
        self.worker.finished.connect(self.on_success)
        self.worker.failed.connect(self.on_failure)
        self.worker.finished.connect(self.worker_thread.quit)
        self.worker.failed.connect(self.worker_thread.quit)
        self.worker_thread.finished.connect(self.worker.deleteLater)
        self.worker_thread.finished.connect(self.worker_thread.deleteLater)
        self.worker_thread.start()

    def on_success(self, path, count, period):
        self.print_button.setEnabled(True)
        self.statusBar().showMessage(f"Generated printable PDF for {count} personnel records")
        self.preview.load(path)
        QMessageBox.information(
            self, "DTR generated",
            f"Printable DTR created successfully for {period}.\n\nSaved to:\n{path}"
        )

    def on_failure(self, message, detail):
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
    app.setStyle(QStyleFactory.create("Windows"))
    window = DTRApp()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
