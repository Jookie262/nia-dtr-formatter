"""
Generate a Daily Time Record (DTR) PDF per personnel from a raw attendance
scan log CSV using the SimpleDTRProcessor.

Expected CSV columns: Index, Timestamp, ID, Name, Details
  - Timestamp format: D/M/YYYY H:MM  (e.g. 13/8/2026 22:09)
  - Each scan is classified into a slot by its time of day (not by
    position/order), so employees with only 1, 2, or 3 scans in a day
    are handled correctly:
        AM In  : 12:00 AM - 11:59 AM
        AM Out : 12:00 PM - 12:29 PM
        PM In  : 12:30 PM - 1:00  PM
        PM Out : 1:01 PM  - 11:59 PM
    If multiple scans fall in the same slot on a day with 5 or more total
    scans, the latest scan in that slot is kept. On days with fewer than
    5 scans, the earliest scan is kept for "In" slots and the latest for
    "Out" slots (standard behavior).

Output: a single PDF with one page per person (alphabetical by name),
saved to the filename you specify.

Usage:
    python generate_simple_dtr.py <input_csv> [output_filename.pdf]
"""

import sys
import os
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER

from generate_dtr import DTRProcessor


class SimpleDTRProcessor(DTRProcessor):
    """
    Concrete implementation of DTRProcessor that generates simple DTR PDFs
    with one page per person, showing a table of dates and their time slots.
    """

    def build_person_story(self, name: str, rows: list, styles) -> list:
        """Build the flowable content (title, table, notes, signature) for one person."""
        header_style = ParagraphStyle(
            "DTRHeader", parent=styles["Normal"], fontSize=12, alignment=TA_CENTER,
            fontName="Helvetica-Bold", spaceAfter=4,
        )
        title_style = ParagraphStyle(
            "DTRTitle", parent=styles["Title"], fontSize=16, alignment=TA_CENTER
        )
        subtitle_style = ParagraphStyle(
            "DTRSubtitle", parent=styles["Normal"], fontSize=11, alignment=TA_CENTER,
            textColor=colors.HexColor("#444444"), spaceAfter=6,
        )
        name_style = ParagraphStyle(
            "DTRName", parent=styles["Normal"], fontSize=12, alignment=TA_CENTER,
            spaceAfter=14,
        )

        story = []
        story.append(Paragraph("Panay River Basin Integrated Development Project", header_style))
        story.append(Paragraph("Daily Time Record", title_style))
        story.append(Paragraph("(Generated from biometric data)", subtitle_style))
        story.append(Paragraph(f"<b>Name:</b> {name}", name_style))

        table_data = [["Date", "AM In", "AM Out", "PM In", "PM Out"]]

        for r in rows:
            table_data.append([r["date"], r["am_in"], r["am_out"], r["pm_in"], r["pm_out"]])

        col_widths = [1.3 * inch, 1.1 * inch, 1.1 * inch, 1.1 * inch, 1.1 * inch]
        table = Table(table_data, colWidths=col_widths, repeatRows=1)
        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2c3e50")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cccccc")),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f5f6f7")]),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ]))
        story.append(table)

        # --- Certification statement ---
        story.append(Spacer(1, 20))
        cert_style = ParagraphStyle(
            "Certification", parent=styles["Normal"], fontSize=9, alignment=TA_CENTER,
            spaceAfter=10
        )
        story.append(Paragraph(
            "I hereby certify on my honor that the above statement is true and correct report of the "
            "work performed, record of which was made daily at the time of arrival and departure from office.",
            cert_style,
        ))

        # --- Signature block ---
        story.append(Spacer(1, 30))
        
        # Create a style for bold, larger names
        name_style = ParagraphStyle(
            'NameStyle',
            parent=styles['Normal'],
            fontSize=12,
            fontName='Helvetica-Bold',
            alignment=TA_CENTER,
        )
        
        sig_data = [
            [Paragraph("<b>Jelyn Largo</b>", name_style), Paragraph("<b>Jessa A. Resol</b>", name_style)],
            ["_______________________________", "_______________________________"],
            ["Prepared by", "Verified by"],
        ]
        sig_table = Table(sig_data, colWidths=[3.65 * inch, 3.65 * inch])
        sig_table.setStyle(TableStyle([
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("FONTSIZE", (0, 1), (-1, 1), 9),  # signature lines
            ("FONTSIZE", (0, 2), (-1, 2), 9),  # labels
            ("TOPPADDING", (0, 0), (-1, 0), 0),
            ("TOPPADDING", (0, 1), (-1, 1), 0),
            ("TOPPADDING", (0, 2), (-1, 2), 0),
            ("BOTTOMPADDING", (0, 0), (-1, 0), 0),
            ("BOTTOMPADDING", (0, 1), (-1, 1), 0),
        ]))
        story.append(sig_table)

        return story

    def build_combined_pdf(self, grouped: dict, output_path: str) -> list:
        """Build one PDF with one page (or more) per person, in a single file."""
        pdf_title = os.path.splitext(os.path.basename(output_path))[0]
        doc = SimpleDocTemplate(
            output_path,
            pagesize=letter,
            topMargin=0.6 * inch,
            bottomMargin=0.6 * inch,
            leftMargin=0.6 * inch,
            rightMargin=0.6 * inch,
            title=pdf_title,
        )
        styles = getSampleStyleSheet()

        full_story = []
        names = sorted(grouped.keys())
        for i, name in enumerate(names):
            dates = grouped[name]
            rows = [self.compute_row(date, scans) for date, scans in sorted(dates.items())]
            full_story.extend(self.build_person_story(name, rows, styles))
            if i < len(names) - 1:
                full_story.append(PageBreak())

        doc.build(full_story)
        return names

    def generate(self, csv_path: str, output_filename: str = "DTR_combined.pdf"):
        """
        Generate a simple DTR PDF from a CSV file.
        
        Args:
            csv_path: Path to the input CSV file
            output_filename: Output PDF filename (will be saved to 'output' directory)
        """
        filename = os.path.basename(output_filename)  # ignore any path the user typed
        if not filename.lower().endswith(".pdf"):
            filename += ".pdf"

        output_dir = "output"
        os.makedirs(output_dir, exist_ok=True)  # creates it if missing, reuses it if it exists
        output_path = os.path.join(output_dir, filename)

        grouped = self.load_and_group(csv_path)
        names = self.build_combined_pdf(grouped, output_path)

        print(f"Generated: {output_path}")
        print(f"Done. {len(names)} personnel included in one PDF ({len(names)} page(s)).")
        
        return output_path


def compute_row(date, scans):
    """
    Deprecated: Use DTRProcessor.compute_row() instead.
    Kept for backwards compatibility.
    """
    return DTRProcessor.compute_row(date, scans)


def main():
    if len(sys.argv) < 2:
        print("Usage: python generate_simple_dtr.py <input_csv> [output_filename.pdf]")
        sys.exit(1)

    csv_path = sys.argv[1]
    filename = sys.argv[2] if len(sys.argv) > 2 else "DTR_combined.pdf"

    processor = SimpleDTRProcessor()
    processor.generate(csv_path, filename)


if __name__ == "__main__":
    main()