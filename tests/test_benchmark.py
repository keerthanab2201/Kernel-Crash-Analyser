import json
import pytest
from src.benchmark import consensus, fit_threshold, load_manifest, risk_coverage, cluster_interval


def test_test_set_cannot_tune_policy():
    with pytest.raises(ValueError, match="development"):
        fit_threshold([{"split": "test"}])


def test_family_leakage_rejected(tmp_path):
    path = tmp_path / "m.json"
    path.write_text(json.dumps([{"crash_id": "a", "bug_family": "same", "split": "dev"}, {"crash_id": "b", "bug_family": "same", "split": "test"}]))
    with pytest.raises(ValueError, match="boundary"):
        load_manifest(path)


def test_tied_scores_move_together_and_abstain_if_no_safe_threshold():
    rows = [{"split": "dev", "score": .8, "eligible": True, "correct": value} for value in (True, False)]
    assert len(risk_coverage(rows)) == 2
    assert fit_threshold(rows)["threshold"] is None


def test_tied_vote_and_missing_repeat_not_accepted():
    runs = [{"status": "ok", "category": c, "confidence": .9, "supporting_evidence": ["line"]} for c in ("panic_explicit", "unknown_other")]
    assert consensus({"runs": runs})["category"] is None
    assert not consensus({"runs": runs[:1], "requested_repeats": 3})["eligible"]


def test_bootstrap_does_not_invent_independent_incidents():
    assert cluster_interval([{"bug_family": "same", "correct": True}] * 10, "correct") is None
