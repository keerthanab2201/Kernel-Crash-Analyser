import gzip
import pytest
from src.lab import initramfs, capture


def test_archive_is_deterministic_and_guest_guard_is_present(tmp_path):
    busybox = tmp_path / "busybox"
    busybox.write_bytes(b"placeholder executable")
    first = initramfs(busybox, "panic")
    assert first == initramfs(busybox, "panic")
    archive = gzip.decompress(first)
    assert archive.startswith(b"070701")
    assert b"kca_lab=1" in archive and b"echo PANIC" in archive
    with pytest.raises(ValueError):
        initramfs(busybox, "module-uaf")


def test_capture_failure_keeps_pending_review_provenance(tmp_path):
    input_file = tmp_path / "input"
    input_file.write_bytes(b"fixture")
    output = tmp_path / "run"
    result = capture(
        input_file,
        input_file,
        input_file,
        output,
        "panic",
        kernel_revision="test",
        qemu="nonexistent-kca-qemu-command",
    )
    assert result["ground_truth_status"] == "pending_review"
    assert result["launch_error"] == "FileNotFoundError"
    assert (output / "manifest.json").exists()
    with pytest.raises(FileExistsError):
        capture(
            input_file, input_file, input_file, output, "panic", kernel_revision="test"
        )
