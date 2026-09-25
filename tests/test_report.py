from src.report import plot_calibration, render_markdown


def _report():
    return {
        "n_crashes": 1,
        "api_calls": 2,
        "failed_calls": 0,
        "failure_rate": 0.0,
        "failure_rate_warning": False,
        "small_sample_warning": True,
        "confidence_icc": {"icc2_1": None, "n_crashes": 1},
        "aggregate_consistency": {
            "mean_category_entropy_bits": 0.0,
            "mean_semantic_similarity": 1.0,
        },
        "calibration": {
            "n": 1,
            "brier_score": 0.04,
            "ece": 0.2,
            "bins": [
                {
                    "lower": 0.6,
                    "upper": 0.8,
                    "count": 1,
                    "mean_confidence": 0.8,
                    "fraction_correct": 1.0,
                }
            ],
        },
        "per_crash": [
            {
                "crash_id": "sample",
                "group": "well_defined",
                "valid_runs": 2,
                "majority_category": "panic_explicit",
                "majority_correct": True,
                "category_entropy_bits": 0.0,
                "mean_semantic_similarity": 1.0,
                "mean_confidence": 0.8,
                "confidence_sd": 0.1,
            }
        ],
        "worked_examples": [],
    }


def test_markdown_links_calibration_image():
    rendered = render_markdown(_report(), calibration_image="calibration.png")
    assert "![Calibration reliability diagram](calibration.png)" in rendered
    assert "Consistency is not correctness" in rendered


def test_calibration_plot_is_written(tmp_path):
    output = tmp_path / "calibration.png"
    assert plot_calibration(_report(), output) is True
    assert output.stat().st_size > 0

