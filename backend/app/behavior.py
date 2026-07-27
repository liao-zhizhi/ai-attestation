"""Behavior baseline snapshots + silent drift marks (mark, don't judge)."""

from __future__ import annotations

import json
import math
import statistics
import time
import uuid
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

from attestation import (
    GENESIS,
    compute_baseline_chain_hash,
    compute_drift_mark_chain_hash,
    compute_drift_review_chain_hash,
    sha256_text,
    utc_now,
)
from models import (
    get_baseline,
    get_drift_mark,
    insert_baseline,
    insert_drift_mark,
    list_baselines,
    list_drift_marks,
    query_calls,
    soft_delete_baseline,
    update_drift_mark_review,
)
from key_auth import require_key
from write_buffer import build_next_record


def _parse_ts(ts: str) -> datetime:
    s = (ts or "").replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(s)
    except ValueError:
        return datetime.now(timezone.utc)


def _day_key(ts: str) -> str:
    return _parse_ts(ts).strftime("%Y-%m-%d")


def _percentile(sorted_vals: Sequence[float], p: float) -> float:
    if not sorted_vals:
        return 0.0
    if len(sorted_vals) == 1:
        return float(sorted_vals[0])
    k = (len(sorted_vals) - 1) * (p / 100.0)
    f = math.floor(k)
    c = math.ceil(k)
    if f == c:
        return float(sorted_vals[int(k)])
    return float(sorted_vals[f] * (c - k) + sorted_vals[c] * (k - f))


def _range_bounds(
    time_range: str,
    *,
    custom_from: Optional[str] = None,
    custom_to: Optional[str] = None,
) -> Tuple[str, str]:
    now = datetime.now(timezone.utc)
    tr = (time_range or "7d").strip().lower()
    if tr == "custom" and custom_from:
        end = custom_to or now.strftime("%Y-%m-%dT%H:%M:%S.%fZ")
        return custom_from, end
    days = 7
    if tr in ("30d", "30days"):
        days = 30
    elif tr in ("1d", "today"):
        days = 1
    start = (now - timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%S.%fZ")
    end = now.strftime("%Y-%m-%dT%H:%M:%S.%fZ")
    return start, end


def compute_stats(calls: Sequence[Mapping[str, Any]]) -> Dict[str, Any]:
    if not calls:
        return {
            "n_calls": 0,
            "daily_calls": {"mean": 0.0, "std": 0.0, "min": 0, "max": 0, "by_day": {}},
            "endpoints": {"dist": {}, "set": []},
            "costs": {"daily_mean": 0.0, "p25": 0.0, "p50": 0.0, "p75": 0.0, "p95": 0.0},
            "latency": {"mean": 0.0, "p95": 0.0},
            "models": {"dist": {}},
        }

    by_day: Dict[str, int] = defaultdict(int)
    day_cost: Dict[str, float] = defaultdict(float)
    endpoints: Counter = Counter()
    models: Counter = Counter()
    costs: List[float] = []
    latencies: List[float] = []

    for c in calls:
        dk = _day_key(str(c.get("timestamp") or ""))
        by_day[dk] += 1
        cost = float(c.get("cost_usd") or 0)
        day_cost[dk] += cost
        costs.append(cost)
        latencies.append(float(c.get("duration_ms") or 0))
        ep = str(c.get("endpoint") or "").strip() or "(empty)"
        endpoints[ep] += 1
        mid = str(c.get("model") or "").strip() or "(unknown)"
        models[mid] += 1

    daily_counts = list(by_day.values())
    mean = statistics.mean(daily_counts) if daily_counts else 0.0
    std = statistics.pstdev(daily_counts) if len(daily_counts) > 1 else 0.0
    n = len(calls)
    ep_dist = {k: round(v / n, 4) for k, v in endpoints.most_common()}
    model_dist = {k: round(v / n, 4) for k, v in models.most_common()}
    costs_s = sorted(costs)
    lats_s = sorted(latencies)
    daily_means = list(day_cost.values())
    return {
        "n_calls": n,
        "daily_calls": {
            "mean": round(mean, 4),
            "std": round(std, 4),
            "min": min(daily_counts) if daily_counts else 0,
            "max": max(daily_counts) if daily_counts else 0,
            "by_day": dict(sorted(by_day.items())),
        },
        "endpoints": {"dist": ep_dist, "set": sorted(endpoints.keys())},
        "costs": {
            "daily_mean": round(statistics.mean(daily_means) if daily_means else 0.0, 8),
            "p25": round(_percentile(costs_s, 25), 8),
            "p50": round(_percentile(costs_s, 50), 8),
            "p75": round(_percentile(costs_s, 75), 8),
            "p95": round(_percentile(costs_s, 95), 8),
        },
        "latency": {
            "mean": round(statistics.mean(latencies) if latencies else 0.0, 3),
            "p95": round(_percentile(lats_s, 95), 3),
        },
        "models": {"dist": model_dist},
    }


def stats_hash(stats: Mapping[str, Any]) -> str:
    blob = json.dumps(stats, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return sha256_text(blob)


def deviation_hash(
    call_id: str, mark_type: str, deviation: Mapping[str, Any]
) -> str:
    blob = json.dumps(
        {"call_id": call_id, "mark_type": mark_type, "deviation": deviation},
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return sha256_text(blob)


def create_baseline(
    *,
    api_key: str,
    time_range: str = "7d",
    custom_from: Optional[str] = None,
    custom_to: Optional[str] = None,
    db_path=None,
) -> Dict[str, Any]:
    require_key(api_key, min_role="read_write", db_path=db_path, label="behavior")
    t0 = time.perf_counter()
    start, end = _range_bounds(time_range, custom_from=custom_from, custom_to=custom_to)
    calls = query_calls(api_key, ts_from=start, ts_to=end, limit=1000, db_path=db_path)
    stats = compute_stats(calls)
    bh = stats_hash(stats)
    baseline_id = f"bl_{uuid.uuid4().hex[:16]}"
    attest_id = f"att_{uuid.uuid4().hex[:16]}"
    ts = utc_now()
    duration_ms = (time.perf_counter() - t0) * 1000.0

    def _build(prev: str):
        chain_h = compute_baseline_chain_hash(
            prev_hash=prev,
            baseline_id=baseline_id,
            timestamp=ts,
            time_range_start=start,
            time_range_end=end,
            baseline_hash=bh,
        )
        return {
            "id": baseline_id,
            "attest_id": attest_id,
            "api_key": api_key,
            "timestamp": ts,
            "time_range_start": start,
            "time_range_end": end,
            "time_range_label": time_range,
            "stats": stats,
            "stats_json": json.dumps(stats, ensure_ascii=False, sort_keys=True),
            "baseline_hash": bh,
            "prev_hash": prev or GENESIS,
            "chain_hash": chain_h,
            "duration_ms": round(duration_ms, 3),
            "deleted": 0,
        }

    record = build_next_record(api_key, _build, db_path=db_path)
    insert_baseline(record, db_path=db_path)
    chain_h = record["chain_hash"]
    return {
        "baseline_id": baseline_id,
        "time_range_start": start,
        "time_range_end": end,
        "time_range_label": time_range,
        "stats": stats,
        "baseline_hash": bh,
        "chain_hash": chain_h,
        "prev_hash": record["prev_hash"],
        "timestamp": ts,
        "duration_ms": record["duration_ms"],
        "n_calls": stats["n_calls"],
    }


def _volume_threshold(mean: float, std: float) -> float:
    # Prefer over-marking: if std≈0, still flag 2x mean or mean+3
    if std <= 1e-9:
        return max(mean * 2.0, mean + 3.0, 1.0)
    return mean + 3.0 * std


def detect_drift(
    *,
    api_key: str,
    baseline_id: Optional[str] = None,
    window: str = "today",
    db_path=None,
) -> Dict[str, Any]:
    """Compare recent window to baseline; silently create pending drift marks."""
    require_key(api_key, min_role="read_write", db_path=db_path, label="behavior")
    t0 = time.perf_counter()
    if baseline_id:
        bl = get_baseline(baseline_id, db_path=db_path)
        if not bl or bl.get("api_key") != api_key or bl.get("deleted"):
            raise ValueError("baseline not found")
    else:
        bas = list_baselines(api_key, limit=1, include_deleted=False, db_path=db_path)
        if not bas:
            raise ValueError("no baseline — create one first")
        bl = bas[0]
        baseline_id = str(bl["id"])

    stats = bl.get("stats") or {}
    now = datetime.now(timezone.utc)
    if window == "yesterday":
        day = (now - timedelta(days=1)).strftime("%Y-%m-%d")
    else:
        day = now.strftime("%Y-%m-%d")
    win_from = f"{day}T00:00:00.000000Z"
    win_to = f"{day}T23:59:59.999999Z"
    recent = query_calls(
        api_key, ts_from=win_from, ts_to=win_to, limit=1000, db_path=db_path
    )

    existing = list_drift_marks(api_key, status=None, limit=500, db_path=db_path)
    existing_keys = {
        (str(m.get("call_id")), str(m.get("mark_type")))
        for m in existing
        if m.get("status") in ("pending", "reviewed", "ignored")
    }

    marks_out: List[Dict[str, Any]] = []
    daily = stats.get("daily_calls") or {}
    mean = float(daily.get("mean") or 0)
    std = float(daily.get("std") or 0)
    vol_thr = _volume_threshold(mean, std)
    volume_spike_day = len(recent) > vol_thr

    known_eps = set((stats.get("endpoints") or {}).get("set") or [])
    cost_p95 = float((stats.get("costs") or {}).get("p95") or 0)
    lat_p95 = float((stats.get("latency") or {}).get("p95") or 0)

    # Prefer recall: if p95 is 0, any positive cost/latency can mark
    if cost_p95 <= 0:
        cost_p95 = 1e-12
    if lat_p95 <= 0:
        lat_p95 = 1e-12

    candidates: List[Tuple[Mapping[str, Any], str, Dict[str, Any], str]] = []

    if volume_spike_day and recent:
        # Mark all calls in the spike window (assistive — over-mark OK)
        mult = (len(recent) / vol_thr) if vol_thr else float(len(recent))
        for c in recent:
            candidates.append(
                (
                    c,
                    "volume_spike",
                    {
                        "metric": "daily_call_count",
                        "baseline_value": vol_thr,
                        "current_value": len(recent),
                        "multiplier": round(mult, 3),
                        "message": (
                            f"日调用量 {len(recent)} 超出基线阈值 {vol_thr:.1f} "
                            f"（mean={mean:.1f}, std={std:.1f}）"
                        ),
                    },
                    f"日调用量超出基线 {mult:.1f}×",
                )
            )

    for c in recent:
        ep = str(c.get("endpoint") or "").strip() or "(empty)"
        if known_eps and ep not in known_eps:
            candidates.append(
                (
                    c,
                    "new_endpoint",
                    {
                        "metric": "endpoint",
                        "baseline_value": sorted(known_eps)[:20],
                        "current_value": ep,
                        "multiplier": 1.0,
                        "message": f"新端点 {ep} 未出现在基线集合中",
                    },
                    f"新端点: {ep}",
                )
            )
        cost = float(c.get("cost_usd") or 0)
        if cost > cost_p95:
            mult = cost / cost_p95
            candidates.append(
                (
                    c,
                    "cost_spike",
                    {
                        "metric": "cost_usd",
                        "baseline_value": cost_p95,
                        "current_value": cost,
                        "multiplier": round(mult, 3),
                        "message": f"费用 ${cost:.6f} 超出基线 P95 ${cost_p95:.6f} 的 {mult:.1f} 倍",
                    },
                    f"费用超出基线 P95 的 {mult:.1f} 倍",
                )
            )
        lat = float(c.get("duration_ms") or 0)
        if lat > lat_p95:
            mult = lat / lat_p95
            candidates.append(
                (
                    c,
                    "latency_drop",
                    {
                        "metric": "duration_ms",
                        "baseline_value": lat_p95,
                        "current_value": lat,
                        "multiplier": round(mult, 3),
                        "message": f"耗时 {lat:.1f}ms 超出基线 P95 {lat_p95:.1f}ms 的 {mult:.1f} 倍",
                    },
                    f"耗时超出基线 P95 的 {mult:.1f} 倍",
                )
            )

    for c, mark_type, deviation, _summary in candidates:
        call_id = str(c.get("id") or "")
        if not call_id:
            continue
        if (call_id, mark_type) in existing_keys:
            continue
        mark_h = deviation_hash(call_id, mark_type, deviation)
        mark_id = f"dm_{uuid.uuid4().hex[:16]}"
        attest_id = f"att_{uuid.uuid4().hex[:16]}"
        ts = utc_now()

        def _build(prev: str, _cid=call_id, _mt=mark_type, _mh=mark_h, _mid=mark_id, _aid=attest_id, _ts=ts, _dev=deviation, _c=c):
            chain_h = compute_drift_mark_chain_hash(
                prev_hash=prev,
                mark_id=_mid,
                timestamp=_ts,
                call_id=_cid,
                mark_type=_mt,
                baseline_id=str(baseline_id),
                mark_hash=_mh,
            )
            return {
                "id": _mid,
                "attest_id": _aid,
                "api_key": api_key,
                "timestamp": _ts,
                "call_id": _cid,
                "mark_type": _mt,
                "baseline_id": baseline_id,
                "deviation": _dev,
                "deviation_json": json.dumps(_dev, ensure_ascii=False, sort_keys=True),
                "status": "pending",
                "reviewed_by": None,
                "reviewed_at": None,
                "mark_hash": _mh,
                "prev_hash": prev or GENESIS,
                "chain_hash": chain_h,
                "call_endpoint": _c.get("endpoint"),
                "call_timestamp": _c.get("timestamp"),
                "call_cost_usd": _c.get("cost_usd"),
            }

        row = build_next_record(api_key, _build, db_path=db_path)
        insert_drift_mark(row, db_path=db_path)
        chain_h = row["chain_hash"]
        existing_keys.add((call_id, mark_type))
        marks_out.append(
            {
                "id": mark_id,
                "call_id": call_id,
                "mark_type": mark_type,
                "deviation": deviation,
                "status": "pending",
                "chain_hash": chain_h,
            }
        )

    duration_ms = (time.perf_counter() - t0) * 1000.0
    return {
        "baseline_id": baseline_id,
        "window": window,
        "window_day": day,
        "n_recent_calls": len(recent),
        "n_marks_created": len(marks_out),
        "marks": marks_out,
        "duration_ms": round(duration_ms, 3),
        "note": "silent marks only — no alerts, no blocking",
    }


def review_drift_mark(
    *,
    mark_id: str,
    api_key: str,
    status: str,
    reviewed_by: str = "dashboard_user",
    db_path=None,
) -> Dict[str, Any]:
    if status not in ("reviewed", "ignored"):
        raise ValueError("status must be reviewed or ignored")
    row = get_drift_mark(mark_id, db_path=db_path)
    if not row or row.get("api_key") != api_key:
        raise ValueError("mark not found")
    ts = utc_now()
    review_payload = {
        "mark_id": mark_id,
        "status": status,
        "reviewed_by": reviewed_by,
        "reviewed_at": ts,
    }
    review_h = sha256_text(
        json.dumps(review_payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    )
    attest_id = f"att_{uuid.uuid4().hex[:16]}"

    def _build(prev: str):
        chain_h = compute_drift_review_chain_hash(
            prev_hash=prev,
            mark_id=mark_id,
            timestamp=ts,
            status=status,
            reviewed_by=reviewed_by,
            review_hash=review_h,
        )
        return {
            "api_key": api_key,
            "prev_hash": prev or GENESIS,
            "chain_hash": chain_h,
        }

    link = build_next_record(api_key, _build, db_path=db_path)
    updated = update_drift_mark_review(
        mark_id,
        status=status,
        reviewed_by=reviewed_by,
        reviewed_at=ts,
        review_attest_id=attest_id,
        review_prev_hash=link["prev_hash"],
        review_chain_hash=link["chain_hash"],
        review_hash=review_h,
        db_path=db_path,
    )
    return {
        "mark": updated,
        "review": {
            "status": status,
            "reviewed_by": reviewed_by,
            "reviewed_at": ts,
            "review_hash": review_h,
            "chain_hash": link["chain_hash"],
            "prev_hash": link["prev_hash"],
        },
    }


def compare_baselines(
    older: Mapping[str, Any], newer: Mapping[str, Any]
) -> Dict[str, Any]:
    so = older.get("stats") or {}
    sn = newer.get("stats") or {}
    o_mean = float((so.get("daily_calls") or {}).get("mean") or 0)
    n_mean = float((sn.get("daily_calls") or {}).get("mean") or 0)
    growth = None
    if o_mean > 0:
        growth = round((n_mean - o_mean) / o_mean * 100.0, 1)
    o_eps = set((so.get("endpoints") or {}).get("set") or [])
    n_eps = set((sn.get("endpoints") or {}).get("set") or [])
    added = sorted(n_eps - o_eps)
    removed = sorted(o_eps - n_eps)
    summary_parts = []
    if growth is not None:
        summary_parts.append(f"日均调用量变化 {growth:+.1f}%")
    if added:
        summary_parts.append(f"新增 {len(added)} 个端点")
    if removed:
        summary_parts.append(f"消失 {len(removed)} 个端点")
    return {
        "older_id": older.get("id"),
        "newer_id": newer.get("id"),
        "daily_call_mean_older": o_mean,
        "daily_call_mean_newer": n_mean,
        "daily_call_growth_pct": growth,
        "endpoints_added": added,
        "endpoints_removed": removed,
        "cost_p95_older": (so.get("costs") or {}).get("p95"),
        "cost_p95_newer": (sn.get("costs") or {}).get("p95"),
        "summary": "；".join(summary_parts) or "无明显差异",
    }


def soft_delete(
    *, baseline_id: str, api_key: str, db_path=None
) -> Dict[str, Any]:
    row = get_baseline(baseline_id, db_path=db_path)
    if not row or row.get("api_key") != api_key:
        raise ValueError("baseline not found")
    soft_delete_baseline(baseline_id, db_path=db_path)
    return {"ok": True, "baseline_id": baseline_id, "deleted": True, "chain_retained": True}
