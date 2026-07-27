"""Query-as-audit: filter API calls and append query events to the hash chain.

Any filterable call state becomes an auditable query surface on the hash chain.
"""

from __future__ import annotations

import json
import time
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Mapping, Optional, Tuple

from attestation import (
    GENESIS,
    compute_query_chain_hash,
    sha256_text,
    utc_now,
)
from models import (
    insert_query,
    query_calls,
)
from key_auth import require_key
from write_buffer import build_next_record


def _parse_time_range(
    time_range: str,
    *,
    custom_from: Optional[str] = None,
    custom_to: Optional[str] = None,
) -> Tuple[Optional[str], Optional[str]]:
    now = datetime.now(timezone.utc)
    tr = (time_range or "").strip().lower()
    if tr in ("", "all"):
        return None, None
    if tr == "today":
        start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        return start.strftime("%Y-%m-%dT%H:%M:%S.%fZ"), None
    if tr in ("7d", "7days", "last_7_days"):
        return (now - timedelta(days=7)).strftime("%Y-%m-%dT%H:%M:%S.%fZ"), None
    if tr in ("30d", "30days", "last_30_days"):
        return (now - timedelta(days=30)).strftime("%Y-%m-%dT%H:%M:%S.%fZ"), None
    if tr == "custom":
        return custom_from, custom_to
    return None, None


def normalize_params(raw: Mapping[str, Any]) -> Dict[str, Any]:
    """Canonical query params for hashing (stable key order)."""
    status = raw.get("status")
    status_code_min = raw.get("status_code_min")
    status_code_max = raw.get("status_code_max")
    if status == "success":
        status_code_min, status_code_max = 200, 399
    elif status == "failure":
        status_code_min, status_code_max = 400, 599
    elif status == "timeout":
        # heuristic: 408 or 504
        status_code_min, status_code_max = 408, 504

    tr = str(raw.get("time_range") or "7d")
    ts_from, ts_to = _parse_time_range(
        tr,
        custom_from=raw.get("custom_from"),
        custom_to=raw.get("custom_to"),
    )
    params = {
        "time_range": tr,
        "custom_from": raw.get("custom_from") or None,
        "custom_to": raw.get("custom_to") or None,
        "ts_from": ts_from,
        "ts_to": ts_to,
        "endpoint": (str(raw.get("endpoint") or "").strip() or None),
        "min_cost": float(raw["min_cost"]) if raw.get("min_cost") is not None else None,
        "max_cost": float(raw["max_cost"]) if raw.get("max_cost") is not None else None,
        "status": status or None,
        "status_code_min": status_code_min,
        "status_code_max": status_code_max,
        "model": (str(raw.get("model") or "").strip() or None),
        "vendor": (str(raw.get("vendor") or "").strip().lower() or None),
        "limit": int(raw.get("limit") or 100),
    }
    return params


def params_hash(params: Mapping[str, Any]) -> str:
    blob = json.dumps(params, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return sha256_text(blob)


def results_hash(call_ids: List[str]) -> str:
    # ordered ids only — no PII bodies
    blob = "|".join(call_ids)
    return sha256_text(blob or "empty")


def execute_attested_query(
    *,
    api_key: str,
    raw_params: Mapping[str, Any],
    db_path=None,
) -> Dict[str, Any]:
    require_key(api_key, min_role="read_write", db_path=db_path, label="query")
    params = normalize_params(raw_params)
    t0 = time.perf_counter()
    rows = query_calls(
        api_key,
        ts_from=params.get("ts_from"),
        ts_to=params.get("ts_to"),
        endpoint_substr=params.get("endpoint"),
        min_cost=params.get("min_cost"),
        max_cost=params.get("max_cost"),
        status_code_min=params.get("status_code_min"),
        status_code_max=params.get("status_code_max"),
        model_substr=params.get("model"),
        vendor=params.get("vendor"),
        limit=int(params.get("limit") or 100),
        db_path=db_path,
    )
    duration_ms = (time.perf_counter() - t0) * 1000.0
    call_ids = [str(r["id"]) for r in rows]
    qh = params_hash(params)
    rh = results_hash(call_ids)
    query_id = f"qry_{uuid.uuid4().hex[:16]}"
    attest_id = f"att_{uuid.uuid4().hex[:16]}"
    ts = utc_now()

    def _build(prev: str):
        chain_h = compute_query_chain_hash(
            prev_hash=prev,
            query_id=query_id,
            timestamp=ts,
            query_params_hash=qh,
            result_count=len(rows),
            result_hash=rh,
        )
        return {
            "id": query_id,
            "attest_id": attest_id,
            "api_key": api_key,
            "timestamp": ts,
            "query_params": params,
            "query_params_json": json.dumps(params, ensure_ascii=False, sort_keys=True),
            "result_count": len(rows),
            "result_ids_json": json.dumps(call_ids, ensure_ascii=False),
            "query_hash": qh,
            "result_hash": rh,
            "prev_hash": prev or GENESIS,
            "chain_hash": chain_h,
            "duration_ms": round(duration_ms, 3),
        }

    record = build_next_record(api_key, _build, db_path=db_path)
    insert_query(record, db_path=db_path)
    chain_h = record["chain_hash"]
    # lean results for dashboard table
    lean = [
        {
            "id": r["id"],
            "timestamp": r["timestamp"],
            "endpoint": r["endpoint"],
            "model": r.get("model"),
            "status_code": r.get("status_code"),
            "cost_usd": r.get("cost_usd"),
            "duration_ms": r.get("duration_ms"),
        }
        for r in rows
    ]
    return {
        "query_id": query_id,
        "results": lean,
        "count": len(lean),
        "duration_ms": record["duration_ms"],
        "query_hash": qh,
        "result_hash": rh,
        "chain_hash": chain_h,
        "prev_hash": record["prev_hash"],
        "timestamp": ts,
        "query_params": params,
    }
