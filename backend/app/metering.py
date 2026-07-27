"""Usage metering for the attestation proxy.

Parse ``usage`` from OpenAI-compatible chat/completions responses and apply
published per-1M-token rates to estimate USD cost.
"""

from __future__ import annotations

import json
from typing import Any, Dict, Mapping, Optional, Tuple

# USD per 1M tokens — approximate public list prices (2025/2026). Update as needed.
# Format: model_prefix -> (input_per_m, output_per_m)
OPENAI_USD_PER_M: Dict[str, Tuple[float, float]] = {
    "gpt-4o": (2.50, 10.00),
    "gpt-4o-mini": (0.15, 0.60),
    "gpt-4.1": (2.00, 8.00),
    "gpt-4.1-mini": (0.40, 1.60),
    "gpt-4.1-nano": (0.10, 0.40),
    "gpt-4-turbo": (10.00, 30.00),
    "gpt-4": (30.00, 60.00),
    "gpt-3.5-turbo": (0.50, 1.50),
    "o1": (15.00, 60.00),
    "o1-mini": (3.00, 12.00),
    "o3-mini": (1.10, 4.40),
    "text-embedding-3-small": (0.02, 0.0),
    "text-embedding-3-large": (0.13, 0.0),
    "text-embedding-ada-002": (0.10, 0.0),
}

DEFAULT_RATES = (1.00, 3.00)


def resolve_rates(model: Optional[str]) -> Tuple[float, float]:
    if not model:
        return DEFAULT_RATES
    m = model.lower().strip()
    if m in OPENAI_USD_PER_M:
        return OPENAI_USD_PER_M[m]
    # longest prefix match
    best: Optional[Tuple[float, float]] = None
    best_len = 0
    for key, rates in OPENAI_USD_PER_M.items():
        if m.startswith(key) and len(key) > best_len:
            best = rates
            best_len = len(key)
    return best or DEFAULT_RATES


def extract_usage(response_json: Mapping[str, Any]) -> Tuple[int, int, Optional[str]]:
    usage = response_json.get("usage") or {}
    prompt = int(usage.get("prompt_tokens") or usage.get("input_tokens") or 0)
    completion = int(usage.get("completion_tokens") or usage.get("output_tokens") or 0)
    model = response_json.get("model")
    if isinstance(model, str):
        return prompt, completion, model
    return prompt, completion, None


def estimate_cost_usd(
    *,
    model: Optional[str],
    prompt_tokens: int,
    completion_tokens: int,
) -> float:
    inp, out = resolve_rates(model)
    return round(
        (max(0, prompt_tokens) * inp + max(0, completion_tokens) * out) / 1_000_000.0,
        8,
    )


def meter_from_response_bytes(
    response_body: bytes, *, request_model: Optional[str] = None
) -> Dict[str, Any]:
    """Parse usage from OpenAI JSON response; never requires storing the body."""
    model = request_model
    prompt = completion = 0
    try:
        data = json.loads(response_body.decode("utf-8"))
        if isinstance(data, dict):
            prompt, completion, resp_model = extract_usage(data)
            model = resp_model or model
    except (UnicodeDecodeError, json.JSONDecodeError, TypeError, ValueError):
        pass
    cost = estimate_cost_usd(
        model=model, prompt_tokens=prompt, completion_tokens=completion
    )
    return {
        "model": model,
        "prompt_tokens": prompt,
        "completion_tokens": completion,
        "cost_usd": cost,
        "rates_usd_per_m": resolve_rates(model),
    }


def peek_request_model(request_body: bytes) -> Optional[str]:
    try:
        data = json.loads(request_body.decode("utf-8"))
        if isinstance(data, dict) and isinstance(data.get("model"), str):
            return data["model"]
    except (UnicodeDecodeError, json.JSONDecodeError, TypeError, ValueError):
        return None
    return None
