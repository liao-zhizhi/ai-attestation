"""P1 公开验证链接：生成、公开读取、撤销、权限。"""

from __future__ import annotations

import tempfile
from pathlib import Path

from fastapi.testclient import TestClient

from attestation import build_call_record
from models import ensure_api_key, init_db, insert_call


def _db():
    td = tempfile.TemporaryDirectory()
    path = Path(td.name) / "t.db"
    init_db(path)
    return td, path


def _call(key: str, db, *, prev: str = "0" * 64):
    rec = build_call_record(
        api_key=key,
        prev_hash=prev,
        endpoint="/v1/chat/completions",
        method="POST",
        model="gpt-4o-mini",
        status_code=200,
        request_body=b'{"secret":"BODY_MUST_NOT_LEAK"}',
        response_body=b'{"ok":true}',
        duration_ms=12,
        prompt_tokens=3,
        completion_tokens=4,
        cost_usd=0.001,
        vendor="openai",
    )
    insert_call(rec, db_path=db)
    return rec


def test_share_public_verify_hides_api_key_and_body(monkeypatch):
    td, db = _db()
    try:
        rw = "ata_test_share_rw_0001"
        ensure_api_key(rw, label="t", role="read_write", db_path=db)
        rec = _call(rw, db)

        import main as main_mod

        monkeypatch.setattr(main_mod, "DB_PATH", db)
        client = TestClient(main_mod.app)

        r = client.post(
            f"/v1/public/share/call/{rec['id']}", params={"api_key": rw}
        )
        assert r.status_code == 200, r.text
        token = r.json()["token"]
        assert token
        assert "/verify/call/" in r.json()["url"]

        pub = client.get(f"/v1/public/verify/call/{token}")
        assert pub.status_code == 200, pub.text
        data = pub.json()
        blob = pub.text
        assert "api_key" not in data
        assert rw not in blob
        assert "BODY_MUST_NOT_LEAK" not in blob
        assert data["request_hash"] == rec["request_hash"]
        assert data["chain_hash"] == rec["chain_hash"]
        assert data["chain_status"] in ("intact", "broken")
        assert data.get("chain_ok") is True
    finally:
        td.cleanup()


def test_revoke_then_public_404(monkeypatch):
    td, db = _db()
    try:
        rw = "ata_test_share_rev_0001"
        ensure_api_key(rw, label="t", role="read_write", db_path=db)
        rec = _call(rw, db)
        import main as main_mod

        monkeypatch.setattr(main_mod, "DB_PATH", db)
        client = TestClient(main_mod.app)
        token = client.post(
            f"/v1/public/share/call/{rec['id']}", params={"api_key": rw}
        ).json()["token"]
        assert client.get(f"/v1/public/verify/call/{token}").status_code == 200
        d = client.delete(f"/v1/public/share/{token}", params={"api_key": rw})
        assert d.status_code == 200
        assert d.json().get("ok") is True
        assert client.get(f"/v1/public/verify/call/{token}").status_code == 404
    finally:
        td.cleanup()


def test_foreign_call_and_foreign_token_404(monkeypatch):
    """别人的调用不能生成链接；别人的 token 不能撤销。"""
    td, db = _db()
    try:
        a = "ata_test_share_own_aaa1"
        b = "ata_test_share_own_bbb1"
        ensure_api_key(a, label="a", role="read_write", db_path=db)
        ensure_api_key(b, label="b", role="read_write", db_path=db)
        rec = _call(a, db)
        import main as main_mod

        monkeypatch.setattr(main_mod, "DB_PATH", db)
        client = TestClient(main_mod.app)

        steal = client.post(
            f"/v1/public/share/call/{rec['id']}", params={"api_key": b}
        )
        assert steal.status_code == 404

        token = client.post(
            f"/v1/public/share/call/{rec['id']}", params={"api_key": a}
        ).json()["token"]
        # 公开接口任何人可看（有 token 即能力）
        assert client.get(f"/v1/public/verify/call/{token}").status_code == 200
        # 别人不能撤销
        bad = client.delete(f"/v1/public/share/{token}", params={"api_key": b})
        assert bad.status_code == 404
        # 未知 token
        assert (
            client.get("/v1/public/verify/call/this-token-does-not-exist").status_code
            == 404
        )
    finally:
        td.cleanup()


def test_readonly_cannot_create_share(monkeypatch):
    td, db = _db()
    try:
        rw = "ata_test_share_ro_rw01"
        ro = "ata_test_share_ro_ro01"
        ensure_api_key(rw, label="rw", role="read_write", db_path=db)
        ensure_api_key(ro, label="ro", role="read_only", db_path=db)
        rec = _call(rw, db)
        import main as main_mod

        monkeypatch.setattr(main_mod, "DB_PATH", db)
        client = TestClient(main_mod.app)
        r = client.post(
            f"/v1/public/share/call/{rec['id']}", params={"api_key": ro}
        )
        assert r.status_code == 403
    finally:
        td.cleanup()
