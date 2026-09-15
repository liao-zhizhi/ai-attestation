"""Proxy SSRF guards, timestamp coerce, and cost aggregation."""

from __future__ import annotations

import sys
from pathlib import Path
from urllib.parse import urljoin

APP = Path(__file__).resolve().parents[1] / "app"
sys.path.insert(0, str(APP))

import pytest
from fastapi import HTTPException

from proxy import _join_upstream, _sanitize_upstream_base
from query_audit import coerce_iso_ts
from models import ensure_api_key, init_db, insert_call, sum_call_cost
from attestation import GENESIS, build_call_record


def test_urljoin_absolute_path_would_takeover_host():
    """Document the urljoin footgun that _join_upstream must prevent."""
    hijacked = urljoin("https://api.openai.com/", "https://169.254.169.254/")
    assert hijacked.startswith("https://169.254.169.254")


def test_join_upstream_rejects_absolute_and_protocol_relative():
    with pytest.raises(HTTPException) as ei:
        _join_upstream("https://api.openai.com/", "https://evil.example/v1")
    assert ei.value.status_code == 400

    with pytest.raises(HTTPException):
        _join_upstream("https://api.openai.com/", "//evil.example/v1")

    ok = _join_upstream("https://api.openai.com/", "v1/chat/completions")
    assert ok == "https://api.openai.com/v1/chat/completions"


def test_sanitize_blocks_localhost_and_loopback(monkeypatch):
    monkeypatch.delenv("ATA_ALLOW_PRIVATE_UPSTREAM", raising=False)
    monkeypatch.delenv("ATA_UPSTREAM_ALLOWLIST", raising=False)
    with pytest.raises(HTTPException):
        _sanitize_upstream_base("http://localhost:11434/")
    with pytest.raises(HTTPException):
        _sanitize_upstream_base("http://127.0.0.1:8000/")
    with pytest.raises(HTTPException):
        _sanitize_upstream_base("http://169.254.169.254/")
    with pytest.raises(HTTPException):
        _sanitize_upstream_base("http://metadata.google.internal/")


def test_sanitize_allows_localhost_when_opted_in(monkeypatch):
    monkeypatch.setenv("ATA_ALLOW_PRIVATE_UPSTREAM", "1")
    monkeypatch.delenv("ATA_UPSTREAM_ALLOWLIST", raising=False)
    out = _sanitize_upstream_base("http://localhost:11434")
    assert out.startswith("http://localhost:11434")
    # cloud metadata stays blocked even with the private opt-in
    with pytest.raises(HTTPException):
        _sanitize_upstream_base("http://metadata.google.internal/")


def test_coerce_iso_ts_datetime_local_and_millis():
    assert coerce_iso_ts("2026-09-16T08:00") == "2026-09-16T08:00:00.000000Z"
    assert coerce_iso_ts("2026-09-16T08:00:00.000Z") == "2026-09-16T08:00:00.000000Z"
    assert coerce_iso_ts("2026-09-16T08:00:00.123456Z") == "2026-09-16T08:00:00.123456Z"
    assert coerce_iso_ts(None) is None


def test_sum_call_cost_not_capped_at_500(tmp_path):
    db = tmp_path / "cost.db"
    init_db(db)
    key = "ata_test_sum_cost_key01"
    ensure_api_key(key, label="t", role="admin", db_path=db)
    prev = GENESIS
    n = 12
    for i in range(n):
        rec = build_call_record(
            api_key=key,
            prev_hash=prev,
            endpoint="/v1/chat/completions",
            method="POST",
            model="gpt-4o-mini",
            status_code=200,
            request_body=b"{}",
            response_body=b"{}",
            duration_ms=1,
            prompt_tokens=1,
            completion_tokens=1,
            cost_usd=1.0,
        )
        insert_call(rec, db_path=db)
        prev = rec["chain_hash"]
    assert abs(sum_call_cost(key, db_path=db) - float(n)) < 1e-9
