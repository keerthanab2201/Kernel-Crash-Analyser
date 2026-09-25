"""Shared data contracts and validation.

These validators deliberately do not trust either the model or stored JSON. The
Anthropic schema constrains generation, while this module independently checks
the response before it enters the evaluation dataset.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

CATEGORIES = (
    "null_pointer_deref",
    "use_after_free",
    "stack_overflow",
    "general_protection_fault",
    "deadlock",
    "panic_explicit",
    "unknown_other",
)


@dataclass(slots=True)
class ParsedCrash:
    crash_id: str
    source_file: str
    raw_log: str
    crash_type_guess: str = "unknown_other"
    faulting_instruction: str | None = None
    call_stack: list[str] = field(default_factory=list)
    registers: list[str] = field(default_factory=list)
    key_lines: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class Diagnosis:
    category: str
    likely_cause: str
    confidence: float
    supporting_evidence: list[str]

    @classmethod
    def from_mapping(cls, value: Any) -> "Diagnosis":
        if not isinstance(value, dict):
            raise ValueError("tool input is not an object")
        missing = {
            "category",
            "likely_cause",
            "confidence",
            "supporting_evidence",
        } - value.keys()
        if missing:
            raise ValueError(f"missing required fields: {sorted(missing)}")
        extra = value.keys() - {
            "category",
            "likely_cause",
            "confidence",
            "supporting_evidence",
        }
        if extra:
            raise ValueError(f"unexpected fields: {sorted(extra)}")
        if value["category"] not in CATEGORIES:
            raise ValueError(f"invalid category: {value['category']!r}")
        cause = value["likely_cause"]
        if not isinstance(cause, str) or not cause.strip():
            raise ValueError("likely_cause must be a non-empty string")
        confidence = value["confidence"]
        if isinstance(confidence, bool) or not isinstance(confidence, (int, float)):
            raise ValueError("confidence must be numeric")
        if not 0 <= float(confidence) <= 1:
            raise ValueError("confidence must be between 0 and 1")
        evidence = value["supporting_evidence"]
        if not isinstance(evidence, list) or not all(
            isinstance(item, str) and item.strip() for item in evidence
        ):
            raise ValueError("supporting_evidence must be a list of non-empty strings")
        return cls(value["category"], cause.strip(), float(confidence), evidence)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

