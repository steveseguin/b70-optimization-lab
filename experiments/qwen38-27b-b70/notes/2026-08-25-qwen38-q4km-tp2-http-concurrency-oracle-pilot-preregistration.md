# Qwen3.8 Q4_K_M TP2 HTTP concurrency oracle pilot preregistration

Status: **preregistered; not run; pilot values are non-publishable**.

The TP2 output-audited concurrency ladder requires a frozen sequential oracle
for every one of its 64 expanded prompts. This one fresh-server pilot creates
those complete 128-token sequences with prompt caching disabled. The harness
also executes its concurrency points because that is how the current frozen
harness expands all 64 prompts, but those pilot rates are explicitly excluded
from publication.

The pilot passes only if all 64 sequential responses return complete raw token
IDs and report zero cached prompt tokens. On pass, only compact prompt and
token-ID digests are retained as the oracle. A separately committed R2
preregistration must then name the oracle hash and require two new servers,
output isolation, complete response counts, cache zero, and pointwise
stability before any aggregate curve is published.

See the [machine-readable contract](../data/2026-08-25-qwen38-q4km-tp2-http-concurrency-oracle-pilot-prereg.json).
