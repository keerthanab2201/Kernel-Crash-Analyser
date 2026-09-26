"""Render comparison results without manufacturing observations."""

from pathlib import Path
from .report import _fmt


def render_comparison(result: dict, output: Path) -> None:
    import matplotlib.pyplot as plt

    output.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Baseline and abstention comparison",
        "",
        f"Verified incidents in manifest: {result['n_verified_incidents']}",
        "",
        "Accuracy below includes missing predictions as incorrect. Coverage and selective accuracy apply the development-fitted policy.",
        "",
        "| Method | Test incidents | Accuracy | 95% family-bootstrap interval | Coverage | Selective accuracy |",
        "|---|---:|---:|---|---:|---:|",
    ]
    fig, axis = plt.subplots(figsize=(6, 4))
    plotted = False
    for name, method in result["methods"].items():
        interval = method["accuracy_ci95"]
        interval_text = (
            "unavailable"
            if interval is None
            else f"[{interval[0]:.3f}, {interval[1]:.3f}]"
        )
        lines.append(
            f"| {name} | {method['n_test']} | {_fmt(method['accuracy'])} | {interval_text} | {_fmt(method['coverage'])} | {_fmt(method['selective_accuracy'])} |"
        )
        points = [p for p in method["test_risk_coverage"] if p["risk"] is not None]
        if points:
            axis.plot(
                [p["coverage"] for p in points],
                [p["risk"] for p in points],
                marker="o",
                label=name,
            )
            plotted = True
    if plotted:
        axis.set(
            xlim=(0, 1),
            ylim=(0, 1),
            xlabel="Coverage (fraction of test incidents answered)",
            ylabel="Risk (error among answered incidents)",
            title="Held-out risk–coverage (descriptive)",
        )
        axis.legend()
        axis.grid(alpha=0.2)
        fig.tight_layout()
        image = output.with_suffix(".png")
        fig.savefig(image, dpi=150)
        lines += ["", f"![Risk coverage]({image.name})", ""]
    plt.close(fig)
    lines += [
        "",
        result["limits"],
        "",
        "Thresholds are chosen on development incidents only. Test curves must not be used to retune the policy.",
        "",
    ]
    output.write_text("\n".join(lines), encoding="utf-8")
