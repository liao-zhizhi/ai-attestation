from adapters.base import OpenAICompatibleAdapter


class AlibabaAdapter(OpenAICompatibleAdapter):
    vendor_id = "alibaba"
    display_name = "阿里通义"
    default_base = "https://dashscope.aliyuncs.com/"
