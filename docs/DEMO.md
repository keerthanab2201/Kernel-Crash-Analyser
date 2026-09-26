# Two-minute walkthrough

The demo should establish what was implemented, how it was checked, and what
remains unmeasured. It is not a substitute for a held-out model evaluation.

1. Show `lab/kca_demo.c`: the buggy branch releases an allocation before its last
   read; the corrected branch reads while ownership is still valid. Open the CI
   job that compiles the module without loading it into the runner kernel.
2. Show one reviewed QEMU serial capture and its input hashes. Explain the observed
   violation, then show the fixed-path control. If captures are still pending,
   show the workflow status and say so explicitly.
3. Run `python -m src.cli ingest crash_logs --output parsed_logs.json` to show
   the parser on the five labeled synthetic fixtures. These are parser examples,
   not a performance evaluation.
4. Show the real SDK/mock-transport test: the request forces structured submission,
   sensitive fields are redacted, and evidence is checked against supplied lines.
5. Show the benchmark contract: same held-out incidents for regex and model
   methods, grouping by bug family, and a threshold fitted only on development
   data. With live predictions, run `benchmark` followed by `benchmark-report`.
6. Show one disagreement or abstention and explain what evidence would be needed
   next. Until a model run exists, describe the behavior as tested policy logic,
   not an observed model finding.

For interview preparation, be ready to explain allocation lifetime, why a KASAN
signature is not a complete causal explanation, why repeated model samples are
correlated, how labels can leak through function names, and why a high agreement
score can accompany a wrong diagnosis. Keep the publication citation separate
until its exact methodology has been mapped to the implemented estimands.
