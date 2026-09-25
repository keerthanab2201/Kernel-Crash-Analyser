import pytest

from src.diagnose import SUBMIT_DIAGNOSIS_TOOL, diagnose_repeated
from src.models import ParsedCrash
from src.models import Diagnosis


def test_diagnosis_contract_accepts_valid_mapping():
    value = Diagnosis.from_mapping(
        {
            "category": "panic_explicit",
            "likely_cause": "The panic was called explicitly.",
            "confidence": 0.9,
            "supporting_evidence": ["Kernel panic - not syncing: deliberate test panic"],
        }
    )
    assert value.confidence == 0.9


@pytest.mark.parametrize("confidence", [-0.1, 1.1, True, "0.5"])
def test_diagnosis_contract_rejects_bad_confidence(confidence):
    with pytest.raises(ValueError):
        Diagnosis.from_mapping(
            {
                "category": "unknown_other",
                "likely_cause": "Insufficient evidence.",
                "confidence": confidence,
                "supporting_evidence": ["Oops"],
            }
        )


class _Block:
    type = "tool_use"
    name = "submit_diagnosis"

    def __init__(self, value):
        self.input = value


class _Messages:
    def __init__(self, values):
        self.values = iter(values)

    def create(self, **kwargs):
        value = next(self.values)
        if isinstance(value, Exception):
            raise value
        return type("Response", (), {"content": [_Block(value)]})()


class _Client:
    def __init__(self, values):
        self.messages = _Messages(values)


def _crash():
    return ParsedCrash("id", "fixture.log", "Kernel panic - not syncing: test")


def test_strict_tool_contract_and_retry_preserves_run():
    assert SUBMIT_DIAGNOSIS_TOOL["strict"] is True
    valid = {
        "category": "panic_explicit",
        "likely_cause": "Explicit test panic.",
        "confidence": 0.9,
        "supporting_evidence": ["Kernel panic - not syncing: test"],
    }
    record = diagnose_repeated(
        _Client([RuntimeError("temporary"), valid]),
        _crash(),
        model="test-model",
        repeats=1,
        max_attempts=2,
        sleeper=lambda _: None,
    )
    assert record["runs"][0]["status"] == "ok"
    assert record["log_excerpt"].startswith("Kernel panic")


def test_exhausted_attempt_is_explicit_failed_run():
    record = diagnose_repeated(
        _Client([RuntimeError("one"), RuntimeError("two")]),
        _crash(),
        model="test-model",
        repeats=1,
        max_attempts=2,
        sleeper=lambda _: None,
    )
    assert record["runs"][0]["status"] == "failed"
    assert len(record["runs"][0]["errors"]) == 2
