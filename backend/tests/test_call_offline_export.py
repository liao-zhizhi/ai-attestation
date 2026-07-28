"""Offline call verify-pack ZIP + /v1/reports/{id}/export."""

from __future__ import annotations

import io
import tempfile
import zipfile
from pathlib import Path

from fastapi.testclient import TestClient

from attestation import build_call_record, verify_single_call
from models import ensure_api_key, init_db, insert_call
from verify_offline import build_call_offline_zip


def _db():
    td = tempfile.TemporaryDirectory()
    path = Path(td.name) / "t.db"
    init_db(path)
    return td, path


def test_build_call_offline_zip_contents():
    td, db = _db()
    try:
        key = "ata_test_call_zip_key01"
        ensure_api_key(key, label="t", role="read_write", db_path=db)
        rec = build_call_record(
            api_key=key,
            prev_hash="0" * 64,
            endpoint="/v1/chat/completions",
            method="POST",
            model="gpt-4o-mini",
            status_code=200,
            request_body=b'{"hello":1}',
            response_body=b'{"ok":true}',
            duration_ms=12,
            prompt_tokens=3,
            completion_tokens=4,
            cost_usd=0.00123456,
            vendor="openai",
        )
        insert_call(rec, db_path=db)
        proof = verify_single_call(rec)
        assert proof["ok"] is True

        zbytes = build_call_offline_zip(
            call=rec,
            verification=proof,
            api_key=key,
            db_path=db,
        )
        with zipfile.ZipFile(io.BytesIO(zbytes), "r") as zf:
            names = set(zf.namelist())
            assert names >= {
                "call.json",
                "chain.json",
                "verification.json",
                "verify.html",
                "README.txt",
            }
            call_txt = zf.read("call.json").decode("utf-8")
            assert "api_key" not in call_txt  # never leak key into pack
            assert rec["chain_hash"] in call_txt
            assert "request_hash" in call_txt
            assert '{"hello"' not in call_txt  # no raw body
            chain_meta = __import__("json").loads(zf.read("chain.json"))["meta"]
            assert chain_meta.get("adjacency_trusted") in (True, False)
            readme = zf.read("README.txt").decode("utf-8")
            assert "verify.html" in readme
            assert "http.server" in readme
    finally:
        td.cleanup()


def test_export_route_auth_and_zip(monkeypatch):
    td, db = _db()
    try:
        key = "ata_test_export_route_k1"
        other = "ata_test_export_other01"
        ensure_api_key(key, label="t", role="read_write", db_path=db)
        ensure_api_key(other, label="o", role="read_write", db_path=db)
        rec = build_call_record(
            api_key=key,
            prev_hash="0" * 64,
            endpoint="/v1/chat/completions",
            method="POST",
            model="deepseek-chat",
            status_code=200,
            request_body=b"{}",
            response_body=b"{}",
            duration_ms=2,
            prompt_tokens=1,
            completion_tokens=1,
            cost_usd=0.01,
            vendor="deepseek",
        )
        insert_call(rec, db_path=db)

        import main as main_mod

        monkeypatch.setattr(main_mod, "DB_PATH", db)
        client = TestClient(main_mod.app)

        # missing key
        r0 = client.get(f"/v1/reports/{rec['id']}/export")
        assert r0.status_code in (401, 422)

        # wrong owner
        r1 = client.get(
            f"/v1/reports/{rec['id']}/export", params={"api_key": other}
        )
        assert r1.status_code == 404

        # ok
        r2 = client.get(
            f"/v1/reports/{rec['id']}/export", params={"api_key": key}
        )
        assert r2.status_code == 200
        assert "application/zip" in r2.headers.get("content-type", "")
        assert "ata_call_" in r2.headers.get("content-disposition", "")
        with zipfile.ZipFile(io.BytesIO(r2.content), "r") as zf:
            assert "call.json" in zf.namelist()
            assert "verify.html" in zf.namelist()

        # X-Attest-Key header also works
        r3 = client.get(
            f"/v1/reports/{rec['id']}/export",
            headers={"X-Attest-Key": key},
        )
        assert r3.status_code == 200
    finally:
        td.cleanup()
