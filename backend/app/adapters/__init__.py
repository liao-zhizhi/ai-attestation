"""Vendor adapters registry."""

from __future__ import annotations

from typing import Dict

from adapters.alibaba import AlibabaAdapter
from adapters.anthropic import AnthropicAdapter
from adapters.azure import AzureAdapter
from adapters.baidu import BaiduAdapter
from adapters.bytedance import BytedanceAdapter
from adapters.cohere import CohereAdapter
from adapters.deepseek import DeepSeekAdapter
from adapters.detect import detect_vendor
from adapters.google import GoogleAdapter
from adapters.moonshot import MoonshotAdapter
from adapters.openai import OpenAIAdapter
from adapters.tencent import TencentAdapter
from adapters.zhipu import ZhipuAdapter

_ADAPTERS = {
    "openai": OpenAIAdapter(),
    "anthropic": AnthropicAdapter(),
    "google": GoogleAdapter(),
    "azure": AzureAdapter(),
    "cohere": CohereAdapter(),
    "baidu": BaiduAdapter(),
    "alibaba": AlibabaAdapter(),
    "tencent": TencentAdapter(),
    "bytedance": BytedanceAdapter(),
    "deepseek": DeepSeekAdapter(),
    "zhipu": ZhipuAdapter(),
    "moonshot": MoonshotAdapter(),
}


def get_adapter(vendor_id: str):
    return _ADAPTERS.get((vendor_id or "openai").lower()) or _ADAPTERS["openai"]


def list_vendors() -> Dict[str, str]:
    return {k: a.display_name for k, a in _ADAPTERS.items()}


__all__ = ["detect_vendor", "get_adapter", "list_vendors"]
