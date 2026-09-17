"""公开验证链接（P1）：生成/撤销 token，甲方无需登录即可核对哈希链。

不返回 api_key、租户信息、请求/响应原文。不改旧 ZIP 格式。
"""

from __future__ import annotations

import secrets
from typing import Any, Dict, Optional
from urllib.parse import urlparse

from fastapi import HTTPException, Request

from attestation import utc_now, verify_single_call, verify_single_research_artifact
from key_auth import require_key
from models import (
    bump_share_views,
    get_active_share,
    get_call,
    get_public_share,
    get_research_artifact,
    insert_public_share,
    revoke_public_share,
)

PUBLIC_SITE_DEFAULT = "https://ai-attestation.com"
_TARGET_TYPES = ("call", "artifact")


def public_frontend_origin(request: Optional[Request] = None) -> str:
    """公开页在前端站点（默认生产域名）；本机开发跟 Referer 走 :3002。"""
    if request is not None:
        ref = request.headers.get("referer") or ""
        if "localhost:3002" in ref or "127.0.0.1:3002" in ref:
            p = urlparse(ref)
            if p.scheme and p.netloc:
                return f"{p.scheme}://{p.netloc}"
        host = (
            request.headers.get("x-forwarded-host")
            or request.headers.get("host")
            or ""
        )
        if "ai-attestation.com" in host:
            return "https://ai-attestation.com"
        origin = request.headers.get("origin") or ""
        if "localhost:3002" in origin or "127.0.0.1:3002" in origin:
            return origin.rstrip("/")
    return PUBLIC_SITE_DEFAULT


def share_public_url(target_type: str, token: str, *, request: Optional[Request] = None) -> str:
    origin = public_frontend_origin(request)
    return f"{origin}/verify/{target_type}/{token}"


def _assert_target_owned(*, api_key: str, target_type: str, target_id: str, db_path=None) -> None:
    if target_type == "call":
        row = get_call(target_id, db_path=db_path)
        if not row or row.get("api_key") != api_key:
            raise HTTPException(404, "call not found")
        return
    if target_type == "artifact":
        row = get_research_artifact(target_id, db_path=db_path)
        if not row or row.get("api_key") != api_key:
            raise HTTPException(404, "artifact not found")
        return
    raise HTTPException(400, "target_type 须为 call 或 artifact")


def create_or_get_share(
    *,
    api_key: str,
    target_type: str,
    target_id: str,
    request: Optional[Request] = None,
    db_path=None,
) -> Dict[str, Any]:
    """幂等：已有未撤销链接则直接返回。需要 read_write。"""
    require_key(api_key, min_role="read_write", db_path=db_path, label="public_share")
    tt = (target_type or "").strip().lower()
    if tt not in _TARGET_TYPES:
        raise HTTPException(400, "target_type 须为 call 或 artifact")
    tid = (target_id or "").strip()
    if not tid:
        raise HTTPException(400, "缺少 target_id")
    _assert_target_owned(api_key=api_key, target_type=tt, target_id=tid, db_path=db_path)
    existing = get_active_share(
        api_key, target_type=tt, target_id=tid, db_path=db_path
    )
    if existing:
        token = str(existing["token"])
        return {"token": token, "url": share_public_url(tt, token, request=request), "created": False}
    token = secrets.token_urlsafe(24)
    insert_public_share(
        {
            "token": token,
            "api_key": api_key,
            "target_type": tt,
            "target_id": tid,
            "created_at": utc_now(),
            "revoked": 0,
            "revoked_at": None,
            "view_count": 0,
        },
        db_path=db_path,
    )
    return {"token": token, "url": share_public_url(tt, token, request=request), "created": True}


def lookup_share(
    *,
    api_key: str,
    target_type: str,
    target_id: str,
    request: Optional[Request] = None,
    db_path=None,
) -> Dict[str, Any]:
    """查询当前有效公开链接（只读即可）。没有则 token=null。"""
    require_key(api_key, min_role="read_only", db_path=db_path, label="public_share")
    tt = (target_type or "").strip().lower()
    existing = get_active_share(
        api_key, target_type=tt, target_id=target_id, db_path=db_path
    )
    if not existing:
        return {"token": None, "url": None}
    token = str(existing["token"])
    return {"token": token, "url": share_public_url(tt, token, request=request)}


def revoke_share(*, api_key: str, token: str, db_path=None) -> Dict[str, Any]:
    require_key(api_key, min_role="read_write", db_path=db_path, label="public_share")
    row = get_public_share(token, db_path=db_path)
    if not row or row.get("api_key") != api_key:
        raise HTTPException(404, "share not found")
    if int(row.get("revoked") or 0) == 1:
        return {"ok": True, "already_revoked": True}
    ok = revoke_public_share(token, api_key, revoked_at=utc_now(), db_path=db_path)
    if not ok:
        raise HTTPException(404, "share not found")
    return {"ok": True}


def _public_call_payload(row: Dict[str, Any]) -> Dict[str, Any]:
    """白名单字段：绝不能带 api_key / 原文。"""
    proof = verify_single_call(row)
    ok = bool(proof.get("ok"))
    return {
        "target_type": "call",
        "timestamp": row.get("timestamp"),
        "model": row.get("model"),
        "vendor": row.get("vendor"),
        "endpoint": row.get("endpoint"),
        "status_code": row.get("status_code"),
        "cost_usd": row.get("cost_usd"),
        "prompt_tokens": row.get("prompt_tokens"),
        "completion_tokens": row.get("completion_tokens"),
        "request_hash": row.get("request_hash"),
        "response_hash": row.get("response_hash"),
        "prev_hash": row.get("prev_hash"),
        "chain_hash": row.get("chain_hash"),
        "chain_ok": ok,
        "chain_status": "intact" if ok else "broken",
        "chain_status_label": "链完整" if ok else "链异常",
    }


def _public_artifact_payload(row: Dict[str, Any]) -> Dict[str, Any]:
    proof = verify_single_research_artifact(row)
    ok = bool(proof.get("ok"))
    return {
        "target_type": "artifact",
        "timestamp": row.get("timestamp"),
        "title": row.get("title"),
        "kind": row.get("kind"),
        "artifact_hash": row.get("artifact_hash"),
        "byte_length": row.get("byte_length"),
        "authors_label": row.get("authors_label"),
        "prev_hash": row.get("prev_hash"),
        "chain_hash": row.get("chain_hash"),
        "chain_ok": ok,
        "chain_status": "intact" if ok else "broken",
        "chain_status_label": "链完整" if ok else "链异常",
    }


def public_verify_call(token: str, *, db_path=None) -> Dict[str, Any]:
    """无需鉴权。撤销或不存在 → 404。"""
    share = get_public_share(token, db_path=db_path)
    if (
        not share
        or int(share.get("revoked") or 0) == 1
        or share.get("target_type") != "call"
    ):
        raise HTTPException(404, "公开链接不存在或已撤销")
    row = get_call(str(share.get("target_id") or ""), db_path=db_path)
    if not row or row.get("api_key") != share.get("api_key"):
        raise HTTPException(404, "公开链接不存在或已撤销")
    bump_share_views(token, db_path=db_path)
    out = _public_call_payload(row)
    out["view_count"] = int(share.get("view_count") or 0) + 1
    out["disclaimer"] = "此页面数据由 ai-attestation.com 独立见证，可离线复核。这不是法律意见。"
    if "api_key" in out:
        del out["api_key"]
    return out


def public_verify_artifact(token: str, *, db_path=None) -> Dict[str, Any]:
    share = get_public_share(token, db_path=db_path)
    if (
        not share
        or int(share.get("revoked") or 0) == 1
        or share.get("target_type") != "artifact"
    ):
        raise HTTPException(404, "公开链接不存在或已撤销")
    row = get_research_artifact(str(share.get("target_id") or ""), db_path=db_path)
    if not row or row.get("api_key") != share.get("api_key"):
        raise HTTPException(404, "公开链接不存在或已撤销")
    bump_share_views(token, db_path=db_path)
    out = _public_artifact_payload(row)
    out["view_count"] = int(share.get("view_count") or 0) + 1
    out["disclaimer"] = "此页面数据由 ai-attestation.com 独立见证，可离线复核。这不是法律意见。"
    if "api_key" in out:
        del out["api_key"]
    return out
