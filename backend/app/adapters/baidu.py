from adapters.base import OpenAICompatibleAdapter


class BaiduAdapter(OpenAICompatibleAdapter):
    vendor_id = "baidu"
    display_name = "百度文心"
    default_base = "https://aip.baidubce.com/"
