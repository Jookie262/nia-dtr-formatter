"""
Generate a Daily Time Record (DTR) PDF per personnel from a raw attendance
scan log CSV.

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
    python generate_dtr.py <input_csv> [output_filename.pdf]
"""

import sys
import os
import re
import pandas as pd
from datetime import datetime
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER


def safe_filename(name: str) -> str:
    """Turn a person's name into a filesystem-safe filename."""
    name = name.strip()
    name = re.sub(r"[^\w\s-]", "", name)
    name = re.sub(r"\s+", "_", name)
    return name


def load_and_group(csv_path: str) -> dict:
    """
    Load the CSV and group scans by (Name, Date).
    Returns: { name: { date: [sorted datetime scans] } }
    """
    df = pd.read_csv(csv_path)

    required_cols = {"Timestamp", "Name"}
    missing = required_cols - set(c.strip() for c in df.columns)
    if missing:
        raise ValueError(f"CSV is missing required column(s): {missing}")

    df.columns = [c.strip() for c in df.columns]
    df["Timestamp"] = pd.to_datetime(df["Timestamp"], format="%d/%m/%Y %H:%M")
    df["Date"] = df["Timestamp"].dt.date
    df["Name"] = df["Name"].str.strip()

    grouped = {}
    for name, name_df in df.groupby("Name"):
        grouped[name] = {}
        for date, date_df in name_df.groupby("Date"):
            scans = sorted(date_df["Timestamp"].tolist())
            grouped[name][date] = scans

    return grouped


def classify_scan(t: datetime) -> str:
    """
    Classify a scan into a DTR slot based on its time of day:
        AM In  : 12:00 AM - 11:59 AM   (0     - 719 minutes)
        AM Out : 12:00 PM - 12:29 PM   (720   - 749 minutes)
        PM In  : 12:30 PM - 1:00  PM   (750   - 780 minutes)
        PM Out : 1:01 PM  - 11:59 PM   (781   - 1439 minutes)
    """
    minutes = t.hour * 60 + t.minute
    if minutes <= 719:
        return "am_in"
    elif minutes <= 749:
        return "am_out"
    elif minutes <= 780:
        return "pm_in"
    else:
        return "pm_out"


def compute_row(date, scans):
    """
    Given a date and its list of scan datetimes, classify each scan into
    a slot (AM In / AM Out / PM In / PM Out) by time of day, then compute
    total hours from whichever pairs are complete. Handles days with any
    number of scans (including just 1), not only exactly 4.
    """
    date_str = date.strftime("%m/%d/%Y")

    buckets = {"am_in": [], "am_out": [], "pm_in": [], "pm_out": []}
    for s in scans:
        buckets[classify_scan(s)].append(s)

    if len(scans) >= 5:
        # Many taps that day (likely duplicate/accidental scans) -> always
        # keep the latest scan in each slot.
        am_in = max(buckets["am_in"]) if buckets["am_in"] else None
        am_out = max(buckets["am_out"]) if buckets["am_out"] else None
        pm_in = max(buckets["pm_in"]) if buckets["pm_in"] else None
        pm_out = max(buckets["pm_out"]) if buckets["pm_out"] else None
    else:
        # Normal day -> earliest scan for "In" slots, latest for "Out" slots.
        am_in = min(buckets["am_in"]) if buckets["am_in"] else None
        am_out = max(buckets["am_out"]) if buckets["am_out"] else None
        pm_in = min(buckets["pm_in"]) if buckets["pm_in"] else None
        pm_out = max(buckets["pm_out"]) if buckets["pm_out"] else None

    def fmt(t):
        return t.strftime("%I:%M %p").lstrip("0") if t else "-"

    total_hours = 0.0
    missing = []

    if am_in and am_out:
        total_hours += (am_out - am_in).total_seconds() / 3600
    else:
        if not am_in:
            missing.append("AM In")
        if not am_out:
            missing.append("AM Out")

    if pm_in and pm_out:
        total_hours += (pm_out - pm_in).total_seconds() / 3600
    else:
        if not pm_in:
            missing.append("PM In")
        if not pm_out:
            missing.append("PM Out")

    note = ""
    if missing:
        note = f"Missing: {', '.join(missing)}"

    return {
        "date": date_str,
        "am_in": fmt(am_in),
        "am_out": fmt(am_out),
        "pm_in": fmt(pm_in),
        "pm_out": fmt(pm_out),
        "total": f"{total_hours:.2f}",
        "note": note,
    }


def build_person_story(name: str, rows: list, styles) -> list:
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
    story.append(Paragraph("(Generated from attendance log)", subtitle_style))
    story.append(Paragraph(f"<b>Name:</b> {name}", name_style))

    table_data = [["Date", "AM In", "AM Out", "PM In", "PM Out"]]
    incomplete_notes = []

    for r in rows:
        table_data.append([r["date"], r["am_in"], r["am_out"], r["pm_in"], r["pm_out"]])
        if r["note"]:
            incomplete_notes.append(f"{r['date']}: {r['note']}")

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

    if incomplete_notes:
        story.append(Spacer(1, 14))
        note_style = ParagraphStyle(
            "Notes", parent=styles["Normal"], fontSize=8.5, textColor=colors.HexColor("#b03a2e")
        )
        story.append(Paragraph("<b>Note:</b> The following day(s) have missing scan(s):", note_style))
        for n in incomplete_notes:
            story.append(Paragraph(f"&bull; {n}", note_style))

    return story


def build_combined_pdf(grouped: dict, output_path: str):
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
        rows = [compute_row(date, scans) for date, scans in sorted(dates.items())]
        full_story.extend(build_person_story(name, rows, styles))
        if i < len(names) - 1:
            full_story.append(PageBreak())

    doc.build(full_story)
    return names


def main():
    if len(sys.argv) < 2:
        print("Usage: python generate_dtr.py <input_csv> [output_filename.pdf]")
        sys.exit(1)

    csv_path = sys.argv[1]
    filename = sys.argv[2] if len(sys.argv) > 2 else "DTR_combined.pdf"
    filename = os.path.basename(filename)  # ignore any path the user typed
    if not filename.lower().endswith(".pdf"):
        filename += ".pdf"

    output_dir = "output"
    os.makedirs(output_dir, exist_ok=True)  # creates it if missing, reuses it if it exists
    output_path = os.path.join(output_dir, filename)

    grouped = load_and_group(csv_path)
    names = build_combined_pdf(grouped, output_path)

    print(f"Generated: {output_path}")
    print(f"Done. {len(names)} personnel included in one PDF ({len(names)} page(s)).")


if __name__ == "__main__":
    main()