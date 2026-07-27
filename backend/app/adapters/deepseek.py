from adapters.base import OpenAICompatibleAdapter


class DeepSeekAdapter(OpenAICompatibleAdapter):
    vendor_id = "deepseek"
    display_name = "DeepSeek"
    default_base = "https://api.deepseek.com/"
