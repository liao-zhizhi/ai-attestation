"""Tamper-evident hash chain for API call attestation.

Append-only event chain with SHA-256 digests; no raw PII bodies stored.
MVP uses an explicit prev_hash → chain_hash ledger.
"""

from __future__ import annotations

import hashlib
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

GENESIS = "0" * 64


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_text(text: str) -> str:
    return sha256_bytes(text.encode("utf-8"))


def compute_chain_hash(
    *,
    prev_hash: str,
    call_id: str,
    timestamp: str,
    endpoint: str,
    request_hash: str,
    response_hash: str,
    status_code: int,
    cost_usd: float,
) -> str:
    """Bind call metadata into the next hash-chain link (no request body)."""
    payload = "|".join(
        [
            prev_hash or GENESIS,
            call_id,
            timestamp,
            endpoint,
            request_hash,
            response_hash,
            str(status_code),
            f"{float(cost_usd):.8f}",
        ]
    )
    return sha256_text(payload)


def compute_query_chain_hash(
    *,
    prev_hash: str,
    query_id: str,
    timestamp: str,
    query_params_hash: str,
    result_count: int,
    result_hash: str,
) -> str:
    """Bind query-as-audit event into the unified hash chain."""
    payload = "|".join(
        [
            prev_hash or GENESIS,
            "query",
            query_id,
            timestamp,
            query_params_hash,
            str(int(result_count)),
            result_hash,
        ]
    )
    return sha256_text(payload)


def compute_compliance_chain_hash(
    *,
    prev_hash: str,
    check_id: str,
    timestamp: str,
    standard: str,
    report_hash: str,
) -> str:
    """Bind compliance-as-code run into the unified hash chain."""
    payload = "|".join(
        [
            prev_hash or GENESIS,
            "compliance",
            check_id,
            timestamp,
            standard,
            report_hash,
        ]
    )
    return sha256_text(payload)


def compute_baseline_chain_hash(
    *,
    prev_hash: str,
    baseline_id: str,
    timestamp: str,
    time_range_start: str,
    time_range_end: str,
    baseline_hash: str,
) -> str:
    """Bind behavior baseline snapshot into the unified hash chain."""
    payload = "|".join(
        [
            prev_hash or GENESIS,
            "baseline",
            baseline_id,
            timestamp,
            time_range_start,
            time_range_end,
            baseline_hash,
        ]
    )
    return sha256_text(payload)


def compute_drift_mark_chain_hash(
    *,
    prev_hash: str,
    mark_id: str,
    timestamp: str,
    call_id: str,
    mark_type: str,
    baseline_id: str,
    mark_hash: str,
) -> str:
    """Bind silent drift mark (record & prove, no alert)."""
    payload = "|".join(
        [
            prev_hash or GENESIS,
            "drift_mark",
            mark_id,
            timestamp,
            call_id,
            mark_type,
            baseline_id,
            mark_hash,
        ]
    )
    return sha256_text(payload)


def compute_drift_review_chain_hash(
    *,
    prev_hash: str,
    mark_id: str,
    timestamp: str,
    status: str,
    reviewed_by: str,
    review_hash: str,
) -> str:
    """Bind human review action on a drift mark."""
    payload = "|".join(
        [
            prev_hash or GENESIS,
            "drift_review",
            mark_id,
            timestamp,
            status,
            reviewed_by,
            review_hash,
        ]
    )
    return sha256_text(payload)


def _empty_verify() -> Dict[str, Any]:
    return {
        "ok": True,
        "chain_length": 0,
        "latest_hash": GENESIS,
        "broken_at": None,
        "message": "empty chain",
        "n_calls": 0,
        "n_queries": 0,
        "n_compliance": 0,
        "n_baselines": 0,
        "n_drift_marks": 0,
        "n_drift_reviews": 0,
    }


def verify_chain(links: Sequence[Mapping[str, Any]]) -> Dict[str, Any]:
    """Return integrity status for the unified attestation chain."""
    if not links:
        return _empty_verify()
    expected_prev = GENESIS
    counts = {
        "n_calls": 0,
        "n_queries": 0,
        "n_compliance": 0,
        "n_baselines": 0,
        "n_drift_marks": 0,
        "n_drift_reviews": 0,
    }

    def fail(i: int, et: str, msg: str, ref: Any) -> Dict[str, Any]:
        return {
            "ok": False,
            "chain_length": len(links),
            "latest_hash": str(links[-1].get("hash") or links[-1].get("chain_hash") or ""),
            "broken_at": i,
            "ref_id": ref,
            "event_type": et,
            "message": msg,
            **counts,
        }

    for i, link in enumerate(links):
        prev = str(link.get("prev_hash") or "")
        cur = str(link.get("hash") or link.get("chain_hash") or "")
        et = str(link.get("event_type") or "call")
        if prev != expected_prev:
            return fail(
                i,
                et,
                f"prev_hash mismatch at index {i}",
                link.get("ref_id") or link.get("call_id") or link.get("id"),
            )

        if et == "query":
            counts["n_queries"] += 1
            required = ("query_id", "timestamp", "query_hash", "result_count", "result_hash")
            if not all(k in link and link[k] is not None for k in required):
                return fail(
                    i,
                    "query",
                    f"query link missing required fields at index {i}",
                    link.get("query_id") or link.get("id"),
                )
            recomputed = compute_query_chain_hash(
                prev_hash=prev,
                query_id=str(link.get("query_id") or link.get("id") or ""),
                timestamp=str(link["timestamp"]),
                query_params_hash=str(link["query_hash"]),
                result_count=int(link["result_count"]),
                result_hash=str(link["result_hash"]),
            )
            if recomputed != cur:
                return fail(i, "query", f"query hash recompute failed at index {i}", link.get("query_id"))
        elif et == "compliance":
            counts["n_compliance"] += 1
            required = ("check_id", "timestamp", "standard", "report_hash")
            if not all(k in link and link[k] is not None for k in required):
                return fail(
                    i,
                    "compliance",
                    f"compliance link missing required fields at index {i}",
                    link.get("check_id") or link.get("id"),
                )
            recomputed = compute_compliance_chain_hash(
                prev_hash=prev,
                check_id=str(link.get("check_id") or link.get("id") or ""),
                timestamp=str(link["timestamp"]),
                standard=str(link["standard"]),
                report_hash=str(link["report_hash"]),
            )
            if recomputed != cur:
                return fail(i, "compliance", f"compliance hash recompute failed at index {i}", link.get("check_id"))
        elif et == "baseline":
            counts["n_baselines"] += 1
            required = (
                "baseline_id",
                "timestamp",
                "time_range_start",
                "time_range_end",
                "baseline_hash",
            )
            if not all(k in link and link[k] is not None for k in required):
                return fail(
                    i,
                    "baseline",
                    f"baseline link missing required fields at index {i}",
                    link.get("baseline_id") or link.get("id"),
                )
            recomputed = compute_baseline_chain_hash(
                prev_hash=prev,
                baseline_id=str(link.get("baseline_id") or link.get("id") or ""),
                timestamp=str(link["timestamp"]),
                time_range_start=str(link["time_range_start"]),
                time_range_end=str(link["time_range_end"]),
                baseline_hash=str(link["baseline_hash"]),
            )
            if recomputed != cur:
                return fail(i, "baseline", f"baseline hash recompute failed at index {i}", link.get("baseline_id"))
        elif et == "drift_mark":
            counts["n_drift_marks"] += 1
            required = (
                "mark_id",
                "timestamp",
                "call_id",
                "mark_type",
                "baseline_id",
                "mark_hash",
            )
            if not all(k in link and link[k] is not None for k in required):
                return fail(
                    i,
                    "drift_mark",
                    f"drift_mark link missing required fields at index {i}",
                    link.get("mark_id") or link.get("id"),
                )
            recomputed = compute_drift_mark_chain_hash(
                prev_hash=prev,
                mark_id=str(link.get("mark_id") or link.get("id") or ""),
                timestamp=str(link["timestamp"]),
                call_id=str(link["call_id"]),
                mark_type=str(link["mark_type"]),
                baseline_id=str(link["baseline_id"]),
                mark_hash=str(link["mark_hash"]),
            )
            if recomputed != cur:
                return fail(i, "drift_mark", f"drift_mark hash recompute failed at index {i}", link.get("mark_id"))
        elif et == "drift_review":
            counts["n_drift_reviews"] += 1
            required = ("mark_id", "timestamp", "status", "reviewed_by", "review_hash")
            if not all(k in link and link[k] is not None for k in required):
                return fail(
                    i,
                    "drift_review",
                    f"drift_review link missing required fields at index {i}",
                    link.get("mark_id"),
                )
            recomputed = compute_drift_review_chain_hash(
                prev_hash=prev,
                mark_id=str(link["mark_id"]),
                timestamp=str(link["timestamp"]),
                status=str(link["status"]),
                reviewed_by=str(link["reviewed_by"]),
                review_hash=str(link["review_hash"]),
            )
            if recomputed != cur:
                return fail(i, "drift_review", f"drift_review hash recompute failed at index {i}", link.get("mark_id"))
        else:
            counts["n_calls"] += 1
            required = (
                "call_id",
                "timestamp",
                "endpoint",
                "request_hash",
                "response_hash",
                "status_code",
                "cost_usd",
            )
            if not all(k in link and link[k] is not None for k in required):
                return fail(
                    i,
                    "call",
                    f"call link missing required fields at index {i}",
                    link.get("call_id") or link.get("id"),
                )
            recomputed = compute_chain_hash(
                prev_hash=prev,
                call_id=str(link["call_id"]),
                timestamp=str(link["timestamp"]),
                endpoint=str(link["endpoint"]),
                request_hash=str(link["request_hash"]),
                response_hash=str(link["response_hash"]),
                status_code=int(link["status_code"]),
                cost_usd=round(float(link["cost_usd"]), 8),
            )
            if recomputed != cur:
                return fail(i, "call", f"call hash recompute failed at index {i}", link.get("call_id"))
        expected_prev = cur
    return {
        "ok": True,
        "chain_length": len(links),
        "latest_hash": str(links[-1].get("hash") or links[-1].get("chain_hash") or ""),
        "broken_at": None,
        "message": "chain intact",
        **counts,
    }


def new_ids() -> Tuple[str, str]:
    return f"call_{uuid.uuid4().hex[:16]}", f"att_{uuid.uuid4().hex[:16]}"


def build_call_record(
    *,
    api_key: str,
    prev_hash: str,
    endpoint: str,
    method: str,
    model: Optional[str],
    status_code: int,
    request_body: bytes,
    response_body: bytes,
    duration_ms: float,
    prompt_tokens: int,
    completion_tokens: int,
    cost_usd: float,
    vendor: Optional[str] = None,
) -> Dict[str, Any]:
    call_id, attest_id = new_ids()
    ts = utc_now()
    req_h = sha256_bytes(request_body)
    res_h = sha256_bytes(response_body)
    prev = prev_hash or GENESIS
    # Round once before hashing so stored cost matches chain payload
    cost_r = round(float(cost_usd), 8)
    chain_h = compute_chain_hash(
        prev_hash=prev,
        call_id=call_id,
        timestamp=ts,
        endpoint=endpoint,
        request_hash=req_h,
        response_hash=res_h,
        status_code=status_code,
        cost_usd=cost_r,
    )
    return {
        "id": call_id,
        "attest_id": attest_id,
        "api_key": api_key,
        "timestamp": ts,
        "endpoint": endpoint,
        "method": method,
        "model": model,
        "vendor": vendor or "openai",
        "status_code": status_code,
        "request_size": len(request_body),
        "response_size": len(response_body),
        "duration_ms": round(duration_ms, 3),
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "cost_usd": cost_r,
        "request_hash": req_h,
        "response_hash": res_h,
        "prev_hash": prev,
        "chain_hash": chain_h,
    }


def verify_call_links(
    calls: Sequence[Mapping[str, Any]],
) -> Dict[str, Any]:
    """Verify using full api_calls rows (includes fields for recompute).

    Walks by prev_hash → chain_hash (not timestamp/id lexicographic order),
    so same-timestamp or out-of-order ids still verify correctly.
    """
    by_prev: Dict[str, List[Mapping[str, Any]]] = {}
    for c in calls:
        prev = str(c.get("prev_hash") or GENESIS)
        by_prev.setdefault(prev, []).append(c)

    ordered: List[Mapping[str, Any]] = []
    seen: set[str] = set()
    cur_prev = GENESIS
    while cur_prev in by_prev:
        nxts = [c for c in by_prev[cur_prev] if str(c.get("chain_hash") or "") not in seen]
        if not nxts:
            break
        # Deterministic pick on fork; verify_chain will fail remaining orphans
        nxts.sort(key=lambda c: (str(c.get("timestamp") or ""), str(c.get("id") or "")))
        c = nxts[0]
        ch = str(c.get("chain_hash") or "")
        ordered.append(c)
        if ch:
            seen.add(ch)
        cur_prev = ch

    # Orphans / fork siblings — append so integrity fails closed
    for c in sorted(calls, key=lambda x: (str(x.get("timestamp") or ""), str(x.get("id") or ""))):
        ch = str(c.get("chain_hash") or "")
        if ch not in seen:
            ordered.append(c)
            if ch:
                seen.add(ch)

    links: List[Dict[str, Any]] = []
    for c in ordered:
        links.append(
            {
                "event_type": "call",
                "call_id": c.get("id"),
                "hash": c.get("chain_hash"),
                "prev_hash": c.get("prev_hash"),
                "timestamp": c.get("timestamp"),
                "endpoint": c.get("endpoint"),
                "request_hash": c.get("request_hash"),
                "response_hash": c.get("response_hash"),
                "status_code": c.get("status_code"),
                "cost_usd": c.get("cost_usd"),
            }
        )
    return verify_chain(links)


def verify_single_call(call: Mapping[str, Any]) -> Dict[str, Any]:
    """Recompute one link without requiring the full chain in memory."""
    prev = str(call.get("prev_hash") or GENESIS)
    expected = compute_chain_hash(
        prev_hash=prev,
        call_id=str(call.get("id") or ""),
        timestamp=str(call.get("timestamp") or ""),
        endpoint=str(call.get("endpoint") or ""),
        request_hash=str(call.get("request_hash") or ""),
        response_hash=str(call.get("response_hash") or ""),
        status_code=int(call.get("status_code") or 0),
        cost_usd=round(float(call.get("cost_usd") or 0), 8),
    )
    actual = str(call.get("chain_hash") or "")
    ok = expected == actual
    return {
        "ok": ok,
        "expected_hash": expected,
        "actual_hash": actual,
        "prev_hash": prev,
        "message": "link intact" if ok else "link hash mismatch",
    }


def verify_single_query(query: Mapping[str, Any]) -> Dict[str, Any]:
    prev = str(query.get("prev_hash") or GENESIS)
    expected = compute_query_chain_hash(
        prev_hash=prev,
        query_id=str(query.get("id") or ""),
        timestamp=str(query.get("timestamp") or ""),
        query_params_hash=str(query.get("query_hash") or ""),
        result_count=int(query.get("result_count") or 0),
        result_hash=str(query.get("result_hash") or ""),
    )
    actual = str(query.get("chain_hash") or "")
    ok = expected == actual
    return {
        "ok": ok,
        "expected_hash": expected,
        "actual_hash": actual,
        "prev_hash": prev,
        "message": "query link intact" if ok else "query link hash mismatch",
    }


def verify_single_compliance(row: Mapping[str, Any]) -> Dict[str, Any]:
    prev = str(row.get("prev_hash") or GENESIS)
    expected = compute_compliance_chain_hash(
        prev_hash=prev,
        check_id=str(row.get("id") or ""),
        timestamp=str(row.get("timestamp") or ""),
        standard=str(row.get("standard") or ""),
        report_hash=str(row.get("report_hash") or ""),
    )
    actual = str(row.get("chain_hash") or "")
    ok = expected == actual
    return {
        "ok": ok,
        "expected_hash": expected,
        "actual_hash": actual,
        "prev_hash": prev,
        "message": "compliance link intact" if ok else "compliance link hash mismatch",
    }


def verify_single_baseline(row: Mapping[str, Any]) -> Dict[str, Any]:
    prev = str(row.get("prev_hash") or GENESIS)
    expected = compute_baseline_chain_hash(
        prev_hash=prev,
        baseline_id=str(row.get("id") or ""),
        timestamp=str(row.get("timestamp") or ""),
        time_range_start=str(row.get("time_range_start") or ""),
        time_range_end=str(row.get("time_range_end") or ""),
        baseline_hash=str(row.get("baseline_hash") or ""),
    )
    actual = str(row.get("chain_hash") or "")
    ok = expected == actual
    return {
        "ok": ok,
        "expected_hash": expected,
        "actual_hash": actual,
        "prev_hash": prev,
        "message": "baseline link intact" if ok else "baseline link hash mismatch",
    }


def verify_single_drift_mark(row: Mapping[str, Any]) -> Dict[str, Any]:
    prev = str(row.get("prev_hash") or GENESIS)
    expected = compute_drift_mark_chain_hash(
        prev_hash=prev,
        mark_id=str(row.get("id") or ""),
        timestamp=str(row.get("timestamp") or ""),
        call_id=str(row.get("call_id") or ""),
        mark_type=str(row.get("mark_type") or ""),
        baseline_id=str(row.get("baseline_id") or ""),
        mark_hash=str(row.get("mark_hash") or ""),
    )
    actual = str(row.get("chain_hash") or "")
    ok = expected == actual
    return {
        "ok": ok,
        "expected_hash": expected,
        "actual_hash": actual,
        "prev_hash": prev,
        "message": "drift_mark link intact" if ok else "drift_mark link hash mismatch",
    }


def verify_unified_records(
    calls: Sequence[Mapping[str, Any]],
    queries: Sequence[Mapping[str, Any]],
    compliance: Sequence[Mapping[str, Any]] | None = None,
    baselines: Sequence[Mapping[str, Any]] | None = None,
    drift_marks: Sequence[Mapping[str, Any]] | None = None,
) -> Dict[str, Any]:
    """Merge event rows by prev_hash walk. Prefer verify_chain_rows when possible."""
    by_hash: Dict[str, Dict[str, Any]] = {}
    for c in calls:
        link = {
            "event_type": "call",
            "call_id": c.get("id"),
            "hash": c.get("chain_hash"),
            "prev_hash": c.get("prev_hash"),
            "timestamp": c.get("timestamp"),
            "endpoint": c.get("endpoint"),
            "request_hash": c.get("request_hash"),
            "response_hash": c.get("response_hash"),
            "status_code": c.get("status_code"),
            "cost_usd": c.get("cost_usd"),
        }
        by_hash[str(link["hash"])] = link
    for q in queries:
        link = {
            "event_type": "query",
            "query_id": q.get("id"),
            "id": q.get("id"),
            "hash": q.get("chain_hash"),
            "prev_hash": q.get("prev_hash"),
            "timestamp": q.get("timestamp"),
            "query_hash": q.get("query_hash"),
            "result_count": q.get("result_count"),
            "result_hash": q.get("result_hash"),
        }
        by_hash[str(link["hash"])] = link
    for cmp in compliance or []:
        link = {
            "event_type": "compliance",
            "check_id": cmp.get("id"),
            "id": cmp.get("id"),
            "hash": cmp.get("chain_hash"),
            "prev_hash": cmp.get("prev_hash"),
            "timestamp": cmp.get("timestamp"),
            "standard": cmp.get("standard"),
            "report_hash": cmp.get("report_hash"),
        }
        by_hash[str(link["hash"])] = link
    for b in baselines or []:
        link = {
            "event_type": "baseline",
            "baseline_id": b.get("id"),
            "id": b.get("id"),
            "hash": b.get("chain_hash"),
            "prev_hash": b.get("prev_hash"),
            "timestamp": b.get("timestamp"),
            "time_range_start": b.get("time_range_start"),
            "time_range_end": b.get("time_range_end"),
            "baseline_hash": b.get("baseline_hash"),
        }
        by_hash[str(link["hash"])] = link
    for m in drift_marks or []:
        link = {
            "event_type": "drift_mark",
            "mark_id": m.get("id"),
            "id": m.get("id"),
            "hash": m.get("chain_hash"),
            "prev_hash": m.get("prev_hash"),
            "timestamp": m.get("timestamp"),
            "call_id": m.get("call_id"),
            "mark_type": m.get("mark_type"),
            "baseline_id": m.get("baseline_id"),
            "mark_hash": m.get("mark_hash"),
        }
        by_hash[str(link["hash"])] = link
        if m.get("review_chain_hash"):
            rlink = {
                "event_type": "drift_review",
                "mark_id": m.get("id"),
                "hash": m.get("review_chain_hash"),
                "prev_hash": m.get("review_prev_hash"),
                "timestamp": m.get("reviewed_at"),
                "status": m.get("status"),
                "reviewed_by": m.get("reviewed_by"),
                "review_hash": m.get("review_hash"),
            }
            by_hash[str(rlink["hash"])] = rlink
    children: Dict[str, List[str]] = {}
    for h, link in by_hash.items():
        children.setdefault(str(link.get("prev_hash") or GENESIS), []).append(h)
    ordered: List[Dict[str, Any]] = []
    frontier = list(children.get(GENESIS, []))
    seen = set()
    while frontier:
        h = frontier.pop(0)
        if h in seen:
            continue
        seen.add(h)
        ordered.append(by_hash[h])
        frontier.extend(children.get(h, []))
    if len(ordered) != len(by_hash):
        ordered = sorted(
            by_hash.values(),
            key=lambda x: (str(x.get("timestamp") or ""), str(x.get("hash") or "")),
        )
    return verify_chain(ordered)


def verify_chain_rows(
    chain_rows: Sequence[Mapping[str, Any]],
    *,
    calls_by_id: Mapping[str, Mapping[str, Any]],
    queries_by_id: Mapping[str, Mapping[str, Any]],
    compliance_by_id: Mapping[str, Mapping[str, Any]] | None = None,
    baselines_by_id: Mapping[str, Mapping[str, Any]] | None = None,
    drift_marks_by_id: Mapping[str, Mapping[str, Any]] | None = None,
) -> Dict[str, Any]:
    """Verify using attestation_chain insertion order + enriched rows."""
    compliance_by_id = compliance_by_id or {}
    baselines_by_id = baselines_by_id or {}
    drift_marks_by_id = drift_marks_by_id or {}
    links: List[Dict[str, Any]] = []
    for row in chain_rows:
        et = str(row.get("event_type") or "call")
        ref = str(row.get("ref_id") or row.get("call_id") or "")
        base: Dict[str, Any] = {
            "event_type": et,
            "hash": row.get("hash"),
            "prev_hash": row.get("prev_hash"),
            "timestamp": row.get("timestamp"),
            "ref_id": ref,
        }
        if et == "query":
            q = queries_by_id.get(ref) or {}
            base.update(
                {
                    "query_id": q.get("id") or ref,
                    "id": q.get("id") or ref,
                    "query_hash": q.get("query_hash"),
                    "result_count": q.get("result_count"),
                    "result_hash": q.get("result_hash"),
                    "timestamp": q.get("timestamp") or row.get("timestamp"),
                    "hash": q.get("chain_hash") or row.get("hash"),
                    "prev_hash": q.get("prev_hash") or row.get("prev_hash"),
                }
            )
        elif et == "compliance":
            c = compliance_by_id.get(ref) or {}
            base.update(
                {
                    "check_id": c.get("id") or ref,
                    "id": c.get("id") or ref,
                    "standard": c.get("standard"),
                    "report_hash": c.get("report_hash"),
                    "timestamp": c.get("timestamp") or row.get("timestamp"),
                    "hash": c.get("chain_hash") or row.get("hash"),
                    "prev_hash": c.get("prev_hash") or row.get("prev_hash"),
                }
            )
        elif et == "baseline":
            b = baselines_by_id.get(ref) or {}
            base.update(
                {
                    "baseline_id": b.get("id") or ref,
                    "id": b.get("id") or ref,
                    "time_range_start": b.get("time_range_start"),
                    "time_range_end": b.get("time_range_end"),
                    "baseline_hash": b.get("baseline_hash"),
                    "timestamp": b.get("timestamp") or row.get("timestamp"),
                    "hash": b.get("chain_hash") or row.get("hash"),
                    "prev_hash": b.get("prev_hash") or row.get("prev_hash"),
                }
            )
        elif et == "drift_mark":
            m = drift_marks_by_id.get(ref) or {}
            base.update(
                {
                    "mark_id": m.get("id") or ref,
                    "id": m.get("id") or ref,
                    "call_id": m.get("call_id"),
                    "mark_type": m.get("mark_type"),
                    "baseline_id": m.get("baseline_id"),
                    "mark_hash": m.get("mark_hash"),
                    "timestamp": m.get("timestamp") or row.get("timestamp"),
                    "hash": m.get("chain_hash") or row.get("hash"),
                    "prev_hash": m.get("prev_hash") or row.get("prev_hash"),
                }
            )
        elif et == "drift_review":
            # Review fields live on the mark row (review_* columns) or chain metadata
            m = drift_marks_by_id.get(ref) or {}
            base.update(
                {
                    "mark_id": m.get("id") or ref,
                    "status": m.get("status") or m.get("review_status"),
                    "reviewed_by": m.get("reviewed_by"),
                    "review_hash": m.get("review_hash"),
                    "timestamp": m.get("reviewed_at") or row.get("timestamp"),
                    "hash": m.get("review_chain_hash") or row.get("hash"),
                    "prev_hash": m.get("review_prev_hash") or row.get("prev_hash"),
                }
            )
        else:
            c = calls_by_id.get(ref) or {}
            base.update(
                {
                    "call_id": c.get("id") or ref,
                    "endpoint": c.get("endpoint"),
                    "request_hash": c.get("request_hash"),
                    "response_hash": c.get("response_hash"),
                    "status_code": c.get("status_code"),
                    "cost_usd": c.get("cost_usd"),
                    "timestamp": c.get("timestamp") or row.get("timestamp"),
                    "hash": c.get("chain_hash") or row.get("hash"),
                    "prev_hash": c.get("prev_hash") or row.get("prev_hash"),
                }
            )
        links.append(base)
    return verify_chain(links)


def verify_key_chain(api_key: str, *, db_path=None) -> Dict[str, Any]:
    """Full-chain integrity check with per-ref enrichment (no tip-window gaps)."""
    from models import enrich_maps_for_chain, list_chain

    chain = list_chain(api_key, limit=None, db_path=db_path)
    maps = enrich_maps_for_chain(api_key, chain, db_path=db_path)
    return verify_chain_rows(
        chain,
        calls_by_id=maps["calls_by_id"],
        queries_by_id=maps["queries_by_id"],
        compliance_by_id=maps["compliance_by_id"],
        baselines_by_id=maps["baselines_by_id"],
        drift_marks_by_id=maps["drift_marks_by_id"],
    )
