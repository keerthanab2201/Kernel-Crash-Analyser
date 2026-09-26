"""Command-line entry point."""

from __future__ import annotations

import json
import os
from pathlib import Path

import click

from .diagnose import diagnose_repeated, load_parsed, make_client, write_diagnoses
from .ingest import ingest_directory, parse_log, write_parsed
from .reliability_eval import evaluate, load_diagnoses, write_report
from .report import render_file, render_markdown


@click.group()
def main() -> None:
    """Analyze Linux kernel logs and measure repeated-diagnosis reliability."""


@main.command("ingest")
@click.argument(
    "log_directory", type=click.Path(exists=True, file_okay=False, path_type=Path)
)
@click.option(
    "--output",
    type=click.Path(path_type=Path),
    default=Path("parsed_logs.json"),
    show_default=True,
)
def ingest_command(log_directory: Path, output: Path) -> None:
    crashes = ingest_directory(log_directory)
    write_parsed(crashes, output)
    click.echo(f"Parsed {len(crashes)} logs into {output}")


@main.command("diagnose")
@click.argument(
    "parsed_json", type=click.Path(exists=True, dir_okay=False, path_type=Path)
)
@click.option(
    "--output",
    type=click.Path(path_type=Path),
    default=Path("diagnoses.json"),
    show_default=True,
)
@click.option("--repeats", type=click.IntRange(1), default=5, show_default=True)
@click.option(
    "--corpus",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    help="Approved versioned documentation corpus for bounded investigation.",
)
@click.option(
    "--model",
    default=lambda: os.getenv("KCA_MODEL", "claude-sonnet-5"),
    show_default="KCA_MODEL or claude-sonnet-5",
)
def diagnose_command(
    parsed_json: Path, output: Path, repeats: int, model: str, corpus: Path | None
) -> None:
    client = make_client()
    records = []
    for crash in load_parsed(parsed_json):
        records.append(
            diagnose_repeated(
                client, crash, model=model, repeats=repeats, corpus=corpus
            )
        )
        write_diagnoses(records, output)
    write_diagnoses(records, output)
    click.echo(f"Wrote {len(records)} repeated-diagnosis records to {output}")


@main.command("evaluate")
@click.argument(
    "diagnoses_json", type=click.Path(exists=True, dir_okay=False, path_type=Path)
)
@click.option("--labels", type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.option(
    "--output",
    type=click.Path(path_type=Path),
    default=Path("reliability_report.json"),
    show_default=True,
)
def evaluate_command(diagnoses_json: Path, labels: Path | None, output: Path) -> None:
    result = evaluate(load_diagnoses(diagnoses_json), labels_path=labels)
    write_report(result, output)
    click.echo(f"Wrote reliability metrics to {output}")


@main.command("report")
@click.argument(
    "report_json", type=click.Path(exists=True, dir_okay=False, path_type=Path)
)
@click.option(
    "--output",
    type=click.Path(path_type=Path),
    default=Path("reports/reliability_report.md"),
    show_default=True,
)
def report_command(report_json: Path, output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    render_file(report_json, output)
    click.echo(f"Rendered {output}")


@main.command("benchmark")
@click.argument("manifest", type=click.Path(exists=True, path_type=Path))
@click.option("--diagnoses", type=click.Path(exists=True, path_type=Path))
@click.option("--retrieval-diagnoses", type=click.Path(exists=True, path_type=Path))
@click.option("--output", default="benchmark.json", type=click.Path(path_type=Path))
def benchmark_command(manifest, diagnoses, retrieval_diagnoses, output):
    """Compare regex, single, repeated, and retrieval predictions on identical incidents."""
    from .benchmark import compare

    methods = {"regex": []}
    if diagnoses:
        records = load_diagnoses(diagnoses)
        methods.update(single_llm=records, repeated_llm=records)
    if retrieval_diagnoses:
        methods["retrieval_llm"] = load_diagnoses(retrieval_diagnoses)
    result = compare(manifest, methods)
    write_report(result, output)
    click.echo(json.dumps(result["methods"], indent=2))


@main.command("analyze")
@click.argument(
    "log_file", type=click.Path(exists=True, dir_okay=False, path_type=Path)
)
@click.option("--repeats", type=click.IntRange(2), default=5, show_default=True)
@click.option(
    "--model",
    default=lambda: os.getenv("KCA_MODEL", "claude-sonnet-5"),
    show_default="KCA_MODEL or claude-sonnet-5",
)
def analyze_command(log_file: Path, repeats: int, model: str) -> None:
    crash = parse_log(
        log_file.read_text(encoding="utf-8", errors="replace"),
        crash_id=log_file.stem,
        source_file=str(log_file),
    )
    record = diagnose_repeated(make_client(), crash, model=model, repeats=repeats)
    # Single-crash mode intentionally omits ICC; ICC requires multiple targets.
    result = evaluate([record])
    from .benchmark import triage

    click.echo(json.dumps(triage(record), indent=2))
    click.echo(render_markdown(result))
    click.echo("\nRaw diagnoses:\n" + json.dumps(record, indent=2))


@main.command("lab-capture")
@click.option("--kernel", required=True, type=click.Path(exists=True, path_type=Path))
@click.option("--config", required=True, type=click.Path(exists=True, path_type=Path))
@click.option("--busybox", required=True, type=click.Path(exists=True, path_type=Path))
@click.option("--module", type=click.Path(exists=True, path_type=Path))
@click.option("--kernel-revision", required=True)
@click.option(
    "--action",
    required=True,
    type=click.Choice(
        ["panic", "null", "overflow", "uaf", "module-uaf", "module-fixed"]
    ),
)
@click.option("--output", required=True, type=click.Path(path_type=Path))
def lab_command(kernel, config, busybox, module, kernel_revision, action, output):
    """Boot a disposable, diskless QEMU guest and capture a deliberate fault."""
    from .lab import capture

    click.echo(
        json.dumps(
            capture(
                kernel,
                config,
                busybox,
                output,
                action,
                kernel_revision=kernel_revision,
                module=module,
            ),
            indent=2,
        )
    )


@main.command("cellular-timeline")
@click.argument(
    "logs",
    nargs=-1,
    required=True,
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
)
@click.option(
    "--output", default="cellular-timeline.json", type=click.Path(path_type=Path)
)
def cellular_command(logs, output):
    """Correlate one lab scenario's cellular log events; no root-cause inference."""
    from .cellular import timeline

    result = timeline(
        {str(path): path.read_text(encoding="utf-8", errors="replace") for path in logs}
    )
    write_report(result, output)
    click.echo(f"Recorded {len(result['events'])} events in {output}")


@main.command("benchmark-report")
@click.argument("benchmark_json", type=click.Path(exists=True, path_type=Path))
@click.option(
    "--output", default="reports/benchmark.md", type=click.Path(path_type=Path)
)
def benchmark_report_command(benchmark_json, output):
    """Render baseline results and a held-out risk–coverage diagram."""
    from .benchmark_report import render_comparison

    render_comparison(json.loads(benchmark_json.read_text(encoding="utf-8")), output)
    click.echo(f"Wrote {output}")


if __name__ == "__main__":
    main()
