from src.cellular import timeline


def test_stage_is_not_cause_and_identifiers_are_redacted():
    result = timeline({"ue.log": "[2026-01-01 10:00:00.200] Registration accept received IMSI=123456789012345\n[2026-01-01 10:00:00.300] PDU Session Establishment Reject received", "gnb.log": "[2026-01-01 10:00:00.100] NG Setup Failure"})
    assert result["events"][0]["source"] == "gnb.log"
    assert len(result["observed_failure_events"]) == 2
    assert result["root_cause"] is None
    assert "123456789012345" not in str(result)


def test_unknown_lines_and_missing_timestamp_remain_explicit():
    result = timeline({"ue.log": "unrecognized text\nPDU Session Establishment Reject received"})
    assert result["unmatched_lines"] == 1
    assert result["events"][0]["timestamp"] is None
