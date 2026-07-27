from typing import Any, Mapping

from adapters.base import OpenAICompatibleAdapter, ParsedUsage, _json


class GoogleAdapter(OpenAICompatibleAdapter):
    vendor_id = "google"
    display_name = "Google Gemini"
    default_base = "https://generativelanguage.googleapis.com/"

    def extract_usage(
        self, request_body: bytes, response_body: bytes, *, rates: Mapping[str, Any]
    ) -> ParsedUsage:
        """Parse Gemini ``usageMetadata`` (falls back to OpenAI-style ``usage``)."""
        from metering import estimate_cost_usd

        req = _json(request_body)
        resp = _json(response_body)
        model = (
            resp.get("model")
            or req.get("model")
            or (req.get("model") if isinstance(req.get("model"), str) else None)
            or "gemini-1.5-flash"
        )
        # generateContent often nests model in response differently
        if not model or model == "gemini-1.5-flash":
            model = (
                resp.get("modelVersion")
                or resp.get("model")
                or req.get("model")
                or "gemini-1.5-flash"
            )

        meta = resp.get("usageMetadata") or {}
        usage = resp.get("usage") or {}
        if isinstance(meta, dict) and meta:
            prompt = int(
                meta.get("promptTokenCount")
                or meta.get("prompt_token_count")
                or 0
            )
            completion = int(
                meta.get("candidatesTokenCount")
                or meta.get("candidates_token_count")
                or meta.get("outputTokenCount")
                or 0
            )
            # Do not invent a prompt/completion split from totalTokenCount —
            # that would skew metering. Keep zeros; record total in extra below.
            total_tokens = int(meta.get("totalTokenCount") or 0)
        elif isinstance(usage, dict):
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
            total_tokens = 0
        else:
            prompt = completion = 0
            total_tokens = 0

        cost = estimate_cost_usd(
            model=str(model),
            prompt_tokens=prompt,
            completion_tokens=completion,
        )
        extra: dict = {"rates_hint": bool(rates), "vendor": "google"}
        if total_tokens and prompt == 0 and completion == 0:
            extra["total_token_count"] = total_tokens
            extra["metering_note"] = "totalTokenCount present but parts missing; cost not inferred"
        return ParsedUsage(
            model=str(model) if model else None,
            prompt_tokens=prompt,
            completion_tokens=completion,
            cost_usd=float(cost),
            extra=extra,
        )
