"""Transform: normalise the raw SODA rows into the warehouse schema.

Column names in open-data portals drift, so source fields are resolved through an
alias table instead of hard-coding one name. The untouched row is always kept in `raw`.
"""
import hashlib
import json
import re
from datetime import datetime
from typing import Iterable, Optional

FIELD_ALIASES = {
    "incident_number": ["incident_number", "incident_no", "incident", "number", "incident_id", "id"],
    "incident_type": ["incident_type", "type"],
    "occurred_at": ["date_time", "datetime", "date_and_time", "date"],
    "crime_description": ["subtype", "crime", "offense", "incident_description"],
    "street": ["location", "street", "address"],
    "neighborhood": ["neighborhood"],
    "reporting_area": ["reporting_area", "reporting_area_id"],
    "narrative": ["description", "info", "narrative", "comments", "details", "notes"],
}

STATUTE_RE = re.compile(r"\bC\s?(\d+[A-Z]?)\s+S\s?(\d+[A-Z]?)\b", re.IGNORECASE)
_DT_FORMATS = ("%Y-%m-%dT%H:%M:%S.%f", "%Y-%m-%dT%H:%M:%S", "%m/%d/%Y %H:%M", "%m/%d/%Y%H:%M", "%m/%d/%Y")

DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

OUTPUT_COLUMNS = [
    "record_id", "incident_number", "incident_type", "crime_description", "statute_chapter",
    "statute_section", "street", "neighborhood", "reporting_area", "narrative", "occurred_at",
    "incident_date", "incident_hour", "day_of_week", "raw",
]


def _clean(value) -> Optional[str]:
    if value is None:
        return None
    text = re.sub(r"\s+", " ", str(value)).strip()
    return text or None


def _pick(row: dict, logical: str) -> Optional[str]:
    for key in FIELD_ALIASES[logical]:
        if key in row and _clean(row[key]) is not None:
            return _clean(row[key])
    return None


def parse_datetime(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    for fmt in _DT_FORMATS:
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue
    return None


def make_record_id(incident_number, occurred_at, crime, street, narrative) -> str:
    # Entries with an incident number are identified by it; narrative-only entries
    # (no number) fall back to their text so distinct entries don't collapse together.
    parts = [incident_number or "", occurred_at or "", (crime or "").upper(), (street or "").upper()]
    if not incident_number:
        parts.append((narrative or "")[:200])
    return hashlib.sha1("|".join(parts).encode("utf-8")).hexdigest()


def transform_row(row: dict) -> Optional[dict]:
    occurred_raw = _pick(row, "occurred_at")
    occurred = parse_datetime(occurred_raw)
    incident_number = _pick(row, "incident_number")
    crime = _pick(row, "crime_description")
    narrative = _pick(row, "narrative")
    street = _pick(row, "street")

    # Reject rows with nothing identifiable
    if occurred is None and not incident_number and not narrative:
        return None

    chapter = section = None
    if crime:
        m = STATUTE_RE.search(crime)
        if m:
            chapter, section = m.group(1).upper(), m.group(2).upper()

    itype = _pick(row, "incident_type")
    return {
        "record_id": make_record_id(incident_number, occurred.isoformat() if occurred else None,
                                    crime, street, narrative),
        "incident_number": incident_number,
        "incident_type": itype.upper() if itype else None,
        "crime_description": crime.upper() if crime else None,
        "statute_chapter": chapter,
        "statute_section": section,
        "street": street.upper() if street else None,
        "neighborhood": _pick(row, "neighborhood"),
        "reporting_area": _pick(row, "reporting_area"),
        "narrative": narrative,
        "occurred_at": occurred,
        "incident_date": occurred.date() if occurred else None,
        "incident_hour": occurred.hour if occurred else None,
        "day_of_week": DAYS[occurred.weekday()] if occurred else None,
        "raw": json.dumps(row, sort_keys=True),
    }


def transform_rows(rows: Iterable[dict]) -> tuple[list[dict], int]:
    """Return (clean unique rows, rejected_count). Last occurrence of a record_id wins."""
    out: dict[str, dict] = {}
    rejected = 0
    for row in rows:
        t = transform_row(row)
        if t is None:
            rejected += 1
            continue
        out[t["record_id"]] = t
    return list(out.values()), rejected
