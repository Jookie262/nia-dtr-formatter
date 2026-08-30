"""
Generate a Raw Daily Time Record (DTR) PDF per personnel from raw attendance
data CSV using the RawDTRProcessor.

This format simply lists timestamp and name without classification into AM/PM
slots. It's useful for quick capture and PDF generation without formatting requirements.

Expected CSV columns: Timestamp, Name (and optionally: Index, ID, Details)
  - Timestamp format: D/M/YYYY H:MM  (e.g. 13/8/2026 22:09)
  - Each row is displayed as-is in the table, grouped by person

Output: a single PDF with one page per person (alphabetical by name),
saved to the filename you specify.

Usage:
    python generate_raw_dtr.py <input_csv> [output_filename.pdf]
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


class RawDTRProcessor(DTRProcessor):
    """
    Concrete implementation of DTRProcessor that generates raw DTR PDFs
    with one page per person, showing a table of timestamps and names.
    No AM/PM slot classification is performed.
    """

    def build_person_story(self, name: str, timestamps: list, styles) -> list:
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
        date_header_style = ParagraphStyle(
            "DateHeader", parent=styles["Normal"], fontSize=10, alignment=TA_CENTER,
            fontName="Helvetica-Bold", textColor=colors.HexColor("#ffffff")
        )

        story = []
        story.append(Paragraph("Panay River Basin Integrated Development Project", header_style))
        story.append(Paragraph("Daily Time Record", title_style))
        story.append(Paragraph(f"<b>Name:</b> {name}", name_style))

        # Group timestamps by date
        from collections import defaultdict
        date_groups = defaultdict(list)
        for ts in timestamps:
            date_str = ts.strftime("%d/%m/%Y")
            time_str = ts.strftime("%H:%M")
            date_groups[date_str].append(time_str)
        
        # Create individual date tables
        date_tables = []
        for date_str in sorted(date_groups.keys()):
            times = sorted(date_groups[date_str])
            
            # Create a small table for this date
            date_table_data = [[Paragraph(f"<b>{date_str}</b>", date_header_style)]]
            for time_str in times:
                date_table_data.append([time_str])
            
            date_table = Table(date_table_data, colWidths=[1.2 * inch])
            date_table.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2c3e50")),
                ("FONTSIZE", (0, 0), (-1, -1), 8),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cccccc")),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]))
            date_tables.append(date_table)
        
        # Arrange tables in 4 columns
        num_cols = 4
        col_width = 1.4 * inch
        layout_data = []
        
        for i in range(0, len(date_tables), num_cols):
            row = date_tables[i:i+num_cols]
            # Pad with empty cells if needed
            while len(row) < num_cols:
                row.append("")
            layout_data.append(row)
        
        if layout_data:
            layout_table = Table(layout_data, colWidths=[col_width] * num_cols)
            layout_table.setStyle(TableStyle([
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ("LEFTPADDING", (0, 0), (-1, -1), 3),
                ("RIGHTPADDING", (0, 0), (-1, -1), 3),
            ]))
            story.append(layout_table)

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
        sig_name_style = ParagraphStyle(
            'NameStyle',
            parent=styles['Normal'],
            fontSize=12,
            fontName='Helvetica-Bold',
            alignment=TA_CENTER,
        )
        
        sig_data = [
            [Paragraph("<b>Jelyn Largo</b>", sig_name_style), Paragraph("<b>Jessa A. Resol</b>", sig_name_style)],
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
            scans = grouped[name]
            # Sort all scans for this person chronologically
            all_timestamps = sorted(sum(scans.values(), []))
            full_story.extend(self.build_person_story(name, all_timestamps, styles))
            if i < len(names) - 1:
                full_story.append(PageBreak())

        doc.build(full_story)
        return names

    def generate(self, csv_path: str, output_filename: str = "raw_dtr_format.pdf"):
        """
        Generate a raw DTR PDF from a CSV file.
        
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
        print("Usage: python generate_raw_dtr.py <input_csv> [output_filename.pdf]")
        sys.exit(1)

    csv_path = sys.argv[1]
    filename = sys.argv[2] if len(sys.argv) > 2 else "raw_dtr_format.pdf"

    processor = RawDTRProcessor()
    processor.generate(csv_path, filename)


if __name__ == "__main__":
    main()
