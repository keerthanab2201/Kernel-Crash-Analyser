"""Use real SDK serialization against a local HTTP mock; never reaches the API."""

import json
import httpx
import anthropic
from src.diagnose import diagnose_repeated
from src.models import ParsedCrash


def test_sdk_request_is_strict_redacted_and_usage_is_retained():
    requests = []
    evidence = "Kernel panic - not syncing: test"

    def handle(request):
        payload = json.loads(request.content)
        requests.append(payload)
        return httpx.Response(
            200,
            json={
                "id": "msg_mock",
                "type": "message",
                "role": "assistant",
                "model": "test-model",
                "content": [
                    {
                        "type": "tool_use",
                        "id": "tool_mock",
                        "name": "submit_diagnosis",
                        "input": {
                            "category": "panic_explicit",
                            "confidence": 0.9,
                            "likely_cause": "Explicit panic observed.",
                            "supporting_evidence": [evidence],
                        },
                    }
                ],
                "stop_reason": "tool_use",
                "stop_sequence": None,
                "usage": {"input_tokens": 25, "output_tokens": 20},
            },
        )

    with anthropic.Anthropic(
        api_key="test-not-a-secret",
        max_retries=0,
        http_client=httpx.Client(transport=httpx.MockTransport(handle)),
    ) as client:
        record = diagnose_repeated(
            client,
            ParsedCrash("mock", "mock.log", evidence + "\nIMSI=123456789012345"),
            model="test-model",
            repeats=1,
        )
    assert len(requests) == 1
    assert requests[0]["tools"][0]["strict"] is True
    assert requests[0]["tool_choice"]["name"] == "submit_diagnosis"
    assert "123456789012345" not in json.dumps(requests)
    assert record["runs"][0]["attempts"][0]["calls"][0]["usage"]["input_tokens"] == 25
