"""Airflow DAG: Cambridge PD Daily Police Log  ->  PostgreSQL (postgres_cpd).

prepare -> extract (Socrata API) -> transform -> load (upsert) -> quality checks
Runs daily. Re-runs are safe (idempotent upsert on record_id).
Trigger manually with {"full_refresh": true} to ignore the watermark.
"""
import json
import os
from datetime import datetime, timedelta

from airflow.decorators import dag, task
from airflow.models.param import Param
from airflow.providers.postgres.hooks.postgres import PostgresHook

from cpd_etl import config, extract, load, transform


def _paths(run_id: str):
    safe = "".join(ch if ch.isalnum() else "_" for ch in run_id)
    return (os.path.join(config.STAGING_DIR, f"raw_{safe}.jsonl"),
            os.path.join(config.STAGING_DIR, f"clean_{safe}.jsonl"))


def _conn():
    return PostgresHook(postgres_conn_id=config.WAREHOUSE_CONN_ID).get_conn()


@dag(
    dag_id="cpd_daily_police_log",
    description="ETL: Cambridge Police Daily Police Log -> PostgreSQL",
    schedule="@daily",
    start_date=datetime(2024, 1, 1),
    catchup=False,
    max_active_runs=1,
    params={"full_refresh": Param(False, type="boolean")},
    default_args={"owner": "data-eng", "retries": 2, "retry_delay": timedelta(minutes=5)},
    tags=["cambridge", "police", "etl"],
)
def cpd_daily_police_log():

    @task
    def prepare(**ctx) -> str | None:
        """Create schema if needed; return the incremental watermark (ISO) or None for a full load."""
        conn = _conn()
        try:
            load.ensure_schema(conn)
            if ctx["params"].get("full_refresh"):
                return None
            wm = load.get_watermark(conn)
            return wm.isoformat() if wm else None
        finally:
            conn.close()

    @task
    def extract_task(watermark: str | None, **ctx) -> int:
        raw_path, _ = _paths(ctx["run_id"])
        since = datetime.fromisoformat(watermark) if watermark else None
        return extract.extract_to_file(raw_path, since)

    @task
    def transform_task(extracted: int, **ctx) -> dict:
        raw_path, clean_path = _paths(ctx["run_id"])
        with open(raw_path, encoding="utf-8") as fh:
            raw_rows = [json.loads(line) for line in fh]
        rows, rejected = transform.transform_rows(raw_rows)
        with open(clean_path, "w", encoding="utf-8") as fh:
            for r in rows:
                r = dict(r)
                for k in ("occurred_at", "incident_date"):
                    r[k] = r[k].isoformat() if r[k] else None
                fh.write(json.dumps(r) + "\n")
        return {"extracted": extracted, "clean": len(rows), "rejected": rejected}

    @task
    def load_task(stats: dict, watermark: str | None, **ctx) -> dict:
        _, clean_path = _paths(ctx["run_id"])
        rows = []
        with open(clean_path, encoding="utf-8") as fh:
            for line in fh:
                r = json.loads(line)
                r["occurred_at"] = datetime.fromisoformat(r["occurred_at"]) if r["occurred_at"] else None
                r["incident_date"] = datetime.fromisoformat(r["incident_date"]).date() if r["incident_date"] else None
                rows.append(r)
        conn = _conn()
        try:
            loaded = load.upsert(conn, rows)
            load.log_run(conn, ctx["run_id"], stats["extracted"], loaded, stats["rejected"],
                         datetime.fromisoformat(watermark) if watermark else None)
        finally:
            conn.close()
        return {**stats, "loaded": loaded}

    @task
    def quality_checks(stats: dict, **ctx):
        """Fail loudly instead of silently loading garbage."""
        if stats["extracted"] > 0 and stats["clean"] == 0:
            raise ValueError(f"All {stats['extracted']} extracted rows were rejected - schema change?")
        if stats["extracted"] > 50 and stats["rejected"] / stats["extracted"] > 0.2:
            raise ValueError(f"Reject rate too high: {stats['rejected']}/{stats['extracted']}")
        conn = _conn()
        try:
            with conn.cursor() as cur:
                cur.execute(f"SELECT count(*), count(*) FILTER (WHERE occurred_at IS NULL) FROM {config.TARGET_TABLE}")
                total, null_ts = cur.fetchone()
            if total and null_ts / total > 0.05:
                raise ValueError(f"{null_ts}/{total} rows have no parsed timestamp")
        finally:
            conn.close()
        for p in _paths(ctx["run_id"]):  # cleanup staging files
            if os.path.exists(p):
                os.remove(p)

    wm = prepare()
    ext = extract_task(wm)
    tr = transform_task(ext)
    ld = load_task(tr, wm)
    quality_checks(ld)


cpd_daily_police_log()
