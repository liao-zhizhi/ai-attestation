from adapters.base import OpenAICompatibleAdapter


class OpenAIAdapter(OpenAICompatibleAdapter):
    vendor_id = "openai"
    display_name = "OpenAI"
    default_base = "https://api.openai.com/"
