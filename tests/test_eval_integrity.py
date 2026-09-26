import numpy as np
import pytest

from src.reliability_eval import evaluate


def test_unverified_labels_excluded_and_confidences_score_their_own_predictions(
    tmp_path,
):
    labels = tmp_path / "labels.csv"
    labels.write_text(
        "crash_id,crash_type,ground_truth_status,evidence_group\na,panic_explicit,verified,ambiguous\nb,panic_explicit,fixture_only,\n"
    )
    runs = [
        {
            "run_index": 0,
            "status": "ok",
            "category": "panic_explicit",
            "confidence": 0.8,
            "likely_cause": "a",
        },
        {
            "run_index": 1,
            "status": "ok",
            "category": "unknown_other",
            "confidence": 0.9,
            "likely_cause": "b",
        },
    ]
    records = [{"crash_id": key, "runs": runs} for key in ("a", "b")]
    result = evaluate(records, labels_path=labels, embedder=lambda _: np.eye(2))
    assert result["verified_crashes"] == 1
    assert result["calibration"]["n"] == 2
    assert result["calibration"]["brier_score"] == pytest.approx((0.04 + 0.81) / 2)
    assert result["per_crash"][1]["majority_correct"] is None
    assert result["per_crash"][1]["group"] == "unannotated"


def test_recovered_malformed_attempt_is_counted():
    run = {
        "run_index": 0,
        "status": "ok",
        "category": "unknown_other",
        "confidence": 0.2,
        "likely_cause": "unknown",
        "attempts": [{"status": "malformed"}, {"status": "ok"}],
    }
    result = evaluate([{"crash_id": "a", "runs": [run]}])
    assert result["recorded_api_attempts"] == 2
    assert result["malformed_attempt_rate"] == 0.5
    assert result["malformed_attempt_warning"]


def test_missing_repeat_is_not_silently_removed_from_denominator():
    with pytest.raises(ValueError, match="every requested"):
        evaluate([{"crash_id": "a", "requested_repeats": 2, "runs": []}])


def test_total_api_failure_counts_against_verified_accuracy(tmp_path):
    labels = tmp_path / "labels.csv"
    labels.write_text(
        "crash_id,crash_type,ground_truth_status,evidence_group\na,panic_explicit,verified,well_defined\n"
    )
    result = evaluate(
        [{"crash_id": "a", "runs": [{"run_index": 0, "status": "failed"}]}],
        labels_path=labels,
    )
    assert result["verified_crashes"] == 1
    assert result["majority_accuracy"] == 0
    assert result["groups"]["well_defined"]["n_crashes"] == 1
    assert result["calibration"]["n"] == 0
