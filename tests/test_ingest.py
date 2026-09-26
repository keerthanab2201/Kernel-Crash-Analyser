from pathlib import Path

import pytest

from src.ingest import ingest_directory, parse_log


FIXTURES = Path(__file__).parents[1] / "crash_logs"


def test_five_fixture_categories_and_fields():
    parsed = {item.crash_id: item for item in ingest_directory(FIXTURES)}
    assert parsed["null_deref_fixture"].crash_type_guess == "null_pointer_deref"
    assert parsed["explicit_panic_fixture"].crash_type_guess == "panic_explicit"
    assert parsed["stack_overflow_fixture"].crash_type_guess == "stack_overflow"
    assert parsed["uaf_fixture"].crash_type_guess == "use_after_free"
    assert parsed["gpf_fixture"].crash_type_guess == "general_protection_fault"
    assert parsed["null_deref_fixture"].faulting_instruction.startswith("toy_write")
    assert "vfs_write+0xc7/0x390" in parsed["null_deref_fixture"].call_stack
    assert parsed["null_deref_fixture"].registers


def test_specific_signature_beats_generic_panic_trailer():
    text = "BUG: unable to handle kernel NULL pointer dereference\nKernel panic - not syncing: Fatal exception"
    assert parse_log(text).crash_type_guess == "null_pointer_deref"


def test_empty_log_rejected():
    with pytest.raises(ValueError, match="empty"):
        parse_log("  \n")
