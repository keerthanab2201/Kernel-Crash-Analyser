from src.robustness import perturb


def test_degraded_views_are_deterministic_and_hash_parent():
    raw = "BUG: KASAN: use-after-free\n worker+0x10/0x20\nCPU: 0\n"
    result, metadata = perturb(raw, "remove-signatures")
    assert "KASAN" not in result
    assert "worker" in result
    assert (result, metadata) == perturb(raw, "remove-signatures")
    assert metadata["source_sha256"] != metadata["view_sha256"]


def test_empty_evidence_and_injection_are_explicit():
    result, _ = perturb("Kernel panic", "remove-signatures")
    assert "All supplied evidence removed" in result
    result, _ = perturb("CPU: 0", "instruction-injection")
    assert result.startswith("CPU: 0") and "USER_LOG_PAYLOAD" in result
