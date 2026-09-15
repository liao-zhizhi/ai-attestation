"""Write-buffer flush must not deadlock or rewind the in-memory chain tip."""

from __future__ import annotations

import sys
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeout
from pathlib import Path

APP = Path(__file__).resolve().parents[1] / "app"
sys.path.insert(0, str(APP))

from attestation import build_call_record
from models import ensure_api_key, init_db, list_calls
from write_buffer import _FLUSH_SIZE, enqueue_with_builder, flush_now, peek_prev_hash


def _build(key: str, i: int):
    def _fn(prev: str):
        return build_call_record(
            api_key=key,
            prev_hash=prev,
            endpoint="/v1/chat/completions",
            method="POST",
            model="gpt-4o-mini",
            status_code=200,
            request_body=f'{{"n":{i}}}'.encode(),
            response_body=b"{}",
            duration_ms=1,
            prompt_tokens=1,
            completion_tokens=1,
            cost_usd=0.001,
        )

    return _fn


def test_enqueue_flush_threshold_does_not_deadlock(tmp_path):
    db = tmp_path / "buf.db"
    init_db(db)
    key = "ata_test_wbuf_flush_k1"
    ensure_api_key(key, label="t", role="admin", db_path=db)
    flush_now()

    def _run():
        last = None
        for i in range(_FLUSH_SIZE):
            last = enqueue_with_builder(key, _build(key, i), db_path=db)
        flush_now()
        return last

    with ThreadPoolExecutor(max_workers=1) as ex:
        fut = ex.submit(_run)
        try:
            last = fut.result(timeout=15)
        except FuturesTimeout:
            raise AssertionError("write-buffer flush deadlocked") from None

    rows = list_calls(key, limit=50, db_path=db)
    assert len(rows) == _FLUSH_SIZE
    assert last is not None
    assert peek_prev_hash(key, db_path=db) == last["chain_hash"]
    # Chain is linear: unique prev_hash values
    prevs = {r["prev_hash"] for r in rows}
    hashes = {r["chain_hash"] for r in rows}
    assert len(hashes) == _FLUSH_SIZE
    assert len(prevs) == _FLUSH_SIZE
