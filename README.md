# Cambridge PD Daily Police Log — ETL + Metabase

Socrata API → (Airflow: extract → transform → load) → PostgreSQL `postgres_cpd` ⇄ Metabase

Source: https://data.cambridgema.gov/Public-Safety/Daily-Police-Log/3gki-wyrb

## Run it
```bash
cp .env.example .env          # set AIRFLOW_FERNET_KEY (command is in the file); optionally SOCRATA_APP_TOKEN
docker compose up -d --build
```
| Service  | URL                    | Login                         |
|----------|------------------------|-------------------------------|
| Airflow  | http://localhost:8080  | `AIRFLOW_ADMIN_*` from `.env` |
| Metabase | http://localhost:3000  | created on first visit        |
| Warehouse| localhost:5433         | `CPD_DB_*` from `.env`        |

1. In Airflow, unpause **cpd_daily_police_log** and trigger it once (first run = full load; later runs are incremental).
2. Metabase → Add database → PostgreSQL → host `postgres_cpd`, port `5432`, db/user/password from `.env`.
3. Build charts from `sql/metabase_questions.sql` and put them on a dashboard (set auto-refresh to daily).

## Design notes
- **Idempotent**: `record_id` = hash of incident number + time + offence + street; load is `INSERT … ON CONFLICT DO UPDATE`. Re-runs and overlaps never duplicate.
- **Incremental**: watermark = `max(occurred_at)` minus a 7-day look-back (`CPD_LOOKBACK_DAYS`) to catch late-posted entries. Trigger with `{"full_refresh": true}` to reload everything.
- **Schema-drift tolerant**: source columns are resolved via aliases in `transform.py`; the untouched row is kept in `raw` (JSONB), so nothing is lost if a column is renamed.
- **Quality gates**: DAG fails if everything is rejected, >20% rejected, or >5% of rows lack a timestamp. Each run is logged in `cpd.etl_run_log`.
- **Metabase** has its own app DB (`postgres_metabase`) — separate from your data.
- Narratives can contain names of arrested people (public record). Drop/mask `narrative` in `transform.py` if you share the dashboard widely.

## Dev
```bash
pip install -r requirements.txt && pytest
```
