# Kernel Crash Analyzer

**Systems debugging in C and Python, with evidence-linked LLM diagnosis and an evaluation framework that separates consistency from correctness.**

Can an LLM explain a Linux kernel failure—and when should an engineer distrust its answer? This research CLI parses crash traces, requests structured diagnoses through the Anthropic API, and compares repeated responses. A disposable QEMU lab supplies controlled faults and a corrected C implementation for investigating memory lifetime errors.

![Tests](https://github.com/keerthanab2201/Kernel-Crash-Analyser/actions/workflows/ci.yml/badge.svg)

**Stack:** Python 3.11+ · C · Linux/KASAN · QEMU · Anthropic tool calling · sentence-transformers · pytest · GitHub Actions

## Start here: engineering evidence

| Area | What to inspect |
| --- | --- |
| Systems debugging | [C use-after-free example and corrected path](lab/kca_demo.c): allocation ownership, last read, and release; [isolated QEMU harness](lab/README.md) with serial captures and input hashes. |
| LLM application engineering | [Diagnosis pipeline](src/diagnose.py): forced structured submission, local validation, retries, evidence-line checks, and request traces. |
| Tool-assisted investigation | [Bounded read-only tools](docs/INVESTIGATION.md): log context, versioned documentation retrieval, and exact-revision symbol lookup support. |
| AI evaluation | [Benchmark design](docs/BENCHMARK.md): regex, single-call, repeated-call, and retrieval-assisted comparisons; bug-family splits and development-only abstention tuning. |
| Responsible handling | [Redaction and trace policy](docs/INVESTIGATION.md): incident-local pseudonyms for recognized identifiers, visible failures, and explicit privacy limitations. |
| Software quality | [Tests](tests) for parsers, statistical edge cases, and mocked SDK requests; [CI](.github/workflows/ci.yml) runs Python tests and compiles the C module without loading it into the host. |

For a short code-and-demo walkthrough, see [DEMO.md](docs/DEMO.md).

## What has actually been demonstrated?

### Controlled Linux experiments

The [QEMU workflow run](https://github.com/keerthanab2201/Kernel-Crash-Analyser/actions/runs/36212488760) captured six guest scenarios using Linux v6.12. Inspection of the downloaded serial logs showed:

| Scenario | Observed result |
| --- | --- |
| C module: read after free | KASAN reported `slab-use-after-free` in `read_value` in `kca_demo`. |
| C module: corrected lifetime | Printed `read completed value=42`; no KASAN finding was observed in this capture. |
| LKDTM explicit panic | Recorded `Kernel panic - not syncing: dumptest`. |
| LKDTM use-after-free | KASAN reported `slab-use-after-free` in `lkdtm_READ_AFTER_FREE`. |
| Intended NULL-fault scenario | Produced a **general protection fault**, not the intended NULL-dereference classification. |
| Intended stack-overflow scenario | Trigger returned `Invalid argument`; this was a **failed experiment**, not a captured stack overflow. |

These are observed lab outcomes, **not LLM accuracy results**. A successful workflow does not prove that every intended fault occurred. Captures require a reviewed ground-truth manifest before inclusion in a correctness benchmark; repeated boots are not independent root causes. Workflow artifacts have limited retention.

### Dataset and model evaluation status

- Five synthetic logs are bundled in [crash_logs](crash_logs) for parser testing—not for accuracy claims.
- A supplied archive contains **24 attributed public-report excerpts across five source-label categories**. It has been imported locally; source authenticity and redistribution terms have not been independently verified. The excerpts are not guaranteed complete console dumps.
- All 24 public excerpts have **unverified causal ground truth**. Report-title/sanitizer labels must not be presented as verified root causes.
- **No live LLM evaluation results are available yet.** Entropy, semantic similarity, ICC, calibration, and benchmark code are implemented, but no measured model accuracy or improvement is claimed.

## How it works

```text
Crash log → parsed evidence → repeated structured diagnoses → evaluation → Markdown report
                                  ↕ optional read-only tools
                            approved documentation corpus
```

Each diagnosis contains a category, proposed cause, confidence, and supporting log lines. Failed calls remain visible rather than being silently removed from evaluation.

| Question | Measurement |
| --- | --- |
| Does the model choose the same category? | Per-crash category entropy. |
| Are its explanations similar? | Mean pairwise sentence-embedding cosine similarity. |
| Are confidence scores stable across repeats? | ICC(2,1) across a complete **set of crashes**, not one crash. |
| Is it correct, and is confidence meaningful? | Verified-category accuracy, Brier score, ECE, and calibration diagrams on the verified subset only. |
| Can it decline uncertain cases? | Development-tuned abstention and held-out risk–coverage analysis. |

Agreement is not correctness. Category correctness is also narrower than verifying a causal explanation. See [methodology and assumptions](docs/METHODOLOGY.md).

## Try it

From the repository root:

```bash
python -m venv .venv
# Activate: .venv\Scripts\Activate.ps1 (PowerShell)
# Or: source .venv/bin/activate (bash)
python -m pip install -e ".[test]"
python -m src.cli ingest crash_logs --output parsed_logs.json
pytest
```

Parsing and tests do not require API credentials. Installation requires dependency downloads.

### Run model diagnosis

Set `ANTHROPIC_API_KEY` in your environment, never in source control. Supply an exact model ID available to your account; live calls incur API charges.

```bash
python -m src.cli diagnose parsed_logs.json --model YOUR_MODEL_ID --repeats 5 --output diagnoses.json
python -m src.cli evaluate diagnoses.json --labels labels.csv --output reliability_report.json
python -m src.cli report reliability_report.json --output reports/reliability_report.md
```

The bundled fixture labels do not establish ground truth for model accuracy. Semantic evaluation downloads `all-MiniLM-L6-v2` on first use. For one new log:

```bash
python -m src.cli analyze path/to/crash.log --model YOUR_MODEL_ID --repeats 5
```

Optional investigation adds `--corpus corpus/kernel-notes.json` to `diagnose`. The bundled retriever uses **TF-IDF over three authored notes**, not a large knowledge base or dense vector search. Its effectiveness has not been measured.


## Further Work

1. **Publish a reproducible, held-out model benchmark.** Freeze incident families, model/prompt/corpus versions, and verified labels; compare against regex and single-call baselines. Report failures, uncertainty, latency, and token usage—even if repeated calls do not improve results.
2. **Finish the controlled-fault evidence package.** Preserve reviewed traces and the faulty/fixed C comparison, repair and rerun the failed overflow trigger, and distinguish intended faults from observed failure modes.
3. **Test evidence quality, not just happy paths.** Compare full traces with masked signatures and removed stack frames using the [perturbation utilities](src/robustness.py). Keep related variants in the same split to prevent leakage.
4. **Complete one narrow cellular experiment.** Capture a controlled registration or session failure and recovery, align events across components, and validate the explanation against the injected condition before claiming wireless diagnostic capability.

## Limitations and data responsibility

This is a small research prototype, not a production or safety-critical diagnostic system. Parsing is heuristic and primarily x86-oriented. One provider is supported; repeated samples are correlated, and embedding similarity can miss important technical differences. Small verified subsets cannot support strong generalization or calibration claims.

Redaction is best effort, not guaranteed anonymization. Use approved lab/public inputs and inspect them before sending logs to an external API. Retain source attribution and review redistribution terms for public reports. A matching citation proves that a line exists—not that it supports the model's causal claim.
