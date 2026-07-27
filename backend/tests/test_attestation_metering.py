"""Smoke tests for attestation + query-as-audit + compliance-as-code."""

from __future__ import annotations

import sys
from pathlib import Path

APP = Path(__file__).resolve().parents[1] / "app"
sys.path.insert(0, str(APP))

from attestation import (  # noqa: E402
    GENESIS,
    build_call_record,
    verify_call_links,
    verify_chain_rows,
    verify_key_chain,
    verify_single_baseline,
    verify_single_call,
    verify_single_compliance,
    verify_single_drift_mark,
    verify_single_query,
    verify_unified_records,
)
from behavior import (  # noqa: E402
    compare_baselines,
    create_baseline,
    detect_drift,
    review_drift_mark,
    soft_delete,
)
from compliance import compare_compliance, execute_compliance_check  # noqa: E402
from compliance_catalog import STANDARD_EU_AI_ACT_TRANSPARENCY, list_standards  # noqa: E402
from metering import estimate_cost_usd, meter_from_response_bytes  # noqa: E402
from models import (  # noqa: E402
    ensure_api_key,
    init_db,
    insert_call,
    latest_chain_hash,
    list_baselines,
    list_calls,
    list_chain,
    list_compliance,
    list_drift_marks,
    list_queries,
)
from query_audit import execute_attested_query  # noqa: E402


def _seed_calls(db, key: str, n: int = 3):
    ensure_api_key(key, label="test", role="admin", db_path=db)
    prev = GENESIS
    records = []
    for i in range(n):
        req = f'{{"model":"gpt-4o-mini","n":{i}}}'.encode()
        res = b'{"model":"gpt-4o-mini","usage":{"prompt_tokens":100,"completion_tokens":50}}'
        meter = meter_from_response_bytes(res, request_model="gpt-4o-mini")
        rec = build_call_record(
            api_key=key,
            prev_hash=prev,
            endpoint="/v1/chat/completions" if i % 2 == 0 else "/v1/embeddings",
            method="POST",
            model=meter["model"] if i < 2 else "gpt-4",
            status_code=200 if i < 2 else 500,
            request_body=req,
            response_body=res,
            duration_ms=10.0 + i,
            prompt_tokens=meter["prompt_tokens"],
            completion_tokens=meter["completion_tokens"],
            cost_usd=meter["cost_usd"] * (i + 1),
        )
        insert_call(rec, db_path=db)
        assert verify_single_call(rec)["ok"]
        prev = rec["chain_hash"]
        records.append(rec)
    return records


def test_long_chain_full_verify(tmp_path):
    """Tip-window list_chain must not break full-chain integrity checks."""
    db = tmp_path / "long.db"
    init_db(db)
    key = "ata_test_key_long_chain"
    n = 60
    _seed_calls(db, key, n)
    tip_window = list_chain(key, limit=20, db_path=db)
    assert len(tip_window) == 20
    assert tip_window[0]["prev_hash"] != GENESIS
    proof = verify_key_chain(key, db_path=db)
    assert proof["ok"] is True
    assert proof["chain_length"] == n
    assert proof["n_calls"] == n


def test_hash_chain_and_meter(tmp_path):
    db = tmp_path / "t.db"
    init_db(db)
    key = "ata_test_key_001"
    records = _seed_calls(db, key, 3)

    assert latest_chain_hash(key, db_path=db) == records[-1]["chain_hash"]
    calls = list_calls(key, db_path=db)
    proof = verify_call_links(calls)
    assert proof["ok"] is True
    assert proof["chain_length"] == 3

    calls[0]["chain_hash"] = "deadbeef" * 8
    broken = verify_call_links(calls)
    assert broken["ok"] is False

    cost = estimate_cost_usd(model="gpt-4o-mini", prompt_tokens=1_000_000, completion_tokens=0)
    assert abs(cost - 0.15) < 1e-9


def test_query_as_audit_unified_chain(tmp_path):
    db = tmp_path / "q.db"
    init_db(db)
    key = "ata_test_key_query"
    _seed_calls(db, key, 5)

    out = execute_attested_query(
        api_key=key,
        raw_params={"time_range": "all", "endpoint": "chat/completions", "status": "success"},
        db_path=db,
    )
    assert out["count"] >= 1
    assert out["duration_ms"] < 100
    assert out["query_id"].startswith("qry_")
    assert verify_single_query(
        {
            "id": out["query_id"],
            "timestamp": out["timestamp"],
            "query_hash": out["query_hash"],
            "result_count": out["count"],
            "result_hash": out["result_hash"],
            "prev_hash": out["prev_hash"],
            "chain_hash": out["chain_hash"],
        }
    )["ok"]

    out2 = execute_attested_query(
        api_key=key,
        raw_params={"time_range": "all", "status": "failure"},
        db_path=db,
    )
    assert out2["count"] >= 1

    calls = list_calls(key, limit=500, db_path=db)
    queries = list_queries(key, limit=50, db_path=db)
    assert len(queries) == 2

    unified = verify_unified_records(calls, queries)
    assert unified["ok"] is True
    assert unified["n_calls"] == 5
    assert unified["n_queries"] == 2

    chain = list_chain(key, limit=100, db_path=db)
    assert len(chain) == 7
    proof = verify_chain_rows(
        chain,
        calls_by_id={str(c["id"]): c for c in calls},
        queries_by_id={str(q["id"]): q for q in queries},
    )
    assert proof["ok"] is True
    assert proof["n_queries"] == 2

    queries[0]["result_hash"] = "ff" * 32
    broken = verify_unified_records(calls, queries)
    assert broken["ok"] is False


def test_compliance_as_code_unified_chain(tmp_path):
    db = tmp_path / "c.db"
    init_db(db)
    key = "ata_test_key_compliance"
    _seed_calls(db, key, 5)

    standards = list_standards()
    assert len(standards) >= 5  # 4 new + EU (+ maybe community example)
    eu = next(s for s in standards if s["id"] == STANDARD_EU_AI_ACT_TRANSPARENCY)
    assert eu["auto_coverage"] >= 0.6

    run1 = execute_compliance_check(
        api_key=key,
        standard=STANDARD_EU_AI_ACT_TRANSPARENCY,
        db_path=db,
    )
    assert run1["check_id"].startswith("cmp_")
    assert run1["duration_ms"] < 5000
    assert run1["summary"]["n_total"] == 11
    assert run1["summary"]["n_manual"] == 4
    assert run1["summary"]["n_pass"] + run1["summary"]["n_fail"] == 7
    assert verify_single_compliance(
        {
            "id": run1["check_id"],
            "timestamp": run1["timestamp"],
            "standard": run1["standard"],
            "report_hash": run1["report_hash"],
            "prev_hash": run1["prev_hash"],
            "chain_hash": run1["chain_hash"],
        }
    )["ok"]

    # second run for compare + another chain link
    execute_compliance_check(
        api_key=key,
        standard=STANDARD_EU_AI_ACT_TRANSPARENCY,
        db_path=db,
    )
    comps = list_compliance(key, limit=10, db_path=db)
    assert len(comps) == 2
    diff = compare_compliance(comps[1], comps[0])  # older, newer by list desc
    assert "changes" in diff

    calls = list_calls(key, limit=500, db_path=db)
    queries = list_queries(key, limit=50, db_path=db)
    unified = verify_unified_records(calls, queries, comps)
    assert unified["ok"] is True
    assert unified["n_compliance"] == 2

    chain = list_chain(key, limit=200, db_path=db)
    assert len(chain) == 7  # 5 calls + 2 compliance
    proof = verify_chain_rows(
        chain,
        calls_by_id={str(c["id"]): c for c in calls},
        queries_by_id={str(q["id"]): q for q in queries},
        compliance_by_id={str(c["id"]): c for c in comps},
    )
    assert proof["ok"] is True
    assert proof["n_compliance"] == 2

    comps[0]["report_hash"] = "aa" * 32
    broken = verify_unified_records(calls, queries, comps)
    assert broken["ok"] is False


def test_compliance_catalog_compare_and_gap(tmp_path):
    from compliance import gap_analysis
    from compliance_catalog import (
        STANDARD_ISO_42001,
        STANDARD_US_AI_EO,
        compare_standards,
    )

    db = tmp_path / "cg.db"
    init_db(db)
    key = "ata_test_key_catalog"
    _seed_calls(db, key, 4)

    matrix = compare_standards(
        [STANDARD_EU_AI_ACT_TRANSPARENCY, STANDARD_ISO_42001, STANDARD_US_AI_EO]
    )
    assert matrix["n_overlap"] >= 1
    assert "api_trail_30d" in matrix["overlap_groups"]
    assert len(matrix["matrix"]) >= 5

    # multi-standard run dedupes groups
    bundle = execute_compliance_check(
        api_key=key,
        standards=[STANDARD_EU_AI_ACT_TRANSPARENCY, STANDARD_ISO_42001],
        db_path=db,
    )
    assert bundle.get("bundle") is True
    assert bundle["n_groups_executed"] < (
        list_standards()[0]["n_checks"] + 9
    )  # less than naive sum
    assert len(bundle["reports"]) == 2

    gap = gap_analysis(
        api_key=key,
        standards=[STANDARD_EU_AI_ACT_TRANSPARENCY, STANDARD_ISO_42001],
        db_path=db,
    )
    assert gap["summary"]["n_total"] > 0
    assert "satisfied" in gap and "unsatisfied" in gap and "partial" in gap
    # history source after bundle
    assert gap["by_standard"][STANDARD_EU_AI_ACT_TRANSPARENCY]["source"] == "history"


def test_behavior_baseline_and_drift(tmp_path):
    db = tmp_path / "b.db"
    init_db(db)
    key = "ata_test_key_behavior"
    _seed_calls(db, key, 5)

    bl = create_baseline(api_key=key, time_range="7d", db_path=db)
    assert bl["baseline_id"].startswith("bl_")
    assert bl["duration_ms"] < 5000
    assert bl["n_calls"] == 5
    assert verify_single_baseline(
        {
            "id": bl["baseline_id"],
            "timestamp": bl["timestamp"],
            "time_range_start": bl["time_range_start"],
            "time_range_end": bl["time_range_end"],
            "baseline_hash": bl["baseline_hash"],
            "prev_hash": bl["prev_hash"],
            "chain_hash": bl["chain_hash"],
        }
    )["ok"]

    # Inject anomalous call: new endpoint + high cost + slow latency
    prev = latest_chain_hash(key, db_path=db)
    weird = build_call_record(
        api_key=key,
        prev_hash=prev,
        endpoint="/v1/never-seen-before",
        method="POST",
        model="gpt-4",
        status_code=200,
        request_body=b'{"x":1}',
        response_body=b'{"ok":true}',
        duration_ms=99999.0,
        prompt_tokens=10,
        completion_tokens=10,
        cost_usd=999.0,
    )
    insert_call(weird, db_path=db)

    drift = detect_drift(api_key=key, baseline_id=bl["baseline_id"], window="today", db_path=db)
    assert drift["n_marks_created"] >= 1
    marks = list_drift_marks(key, status="pending", limit=50, db_path=db)
    assert len(marks) >= 1
    types = {m["mark_type"] for m in marks}
    assert "new_endpoint" in types or "cost_spike" in types or "latency_drop" in types
    assert verify_single_drift_mark(marks[0])["ok"]

    reviewed = review_drift_mark(
        mark_id=marks[0]["id"],
        api_key=key,
        status="reviewed",
        reviewed_by="tester",
        db_path=db,
    )
    assert reviewed["mark"]["status"] == "reviewed"

    bl2 = create_baseline(api_key=key, time_range="7d", db_path=db)
    bas = list_baselines(key, limit=10, db_path=db)
    assert len(bas) >= 2
    cmp = compare_baselines(
        next(b for b in bas if b["id"] == bl["baseline_id"]),
        next(b for b in bas if b["id"] == bl2["baseline_id"]),
    )
    assert "summary" in cmp

    soft_delete(baseline_id=bl["baseline_id"], api_key=key, db_path=db)
    active = list_baselines(key, include_deleted=False, db_path=db)
    assert all(b["id"] != bl["baseline_id"] for b in active)

    calls = list_calls(key, limit=500, db_path=db)
    all_marks = list_drift_marks(key, status=None, limit=100, db_path=db)
    all_bas = list_baselines(key, include_deleted=True, db_path=db)
    unified = verify_unified_records(calls, [], None, all_bas, all_marks)
    assert unified["ok"] is True
    assert unified["n_baselines"] >= 2
    assert unified["n_drift_marks"] >= 1

    chain = list_chain(key, limit=500, db_path=db)
    proof = verify_chain_rows(
        chain,
        calls_by_id={str(c["id"]): c for c in calls},
        queries_by_id={},
        compliance_by_id={},
        baselines_by_id={str(b["id"]): b for b in all_bas},
        drift_marks_by_id={str(m["id"]): m for m in all_marks},
    )
    assert proof["ok"] is True


def test_timestamp_anchor_and_verify_pack(tmp_path):
    from anchoring import anchor_chain_head, stamp_hash, verify_tsa_receipt
    from compliance_catalog import STANDARD_EU_AI_ACT_TRANSPARENCY
    from verify_pack import (
        build_verify_pack,
        decode_pack,
        encode_pack,
        report_to_oscal,
        verify_pack,
    )

    db = tmp_path / "a.db"
    init_db(db)
    key = "ata_test_key_anchor"
    _seed_calls(db, key, 3)

    run = execute_compliance_check(
        api_key=key,
        standard=STANDARD_EU_AI_ACT_TRANSPARENCY,
        db_path=db,
    )
    assert run.get("timestamp_proof")
    assert verify_tsa_receipt(run["timestamp_proof"])["ok"]

    receipt = stamp_hash(run["report_hash"])
    assert verify_tsa_receipt(receipt)["ok"]

    anc = anchor_chain_head(api_key=key, db_path=db, force_mock=True)
    assert anc["tx_hash"].startswith("0x")
    assert anc["network"] == "sepolia-mock"
    assert anc.get("timestamp_proof")

    pack = build_verify_pack(
        {
            "id": run["check_id"],
            "standard": run["standard"],
            "standard_name": run["standard_name"],
            "timestamp": run["timestamp"],
            "summary": run["summary"],
            "check_results": run["check_results"],
            "report_hash": run["report_hash"],
            "prev_hash": run["prev_hash"],
            "chain_hash": run["chain_hash"],
        },
        timestamp_proof=run["timestamp_proof"],
        blockchain_anchor=anc,
    )
    token = encode_pack(pack)
    roundtrip = decode_pack(token)
    v = verify_pack(roundtrip)
    assert v["report_hash"]["ok"] is True
    assert v["chain"]["ok"] is True
    assert v["timestamp"]["ok"] is True
    assert v["blockchain_anchor"]["present"] is True

    oscal = report_to_oscal(run, pack=pack)
    assert oscal["oscal-version"] == "1.1.2"
    assert oscal["assessment-results"]["results"]


if __name__ == "__main__":
    import tempfile
    from pathlib import Path as P

    with tempfile.TemporaryDirectory() as d:
        base = P(d)
        test_hash_chain_and_meter(base)
        test_query_as_audit_unified_chain(base / "q")
        test_compliance_as_code_unified_chain(base / "c")
        test_behavior_baseline_and_drift(base / "b")
        test_timestamp_anchor_and_verify_pack(base / "a")
    print("ok")
