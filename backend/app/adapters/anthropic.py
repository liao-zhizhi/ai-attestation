from __future__ import annotations

from typing import Any, Mapping

from adapters.base import OpenAICompatibleAdapter, ParsedUsage, _json, openai_style_usage


class AnthropicAdapter(OpenAICompatibleAdapter):
    vendor_id = "anthropic"
    display_name = "Anthropic"
    default_base = "https://api.anthropic.com/"

    def extract_usage(
        self, request_body: bytes, response_body: bytes, *, rates: Mapping[str, Any]
    ) -> ParsedUsage:
        resp = _json(response_body)
        usage = resp.get("usage") or {}
        if "input_tokens" in usage or "output_tokens" in usage:
            from metering import estimate_cost_usd

            req = _json(request_body)
            model = resp.get("model") or req.get("model") or "claude-3-5-sonnet"
            prompt = int(usage.get("input_tokens") or 0)
            completion = int(usage.get("output_tokens") or 0)
            cost = estimate_cost_usd(
                model=str(model),
                prompt_tokens=prompt,
                completion_tokens=completion,
            )
            return ParsedUsage(
                model=str(model),
                prompt_tokens=prompt,
                completion_tokens=completion,
                cost_usd=float(cost),
                extra={},
            )
        return openai_style_usage(
            request_body, response_body, rates=rates, default_model="claude-3-5-sonnet"
        )
