"""P1 科研时间线：关联调用、权限、软删除、整链仍可校验。"""

from __future__ import annotations

import hashlib
import tempfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from attestation import build_call_record, verify_key_chain
from models import ensure_api_key, init_db, insert_call
from research import register_artifact


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


def _hash64(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _call(key: str, db, *, prev: str = "0" * 64):
    rec = build_call_record(
        api_key=key,
        prev_hash=prev,
        endpoint="/v1/chat/completions",
        method="POST",
        model="gpt-4o-mini",
        status_code=200,
        request_body=b'{"m":1}',
        response_body=b'{"ok":true}',
        duration_ms=9,
        prompt_tokens=2,
        completion_tokens=2,
        cost_usd=0.0001,
        vendor="openai",
    )
    insert_call(rec, db_path=db)
    return rec


def test_link_call_listed_and_chain_ok(monkeypatch):
    td, db = _db()
    try:
        key = "ata_test_rtl_link_ok01"
        ensure_api_key(key, label="t", role="read_write", db_path=db)
        rec = _call(key, db)
        art = register_artifact(
            api_key=key,
            title="草稿",
            kind="draft",
            artifact_hash=_hash64("rtl-draft"),
            db_path=db,
        )
        aid = art["artifact"]["id"]

        import main as main_mod

        monkeypatch.setattr(main_mod, "DB_PATH", db)
        client = TestClient(main_mod.app)

        r = client.post(
            "/v1/research/timeline/link-call",
            json={"api_key": key, "call_id": rec["id"], "artifact_id": aid, "label": "发 AI 前"},
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["ok"] is True
        assert "api_key" not in body["timeline"]
        assert body["timeline"]["call_id"] == rec["id"]
        assert body["proof"]["ok"] is True

        listed = client.get(
            "/v1/research/timeline",
            params={"api_key": key, "artifact_id": aid},
        )
        assert listed.status_code == 200
        assert listed.json()["n"] >= 1
        assert listed.json()["timeline"][0]["call_id"] == rec["id"]

        linked = client.get(
            f"/v1/research/artifacts/{aid}/linked-calls",
            params={"api_key": key},
        )
        assert linked.status_code == 200
        assert linked.json()["calls"][0]["call_id"] == rec["id"]

        proof = verify_key_chain(key, db_path=db)
        assert proof["ok"] is True
        assert proof.get("n_research_timeline") == 1
        assert proof.get("n_research_artifacts") == 1
        assert proof.get("n_calls") == 1
    finally:
        td.cleanup()


def test_link_foreign_call_404(monkeypatch):
    td, db = _db()
    try:
        a = "ata_test_rtl_own_aaa1"
        b = "ata_test_rtl_own_bbb1"
        ensure_api_key(a, label="a", role="read_write", db_path=db)
        ensure_api_key(b, label="b", role="read_write", db_path=db)
        rec_b = _call(b, db)
        art = register_artifact(
            api_key=a, title="x", kind="note", artifact_hash=_hash64("a"), db_path=db
        )
        import main as main_mod

        monkeypatch.setattr(main_mod, "DB_PATH", db)
        client = TestClient(main_mod.app)
        r = client.post(
            "/v1/research/timeline/link-call",
            json={
                "api_key": a,
                "call_id": rec_b["id"],
                "artifact_id": art["artifact"]["id"],
            },
        )
        assert r.status_code == 404
    finally:
        td.cleanup()


def test_delete_timeline_then_hidden_chain_still_ok(monkeypatch):
    td, db = _db()
    try:
        key = "ata_test_rtl_del_0001"
        ensure_api_key(key, label="t", role="read_write", db_path=db)
        rec = _call(key, db)
        art = register_artifact(
            api_key=key,
            title="x",
            kind="draft",
            artifact_hash=_hash64("del"),
            db_path=db,
        )
        import main as main_mod

        monkeypatch.setattr(main_mod, "DB_PATH", db)
        client = TestClient(main_mod.app)
        created = client.post(
            "/v1/research/timeline/link-call",
            json={
                "api_key": key,
                "call_id": rec["id"],
                "artifact_id": art["artifact"]["id"],
            },
        )
        tid = created.json()["timeline"]["id"]
        d = client.delete(
            f"/v1/research/timeline/{tid}", params={"api_key": key}
        )
        assert d.status_code == 200
        listed = client.get(
            "/v1/research/timeline",
            params={"api_key": key, "artifact_id": art["artifact"]["id"]},
        )
        assert listed.json()["n"] == 0
        proof = verify_key_chain(key, db_path=db)
        assert proof["ok"] is True
        assert proof.get("n_research_timeline") == 1
    finally:
        td.cleanup()
