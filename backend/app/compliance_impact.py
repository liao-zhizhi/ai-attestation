"""Blast-radius / impact analysis for compliance check results.

Assigns impact factors (core / critical / general) and compares runs so
operators can see which changes invalidate which reports.
"""

from __future__ import annotations

from typing import Any, Dict, List, Mapping, Optional

IMPACT_LEVELS = ("core", "critical", "general")
IMPACT_LABELS_ZH = {
    "core": "核心",
    "critical": "关键",
    "general": "一般",
}

# Weights for failed checks when computing radius (0–100)
_FAIL_WEIGHT = {"core": 40.0, "critical": 18.0, "general": 5.0}
_REGRESS_WEIGHT = {"core": 25.0, "critical": 12.0, "general": 4.0}

_CORE_ID_NEEDLES = (
    "hash_chain",
    "chain",
    "attest",
    "integrity",
)
_CORE_CAT_NEEDLES = ("链", "证据", "完整性", "哈希")
_CRITICAL_NEEDLES = (
    "cost",
    "billing",
    "model",
    "coverage",
    "endpoint",
    "proxy",
    "compliance",
    "费用",
    "计费",
    "端点",
    "模型",
    "覆盖",
)


def _haystack(check: Mapping[str, Any], result: Mapping[str, Any]) -> str:
    parts = [
        str(check.get("group_id") or result.get("group_id") or ""),
        str(check.get("check_id") or result.get("check_id") or ""),
        str(check.get("category") or result.get("category") or ""),
        str(check.get("pass_rule") or result.get("pass_rule") or ""),
        str(check.get("requirement") or result.get("requirement") or ""),
    ]
    return " ".join(parts).lower()


def assign_impact_factor(check: dict, result: dict) -> dict:
    """Enrich a check result with impact_factor and impact_factor_zh."""
    out = dict(result)
    hay = _haystack(check or {}, out)
    cat = str((check or {}).get("category") or out.get("category") or "")

    level = "general"
    if any(n in hay for n in _CORE_ID_NEEDLES) or any(n in cat for n in _CORE_CAT_NEEDLES):
        level = "core"
    elif any(n in hay for n in _CRITICAL_NEEDLES) or any(
        n in cat.lower() for n in ("cost", "billing", "endpoint", "model", "proxy")
    ):
        level = "critical"

    out["impact_factor"] = level
    out["impact_factor_zh"] = IMPACT_LABELS_ZH[level]
    return out


def enrich_results_with_impact(check_results: dict) -> dict:
    """Return a new dict with every result carrying impact_factor fields."""
    enriched: Dict[str, Any] = {}
    for cid, raw in (check_results or {}).items():
        r = dict(raw or {})
        check_stub = {
            "check_id": r.get("check_id") or cid,
            "group_id": r.get("group_id"),
            "category": r.get("category"),
            "pass_rule": r.get("pass_rule"),
            "requirement": r.get("requirement"),
        }
        enriched[cid] = assign_impact_factor(check_stub, r)
    return enriched


def compute_impact_radius_score(check_results: Mapping[str, Any]) -> float:
    """0–100 score; core failures weigh most heavily."""
    score = 0.0
    for r in (check_results or {}).values():
        level = str(r.get("impact_factor") or "general")
        if level not in _FAIL_WEIGHT:
            level = "general"
        st = r.get("status")
        if st == "fail":
            score += _FAIL_WEIGHT[level]
        elif st == "manual":
            score += _FAIL_WEIGHT[level] * 0.25
    return round(min(100.0, score), 2)


def _impact_counts(check_results: Mapping[str, Any]) -> Dict[str, int]:
    counts = {k: 0 for k in IMPACT_LEVELS}
    fail_by = {k: 0 for k in IMPACT_LEVELS}
    for r in (check_results or {}).values():
        level = str(r.get("impact_factor") or "general")
        if level not in counts:
            level = "general"
        counts[level] += 1
        if r.get("status") == "fail":
            fail_by[level] += 1
    return {
        "n_core": counts["core"],
        "n_critical": counts["critical"],
        "n_general": counts["general"],
        "n_fail_core": fail_by["core"],
        "n_fail_critical": fail_by["critical"],
        "n_fail_general": fail_by["general"],
    }


def analyze_change_impact(
    *,
    older_results: Mapping[str, Any],
    newer_results: Mapping[str, Any],
    older_meta: Optional[Mapping[str, Any]] = None,
    newer_meta: Optional[Mapping[str, Any]] = None,
) -> dict:
    """Compare two result maps: status flips, affected checks, radius score."""
    older = enrich_results_with_impact(dict(older_results or {}))
    newer = enrich_results_with_impact(dict(newer_results or {}))
    older_meta = older_meta or {}
    newer_meta = newer_meta or {}

    ids = sorted(set(older) | set(newer))
    affected: List[Dict[str, Any]] = []
    radius_delta = 0.0

    for cid in ids:
        a = older.get(cid) or {}
        b = newer.get(cid) or {}
        sa = a.get("status")
        sb = b.get("status")
        if sa == sb and cid in older and cid in newer:
            continue
        level = str(
            b.get("impact_factor") or a.get("impact_factor") or "general"
        )
        if level not in IMPACT_LEVELS:
            level = "general"
        improved = sa == "fail" and sb == "pass"
        regressed = sa == "pass" and sb == "fail"
        added = cid not in older and cid in newer
        removed = cid in older and cid not in newer
        item = {
            "check_id": cid,
            "from": sa,
            "to": sb,
            "impact_factor": level,
            "impact_factor_zh": IMPACT_LABELS_ZH[level],
            "improved": improved,
            "regressed": regressed,
            "added": added,
            "removed": removed,
            "category": b.get("category") or a.get("category"),
            "requirement": b.get("requirement") or a.get("requirement"),
        }
        affected.append(item)
        if regressed or (added and sb == "fail") or (removed and sa == "pass"):
            radius_delta += _REGRESS_WEIGHT[level]
        elif improved:
            radius_delta -= _REGRESS_WEIGHT[level] * 0.5

    newer_radius = compute_impact_radius_score(newer)
    combined = round(min(100.0, max(0.0, newer_radius + max(0.0, radius_delta))), 2)

    older_id = older_meta.get("id") or older_meta.get("check_id")
    newer_id = newer_meta.get("id") or newer_meta.get("check_id")
    older_hash = older_meta.get("report_hash")
    newer_hash = newer_meta.get("report_hash")

    invalidated_hint = None
    if affected:
        core_hit = any(x["impact_factor"] == "core" for x in affected)
        invalidated_hint = (
            f"报告 {older_hash or older_id or '旧报告'} 中的 "
            f"{len(affected)} 项检查状态已变化"
            + (
                "；含核心完整性/哈希链项，建议作废旧报告并重新生成证据。"
                if core_hit
                else "；建议复核并更新验证包。"
            )
        )

    return {
        "older_id": older_id,
        "newer_id": newer_id,
        "older_report_hash": older_hash,
        "newer_report_hash": newer_hash,
        "n_affected": len(affected),
        "affected_checks": affected,
        "impact_radius_score": combined,
        "newer_impact_radius_score": newer_radius,
        "impact_counts": _impact_counts(newer),
        "invalidated_reports_hint": invalidated_hint,
        "change_summary": {
            "n_regressed": sum(1 for x in affected if x.get("regressed")),
            "n_improved": sum(1 for x in affected if x.get("improved")),
            "n_added": sum(1 for x in affected if x.get("added")),
            "n_removed": sum(1 for x in affected if x.get("removed")),
        },
    }


def impact_analysis_from_change(
    api_key: str,
    change: dict,
    db_path=None,
) -> dict:
    """Build impact analysis from check ids and/or simulated config changes."""
    from models import get_compliance

    change = dict(change or {})
    older_id = change.get("older_check_id")
    newer_id = change.get("newer_check_id")
    older_meta: Dict[str, Any] = {}
    newer_meta: Dict[str, Any] = {}
    older_results: Dict[str, Any] = {}
    newer_results: Dict[str, Any] = {}
    mode = "compare_stored"

    if older_id and newer_id:
        older = get_compliance(str(older_id), db_path=db_path)
        newer = get_compliance(str(newer_id), db_path=db_path)
        if not older or older.get("api_key") != api_key:
            raise ValueError(f"older check not found: {older_id}")
        if not newer or newer.get("api_key") != api_key:
            raise ValueError(f"newer check not found: {newer_id}")
        older_results = dict(older.get("check_results") or {})
        newer_results = dict(newer.get("check_results") or {})
        older_meta = {
            "id": older.get("id"),
            "report_hash": older.get("report_hash"),
            "standard": older.get("standard"),
        }
        newer_meta = {
            "id": newer.get("id"),
            "report_hash": newer.get("report_hash"),
            "standard": newer.get("standard"),
        }
    else:
        mode = "simulate"
        # Baseline: latest history for the standard if available, else empty
        from models import list_compliance

        std = change.get("new_standard")
        history = list_compliance(api_key, limit=50, db_path=db_path)
        if std:
            for row in history:
                if row.get("standard") == std:
                    older_results = dict(row.get("check_results") or {})
                    older_meta = {
                        "id": row.get("id"),
                        "report_hash": row.get("report_hash"),
                        "standard": row.get("standard"),
                    }
                    break
        elif history:
            row = history[0]
            older_results = dict(row.get("check_results") or {})
            older_meta = {
                "id": row.get("id"),
                "report_hash": row.get("report_hash"),
                "standard": row.get("standard"),
            }
            std = row.get("standard")

        newer_results = _simulate_newer_results(
            api_key=api_key,
            standard=std,
            template_yaml=change.get("template_yaml"),
            proxy_config=change.get("proxy_config"),
            db_path=db_path,
            fallback_older=older_results,
        )
        newer_meta = {
            "id": None,
            "report_hash": None,
            "standard": std,
            "simulated": True,
        }

    analysis = analyze_change_impact(
        older_results=older_results,
        newer_results=newer_results,
        older_meta=older_meta,
        newer_meta=newer_meta,
    )
    analysis["mode"] = mode
    analysis["api_key_suffix"] = api_key[-6:] if api_key else None
    if change.get("change_summary"):
        analysis["user_change_summary"] = change.get("change_summary")
    if change.get("new_standard"):
        analysis["new_standard"] = change.get("new_standard")
    if change.get("proxy_config") is not None:
        analysis["proxy_config_noted"] = True
    # Always guarantee these keys
    analysis.setdefault("affected_checks", [])
    analysis.setdefault(
        "impact_radius_score",
        compute_impact_radius_score(enrich_results_with_impact(newer_results)),
    )
    return analysis


def _simulate_newer_results(
    *,
    api_key: str,
    standard: Optional[str],
    template_yaml: Any,
    proxy_config: Any,
    db_path=None,
    fallback_older: Mapping[str, Any],
) -> Dict[str, Any]:
    """Best-effort live evaluation; falls back to tagging older results."""
    from compliance import run_one_check
    from compliance_catalog import get_standard

    results: Dict[str, Any] = {}

    if template_yaml:
        try:
            from compliance_catalog import _enrich
            from compliance_templates_loader import parse_template_yaml

            if isinstance(template_yaml, str):
                doc = parse_template_yaml(template_yaml)
            elif isinstance(template_yaml, Mapping):
                doc = dict(template_yaml)
            else:
                doc = None
            if doc:
                spec = _enrich(doc)
                for chk in spec.get("checks") or []:
                    cid = chk.get("check_id")
                    if not cid:
                        continue
                    results[cid] = run_one_check(chk, api_key=api_key, db_path=db_path)
                if results:
                    return enrich_results_with_impact(results)
        except Exception:
            pass

    if standard:
        try:
            spec = get_standard(str(standard), api_key=api_key)
            if spec:
                for chk in spec.get("checks") or []:
                    cid = chk.get("check_id")
                    if not cid:
                        continue
                    results[cid] = run_one_check(chk, api_key=api_key, db_path=db_path)
                if results:
                    return enrich_results_with_impact(results)
        except Exception:
            pass

    # Fallback: clone older and annotate hypothetical proxy/standard change
    cloned = enrich_results_with_impact(dict(fallback_older or {}))
    note = "simulated_change"
    if proxy_config is not None:
        note = "proxy_config_change"
    for cid, r in cloned.items():
        r = dict(r)
        r["simulation_note"] = note
        cloned[cid] = r
    return cloned


__all__ = [
    "IMPACT_LEVELS",
    "IMPACT_LABELS_ZH",
    "assign_impact_factor",
    "enrich_results_with_impact",
    "compute_impact_radius_score",
    "analyze_change_impact",
    "impact_analysis_from_change",
]
