"""Multi-vendor API proxy with attestation + metering side effects.

Client points base URL here; Authorization carries the upstream vendor key.
Attestation tenant key: ``X-Attest-Key`` header (or ``attest_key`` query).
Optional: ``X-Upstream-Base`` / ``X-Attest-Vendor`` for routing hints.
Request/response bodies are hashed then discarded from storage.
"""

from __future__ import annotations

import ipaddress
import json
import os
import time
from typing import Optional, Tuple
from urllib.parse import parse_qsl, urlencode, urljoin, urlparse

import httpx
from fastapi import HTTPException, Request, Response

from adapters import detect_vendor, get_adapter
from attestation import build_call_record
from key_auth import require_key
from write_buffer import enqueue_with_builder

DEFAULT_UPSTREAM = os.environ.get("ATA_UPSTREAM_BASE", "https://api.openai.com/").rstrip("/") + "/"
TIMEOUT = float(os.environ.get("ATA_PROXY_TIMEOUT", "120"))
_STRIP_QUERY = frozenset({"attest_key", "ata_key", "x-attest-key"})
_BLOCKED_UPSTREAM_HOSTS = frozenset(
    {
        "metadata.google.internal",
        "metadata",
        "169.254.169.254",
    }
)


def resolve_attest_key(request: Request) -> Optional[str]:
    key = request.headers.get("x-attest-key") or request.headers.get("X-Attest-Key")
    if key:
        return key.strip()
    return (request.query_params.get("attest_key") or "").strip() or None


def _forward_query(query: str) -> str:
    """Drop attestation secrets before forwarding query string upstream."""
    if not query:
        return ""
    kept = [(k, v) for k, v in parse_qsl(query, keep_blank_values=True) if k.lower() not in _STRIP_QUERY]
    return urlencode(kept)


def _sanitize_upstream_base(base: str) -> str:
    """Reject non-http(s) and cloud-metadata targets (SSRF guard)."""
    raw = base.strip()
    if not raw:
        raise HTTPException(400, "empty upstream base")
    if "://" not in raw:
        raw = "https://" + raw
    parsed = urlparse(raw)
    if parsed.scheme not in ("http", "https"):
        raise HTTPException(400, "upstream must be http(s)")
    host = (parsed.hostname or "").lower()
    if not host or host in _BLOCKED_UPSTREAM_HOSTS:
        raise HTTPException(400, "blocked upstream host")
    try:
        ip = ipaddress.ip_address(host)
        if ip.is_link_local or str(ip) == "169.254.169.254":
            raise HTTPException(400, "blocked upstream host")
        allow_private = os.environ.get("ATA_ALLOW_PRIVATE_UPSTREAM", "").strip().lower() in (
            "1",
            "true",
            "yes",
        )
        if (ip.is_private or ip.is_loopback) and not allow_private:
            raise HTTPException(
                400,
                "private upstream blocked; set ATA_ALLOW_PRIVATE_UPSTREAM=1 to allow",
            )
    except ValueError:
        pass  # hostname, not an IP literal
    allowlist = os.environ.get("ATA_UPSTREAM_ALLOWLIST", "").strip()
    if allowlist:
        allowed = {h.strip().lower() for h in allowlist.split(",") if h.strip()}
        if host not in allowed:
            raise HTTPException(400, "X-Upstream-Base host not in ATA_UPSTREAM_ALLOWLIST")
    return raw.rstrip("/") + "/"


def _upstream_base(request: Request, vendor_id: str, adapter) -> str:
    explicit = (
        request.headers.get("x-upstream-base")
        or request.headers.get("X-Upstream-Base")
        or ""
    ).strip()
    if explicit:
        return _sanitize_upstream_base(explicit)
    env_key = f"ATA_UPSTREAM_{vendor_id.upper()}"
    env_val = os.environ.get(env_key, "").strip()
    if env_val:
        return env_val.rstrip("/") + "/"
    if vendor_id == "openai":
        return DEFAULT_UPSTREAM
    return (getattr(adapter, "default_base", None) or DEFAULT_UPSTREAM).rstrip("/") + "/"


async def forward_openai(
    request: Request,
    path: str,
    *,
    db_path=None,
) -> Tuple[Response, Optional[dict]]:
    """Proxy to detected vendor upstream and append an attestation chain link.

    Returns (client Response, call_record_or_None).
    """
    attest_key = resolve_attest_key(request)
    if not attest_key:
        return (
            Response(
                content=b'{"error":"missing X-Attest-Key"}',
                status_code=401,
                media_type="application/json",
            ),
            None,
        )

    try:
        require_key(attest_key, for_proxy=True, db_path=db_path, label="proxy")
    except HTTPException as e:
        return (
            Response(
                content=json.dumps({"error": e.detail}).encode(),
                status_code=e.status_code,
                media_type="application/json",
            ),
            None,
        )

    body = await request.body()
    skip = {
        "host",
        "content-length",
        "x-attest-key",
        "x-attest-vendor",
        "x-upstream-base",
        "x-upstream-host",
        "connection",
        "transfer-encoding",
    }
    headers = {
        k: v
        for k, v in request.headers.items()
        if k.lower() not in skip
    }
    if "authorization" not in {k.lower() for k in headers} and "x-api-key" not in {
        k.lower() for k in headers
    }:
        return (
            Response(
                content=b'{"error":"missing Authorization or x-api-key (upstream)"}',
                status_code=401,
                media_type="application/json",
            ),
            None,
        )

    host_hint = (
        request.headers.get("x-upstream-host")
        or request.headers.get("X-Upstream-Host")
        or request.headers.get("host")
        or ""
    )
    vendor_id = detect_vendor(path=path, headers=request.headers, host=host_hint, body=body)
    adapter = get_adapter(vendor_id)
    try:
        upstream_base = _upstream_base(request, vendor_id, adapter)
    except HTTPException as e:
        return (
            Response(
                content=json.dumps({"error": e.detail}).encode(),
                status_code=e.status_code,
                media_type="application/json",
            ),
            None,
        )

    url = urljoin(upstream_base, path.lstrip("/"))
    fwd_q = _forward_query(str(request.url.query or ""))
    if fwd_q:
        url = f"{url}?{fwd_q}"

    t0 = time.perf_counter()
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        upstream = await client.request(
            request.method,
            url,
            content=body,
            headers=headers,
        )
    duration_ms = (time.perf_counter() - t0) * 1000.0

    resp_body = upstream.content
    usage = adapter.extract_usage(body, resp_body, rates={})

    # Atomically allocate prev_hash + enqueue (avoids concurrent tip forks)
    record = enqueue_with_builder(
        attest_key,
        lambda prev: build_call_record(
            api_key=attest_key,
            prev_hash=prev,
            endpoint="/" + path.lstrip("/"),
            method=request.method,
            model=usage.model,
            status_code=upstream.status_code,
            request_body=body,
            response_body=resp_body,
            duration_ms=duration_ms,
            prompt_tokens=int(usage.prompt_tokens or 0),
            completion_tokens=int(usage.completion_tokens or 0),
            cost_usd=float(usage.cost_usd or 0),
            vendor=vendor_id,
        ),
        db_path=db_path,
    )

    out_headers = {
        k: v
        for k, v in upstream.headers.items()
        if k.lower()
        not in {
            "content-encoding",
            "transfer-encoding",
            "content-length",
            "connection",
        }
    }
    out_headers["X-Attest-Call-Id"] = record["id"]
    out_headers["X-Attest-Chain-Hash"] = record["chain_hash"]
    out_headers["X-Attest-Vendor"] = vendor_id

    return (
        Response(
            content=resp_body,
            status_code=upstream.status_code,
            headers=out_headers,
            media_type=upstream.headers.get("content-type"),
        ),
        record,
    )
