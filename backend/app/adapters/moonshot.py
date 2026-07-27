from adapters.base import OpenAICompatibleAdapter


class MoonshotAdapter(OpenAICompatibleAdapter):
    vendor_id = "moonshot"
    display_name = "月之暗面 Kimi"
    default_base = "https://api.moonshot.cn/"
