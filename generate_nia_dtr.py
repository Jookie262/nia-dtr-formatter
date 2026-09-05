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
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    BaseDocTemplate, Frame, PageTemplate, SimpleDocTemplate, Table, TableStyle,
    Paragraph, Spacer, PageBreak, FrameBreak, Image
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT

from generate_dtr import DTRProcessor


DAY_ABBR = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]

# Logo files, expected inside an "img" folder next to this script:
#   img/nia_logo.png           -> shown on the LEFT of the header
#   img/bagong_pilipinas.png   -> shown on the RIGHT of the header
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
APP_DIR = os.path.dirname(sys.executable) if getattr(sys, "frozen", False) else SCRIPT_DIR
IMG_DIR = os.path.join(SCRIPT_DIR, "img")
FONT_DIR = os.path.join(SCRIPT_DIR, "font")
NIA_LOGO_PATH = os.path.join(IMG_DIR, "nia_logo.png")
OFFICE_PRESIDENT_LOGO_PATH = os.path.join(IMG_DIR, "office_president.png")
BAGONG_PILIPINAS_LOGO_PATH = os.path.join(IMG_DIR, "bagong_pilipinas.png")

LOGO_SIZE = 0.55 * inch  # logos are drawn at this width/height
NIA_PAGE_WIDTH = 8.5 * inch
NIA_FORM_HEIGHT = 6.5 * inch
NIA_SHEET_HEIGHT = 13 * inch
BORDER_HORIZONTAL_INSET = 0.40 * inch
BORDER_VERTICAL_INSET = 0.18 * inch
CUT_LINE_VERTICAL_OFFSET = -0.05 * inch
FOOTER_BOTTOM_PADDING = 0.05 * inch


def register_header_fonts():
    """Register the requested header fonts and return their ReportLab names."""
    cambria_path = os.path.join(FONT_DIR, "Cambria.ttf")
    cambria_bold_path = os.path.join(FONT_DIR, "Cambria-Bold.ttf")
    if not os.path.isfile(cambria_bold_path):
        cambria_bold_path = os.path.join(os.environ["WINDIR"], "Fonts", "cambriab.ttf")
    pdfmetrics.registerFont(
        TTFont("NIA-Cambria", cambria_path)
    )
    pdfmetrics.registerFont(
        TTFont("NIA-Cambria-Bold", cambria_bold_path)
    )

    trajan_candidates = [
        os.path.join(FONT_DIR, "TrajanPro-Regular.ttf"),
        os.path.join(FONT_DIR, "TrajanPro-Regular.otf"),
    ]
    trajan_bold_candidates = [
        os.path.join(FONT_DIR, "TrajanPro-Bold.ttf"),
        os.path.join(FONT_DIR, "TrajanPro-Bold.otf"),
    ]
    trajan_path = next((path for path in trajan_candidates if os.path.isfile(path)), None)
    trajan_bold_path = next(
        (path for path in trajan_bold_candidates if os.path.isfile(path)), None
    )
    if trajan_path:
        pdfmetrics.registerFont(TTFont("NIA-TrajanPro", trajan_path))
        trajan_font = "NIA-TrajanPro"
        if trajan_bold_path:
            try:
                pdfmetrics.registerFont(TTFont("NIA-TrajanPro-Bold", trajan_bold_path))
                trajan_bold_font = "NIA-TrajanPro-Bold"
            except Exception:
                trajan_bold_font = "Times-Bold"
        else:
            trajan_bold_font = trajan_font
    else:
        trajan_font = "Times-Roman"
        trajan_bold_font = "Times-Bold"
    return "NIA-Cambria", "NIA-Cambria-Bold", trajan_font, trajan_bold_font


CAMBRIA_FONT, CAMBRIA_BOLD_FONT, TRAJAN_FONT, TRAJAN_BOLD_FONT = register_header_fonts()


class NIADTRProcessor(DTRProcessor):
    """
    Concrete implementation of DTRProcessor that generates NIA-format DTR PDFs
    with one page per person per period, showing the official NIA DTR layout
    with all calendar dates in the period, including weekends.
    """

    @staticmethod
    def compute_slots_for_date(scans: list, time_format: str = "24") -> dict:
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
            if not t:
                return "00:00"
            return t.strftime("%I:%M %p").lstrip("0") if time_format == "12" else t.strftime("%H:%M")

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
                            period_lbl: str, date_generated: str, styles,
                            time_format: str = "24") -> list:
        """Build the flowable content for one person's NIA-format DTR page."""

        agency_style = ParagraphStyle(
            "NIAAgency", parent=styles["Normal"], fontSize=9.5, alignment=TA_LEFT,
            fontName=CAMBRIA_FONT, leading=12,
        )
        agency_cambria_bold_style = ParagraphStyle(
            "NIAAgencyCambriaBold", parent=agency_style,
            fontName=CAMBRIA_BOLD_FONT
        )
        agency_bold_style = ParagraphStyle(
            "NIAAgencyBold", parent=agency_style, fontName=TRAJAN_FONT, fontSize=9.5
        )
        regional_style = ParagraphStyle(
            "NIARegional", parent=agency_style, fontName=TRAJAN_FONT, fontSize=9.5, 
        )
        title_style = ParagraphStyle(
            "NIATitle", parent=styles["Normal"], fontSize=11, alignment=TA_CENTER,
            fontName="Helvetica-Bold", spaceBefore=3, spaceAfter=3,
        )
        info_style = ParagraphStyle(
            "NIAInfo", parent=styles["Normal"], fontSize=9, alignment=TA_LEFT, leading=13,
        )
        employee_name_style = ParagraphStyle(
            "NIAEmployeeName", parent=info_style, alignment=TA_CENTER,
        )
        date_generated_style = ParagraphStyle(
            "NIADateGenerated", parent=info_style, alignment=TA_CENTER,
        )
        office_hours_style = ParagraphStyle(
            "NIAOfficeHours", parent=info_style, fontSize=7.5, leading=9.5,
        )
        cert_style = ParagraphStyle(
            "NIACert", parent=styles["Normal"], fontSize=8.5, alignment=TA_LEFT,
            fontName="Helvetica-Oblique", leading=12,
            spaceBefore=16,
        )
        sig_style = ParagraphStyle(
            "NIASig", parent=styles["Normal"], fontSize=9, alignment=TA_CENTER,
        )

        story = []

        # --- Agency header: NIA logo (left) | agency text (center) | Bagong Pilipinas logo (right) ---
        agency_text_cell = [
            Spacer(1, 5),
            Paragraph("Republic of the Philippines", agency_cambria_bold_style),
            Paragraph("OFFICE OF THE PRESIDENT", agency_style),
            Paragraph("NATIONAL IRRIGATION ADMINISTRATION", agency_bold_style),
            Paragraph("REGIONAL OFFICE NO. VI (WESTERN VISAYAS)", regional_style),
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
            colWidths=[1 * LOGO_SIZE, 1.2 * LOGO_SIZE]
        )

        left_logos.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ("RIGHTPADDING", (0, 0), (-1, -1), 0),
            ("TOPPADDING", (0, 0), (-1, -1), 0),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
        ]))

        right_logo = Table(
            [[bagong_pilipinas_logo if bagong_pilipinas_logo else ""]],
            colWidths=[1.0 * inch],
        )
        right_logo.setStyle(TableStyle([
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
            right_logo,
        ]]
        header_table = Table(
            header_data,
            colWidths=[2.4 * LOGO_SIZE, 4 * inch, 1.0 * inch],
        )
        header_table.hAlign = "CENTER"
        header_table.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("ALIGN", (0, 0), (0, 0), "CENTER"),
            ("ALIGN", (1, 0), (1, 0), "CENTER"),
            ("ALIGN", (2, 0), (2, 0), "CENTER"),
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ("RIGHTPADDING", (0, 0), (-1, -1), 0),
            ("TOPPADDING", (0, 0), (-1, -1), 10),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
        ]))
        story.append(header_table)

        # --- Title + period ---
        story.append(Paragraph(f"Daily Time Record &nbsp;&nbsp;&nbsp; {period_lbl}", title_style))

        # --- Name / Date Generated / Office Hours row ---
        info_data = [[
            Paragraph(f"<b>{name.upper()}</b>", employee_name_style),
            Paragraph(f"<b>Date Generated:</b><br/>{date_generated}", date_generated_style),
            Paragraph(
                "<b>OFFICE HOURS</b><br/>"
                "MONDAY: 8:00 AM to 5:00 PM<br/>"
                "TUESDAY - FRIDAY: <u>8:00-8:30 AM</u> to <u>5:00-5:30 PM</u>",
                office_hours_style,
            ),
        ]]
        info_fixed_col_widths = [2.8 * inch, 1.8 * inch]
        info_table_width = NIA_PAGE_WIDTH - (2 * BORDER_HORIZONTAL_INSET)
        info_table = Table(
            info_data,
            colWidths=info_fixed_col_widths + [
                info_table_width - sum(info_fixed_col_widths),
            ],
        )
        info_table.hAlign = "CENTER"
        info_table.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("VALIGN", (0, 0), (0, 0), "MIDDLE"),
            ("VALIGN", (1, 0), (1, 0), "MIDDLE"),
            ("LINEABOVE", (0, 0), (-1, 0), 0.5, colors.black),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
            ("TOPPADDING", (0, 0), (-1, -1), 0),
        ]))
        story.append(info_table)

        header_cell_style = ParagraphStyle(
            "NIAHeaderCell", parent=styles["Normal"], fontSize=8, alignment=TA_CENTER,
            fontName="Helvetica-Bold", textColor=colors.black, leading=9,
        )

        # --- Main table: Date | Day | AM In/Out | PM In/Out | Tardiness/Undertime In/Out | Remarks ---
        header_row1 = [
            "Date", "Day", "AM", "", "PM", "",
            "TARDINESS/UNDERTIME", "", "Remarks",
        ]
        header_row2 = ["", "", "IN", "OUT", "IN", "OUT", "IN", "OUT", ""]

        table_data = [header_row1, header_row2]
        for i, d in enumerate(period_dates, start=1):
            day_label = f"{i} {DAY_ABBR[d.weekday()]}"
            slots = self.compute_slots_for_date(dates_scans.get(d, []), time_format)
            table_data.append([
                d.strftime("%m/%d/%Y"),
                day_label,
                slots["am_in"], slots["am_out"],
                slots["pm_in"], slots["pm_out"],
                "", "",  # Tardiness/Undertime In, Out -- left blank for manual entry
                "",      # Remarks
            ])

        fixed_col_widths = [
            0.75 * inch, 0.65 * inch,   # Date, Day
            0.62 * inch, 0.62 * inch,   # AM In, Out
            0.62 * inch, 0.62 * inch,   # PM In, Out
            0.76 * inch, 0.76 * inch,   # Tardiness/Undertime In, Out
        ]
        table_width = NIA_PAGE_WIDTH - (2 * BORDER_HORIZONTAL_INSET)
        col_widths = fixed_col_widths + [
            table_width - sum(fixed_col_widths),  # Remarks
        ]

        table = Table(table_data, colWidths=col_widths, repeatRows=2)
        table.hAlign = "CENTER"
        table_padding = 1.1 if len(period_dates) == 15 else 0.68
        style_cmds = [
            ("SPAN", (0, 0), (0, 1)),   # Date
            ("SPAN", (1, 0), (1, 1)),   # Day
            ("SPAN", (2, 0), (3, 0)),   # AM
            ("SPAN", (4, 0), (5, 0)),   # PM
            ("SPAN", (6, 0), (7, 0)),   # TARDINESS/UNDERTIME
            ("SPAN", (8, 0), (8, 1)),   # Remarks
            ("BACKGROUND", (0, 0), (-1, -1), colors.white),
            ("TEXTCOLOR", (0, 0), (-1, 1), colors.black),
            ("FONTNAME", (0, 0), (-1, 1), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, 1), 8),
            ("FONTSIZE", (0, 2), (-1, -1), 8.5),
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("ALIGN", (1, 0), (1, 1), "CENTER"),
            ("ALIGN", (1, 2), (1, -1), "LEFT"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.black),
            ("TOPPADDING", (0, 0), (-1, -1), table_padding),
            ("BOTTOMPADDING", (0, 0), (-1, -1), table_padding),
        ]
        table.setStyle(TableStyle(style_cmds))
        story.append(table)

        undertime_label_style = ParagraphStyle(
            "NIAUndertimeLabel", parent=styles["Normal"], fontSize=7,
            alignment=TA_CENTER, leading=10,
        )
        undertime_label_table = Table(
            [["", "", "", "", "", "", Paragraph(
                "TARDINESS<br/>UNDERTIME", undertime_label_style,
            )]],
            colWidths=col_widths,
        )
        undertime_label_table.hAlign = "CENTER"
        undertime_label_table.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ("RIGHTPADDING", (0, 0), (-1, -1), 0),
            ("TOPPADDING", (0, 0), (-1, -1), 0),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
        ]))
        story.append(undertime_label_table)

        # --- Certification statement ---
        certification_table = Table(
            [[Paragraph(
                "I hereby certify on my honor that the above statement is true and correct report of the "
                "work performed, record of which was made daily at the time of arrival and departure from office.",
                cert_style,
            )]],
            colWidths=[NIA_PAGE_WIDTH - (2 * BORDER_HORIZONTAL_INSET)],
        )
        certification_table.hAlign = "CENTER"
        certification_table.setStyle(TableStyle([
            ("LINEABOVE", (0, 0), (-1, 0), 0.3, colors.black),
            ("LINEBELOW", (0, 0), (-1, 0), 0.3, colors.black),
            ("LEFTPADDING", (0, 0), (-1, -1), 2),
            ("RIGHTPADDING", (0, 0), (-1, -1), 2),
            ("TOPPADDING", (0, 0), (-1, -1), 2),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
        ]))
        story.append(certification_table)

        # --- Signature block ---
        #story.append(Spacer(1, 10))
        
        signatory_name_style = ParagraphStyle(
            "NIASignatoryName", parent=styles["Normal"], fontSize=10,
            fontName="Helvetica-Bold", alignment=TA_CENTER, leading=5,
        )
        signatory_label_style = ParagraphStyle(
            "NIASignatoryLabel", parent=styles["Normal"], fontSize=8,
            alignment=TA_LEFT, leading=25,
        )
        signatory_role_style = ParagraphStyle(
            "NIASignatoryRole", parent=styles["Normal"], fontSize=9,
            alignment=TA_CENTER, leading=8,
        )
        signature_line_style = ParagraphStyle(
            "NIASignatureLine", parent=styles["Normal"], fontSize=8,
            alignment=TA_CENTER, leading=12,
        )

        sig_data = [
            [
                "",
                Paragraph("CERTIFIED BY:", signatory_label_style),
                Paragraph("APPROVED:", signatory_label_style),
            ],
            [
                Paragraph(name.upper(), signatory_name_style),
                Paragraph("MARITESS M. BOLINAS", signatory_name_style),
                Paragraph("REBECCA F. GRANA", signatory_name_style),
            ],
            [
                Paragraph("_____________________________", signature_line_style),
                Paragraph("_____________________________", signature_line_style),
                Paragraph("_____________________________", signature_line_style),
            ],
            [
                Paragraph("Signature of Employee", signatory_role_style),
                Paragraph("Administrative Services Officer V", signatory_role_style),
                Paragraph("Acting Division Manager - EOD", signatory_role_style),
            ],
        ]
        sig_table = Table(
            sig_data,
            colWidths=[
                (NIA_PAGE_WIDTH - (2 * BORDER_HORIZONTAL_INSET)) / 3,
            ] * 3,
        )
        sig_table.setStyle(TableStyle([
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("TOPPADDING", (0, 0), (-1, 0), 0),
            ("TOPPADDING", (1, 0), (2, 0), 2),
            ("TOPPADDING", (0, 1), (-1, 1), 0),
            ("TOPPADDING", (0, 2), (-1, 2), 0),
            ("TOPPADDING", (0, 3), (-1, 3), 0),
            ("BOTTOMPADDING", (0, 0), (-1, 0), 0),
            ("BOTTOMPADDING", (0, 1), (-1, 1), 0),
            ("BOTTOMPADDING", (0, 2), (-1, 2), 0),
            ("BOTTOMPADDING", (0, 3), (-1, 3), 0),
        ]))
        story.append(sig_table)

        return story

    def build_combined_pdf(self, grouped: dict, period_dates: list, output_path: str,
                           time_format: str = "24", copies: int = 3) -> list:
        """
        Build one PDF with the requested number of NIA-format copies per
        person. Three copies use two forms on each 8.5 x 13 sheet and place
        the third copy on the next sheet; one copy uses the original 8.5 x
        6.5 form page. `grouped` is the {name: {date: [scans]}} dict returned
        by load_and_group.
        """
        if copies not in (1, 3):
            raise ValueError("copies must be 1 or 3")

        forms_per_sheet = 2 if copies == 3 else 1
        sheet_height = NIA_SHEET_HEIGHT if copies == 3 else NIA_FORM_HEIGHT

        def draw_page_border(canvas, document):
            canvas.saveState()
            canvas.setStrokeColor(colors.black)
            canvas.setLineWidth(0.75)
            canvas.setFont("Helvetica-Oblique", 7.5)
            form_width = document.pagesize[0] - (2 * BORDER_HORIZONTAL_INSET)
            form_bottoms = (0, NIA_FORM_HEIGHT) if forms_per_sheet == 2 else (0,)
            for form_bottom in form_bottoms:
                canvas.rect(
                    BORDER_HORIZONTAL_INSET,
                    form_bottom + BORDER_VERTICAL_INSET,
                    form_width,
                    NIA_FORM_HEIGHT - (2 * BORDER_VERTICAL_INSET),
                    stroke=1,
                    fill=0,
                )
                canvas.drawString(
                    BORDER_HORIZONTAL_INSET,
                    form_bottom + FOOTER_BOTTOM_PADDING,
                    "NIA-ROVI-AFD-AS-INT-Form55 Rev.01",
                )
            if forms_per_sheet == 2:
                canvas.setDash(4, 3)
                canvas.line(
                    BORDER_HORIZONTAL_INSET,
                    NIA_FORM_HEIGHT + CUT_LINE_VERTICAL_OFFSET,
                    document.pagesize[0] - BORDER_HORIZONTAL_INSET,
                    NIA_FORM_HEIGHT + CUT_LINE_VERTICAL_OFFSET,
                )
            canvas.restoreState()

        pdf_title = os.path.splitext(os.path.basename(output_path))[0]
        if copies == 3:
            doc = BaseDocTemplate(
                output_path,
                pagesize=(NIA_PAGE_WIDTH, sheet_height),
                topMargin=0,
                bottomMargin=0,
                leftMargin=0,
                rightMargin=0,
                title=pdf_title,
            )
            frame_width = NIA_PAGE_WIDTH
            doc.addPageTemplates([
                PageTemplate(
                    id="legalDTR",
                    frames=[
                        Frame(0, NIA_FORM_HEIGHT, frame_width, NIA_FORM_HEIGHT,
                              leftPadding=0, bottomPadding=0, rightPadding=0, topPadding=0),
                        Frame(0, 0, frame_width, NIA_FORM_HEIGHT,
                              leftPadding=0, bottomPadding=0, rightPadding=0, topPadding=0),
                    ],
                    onPage=draw_page_border,
                )
            ])
        else:
            doc = SimpleDocTemplate(
                output_path,
                pagesize=(NIA_PAGE_WIDTH, sheet_height),
                topMargin=0,
                bottomMargin=0,
                leftMargin=0,
                rightMargin=0,
                title=pdf_title,
            )
        styles = getSampleStyleSheet()
        lbl = self.period_label(period_dates)
        date_generated = date.today().strftime("%-d %b %Y") if os.name != "nt" else date.today().strftime("%#d %b %Y")

        full_story = []
        names = sorted(grouped.keys())
        total_forms = len(names) * copies
        form_number = 0
        for i, name in enumerate(names):
            dates_scans = grouped[name]
            for copy_number in range(copies):
                full_story.extend(
                    self.build_person_story(
                        name, period_dates, dates_scans, lbl, date_generated, styles,
                        time_format
                    )
                )
                if copies == 3:
                    form_number += 1
                    if form_number < total_forms:
                        full_story.append(FrameBreak())
                elif i < len(names) - 1:
                    full_story.append(PageBreak())

        if copies == 3:
            doc.build(full_story)
        else:
            doc.build(full_story, onFirstPage=draw_page_border, onLaterPages=draw_page_border)
        return names

    def generate(self, csv_path: str, year: int, month: int, half: int,
                 output_filename: str = "NIA_DTR_combined.pdf",
                 time_format: str = "24", copies: int = 3,
                 employee_mode: str = "all", employee_names: list = None):
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

        output_dir = os.path.join(APP_DIR, "output")
        os.makedirs(output_dir, exist_ok=True)
        output_path = os.path.join(output_dir, filename)

        grouped = self.load_and_group(csv_path)
        employee_names = set(employee_names or [])
        if employee_mode == "selected":
            grouped = {
                name: grouped[name] for name in employee_names if name in grouped
            }
        elif employee_mode == "except":
            grouped = {
                name: data for name, data in grouped.items()
                if name not in employee_names
            }
        elif employee_mode != "all":
            raise ValueError(f"Unknown employee selection mode: {employee_mode}")
        if not grouped:
            raise ValueError("No employees remain in the selected employee scope.")
        period_dates = self.get_period_dates(year, month, half)
        names = self.build_combined_pdf(
            grouped, period_dates, output_path, time_format, copies
        )

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