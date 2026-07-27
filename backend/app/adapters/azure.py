from adapters.base import OpenAICompatibleAdapter


class AzureAdapter(OpenAICompatibleAdapter):
    vendor_id = "azure"
    display_name = "Azure OpenAI"
    default_base = "https://openai.azure.com/"
