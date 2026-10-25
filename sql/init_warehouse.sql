CREATE SCHEMA IF NOT EXISTS cpd;

CREATE TABLE IF NOT EXISTS cpd.daily_police_log (
    record_id         TEXT PRIMARY KEY,          -- stable hash; makes loads idempotent
    incident_number   TEXT,
    incident_type     TEXT,
    crime_description TEXT,
    statute_chapter   TEXT,                      -- e.g. 266 from "C266 S16"
    statute_section   TEXT,                      -- e.g. 16
    street            TEXT,
    neighborhood      TEXT,
    reporting_area    TEXT,
    narrative         TEXT,
    occurred_at       TIMESTAMP,
    incident_date     DATE,
    incident_hour     SMALLINT,
    day_of_week       TEXT,
    raw               JSONB NOT NULL,            -- untouched source row
    loaded_at         TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_dpl_incident_date ON cpd.daily_police_log (incident_date);
CREATE INDEX IF NOT EXISTS idx_dpl_crime         ON cpd.daily_police_log (crime_description);
CREATE INDEX IF NOT EXISTS idx_dpl_street        ON cpd.daily_police_log (street);

CREATE TABLE IF NOT EXISTS cpd.etl_run_log (
    run_id         BIGSERIAL PRIMARY KEY,
    dag_run_id     TEXT,
    started_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    rows_extracted INTEGER,
    rows_loaded    INTEGER,
    rows_rejected  INTEGER,
    watermark_used TIMESTAMP
);
