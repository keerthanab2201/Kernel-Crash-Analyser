"""Reliability and calibration metrics for repeated structured diagnoses."""

from __future__ import annotations

import csv
import itertools
import json
import math
from collections import Counter
from functools import lru_cache
from pathlib import Path
from typing import Any, Callable, Iterable

import numpy as np

WELL_DEFINED = {"panic_explicit", "null_pointer_deref", "stack_overflow"}


def category_entropy(categories: Iterable[str]) -> float:
    values = list(categories)
    if not values:
        return math.nan
    counts = np.asarray(list(Counter(values).values()), dtype=float)
    probabilities = counts / counts.sum()
    return float(-(probabilities * np.log2(probabilities)).sum())


def mean_pairwise_cosine(embeddings: np.ndarray) -> float:
    matrix = np.asarray(embeddings, dtype=float)
    if matrix.ndim != 2:
        raise ValueError("embeddings must be a two-dimensional matrix")
    if len(matrix) < 2:
        return math.nan
    norms = np.linalg.norm(matrix, axis=1)
    if np.any(norms == 0):
        raise ValueError("zero-length embedding cannot be cosine-normalized")
    normalized = matrix / norms[:, None]
    values = [
        float(normalized[i] @ normalized[j])
        for i, j in itertools.combinations(range(len(matrix)), 2)
    ]
    return float(np.mean(values))


@lru_cache(maxsize=1)
def _embedding_model() -> Any:
    try:
        from sentence_transformers import SentenceTransformer
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError(
            "sentence-transformers is required for semantic similarity"
        ) from exc
    return SentenceTransformer("all-MiniLM-L6-v2")


def default_embedder(texts: list[str]) -> np.ndarray:
    return np.asarray(_embedding_model().encode(texts, normalize_embeddings=True))


def expected_calibration_error(
    confidences: Iterable[float], correctness: Iterable[bool], *, bins: int = 5
) -> float:
    conf = np.asarray(list(confidences), dtype=float)
    corr = np.asarray(list(correctness), dtype=float)
    if len(conf) == 0 or len(conf) != len(corr):
        return math.nan
    if bins < 1 or np.any((conf < 0) | (conf > 1)):
        raise ValueError("invalid bins or confidence outside [0, 1]")
    # right=True ensures confidence exactly 1.0 belongs to the last bin.
    assignments = np.minimum(
        np.digitize(conf, np.linspace(0, 1, bins + 1)[1:], right=True), bins - 1
    )
    ece = 0.0
    for index in range(bins):
        mask = assignments == index
        if mask.any():
            ece += float(mask.mean()) * abs(
                float(conf[mask].mean()) - float(corr[mask].mean())
            )
    return ece


def calibration_summary(
    confidences: list[float], correctness: list[bool], *, bins: int = 5
) -> dict[str, Any]:
    if not confidences:
        return {"n": 0, "brier_score": None, "ece": None, "bins": []}
    conf = np.asarray(confidences, dtype=float)
    corr = np.asarray(correctness, dtype=float)
    from sklearn.metrics import brier_score_loss

    edges = np.linspace(0, 1, bins + 1)
    assignments = np.minimum(np.digitize(conf, edges[1:], right=True), bins - 1)
    curve = []
    for index in range(bins):
        mask = assignments == index
        if mask.any():
            curve.append(
                {
                    "lower": float(edges[index]),
                    "upper": float(edges[index + 1]),
                    "count": int(mask.sum()),
                    "mean_confidence": float(conf[mask].mean()),
                    "fraction_correct": float(corr[mask].mean()),
                }
            )
    return {
        "n": len(confidences),
        "brier_score": float(brier_score_loss(corr, conf)),
        "ece": expected_calibration_error(conf, corr, bins=bins),
        "bins": curve,
    }


def confidence_icc(records: list[dict[str, Any]]) -> dict[str, Any]:
    """Compute ICC(2,1): absolute agreement, random raters, single rating.

    Only crashes having the same complete run-index set are included. Failed API
    calls are never silently imputed.
    """
    per_crash: dict[str, dict[int, float]] = {}
    for item in records:
        valid = {
            int(run["run_index"]): float(run["confidence"])
            for run in item.get("runs", [])
            if run.get("status") == "ok"
        }
        if valid:
            per_crash[str(item["crash_id"])] = valid
    if not per_crash:
        return {
            "icc2_1": None,
            "n_crashes": 0,
            "n_raters": 0,
            "reason": "no valid ratings",
        }
    requested = {
        int(item.get("requested_repeats", len(item.get("runs", []))))
        for item in records
    }
    if len(requested) != 1:
        return {
            "icc2_1": None,
            "n_crashes": 0,
            "n_raters": 0,
            "reason": "mixed repeat counts",
        }
    common_runs = tuple(range(next(iter(requested))))
    complete = {
        key: value
        for key, value in per_crash.items()
        if tuple(sorted(value)) == common_runs
    }
    if (
        len(complete) < 2
        or len(common_runs) < 2
        or len(complete) * len(common_runs) < 5
    ):
        return {
            "icc2_1": None,
            "n_crashes": len(complete),
            "n_raters": len(common_runs),
            "reason": "ICC requires two crashes, two raters, and at least five observations for Pingouin",
        }
    try:
        import pandas as pd
        import pingouin as pg
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("pingouin and pandas are required for ICC") from exc
    rows = [
        {"crash": crash_id, "run": run, "confidence": values[run]}
        for crash_id, values in complete.items()
        for run in common_runs
    ]
    if len({row["confidence"] for row in rows}) == 1:
        return {
            "icc2_1": None,
            "n_crashes": len(complete),
            "n_raters": len(common_runs),
            "reason": "constant confidence: variance ratio is undefined",
        }
    table = pg.intraclass_corr(
        data=pd.DataFrame(rows),
        targets="crash",
        raters="run",
        ratings="confidence",
        nan_policy="raise",
    )
    # Pingouin <=0.5 names this Shrout-Fleiss form "ICC2"; 0.6 uses
    # McGraw-Wong notation "ICC(A,1)" for the same absolute-agreement,
    # two-way random-effects, single-measure statistic.
    matching = table.loc[table["Type"].isin(("ICC2", "ICC(A,1)"))]
    if matching.empty:
        raise RuntimeError(
            f"Pingouin returned no ICC(2,1)/ICC(A,1) row: {table['Type'].tolist()}"
        )
    row = matching.iloc[0]
    value = float(row["ICC"])
    return {
        "icc2_1": value if math.isfinite(value) else None,
        "n_crashes": len(complete),
        "n_raters": len(common_runs),
        "excluded_incomplete_crashes": len(per_crash) - len(complete),
    }


def _majority(values: list[str]) -> str | None:
    counts = Counter(values)
    top = counts.most_common()
    return None if len(top) > 1 and top[0][1] == top[1][1] else top[0][0]


def _label_map(labels_path: Path | None) -> dict[str, dict[str, str]]:
    if labels_path is None:
        return {}
    with labels_path.open(newline="", encoding="utf-8") as handle:
        return {row["crash_id"]: row for row in csv.DictReader(handle)}


def _worked_examples(
    records: list[dict[str, Any]], per_crash: list[dict[str, Any]], limit: int = 3
) -> list[dict[str, Any]]:
    """Select examples spanning the observed entropy range, not cherry-picked outcomes."""
    eligible = sorted(
        (row for row in per_crash if row.get("valid_runs") and row.get("crash_id")),
        key=lambda row: (row["category_entropy_bits"], str(row["crash_id"])),
    )
    if not eligible:
        return []
    positions = [0]
    if len(eligible) > 2 and limit >= 3:
        positions.append(len(eligible) // 2)
    if len(eligible) > 1 and limit >= 2:
        positions.append(len(eligible) - 1)
    by_id = {str(item["crash_id"]): item for item in records}
    examples = []
    for position in dict.fromkeys(positions):
        metric = eligible[position]
        source = by_id[str(metric["crash_id"])]
        examples.append(
            {
                "crash_id": metric["crash_id"],
                "source_file": source.get("source_file"),
                "log_excerpt": source.get("log_excerpt"),
                "metrics": metric,
                "diagnoses": [
                    run for run in source.get("runs", []) if run.get("status") == "ok"
                ],
            }
        )
    return examples


def evaluate(
    records: list[dict[str, Any]],
    *,
    labels_path: Path | None = None,
    embedder: Callable[[list[str]], np.ndarray] = default_embedder,
    calibration_bins: int = 5,
) -> dict[str, Any]:
    seen = set()
    for item in records:
        if item["crash_id"] in seen:
            raise ValueError("duplicate crash_id in diagnoses")
        seen.add(item["crash_id"])
        runs = item.get("runs", [])
        requested = item.get("requested_repeats", len(runs))
        if {r["run_index"] for r in runs} != set(range(requested)) or len(
            runs
        ) != requested:
            raise ValueError(
                "every requested repeat must have exactly one explicit record"
            )
        for run in runs:
            if run.get("status") not in ("ok", "failed"):
                raise ValueError("unknown run status")
            if run["status"] == "ok":
                confidence = run["confidence"]
                if (
                    isinstance(confidence, bool)
                    or not isinstance(confidence, (int, float))
                    or not math.isfinite(confidence)
                    or not 0 <= confidence <= 1
                ):
                    raise ValueError("confidence must be a finite number in [0,1]")
                from .models import CATEGORIES

                if run["category"] not in CATEGORIES:
                    raise ValueError("unknown diagnosis category")
    labels = _label_map(labels_path)
    per_crash: list[dict[str, Any]] = []
    calibration_conf: list[float] = []
    calibration_correct: list[bool] = []
    calibration_clusters: list[dict] = []
    failed = total = 0
    for item in records:
        runs = item.get("runs", [])
        total += len(runs)
        failed += sum(run.get("status") != "ok" for run in runs)
        valid = [run for run in runs if run.get("status") == "ok"]
        label = labels.get(str(item["crash_id"]), {})
        expected = (
            label.get("crash_type")
            if label.get("ground_truth_status") == "verified"
            else None
        )
        if not valid:
            per_crash.append(
                {
                    "crash_id": item["crash_id"],
                    "valid_runs": 0,
                    "failed_runs": len(runs),
                }
            )
            continue
        categories = [run["category"] for run in valid]
        confidences = [float(run["confidence"]) for run in valid]
        majority = _majority(categories)
        similarity = (
            mean_pairwise_cosine(embedder([run["likely_cause"] for run in valid]))
            if len(valid) > 1
            else math.nan
        )
        correct = majority == expected if expected else None
        result = {
            "crash_id": item["crash_id"],
            "group": label.get("evidence_group") or "unannotated",
            "valid_runs": len(valid),
            "failed_runs": len(runs) - len(valid),
            "majority_category": majority,
            "ground_truth_category": expected,
            "majority_correct": correct,
            "category_entropy_bits": category_entropy(categories),
            "mean_semantic_similarity": (
                similarity if math.isfinite(similarity) else None
            ),
            "mean_confidence": float(np.mean(confidences)),
            "confidence_sd": (
                float(np.std(confidences, ddof=1)) if len(confidences) > 1 else None
            ),
            "icc_scope_note": "ICC is defined across crashes, not per crash.",
        }
        per_crash.append(result)
        if expected:
            calibration_conf.extend(confidences)
            calibration_correct.extend(run["category"] == expected for run in valid)
            calibration_clusters.extend(
                {
                    "bug_family": label.get("bug_family") or item["crash_id"],
                    "brier": (float(run["confidence"]) - (run["category"] == expected))
                    ** 2,
                }
                for run in valid
            )

    groups: dict[str, Any] = {}
    for group_name in ("well_defined", "ambiguous", "unannotated"):
        ids = {row["crash_id"] for row in per_crash if row.get("group") == group_name}
        subset = [item for item in records if item["crash_id"] in ids]
        rows = [row for row in per_crash if row.get("group") == group_name]
        groups[group_name] = {
            "n_crashes": len(rows),
            "mean_entropy_bits": (
                float(np.mean([r["category_entropy_bits"] for r in rows]))
                if rows
                else None
            ),
            "mean_semantic_similarity": (
                float(
                    np.mean(
                        [
                            r["mean_semantic_similarity"]
                            for r in rows
                            if r["mean_semantic_similarity"] is not None
                        ]
                    )
                )
                if any(r.get("mean_semantic_similarity") is not None for r in rows)
                else None
            ),
            "confidence_icc": confidence_icc(subset),
        }
        annotated = [r for r in rows if r["majority_correct"] is not None]
        expected_by_id = {r["crash_id"]: r["ground_truth_category"] for r in annotated}
        predictions = [
            (run, expected_by_id[item["crash_id"]])
            for item in subset
            if item["crash_id"] in expected_by_id
            for run in item["runs"]
            if run["status"] == "ok"
        ]
        groups[group_name]["verified_crashes"] = len(annotated)
        groups[group_name]["majority_accuracy"] = (
            float(np.mean([r["majority_correct"] for r in annotated]))
            if annotated
            else None
        )
        groups[group_name]["calibration"] = calibration_summary(
            [r["confidence"] for r, _ in predictions],
            [r["category"] == truth for r, truth in predictions],
            bins=calibration_bins,
        )
    valid_rows = [row for row in per_crash if row.get("valid_runs")]
    semantic_rows = [
        row["mean_semantic_similarity"]
        for row in valid_rows
        if row.get("mean_semantic_similarity") is not None
    ]
    attempt_rows = [
        attempt
        for item in records
        for run in item.get("runs", [])
        for attempt in run.get("attempts", [])
    ]
    sdk_calls = [
        call for attempt in attempt_rows for call in attempt.get("calls", [attempt])
    ]
    malformed = sum(a["status"] == "malformed" for a in sdk_calls)
    attempt_count = len(sdk_calls)
    verified_rows = [row for row in valid_rows if row["majority_correct"] is not None]
    from .benchmark import cluster_interval

    return {
        "methodology": {
            "entropy_log_base": 2,
            "icc": "ICC(2,1), absolute agreement, random repeat raters, single rating",
            "semantic_model": "sentence-transformers/all-MiniLM-L6-v2",
            "calibration_unit": "individual predictions on verified crashes; repeats are correlated, not independent samples",
            "group_rule": "preannotated evidence_group; missing annotations remain unannotated",
        },
        "n_crashes": len(records),
        "api_calls": total,
        "recorded_api_attempts": attempt_count,
        "diagnosis_attempts": len(attempt_rows),
        "recorded_sdk_requests": sum(len(a.get("calls", [])) for a in attempt_rows),
        "attempt_accounting_complete": all(
            "attempts" in run for item in records for run in item.get("runs", [])
        ),
        "malformed_attempts": malformed,
        "malformed_attempt_rate": malformed / attempt_count if attempt_count else None,
        "malformed_attempt_warning": bool(
            attempt_count and malformed / attempt_count > 0.05
        ),
        "verified_crashes": len(verified_rows),
        "majority_accuracy": (
            float(np.mean([r["majority_correct"] for r in verified_rows]))
            if verified_rows
            else None
        ),
        "failed_calls": failed,
        "failure_rate": (failed / total) if total else None,
        "failure_rate_warning": bool(total and failed / total > 0.05),
        "confidence_icc": confidence_icc(records),
        "aggregate_consistency": {
            "mean_category_entropy_bits": (
                float(np.mean([row["category_entropy_bits"] for row in valid_rows]))
                if valid_rows
                else None
            ),
            "mean_semantic_similarity": (
                float(np.mean(semantic_rows)) if semantic_rows else None
            ),
        },
        "calibration": calibration_summary(
            calibration_conf, calibration_correct, bins=calibration_bins
        ),
        "brier_cluster_ci95": cluster_interval(calibration_clusters, "brier"),
        "groups": groups,
        "per_crash": per_crash,
        "worked_examples": _worked_examples(records, per_crash),
        "small_sample_warning": len(records) < 100,
    }


def load_diagnoses(path: Path) -> list[dict[str, Any]]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_report(report: dict[str, Any], output: Path) -> None:
    output.write_text(
        json.dumps(report, indent=2, allow_nan=False) + "\n", encoding="utf-8"
    )
