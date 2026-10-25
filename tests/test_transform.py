import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "dags"))

from cpd_etl.transform import parse_datetime, transform_row, transform_rows  # noqa: E402

SAMPLE = {
    "date_time": "2023-11-15T05:47:00.000",
    "incident": "23010465-1",
    "type": "incident",
    "crime": "B&E NIGHTTIME FOR FELONY C266 S16",
    "location": "banks st",
    "info": "Police responded to a residence   for a breaking & entering.",
}


def test_basic_transform():
    t = transform_row(SAMPLE)
    assert t["incident_number"] == "23010465-1"
    assert t["incident_type"] == "INCIDENT"
    assert (t["statute_chapter"], t["statute_section"]) == ("266", "16")
    assert t["street"] == "BANKS ST"
    assert t["incident_hour"] == 5 and t["day_of_week"] == "Wednesday"
    assert "  " not in t["narrative"]
    assert json.loads(t["raw"])["incident"] == "23010465-1"


def test_idempotent_ids_and_dedupe():
    rows, rejected = transform_rows([SAMPLE, dict(SAMPLE)])
    assert len(rows) == 1 and rejected == 0


def test_rejects_empty_rows():
    rows, rejected = transform_rows([{"foo": "bar"}, {}])
    assert rows == [] and rejected == 2


def test_alternate_field_names_and_formats():
    t = transform_row({"datetime": "11/15/2023 08:17", "incident_number": "1", "offense": "LARCENY C266 S30"})
    assert t["occurred_at"].hour == 8 and t["statute_section"] == "30"
    assert parse_datetime("garbage") is None


def test_narrative_only_rows_stay_distinct():
    a = transform_row({"date_time": "2023-11-15T10:20:00", "info": "Police responded for a disturbance."})
    b = transform_row({"date_time": "2023-11-15T10:20:00", "info": "Police responded for a stolen bicycle."})
    assert a["record_id"] != b["record_id"]
