import math

import numpy as np
import pytest

from src.reliability_eval import (
    calibration_summary,
    category_entropy,
    confidence_icc,
    evaluate,
    expected_calibration_error,
    mean_pairwise_cosine,
)


def test_entropy_hand_computed_cases():
    assert category_entropy(["a", "a", "a", "a"]) == 0.0
    assert category_entropy(["a", "a", "b", "b"]) == 1.0
    assert category_entropy(["a", "b", "c", "d"]) == 2.0
    expected = -(0.75 * math.log2(0.75) + 0.25 * math.log2(0.25))
    assert category_entropy(["a", "a", "a", "b"]) == pytest.approx(expected)


def test_pairwise_cosine_hand_computed():
    vectors = np.array([[1.0, 0.0], [1.0, 0.0], [0.0, 1.0]])
    # Pairwise similarities are 1, 0, 0.
    assert mean_pairwise_cosine(vectors) == pytest.approx(1 / 3)


def test_ece_and_brier_hand_computed():
    confidence = [0.1, 0.4, 0.8, 0.9]
    correct = [False, True, True, True]
    # With two bins: first bin mean conf=.25, accuracy=.5 (weight .5),
    # second mean conf=.85, accuracy=1 (weight .5): ECE=.2.
    assert expected_calibration_error(confidence, correct, bins=2) == pytest.approx(0.2)
    result = calibration_summary(confidence, correct, bins=2)
    assert result["brier_score"] == pytest.approx((0.01 + 0.36 + 0.04 + 0.01) / 4)


def test_confidence_one_is_in_last_bin():
    result = calibration_summary([1.0], [True], bins=5)
    assert result["bins"] == [
        {"lower": 0.8, "upper": 1.0, "count": 1, "mean_confidence": 1.0, "fraction_correct": 1.0}
    ]


def test_embedding_validation():
    with pytest.raises(ValueError, match="two-dimensional"):
        mean_pairwise_cosine(np.array([1.0, 2.0]))
    with pytest.raises(ValueError, match="zero-length"):
        mean_pairwise_cosine(np.array([[0.0, 0.0], [1.0, 0.0]]))


def test_icc_perfect_agreement_hand_computed():
    # Each repeat gives exactly the same score for a target, so within-target and
    # rater disagreement variances are zero while between-target variance is nonzero.
    records = []
    for crash_id, confidence in (("low", 0.1), ("mid", 0.5), ("high", 0.9)):
        records.append(
            {
                "crash_id": crash_id,
                "runs": [
                    {"run_index": run, "status": "ok", "confidence": confidence}
                    for run in range(3)
                ],
            }
        )
    result = confidence_icc(records)
    assert result["icc2_1"] == pytest.approx(1.0)
    assert result["n_crashes"] == 3
    assert result["n_raters"] == 3


def test_evaluate_reports_failures_and_aggregates():
    records = [
        {
            "crash_id": "one",
            "runs": [
                {
                    "run_index": 0,
                    "status": "ok",
                    "category": "panic_explicit",
                    "confidence": 0.8,
                    "likely_cause": "explicit panic",
                },
                {
                    "run_index": 1,
                    "status": "ok",
                    "category": "panic_explicit",
                    "confidence": 0.9,
                    "likely_cause": "explicit panic",
                },
                {"run_index": 2, "status": "failed", "errors": ["bad schema"]},
            ],
        }
    ]

    def embed(texts):
        return np.array([[1.0, 0.0] for _ in texts])

    result = evaluate(records, embedder=embed)
    assert result["failure_rate"] == pytest.approx(1 / 3)
    assert result["failure_rate_warning"] is True
    assert result["aggregate_consistency"]["mean_category_entropy_bits"] == 0.0
    assert result["aggregate_consistency"]["mean_semantic_similarity"] == 1.0
    assert result["worked_examples"][0]["crash_id"] == "one"
