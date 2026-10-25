"""Extract: page through the Socrata (SODA) API."""
import json
import logging
import os
from datetime import datetime
from typing import Iterator, Optional

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from . import config

log = logging.getLogger(__name__)

DATE_FIELD_CANDIDATES = ["date_time", "datetime", "date_and_time", "date"]


def _session() -> requests.Session:
    s = requests.Session()
    retry = Retry(total=5, backoff_factor=2, status_forcelist=(429, 500, 502, 503, 504))
    s.mount("https://", HTTPAdapter(max_retries=retry))
    if config.APP_TOKEN:
        s.headers["X-App-Token"] = config.APP_TOKEN
    return s


def detect_date_field(sample_row: dict) -> Optional[str]:
    for c in DATE_FIELD_CANDIDATES:
        if c in sample_row:
            return c
    return None


def fetch_records(since: Optional[datetime] = None) -> Iterator[dict]:
    """Yield raw rows. If `since` is given, only rows with date >= since (incremental)."""
    s = _session()
    where = None
    if since is not None:
        probe = s.get(config.RESOURCE_URL, params={"$limit": 1}, timeout=60)
        probe.raise_for_status()
        rows = probe.json()
        field = detect_date_field(rows[0]) if rows else None
        if field is None:
            log.warning("Could not detect date field; falling back to full extract.")
        else:
            where = f"{field} >= '{since.strftime('%Y-%m-%dT%H:%M:%S')}'"

    offset = 0
    while True:
        params = {"$limit": config.PAGE_SIZE, "$offset": offset, "$order": ":id"}
        if where:
            params["$where"] = where
        resp = s.get(config.RESOURCE_URL, params=params, timeout=120)
        resp.raise_for_status()
        page = resp.json()
        if not page:
            break
        log.info("Fetched %d rows (offset=%d)", len(page), offset)
        yield from page
        if len(page) < config.PAGE_SIZE:
            break
        offset += config.PAGE_SIZE


def extract_to_file(path: str, since: Optional[datetime] = None) -> int:
    """Stream raw rows to a JSONL file (keeps memory flat, avoids XCom size limits)."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    n = 0
    with open(path, "w", encoding="utf-8") as fh:
        for row in fetch_records(since):
            fh.write(json.dumps(row) + "\n")
            n += 1
    log.info("Extracted %d rows -> %s", n, path)
    return n
