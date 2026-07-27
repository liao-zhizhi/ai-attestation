from adapters.base import OpenAICompatibleAdapter


class TencentAdapter(OpenAICompatibleAdapter):
    vendor_id = "tencent"
    display_name = "腾讯混元"
    default_base = "https://hunyuan.tencentcloudapi.com/"
