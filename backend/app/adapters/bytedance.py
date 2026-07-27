from adapters.base import OpenAICompatibleAdapter


class BytedanceAdapter(OpenAICompatibleAdapter):
    vendor_id = "bytedance"
    display_name = "字节豆包"
    default_base = "https://ark.cn-beijing.volces.com/"
