from adapters.base import OpenAICompatibleAdapter


class CohereAdapter(OpenAICompatibleAdapter):
    vendor_id = "cohere"
    display_name = "Cohere"
    default_base = "https://api.cohere.ai/"
