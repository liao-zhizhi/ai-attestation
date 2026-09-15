"""科研优先权见证（P0）：只接受客户端 SHA-256，不接收原文。

用户在浏览器本地算指纹后登记到统一哈希链，并导出离线优先权证书。
不修改 /v1/proxy 与 api_calls。
"""

from __future__ import annotations

import re
import uuid
from typing import Any, Dict, List, Optional

from anchoring import stamp_hash
from attestation import (
    GENESIS,
    compute_research_artifact_chain_hash,
    utc_now,
    verify_single_research_artifact,
)
from key_auth import require_key
from models import (
    count_research_artifacts,
    get_research_artifact,
    insert_research_artifact,
    list_prior_artifact_hashes,
    list_research_artifacts,
)
from write_buffer import build_next_record, flush_now

# 仅允许 64 位小写 hex；登记前会把大写规范化。
_HASH_RE = re.compile(r"^[0-9a-f]{64}$")
_KINDS = ("draft", "derivation", "prompt", "note", "other")
_MAX_ARTIFACTS = 10_000
_MAX_TITLE = 200
PACK_TYPE = "ata-research-priority-v1"


def normalize_artifact_hash(value: str) -> str:
    """去掉空白并转小写；非法则抛 ValueError。"""
    h = (value or "").strip().lower()
    if not _HASH_RE.match(h):
        raise ValueError("artifact_hash 必须是 64 位十六进制 SHA-256（不含原文）")
    return h


def _earlier_priors(
    priors: List[Dict[str, Any]],
    *,
    current_id: str,
    current_ts: str,
) -> List[Dict[str, Any]]:
    """只保留比当前记录更早的同指纹登记（后登记的不应让先登记显示提示）。"""
    out: List[Dict[str, Any]] = []
    for p in priors:
        if str(p.get("id") or "") == current_id:
            continue
        pts = str(p.get("timestamp") or "")
        if pts < current_ts or (pts == current_ts and str(p.get("id") or "") < current_id):
            out.append(p)
    return out


def _duplicate_notice(priors: List[Dict[str, Any]]) -> Optional[str]:
    """列表/详情上的重复提示：该指纹已于某时登记过。"""
    if not priors:
        return None
    first = priors[0].get("timestamp") or ""
    return f"该指纹已于 {first} 登记过"


def register_artifact(
    *,
    api_key: str,
    title: str,
    kind: str,
    artifact_hash: str,
    byte_length: Optional[int] = None,
    filename_hint: Optional[str] = None,
    authors_label: Optional[str] = None,
    description: Optional[str] = None,
    client_hashed: bool = True,
    db_path=None,
) -> Dict[str, Any]:
    """登记科研工件：只写入哈希与元数据，立即同步上链并盖本地 TSA。"""
    require_key(api_key, min_role="read_write", db_path=db_path, label="research")
    digest = normalize_artifact_hash(artifact_hash)
    k = (kind or "draft").strip().lower()
    if k not in _KINDS:
        raise ValueError(f"kind 须为 {', '.join(_KINDS)} 之一")
    title_s = (title or "").strip() or "未命名工件"
    if len(title_s) > _MAX_TITLE:
        raise ValueError(f"title 最长 {_MAX_TITLE} 字")
    if byte_length is not None and int(byte_length) < 0:
        raise ValueError("byte_length 不能为负")
    n = count_research_artifacts(api_key, db_path=db_path)
    if n >= _MAX_ARTIFACTS:
        raise ValueError(f"已达到单 Key 工件上限 {_MAX_ARTIFACTS}")

    priors = list_prior_artifact_hashes(api_key, digest, db_path=db_path)
    # 优先权存证必须立刻落盘，避免缓冲延迟造成时间歧义
    flush_now()
    artifact_id = f"art_{uuid.uuid4().hex[:16]}"
    attest_id = f"att_{uuid.uuid4().hex[:16]}"
    ts = utc_now()
    tsa = stamp_hash(digest)

    def _build(prev: str) -> Dict[str, Any]:
        p = prev or GENESIS
        chain_h = compute_research_artifact_chain_hash(
            prev_hash=p,
            artifact_id=artifact_id,
            timestamp=ts,
            artifact_hash=digest,
            kind=k,
        )
        return {
            "id": artifact_id,
            "attest_id": attest_id,
            "api_key": api_key,
            "timestamp": ts,
            "title": title_s,
            "kind": k,
            "artifact_hash": digest,
            "hash_alg": "sha256",
            "byte_length": int(byte_length) if byte_length is not None else None,
            "filename_hint": (filename_hint or "").strip() or None,
            "authors_label": (authors_label or "").strip() or None,
            "description": (description or "").strip() or None,
            "client_hashed": bool(client_hashed),
            "prev_hash": p,
            "chain_hash": chain_h,
            "tsa_receipt": tsa,
            "status": "active",
            "superseded_by": None,
        }

    record = build_next_record(api_key, _build, db_path=db_path)
    insert_research_artifact(record, db_path=db_path)
    proof = verify_single_research_artifact(record)
    notice = _duplicate_notice(priors)
    public = public_artifact(record)
    return {
        "ok": True,
        "artifact": public,
        "proof": proof,
        "duplicate_notice": notice,
        "prior_registrations": [
            {"id": p["id"], "timestamp": p["timestamp"], "title": p.get("title")}
            for p in priors
        ],
        "disclaimer": "技术存证，不构成法律意见或学术优先权裁定。原文未上传、未入库。",
    }


def public_artifact(row: Dict[str, Any]) -> Dict[str, Any]:
    """对外字段：不含 api_key、不含原文。"""
    return {
        "pack_type": PACK_TYPE,
        "id": row.get("id"),
        "timestamp": row.get("timestamp"),
        "title": row.get("title"),
        "kind": row.get("kind"),
        "artifact_hash": row.get("artifact_hash"),
        "hash_alg": row.get("hash_alg") or "sha256",
        "byte_length": row.get("byte_length"),
        "filename_hint": row.get("filename_hint"),
        "authors_label": row.get("authors_label"),
        "description": row.get("description"),
        "client_hashed": bool(row.get("client_hashed")),
        "prev_hash": row.get("prev_hash"),
        "chain_hash": row.get("chain_hash"),
        "status": row.get("status") or "active",
        "tsa_receipt": row.get("tsa_receipt"),
    }


def list_artifacts_for_key(
    *,
    api_key: str,
    limit: int = 50,
    offset: int = 0,
    db_path=None,
) -> Dict[str, Any]:
    require_key(api_key, min_role="read_only", db_path=db_path, label="research")
    total = count_research_artifacts(api_key, db_path=db_path)
    rows = list_research_artifacts(
        api_key, limit=limit, offset=offset, db_path=db_path
    )
    lean = []
    for r in rows:
        priors = list_prior_artifact_hashes(
            api_key,
            str(r.get("artifact_hash") or ""),
            exclude_id=str(r.get("id") or ""),
            db_path=db_path,
        )
        earlier = _earlier_priors(
            priors,
            current_id=str(r.get("id") or ""),
            current_ts=str(r.get("timestamp") or ""),
        )
        first = earlier[0] if earlier else None
        proof = verify_single_research_artifact(r)
        notice = _duplicate_notice(earlier)
        lean.append(
            {
                "id": r["id"],
                "timestamp": r["timestamp"],
                "title": r.get("title"),
                "kind": r.get("kind"),
                "artifact_hash": r.get("artifact_hash"),
                "hash_prefix": str(r.get("artifact_hash") or "")[:12],
                "chain_ok": bool(proof.get("ok")),
                "chain_hash": r.get("chain_hash"),
                "duplicate_notice": notice,
                "first_seen_at": (first or {}).get("timestamp"),
            }
        )
    return {
        "n": len(lean),
        "total": total,
        "limit": limit,
        "offset": offset,
        "has_more": offset + len(lean) < total,
        "artifacts": lean,
        "disclaimer": "只保存指纹。请自行保管原件。本记录不构成法律意见。",
    }


def get_artifact_detail(
    *,
    api_key: str,
    artifact_id: str,
    db_path=None,
) -> Dict[str, Any]:
    require_key(api_key, min_role="read_only", db_path=db_path, label="research")
    row = get_research_artifact(artifact_id, db_path=db_path)
    if not row or row.get("api_key") != api_key:
        return {}
    priors = list_prior_artifact_hashes(
        api_key,
        str(row.get("artifact_hash") or ""),
        exclude_id=artifact_id,
        db_path=db_path,
    )
    earlier = _earlier_priors(
        priors,
        current_id=artifact_id,
        current_ts=str(row.get("timestamp") or ""),
    )
    return {
        "artifact": public_artifact(row),
        "proof": verify_single_research_artifact(row),
        "duplicate_notice": _duplicate_notice(earlier),
        "prior_registrations": [
            {"id": p["id"], "timestamp": p["timestamp"], "title": p.get("title")}
            for p in earlier
        ],
        "disclaimer": "技术存证，不构成法律意见或学术优先权裁定。",
    }
