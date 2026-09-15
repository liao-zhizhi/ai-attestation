"""科研优先权 P0：登记、重算链、证书 ZIP、只读 Key、篡改失败。

不覆盖旧调用包格式；verify.html 规则须与 Python 链环一致。
"""

from __future__ import annotations

import hashlib
import io
import json
import tempfile
import zipfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from attestation import (
    compute_research_artifact_chain_hash,
    sha256_text,
    verify_key_chain,
    verify_single_research_artifact,
)
from models import (
    connect,
    ensure_api_key,
    get_research_artifact,
    init_db,
)
from research import PACK_TYPE, register_artifact
from research_cert import CERT_ZIP_NAMES, _PRIORITY_VERIFY_HTML, certificate_filename


def _db():
    td = tempfile.TemporaryDirectory()
    path = Path(td.name) / "t.db"
    init_db(path)
    return td, path


@pytest.fixture(autouse=True)
def _skip_ots_network(monkeypatch):
    """登记会 stamp_hash；禁止测试去打公开日历（避免 2.5s 超时）。"""

    def _boom(*_a, **_k):
        raise OSError("offline")

    monkeypatch.setattr("urllib.request.urlopen", _boom)


def _hash64(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def test_register_recomputes_chain_and_counts():
    """合法哈希登记后，单条与整链均可重算，且计入 n_research_artifacts。"""
    td, db = _db()
    try:
        key = "ata_test_research_rw_001"
        ensure_api_key(key, label="t", role="read_write", db_path=db)
        digest = _hash64("多尺度放大构造爆破解 草稿")
        out = register_artifact(
            api_key=key,
            title="idea.txt",
            kind="draft",
            artifact_hash=digest.upper(),  # 允许大写，入库小写
            byte_length=len("多尺度放大构造爆破解 草稿".encode("utf-8")),
            filename_hint="idea.txt",
            client_hashed=True,
            db_path=db,
        )
        assert out["ok"] is True
        assert out["duplicate_notice"] is None
        art = out["artifact"]
        assert art["pack_type"] == PACK_TYPE
        assert art["artifact_hash"] == digest
        assert "api_key" not in art
        assert out["proof"]["ok"] is True

        expected = compute_research_artifact_chain_hash(
            prev_hash=art["prev_hash"],
            artifact_id=art["id"],
            timestamp=art["timestamp"],
            artifact_hash=digest,
            kind="draft",
        )
        assert art["chain_hash"] == expected

        proof = verify_key_chain(key, db_path=db)
        assert proof["ok"] is True
        assert proof.get("n_research_artifacts") == 1
    finally:
        td.cleanup()


def test_duplicate_hash_allowed_with_notice():
    """同一指纹允许再登记；仅后一条标注该指纹已于某时登记过。"""
    td, db = _db()
    try:
        key = "ata_test_research_dup_01"
        ensure_api_key(key, label="t", role="read_write", db_path=db)
        digest = _hash64("same-bytes")
        first = register_artifact(
            api_key=key, title="一", kind="note", artifact_hash=digest, db_path=db
        )
        second = register_artifact(
            api_key=key, title="二", kind="note", artifact_hash=digest, db_path=db
        )
        assert first["duplicate_notice"] is None
        assert second["duplicate_notice"]
        assert "该指纹已于" in second["duplicate_notice"]
        assert "登记过" in second["duplicate_notice"]
        from research import list_artifacts_for_key

        listing = list_artifacts_for_key(api_key=key, db_path=db)
        by_id = {a["id"]: a for a in listing["artifacts"]}
        # 后登记的带提示；先登记的不提示「已于更晚时间登记过」
        assert by_id[second["artifact"]["id"]]["duplicate_notice"]
        assert by_id[first["artifact"]["id"]]["duplicate_notice"] is None
    finally:
        td.cleanup()


def test_tamper_artifact_hash_fails_verify():
    """篡改 artifact_hash 后单条与整链校验均失败。"""
    td, db = _db()
    try:
        key = "ata_test_research_tamper1"
        ensure_api_key(key, label="t", role="read_write", db_path=db)
        digest = _hash64("original")
        out = register_artifact(
            api_key=key, title="t", kind="draft", artifact_hash=digest, db_path=db
        )
        aid = out["artifact"]["id"]
        conn = connect(db)
        try:
            conn.execute(
                "UPDATE research_artifacts SET artifact_hash=? WHERE id=?",
                ("b" * 64, aid),
            )
            conn.commit()
        finally:
            conn.close()
        row = get_research_artifact(aid, db_path=db)
        assert row is not None
        proof = verify_single_research_artifact(row)
        assert proof["ok"] is False
        chain = verify_key_chain(key, db_path=db)
        assert chain["ok"] is False
    finally:
        td.cleanup()


def test_certificate_zip_manifest_and_no_plaintext():
    """ZIP 仅含约定文件；无 api_key、无原文；TSA token 可重算。"""
    td, db = _db()
    try:
        key = "ata_test_research_zip_01"
        ensure_api_key(key, label="t", role="read_write", db_path=db)
        secret = "THIS_MUST_NOT_APPEAR_IN_ZIP"
        digest = _hash64(secret)
        out = register_artifact(
            api_key=key,
            title="代号-A",
            kind="prompt",
            artifact_hash=digest,
            description="可用代号",
            db_path=db,
        )
        from research_cert import build_priority_certificate_zip

        row = get_research_artifact(out["artifact"]["id"], db_path=db)
        zbytes = build_priority_certificate_zip(row=row, verification=out["proof"])
        with zipfile.ZipFile(io.BytesIO(zbytes), "r") as zf:
            names = set(zf.namelist())
            assert names == set(CERT_ZIP_NAMES)
            art = json.loads(zf.read("artifact.json"))
            assert art["pack_type"] == "ata-research-priority-v1"
            assert "api_key" not in art
            blob = zf.read("artifact.json") + zf.read("README.txt")
            assert secret.encode() not in blob
            assert key.encode() not in blob
            assert art["chain_hash"] == out["artifact"]["chain_hash"]
            html = zf.read("verify.html").decode("utf-8")
            assert "ata-research-priority-v1" in html
            assert "call.json" not in html
            assert "运行本地验证" in html
            assert "用原件选择文件" in html
            ts = json.loads(zf.read("timestamp.json"))
            assert ts.get("payload_hash") == digest
            assert ts.get("token")
            # TSA token 与 Python 一致
            expect_tok = sha256_text(
                f"{ts['payload_hash']}|{ts['unix']}|{ts['nonce']}"
            )
            assert ts["token"] == expect_tok
        assert certificate_filename(out["artifact"]["id"]).startswith("ata_priority_")
        assert certificate_filename(out["artifact"]["id"]).endswith("_cert.zip")
    finally:
        td.cleanup()


def test_verify_html_payload_matches_python():
    """离线页拼接顺序必须与 compute_research_artifact_chain_hash 一致。"""
    html = _PRIORITY_VERIFY_HTML
    assert "pack_type === 'ata-research-priority-v1'" in html
    # 与 attestation.py 相同字段顺序
    for token in (
        "prev",
        "'research_artifact'",
        "art.id",
        "art.timestamp",
        "art.artifact_hash",
        "art.kind",
    ):
        assert token in html
    prev = "0" * 64
    aid = "art_demo"
    ts = "2026-01-01T00:00:00.000000Z"
    digest = "a" * 64
    kind = "draft"
    js_style = "|".join([prev, "research_artifact", aid, ts, digest, kind])
    assert sha256_text(js_style) == compute_research_artifact_chain_hash(
        prev_hash=prev,
        artifact_id=aid,
        timestamp=ts,
        artifact_hash=digest,
        kind=kind,
    )


def test_routes_readonly_forbidden_and_extra_body_rejected(monkeypatch):
    """只读 Key 禁止 POST；额外原文字段 422；证书下载文件名正确。"""
    td, db = _db()
    try:
        rw = "ata_test_research_route_rw"
        ro = "ata_test_research_route_ro"
        ensure_api_key(rw, label="rw", role="read_write", db_path=db)
        ensure_api_key(ro, label="ro", role="read_only", db_path=db)
        digest = _hash64("route-body")

        import main as main_mod

        monkeypatch.setattr(main_mod, "DB_PATH", db)
        client = TestClient(main_mod.app)

        # 禁止附带原文
        r_extra = client.post(
            "/v1/research/artifacts",
            json={
                "api_key": rw,
                "title": "x",
                "kind": "draft",
                "artifact_hash": digest,
                "content": "SECRET_SHOULD_422",
            },
        )
        assert r_extra.status_code == 422

        r_bad = client.post(
            "/v1/research/artifacts",
            json={
                "api_key": rw,
                "title": "x",
                "kind": "draft",
                "artifact_hash": "zzzz",
            },
        )
        assert r_bad.status_code == 422

        r_ro = client.post(
            "/v1/research/artifacts",
            json={
                "api_key": ro,
                "title": "x",
                "kind": "draft",
                "artifact_hash": digest,
            },
        )
        assert r_ro.status_code == 403

        r_ok = client.post(
            "/v1/research/artifacts",
            json={
                "api_key": rw,
                "title": "idea",
                "kind": "draft",
                "artifact_hash": digest,
                "client_hashed": True,
            },
        )
        assert r_ok.status_code == 200
        aid = r_ok.json()["artifact"]["id"]

        r_list = client.get("/v1/research/artifacts", params={"api_key": ro})
        # 只读可列表（空或仅自己的）；本 Key 无工件
        assert r_list.status_code == 200
        assert r_list.json()["total"] == 0

        r_list_rw = client.get("/v1/research/artifacts", params={"api_key": rw})
        assert r_list_rw.status_code == 200
        assert r_list_rw.json()["total"] == 1
        assert r_list_rw.json()["artifacts"][0]["hash_prefix"] == digest[:12]

        r_get = client.get(
            f"/v1/research/artifacts/{aid}", params={"api_key": rw}
        )
        assert r_get.status_code == 200
        assert r_get.json()["proof"]["ok"] is True

        r_other = client.get(
            f"/v1/research/artifacts/{aid}", params={"api_key": ro}
        )
        assert r_other.status_code == 404

        r_zip = client.get(
            f"/v1/research/artifacts/{aid}/certificate",
            params={"api_key": rw},
        )
        assert r_zip.status_code == 200
        assert "application/zip" in r_zip.headers.get("content-type", "")
        disp = r_zip.headers.get("content-disposition", "")
        assert "ata_priority_" in disp
        with zipfile.ZipFile(io.BytesIO(r_zip.content), "r") as zf:
            assert set(zf.namelist()) == set(CERT_ZIP_NAMES)
    finally:
        td.cleanup()


def test_invalid_hash_rejected_in_domain():
    """非 64 hex 在领域层直接拒绝。"""
    td, db = _db()
    try:
        key = "ata_test_research_badhash"
        ensure_api_key(key, label="t", role="read_write", db_path=db)
        with pytest.raises(ValueError):
            register_artifact(
                api_key=key,
                title="x",
                kind="draft",
                artifact_hash="not-a-hash",
                db_path=db,
            )
    finally:
        td.cleanup()
