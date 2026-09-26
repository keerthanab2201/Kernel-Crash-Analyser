# LLM-Assisted Kernel Crash/Log Root-Cause Analyzer

A research-oriented Python CLI that parses Linux kernel panic/oops text, asks an
Anthropic model for a strict tool-call diagnosis multiple times, and measures
whether those repeated diagnoses agree. It keeps self-consistency separate from
correctness: agreement, by itself, does not prove that a diagnosis is right.

This repository contains five **synthetic parser fixtures**, a controlled QEMU fault
lab, and a benchmark that compares regex, single-call, repeated-call, and optional
retrieval-assisted diagnoses. Live model results are not available yet. Controlled
captures remain pending review until their observed traces match the injected fault.

![Tests](https://github.com/keerthanab2201/Kernel-Crash-Analyser/actions/workflows/ci.yml/badge.svg)

## Engineering walkthrough

1. [C lifetime bug and corrected path](lab/kca_demo.c): allocation, last consumer,
   and ownership release, compiled in CI without loading the host module.
2. [Disposable QEMU lab](lab/README.md): deterministic initramfs and captured serial
   logs with kernel/config hashes. A manual GitHub workflow runs the experiments.
3. [Evaluation contract](docs/METHODOLOGY.md): verified-label gating, complete-repeat
   ICC, per-prediction calibration, and visible recovered failures.
4. [Benchmark](docs/BENCHMARK.md): grouped development/test split, common incident
   denominator, baseline comparisons, and development-tuned abstention.
5. [Evidence tools](docs/INVESTIGATION.md): bounded local retrieval, exact-revision
   lookup, citation checks, request traces, and best-effort log redaction.
6. [Cellular study](docs/CELLULAR_STUDY.md): a separate event-timeline adapter and
   proposed controlled registration/session experiments. No cellular accuracy claim.

## What is implemented

- Regex ingestion for common x86 panic, NULL dereference, KASAN use-after-free,
  stack-overflow, general-protection-fault, and lockup signatures.
- Forced `submit_diagnosis` Anthropic tool calls, independent response validation,
  exponential retry, and explicit failed-call records.
- Category entropy (bits), mean pairwise embedding cosine similarity, confidence
  ICC(2,1), majority-vote accuracy, Brier score, and binned ECE.
- Markdown reporting with failure-rate and small-sample warnings.
- A calibration reliability diagram when labeled examples are available.
- Bug-family bootstrap intervals, development-only abstention tuning, and risk–coverage curves in benchmark JSON.
- Three bounded read-only investigation tools backed by a versioned documentation corpus.
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
  measurement. Crashes are targets and repeat indices are raters. Only complete
  requested repeat sets enter ICC; mixed repeat counts return unavailable.
- **Calibration:** each prediction's confidence is scored against the correctness
  of that prediction's category, on verified incidents only. Repeats are correlated;
  Brier uncertainty resamples whole bug families. Consensus vote share is a ranking
  score, not an estimated probability of correctness. Tied votes have no winner.

The optional `evidence_group` annotation is assigned before looking at predictions.
Missing values remain `unannotated`. A difference between evidence groups is a
hypothesis to test, not an expected result to manufacture.

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

Every repeat retains its attempts, including recovered validation failures. Tool
rounds retain SDK request counts, usage, latency, and response IDs. Evaluation
separately reports exhausted-repeat and malformed-attempt rates and warns above
5%. SDK retries are disabled. Authentication/configuration errors fail immediately.
Exact line matching checks citation existence, not whether it proves a causal claim.

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

## Current verification and remaining experiments

Python unit and regression tests run on every push. CI also compiles the C module
against Linux headers. The manual `controlled-fault-lab` workflow builds Linux v6.12
with KASAN/LKDTM and captures six guest scenarios as downloadable artifacts.
Compilation and mock API tests do not verify live provider behavior. A live run
needs `ANTHROPIC_API_KEY` and the Anthropic SDK installed.

The retrieval baseline uses TF-IDF over three authored documentation notes; it is
not a complete knowledge base or a dense embedding retriever. Semantic similarity
still uses sentence-transformers. Ground-truth root-cause explanations require
manual review in addition to category labels. The 40-incident study, a measured
LLM improvement over regex, and a working 5G lab remain experimental work.

## Resume bullets (use only after the corresponding work is verified)

Do not add sample counts, accuracy, or reliability claims until the corresponding
artifacts are committed and reproducible. Once completed, describe the actual tool,
the verified/public split, and the observed consistency-versus-correctness result;
retain the small-sample and single-provider caveats.
