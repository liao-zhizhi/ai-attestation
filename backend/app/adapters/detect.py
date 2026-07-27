"""Detect AI vendor from path, headers, host, and model field."""

from __future__ import annotations

import json
from typing import Mapping


def _hdr(headers: Mapping[str, str], *names: str) -> str:
    lower = {k.lower(): v for k, v in headers.items()}
    for n in names:
        if n.lower() in lower:
            return (lower[n.lower()] or "").strip()
    return ""


def _peek_model(body: bytes) -> str:
    if not body:
        return ""
    try:
        data = json.loads(body)
        if isinstance(data, dict):
            return str(data.get("model") or "").lower()
    except (json.JSONDecodeError, TypeError):
        pass
    return ""


def detect_vendor(
    *,
    path: str,
    headers: Mapping[str, str],
    host: str = "",
    body: bytes = b"",
) -> str:
    """Return vendor id. Defaults to openai when ambiguous."""
    p = "/" + (path or "").lstrip("/")
    pl = p.lower()
    host_l = (host or "").lower()
    # Explicit override
    forced = _hdr(headers, "x-attest-vendor", "X-Attest-Vendor")
    if forced:
        return forced.strip().lower()

    upstream_hint = _hdr(
        headers, "x-upstream-host", "X-Upstream-Host", "x-upstream-base", "X-Upstream-Base"
    ).lower()
    combined_host = host_l + " " + upstream_hint

    # Path-first domestic / unique routes
    if "wenxinworkshop" in pl or "/rpc/2.0/ai_custom" in pl:
        return "baidu"
    if "compatible-mode" in pl or "dashscope.aliyuncs.com" in combined_host:
        return "alibaba"
    if "hunyuan.tencentcloudapi.com" in combined_host or (
        "/openapi/v1/chat/completions" in pl and "tencent" in combined_host
    ):
        return "tencent"
    if "ark.cn-beijing.volces.com" in combined_host or (
        "/api/v1/chat/completions" in pl and ("volces" in combined_host or "bytedance" in combined_host)
    ):
        return "bytedance"
    if "open.bigmodel.cn" in combined_host or "/api/paas/v4" in pl:
        return "zhipu"
    if "api.moonshot.cn" in combined_host:
        return "moonshot"
    if "api.deepseek.com" in combined_host:
        return "deepseek"

    # International unique paths
    if "/v1beta/models" in pl or "gemini" in pl:
        return "google"
    if "/openai/deployments" in pl or "azure.com" in combined_host:
        return "azure"

    x_api = _hdr(headers, "x-api-key", "X-Api-Key")
    auth = _hdr(headers, "authorization", "Authorization")
    auth_l = auth.lower()

    if x_api.startswith("sk-ant") or "anthropic" in combined_host:
        return "anthropic"
    if "cohere" in auth_l or "cohere" in combined_host or pl.rstrip("/").endswith("/v1/chat"):
        if "cohere" in auth_l or "cohere" in combined_host:
            return "cohere"

    # Model heuristics
    model = _peek_model(body)
    if model.startswith(("claude",)):
        return "anthropic"
    if model.startswith(("gemini",)):
        return "google"
    if model.startswith(("ernie", "eb-")):
        return "baidu"
    if model.startswith(("qwen",)):
        return "alibaba"
    if model.startswith(("hunyuan",)):
        return "tencent"
    if model.startswith(("doubao", "ep-")):
        return "bytedance"
    if model.startswith(("deepseek",)):
        return "deepseek"
    if model.startswith(("glm",)):
        return "zhipu"
    if model.startswith(("moonshot", "kimi")):
        return "moonshot"
    if model.startswith(("command",)):
        return "cohere"

    if auth_l.startswith("bearer sk-") or auth_l.startswith("bearer sk"):
        # OpenAI-compatible bearer — default openai unless host says otherwise
        if "deepseek" in combined_host:
            return "deepseek"
        if "moonshot" in combined_host:
            return "moonshot"
        if "dashscope" in combined_host:
            return "alibaba"
        return "openai"

    return "openai"
