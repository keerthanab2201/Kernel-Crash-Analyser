"""Incident-level evaluation, baselines, and development-only abstention tuning."""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from pathlib import Path

import numpy as np

from .ingest import parse_log
from .models import CATEGORIES


def load_manifest(path: Path) -> list[dict]:
    rows = json.loads(path.read_text(encoding="utf-8"))
    ids, families = set(), {}
    for row in rows:
        key = row["crash_id"]
        if key in ids:
            raise ValueError(f"duplicate crash_id: {key}")
        ids.add(key)
        if row["split"] not in ("dev", "test"):
            raise ValueError("split must be dev or test")
        family = row["bug_family"]
        if not family or families.setdefault(family, row["split"]) != row["split"]:
            raise ValueError("bug family crosses development/test boundary")
        if row.get("ground_truth_status") == "verified":
            if row.get("category") not in CATEGORIES or not row.get(
                "verification_evidence"
            ):
                raise ValueError(
                    "verified labels require category and verification_evidence"
                )
    return rows


def regex_baseline(text: str) -> dict:
    parsed = parse_log(text)
    return {
        "category": parsed.crash_type_guess,
        "confidence": None,
        "evidence": parsed.key_lines,
        "method": "regex",
    }


def consensus(record: dict, *, single: bool = False) -> dict:
    all_runs = record.get("runs", [])
    runs = [r for r in all_runs if r.get("run_index") == 0] if single else all_runs
    valid = [r for r in runs if r.get("status") == "ok"]
    requested = 1 if single else record.get("requested_repeats", len(runs))
    if not valid:
        return {"category": None, "score": 0.0, "eligible": False}
    counts = Counter(r["category"] for r in valid)
    top = counts.most_common()
    tied = len(top) > 1 and top[0][1] == top[1][1]
    category, votes = top[0]
    # Vote share is a ranking statistic, not a calibrated probability.
    score = valid[0]["confidence"] if single else votes / max(requested, 1)
    eligible = (
        not tied
        and len(valid) == requested
        and category != "unknown_other"
        and all(r.get("supporting_evidence") for r in valid)
    )
    return {
        "category": None if tied else category,
        "score": score,
        "eligible": eligible,
    }


def triage(record: dict, threshold: float | None = None) -> dict:
    prediction = consensus(record)
    if not prediction["eligible"]:
        verdict = "insufficient_evidence"
    elif threshold is None or prediction["score"] < threshold:
        verdict = "tentative_hypothesis"
    else:
        verdict = "accepted_for_expert_review"
    return {
        **prediction,
        "verdict": verdict,
        "note": "Acceptance uses an empirical development policy; it does not establish a root cause.",
    }


def risk_coverage(rows: list[dict]) -> list[dict]:
    """Threshold whole tied score groups; never break ties by correctness."""
    curve = [{"threshold": None, "coverage": 0.0, "risk": None, "accepted": 0}]
    for threshold in sorted({r["score"] for r in rows if r["eligible"]}, reverse=True):
        accepted = [r for r in rows if r["eligible"] and r["score"] >= threshold]
        curve.append(
            {
                "threshold": threshold,
                "coverage": len(accepted) / len(rows),
                "risk": float(np.mean([not r["correct"] for r in accepted])),
                "accepted": len(accepted),
            }
        )
    return curve


def fit_threshold(rows: list[dict], max_dev_risk: float = 0.1) -> dict:
    if not 0 <= max_dev_risk <= 1:
        raise ValueError("max_dev_risk must be within [0,1]")
    if any(r["split"] != "dev" for r in rows):
        raise ValueError("threshold fitting accepts development incidents only")
    candidates = [
        r
        for r in risk_coverage(rows)
        if r["risk"] is not None and r["risk"] <= max_dev_risk
    ]
    best = (
        max(candidates, key=lambda r: r["coverage"])
        if candidates
        else {"threshold": None, "coverage": 0.0, "risk": None}
    )
    return {
        **best,
        "max_dev_risk": max_dev_risk,
        "n_dev": len(rows),
        "note": "empirical development threshold; no guarantee of future risk",
    }


def cluster_interval(
    rows: list[dict], field: str, *, seed: int = 7, samples: int = 1000
) -> list[float] | None:
    """Bootstrap bug families; all observations from a family move together."""
    groups = {}
    for row in rows:
        groups.setdefault(row["bug_family"], []).append(float(row[field]))
    if len(groups) < 2:
        return None
    arrays = list(groups.values())
    rng = np.random.default_rng(seed)
    values = [
        np.mean(
            [
                x
                for index in rng.integers(0, len(arrays), len(arrays))
                for x in arrays[index]
            ]
        )
        for _ in range(samples)
    ]
    return np.quantile(values, [0.025, 0.975]).tolist()


def compare(
    manifest_path: Path, methods: dict[str, list[dict]], *, max_dev_risk: float = 0.1
) -> dict:
    manifest = load_manifest(manifest_path)
    verified = [r for r in manifest if r.get("ground_truth_status") == "verified"]
    result = {
        "schema_version": 1,
        "manifest_sha256": hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
        "n_verified_incidents": len(verified),
        "methods": {},
        "limits": "Category accuracy is not causal correctness. Bootstrap units are bug families. Small-sample intervals remain unstable.",
    }
    for name, records in methods.items():
        by_id = {r["crash_id"]: r for r in records}
        if len(by_id) != len(records):
            raise ValueError("duplicate diagnosis crash_id")
        rows = []
        for incident in verified:
            if name == "regex":
                log_path = manifest_path.parent / incident["log_path"]
                prediction = regex_baseline(log_path.read_text(encoding="utf-8"))
                prediction = {
                    "category": prediction["category"],
                    "score": 1.0,
                    "eligible": prediction["category"] != "unknown_other",
                }
            else:
                prediction = consensus(
                    by_id.get(incident["crash_id"], {"runs": []}),
                    single=name == "single_llm",
                )
            rows.append(
                {
                    **prediction,
                    "crash_id": incident["crash_id"],
                    "bug_family": incident["bug_family"],
                    "split": incident["split"],
                    "correct": prediction["category"] == incident["category"],
                }
            )
        dev = [r for r in rows if r["split"] == "dev"]
        test = [r for r in rows if r["split"] == "test"]
        policy = fit_threshold(dev, max_dev_risk)
        accepted = [
            r
            for r in test
            if r["eligible"]
            and policy["threshold"] is not None
            and r["score"] >= policy["threshold"]
        ]
        calls = [
            call
            for record in records
            for run in record.get("runs", [])
            if name != "single_llm" or run.get("run_index") == 0
            for attempt in run.get("attempts", [])
            for call in attempt.get("calls", [])
        ]
        latencies = [c["latency_seconds"] for c in calls if "latency_seconds" in c]
        result["methods"][name] = {
            "recorded_sdk_requests": len(calls),
            "total_input_tokens": sum(
                (c.get("usage") or {}).get("input_tokens", 0) for c in calls
            ),
            "total_output_tokens": sum(
                (c.get("usage") or {}).get("output_tokens", 0) for c in calls
            ),
            "mean_request_latency_seconds": (
                float(np.mean(latencies)) if latencies else None
            ),
            "telemetry_note": "Totals describe the supplied artifacts, not a priced estimate; single_llm includes only run zero. Missing usage is unavailable, not proof of zero cost.",
            "n_test": len(test),
            "accuracy": float(np.mean([r["correct"] for r in test])) if test else None,
            "accuracy_ci95": cluster_interval(test, "correct"),
            "policy": policy,
            "coverage": len(accepted) / len(test) if test else None,
            "selective_accuracy": (
                float(np.mean([r["correct"] for r in accepted])) if accepted else None
            ),
            "test_risk_coverage": risk_coverage(test),
            "incidents": rows,
        }
    return result
