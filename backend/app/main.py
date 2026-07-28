"""ai-attestation API — MVP FastAPI entry.

Open-source MVP: technical attestation tooling — not legal advice or certified audit.
"""

from __future__ import annotations

import os
from typing import Any, Dict, List, Optional

from fastapi import Depends, FastAPI, HTTPException, Query, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from anchoring import (
    anchor_chain_head,
    attach_timestamp_to_report,
    latest_anchor,
    list_anchors,
    stamp_hash,
    verify_tsa_receipt,
)
from tee_stub import tee_attestation_stub
from verify_pack import (
    build_verify_pack,
    decode_pack,
    encode_pack,
    pack_integrity_token,
    report_to_oscal,
    verify_pack,
)
from attestation import (
    GENESIS,
    build_call_record,
    verify_key_chain,
    verify_single_baseline,
    verify_single_call,
    verify_single_compliance,
    verify_single_drift_mark,
    verify_single_query,
)
from models import (
    ensure_api_key,
    count_calls,
    create_api_key_record,
    dashboard_overview,
    get_baseline,
    get_call,
    get_compliance,
    get_drift_mark,
    get_query,
    get_report_subscription_for_key,
    init_db,
    insert_call,
    latest_chain_hash,
    list_api_keys,
    list_baselines,
    list_calls,
    list_chain,
    list_compliance,
    list_drift_marks,
    list_queries,
    list_report_history_for_key,
    update_api_key,
    upsert_report_subscription,
)
from metering import estimate_cost_usd
from proxy import forward_openai
from query_audit import execute_attested_query
from key_auth import mask_key, require_key, resolve_api_key
from report_mail import send_subscription_async, start_report_scheduler
from export_calls import iter_export_rows, rows_to_csv, rows_to_json
from compliance import (
    check_evidence_detail,
    compare_compliance,
    compare_standards,
    execute_compliance_check,
    gap_analysis,
    list_standards,
    report_to_simple_pdf,
    report_to_text,
)
from compliance_impact import impact_analysis_from_change
from compliance_guardrails import test_rule_against_history
from compliance_catalog import STANDARD_EU_AI_ACT_TRANSPARENCY  # noqa: F401 — re-export/docs
from compliance_catalog import template_update_notices
from compliance_custom import (
    check_method_helper,
    delete_custom_template,
    export_custom_yaml,
    get_custom_template,
    import_custom_yaml,
    list_custom_templates,
    pin_template_version,
    publish_draft,
    save_custom_template,
)
from verify_offline import (
    build_chain_path,
    build_notarization_request,
    build_offline_zip,
    build_call_offline_zip,
    compliance_badge_svg,
)
from behavior import (
    compare_baselines,
    create_baseline,
    detect_drift,
    review_drift_mark,
    soft_delete,
)

BRAND = "ai-attestation"
VERSION = "0.1.0-mvp"
DEFAULT_DEMO_KEY = os.environ.get("ATA_DEMO_API_KEY", "ata_demo_" + "localdev0001")

_CORS = [
    o.strip()
    for o in os.environ.get(
        "ATA_CORS_ORIGINS",
        # Explicit dashboard origins + wildcard for MVP remote testing.
        "*,http://47.119.118.245:3002,http://localhost:3002,http://127.0.0.1:3002",
    ).split(",")
    if o.strip()
]
_ALLOW_ALL = "*" in _CORS
_CORS_ORIGINS: list[str] = (
    [o for o in _CORS if o != "*"]
    if _ALLOW_ALL
    else _CORS
)
# Always keep common local + deploy origins even when env is a custom list.
for _o in (
    "http://47.119.118.245:3002",
    "http://localhost:3002",
    "http://127.0.0.1:3002",
    "http://localhost:3000",
    "http://127.0.0.1:3000",
):
    if _o not in _CORS_ORIGINS:
        _CORS_ORIGINS.append(_o)

DB_PATH = init_db()
ensure_api_key(DEFAULT_DEMO_KEY, label="demo", name="demo", role="admin")
# Ensure demo is admin even if already existed
update_api_key(DEFAULT_DEMO_KEY, role="admin", status="active", name="demo", db_path=DB_PATH)
start_report_scheduler(db_path=DB_PATH)

app = FastAPI(title=BRAND, version=VERSION)
# CORS is built into FastAPI/Starlette — no separate fastapi-cors package needed.
# When ATA_CORS_ORIGINS includes "*", also match any http(s) Origin via regex so
# Access-Control-Allow-Origin echoes the request Origin (works with credentials).
app.add_middleware(
    CORSMiddleware,
    allow_origins=_CORS_ORIGINS,
    allow_origin_regex=r"https?://.*" if _ALLOW_ALL else None,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)


@app.middleware("http")
async def log_requests(request: Request, call_next):
    print(f"[INFO] 收到请求: {request.method} {request.url.path}")
    return await call_next(request)


def _public_api_base(request: Request) -> str:
    """Prefer ATA_PUBLIC_BASE; else reconstruct from the incoming Host."""
    explicit = os.environ.get("ATA_PUBLIC_BASE", "").strip().rstrip("/")
    if explicit:
        return explicit
    host = (
        request.headers.get("x-forwarded-host")
        or request.headers.get("host")
        or "127.0.0.1:8004"
    )
    proto = request.headers.get("x-forwarded-proto") or request.url.scheme or "http"
    return f"{proto}://{host}".rstrip("/")


class IssueKeyBody(BaseModel):
    label: str = Field(default="trial", max_length=80)


@app.get("/health")
def health(request: Request) -> Dict[str, Any]:
    base = _public_api_base(request)
    out: Dict[str, Any] = {
        "ok": True,
        "product": BRAND,
        "version": VERSION,
        "status": "mvp",
        "db": str(DB_PATH),
        "proxy_base": f"{base}/v1/proxy",
    }
    # Do not leak demo credentials by default
    if os.environ.get("ATA_EXPOSE_DEMO_KEY", "").strip().lower() in ("1", "true", "yes"):
        out["demo_api_key"] = DEFAULT_DEMO_KEY
    return out


@app.post("/v1/keys")
def issue_key(body: IssueKeyBody, request: Request) -> Dict[str, Any]:
    """Issue a free trial attestation key (no Stripe / no login)."""
    rec = create_api_key_record(name=body.label or "trial", role="read_write", db_path=DB_PATH)
    base = _public_api_base(request)
    proxy = f"{base}/v1/proxy"
    return {
        "api_key": rec["api_key"],
        "label": body.label,
        "name": rec["name"],
        "role": rec["role"],
        "proxy_url": proxy,
        "usage_hint": (
            f"Set SDK base_url to {proxy} "
            "and header X-Attest-Key: <api_key>. Keep Authorization as upstream key."
        ),
    }


# ── Settings: report subscriptions ──────────────────────────────────────────


class ReportSubBody(BaseModel):
    api_key: str = Field(..., min_length=8)
    email: str = Field(..., min_length=3, max_length=500)
    frequency: str = Field(default="weekly", pattern="^(daily|weekly|monthly)$")
    content_options: Dict[str, bool] = Field(
        default_factory=lambda: {
            "api_overview": True,
            "drift_summary": True,
            "compliance_summary": True,
        }
    )


@app.get("/v1/dashboard/settings/report-subscription")
def get_report_sub(api_key: str = Query(..., min_length=8)) -> Dict[str, Any]:
    require_key(api_key, min_role="read_only", db_path=DB_PATH)
    sub = get_report_subscription_for_key(api_key, db_path=DB_PATH)
    hist = list_report_history_for_key(api_key, limit=10, db_path=DB_PATH)
    return {"subscription": sub, "history": hist}


@app.put("/v1/dashboard/settings/report-subscription")
def put_report_sub(body: ReportSubBody) -> Dict[str, Any]:
    require_key(body.api_key, min_role="read_write", db_path=DB_PATH)
    import uuid
    from datetime import datetime, timezone

    existing = get_report_subscription_for_key(body.api_key, db_path=DB_PATH)
    sub_id = existing["id"] if existing else f"rsub_{uuid.uuid4().hex[:16]}"
    created = (
        existing["created_at"]
        if existing
        else datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    )
    upsert_report_subscription(
        {
            "id": sub_id,
            "api_key": body.api_key,
            "email": body.email.strip(),
            "frequency": body.frequency,
            "content_options": body.content_options,
            "last_sent_at": existing.get("last_sent_at") if existing else None,
            "created_at": created,
        },
        db_path=DB_PATH,
    )
    sub = get_report_subscription_for_key(body.api_key, db_path=DB_PATH)
    return {"ok": True, "subscription": sub}


class ReportTestBody(BaseModel):
    api_key: str = Field(..., min_length=8)


@app.post("/v1/dashboard/settings/report-subscription/test")
def test_report_sub(body: ReportTestBody) -> Dict[str, Any]:
    require_key(body.api_key, min_role="read_write", db_path=DB_PATH)
    sub = get_report_subscription_for_key(body.api_key, db_path=DB_PATH)
    if not sub:
        raise HTTPException(400, "save subscription first")
    send_subscription_async(subscription_id=sub["id"], db_path=DB_PATH, test=True)
    return {"ok": True, "queued": True, "message": "测试报告已排队发送（无 SMTP 时写入 reports/）"}


# ── Settings: API key management ─────────────────────────────────────────────


class CreateManagedKeyBody(BaseModel):
    api_key: str = Field(..., min_length=8)  # caller key (must be admin)
    name: str = Field(..., min_length=1, max_length=80)
    role: str = Field(default="read_write", pattern="^(read_only|read_write|admin)$")


class PatchManagedKeyBody(BaseModel):
    api_key: str = Field(..., min_length=8)
    target_key: str = Field(..., min_length=8)
    name: Optional[str] = None
    role: Optional[str] = Field(default=None, pattern="^(read_only|read_write|admin)$")
    status: Optional[str] = Field(default=None, pattern="^(active|disabled|deleted)$")


@app.get("/v1/dashboard/settings/keys")
def list_managed_keys(api_key: str = Query(..., min_length=8)) -> Dict[str, Any]:
    me = require_key(api_key, min_role="admin", db_path=DB_PATH)
    rows = list_api_keys(include_deleted=False, db_path=DB_PATH)
    lean = []
    for r in rows:
        lean.append(
            {
                "api_key_masked": mask_key(r["api_key"]),
                "api_key_full": r["api_key"],  # admin UI may reveal on click
                "name": r.get("name") or r.get("label"),
                "role": r.get("role") or "read_write",
                "status": r.get("status") or "active",
                "created_at": r.get("created_at"),
                "last_used_at": r.get("last_used_at"),
                "is_self": r["api_key"] == api_key,
            }
        )
    return {"me": me, "keys": lean}


@app.post("/v1/dashboard/settings/keys")
def create_managed_key(body: CreateManagedKeyBody) -> Dict[str, Any]:
    require_key(body.api_key, min_role="admin", db_path=DB_PATH)
    rec = create_api_key_record(name=body.name, role=body.role, db_path=DB_PATH)
    return {"ok": True, "key": {**rec, "api_key_masked": mask_key(rec["api_key"])}}


@app.patch("/v1/dashboard/settings/keys")
def patch_managed_key(body: PatchManagedKeyBody) -> Dict[str, Any]:
    require_key(body.api_key, min_role="admin", db_path=DB_PATH)
    if body.target_key == body.api_key and body.status in ("disabled", "deleted"):
        raise HTTPException(400, "cannot disable/delete the key you are currently using")
    row = update_api_key(
        body.target_key,
        name=body.name,
        role=body.role,
        status=body.status,
        db_path=DB_PATH,
    )
    if not row:
        raise HTTPException(404, "key not found")
    return {
        "ok": True,
        "key": {
            "api_key_masked": mask_key(row["api_key"]),
            "name": row.get("name"),
            "role": row.get("role"),
            "status": row.get("status"),
        },
    }


@app.get("/v1/dashboard/me")
def dashboard_me(api_key: str = Query(..., min_length=8)) -> Dict[str, Any]:
    me = require_key(api_key, min_role="read_only", db_path=DB_PATH)
    return {"me": me}


# ── Export ───────────────────────────────────────────────────────────────────


@app.get("/v1/dashboard/calls/export")
def export_calls(
    api_key: str = Query(..., min_length=8),
    format: str = Query("csv", pattern="^(csv|json)$"),
    time_range: str = Query("7d"),
    custom_from: Optional[str] = None,
    custom_to: Optional[str] = None,
    vendor: Optional[str] = None,
    status: Optional[str] = None,
):
    require_key(api_key, min_role="read_only", db_path=DB_PATH)
    rows = list(
        iter_export_rows(
            api_key,
            time_range=time_range,
            custom_from=custom_from,
            custom_to=custom_to,
            vendor=vendor or None,
            status=status or None,
            db_path=DB_PATH,
        )
    )
    if format == "json":
        data = rows_to_json(rows)
        return Response(
            content=data,
            media_type="application/json",
            headers={
                "Content-Disposition": 'attachment; filename="ata_calls_export.json"'
            },
        )
    data = rows_to_csv(rows)
    return Response(
        content=data,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="ata_calls_export.csv"'},
    )


@app.api_route("/v1/proxy/{path:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE"])
async def proxy_path(path: str, request: Request):
    resp, _ = await forward_openai(request, path, db_path=DB_PATH)
    return resp


@app.get("/v1/dashboard/calls")
def dashboard_calls(
    api_key: str = Query(..., min_length=8),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
) -> Dict[str, Any]:
    require_key(api_key, min_role="read_only", db_path=DB_PATH)
    total = count_calls(api_key, db_path=DB_PATH)
    calls = list_calls(api_key, limit=limit, offset=offset, db_path=DB_PATH)
    return {
        "api_key_suffix": api_key[-6:],
        "n": len(calls),
        "total": total,
        "limit": limit,
        "offset": offset,
        "has_more": offset + len(calls) < total,
        "calls": calls,
    }


@app.get("/v1/dashboard/overview")
def dashboard_overview_api(api_key: str = Query(..., min_length=8)) -> Dict[str, Any]:
    require_key(api_key, min_role="read_only", db_path=DB_PATH)
    return dashboard_overview(api_key, db_path=DB_PATH)


@app.get("/v1/dashboard/calls/{call_id}")
def dashboard_call_detail(call_id: str, api_key: str = Query(..., min_length=8)) -> Dict[str, Any]:
    require_key(api_key, min_role="read_only", db_path=DB_PATH)
    row = get_call(call_id, db_path=DB_PATH)
    if not row or row.get("api_key") != api_key:
        raise HTTPException(404, "call not found")
    return {"call": row, "proof": verify_single_call(row)}


@app.get("/v1/reports/{report_id}/export")
def export_call_verify_pack(
    report_id: str, api_key: str = Depends(resolve_api_key)
) -> Response:
    """Offline ZIP for one API call (report_id == call.id).

    Contains call.json + chain.json + verification.json + verify.html + README.txt.
    Raw request/response bodies are never included (hashes only).
    """
    require_key(api_key, min_role="read_only", db_path=DB_PATH)
    row = get_call(report_id, db_path=DB_PATH)
    if not row or row.get("api_key") != api_key:
        raise HTTPException(404, "call not found")
    verification = verify_single_call(row)
    zbytes = build_call_offline_zip(
        call=row,
        verification=verification,
        api_key=api_key,
        db_path=DB_PATH,
    )
    safe_id = "".join(c if c.isalnum() or c in "-_" else "_" for c in report_id)[:64]
    return Response(
        content=zbytes,
        media_type="application/zip",
        headers={
            "Content-Disposition": f'attachment; filename="ata_call_{safe_id}_verify.zip"'
        },
    )


class SimulateBody(BaseModel):
    api_key: str = Field(..., min_length=8)
    endpoint: str = "/v1/chat/completions"
    model: str = "gpt-4o-mini"
    vendor: str = "openai"
    prompt_tokens: int = Field(default=120, ge=0)
    completion_tokens: int = Field(default=80, ge=0)
    status_code: int = 200


@app.post("/v1/demo/simulate")
def simulate_call(body: SimulateBody) -> Dict[str, Any]:
    """Record a synthetic attested call without hitting OpenAI (local demo)."""
    from write_buffer import build_next_record, flush_now

    require_key(body.api_key, min_role="read_write", db_path=DB_PATH)
    flush_now()
    cost = estimate_cost_usd(
        model=body.model,
        prompt_tokens=body.prompt_tokens,
        completion_tokens=body.completion_tokens,
    )
    # Bodies hashed only — never persisted
    req = (
        f'{{"model":"{body.model}","messages":[{{"role":"user","content":"[redacted]"}}]}}'
    ).encode()
    res = (
        f'{{"model":"{body.model}","usage":{{"prompt_tokens":{body.prompt_tokens},'
        f'"completion_tokens":{body.completion_tokens}}}}}'
    ).encode()

    def _build(prev: str):
        return build_call_record(
            api_key=body.api_key,
            prev_hash=prev,
            endpoint=body.endpoint,
            method="POST",
            model=body.model,
            status_code=body.status_code,
            request_body=req,
            response_body=res,
            duration_ms=12.5,
            prompt_tokens=body.prompt_tokens,
            completion_tokens=body.completion_tokens,
            cost_usd=cost,
            vendor=body.vendor or "openai",
        )

    record = build_next_record(body.api_key, _build, db_path=DB_PATH)
    insert_call(record, db_path=DB_PATH)
    return {"ok": True, "call": record, "proof": verify_single_call(record)}


class QueryBody(BaseModel):
    api_key: str = Field(..., min_length=8)
    time_range: str = Field(default="7d", max_length=32)
    custom_from: Optional[str] = None
    custom_to: Optional[str] = None
    endpoint: Optional[str] = Field(default=None, max_length=200)
    min_cost: Optional[float] = None
    max_cost: Optional[float] = None
    status: Optional[str] = Field(default=None, max_length=32)
    model: Optional[str] = Field(default=None, max_length=120)
    vendor: Optional[str] = Field(default=None, max_length=40)
    limit: int = Field(default=100, ge=1, le=500)


@app.post("/v1/dashboard/query")
def dashboard_query(body: QueryBody) -> Dict[str, Any]:
    """Query-as-audit: filter calls and append a tamper-evident query link."""
    require_key(body.api_key, min_role="read_write", db_path=DB_PATH)
    return execute_attested_query(
        api_key=body.api_key,
        raw_params=body.model_dump(),
        db_path=DB_PATH,
    )


@app.get("/v1/dashboard/query-history")
def dashboard_query_history(
    api_key: str = Query(..., min_length=8),
    limit: int = Query(20, ge=1, le=50),
) -> Dict[str, Any]:
    require_key(api_key, min_role="read_only", db_path=DB_PATH)
    rows = list_queries(api_key, limit=limit, db_path=DB_PATH)
    lean = [
        {
            "id": r["id"],
            "timestamp": r["timestamp"],
            "query_params": r.get("query_params"),
            "result_count": r.get("result_count"),
            "query_hash": r.get("query_hash"),
            "chain_hash": r.get("chain_hash"),
            "duration_ms": r.get("duration_ms"),
        }
        for r in rows
    ]
    return {"api_key_suffix": api_key[-6:], "n": len(lean), "queries": lean}


@app.get("/v1/dashboard/query/{query_id}")
def dashboard_query_detail(
    query_id: str, api_key: str = Query(..., min_length=8)
) -> Dict[str, Any]:
    require_key(api_key, min_role="read_only", db_path=DB_PATH)
    row = get_query(query_id, db_path=DB_PATH)
    if not row or row.get("api_key") != api_key:
        raise HTTPException(404, "query not found")
    result_ids = row.get("result_ids") or []
    results = []
    for cid in result_ids:
        c = get_call(str(cid), db_path=DB_PATH)
        if c and c.get("api_key") == api_key:
            results.append(
                {
                    "id": c["id"],
                    "timestamp": c["timestamp"],
                    "endpoint": c["endpoint"],
                    "model": c.get("model"),
                    "status_code": c.get("status_code"),
                    "cost_usd": c.get("cost_usd"),
                    "duration_ms": c.get("duration_ms"),
                }
            )
    return {
        "query": row,
        "results": results,
        "count": len(results),
        "proof": verify_single_query(row),
    }


@app.get("/v1/dashboard/attestation")
def dashboard_attestation(api_key: str = Query(..., min_length=8)) -> Dict[str, Any]:
    require_key(api_key, min_role="read_only", db_path=DB_PATH)
    proof = verify_key_chain(api_key, db_path=DB_PATH)
    chain = list_chain(api_key, limit=12, db_path=DB_PATH)
    calls = list_calls(api_key, limit=500, db_path=DB_PATH)
    latest = proof.get("latest_hash") or GENESIS
    return {
        "api_key_suffix": api_key[-6:],
        "chain_length": proof.get("chain_length", 0),
        "latest_hash": latest,
        "integrity_ok": bool(proof.get("ok")),
        "message": proof.get("message"),
        "broken_at": proof.get("broken_at"),
        "genesis": GENESIS,
        "links_preview": chain,
        "total_cost_usd": round(sum(float(c.get("cost_usd") or 0) for c in calls), 6),
        "n_calls": proof.get("n_calls", 0),
        "n_queries": proof.get("n_queries", 0),
        "n_compliance": proof.get("n_compliance", 0),
        "n_baselines": proof.get("n_baselines", 0),
        "n_drift_marks": proof.get("n_drift_marks", 0),
        "blockchain_anchor": latest_anchor(api_key, db_path=DB_PATH),
    }


@app.post("/v1/dashboard/calls/{call_id}/verify")
def verify_one(call_id: str, api_key: str = Query(..., min_length=8)) -> Dict[str, Any]:
    require_key(api_key, min_role="read_only", db_path=DB_PATH)
    row = get_call(call_id, db_path=DB_PATH)
    if not row or row.get("api_key") != api_key:
        raise HTTPException(404, "call not found")
    proof = verify_key_chain(api_key, db_path=DB_PATH)
    return {"call_id": call_id, "chain_proof": proof, "call": row}


class ComplianceCheckBody(BaseModel):
    api_key: str = Field(..., min_length=8)
    standard: Optional[str] = Field(default=None, max_length=80)
    standards: Optional[List[str]] = None


@app.get("/v1/dashboard/compliance/standards")
def compliance_standards(
    api_key: Optional[str] = Query(None, min_length=8),
) -> Dict[str, Any]:
    if api_key:
        require_key(api_key, min_role="read_only", db_path=DB_PATH)
    rows = list_standards(api_key=api_key)
    notices = template_update_notices(api_key=api_key)
    return {
        "n": len(rows),
        "standards": rows,
        "template_updates": notices,
        "templates_root_hint": "compliance-templates/",
    }


@app.post("/v1/dashboard/compliance/check")
def compliance_run(body: ComplianceCheckBody) -> Dict[str, Any]:
    require_key(body.api_key, min_role="read_write", db_path=DB_PATH)
    try:
        return execute_compliance_check(
            api_key=body.api_key,
            standard=body.standard,
            standards=body.standards,
            db_path=DB_PATH,
        )
    except ValueError as e:
        raise HTTPException(400, str(e)) from e


@app.get("/v1/dashboard/compliance/standards/compare")
def compliance_standards_compare(
    ids: str = Query(..., description="comma-separated standard ids"),
) -> Dict[str, Any]:
    parts = [p.strip() for p in ids.split(",") if p.strip()]
    if len(parts) < 2:
        raise HTTPException(400, "need at least 2 standard ids")
    try:
        return compare_standards(parts)
    except ValueError as e:
        raise HTTPException(400, str(e)) from e


class GapBody(BaseModel):
    api_key: str = Field(..., min_length=8)
    standards: List[str] = Field(..., min_length=1)


@app.post("/v1/dashboard/compliance/gap-analysis")
def compliance_gap(body: GapBody) -> Dict[str, Any]:
    require_key(body.api_key, min_role="read_write", db_path=DB_PATH)
    try:
        return gap_analysis(
            api_key=body.api_key, standards=body.standards, db_path=DB_PATH
        )
    except ValueError as e:
        raise HTTPException(400, str(e)) from e


@app.get("/v1/dashboard/compliance/history")
def compliance_history(
    api_key: str = Query(..., min_length=8),
    limit: int = Query(50, ge=1, le=100),
) -> Dict[str, Any]:
    require_key(api_key, min_role="read_only", db_path=DB_PATH)
    rows = list_compliance(api_key, limit=limit, db_path=DB_PATH)
    lean = [
        {
            "id": r["id"],
            "timestamp": r["timestamp"],
            "standard": r.get("standard"),
            "standard_name": r.get("standard_name"),
            "summary": r.get("summary"),
            "report_hash": r.get("report_hash"),
            "chain_hash": r.get("chain_hash"),
            "duration_ms": r.get("duration_ms"),
            "template_version": (r.get("summary") or {}).get("template_version"),
        }
        for r in rows
    ]
    return {"api_key_suffix": api_key[-6:], "n": len(lean), "checks": lean}


@app.get("/v1/dashboard/compliance/report/{check_id}")
def compliance_report(
    check_id: str, api_key: str = Query(..., min_length=8)
) -> Dict[str, Any]:
    require_key(api_key, min_role="read_only", db_path=DB_PATH)
    row = get_compliance(check_id, db_path=DB_PATH)
    if not row or row.get("api_key") != api_key:
        raise HTTPException(404, "compliance check not found")
    report = dict(row)
    # Attach fresh independent timestamp over report_hash
    report = attach_timestamp_to_report(report)
    anchor = latest_anchor(api_key, db_path=DB_PATH)
    tee = tee_attestation_stub(
        module="compliance_report",
        payload_hash=str(report.get("report_hash") or ""),
    )
    if tee:
        report["tee_attestation"] = tee
    pack = build_verify_pack(
        report,
        timestamp_proof=report.get("timestamp_proof"),
        blockchain_anchor=anchor,
        tee_attestation=tee,
    )
    token = encode_pack(pack)
    return {
        "report": report,
        "proof": verify_single_compliance(row),
        "timestamp_proof": report.get("timestamp_proof"),
        "timestamp_verify": report.get("timestamp_verify"),
        "blockchain_anchor": anchor,
        "tee_attestation": tee,
        "verify_pack_token": token,
        "verify_pack_hash": pack_integrity_token(pack),
        "text": report_to_text(report),
    }


class AnchorBody(BaseModel):
    api_key: str = Field(..., min_length=8)
    force_mock: bool = True


@app.post("/v1/dashboard/attestation/anchor")
def attestation_anchor(body: AnchorBody) -> Dict[str, Any]:
    require_key(body.api_key, min_role="read_write", db_path=DB_PATH)
    return anchor_chain_head(
        api_key=body.api_key, db_path=DB_PATH, force_mock=body.force_mock
    )


@app.get("/v1/dashboard/attestation/anchors")
def attestation_anchors(
    api_key: str = Query(..., min_length=8),
    limit: int = Query(20, ge=1, le=100),
) -> Dict[str, Any]:
    require_key(api_key, min_role="read_only", db_path=DB_PATH)
    rows = list_anchors(api_key, limit=limit, db_path=DB_PATH)
    return {"n": len(rows), "anchors": rows, "latest": rows[0] if rows else None}


@app.post("/v1/dashboard/timestamp")
def timestamp_stamp(body: Dict[str, Any]) -> Dict[str, Any]:
    """Stamp an arbitrary payload hash (demo / external use)."""
    ph = str(body.get("payload_hash") or "")
    if len(ph) < 16:
        raise HTTPException(400, "payload_hash required")
    receipt = stamp_hash(ph)
    return {"receipt": receipt, "verify": verify_tsa_receipt(receipt)}


@app.get("/v1/dashboard/compliance/report/{check_id}/export")
def compliance_export(
    check_id: str,
    api_key: str = Depends(resolve_api_key),
    format: str = Query("json", pattern="^(json|pdf|txt|oscal)$"),
) -> Response:
    require_key(api_key, min_role="read_only", db_path=DB_PATH)
    row = get_compliance(check_id, db_path=DB_PATH)
    if not row or row.get("api_key") != api_key:
        raise HTTPException(404, "compliance check not found")
    import json as _json

    report = attach_timestamp_to_report(dict(row))
    anchor = latest_anchor(api_key, db_path=DB_PATH)
    tee = tee_attestation_stub(
        module="compliance_export",
        payload_hash=str(report.get("report_hash") or ""),
    )
    pack = build_verify_pack(
        report,
        timestamp_proof=report.get("timestamp_proof"),
        blockchain_anchor=anchor,
        tee_attestation=tee,
    )
    if format == "json":
        export_body = {
            **report,
            "blockchain_anchor": anchor,
            "tee_attestation": tee,
            "verify_pack": pack,
        }
        body = _json.dumps(export_body, ensure_ascii=False, indent=2).encode("utf-8")
        return Response(
            content=body,
            media_type="application/json",
            headers={
                "Content-Disposition": f'attachment; filename="{check_id}.json"'
            },
        )
    if format == "oscal":
        oscal = report_to_oscal(report, pack=pack)
        body = _json.dumps(oscal, ensure_ascii=False, indent=2).encode("utf-8")
        return Response(
            content=body,
            media_type="application/json",
            headers={
                "Content-Disposition": f'attachment; filename="{check_id}.oscal.json"'
            },
        )
    text = report_to_text(report)
    if format == "txt":
        return Response(
            content=text.encode("utf-8"),
            media_type="text/plain; charset=utf-8",
            headers={"Content-Disposition": f'attachment; filename="{check_id}.txt"'},
        )
    pdf = report_to_simple_pdf(text)
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{check_id}.pdf"'},
    )


@app.get("/v1/dashboard/compliance/report/{check_id}/verify-pack")
def compliance_verify_pack(
    check_id: str, api_key: str = Query(..., min_length=8)
) -> Dict[str, Any]:
    """Build a self-contained pack for /verify/{report_hash}?p=…"""
    require_key(api_key, min_role="read_only", db_path=DB_PATH)
    row = get_compliance(check_id, db_path=DB_PATH)
    if not row or row.get("api_key") != api_key:
        raise HTTPException(404, "compliance check not found")
    report = attach_timestamp_to_report(dict(row))
    anchor = latest_anchor(api_key, db_path=DB_PATH)
    tee = tee_attestation_stub(
        module="verify_pack",
        payload_hash=str(report.get("report_hash") or ""),
    )
    pack = build_verify_pack(
        report,
        timestamp_proof=report.get("timestamp_proof"),
        blockchain_anchor=anchor,
        tee_attestation=tee,
    )
    token = encode_pack(pack)
    rh = str(report.get("report_hash") or "")
    return {
        "report_hash": rh,
        "pack_hash": pack_integrity_token(pack),
        "token": token,
        "verify_path": f"/verify/{rh}?p={token}",
        "verification": verify_pack(pack),
        "disclaimer": pack["disclaimer"],
    }


@app.get("/v1/dashboard/compliance/report/{check_id}/checks/{item_id}/evidence")
def compliance_check_evidence(
    check_id: str,
    item_id: str,
    api_key: str = Depends(resolve_api_key),
    format: str = Query("json", pattern="^(json|pdf)$"),
) -> Response:
    """Deep drill: evidence for one checklist item."""
    require_key(api_key, min_role="read_only", db_path=DB_PATH)
    row = get_compliance(check_id, db_path=DB_PATH)
    if not row or row.get("api_key") != api_key:
        raise HTTPException(404, "compliance check not found")
    try:
        detail = check_evidence_detail(row, item_id)
    except ValueError as e:
        raise HTTPException(404, str(e)) from e
    import json as _json

    if format == "json":
        body = _json.dumps(detail, ensure_ascii=False, indent=2).encode("utf-8")
        return Response(
            content=body,
            media_type="application/json",
            headers={
                "Content-Disposition": f'attachment; filename="{check_id}_{item_id}_evidence.json"'
            },
        )
    text = report_to_text(
        {
            **detail,
            "standard_name": f"Evidence · {detail.get('check_id')}",
            "id": check_id,
            "check_results": {item_id: detail},
            "summary": {"n_total": 1},
            "report_hash": row.get("report_hash"),
            "chain_hash": row.get("chain_hash"),
            "prev_hash": row.get("prev_hash"),
            "timestamp": row.get("timestamp"),
        }
    )
    pdf = report_to_simple_pdf(text)
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{check_id}_{item_id}_evidence.pdf"'
        },
    )


@app.get("/v1/dashboard/compliance/report/{check_id}/offline-pack")
def compliance_offline_pack(
    check_id: str, api_key: str = Depends(resolve_api_key)
) -> Response:
    """ZIP: report.json + chain.json + pack.json + verify.html (server-independent)."""
    require_key(api_key, min_role="read_only", db_path=DB_PATH)
    row = get_compliance(check_id, db_path=DB_PATH)
    if not row or row.get("api_key") != api_key:
        raise HTTPException(404, "compliance check not found")
    report = attach_timestamp_to_report(dict(row))
    anchor = latest_anchor(api_key, db_path=DB_PATH)
    tee = tee_attestation_stub(
        module="offline_pack",
        payload_hash=str(report.get("report_hash") or ""),
    )
    pack = build_verify_pack(
        report,
        timestamp_proof=report.get("timestamp_proof"),
        blockchain_anchor=anchor,
        tee_attestation=tee,
    )
    path = build_chain_path(api_key=api_key, report=report, db_path=DB_PATH)
    zbytes = build_offline_zip(
        report=report,
        pack=pack,
        chain_path=path,
        verification=verify_pack(pack),
    )
    return Response(
        content=zbytes,
        media_type="application/zip",
        headers={
            "Content-Disposition": f'attachment; filename="{check_id}_offline_verify.zip"'
        },
    )


@app.get("/v1/dashboard/compliance/report/{check_id}/chain-path")
def compliance_chain_path(
    check_id: str, api_key: str = Query(..., min_length=8)
) -> Dict[str, Any]:
    require_key(api_key, min_role="read_only", db_path=DB_PATH)
    row = get_compliance(check_id, db_path=DB_PATH)
    if not row or row.get("api_key") != api_key:
        raise HTTPException(404, "compliance check not found")
    return build_chain_path(api_key=api_key, report=row, db_path=DB_PATH)


@app.get("/v1/public/offline-pack")
def public_offline_pack(p: str = Query(..., min_length=16)) -> Response:
    """Download offline ZIP from a share token (no api_key)."""
    try:
        pack = decode_pack(p)
    except Exception as e:
        raise HTTPException(400, f"invalid pack: {e}") from e
    report = pack.get("report") or {}
    # Minimal chain from pack hashes
    chain_path = {
        "nodes": [
            {
                "id": "prev",
                "timestamp": None,
                "event_type": "prev",
                "hash": report.get("prev_hash"),
                "ok": True,
            },
            {
                "id": report.get("id"),
                "timestamp": report.get("timestamp"),
                "event_type": "compliance",
                "hash": report.get("chain_hash"),
                "prev_hash": report.get("prev_hash"),
                "ok": True,
                "highlight": True,
                "label": "合规报告",
            },
        ],
        "n_nodes": 2,
        "broken": [],
    }
    zbytes = build_offline_zip(
        report=report,
        pack=pack,
        chain_path=chain_path,
        verification=verify_pack(pack),
    )
    rh = str(report.get("report_hash") or "pack")[:16]
    return Response(
        content=zbytes,
        media_type="application/zip",
        headers={
            "Content-Disposition": f'attachment; filename="ata_offline_{rh}.zip"'
        },
    )


@app.get("/v1/public/badge/{report_hash}.svg")
def public_compliance_badge(
    report_hash: str,
    status: str = Query("unknown"),
    label: str = Query("AI审计合规"),
) -> Response:
    svg = compliance_badge_svg(status=status, label=label, report_hash=report_hash)
    return Response(
        content=svg.encode("utf-8"),
        media_type="image/svg+xml",
        headers={"Cache-Control": "public, max-age=60"},
    )


class NotarizeBody(BaseModel):
    report_hash: str = Field(..., min_length=16)
    method: str = Field(default="opentimestamps", max_length=40)


@app.post("/v1/public/notarize")
def public_notarize(body: NotarizeBody) -> Dict[str, Any]:
    try:
        return build_notarization_request(
            report_hash=body.report_hash, method=body.method
        )
    except ValueError as e:
        raise HTTPException(400, str(e)) from e


# --- Custom compliance templates (private + publish draft) ---


class CustomTemplateBody(BaseModel):
    api_key: str = Field(..., min_length=8)
    template: Dict[str, Any]


class CustomYamlBody(BaseModel):
    api_key: str = Field(..., min_length=8)
    yaml_text: str = Field(..., min_length=8)


class HelperBody(BaseModel):
    goal: str = Field(..., min_length=4, max_length=500)


class PinBody(BaseModel):
    api_key: str = Field(..., min_length=8)
    template_id: str
    version: Optional[str] = None


@app.get("/v1/dashboard/compliance/templates/custom")
def custom_templates_list(api_key: str = Query(..., min_length=8)) -> Dict[str, Any]:
    require_key(api_key, min_role="read_only", db_path=DB_PATH)
    rows = list_custom_templates(api_key)
    return {"n": len(rows), "templates": rows}


@app.get("/v1/dashboard/compliance/templates/custom/{template_id}")
def custom_templates_get(
    template_id: str, api_key: str = Query(..., min_length=8)
) -> Dict[str, Any]:
    require_key(api_key, min_role="read_only", db_path=DB_PATH)
    doc = get_custom_template(api_key, template_id)
    if not doc:
        raise HTTPException(404, "template not found")
    return {"template": doc, "yaml": export_custom_yaml(api_key, template_id)}


@app.post("/v1/dashboard/compliance/templates/custom")
def custom_templates_save(body: CustomTemplateBody) -> Dict[str, Any]:
    require_key(body.api_key, min_role="read_write", db_path=DB_PATH)
    try:
        saved = save_custom_template(body.api_key, body.template)
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    return {"ok": True, "template": saved}


@app.post("/v1/dashboard/compliance/templates/custom/import")
def custom_templates_import(body: CustomYamlBody) -> Dict[str, Any]:
    require_key(body.api_key, min_role="read_write", db_path=DB_PATH)
    try:
        saved = import_custom_yaml(body.api_key, body.yaml_text)
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    return {"ok": True, "template": saved}


@app.delete("/v1/dashboard/compliance/templates/custom/{template_id}")
def custom_templates_delete(
    template_id: str, api_key: str = Query(..., min_length=8)
) -> Dict[str, Any]:
    require_key(api_key, min_role="read_write", db_path=DB_PATH)
    ok = delete_custom_template(api_key, template_id)
    if not ok:
        raise HTTPException(404, "template not found")
    return {"ok": True}


@app.post("/v1/dashboard/compliance/templates/custom/{template_id}/publish")
def custom_templates_publish(
    template_id: str, api_key: str = Query(..., min_length=8)
) -> Dict[str, Any]:
    require_key(api_key, min_role="read_write", db_path=DB_PATH)
    try:
        return publish_draft(api_key, template_id)
    except ValueError as e:
        raise HTTPException(404, str(e)) from e


@app.post("/v1/dashboard/compliance/templates/helper")
def custom_templates_helper(body: HelperBody) -> Dict[str, Any]:
    return check_method_helper(body.goal)


@app.post("/v1/dashboard/compliance/templates/pin")
def custom_templates_pin(body: PinBody) -> Dict[str, Any]:
    require_key(body.api_key, min_role="read_write", db_path=DB_PATH)
    return pin_template_version(body.api_key, body.template_id, body.version)


@app.get("/v1/dashboard/compliance/templates/updates")
def compliance_template_updates(
    api_key: str = Query(..., min_length=8),
) -> Dict[str, Any]:
    require_key(api_key, min_role="read_only", db_path=DB_PATH)
    notices = template_update_notices(api_key=api_key)
    return {"n": len(notices), "updates": notices}


class VerifyPackBody(BaseModel):
    token: Optional[str] = None
    pack: Optional[Dict[str, Any]] = None


@app.post("/v1/public/verify")
def public_verify(body: VerifyPackBody) -> Dict[str, Any]:
    """Offline-capable verification: no api_key, no DB reads of tenant data."""
    try:
        if body.pack:
            pack = body.pack
        elif body.token:
            pack = decode_pack(body.token)
        else:
            raise HTTPException(400, "token or pack required")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(400, f"invalid pack: {e}") from e
    return {"pack": pack, "verification": verify_pack(pack)}


@app.get("/v1/public/verify")
def public_verify_get(p: str = Query(..., min_length=16)) -> Dict[str, Any]:
    try:
        pack = decode_pack(p)
    except Exception as e:
        raise HTTPException(400, f"invalid pack: {e}") from e
    return {"pack": pack, "verification": verify_pack(pack)}


@app.get("/v1/dashboard/compliance/compare")
def compliance_compare(
    api_key: str = Query(..., min_length=8),
    older_id: str = Query(...),
    newer_id: str = Query(...),
) -> Dict[str, Any]:
    require_key(api_key, min_role="read_only", db_path=DB_PATH)
    older = get_compliance(older_id, db_path=DB_PATH)
    newer = get_compliance(newer_id, db_path=DB_PATH)
    if not older or older.get("api_key") != api_key:
        raise HTTPException(404, "older check not found")
    if not newer or newer.get("api_key") != api_key:
        raise HTTPException(404, "newer check not found")
    return compare_compliance(older, newer)


class ImpactAnalysisBody(BaseModel):
    api_key: str = Field(..., min_length=8)
    older_check_id: Optional[str] = Field(default=None, max_length=80)
    newer_check_id: Optional[str] = Field(default=None, max_length=80)
    new_standard: Optional[str] = Field(default=None, max_length=80)
    template_yaml: Optional[Any] = None
    proxy_config: Optional[Any] = None
    change_summary: Optional[str] = Field(default=None, max_length=2000)


@app.post("/v1/dashboard/compliance/impact-analysis")
def compliance_impact_analysis(body: ImpactAnalysisBody) -> Dict[str, Any]:
    require_key(body.api_key, min_role="read_write", db_path=DB_PATH)
    try:
        return impact_analysis_from_change(
            body.api_key,
            {
                "older_check_id": body.older_check_id,
                "newer_check_id": body.newer_check_id,
                "new_standard": body.new_standard,
                "template_yaml": body.template_yaml,
                "proxy_config": body.proxy_config,
                "change_summary": body.change_summary,
            },
            db_path=DB_PATH,
        )
    except ValueError as e:
        raise HTTPException(400, str(e)) from e


class RuleTestBody(BaseModel):
    api_key: str = Field(..., min_length=8)
    rule: Dict[str, Any]
    query_template: Optional[Dict[str, Any]] = None
    window: Optional[str] = Field(default="7d", max_length=32)


@app.post("/v1/dashboard/compliance/rules/test")
def compliance_rules_test(body: RuleTestBody) -> Dict[str, Any]:
    require_key(body.api_key, min_role="read_write", db_path=DB_PATH)
    try:
        return test_rule_against_history(
            body.api_key,
            body.rule,
            window=body.window,
            db_path=DB_PATH,
            query_template=body.query_template,
        )
    except ValueError as e:
        raise HTTPException(400, str(e)) from e


class BaselineBody(BaseModel):
    api_key: str = Field(..., min_length=8)
    time_range: str = Field(default="7d", max_length=32)
    custom_from: Optional[str] = None
    custom_to: Optional[str] = None


@app.post("/v1/dashboard/behavior/baseline")
def behavior_baseline(body: BaselineBody) -> Dict[str, Any]:
    require_key(body.api_key, min_role="read_write", db_path=DB_PATH)
    return create_baseline(
        api_key=body.api_key,
        time_range=body.time_range,
        custom_from=body.custom_from,
        custom_to=body.custom_to,
        db_path=DB_PATH,
    )


@app.get("/v1/dashboard/behavior/baselines")
def behavior_baselines(
    api_key: str = Query(..., min_length=8),
    limit: int = Query(50, ge=1, le=100),
    include_deleted: bool = Query(False),
) -> Dict[str, Any]:
    require_key(api_key, min_role="read_only", db_path=DB_PATH)
    rows = list_baselines(
        api_key, limit=limit, include_deleted=include_deleted, db_path=DB_PATH
    )
    lean = [
        {
            "id": r["id"],
            "timestamp": r["timestamp"],
            "time_range_start": r.get("time_range_start"),
            "time_range_end": r.get("time_range_end"),
            "time_range_label": r.get("time_range_label"),
            "stats": r.get("stats"),
            "baseline_hash": r.get("baseline_hash"),
            "chain_hash": r.get("chain_hash"),
            "n_calls": (r.get("stats") or {}).get("n_calls"),
            "deleted": r.get("deleted"),
            "duration_ms": r.get("duration_ms"),
        }
        for r in rows
    ]
    return {"n": len(lean), "baselines": lean}


@app.get("/v1/dashboard/behavior/baselines/compare")
def behavior_compare(
    api_key: str = Query(..., min_length=8),
    older_id: str = Query(...),
    newer_id: str = Query(...),
) -> Dict[str, Any]:
    require_key(api_key, min_role="read_only", db_path=DB_PATH)
    older = get_baseline(older_id, db_path=DB_PATH)
    newer = get_baseline(newer_id, db_path=DB_PATH)
    if not older or older.get("api_key") != api_key:
        raise HTTPException(404, "older baseline not found")
    if not newer or newer.get("api_key") != api_key:
        raise HTTPException(404, "newer baseline not found")
    return compare_baselines(older, newer)


@app.get("/v1/dashboard/behavior/baselines/{baseline_id}")
def behavior_baseline_detail(
    baseline_id: str, api_key: str = Query(..., min_length=8)
) -> Dict[str, Any]:
    require_key(api_key, min_role="read_only", db_path=DB_PATH)
    row = get_baseline(baseline_id, db_path=DB_PATH)
    if not row or row.get("api_key") != api_key:
        raise HTTPException(404, "baseline not found")
    return {"baseline": row, "proof": verify_single_baseline(row)}


@app.delete("/v1/dashboard/behavior/baselines/{baseline_id}")
def behavior_delete_baseline(
    baseline_id: str, api_key: str = Query(..., min_length=8)
) -> Dict[str, Any]:
    require_key(api_key, min_role="read_write", db_path=DB_PATH)
    try:
        return soft_delete(baseline_id=baseline_id, api_key=api_key, db_path=DB_PATH)
    except ValueError as e:
        raise HTTPException(404, str(e)) from e


class DriftCheckBody(BaseModel):
    api_key: str = Field(..., min_length=8)
    baseline_id: Optional[str] = None
    window: str = Field(default="today", max_length=32)


@app.post("/v1/dashboard/behavior/check-drift")
def behavior_check_drift(body: DriftCheckBody) -> Dict[str, Any]:
    require_key(body.api_key, min_role="read_write", db_path=DB_PATH)
    try:
        return detect_drift(
            api_key=body.api_key,
            baseline_id=body.baseline_id,
            window=body.window,
            db_path=DB_PATH,
        )
    except ValueError as e:
        raise HTTPException(400, str(e)) from e


@app.get("/v1/dashboard/behavior/drift-marks")
def behavior_drift_marks(
    api_key: str = Query(..., min_length=8),
    status: Optional[str] = Query("pending"),
    limit: int = Query(100, ge=1, le=500),
) -> Dict[str, Any]:
    require_key(api_key, min_role="read_only", db_path=DB_PATH)
    st = None if status in (None, "", "all") else status
    rows = list_drift_marks(api_key, status=st, limit=limit, db_path=DB_PATH)
    return {"n": len(rows), "marks": rows}


class ReviewBody(BaseModel):
    api_key: str = Field(..., min_length=8)
    status: str = Field(..., max_length=32)
    reviewed_by: str = Field(default="dashboard_user", max_length=80)


@app.patch("/v1/dashboard/behavior/drift-marks/{mark_id}/review")
def behavior_review_mark(mark_id: str, body: ReviewBody) -> Dict[str, Any]:
    require_key(body.api_key, min_role="read_write", db_path=DB_PATH)
    try:
        return review_drift_mark(
            mark_id=mark_id,
            api_key=body.api_key,
            status=body.status,
            reviewed_by=body.reviewed_by,
            db_path=DB_PATH,
        )
    except ValueError as e:
        raise HTTPException(400, str(e)) from e


@app.get("/v1/dashboard/behavior/drift-marks/{mark_id}")
def behavior_mark_detail(
    mark_id: str, api_key: str = Query(..., min_length=8)
) -> Dict[str, Any]:
    require_key(api_key, min_role="read_only", db_path=DB_PATH)
    row = get_drift_mark(mark_id, db_path=DB_PATH)
    if not row or row.get("api_key") != api_key:
        raise HTTPException(404, "mark not found")
    return {"mark": row, "proof": verify_single_drift_mark(row)}
