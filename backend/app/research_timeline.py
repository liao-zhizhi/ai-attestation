"""科研时间线（P1）：把 API 调用关联到已登记工件。

上链 event_type=research_timeline。取消关联用软删除，避免整链校验失败。
"""

from __future__ import annotations

import uuid
from typing import Any, Dict, Optional

from fastapi import HTTPException

from attestation import (
    GENESIS,
    compute_research_timeline_chain_hash,
    utc_now,
    verify_single_call,
    verify_single_research_timeline,
)
from key_auth import require_key
from models import (
    find_active_timeline_link,
    get_call,
    get_research_artifact,
    get_research_timeline,
    insert_research_timeline,
    list_linked_calls,
    list_research_timeline,
    soft_delete_research_timeline,
)
from write_buffer import build_next_record, flush_now


def _public_timeline(row: Dict[str, Any]) -> Dict[str, Any]:
    """对外字段：不含 api_key。"""
    return {
        "id": row.get("id"),
        "timestamp": row.get("timestamp"),
        "event_kind": row.get("event_kind"),
        "artifact_id": row.get("artifact_id"),
        "call_id": row.get("call_id"),
        "vendor": row.get("vendor"),
        "model": row.get("model"),
        "label": row.get("label"),
        "prev_hash": row.get("prev_hash"),
        "chain_hash": row.get("chain_hash"),
        "deleted": bool(row.get("deleted")),
    }


def link_call_to_artifact(
    *,
    api_key: str,
    call_id: str,
    artifact_id: str,
    label: Optional[str] = None,
    db_path=None,
) -> Dict[str, Any]:
    """把一次调用挂到工件上并写入哈希链。"""
    require_key(api_key, min_role="read_write", db_path=db_path, label="timeline")
    call = get_call(call_id, db_path=db_path)
    if not call or call.get("api_key") != api_key:
        raise HTTPException(404, "call not found")
    art = get_research_artifact(artifact_id, db_path=db_path)
    if not art or art.get("api_key") != api_key:
        raise HTTPException(404, "artifact not found")
    existing = find_active_timeline_link(
        api_key, artifact_id=artifact_id, call_id=call_id, db_path=db_path
    )
    if existing:
        return {
            "ok": True,
            "already_linked": True,
            "timeline": _public_timeline(existing),
            "proof": verify_single_research_timeline(existing),
        }

    flush_now()
    tid = f"rtl_{uuid.uuid4().hex[:16]}"
    attest_id = f"att_{uuid.uuid4().hex[:16]}"
    ts = utc_now()
    vendor = str(call.get("vendor") or "")
    model = str(call.get("model") or "")
    note = (label or "").strip() or None

    def _build(prev: str) -> Dict[str, Any]:
        p = prev or GENESIS
        chain_h = compute_research_timeline_chain_hash(
            prev_hash=p,
            timeline_id=tid,
            timestamp=ts,
            artifact_id=artifact_id,
            call_id=call_id,
            vendor=vendor,
            model=model,
        )
        return {
            "id": tid,
            "attest_id": attest_id,
            "api_key": api_key,
            "timestamp": ts,
            "event_kind": "api_call",
            "artifact_id": artifact_id,
            "call_id": call_id,
            "vendor": vendor,
            "model": model,
            "label": note,
            "prev_hash": p,
            "chain_hash": chain_h,
            "deleted": 0,
        }

    record = build_next_record(api_key, _build, db_path=db_path)
    insert_research_timeline(record, db_path=db_path)
    return {
        "ok": True,
        "already_linked": False,
        "timeline": _public_timeline(record),
        "proof": verify_single_research_timeline(record),
    }


def list_timeline(
    *,
    api_key: str,
    artifact_id: Optional[str] = None,
    limit: int = 200,
    db_path=None,
) -> Dict[str, Any]:
    require_key(api_key, min_role="read_only", db_path=db_path, label="timeline")
    rows = list_research_timeline(
        api_key, artifact_id=artifact_id, limit=limit, db_path=db_path
    )
    return {
        "n": len(rows),
        "timeline": [_public_timeline(r) for r in rows],
    }


def unlink_timeline(*, api_key: str, timeline_id: str, db_path=None) -> Dict[str, Any]:
    """取消关联：软删除。链上记录仍可重算。"""
    require_key(api_key, min_role="read_write", db_path=db_path, label="timeline")
    row = get_research_timeline(timeline_id, db_path=db_path)
    if not row or row.get("api_key") != api_key or row.get("deleted"):
        raise HTTPException(404, "timeline not found")
    ok = soft_delete_research_timeline(timeline_id, api_key, db_path=db_path)
    if not ok:
        raise HTTPException(404, "timeline not found")
    return {"ok": True}


def linked_calls_for_artifact(
    *,
    api_key: str,
    artifact_id: str,
    db_path=None,
) -> Dict[str, Any]:
    require_key(api_key, min_role="read_only", db_path=db_path, label="timeline")
    art = get_research_artifact(artifact_id, db_path=db_path)
    if not art or art.get("api_key") != api_key:
        raise HTTPException(404, "artifact not found")
    rows = list_linked_calls(api_key, artifact_id, db_path=db_path)
    items = []
    for r in rows:
        chain_ok = False
        cid = str(r.get("call_id") or "")
        full = get_call(cid, db_path=db_path) if cid else None
        if full and full.get("api_key") == api_key:
            chain_ok = bool(verify_single_call(full).get("ok"))
        items.append(
            {
                "timeline_id": r.get("timeline_id"),
                "call_id": r.get("call_id"),
                "timestamp": r.get("call_timestamp") or r.get("linked_at"),
                "model": r.get("call_model") or r.get("model"),
                "vendor": r.get("vendor"),
                "label": r.get("label"),
                "chain_hash": r.get("call_chain_hash"),
                "chain_ok": chain_ok,
                "chain_status_label": "链完整" if chain_ok else "链异常",
            }
        )
    return {"n": len(items), "calls": items}
