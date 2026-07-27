"""Export API calls as CSV / JSON with filters."""

from __future__ import annotations

import csv
import io
import json
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Iterator, List, Optional, Tuple

from models import query_calls


def _parse_range(
    time_range: str,
    *,
    custom_from: Optional[str] = None,
    custom_to: Optional[str] = None,
) -> Tuple[Optional[str], Optional[str]]:
    now = datetime.now(timezone.utc)
    tr = (time_range or "7d").lower()
    if tr in ("", "all"):
        return None, None
    if tr == "today":
        start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        return start.strftime("%Y-%m-%dT%H:%M:%S.%fZ"), None
    if tr in ("7d", "7days"):
        return (now - timedelta(days=7)).strftime("%Y-%m-%dT%H:%M:%S.%fZ"), None
    if tr in ("30d", "30days"):
        return (now - timedelta(days=30)).strftime("%Y-%m-%dT%H:%M:%S.%fZ"), None
    if tr == "custom":
        return custom_from, custom_to
    return None, None


def _status_bounds(status: Optional[str]) -> Tuple[Optional[int], Optional[int]]:
    if status == "success":
        return 200, 399
    if status == "failure":
        return 400, 599
    return None, None


def iter_export_rows(
    api_key: str,
    *,
    time_range: str = "7d",
    custom_from: Optional[str] = None,
    custom_to: Optional[str] = None,
    vendor: Optional[str] = None,
    status: Optional[str] = None,
    db_path=None,
    batch_size: int = 1000,
    max_rows: int = 100_000,
) -> Iterator[Dict[str, Any]]:
    ts_from, ts_to = _parse_range(
        time_range, custom_from=custom_from, custom_to=custom_to
    )
    smin, smax = _status_bounds(status)
    offset = 0
    yielded = 0
    while yielded < max_rows:
        n = min(batch_size, max_rows - yielded)
        rows = query_calls(
            api_key,
            ts_from=ts_from,
            ts_to=ts_to,
            vendor=(vendor or None),
            status_code_min=smin,
            status_code_max=smax,
            limit=n,
            offset=offset,
            db_path=db_path,
        )
        if not rows:
            break
        for r in rows:
            yield r
            yielded += 1
        if len(rows) < n:
            break
        offset += n


CSV_COLUMNS = [
    ("timestamp", "时间"),
    ("vendor", "厂商"),
    ("endpoint", "端点"),
    ("model", "模型"),
    ("status_code", "状态"),
    ("cost_usd", "费用"),
    ("request_size", "请求大小"),
    ("response_size", "响应大小"),
    ("duration_ms", "耗时"),
    ("chain_hash", "哈希"),
]


def rows_to_csv(rows: List[Dict[str, Any]]) -> bytes:
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow([c[1] for c in CSV_COLUMNS])
    for r in rows:
        writer.writerow(
            [
                r.get("timestamp"),
                r.get("vendor") or "openai",
                r.get("endpoint"),
                r.get("model"),
                r.get("status_code"),
                r.get("cost_usd"),
                r.get("request_size"),
                r.get("response_size"),
                r.get("duration_ms"),
                r.get("chain_hash"),
            ]
        )
    # UTF-8 BOM for Excel
    return ("\ufeff" + buf.getvalue()).encode("utf-8")


def rows_to_json(rows: List[Dict[str, Any]]) -> bytes:
    lean = []
    for r in rows:
        lean.append(
            {
                "timestamp": r.get("timestamp"),
                "vendor": r.get("vendor") or "openai",
                "endpoint": r.get("endpoint"),
                "model": r.get("model"),
                "status_code": r.get("status_code"),
                "cost_usd": r.get("cost_usd"),
                "request_size": r.get("request_size"),
                "response_size": r.get("response_size"),
                "duration_ms": r.get("duration_ms"),
                "chain_hash": r.get("chain_hash"),
                "id": r.get("id"),
            }
        )
    return json.dumps(
        {"n": len(lean), "calls": lean}, ensure_ascii=False, indent=2
    ).encode("utf-8")
