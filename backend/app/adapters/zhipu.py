from adapters.base import OpenAICompatibleAdapter


class ZhipuAdapter(OpenAICompatibleAdapter):
    vendor_id = "zhipu"
    display_name = "智谱 GLM"
    default_base = "https://open.bigmodel.cn/"
