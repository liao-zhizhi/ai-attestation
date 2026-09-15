from typing import Any, Mapping

from adapters.base import OpenAICompatibleAdapter, ParsedUsage, _json, _safe_int


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
            prompt = _safe_int(
                meta.get("promptTokenCount")
                if meta.get("promptTokenCount") is not None
                else meta.get("prompt_token_count")
            )
            completion = _safe_int(
                meta.get("candidatesTokenCount")
                if meta.get("candidatesTokenCount") is not None
                else meta.get("candidates_token_count")
                if meta.get("candidates_token_count") is not None
                else meta.get("outputTokenCount")
            )
            # Do not invent a prompt/completion split from totalTokenCount —
            # that would skew metering. Keep zeros; record total in extra below.
            total_tokens = _safe_int(meta.get("totalTokenCount"))
        elif isinstance(usage, dict):
            prompt = _safe_int(
                usage.get("prompt_tokens")
                if usage.get("prompt_tokens") is not None
                else usage.get("input_tokens")
                if usage.get("input_tokens") is not None
                else usage.get("promptTokens")
            )
            completion = _safe_int(
                usage.get("completion_tokens")
                if usage.get("completion_tokens") is not None
                else usage.get("output_tokens")
                if usage.get("output_tokens") is not None
                else usage.get("completionTokens")
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
