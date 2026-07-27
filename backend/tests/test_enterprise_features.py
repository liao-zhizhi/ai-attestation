"""Enterprise features: report mail, key roles, export."""

from __future__ import annotations

import tempfile
from pathlib import Path

from export_calls import iter_export_rows, rows_to_csv, rows_to_json
from key_auth import require_key
from models import (
    create_api_key_record,
    ensure_api_key,
    init_db,
    insert_call,
    update_api_key,
    upsert_report_subscription,
)
from report_mail import (
    build_report_payload,
    deliver_html,
    render_report_html,
    send_subscription_report,
)
from attestation import build_call_record
from fastapi import HTTPException


def _db():
    td = tempfile.TemporaryDirectory()
    path = Path(td.name) / "t.db"
    init_db(path)
    return td, path


def test_report_html_and_file_fallback():
    td, db = _db()
    try:
        key = "ata_test_report_key01"
        ensure_api_key(key, label="t", role="admin", db_path=db)
        prev = "0" * 64
        for i in range(3):
            rec = build_call_record(
                api_key=key,
                prev_hash=prev,
                endpoint="/v1/chat/completions",
                method="POST",
                model="gpt-4o-mini",
                status_code=200,
                request_body=b'{"m":1}',
                response_body=b'{"usage":{"prompt_tokens":10,"completion_tokens":5}}',
                duration_ms=1,
                prompt_tokens=10,
                completion_tokens=5,
                cost_usd=0.001,
                vendor="openai",
            )
            insert_call(rec, db_path=db)
            prev = rec["chain_hash"]
        payload = build_report_payload(
            api_key=key,
            frequency="weekly",
            content_options={
                "api_overview": True,
                "drift_summary": True,
                "compliance_summary": True,
            },
            db_path=db,
        )
        html = render_report_html(payload)
        assert "调用总数" in html
        assert "<html" in html.lower()
        status, path = deliver_html(
            to_emails=["a@example.com"], subject="t", html_body=html
        )
        assert status == "success"
        assert path and path.endswith(".html")
        assert Path(path).exists()
    finally:
        td.cleanup()


def test_subscription_send_records_history():
    td, db = _db()
    try:
        key = "ata_test_sub_key0001"
        ensure_api_key(key, label="t", role="admin", db_path=db)
        upsert_report_subscription(
            {
                "id": "rsub_test1",
                "api_key": key,
                "email": "ops@example.com",
                "frequency": "daily",
                "content_options": {"api_overview": True},
                "last_sent_at": None,
                "created_at": "2026-01-01T00:00:00Z",
            },
            db_path=db,
        )
        out = send_subscription_report(
            subscription_id="rsub_test1", db_path=db, test=True
        )
        assert out["ok"] is True
        assert out["status"] == "success"
    finally:
        td.cleanup()


def test_read_only_cannot_proxy():
    td, db = _db()
    try:
        rec = create_api_key_record(name="ro", role="read_only", db_path=db)
        try:
            require_key(rec["api_key"], for_proxy=True, db_path=db)
            assert False, "should raise"
        except HTTPException as e:
            assert e.status_code == 403
        me = require_key(rec["api_key"], min_role="read_only", db_path=db)
        assert me["role"] == "read_only"
    finally:
        td.cleanup()


def test_disabled_key_rejected():
    td, db = _db()
    try:
        rec = create_api_key_record(name="x", role="read_write", db_path=db)
        update_api_key(rec["api_key"], status="disabled", db_path=db)
        try:
            require_key(rec["api_key"], min_role="read_only", db_path=db)
            assert False
        except HTTPException as e:
            assert e.status_code == 403
    finally:
        td.cleanup()


def test_export_csv_bom():
    td, db = _db()
    try:
        key = "ata_test_export_key01"
        ensure_api_key(key, label="t", db_path=db)
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
        rows = list(iter_export_rows(key, time_range="all", db_path=db))
        assert len(rows) >= 1
        csv_bytes = rows_to_csv(rows)
        assert csv_bytes.startswith(b"\xef\xbb\xbf")
        assert "厂商".encode("utf-8") in csv_bytes
        js = rows_to_json(rows)
        assert b"deepseek" in js
    finally:
        td.cleanup()
