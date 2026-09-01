import httpx
import respx

from app.alibaba import AlibabaClient
from app.scanner import classify, discover


def test_classifier_keeps_expensive_models_unprobed():
    assert classify("qwen-coder") == "CODING"
    assert classify("wan-video") == "VIDEO"
    assert classify("qwen-vl") == "VISION"
    assert classify("qwen-chat") == "GENERAL_CHAT"


@respx.mock
def test_discovery_deduplicates_and_does_not_probe():
    route = respx.get("https://example.test/v1/models").mock(return_value=httpx.Response(200, json={"data": [{"id": "qwen-chat"}, {"id": "qwen-chat"}, {"id": "wan-video"}]}))
    results = __import__("asyncio").run(discover(AlibabaClient("https://example.test/v1", "secret")))
    assert route.called
    assert len(results) == 2
    assert all(result["status"] == "NOT_PROBED" for result in results)

