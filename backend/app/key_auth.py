"""API key role checks for proxy + dashboard."""

from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import Header, HTTPException, Query
from models import get_api_key_row, touch_api_key

ROLES = ("read_only", "read_write", "admin")
ACTIVE = "active"


def resolve_api_key(
    api_key: Optional[str] = Query(None, min_length=8),
    x_attest_key: Optional[str] = Header(None, alias="X-Attest-Key"),
) -> str:
    """Accept dashboard key from query or ``X-Attest-Key`` header (prefer header)."""
    key = (x_attest_key or api_key or "").strip()
    if len(key) < 8:
        raise HTTPException(401, "missing api key")
    return key


def require_key(
    api_key: str,
    *,
    min_role: str = "read_only",
    for_proxy: bool = False,
    db_path=None,
    label: str = "access",
) -> Dict[str, Any]:
    """Validate key exists, is active, and meets role floor.

    Role order: read_only < read_write < admin.
    Proxy requires at least read_write.

    Unknown keys are rejected (401). Provision via POST /v1/keys or ensure_api_key.
    """
    del label  # kept for call-site compatibility
    if not api_key or len(api_key) < 8:
        raise HTTPException(401, "invalid api key")
    row = get_api_key_row(api_key, db_path=db_path)
    if not row:
        raise HTTPException(401, "unknown api key")
    status = (row.get("status") or ACTIVE).lower()
    if status == "deleted":
        raise HTTPException(403, "api key deleted")
    if status == "disabled":
        raise HTTPException(403, "api key disabled")
    role = (row.get("role") or "read_only").lower()
    if role not in ROLES:
        # Unknown / corrupt role → least privilege (not read_write)
        role = "read_only"
    order = {r: i for i, r in enumerate(ROLES)}
    need = "read_write" if for_proxy else min_role
    if order.get(role, 1) < order.get(need, 0):
        if for_proxy:
            raise HTTPException(403, "read_only key cannot use proxy")
        raise HTTPException(403, f"requires role >= {need}")
    touch_api_key(api_key, db_path=db_path)
    return {
        "api_key": api_key,
        "name": row.get("name") or row.get("label") or "",
        "role": role,
        "status": status,
    }


def mask_key(api_key: str) -> str:
    if len(api_key) <= 8:
        return api_key[:2] + "****"
    return api_key[:8] + "****"
