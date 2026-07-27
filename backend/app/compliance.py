"""Compliance-as-code runner: execute checklist + append to unified hash chain.

Requirements become machine-checkable rules and evidence, not static PDFs.
"""

from __future__ import annotations

import json
import time
import uuid
from typing import Any, Dict, List, Mapping, Optional, Tuple

from anchoring import attach_timestamp_to_report
from attestation import (
    GENESIS,
    compute_compliance_chain_hash,
    sha256_text,
    utc_now,
)
from compliance_catalog import compare_standards, get_standard, list_standards
from models import (
    insert_compliance,
    list_calls,
    list_compliance,
    query_calls,
)
from key_auth import require_key
from write_buffer import build_next_record
from query_audit import normalize_params
from compliance_impact import (
    assign_impact_factor,
    compute_impact_radius_score,
    enrich_results_with_impact,
)
from compliance_guardrails import is_rule_check, run_rule_check


def results_report_hash(standard: str, check_results: Mapping[str, Any]) -> str:
    blob = json.dumps(
        {"standard": standard, "results": check_results},
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return sha256_text(blob)


def _fetch_by_template(
    api_key: str, template: Optional[Mapping[str, Any]], *, db_path=None
) -> List[Dict[str, Any]]:
    """Fetch calls for a compliance rule; auto-batch when limit > 1000."""
    if not template:
        return _batched_list_calls(api_key, limit=2000, db_path=db_path)
    params = normalize_params(dict(template))
    limit = int(params.get("limit") or 500)
    return _batched_query_calls(
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
        limit=limit,
        db_path=db_path,
    )


def _batched_list_calls(
    api_key: str, *, limit: int, db_path=None
) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    offset = 0
    chunk = 1000
    while offset < limit:
        n = min(chunk, limit - offset)
        rows = list_calls(api_key, limit=n, offset=offset, db_path=db_path)
        out.extend(rows)
        if len(rows) < n:
            break
        offset += n
    return out


def _batched_query_calls(api_key: str, *, limit: int, db_path=None, **kwargs) -> List[Dict[str, Any]]:
    if limit <= 1000:
        return query_calls(api_key, limit=limit, offset=0, db_path=db_path, **kwargs)
    out: List[Dict[str, Any]] = []
    offset = 0
    while offset < limit:
        n = min(1000, limit - offset)
        rows = query_calls(api_key, limit=n, offset=offset, db_path=db_path, **kwargs)
        out.extend(rows)
        if len(rows) < n:
            break
        offset += n
    return out


def _evidence_from_calls(rows: List[Dict[str, Any]], *, limit: int = 50) -> List[Dict[str, Any]]:
    out = []
    for r in rows[:limit]:
        out.append(
            {
                "call_id": r.get("id"),
                "timestamp": r.get("timestamp"),
                "endpoint": r.get("endpoint"),
                "chain_hash": r.get("chain_hash"),
                "status_code": r.get("status_code"),
            }
        )
    return out


def _eval_pass_rule(
    rule: str,
    rows: List[Dict[str, Any]],
    *,
    api_key: str,
    db_path=None,
) -> Tuple[str, str, List[Dict[str, Any]]]:
    """Return (status, detail, evidence) where status is pass|fail."""
    evidence = _evidence_from_calls(rows)

    if rule == "has_calls_with_required_fields":
        if not rows:
            return "fail", "过去 30 天无 API 调用记录", evidence
        missing = [
            r["id"]
            for r in rows
            if not r.get("timestamp")
            or not r.get("endpoint")
            or r.get("cost_usd") is None
            or not r.get("chain_hash")
        ]
        if missing:
            return "fail", f"{len(missing)} 条缺少必填审计字段", evidence
        return "pass", f"{len(rows)} 条调用具备时间/端点/费用/哈希", evidence

    if rule == "chain_integrity":
        from attestation import verify_key_chain

        proof = verify_key_chain(api_key, db_path=db_path)
        if proof.get("ok"):
            return (
                "pass",
                f"链完整 length={proof.get('chain_length')} latest={str(proof.get('latest_hash') or '')[:16]}…",
                [{"chain_length": proof.get("chain_length"), "latest_hash": proof.get("latest_hash")}],
            )
        return "fail", str(proof.get("message") or "chain broken"), [
            {"broken_at": proof.get("broken_at"), "message": proof.get("message")}
        ]

    if rule == "all_have_endpoint":
        if not rows:
            return "fail", "无调用可检查", evidence
        bad = [r["id"] for r in rows if not (r.get("endpoint") or "").strip()]
        if bad:
            return "fail", f"{len(bad)} 条缺少 endpoint", evidence
        return "pass", f"{len(rows)} 条均有 endpoint", evidence

    if rule == "model_coverage_ge_90":
        if not rows:
            return "fail", "无调用可检查", evidence
        ok_n = sum(1 for r in rows if (r.get("model") or "").strip())
        ratio = ok_n / len(rows)
        if ratio >= 0.9:
            return "pass", f"model 覆盖率 {ratio:.1%} (≥90%)", evidence
        return "fail", f"model 覆盖率 {ratio:.1%} (<90%)", evidence

    if rule == "all_have_cost":
        if not rows:
            return "fail", "无调用可检查", evidence
        bad = [r["id"] for r in rows if r.get("cost_usd") is None]
        if bad:
            return "fail", f"{len(bad)} 条缺少 cost_usd", evidence
        return "pass", f"{len(rows)} 条均有 cost_usd", evidence

    if rule == "failures_have_chain_or_none":
        if not rows:
            return "pass", "无失败调用（或窗口内无失败）", []
        bad = [r["id"] for r in rows if not r.get("chain_hash")]
        if bad:
            return "fail", f"{len(bad)} 条失败调用缺少 chain_hash", evidence
        return "pass", f"{len(rows)} 条失败调用均在哈希链中", evidence

    if rule == "all_have_body_hashes":
        if not rows:
            return "fail", "无调用可检查", evidence
        bad = [
            r["id"]
            for r in rows
            if not r.get("request_hash") or not r.get("response_hash")
        ]
        if bad:
            return "fail", f"{len(bad)} 条缺少 request/response hash", evidence
        return "pass", f"{len(rows)} 条均有 body 哈希", evidence

    return "fail", f"未知 pass_rule: {rule}", evidence


def run_one_check(
    check: Mapping[str, Any],
    *,
    api_key: str,
    db_path=None,
) -> Dict[str, Any]:
    base = {
        "check_id": check["check_id"],
        "group_id": check.get("group_id") or check["check_id"],
        "category": check.get("category"),
        "requirement": check.get("requirement"),
        "check_method": check.get("check_method"),
        "auto_check": bool(check.get("auto_check")),
        "query_template": check.get("query_template"),
        "pass_rule": check.get("pass_rule"),
        "how_to_satisfy": check.get("how_to_satisfy")
        or check.get("manual_guidance")
        or check.get("check_method"),
    }
    if not check.get("auto_check"):
        guidance = check.get("manual_guidance") or check.get("check_method")
        result = {
            **base,
            "status": "manual",
            "detail": "需要人工审查",
            "manual_guidance": guidance,
            "review_guidance": guidance,
            "fail_reason": None,
            "evidence": [],
            "evidence_summary": "人工审查项 — 无自动查询结果",
        }
        return assign_impact_factor(dict(check), result)

    qt = check.get("query_template")
    if is_rule_check(check):
        status, detail, evidence, n_matched = run_rule_check(
            check, api_key=api_key, db_path=db_path
        )
        fail_reason = detail if status in ("fail", "flag", "pending_audit") else None
        result = {
            **base,
            "type": "rule",
            "rule": check.get("rule"),
            "on_match": check.get("on_match"),
            "status": status,
            "detail": detail,
            "fail_reason": fail_reason,
            "evidence": evidence,
            "n_matched": n_matched,
            "evidence_summary": (
                f"护栏规则 → 匹配窗口内 {n_matched} 条；结果：{detail}"
            ),
        }
    else:
        rows = _fetch_by_template(api_key, qt, db_path=db_path)
        status, detail, evidence = _eval_pass_rule(
            str(check.get("pass_rule") or ""),
            rows,
            api_key=api_key,
            db_path=db_path,
        )
        fail_reason = detail if status == "fail" else None
        result = {
            **base,
            "status": status,
            "detail": detail,
            "fail_reason": fail_reason,
            "evidence": evidence,
            "n_matched": len(rows),
            "evidence_summary": (
                f"查询条件 {json.dumps(qt, ensure_ascii=False) if qt else '{}'} → "
                f"匹配 {len(rows)} 条；结果：{detail}"
            ),
        }
    return assign_impact_factor(dict(check), result)


def summarize(results: Mapping[str, Mapping[str, Any]]) -> Dict[str, int]:
    n_pass = n_fail = n_manual = 0
    for r in results.values():
        st = r.get("status")
        if st == "pass":
            n_pass += 1
        elif st in ("fail", "flag", "pending_audit"):
            n_fail += 1
        else:
            n_manual += 1
    return {
        "n_pass": n_pass,
        "n_fail": n_fail,
        "n_manual": n_manual,
        "n_total": len(results),
    }


def _persist_compliance_run(
    *,
    api_key: str,
    standard: str,
    spec: Mapping[str, Any],
    check_results: Dict[str, Dict[str, Any]],
    duration_ms: float,
    db_path=None,
) -> Dict[str, Any]:
    check_results = enrich_results_with_impact(check_results)
    stats = summarize(check_results)
    template_version = str(spec.get("version") or "0.0.0")
    template_source = str(spec.get("source") or "open")
    impact_radius = compute_impact_radius_score(check_results)
    impact_counts = {"core": 0, "critical": 0, "general": 0}
    for r in check_results.values():
        lvl = str(r.get("impact_factor") or "general")
        if lvl in impact_counts:
            impact_counts[lvl] += 1
    # Persist version inside summary for history traceability (no DB migration)
    stats_full = {
        **stats,
        "template_version": template_version,
        "template_source": template_source,
        "template_id": standard,
        "impact_radius_score": impact_radius,
        "impact_counts": impact_counts,
    }
    check_id = f"cmp_{uuid.uuid4().hex[:16]}"
    attest_id = f"att_{uuid.uuid4().hex[:16]}"
    ts = utc_now()
    report_h = results_report_hash(standard, check_results)

    def _build(prev: str):
        chain_h = compute_compliance_chain_hash(
            prev_hash=prev,
            check_id=check_id,
            timestamp=ts,
            standard=standard,
            report_hash=report_h,
        )
        return {
            "id": check_id,
            "attest_id": attest_id,
            "api_key": api_key,
            "timestamp": ts,
            "standard": standard,
            "standard_name": spec["name"],
            "check_results": check_results,
            "check_results_json": json.dumps(check_results, ensure_ascii=False, sort_keys=True),
            "summary": stats_full,
            "summary_json": json.dumps(stats_full, ensure_ascii=False, sort_keys=True),
            "report_hash": report_h,
            "prev_hash": prev or GENESIS,
            "chain_hash": chain_h,
            "duration_ms": round(duration_ms, 3),
        }

    record = build_next_record(api_key, _build, db_path=db_path)
    insert_compliance(record, db_path=db_path)
    chain_h = record["chain_hash"]
    out = {
        "check_id": check_id,
        "standard": standard,
        "standard_name": spec["name"],
        "timestamp": ts,
        "summary": stats_full,
        "check_results": check_results,
        "report_hash": report_h,
        "chain_hash": chain_h,
        "prev_hash": record["prev_hash"],
        "duration_ms": record["duration_ms"],
        "auto_coverage": spec["auto_coverage"],
        "template_version": template_version,
        "template_source": template_source,
    }
    return attach_timestamp_to_report(out)


def execute_compliance_check(
    *,
    api_key: str,
    standard: str | None = None,
    standards: List[str] | None = None,
    db_path=None,
) -> Dict[str, Any]:
    """Run one or many standards; overlapping group_id executed once and mapped."""
    require_key(api_key, min_role="read_write", db_path=db_path, label="compliance")
    ids: List[str] = []
    if standards:
        ids.extend([str(s) for s in standards if s])
    if standard:
        ids.append(str(standard))
    # dedupe preserve order
    seen: set = set()
    ordered: List[str] = []
    for sid in ids:
        if sid not in seen:
            seen.add(sid)
            ordered.append(sid)
    if not ordered:
        raise ValueError("standard or standards required")

    specs = []
    for sid in ordered:
        spec = get_standard(sid, api_key=api_key)
        if not spec:
            raise ValueError(f"unknown standard: {sid}")
        specs.append(spec)

    t0 = time.perf_counter()
    # Execute unique groups once
    group_cache: Dict[str, Dict[str, Any]] = {}
    for spec in specs:
        for chk in spec["checks"]:
            gid = str(chk.get("group_id") or chk["check_id"])
            if gid in group_cache:
                continue
            group_cache[gid] = run_one_check(chk, api_key=api_key, db_path=db_path)

    reports = []
    for spec in specs:
        check_results: Dict[str, Dict[str, Any]] = {}
        for chk in spec["checks"]:
            gid = str(chk.get("group_id") or chk["check_id"])
            cached = dict(group_cache[gid])
            cached["check_id"] = chk["check_id"]
            cached["group_id"] = gid
            check_results[chk["check_id"]] = cached
        # per-standard duration share
        elapsed = (time.perf_counter() - t0) * 1000.0
        reports.append(
            _persist_compliance_run(
                api_key=api_key,
                standard=spec["id"],
                spec=spec,
                check_results=check_results,
                duration_ms=elapsed,
                db_path=db_path,
            )
        )

    duration_ms = (time.perf_counter() - t0) * 1000.0
    if len(reports) == 1:
        out = dict(reports[0])
        out["n_groups_executed"] = len(group_cache)
        out["duration_ms"] = round(duration_ms, 3)
        return out
    return {
        "bundle": True,
        "standards": ordered,
        "n_groups_executed": len(group_cache),
        "duration_ms": round(duration_ms, 3),
        "reports": reports,
        "note": "重叠 group 只执行一次并映射到各标准报告",
    }


def gap_analysis(
    *,
    api_key: str,
    standards: List[str],
    db_path=None,
) -> Dict[str, Any]:
    """Compare target standards against latest stored check results (or evaluate live)."""
    require_key(api_key, min_role="read_write", db_path=db_path, label="compliance")
    if not standards:
        raise ValueError("standards required")

    # Latest result per standard from history
    history = list_compliance(api_key, limit=200, db_path=db_path)
    latest_by_std: Dict[str, Mapping[str, Any]] = {}
    for row in history:
        sid = str(row.get("standard") or "")
        if sid and sid not in latest_by_std:
            latest_by_std[sid] = row

    # Live-evaluate missing standards without persisting? User wants gap report —
    # use live run_one_check for missing, but don't write chain for gap-only.
    satisfied = []
    unsatisfied = []
    partial = []
    by_standard: Dict[str, Any] = {}

    for sid in standards:
        spec = get_standard(sid)
        if not spec:
            raise ValueError(f"unknown standard: {sid}")
        stored = latest_by_std.get(sid)
        results: Dict[str, Any] = {}
        if stored:
            results = dict(stored.get("check_results") or {})
            source = "history"
            run_id = stored.get("id")
        else:
            # live ephemeral evaluation
            for chk in spec["checks"]:
                results[chk["check_id"]] = run_one_check(
                    chk, api_key=api_key, db_path=db_path
                )
            source = "live_ephemeral"
            run_id = None

        s_ok = s_fail = s_man = []
        s_ok, s_fail, s_man = [], [], []
        for cid, r in results.items():
            item = {
                "standard": sid,
                "standard_name": spec["name"],
                "check_id": cid,
                "group_id": r.get("group_id"),
                "category": r.get("category"),
                "requirement": r.get("requirement"),
                "status": r.get("status"),
                "detail": r.get("detail"),
                "how_to_satisfy": r.get("how_to_satisfy")
                or r.get("manual_guidance")
                or r.get("check_method"),
            }
            st = r.get("status")
            if st == "pass":
                satisfied.append(item)
                s_ok.append(item)
            elif st in ("fail", "flag", "pending_audit"):
                # Align with summarize(): guardrail hits count as unsatisfied
                unsatisfied.append(item)
                s_fail.append(item)
            else:
                # manual = partial / needs review
                partial.append(item)
                s_man.append(item)

        by_standard[sid] = {
            "standard_name": spec["name"],
            "source": source,
            "run_id": run_id,
            "n_satisfied": len(s_ok),
            "n_unsatisfied": len(s_fail),
            "n_partial": len(s_man),
            "n_total": len(results),
        }

    return {
        "api_key_suffix": api_key[-6:],
        "target_standards": standards,
        "summary": {
            "n_satisfied": len(satisfied),
            "n_unsatisfied": len(unsatisfied),
            "n_partial": len(partial),
            "n_total": len(satisfied) + len(unsatisfied) + len(partial),
        },
        "by_standard": by_standard,
        "satisfied": satisfied,
        "unsatisfied": unsatisfied,
        "partial": partial,
        "disclaimer": "技术差距分析，不构成法律意见或合规效力保证。",
    }


def compare_compliance(
    older: Mapping[str, Any], newer: Mapping[str, Any]
) -> Dict[str, Any]:
    """Diff two compliance runs: which check_ids changed status."""
    a = older.get("check_results") or {}
    b = newer.get("check_results") or {}
    ids = sorted(set(a) | set(b))
    changes = []
    for cid in ids:
        sa = (a.get(cid) or {}).get("status")
        sb = (b.get(cid) or {}).get("status")
        if sa != sb:
            changes.append(
                {
                    "check_id": cid,
                    "from": sa,
                    "to": sb,
                    "improved": sa == "fail" and sb == "pass",
                    "regressed": sa == "pass" and sb == "fail",
                }
            )
    return {
        "older_id": older.get("id"),
        "newer_id": newer.get("id"),
        "n_changes": len(changes),
        "changes": changes,
    }


def report_to_text(report: Mapping[str, Any]) -> str:
    lines = [
        "ai-attestation — Compliance Report",
        f"standard: {report.get('standard_name') or report.get('standard')}",
        f"check_id: {report.get('id') or report.get('check_id')}",
        f"timestamp: {report.get('timestamp')}",
        f"report_hash: {report.get('report_hash')}",
        f"chain_hash: {report.get('chain_hash')}",
        f"prev_hash: {report.get('prev_hash')}",
        "",
    ]
    summary = report.get("summary") or {}
    lines.append(
        f"summary: pass={summary.get('n_pass')} fail={summary.get('n_fail')} "
        f"manual={summary.get('n_manual')} total={summary.get('n_total')}"
    )
    lines.append("")
    results = report.get("check_results") or {}
    for cid, r in results.items():
        lines.append(f"[{r.get('status')}] {cid}")
        lines.append(f"  category: {r.get('category')}")
        lines.append(f"  requirement: {r.get('requirement')}")
        lines.append(f"  detail: {r.get('detail')}")
        if r.get("manual_guidance"):
            lines.append(f"  guidance: {r.get('manual_guidance')}")
        ev = r.get("evidence") or []
        if ev:
            lines.append(f"  evidence: {json.dumps(ev, ensure_ascii=False)[:400]}")
        lines.append("")
    return "\n".join(lines)


def report_to_simple_pdf(text: str) -> bytes:
    """Minimal single-page text PDF (no external deps)."""
    # Escape PDF string specials
    safe = text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
    # Limit lines for one content stream
    content_lines = []
    y = 780
    for raw in safe.split("\n")[:90]:
        chunk = raw[:95]
        content_lines.append(f"BT /F1 9 Tf 40 {y} Td ({chunk}) Tj ET")
        y -= 12
        if y < 40:
            break
    stream = "\n".join(content_lines).encode("latin-1", errors="replace")
    objs = []
    objs.append(b"1 0 obj<< /Type /Catalog /Pages 2 0 R >>endobj\n")
    objs.append(b"2 0 obj<< /Type /Pages /Kids [3 0 R] /Count 1 >>endobj\n")
    objs.append(
        b"3 0 obj<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
        b"/Contents 4 0 R /Resources<< /Font<< /F1 5 0 R >> >> >>endobj\n"
    )
    objs.append(
        f"4 0 obj<< /Length {len(stream)} >>stream\n".encode()
        + stream
        + b"\nendstream\nendobj\n"
    )
    objs.append(b"5 0 obj<< /Type /Font /Subtype /Type1 /BaseFont /Courier >>endobj\n")
    out = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for obj in objs:
        offsets.append(len(out))
        out.extend(obj)
    xref_pos = len(out)
    out.extend(f"xref\n0 {len(offsets)}\n".encode())
    out.extend(b"0000000000 65535 f \n")
    for off in offsets[1:]:
        out.extend(f"{off:010d} 00000 n \n".encode())
    out.extend(
        f"trailer<< /Size {len(offsets)} /Root 1 0 R >>\nstartxref\n{xref_pos}\n%%EOF\n".encode()
    )
    return bytes(out)


def check_evidence_detail(
    report: Mapping[str, Any],
    check_id: str,
) -> Dict[str, Any]:
    """Deep-drill payload for one check item (evidence / fail reason / guidance)."""
    results = report.get("check_results") or {}
    item = results.get(check_id)
    if not item:
        # fuzzy: match suffix
        for cid, r in results.items():
            if cid == check_id or cid.endswith(check_id) or check_id.endswith(cid):
                item = r
                check_id = cid
                break
    if not item:
        raise ValueError(f"check not found: {check_id}")
    status = item.get("status")
    evidence = list(item.get("evidence") or [])
    return {
        "check_id": check_id,
        "status": status,
        "category": item.get("category"),
        "requirement": item.get("requirement"),
        "check_method": item.get("check_method"),
        "query_template": item.get("query_template"),
        "evidence_summary": item.get("evidence_summary") or item.get("detail"),
        "detail": item.get("detail"),
        "fail_reason": item.get("fail_reason")
        or (item.get("detail") if status == "fail" else None),
        "review_guidance": item.get("review_guidance")
        or item.get("manual_guidance")
        or (item.get("how_to_satisfy") if status == "manual" else None),
        "how_to_satisfy": item.get("how_to_satisfy"),
        "n_matched": item.get("n_matched"),
        "evidence": evidence,
        "n_evidence": len(evidence),
        "report_id": report.get("id") or report.get("check_id"),
        "template_version": (report.get("summary") or {}).get("template_version")
        or report.get("template_version"),
        "standard": report.get("standard"),
        "standard_name": report.get("standard_name"),
    }


__all__ = [
    "list_standards",
    "get_standard",
    "compare_standards",
    "execute_compliance_check",
    "gap_analysis",
    "compare_compliance",
    "report_to_text",
    "report_to_simple_pdf",
    "results_report_hash",
    "check_evidence_detail",
]
