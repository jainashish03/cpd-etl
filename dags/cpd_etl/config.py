import os

SOCRATA_DOMAIN = "data.cambridgema.gov"
DATASET_ID = "3gki-wyrb"  # Cambridge Daily Police Log
RESOURCE_URL = f"https://{SOCRATA_DOMAIN}/resource/{DATASET_ID}.json"

APP_TOKEN = os.getenv("SOCRATA_APP_TOKEN") or None
PAGE_SIZE = int(os.getenv("CPD_PAGE_SIZE", "5000"))
# Re-pull this many days before the watermark to catch late-posted/edited log entries.
LOOKBACK_DAYS = int(os.getenv("CPD_LOOKBACK_DAYS", "7"))

STAGING_DIR = os.getenv("CPD_STAGING_DIR", "/tmp/cpd")
WAREHOUSE_CONN_ID = "postgres_cpd"
TARGET_TABLE = "cpd.daily_police_log"
