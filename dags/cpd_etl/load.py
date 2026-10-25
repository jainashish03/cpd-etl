"""Load: idempotent upsert into PostgreSQL."""
import logging
import os
from datetime import datetime, timedelta
from typing import Optional

from psycopg2.extras import execute_values

from . import config
from .transform import OUTPUT_COLUMNS

log = logging.getLogger(__name__)

SQL_DIR = os.getenv("CPD_SQL_DIR", "/opt/airflow/sql")


def ensure_schema(conn) -> None:
    with open(os.path.join(SQL_DIR, "init_warehouse.sql"), encoding="utf-8") as fh:
        ddl = fh.read()
    with conn.cursor() as cur:
        cur.execute(ddl)
    conn.commit()


def get_watermark(conn) -> Optional[datetime]:
    """Latest loaded timestamp minus the look-back window; None => full load."""
    with conn.cursor() as cur:
        cur.execute(f"SELECT max(occurred_at) FROM {config.TARGET_TABLE}")
        latest = cur.fetchone()[0]
    return latest - timedelta(days=config.LOOKBACK_DAYS) if latest else None


def upsert(conn, rows: list[dict], batch_size: int = 2000) -> int:
    if not rows:
        return 0
    cols = ", ".join(OUTPUT_COLUMNS)
    updates = ", ".join(f"{c} = EXCLUDED.{c}" for c in OUTPUT_COLUMNS if c != "record_id")
    sql = (
        f"INSERT INTO {config.TARGET_TABLE} ({cols}) VALUES %s "
        f"ON CONFLICT (record_id) DO UPDATE SET {updates}, loaded_at = now()"
    )
    placeholders = ["%s"] * (len(OUTPUT_COLUMNS) - 1) + ["%s::jsonb"]  # raw is the last column
    template = "(" + ", ".join(placeholders) + ")"
    total = 0
    with conn.cursor() as cur:
        for i in range(0, len(rows), batch_size):
            chunk = rows[i:i + batch_size]
            values = [tuple(r[c] for c in OUTPUT_COLUMNS) for r in chunk]
            execute_values(cur, sql, values, template=template, page_size=batch_size)
            total += len(chunk)
    conn.commit()
    log.info("Upserted %d rows into %s", total, config.TARGET_TABLE)
    return total


def log_run(conn, dag_run_id, extracted, loaded, rejected, watermark) -> None:
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO cpd.etl_run_log (dag_run_id, rows_extracted, rows_loaded, rows_rejected, watermark_used) "
            "VALUES (%s, %s, %s, %s, %s)",
            (dag_run_id, extracted, loaded, rejected, watermark),
        )
    conn.commit()
