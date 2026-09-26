"""Render a compact, conservative Markdown evaluation report."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def _fmt(value: Any, digits: int = 3) -> str:
    return "n/a" if value is None else f"{value:.{digits}f}"


def _consistency_verdict(metrics: dict[str, Any]) -> str:
    if metrics.get("valid_runs", 0) < 2:
        return "Insufficient repeated observations to assess consistency."
    if metrics.get("failed_runs", 0):
        return "Incomplete repeated sampling; successful-run agreement may be biased."
    entropy = metrics.get("category_entropy_bits")
    similarity = metrics.get("mean_semantic_similarity")
    if entropy == 0:
        return "All sampled categories agree. Text similarity is descriptive; correctness requires independent verification."
    return "Sampled categories disagree; inspect competing explanations and supporting lines."


def render_markdown(
    report: dict[str, Any], *, calibration_image: str | None = None
) -> str:
    icc = report["confidence_icc"]
    calibration = report["calibration"]
    aggregate = report["aggregate_consistency"]
    lines = [
        "# Kernel Crash Diagnosis Reliability Report",
        "",
        "> This is an evaluation artifact, not a production kernel diagnostic or security tool.",
        "",
        "## Evaluation summary",
        "",
        f"- Crashes evaluated: **{report['n_crashes']}**",
        f"- Recorded repeats: **{report['api_calls']}**; recorded API attempts: **{report.get('recorded_api_attempts', 'unknown')}**",
        f"- Malformed-attempt rate: **{_fmt(report.get('malformed_attempt_rate'))}**",
        f"- Failed calls: **{report['failed_calls']}** ({_fmt(report['failure_rate'])})",
        f"- Mean category entropy: **{_fmt(aggregate.get('mean_category_entropy_bits'))} bits**",
        f"- Mean semantic similarity: **{_fmt(aggregate.get('mean_semantic_similarity'))}**",
        f"- Confidence ICC(2,1): **{_fmt(icc.get('icc2_1'))}** across {icc.get('n_crashes', 0)} complete crashes",
        f"- Ground-truth calibration samples: **{calibration['n']}**",
        f"- Brier score: **{_fmt(calibration.get('brier_score'))}**; ECE: **{_fmt(calibration.get('ece'))}**",
        "",
    ]
    if report.get("failure_rate_warning"):
        lines += [
            "> **Call reliability warning:** More than 5% of model calls failed validation or exhausted retries.",
            "",
        ]
    if report.get("malformed_attempt_warning"):
        lines += [
            "> **Validation warning:** More than 5% of recorded API attempts returned malformed or ungrounded diagnoses, including recovered retries.",
            "",
        ]
    if report.get("small_sample_warning"):
        lines += [
            "> **Small-sample warning:** Estimates are descriptive and may be unstable; near-perfect values should not be treated as strong evidence.",
            "",
        ]
    if calibration_image and calibration.get("n"):
        lines += [
            "## Calibration diagram",
            "",
            f"![Calibration reliability diagram]({calibration_image})",
            "",
        ]
    if report.get("groups"):
        lines += [
            "## Independently annotated evidence groups",
            "",
            "| Group | Crashes | Verified | Accuracy | Entropy | Similarity | ICC | Brier | ECE |",
            "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
        ]
        for name, group in report["groups"].items():
            cal = group.get("calibration", {})
            lines.append(
                f"| {name} | {group['n_crashes']} | {group.get('verified_crashes', 0)} | {_fmt(group.get('majority_accuracy'))} | {_fmt(group.get('mean_entropy_bits'))} | {_fmt(group.get('mean_semantic_similarity'))} | {_fmt(group['confidence_icc'].get('icc2_1'))} | {_fmt(cal.get('brier_score'))} | {_fmt(cal.get('ece'))} |"
            )
        lines.append("")
    lines += [
        "## Per-crash consistency",
        "",
        "ICC is not a per-crash statistic. Confidence SD is shown per crash; ICC is estimated across crashes above.",
        "",
        "| Crash | Group | Runs | Majority | Correct | Entropy (bits) | Semantic similarity | Mean conf. | Conf. SD |",
        "|---|---|---:|---|---|---:|---:|---:|---:|",
    ]
    for row in report["per_crash"]:
        if not row.get("valid_runs"):
            lines.append(
                f"| {row['crash_id']} | n/a | 0 | n/a | n/a | n/a | n/a | n/a | n/a |"
            )
            continue
        correct = (
            "n/a"
            if row["majority_correct"] is None
            else ("yes" if row["majority_correct"] else "no")
        )
        lines.append(
            f"| {row['crash_id']} | {row['group']} | {row['valid_runs']} | {row['majority_category']} | "
            f"{correct} | {_fmt(row['category_entropy_bits'])} | {_fmt(row['mean_semantic_similarity'])} | "
            f"{_fmt(row['mean_confidence'])} | {_fmt(row['confidence_sd'])} |"
        )
    if report.get("worked_examples"):
        lines += ["", "## Worked examples", ""]
        for example in report["worked_examples"]:
            metrics = example["metrics"]
            lines += [
                f"### {example['crash_id']}",
                "",
                f"**Consistency verdict:** {_consistency_verdict(metrics)}",
                "",
                "Log excerpt:",
                "",
                "```text",
                example.get("log_excerpt")
                or "Log excerpt was not retained in this input artifact.",
                "```",
                "",
                "Repeated structured diagnoses:",
                "",
            ]
            for diagnosis in example["diagnoses"]:
                evidence = (
                    "; ".join(diagnosis.get("supporting_evidence", []))
                    or "none recorded"
                )
                lines.append(
                    f"- Run {diagnosis.get('run_index')}: `{diagnosis.get('category')}` at "
                    f"{_fmt(diagnosis.get('confidence'))} — {diagnosis.get('likely_cause')} "
                    f"Evidence: {evidence}"
                )
    lines += [
        "",
        "## Interpretation limits",
        "",
        "- Consistency is not correctness: repeated agreement can reinforce the same wrong diagnosis.",
        "- Calibration scores individual predictions on verified crashes; repeats are correlated and are not independent sample units.",
        "- The well-defined/ambiguous split is a declared heuristic, not a discovered taxonomy.",
        "- Semantic similarity depends on a general-purpose embedding model and may miss kernel-specific distinctions.",
        "- Results apply only to the recorded model/version, prompt, logs, and repeat count.",
        "",
    ]
    return "\n".join(lines)


def plot_calibration(report: dict[str, Any], output_path: Path) -> bool:
    bins = report.get("calibration", {}).get("bins", [])
    if not bins:
        return False
    import matplotlib.pyplot as plt

    confidence = [item["mean_confidence"] for item in bins]
    accuracy = [item["fraction_correct"] for item in bins]
    counts = [item["count"] for item in bins]
    fig, axis = plt.subplots(figsize=(5.5, 4.5))
    axis.plot([0, 1], [0, 1], linestyle="--", color="0.5", label="perfect calibration")
    axis.plot(confidence, accuracy, marker="o", label="observed")
    for x, y, count in zip(confidence, accuracy, counts, strict=True):
        axis.annotate(f"n={count}", (x, y), xytext=(5, 5), textcoords="offset points")
    axis.set(
        xlim=(0, 1), ylim=(0, 1), xlabel="Mean confidence", ylabel="Fraction correct"
    )
    axis.set_title("Individual-diagnosis calibration")
    axis.grid(alpha=0.2)
    axis.legend()
    fig.tight_layout()
    fig.savefig(output_path, dpi=150)
    plt.close(fig)
    return True


def render_file(input_path: Path, output_path: Path) -> None:
    report = json.loads(input_path.read_text(encoding="utf-8"))
    image_path = output_path.with_name("calibration.png")
    has_plot = plot_calibration(report, image_path)
    output_path.write_text(
        render_markdown(
            report, calibration_image=image_path.name if has_plot else None
        ),
        encoding="utf-8",
    )
