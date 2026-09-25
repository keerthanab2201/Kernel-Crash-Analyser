# LLM-Assisted Kernel Crash/Log Root-Cause Analyzer

A research-oriented Python CLI that parses Linux kernel panic/oops text, asks an
Anthropic model for a strict tool-call diagnosis multiple times, and measures
whether those repeated diagnoses agree. It keeps self-consistency separate from
correctness: agreement, by itself, does not prove that a diagnosis is right.

This repository currently contains the implementation and five **synthetic parser
fixtures**. It does not yet contain the proposed 40-log study or any genuine model
evaluation results. The placeholder report therefore makes no performance claims.

## What is implemented

- Regex ingestion for common x86 panic, NULL dereference, KASAN use-after-free,
  stack-overflow, general-protection-fault, and lockup signatures.
- Forced `submit_diagnosis` Anthropic tool calls, independent response validation,
  exponential retry, and explicit failed-call records.
- Category entropy (bits), mean pairwise embedding cosine similarity, confidence
  ICC(2,1), majority-vote accuracy, Brier score, and binned ECE.
- Markdown reporting with failure-rate and small-sample warnings.
- A calibration reliability diagram when labeled examples are available.
- A batch pipeline and a single-log `analyze` command.
- Unit tests for parsing and hand-computed statistical cases.

## Setup

Python 3.11+ is required. The semantic model is downloaded by
`sentence-transformers` on first evaluation, so that step needs network access.

```bash
python -m venv .venv
# PowerShell: .venv\Scripts\Activate.ps1
python -m pip install -e ".[test]"
```

Set `ANTHROPIC_API_KEY` in the environment. Optionally set `KCA_MODEL`; the current
default is `claude-sonnet-5`. Pin and record the exact model identifier used for a
real evaluation because model changes invalidate direct comparisons.

## Run the pipeline

```bash
kernel-crash-analyzer ingest crash_logs --output parsed_logs.json
kernel-crash-analyzer diagnose parsed_logs.json --repeats 5 --output diagnoses.json
kernel-crash-analyzer evaluate diagnoses.json --labels labels.csv --output reliability_report.json
kernel-crash-analyzer report reliability_report.json --output reports/reliability_report.md
```

For one log:

```bash
kernel-crash-analyzer analyze path/to/crash.log --repeats 5
```

The one-log result does not include ICC: ICC requires multiple crashes as targets.

## Evaluation definitions

- **Entropy:** Shannon entropy in bits over repeated category labels. Zero means all
  valid runs chose the same category.
- **Semantic similarity:** mean cosine similarity over all pairs of `likely_cause`
  embeddings from `all-MiniLM-L6-v2`.
- **Confidence ICC:** ICC(2,1), absolute agreement, two-way random-effects, single
  measurement. Crashes are targets and repeat indices are raters. Only the largest
  group with a common complete run-index set is used; missing calls are not imputed.
- **Calibration:** one observation per labeled crash. The predicted class is the
  deterministic majority category and its confidence is the mean confidence over
  valid repeats. Brier score and ECE therefore assess the majority diagnosis, not
  individual calls.

The `well_defined` group is declared in advance as explicit panic, NULL dereference,
or stack overflow. All other enum categories are grouped as `ambiguous`. This is an
analysis heuristic, not a learned or universally valid kernel taxonomy.

## Dataset protocol and attribution

The included logs are synthetic fixtures only. Before claiming a real sample size:

1. Collect distinct public reports and record the report URL, acquisition date,
   source label, and any reproduction/fix evidence.
2. Avoid treating a syzbot title as exact causal ground truth. A sanitizer signature
   is evidence of failure mode, while a verified reproducer/fix can support a cause.
3. For QEMU cases, retain the kernel commit/config, module source, trigger command,
   and raw serial output. Mark a label verified only when the injected mechanism and
   observed trace match.
4. Review data-source terms before redistributing copied reports. Syzkaller source
   code is Apache-2.0, but linked mailing-list content and crash artifacts need their
   own provenance review. Keeping source URLs is the conservative default.

Syzbot documentation explains that reports may include raw console logs, symbolized
reports, configs, and reproducers, and that reproduction can depend on the exact
kernel/toolchain environment. See the [syzbot documentation](https://github.com/google/syzkaller/blob/master/docs/syzbot.md)
and [crash reproduction guide](https://github.com/google/syzkaller/blob/master/docs/reproducing_crashes.md).

## Failure handling

Every requested repeat becomes either an `ok` record or a `failed` record with the
attempt errors. Evaluation never silently filters the denominator: it reports the
failure rate and emits a warning above 5%. Malformed tool input is treated as a
failed attempt even though tool use is forced by the API request.

## Limitations

- Text parsing is heuristic and currently oriented to representative x86 logs.
- The fixtures are not an evaluation corpus and are not evidence of accuracy.
- Ground truth will exist only for a subset unless controlled QEMU experiments are
  completed; calibration on a tiny subset is descriptive and unstable.
- Only one provider/prompt/model configuration is supported.
- General-purpose sentence embeddings may hide important systems-level differences.
- Repeated samples from one model are not independent human raters. ICC is reused as
  a stability summary and must not be overinterpreted.
- This tool neither finds kernel vulnerabilities nor replaces expert debugging.

## Testing

```bash
pytest
```

The tests emphasize parser precedence and statistics with hand-computed expected
values. Network/API calls are deliberately excluded from CI.

## Resume bullets (use only after a real run)

Do not add sample counts, accuracy, or reliability claims until the corresponding
artifacts are committed and reproducible. Once completed, describe the actual tool,
the verified/public split, and the observed consistency-versus-correctness result;
retain the small-sample and single-provider caveats.
