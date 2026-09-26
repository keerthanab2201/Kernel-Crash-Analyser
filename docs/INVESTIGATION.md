# Bounded investigation and privacy

```
python -m src.cli diagnose parsed_logs.json --corpus corpus/kernel-notes.json --output retrieval.json
```

The optional corpus enables up to three read-only tool rounds before a forced
submission. Tools provide numbered log context, TF-IDF documentation retrieval,
and exact-revision symbol lookup. TF-IDF is an explicit lexical baseline, not
embedding/vector-search marketing. The bundled corpus contains three authored
summaries, not a complete kernel manual; it has no exact-revision symbol entries.
Expand it with reviewed versioned documentation before judging retrieval efficacy.

Every tool input, bounded result, SDK usage object, request latency, response ID,
and corpus hash is retained in the run trace. Whole incident checkpoints are saved
after each crash. The model cannot execute commands or request arbitrary files.
Citation line IDs are resolved locally from verbatim lines. Existence checking
does not establish semantic support or causality.

Corpora must identify documents as documentation with unique IDs, revisions and
source URLs. Incident fixes are prohibited in this benchmark mode. This metadata
check cannot detect deliberately mislabeled content: review the corpus manually
for duplicate test incidents and hidden answer leakage before freezing its hash.

Logs are redacted before the prompt and excerpt are constructed. HMAC pseudonyms
preserve repeated IPv4 addresses, MAC addresses, email addresses, and named
subscriber/credential fields within one incident. Keys are ephemeral and are not
saved. Kernel pointer values are retained for debugging. This is best effort:
unlabeled identifiers, IPv6, free-text names and novel log formats need additional
rules and review. Use approved lab/public logs only; do not assume sensitive
production captures have been anonymized. Retrieval corpora must also be reviewed
before use. Avoid secrets in crash IDs or filenames.
