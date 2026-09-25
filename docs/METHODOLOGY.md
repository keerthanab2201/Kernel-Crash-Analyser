# Evaluation contract (v2)

Only `ground_truth_status=verified` labels enter accuracy and calibration.
`crash_type` measures the immediate failure mode, not the causal mechanism.
Synthetic fixtures and inferred public-report titles are excluded. Review causal
explanations separately using a blinded annotation sheet; matching evidence text
establishes citation existence, not causal entailment.

Confidence estimates the correctness of each run's own category. Brier score and
ECE score those predictions against verified categories. Repeats are correlated;
uncertainty must resample entire incidents, not individual model responses.
Consensus confidence is not the mean of confidences for different categories.

ICC uses complete requested repeat sets, never an opportunistically selected
subset of successful indices. Mixed repeat counts return unavailable. Small
datasets and constant scores may not support an interpretable ICC. Repeat slots
are exchangeable sampling positions, not independent human raters.

Groups are independently annotated `evidence_group` values (`well_defined` or
`ambiguous`), with missing annotations reported as `unannotated`. A difference
between groups is a hypothesis, not a required result.

Each SDK request is recorded, including recovered malformed attempts. SDK retries
are disabled so retries cannot disappear inside the client. Exhausted-repeat rate
and malformed-attempt rate have different denominators. API exceptions are stored
by class, avoiding accidental exposure of credentials or request bodies.

Strict schemas use the supported Anthropic JSON Schema subset; numeric confidence
bounds are checked locally. See https://platform.claude.com/docs/en/build-with-claude/structured-outputs .
