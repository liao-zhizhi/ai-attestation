"""Unit tests for impact factors and programmable guardrail rules."""

from __future__ import annotations

import sys
from pathlib import Path

APP = Path(__file__).resolve().parents[1] / "app"
sys.path.insert(0, str(APP))

from compliance_guardrails import (  # noqa: E402
    eval_guardrail_rule,
    compute_field_metrics,
)
from compliance_impact import (  # noqa: E402
    IMPACT_LEVELS,
    assign_impact_factor,
    compute_impact_radius_score,
    enrich_results_with_impact,
    analyze_change_impact,
)


def test_assign_impact_factor_core_and_critical():
    assert IMPACT_LEVELS == ("core", "critical", "general")

    core = assign_impact_factor(
        {"check_id": "eu_hash_chain", "group_id": "hash_chain", "category": "安全"},
        {"check_id": "eu_hash_chain", "status": "fail"},
    )
    assert core["impact_factor"] == "core"
    assert core["impact_factor_zh"] == "核心"

    critical = assign_impact_factor(
        {"check_id": "cost_recorded", "group_id": "cost_recorded", "category": "计费"},
        {"check_id": "cost_recorded", "status": "pass", "pass_rule": "all_have_cost"},
    )
    assert critical["impact_factor"] == "critical"
    assert critical["impact_factor_zh"] == "关键"

    general = assign_impact_factor(
        {"check_id": "doc_review", "category": "治理"},
        {"check_id": "doc_review", "status": "manual"},
    )
    assert general["impact_factor"] == "general"
    assert general["impact_factor_zh"] == "一般"


def test_compute_impact_radius_weights_core_fails():
    results = enrich_results_with_impact(
        {
            "a": {
                "check_id": "hash_chain",
                "group_id": "hash_chain",
                "status": "fail",
            },
            "b": {
                "check_id": "misc",
                "category": "其他",
                "status": "fail",
            },
        }
    )
    score = compute_impact_radius_score(results)
    assert score >= 40  # at least one core fail
    assert score <= 100


def test_analyze_change_impact_lists_flips():
    older = {
        "hash_chain": {"check_id": "hash_chain", "group_id": "hash_chain", "status": "pass"},
        "x": {"check_id": "x", "status": "pass"},
    }
    newer = {
        "hash_chain": {"check_id": "hash_chain", "group_id": "hash_chain", "status": "fail"},
        "x": {"check_id": "x", "status": "pass"},
    }
    out = analyze_change_impact(
        older_results=older,
        newer_results=newer,
        older_meta={"id": "cmp_old", "report_hash": "aaa"},
        newer_meta={"id": "cmp_new", "report_hash": "bbb"},
    )
    assert out["n_affected"] == 1
    assert out["affected_checks"][0]["check_id"] == "hash_chain"
    assert out["affected_checks"][0]["regressed"] is True
    assert out["impact_radius_score"] >= 0
    assert out["invalidated_reports_hint"]


def test_eval_guardrail_call_count_gt():
    rows = [{"id": f"c{i}", "timestamp": "2026-07-20T12:00:00Z", "cost_usd": 0.1} for i in range(5)]
    status, detail, evidence = eval_guardrail_rule(
        {
            "all": [
                {"field": "call_count", "op": "gt", "value": 3},
            ]
        },
        rows,
        on_match="fail",
        detail_template="调用量超阈",
    )
    assert status == "fail"
    assert "调用量超阈" in detail
    assert evidence[0]["matched"] is True
    assert evidence[0]["actual"] == 5.0

    status2, _, ev2 = eval_guardrail_rule(
        {"all": [{"field": "call_count", "op": "gt", "value": 100}]},
        rows,
        on_match="fail",
    )
    assert status2 == "pass"
    assert ev2[0]["matched"] is False


def test_compute_field_metrics_basics():
    rows = [
        {"cost_usd": 1.0, "status_code": 200, "model": "a"},
        {"cost_usd": 3.0, "status_code": 500, "model": "b"},
    ]
    m = compute_field_metrics(rows)
    assert m["call_count"] == 2
    assert m["total_cost_usd"] == 4.0
    assert m["failure_count"] == 1
    assert m["unique_models"] == 2
    assert m["avg_cost"] == 2.0
