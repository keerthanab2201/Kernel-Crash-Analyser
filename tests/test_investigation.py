import json
import pytest
from src.privacy import Redactor
from src.investigation import EvidenceTools


def corpus(tmp_path):
    path = tmp_path / "corpus.json"
    path.write_text(json.dumps({"version": "1", "documents": [{"id": "d1", "kind": "documentation", "source_url": "https://docs.kernel.org/dev-tools/kasan.html", "revision": "v6.8", "text": "KASAN detects invalid memory accesses including use after free", "symbols": ["kasan_report"]}]}))
    return path


def test_redaction_preserves_correlations_and_kernel_addresses():
    redactor = Redactor(b"test-key")
    text = redactor.redact("IMSI=123456789012345 src=10.0.0.1 dst=10.0.0.1 RIP=ffff888012340000")
    assert "123456789012345" not in text and "10.0.0.1" not in text
    assert text.split("src=")[1].split()[0] == text.split("dst=")[1].split()[0]
    assert "ffff888012340000" in text


def test_tools_restrict_context_and_revision(tmp_path):
    tools = EvidenceTools("first\nsecond\nthird", corpus(tmp_path))
    assert tools.execute("get_log_context", {"line_id": 2, "window": 0})["lines"] == [{"line_id": 2, "text": "second"}]
    with pytest.raises(ValueError):
        tools.execute("get_log_context", {"line_id": 1, "window": 100})
    assert tools.execute("search_documentation", {"query": "use after free"})["matches"][0]["id"] == "d1"
    assert not tools.execute("lookup_symbol", {"symbol": "kasan_report", "kernel_revision": "wrong"})["matches"]


def test_incident_corpus_is_rejected(tmp_path):
    path = corpus(tmp_path)
    value = json.loads(path.read_text())
    value["documents"][0]["kind"] = "incident_fix"
    path.write_text(json.dumps(value))
    with pytest.raises(ValueError, match="documentation only"):
        EvidenceTools("log", path)


def test_investigation_is_bounded_and_records_tool_result(tmp_path):
    from types import SimpleNamespace
    from src.diagnose import diagnose_once
    from src.models import ParsedCrash

    class Block:
        type = "tool_use"
        id = "call-1"
        def __init__(self, name, args):
            self.name, self.input = name, args
        def model_dump(self):
            return {"type": self.type, "id": self.id, "name": self.name, "input": self.input}

    requests = []
    def create(**kwargs):
        requests.append(kwargs)
        block = Block("get_log_context", {"line_id": 1, "window": 0}) if len(requests) == 1 else Block("submit_diagnosis", {"category": "unknown_other", "likely_cause": "Insufficient evidence", "confidence": .1, "supporting_evidence": ["first"]})
        return SimpleNamespace(content=[block])
    trace = {}
    diagnosis = diagnose_once(SimpleNamespace(messages=SimpleNamespace(create=create)), ParsedCrash("a", "a.log", "first"), model="test", telemetry=trace, evidence_tools=EvidenceTools("first", corpus(tmp_path)), max_tool_rounds=1)
    assert diagnosis.category == "unknown_other"
    assert len(trace["calls"]) == 2
    assert requests[1]["tool_choice"]["name"] == "submit_diagnosis"
    assert trace["calls"][0]["tool"]["result"]["lines"][0]["text"] == "first"
