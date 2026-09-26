# Reproducible comparison

Create a JSON manifest containing a list of incident objects:

```json
{
  "crash_id": "incident-001",
  "log_path": "logs/incident-001.log",
  "bug_family": "injected-uaf-v1",
  "split": "dev",
  "ground_truth_status": "verified",
  "category": "use_after_free",
  "verification_evidence": "lab run manifest + reviewed serial trace",
  "evidence_group": "well_defined"
}
```

Paths are relative to the manifest. Every variant of one bug belongs to one split.
Use `dev` for threshold selection and `test` only for the final evaluation. A
verified label requires a reviewable verification artifact, not a filename guess.
Do not promote the bundled parser fixtures to verified incidents.

```
python -m src.cli benchmark dataset/manifest.json --diagnoses diagnoses.json --retrieval-diagnoses retrieval.json --output benchmark.json
python -m src.cli benchmark-report benchmark.json --output reports/benchmark.md
```

All methods use identical verified test incidents. Missing predictions count as
incorrect for overall accuracy and cannot be accepted by the abstention policy.
The single-call baseline uses repeat zero, including its failure if any; it does
not choose the first successful repeat. Repeated-call ranking uses vote share of
requested repeats, with ties and incomplete repeats excluded from acceptance.
This ranking score is not a probability. Regex has no calibrated confidence.

The policy selects the largest development coverage satisfying an empirical risk
target, or abstains on everything if no threshold qualifies. Test risk-coverage
curves are descriptive; never use them to choose the deployed threshold. Accuracy
and Brier intervals bootstrap entire bug families with a fixed RNG seed. More
repeats do not increase the number of independent incidents.

Report category accuracy separately from manually reviewed causal claims. Review
the explanation without method labels, record `supported`, `unsupported`, or
`insufficient_evidence`, and keep disagreements. Verbatim citations alone cannot
establish that a causal explanation is true.

## Evidence sensitivity

```
python -m src.cli perturb dataset/logs/incident-001.log --mode remove-signatures --output dataset/views/incident-001-masked.log
```

Other modes remove stack frames or append a labeled instruction-injection payload.
Hashes and line counts are stored beside each view. Retain the parent's bug family
and split, and do not count these as newly collected root causes. Check residual
leakage manually: function names and trigger text may still disclose the mechanism.
Compare accuracy, confidence, unsupported causal claims and abstention across
views; corruption should not silently change the ground-truth mechanism.
