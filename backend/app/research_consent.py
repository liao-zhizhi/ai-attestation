"""训练同意记录（P1-C）：是否允许某厂商用数据训练。

每次变更追加上链 event_type=research_consent。不改 /v1/proxy。
当前有效规则：按 vendor 取最新一条；缺则回退 vendor='*'；再缺则为 unknown。
"""

from __future__ import annotations

import json
import re
import uuid
from typing import Any, Dict, List, Optional, Tuple

from fastapi import HTTPException

from attestation import (
    GENESIS,
    compute_research_consent_chain_hash,
    utc_now,
    verify_single_research_consent,
)
from key_auth import require_key
from models import insert_consent_record, list_consent_records
from write_buffer import build_next_record, flush_now

ALLOW_VALUES = ("unknown", "yes", "no")
ALLOW_LABELS = {"unknown": "未知", "yes": "允许", "no": "不允许"}
GLOBAL_VENDOR = "*"
_VENDOR_RE = re.compile(r"^(\*|[a-z0-9][a-z0-9._-]{0,62})$")
_HASH_RE = re.compile(r"^[0-9a-fA-F]{64}$")
KNOWN_VENDORS = ("openai", "deepseek", "anthropic", "zhipu")


def normalize_vendor(raw: Optional[str]) -> str:
    v = (raw or "").strip().lower()
    if not v or v in ("global", "default", "*"):
        return GLOBAL_VENDOR
    if not _VENDOR_RE.match(v):
        raise ValueError("vendor 只能是 * 或小写字母数字（可含 . _ -）")
    return v


def _public_row(row: Dict[str, Any]) -> Dict[str, Any]:
    """对外字段：不含 api_key。"""
    proof = verify_single_research_consent(row)
    return {
        "id": row.get("id"),
        "timestamp": row.get("timestamp"),
        "vendor": row.get("vendor"),
        "allow_training": row.get("allow_training"),
        "allow_label": ALLOW_LABELS.get(str(row.get("allow_training") or ""), "未知"),
        "source": row.get("source"),
        "policy_url": row.get("policy_url"),
        "policy_hash": row.get("policy_hash"),
        "note": row.get("note"),
        "prev_hash": row.get("prev_hash"),
        "chain_hash": row.get("chain_hash"),
        "chain_ok": bool(proof.get("ok")),
        "chain_status_label": "链完整" if proof.get("ok") else "链异常",
    }


def _latest_by_vendor(rows: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    """rows 已按时间倒序；每个 vendor 只留第一条。"""
    out: Dict[str, Dict[str, Any]] = {}
    for r in rows:
        v = str(r.get("vendor") or GLOBAL_VENDOR)
        if v not in out:
            out[v] = r
    return out


def current_consent(*, api_key: str, db_path=None) -> Dict[str, Any]:
    require_key(api_key, min_role="read_only", db_path=db_path, label="consent")
    rows = list_consent_records(api_key, limit=500, db_path=db_path)
    latest = _latest_by_vendor(rows)
    g = latest.get(GLOBAL_VENDOR)
    by_vendor = {
        k: _public_row(v) for k, v in latest.items() if k != GLOBAL_VENDOR
    }
    return {
        "global": _public_row(g) if g else None,
        "by_vendor": by_vendor,
        "known_vendors": list(KNOWN_VENDORS),
    }


def put_consent(
    *,
    api_key: str,
    vendor: str,
    allow_training: str,
    policy_url: Optional[str] = None,
    policy_hash: Optional[str] = None,
    note: Optional[str] = None,
    source: str = "user_dashboard",
    db_path=None,
) -> Dict[str, Any]:
    require_key(api_key, min_role="read_write", db_path=db_path, label="consent")
    allow = (allow_training or "").strip().lower()
    if allow not in ALLOW_VALUES:
        raise HTTPException(422, "allow_training 必须是 unknown / yes / no")
    try:
        vend = normalize_vendor(vendor)
    except ValueError as e:
        raise HTTPException(422, str(e)) from e
    url = (policy_url or "").strip() or None
    if url and len(url) > 500:
        raise HTTPException(422, "policy_url 最长 500 字")
    ph = (policy_hash or "").strip() or None
    if ph and not _HASH_RE.match(ph):
        raise HTTPException(422, "policy_hash 须为 64 位十六进制")
    if ph:
        ph = ph.lower()
    note_s = (note or "").strip() or None
    if note_s and len(note_s) > 500:
        raise HTTPException(422, "note 最长 500 字")
    src = (source or "user_dashboard").strip() or "user_dashboard"

    flush_now()
    cid = f"cns_{uuid.uuid4().hex[:16]}"
    attest_id = f"att_{uuid.uuid4().hex[:16]}"
    ts = utc_now()

    def _build(prev: str) -> Dict[str, Any]:
        p = prev or GENESIS
        chain_h = compute_research_consent_chain_hash(
            prev_hash=p,
            consent_id=cid,
            timestamp=ts,
            vendor=vend,
            allow_training=allow,
            policy_hash=ph or "",
        )
        return {
            "id": cid,
            "attest_id": attest_id,
            "api_key": api_key,
            "timestamp": ts,
            "vendor": vend,
            "allow_training": allow,
            "source": src,
            "policy_url": url,
            "policy_hash": ph,
            "note": note_s,
            "prev_hash": p,
            "chain_hash": chain_h,
        }

    record = build_next_record(api_key, _build, db_path=db_path)
    insert_consent_record(record, db_path=db_path)
    return {
        "ok": True,
        "record": _public_row(record),
        "proof": verify_single_research_consent(record),
    }


def consent_report(*, api_key: str, db_path=None) -> Dict[str, Any]:
    require_key(api_key, min_role="read_only", db_path=db_path, label="consent")
    rows = list_consent_records(api_key, limit=500, db_path=db_path)
    current = current_consent(api_key=api_key, db_path=db_path)
    history = [
        {
            "timestamp": r.get("timestamp"),
            "vendor": r.get("vendor"),
            "allow_training": r.get("allow_training"),
            "allow_label": ALLOW_LABELS.get(str(r.get("allow_training") or ""), "未知"),
            "policy_url": r.get("policy_url"),
            "policy_hash": r.get("policy_hash"),
            "note": r.get("note"),
            "chain_hash": r.get("chain_hash"),
            "prev_hash": r.get("prev_hash"),
            "id": r.get("id"),
            "chain_ok": bool(verify_single_research_consent(r).get("ok")),
        }
        for r in rows
    ]
    return {
        "current": {"global": current.get("global"), "by_vendor": current.get("by_vendor")},
        "history": history,
        "n": len(history),
    }


def consent_report_text(report: Dict[str, Any]) -> str:
    """可读摘要，风格对齐合规 TXT 导出。"""
    lines = [
        "ai-attestation — Training Consent Report",
        "训练数据同意审计摘要",
        "",
        "当前有效同意（按厂商最新一条；缺则回退全局 *；再缺则为未知）",
        "",
    ]
    cur = report.get("current") or {}
    g = cur.get("global")
    if g:
        lines.append(
            f"global (*): {g.get('allow_label') or g.get('allow_training')}  "
            f"at {g.get('timestamp')}  chain={g.get('chain_hash')}"
        )
    else:
        lines.append("global (*): 未知（尚未记录）")
    byv = cur.get("by_vendor") or {}
    if byv:
        lines.append("vendor overrides:")
        for name, row in sorted(byv.items()):
            lines.append(
                f"  {name}: {row.get('allow_label') or row.get('allow_training')}  "
                f"at {row.get('timestamp')}  chain={row.get('chain_hash')}"
            )
    else:
        lines.append("vendor overrides: (none)")
    lines.append("")
    lines.append("变更历史（新→旧）")
    lines.append("")
    for h in report.get("history") or []:
        lines.append(
            f"{h.get('timestamp')}  vendor={h.get('vendor')}  "
            f"allow={h.get('allow_training')}  policy_hash={h.get('policy_hash') or '-'}  "
            f"chain_hash={h.get('chain_hash')}"
        )
    lines.append("")
    lines.append("本摘要是技术证据时间线，不是法律意见，也不能证明厂商是否训练了你的数据。")
    return "\n".join(lines) + "\n"


def export_consent_report(
    *, api_key: str, fmt: str, db_path=None
) -> Tuple[bytes, str, str]:
    """返回 (body, media_type, filename)。"""
    report = consent_report(api_key=api_key, db_path=db_path)
    kind = (fmt or "txt").strip().lower()
    if kind == "json":
        body = json.dumps(report, ensure_ascii=False, indent=2).encode("utf-8")
        return body, "application/json", "ata_consent_report.json"
    text = consent_report_text(report)
    return text.encode("utf-8"), "text/plain; charset=utf-8", "ata_consent_report.txt"
