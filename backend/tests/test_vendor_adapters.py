"""Vendor detection unit tests."""

from adapters.detect import detect_vendor


def test_detect_openai_default():
    assert detect_vendor(path="v1/chat/completions", headers={"authorization": "Bearer sk-xxx"}) == "openai"


def test_detect_anthropic_header():
    assert (
        detect_vendor(
            path="v1/chat/completions",
            headers={"x-api-key": "sk-ant-api03-xxx"},
        )
        == "anthropic"
    )


def test_detect_google_path():
    assert detect_vendor(path="v1beta/models/gemini-pro:generateContent", headers={}) == "google"


def test_detect_azure_path():
    assert detect_vendor(path="openai/deployments/gpt/chat/completions", headers={}) == "azure"


def test_detect_baidu_path():
    assert (
        detect_vendor(
            path="rpc/2.0/ai_custom/v1/wenxinworkshop/chat/completions",
            headers={},
        )
        == "baidu"
    )


def test_detect_alibaba_host():
    assert (
        detect_vendor(
            path="compatible-mode/v1/chat/completions",
            headers={"authorization": "Bearer sk-xxx"},
            host="dashscope.aliyuncs.com",
        )
        == "alibaba"
    )


def test_detect_deepseek_host():
    assert (
        detect_vendor(
            path="v1/chat/completions",
            headers={"authorization": "Bearer sk-xxx"},
            host="api.deepseek.com",
        )
        == "deepseek"
    )


def test_detect_zhipu_path():
    assert (
        detect_vendor(
            path="api/paas/v4/chat/completions",
            headers={"authorization": "Bearer xxx"},
            host="open.bigmodel.cn",
        )
        == "zhipu"
    )


def test_detect_model_qwen():
    body = b'{"model":"qwen-plus","messages":[]}'
    assert detect_vendor(path="v1/chat/completions", headers={}, body=body) == "alibaba"
