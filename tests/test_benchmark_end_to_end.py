import json
from click.testing import CliRunner
from src.cli import main


def test_comparison_and_report_exclude_unverified_incidents(tmp_path):
    (tmp_path / "a.log").write_text("Kernel panic - not syncing: controlled test")
    (tmp_path / "b.log").write_text(
        "BUG: unable to handle kernel NULL pointer dereference"
    )
    manifest = [
        {
            "crash_id": "a",
            "bug_family": "panic",
            "split": "dev",
            "ground_truth_status": "verified",
            "category": "panic_explicit",
            "verification_evidence": "unit-test label only",
            "log_path": "a.log",
        },
        {
            "crash_id": "b",
            "bug_family": "null",
            "split": "test",
            "ground_truth_status": "verified",
            "category": "null_pointer_deref",
            "verification_evidence": "unit-test label only",
            "log_path": "b.log",
        },
        {
            "crash_id": "c",
            "bug_family": "unused",
            "split": "test",
            "ground_truth_status": "fixture_only",
        },
    ]
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(manifest))
    output = tmp_path / "result.json"
    runner = CliRunner()
    result = runner.invoke(main, ["benchmark", str(path), "--output", str(output)])
    assert result.exit_code == 0, result.output
    data = json.loads(output.read_text())
    assert data["n_verified_incidents"] == 2
    assert data["methods"]["regex"]["n_test"] == 1
    report = tmp_path / "report.md"
    result = runner.invoke(
        main, ["benchmark-report", str(output), "--output", str(report)]
    )
    assert result.exit_code == 0, result.output
    assert report.with_suffix(".png").exists()
