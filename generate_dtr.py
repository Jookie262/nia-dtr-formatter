"""
Base DTR (Daily Time Record) processor class with shared logic for time
calculation, CSV loading, and scan classification.

This module provides the DTRProcessor base class that both SimpleDTRProcessor
(generate_simple_dtr.py) and NIADTRProcessor (generate_nia_dtr.py) inherit from,
ensuring consistency in how scans are classified, times are computed, and CSV
data is loaded.
"""

import os
import re
import pandas as pd
from datetime import datetime
from abc import ABC, abstractmethod


class DTRProcessor(ABC):
    """
    Abstract base class for DTR generation. Handles:
    - CSV loading and grouping scans by person and date
    - Scan classification into AM In/Out and PM In/Out slots
    - Slot time extraction (earliest AM In, latest AM Out, and earliest/latest PM)
    - Time formatting and total hour calculation
    """

    # Time slot boundaries (in minutes from midnight)
    AM_IN_END = 720      # 12:00 PM (start of AM Out)
    AM_OUT_START = 720   # 12:00 PM
    AM_OUT_END = 751     # 12:31 PM (start of PM In)
    PM_IN_START = 751    # 12:31 PM
    PM_IN_END = 810      # 1:30 PM (start of PM Out)
    PM_OUT_START = 811   # 1:31 PM

    def __init__(self):
        """Initialize the DTR processor."""
        pass

    @staticmethod
    def safe_filename(name: str) -> str:
        """Turn a person's name into a filesystem-safe filename."""
        name = name.strip()
        name = re.sub(r"[^\w\s-]", "", name)
        name = re.sub(r"\s+", "_", name)
        return name

    @staticmethod
    def load_and_group(csv_path: str) -> dict:
        """
        Load the CSV and group scans by (Name, Date).
        
        Args:
            csv_path: Path to the CSV file
            
        Returns:
            { name: { date: [sorted datetime scans] } }
            
        Expected CSV columns: Timestamp, Name (Timestamp, ID, Details are optional)
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

    @staticmethod
    def classify_scan(t: datetime) -> str:
        """
        Classify a scan into a DTR slot based on its time of day.
        
        Time ranges:
            AM In  : 12:00 AM - 11:59 AM   (0     - 719 minutes)
            AM Out : 12:00 PM - 12:30 PM   (720   - 750 minutes)
            PM In/Out pool: 12:31 PM - 11:59 PM (751 - 1439 minutes)
            
        Args:
            t: datetime object to classify
            
        Returns:
            String: "am_in", "am_out", "pm_in", or "pm_out"
        """
        minutes = t.hour * 60 + t.minute
        if minutes <= 719:
            return "am_in"
        elif minutes <= 750:
            return "am_out"
        elif minutes <= 810:
            return "pm_in"
        else:
            return "pm_out"

    @staticmethod
    def format_time(t: datetime) -> str:
        """
        Format a datetime object into a time string (HH:MM AM/PM format).
        
        Args:
            t: datetime object to format, or None
            
        Returns:
            Formatted string like "8:30 AM", or "-" if t is None
        """
        return t.strftime("%I:%M %p").lstrip("0") if t else "-"

    @staticmethod
    def _select_slot_datetimes(scans: list) -> tuple:
        """Select slots after ignoring repeated timestamps."""
        scans = sorted(set(scans))
        buckets = {"am_in": [], "am_out": []}
        pm_scans = []
        for scan in scans:
            slot = DTRProcessor.classify_scan(scan)
            if slot == "am_in":
                buckets["am_in"].append(scan)
            elif slot == "am_out":
                buckets["am_out"].append(scan)
            else:
                pm_scans.append(scan)

        am_in = min(buckets["am_in"]) if buckets["am_in"] else None
        am_out = max(buckets["am_out"]) if buckets["am_out"] else None
        pm_in = min(pm_scans) if pm_scans else None
        pm_out = max(pm_scans) if pm_scans else None
        am_count = len(buckets["am_in"]) + len(buckets["am_out"])
        return am_in, am_out, pm_in, pm_out, am_count, len(pm_scans)

    @staticmethod
    def compute_slots_for_date(scans: list) -> dict:
        """
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
            Each value is a formatted time string ("" if slot has no scan)
        """
        if not scans:
            return {"am_in": "", "am_out": "", "pm_in": "", "pm_out": ""}

        am_in, am_out, pm_in, pm_out, am_count, pm_count = (
            DTRProcessor._select_slot_datetimes(scans)
        )

        am_out_display = "00:00" if am_count == 1 else DTRProcessor.format_time(am_out)
        pm_out_display = "00:00" if pm_count == 1 else DTRProcessor.format_time(pm_out)

        return {
            "am_in": DTRProcessor.format_time(am_in),
            "am_out": am_out_display,
            "pm_in": DTRProcessor.format_time(pm_in),
            "pm_out": pm_out_display,
        }

    @staticmethod
    def calculate_total_hours(am_in: datetime, am_out: datetime,
                            pm_in: datetime, pm_out: datetime) -> tuple:
        """
        Calculate total hours worked given AM and PM in/out times.
        
        Args:
            am_in: datetime for AM In, or None
            am_out: datetime for AM Out, or None
            pm_in: datetime for PM In, or None
            pm_out: datetime for PM Out, or None
            
        Returns:
            Tuple: (total_hours: float, missing_list: list of str)
            missing_list contains descriptive names of missing slots
        """
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

        return total_hours, missing

    @staticmethod
    def compute_row(date, scans: list) -> dict:
        """
        Given a date and its list of scan datetimes, compute a DTR row
        with time slots, total hours, and any missing scan notes.
        
        Args:
            date: date object
            scans: list of datetime objects for that date
            
        Returns:
            Dictionary with keys:
                "date": formatted date string (MM/DD/YYYY)
                "am_in": formatted time or "-"
                "am_out": formatted time or "-"
                "pm_in": formatted time or "-"
                "pm_out": formatted time or "-"
                "total": formatted total hours (HH.MM)
                "note": string describing missing slots, or empty
        """
        date_str = date.strftime("%m/%d/%Y")

        am_in, am_out, pm_in, pm_out, am_count, pm_count = (
            DTRProcessor._select_slot_datetimes(scans)
        )

        total_hours, missing = DTRProcessor.calculate_total_hours(
            am_in, am_out, pm_in, pm_out
        )

        note = ""
        if missing:
            note = f"Missing: {', '.join(missing)}"

        return {
            "date": date_str,
            "am_in": DTRProcessor.format_time(am_in),
            "am_out": "00:00" if am_count == 1 else DTRProcessor.format_time(am_out),
            "pm_in": DTRProcessor.format_time(pm_in),
            "pm_out": "00:00" if pm_count == 1 else DTRProcessor.format_time(pm_out),
            "total": f"{total_hours:.2f}",
            "note": note,
        }

    @abstractmethod
    def generate(self, *args, **kwargs):
        """Generate the DTR PDF. Must be implemented by subclasses."""
        pass
