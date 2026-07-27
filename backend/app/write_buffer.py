"""Async buffered DB writes for proxy hot path.

Hash chain links are computed synchronously; an in-memory tip cache keeps
prev_hash correct across buffered inserts. Persistence is batched
(every 10 records or every 10 seconds).
"""

from __future__ import annotations

import atexit
import threading
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from models import insert_call, latest_chain_hash

GENESIS = "0" * 64

_BUFFER: List[Dict[str, Any]] = []
_TIPS: Dict[str, str] = {}
_BUF_LOCK = threading.Lock()
_FLUSH_SIZE = 10
_FLUSH_INTERVAL = 10.0
_started = False
_stop = threading.Event()


def _flush_locked() -> None:
    """Flush buffer. Caller must hold _BUF_LOCK.

    On insert failure, requeues the failed item and all remaining items
    (no nested lock acquire — avoids deadlock with non-reentrant Lock).
    """
    global _BUFFER
    if not _BUFFER:
        return
    batch = list(_BUFFER)
    _BUFFER = []
    for i, item in enumerate(batch):
        try:
            insert_call(item["record"], db_path=item.get("db_path"))
        except Exception:
            # Restore failed + not-yet-written items at the front
            _BUFFER = batch[i:] + _BUFFER
            return


def _worker() -> None:
    while not _stop.wait(_FLUSH_INTERVAL):
        with _BUF_LOCK:
            _flush_locked()


def _ensure_started() -> None:
    global _started
    if _started:
        return
    t = threading.Thread(target=_worker, name="ata-write-buffer", daemon=True)
    t.start()
    _started = True
    atexit.register(flush_now)


def note_chain_tip(api_key: str, chain_hash: str) -> None:
    """Update in-memory tip after a synchronous insert."""
    with _BUF_LOCK:
        _TIPS[api_key] = chain_hash


def peek_prev_hash(api_key: str, *, db_path: Optional[Path] = None) -> str:
    """Return latest chain tip.

    Prefer in-memory tip when present (covers buffered writes and tips reserved by
    ``build_next_record`` before DB insert). Load DB only when the cache is cold.
    Never overwrite a reserved/memory tip with a stale DB tip.
    """
    with _BUF_LOCK:
        tip = _TIPS.get(api_key)
        if tip:
            return tip
    db_tip = latest_chain_hash(api_key, db_path=db_path) or GENESIS
    with _BUF_LOCK:
        tip = _TIPS.get(api_key)
        if tip:
            return tip
        _TIPS[api_key] = db_tip
        return db_tip


def _allocate_link(
    api_key: str,
    build_fn: Callable[[str], Dict[str, Any]],
    *,
    db_path: Optional[Path] = None,
) -> Dict[str, Any]:
    """Resolve tip (DB only if cache cold), then build+advance under lock."""
    need_db = False
    with _BUF_LOCK:
        need_db = api_key not in _TIPS
    db_tip = GENESIS
    if need_db:
        db_tip = latest_chain_hash(api_key, db_path=db_path) or GENESIS
    with _BUF_LOCK:
        if api_key not in _TIPS:
            _TIPS[api_key] = db_tip
        prev = _TIPS.get(api_key) or GENESIS
        record = build_fn(prev)
        _TIPS[api_key] = str(record["chain_hash"])
        return record


def build_next_record(
    api_key: str,
    build_fn: Callable[[str], Dict[str, Any]],
    *,
    db_path: Optional[Path] = None,
) -> Dict[str, Any]:
    """Atomically allocate prev_hash, build record, and advance in-memory tip.

    ``build_fn(prev_hash)`` must return a record with ``chain_hash`` (and
    usually ``api_key``). Caller is responsible for persistence.
    """
    return _allocate_link(api_key, build_fn, db_path=db_path)


def enqueue_call(record: Dict[str, Any], *, db_path: Optional[Path] = None) -> None:
    """Queue attested call for async insert; update in-memory tip immediately."""
    _ensure_started()
    with _BUF_LOCK:
        _TIPS[record["api_key"]] = record["chain_hash"]
        _BUFFER.append({"record": record, "db_path": db_path})
        if len(_BUFFER) >= _FLUSH_SIZE:
            _flush_locked()


def enqueue_with_builder(
    api_key: str,
    build_fn: Callable[[str], Dict[str, Any]],
    *,
    db_path: Optional[Path] = None,
) -> Dict[str, Any]:
    """Build next chain link and enqueue under one tip lock (proxy hot path)."""
    _ensure_started()
    need_db = False
    with _BUF_LOCK:
        need_db = api_key not in _TIPS
    db_tip = latest_chain_hash(api_key, db_path=db_path) or GENESIS if need_db else GENESIS
    with _BUF_LOCK:
        if api_key not in _TIPS:
            _TIPS[api_key] = db_tip
        prev = _TIPS.get(api_key) or GENESIS
        record = build_fn(prev)
        _TIPS[api_key] = str(record["chain_hash"])
        _BUFFER.append({"record": record, "db_path": db_path})
        if len(_BUFFER) >= _FLUSH_SIZE:
            _flush_locked()
        return record


def flush_now() -> None:
    with _BUF_LOCK:
        _flush_locked()
