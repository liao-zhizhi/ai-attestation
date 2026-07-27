"""Programmable guardrail rules for compliance-as-code checks.

YAML `type: rule` checks evaluate aggregate metrics over a time window
(call_count, total_cost_usd, …) with AND/OR predicates.
"""

from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Mapping, Optional, Tuple

SUPPORTED_FIELDS = (
    "call_count",
    "total_cost_usd",
    "failure_count",
    "unique_models",
    "avg_cost",
)
SUPPORTED_OPS = ("gt", "gte", "lt", "lte", "eq")
_WINDOW_RE = re.compile(r"^(\d+)\s*([hdw])$", re.IGNORECASE)


def is_rule_check(check: Mapping[str, Any]) -> bool:
    if check.get("rule") is not None:
        return True
    t = str(check.get("type") or "").strip().lower()
    return t == "rule"


def parse_window(window: Optional[str]) -> timedelta:
    """Parse Nh / Nd / Nw into a timedelta (default 1d)."""
    raw = str(window or "1d").strip().lower()
    m = _WINDOW_RE.match(raw)
    if not m:
        # also accept query_audit style 7d / 30d already covered; fallback 1 day
        if raw in ("today",):
            return timedelta(days=1)
        return timedelta(days=1)
    n = int(m.group(1))
    unit = m.group(2).lower()
    if unit == "h":
        return timedelta(hours=n)
    if unit == "w":
        return timedelta(weeks=n)
    return timedelta(days=n)


def window_to_time_range(window: Optional[str]) -> str:
    """Map guardrail window to query_audit normalize_params time_range when possible."""
    raw = str(window or "1d").strip().lower()
    m = _WINDOW_RE.match(raw)
    if not m:
        return "7d"
    n = int(m.group(1))
    unit = m.group(2).lower()
    if unit == "d" and n == 7:
        return "7d"
    if unit == "d" and n == 30:
        return "30d"
    if unit == "d" and n == 1:
        return "today"
    # custom absolute range computed by caller
    return f"custom:{raw}"


def _parse_ts(value: Any) -> Optional[datetime]:
    if value is None:
        return None
    s = str(value).strip()
    if not s:
        return None
    try:
        if s.endswith("Z"):
            s = s[:-1] + "+00:00"
        return datetime.fromisoformat(s)
    except ValueError:
        return None


def filter_rows_by_window(
    rows: List[Dict[str, Any]], window: Optional[str]
) -> List[Dict[str, Any]]:
    delta = parse_window(window)
    now = datetime.now(timezone.utc)
    start = now - delta
    out = []
    for r in rows:
        ts = _parse_ts(r.get("timestamp"))
        if ts is None:
            # Unparseable timestamps must not inflate window metrics
            continue
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        if ts >= start:
            out.append(r)
    return out


def compute_field_metrics(rows: List[Dict[str, Any]]) -> Dict[str, float]:
    n = len(rows)
    total_cost = 0.0
    failures = 0
    models = set()
    for r in rows:
        c = r.get("cost_usd")
        if c is not None:
            try:
                total_cost += float(c)
            except (TypeError, ValueError):
                pass
        sc = r.get("status_code")
        try:
            if sc is not None and int(sc) >= 400:
                failures += 1
        except (TypeError, ValueError):
            pass
        m = (r.get("model") or "").strip()
        if m:
            models.add(m)
    avg = (total_cost / n) if n else 0.0
    return {
        "call_count": float(n),
        "total_cost_usd": float(total_cost),
        "failure_count": float(failures),
        "unique_models": float(len(models)),
        "avg_cost": float(avg),
    }


def _compare(op: str, left: float, right: float) -> bool:
    if op == "gt":
        return left > right
    if op == "gte":
        return left >= right
    if op == "lt":
        return left < right
    if op == "lte":
        return left <= right
    if op == "eq":
        return left == right
    raise ValueError(f"unsupported op: {op}")


def _eval_predicate(
    pred: Mapping[str, Any],
    rows: List[Dict[str, Any]],
    metrics_cache: Dict[str, Dict[str, float]],
) -> Tuple[bool, Dict[str, Any]]:
    field = str(pred.get("field") or "")
    op = str(pred.get("op") or "").lower()
    if field not in SUPPORTED_FIELDS:
        raise ValueError(f"unsupported field: {field}")
    if op not in SUPPORTED_OPS:
        raise ValueError(f"unsupported op: {op}")
    try:
        value = float(pred["value"])
    except (KeyError, TypeError, ValueError) as e:
        raise ValueError(f"rule value required for field {field}") from e

    window = pred.get("window")
    wkey = str(window or "__all__")
    if wkey not in metrics_cache:
        scoped = filter_rows_by_window(rows, window) if window else rows
        metrics_cache[wkey] = compute_field_metrics(scoped)
    metrics = metrics_cache[wkey]
    left = float(metrics.get(field, 0.0))
    ok = _compare(op, left, value)
    return ok, {
        "field": field,
        "op": op,
        "value": value,
        "window": window,
        "actual": left,
        "matched": ok,
    }


def eval_guardrail_rule(
    rule: Mapping[str, Any],
    rows: List[Dict[str, Any]],
    *,
    on_match: str = "fail",
    detail_template: Optional[str] = None,
) -> Tuple[str, str, List[Dict[str, Any]]]:
    """Evaluate a rule dict against call rows.

    Returns (status, detail, evidence) where status is pass|fail|flag|pending_audit.
    """
    rule = dict(rule or {})
    on_match = str(on_match or rule.get("on_match") or "fail").lower()
    if on_match not in ("fail", "flag", "pending_audit"):
        on_match = "fail"

    metrics_cache: Dict[str, Dict[str, float]] = {}
    evidence: List[Dict[str, Any]] = []
    matched = False

    if "all" in rule:
        preds = list(rule.get("all") or [])
        if not preds:
            return "pass", "空 all 规则视为通过", []
        oks = []
        for p in preds:
            ok, ev = _eval_predicate(p, rows, metrics_cache)
            evidence.append(ev)
            oks.append(ok)
        matched = all(oks)
        mode = "all"
    elif "any" in rule:
        preds = list(rule.get("any") or [])
        if not preds:
            return "pass", "空 any 规则视为通过", []
        oks = []
        for p in preds:
            ok, ev = _eval_predicate(p, rows, metrics_cache)
            evidence.append(ev)
            oks.append(ok)
        matched = any(oks)
        mode = "any"
    else:
        # single predicate at top level
        if rule.get("field"):
            ok, ev = _eval_predicate(rule, rows, metrics_cache)
            evidence.append(ev)
            matched = ok
            mode = "single"
        else:
            return "fail", "规则缺少 all/any/field", []

    default_detail = (
        f"护栏规则命中 ({mode})"
        if matched
        else f"护栏规则未命中 ({mode})"
    )
    detail = (detail_template or rule.get("detail_template") or default_detail).strip()
    if not matched:
        return "pass", detail if detail_template else f"护栏未触发 ({mode})", evidence

    if on_match == "flag":
        return "flag", detail, evidence
    if on_match == "pending_audit":
        return "pending_audit", detail, evidence
    return "fail", detail, evidence


def _rows_for_rule(
    api_key: str,
    *,
    query_template: Optional[Mapping[str, Any]] = None,
    window: Optional[str] = None,
    db_path=None,
) -> List[Dict[str, Any]]:
    from compliance import _fetch_by_template
    from query_audit import normalize_params

    tmpl: Dict[str, Any] = dict(query_template or {})
    if window and not tmpl.get("time_range") and not tmpl.get("ts_from"):
        tr = window_to_time_range(window)
        if tr.startswith("custom:"):
            delta = parse_window(window)
            now = datetime.now(timezone.utc)
            start = now - delta
            tmpl["time_range"] = "custom"
            tmpl["custom_from"] = start.strftime("%Y-%m-%dT%H:%M:%S.%fZ")
            tmpl["custom_to"] = None
        else:
            tmpl["time_range"] = tr
    if not tmpl:
        tmpl = {"time_range": window_to_time_range(window), "limit": 2000}
    else:
        tmpl.setdefault("limit", 2000)
    # normalize for side effects / validation
    normalize_params(tmpl)
    rows = _fetch_by_template(api_key, tmpl, db_path=db_path)
    if window:
        rows = filter_rows_by_window(rows, window)
    return rows


def run_rule_check(
    check: Mapping[str, Any],
    *,
    api_key: str,
    db_path=None,
) -> Tuple[str, str, List[Dict[str, Any]], int]:
    """Execute a rule-type check definition; returns status, detail, evidence, n_matched."""
    rule_body = check.get("rule")
    if isinstance(rule_body, Mapping):
        rule = dict(rule_body)
    else:
        rule = {}
    on_match = check.get("on_match") or rule.pop("on_match", None) or "fail"
    detail_template = (
        check.get("detail_template")
        or rule.pop("detail_template", None)
    )
    # Prefer outermost window hint from first predicate
    window = check.get("window")
    if not window:
        for key in ("all", "any"):
            for p in rule.get(key) or []:
                if isinstance(p, Mapping) and p.get("window"):
                    window = p.get("window")
                    break
            if window:
                break
    rows = _rows_for_rule(
        api_key,
        query_template=check.get("query_template"),
        window=window,
        db_path=db_path,
    )
    status, detail, evidence = eval_guardrail_rule(
        rule,
        rows,
        on_match=str(on_match),
        detail_template=detail_template,
    )
    return status, detail, evidence, len(rows)


def test_rule_against_history(
    api_key: str,
    rule: Mapping[str, Any],
    window: Optional[str] = None,
    db_path=None,
    *,
    query_template: Optional[Mapping[str, Any]] = None,
) -> dict:
    """Dry-run a rule against historical calls (test API)."""
    rule = dict(rule or {})
    on_match = rule.pop("on_match", None) or "fail"
    detail_template = rule.pop("detail_template", None)
    win = window or rule.get("window")
    rows = _rows_for_rule(
        api_key,
        query_template=query_template,
        window=win,
        db_path=db_path,
    )
    status, detail, evidence = eval_guardrail_rule(
        rule,
        rows,
        on_match=str(on_match),
        detail_template=detail_template,
    )
    metrics = compute_field_metrics(rows)
    return {
        "status": status,
        "detail": detail,
        "evidence": evidence,
        "n_matched": len(rows),
        "metrics": metrics,
        "window": win,
        "on_match": on_match,
    }


__all__ = [
    "SUPPORTED_FIELDS",
    "SUPPORTED_OPS",
    "is_rule_check",
    "parse_window",
    "eval_guardrail_rule",
    "run_rule_check",
    "test_rule_against_history",
    "compute_field_metrics",
    "filter_rows_by_window",
]
