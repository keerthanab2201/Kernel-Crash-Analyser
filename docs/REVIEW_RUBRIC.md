# Blinded causal-explanation review

Category accuracy answers which failure mode is observed. Root-cause quality
requires a separate review of the explanation against reproducer, fix, source and
trace evidence. Keep those labels separate in reports and resume claims.

Export one record per crash/run with randomized review IDs and omit method/model
labels. Have a reviewer record:

- `category_correct`: match to the independently verified failure-mode label.
- `evidence_exists`: every cited line exists in the redacted input.
- `evidence_support`: supported / contradicted / insufficient.
- `cause_support`: supported / contradicted / insufficient.
- `unsupported_claims`: list of specific unsupported statements, not a severity guess.
- `reviewer_id`, `verification_artifact`, and explanatory notes.

Review disagreements before publishing final labels, and preserve the original
annotations. If only one reviewer is available, state that limitation. Citation
existence is automatic; support and causal correctness remain manual in this
version. Do not use the diagnosing model as its own sole correctness judge.

For an honest demo choose: one verified success, one confident verified mistake,
and one example that abstains after critical evidence is removed. If no mistake
was observed in the collected sample, report that fact instead of inventing one.
