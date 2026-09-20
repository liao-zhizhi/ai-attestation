"""P1-C 训练同意记录：全局默认、厂商覆盖、上链、权限、非法值。"""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from attestation import build_call_record, verify_key_chain
from models import ensure_api_key, init_db, insert_call


@pytest.fixture(autouse=True)
def _skip_ots_network(monkeypatch):
    def _boom(*_a, **_k):
        raise OSError("offline")

    monkeypatch.setattr("urllib.request.urlopen", _boom)


def _db():
    td = tempfile.TemporaryDirectory()
    path = Path(td.name) / "t.db"
    init_db(path)
    return td, path


def _client(monkeypatch, db):
    import main as main_mod

    monkeypatch.setattr(main_mod, "DB_PATH", db)
    return TestClient(main_mod.app)


def test_global_default_then_get(monkeypatch):
    td, db = _db()
    try:
        key = "ata_test_cns_glob_0001"
        ensure_api_key(key, label="t", role="read_write", db_path=db)
        client = _client(monkeypatch, db)
        r = client.put(
            "/v1/research/consent",
            json={"api_key": key, "vendor": "*", "allow_training": "no"},
        )
        assert r.status_code == 200, r.text
        rec = r.json()["record"]
        assert rec["vendor"] == "*"
        assert rec["allow_training"] == "no"
        assert "api_key" not in rec
        got = client.get("/v1/research/consent", params={"api_key": key})
        assert got.status_code == 200
        body = got.json()
        assert body["global"]["allow_training"] == "no"
        assert body["by_vendor"] == {}
    finally:
        td.cleanup()


def test_vendor_override_beats_global(monkeypatch):
    td, db = _db()
    try:
        key = "ata_test_cns_ovrd_0001"
        ensure_api_key(key, label="t", role="read_write", db_path=db)
        client = _client(monkeypatch, db)
        client.put(
            "/v1/research/consent",
            json={"api_key": key, "vendor": "*", "allow_training": "no"},
        )
        r = client.put(
            "/v1/research/consent",
            json={"api_key": key, "vendor": "openai", "allow_training": "yes"},
        )
        assert r.status_code == 200, r.text
        got = client.get("/v1/research/consent", params={"api_key": key})
        body = got.json()
        assert body["global"]["allow_training"] == "no"
        assert body["by_vendor"]["openai"]["allow_training"] == "yes"
        assert "deepseek" not in body["by_vendor"]
    finally:
        td.cleanup()


def test_multiple_changes_return_latest(monkeypatch):
    td, db = _db()
    try:
        key = "ata_test_cns_lat_0001"
        ensure_api_key(key, label="t", role="read_write", db_path=db)
        client = _client(monkeypatch, db)
        client.put(
            "/v1/research/consent",
            json={"api_key": key, "vendor": "*", "allow_training": "unknown"},
        )
        client.put(
            "/v1/research/consent",
            json={"api_key": key, "vendor": "*", "allow_training": "yes"},
        )
        client.put(
            "/v1/research/consent",
            json={"api_key": key, "vendor": "*", "allow_training": "no"},
        )
        got = client.get("/v1/research/consent", params={"api_key": key})
        assert got.json()["global"]["allow_training"] == "no"
        hist = client.get("/v1/research/consent/report", params={"api_key": key})
        assert hist.status_code == 200
        assert hist.json()["n"] == 3
        assert hist.json()["history"][0]["allow_training"] == "no"
    finally:
        td.cleanup()


def test_consent_on_chain_verify_ok(monkeypatch):
    td, db = _db()
    try:
        key = "ata_test_cns_chain_001"
        ensure_api_key(key, label="t", role="read_write", db_path=db)
        rec = build_call_record(
            api_key=key,
            prev_hash="0" * 64,
            endpoint="/v1/chat/completions",
            method="POST",
            model="gpt-4o-mini",
            status_code=200,
            request_body=b"{}",
            response_body=b"{}",
            duration_ms=1,
            prompt_tokens=1,
            completion_tokens=1,
            cost_usd=0.0,
            vendor="openai",
        )
        insert_call(rec, db_path=db)
        client = _client(monkeypatch, db)
        r = client.put(
            "/v1/research/consent",
            json={"api_key": key, "vendor": "*", "allow_training": "no"},
        )
        assert r.status_code == 200, r.text
        proof = verify_key_chain(key, db_path=db)
        assert proof["ok"] is True, proof
        assert proof.get("n_research_consent") == 1
        assert proof.get("n_calls") == 1
    finally:
        td.cleanup()


def test_read_only_cannot_put(monkeypatch):
    td, db = _db()
    try:
        key = "ata_test_cns_ro_0001"
        ensure_api_key(key, label="t", role="read_only", db_path=db)
        client = _client(monkeypatch, db)
        r = client.put(
            "/v1/research/consent",
            json={"api_key": key, "vendor": "*", "allow_training": "no"},
        )
        assert r.status_code == 403, r.text
    finally:
        td.cleanup()


def test_illegal_allow_training_422(monkeypatch):
    td, db = _db()
    try:
        key = "ata_test_cns_422_0001"
        ensure_api_key(key, label="t", role="read_write", db_path=db)
        client = _client(monkeypatch, db)
        r = client.put(
            "/v1/research/consent",
            json={"api_key": key, "vendor": "*", "allow_training": "maybe"},
        )
        assert r.status_code == 422, r.text
    finally:
        td.cleanup()


def test_consent_export_txt_and_json(monkeypatch):
    td, db = _db()
    try:
        key = "ata_test_cns_exp_0001"
        ensure_api_key(key, label="t", role="read_write", db_path=db)
        client = _client(monkeypatch, db)
        client.put(
            "/v1/research/consent",
            json={"api_key": key, "vendor": "*", "allow_training": "no"},
        )
        txt = client.get(
            "/v1/research/consent/report/export",
            params={"api_key": key, "format": "txt"},
        )
        assert txt.status_code == 200
        assert "Training Consent" in txt.text
        assert "attachment" in txt.headers.get("content-disposition", "")
        js = client.get(
            "/v1/research/consent/report/export",
            params={"api_key": key, "format": "json"},
        )
        assert js.status_code == 200
        assert js.json()["n"] >= 1
    finally:
        td.cleanup()
