"""
Generate NIA (National Irrigation Administration) Regional Office No. VI
format Daily Time Record PDFs per personnel, for a selected half-month
period, from a raw attendance scan log CSV using the NIADTRProcessor.

Reuses the same CSV-reading and AM/PM In/Out slot-classification logic as
the SimpleDTRProcessor, but lays the page out to match the official NIA DTR form:
  - Half-month period header, e.g. "2026-07-16 -- 2026-07-31"
  - Every calendar day in that period is listed as a row, including days
    with no scans (blank row) and weekends -- not only days with scans
  - AM In/Out and PM In/Out are filled in from the attendance scans
  - Tardiness/Undertime columns are left blank for manual entry
  - Office hours note and a certification/signature block at the bottom

Usage:
    python generate_nia_dtr.py <input_csv> <year> <month> <half> [output_filename.pdf]
        half: "1" for days 1-15, "2" for day 16 through end of month
"""

import sys
import os
import calendar
from datetime import date
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.units import inch
from reportlab.platypus import (
    SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak, Image
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT

from generate_dtr import DTRProcessor


DAY_ABBR = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]

# Logo files, expected inside an "img" folder next to this script:
#   img/nia_logo.png           -> shown on the LEFT of the header
#   img/bagong_pilipinas.png   -> shown on the RIGHT of the header
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
IMG_DIR = os.path.join(SCRIPT_DIR, "img")
NIA_LOGO_PATH = os.path.join(IMG_DIR, "nia_logo.png")
OFFICE_PRESIDENT_LOGO_PATH = os.path.join(IMG_DIR, "office_president.png")
BAGONG_PILIPINAS_LOGO_PATH = os.path.join(IMG_DIR, "bagong_pilipinas.png")

LOGO_SIZE = 1 * inch  # both logos are drawn at this width/height


class NIADTRProcessor(DTRProcessor):
    """
    Concrete implementation of DTRProcessor that generates NIA-format DTR PDFs
    with one page per person per period, showing the official NIA DTR layout
    with all calendar dates in the period, including weekends.
    """

    @staticmethod
    def compute_slots_for_date(scans: list) -> dict:
        """
        Override of base class method to return "00:00" for empty slots (only if date has scans).
        Given a list of scan datetimes for a single date (possibly empty),
        classify them into AM In/Out and PM In/Out slots and return
        formatted time strings.
        
        Selection logic:
            - Keep the EARLIEST AM scan as AM In and the LATEST noon scan as AM Out
            - Treat all scans from 12:31 PM onward as one PM pool
            - Keep the EARLIEST PM scan as PM In and the LATEST as PM Out
              
        Args:
            scans: List of datetime objects for a single date
            
        Returns:
            Dictionary with keys: "am_in", "am_out", "pm_in", "pm_out"
            - If no scans on this date: return empty strings
            - If scans exist: return actual times or "00:00" for missing slots
        """
        if not scans:
            # No scans on this date - return empty strings (blank row)
            return {"am_in": "", "am_out": "", "pm_in": "", "pm_out": ""}

        # Date has at least one scan - process the slots
        am_in, am_out, pm_in, pm_out, am_count, pm_count = (
            DTRProcessor._select_slot_datetimes(scans)
        )

        # Format times: show actual time if available, "00:00" if slot is missing but date has scans
        def fmt(t):
            return t.strftime("%I:%M %p").lstrip("0") if t else "00:00"

        return {
            "am_in": fmt(am_in),
            "am_out": "00:00" if am_count == 1 else fmt(am_out),
            "pm_in": fmt(pm_in),
            "pm_out": "00:00" if pm_count == 1 else fmt(pm_out),
        }

    @staticmethod
    def _load_logo(path, size=LOGO_SIZE):
        """
        Return a reportlab Image flowable for the given logo path, sized to a
        fixed square (keeps the header layout consistent even if the source
        PNGs have different resolutions). Returns None if the file is missing
        so a missing/renamed logo doesn't crash the whole PDF generation --
        that header cell is just left blank instead.
        """
        if not os.path.isfile(path):
            return None
        try:
            img = Image(path, width=size, height=size)
            img.hAlign = "CENTER"
            return img
        except Exception:
            return None

    @staticmethod
    def get_period_dates(year: int, month: int, half: int) -> list:
        """Return the list of date objects for the selected half-month period.

        half=1 -> days 1-15
        half=2 -> day 16 through the last day of the month
        """
        last_day = calendar.monthrange(year, month)[1]
        if half == 1:
            start, end = 1, 15
        else:
            start, end = 16, last_day
        return [date(year, month, d) for d in range(start, end + 1)]

    @staticmethod
    def period_label(period_dates: list) -> str:
        """Return a formatted label for the period."""
        start, end = period_dates[0], period_dates[-1]
        return f"{start.strftime('%Y-%m-%d')} -- {end.strftime('%Y-%m-%d')}"

    def build_person_story(self, name: str, period_dates: list, dates_scans: dict,
                            period_lbl: str, date_generated: str, styles) -> list:
        """Build the flowable content for one person's NIA-format DTR page."""

        agency_style = ParagraphStyle(
            "NIAAgency", parent=styles["Normal"], fontSize=10, alignment=TA_CENTER,
            leading=13,
        )
        agency_bold_style = ParagraphStyle(
            "NIAAgencyBold", parent=agency_style, fontName="Helvetica-Bold", fontSize=11,
        )
        title_style = ParagraphStyle(
            "NIATitle", parent=styles["Normal"], fontSize=13, alignment=TA_CENTER,
            fontName="Helvetica-Bold", spaceBefore=8, spaceAfter=10,
        )
        info_style = ParagraphStyle(
            "NIAInfo", parent=styles["Normal"], fontSize=9, alignment=TA_LEFT, leading=13,
        )
        cert_style = ParagraphStyle(
            "NIACert", parent=styles["Normal"], fontSize=8.5, alignment=TA_LEFT, leading=12,
            spaceBefore=16,
        )
        sig_style = ParagraphStyle(
            "NIASig", parent=styles["Normal"], fontSize=9, alignment=TA_CENTER,
        )

        story = []

        # --- Agency header: NIA logo (left) | agency text (center) | Bagong Pilipinas logo (right) ---
        agency_text_cell = [
            Paragraph("Republic of the Philippines", agency_style),
            Paragraph("OFFICE OF THE PRESIDENT", agency_style),
            Paragraph("NATIONAL IRRIGATION ADMINISTRATION", agency_bold_style),
            Paragraph("REGIONAL OFFICE NO. VI (WESTERN VISAYAS)", agency_style),
        ]

        nia_logo = self._load_logo(NIA_LOGO_PATH)
        office_president_logo = self._load_logo(OFFICE_PRESIDENT_LOGO_PATH)
        bagong_pilipinas_logo = self._load_logo(BAGONG_PILIPINAS_LOGO_PATH)

        # Put NIA and Office of the President logos together
        left_logos = Table(
            [[
                office_president_logo if office_president_logo else "",
                nia_logo if nia_logo else "",
            ]],
            colWidths=[0.85 * inch, 0.85 * inch]
        )

        left_logos.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ("RIGHTPADDING", (0, 0), (-1, -1), 0),
            ("TOPPADDING", (0, 0), (-1, -1), 0),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
        ]))

        header_data = [[
            left_logos,
            agency_text_cell,
            bagong_pilipinas_logo if bagong_pilipinas_logo else "",
        ]]
        header_table = Table(header_data, colWidths=[1.0 * inch, 5.3 * inch, 1.0 * inch])
        header_table.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("ALIGN", (0, 0), (0, 0), "CENTER"),
            ("ALIGN", (1, 0), (1, 0), "CENTER"),
            ("ALIGN", (2, 0), (2, 0), "CENTER"),
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ("RIGHTPADDING", (0, 0), (-1, -1), 0),
            ("TOPPADDING", (0, 0), (-1, -1), 0),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
        ]))
        story.append(header_table)
        story.append(Spacer(1, 6))

        # --- Title + period ---
        story.append(Paragraph(f"Daily Time Record &nbsp;&nbsp;&nbsp; {period_lbl}", title_style))

        # --- Name / Date Generated / Office Hours row ---
        info_data = [[
            Paragraph(f"<b>{name}</b>", info_style),
            Paragraph(f"<b>Date Generated:</b><br/>{date_generated}", info_style),
            Paragraph(
                "<b>OFFICE HOURS</b><br/>"
                "MONDAY: 8:00 AM to 5:00 PM<br/>"
                "TUESDAY - FRIDAY: 8:00-8:30 AM to 5:00-5:30 PM",
                info_style,
            ),
        ]]
        info_table = Table(info_data, colWidths=[2.3 * inch, 1.8 * inch, 3.2 * inch])
        info_table.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LINEBELOW", (0, 0), (-1, 0), 0.75, colors.HexColor("#888888")),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
        ]))
        story.append(info_table)
        story.append(Spacer(1, 6))

        header_cell_style = ParagraphStyle(
            "NIAHeaderCell", parent=styles["Normal"], fontSize=8, alignment=TA_CENTER,
            fontName="Helvetica-Bold", textColor=colors.white, leading=9,
        )

        # --- Main table: Date | Day | AM In/Out | PM In/Out | Tardiness/Undertime In/Out | Remarks ---
        header_row1 = [
            "Date", "Day", "AM", "", "PM", "",
            Paragraph("TARDINESS/<br/>UNDERTIME", header_cell_style), "", "Remarks",
        ]
        header_row2 = ["", "", "IN", "OUT", "IN", "OUT", "IN", "OUT", ""]

        table_data = [header_row1, header_row2]
        for i, d in enumerate(period_dates, start=1):
            day_label = f"{i} {DAY_ABBR[d.weekday()]}"
            slots = self.compute_slots_for_date(dates_scans.get(d, []))
            table_data.append([
                d.strftime("%m/%d/%Y"),
                day_label,
                slots["am_in"], slots["am_out"],
                slots["pm_in"], slots["pm_out"],
                "", "",  # Tardiness/Undertime In, Out -- left blank for manual entry
                "",      # Remarks
            ])

        col_widths = [
            0.75 * inch, 0.55 * inch,   # Date, Day
            0.62 * inch, 0.62 * inch,   # AM In, Out
            0.62 * inch, 0.62 * inch,   # PM In, Out
            0.55 * inch, 0.55 * inch,   # Tardiness/Undertime In, Out
            2.62 * inch,                # Remarks
        ]

        table = Table(table_data, colWidths=col_widths, repeatRows=2)
        style_cmds = [
            ("SPAN", (0, 0), (0, 1)),   # Date
            ("SPAN", (1, 0), (1, 1)),   # Day
            ("SPAN", (2, 0), (3, 0)),   # AM
            ("SPAN", (4, 0), (5, 0)),   # PM
            ("SPAN", (6, 0), (7, 0)),   # TARDINESS/UNDERTIME
            ("SPAN", (8, 0), (8, 1)),   # Remarks
            ("BACKGROUND", (0, 0), (-1, 1), colors.HexColor("#2c3e50")),
            ("TEXTCOLOR", (0, 0), (-1, 1), colors.white),
            ("FONTNAME", (0, 0), (-1, 1), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, 1), 8),
            ("FONTSIZE", (0, 2), (-1, -1), 8.5),
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#999999")),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ]
        # Shade weekend rows lightly, like the blank form's ruled rows
        for i, d in enumerate(period_dates, start=2):
            if d.weekday() >= 5:  # Sat/Sun
                style_cmds.append(("BACKGROUND", (0, i), (-1, i), colors.HexColor("#eef0f2")))
        table.setStyle(TableStyle(style_cmds))
        story.append(table)

        # --- Certification statement ---
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
            fontSize=11,
            fontName='Helvetica-Bold',
            alignment=TA_CENTER,
        )
        
        sig_data = [
            [Paragraph("<b>Jelyn Largo</b>", name_style), Paragraph("<b>Jessa A. Resol</b>", name_style)],
            ["_______________________________", "_______________________________"],
            ["Prepared By", "Verified By (Supervisor)"],
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

    def build_combined_pdf(self, grouped: dict, period_dates: list, output_path: str) -> list:
        """
        Build one PDF with one NIA-format page per person, for the given
        period. `grouped` is the {name: {date: [scans]}} dict returned by
        load_and_group. Only dates that fall inside period_dates are used;
        days with no scans still get a row.
        """
        pdf_title = os.path.splitext(os.path.basename(output_path))[0]
        doc = SimpleDocTemplate(
            output_path,
            pagesize=letter,
            topMargin=0.5 * inch,
            bottomMargin=0.5 * inch,
            leftMargin=0.6 * inch,
            rightMargin=0.6 * inch,
            title=pdf_title,
        )
        styles = getSampleStyleSheet()
        lbl = self.period_label(period_dates)
        date_generated = date.today().strftime("%-d %b %Y") if os.name != "nt" else date.today().strftime("%#d %b %Y")

        full_story = []
        names = sorted(grouped.keys())
        for i, name in enumerate(names):
            dates_scans = grouped[name]
            full_story.extend(
                self.build_person_story(name, period_dates, dates_scans, lbl, date_generated, styles)
            )
            if i < len(names) - 1:
                full_story.append(PageBreak())

        doc.build(full_story)
        return names

    def generate(self, csv_path: str, year: int, month: int, half: int,
                 output_filename: str = "NIA_DTR_combined.pdf"):
        """
        Generate an NIA-format DTR PDF from a CSV file for a specific half-month period.
        
        Args:
            csv_path: Path to the input CSV file
            year: Year (e.g. 2026)
            month: Month (1-12)
            half: Half-month period (1 for days 1-15, 2 for days 16-end of month)
            output_filename: Output PDF filename (will be saved to 'output' directory)
        """
        filename = os.path.basename(output_filename)
        if not filename.lower().endswith(".pdf"):
            filename += ".pdf"

        output_dir = "output"
        os.makedirs(output_dir, exist_ok=True)
        output_path = os.path.join(output_dir, filename)

        grouped = self.load_and_group(csv_path)
        period_dates = self.get_period_dates(year, month, half)
        names = self.build_combined_pdf(grouped, period_dates, output_path)

        print(f"Generated: {output_path}")
        print(f"Done. {len(names)} personnel included for period {self.period_label(period_dates)}.")
        
        return output_path


def main():
    if len(sys.argv) < 5:
        print("Usage: python generate_nia_dtr.py <input_csv> <year> <month> <half> [output_filename.pdf]")
        print('       half: "1" for days 1-15, "2" for day 16-end of month')
        sys.exit(1)

    csv_path = sys.argv[1]
    year = int(sys.argv[2])
    month = int(sys.argv[3])
    half = int(sys.argv[4])
    filename = sys.argv[5] if len(sys.argv) > 5 else "NIA_DTR_combined.pdf"

    processor = NIADTRProcessor()
    processor.generate(csv_path, year, month, half, filename)


if __name__ == "__main__":
    main()