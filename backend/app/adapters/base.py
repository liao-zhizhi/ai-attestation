"""Vendor adapter protocol + shared OpenAI-compatible helpers."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Dict, Mapping, Optional, Protocol


@dataclass
class ParsedUsage:
    model: Optional[str]
    prompt_tokens: int
    completion_tokens: int
    cost_usd: float
    extra: Dict[str, Any]


class VendorAdapter(Protocol):
    vendor_id: str
    display_name: str
    default_base: str

    def parse_request(self, body: bytes) -> Dict[str, Any]:
        ...

    def parse_response(self, body: bytes) -> Dict[str, Any]:
        ...

    def extract_usage(
        self, request_body: bytes, response_body: bytes, *, rates: Mapping[str, Any]
    ) -> ParsedUsage:
        ...


def _json(body: bytes) -> Dict[str, Any]:
    if not body:
        return {}
    try:
        data = json.loads(body)
        return data if isinstance(data, dict) else {}
    except (json.JSONDecodeError, TypeError):
        return {}


def openai_style_usage(
    request_body: bytes,
    response_body: bytes,
    *,
    rates: Mapping[str, Any],
    default_model: str = "gpt-4o-mini",
) -> ParsedUsage:
    from metering import estimate_cost_usd

    req = _json(request_body)
    resp = _json(response_body)
    model = (
        resp.get("model")
        or req.get("model")
        or default_model
    )
    usage = resp.get("usage") or {}
    if isinstance(usage, dict):
        prompt = int(
            usage.get("prompt_tokens")
            or usage.get("input_tokens")
            or usage.get("promptTokens")
            or 0
        )
        completion = int(
            usage.get("completion_tokens")
            or usage.get("output_tokens")
            or usage.get("completionTokens")
            or 0
        )
    else:
        prompt = completion = 0
    cost = estimate_cost_usd(
        model=str(model),
        prompt_tokens=prompt,
        completion_tokens=completion,
    )
    return ParsedUsage(
        model=str(model) if model else None,
        prompt_tokens=prompt,
        completion_tokens=completion,
        cost_usd=float(cost),
        extra={"rates_hint": bool(rates)},
    )


class OpenAICompatibleAdapter:
    """Base for vendors that speak OpenAI chat/completions JSON."""

    vendor_id = "openai"
    display_name = "OpenAI"
    default_base = "https://api.openai.com/"

    def parse_request(self, body: bytes) -> Dict[str, Any]:
        return _json(body)

    def parse_response(self, body: bytes) -> Dict[str, Any]:
        return _json(body)

    def extract_usage(
        self, request_body: bytes, response_body: bytes, *, rates: Mapping[str, Any]
    ) -> ParsedUsage:
        return openai_style_usage(request_body, response_body, rates=rates)
