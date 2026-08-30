# Qwen3.8-27B Q4_K TP2 current control oracle r2 — c64 exactness failed

The WDC-off, scoped-Q4_K-reorder control was deterministic on the fixed diverse
single-user suite: the second fresh server matched all 12 first-server output
hashes and both attempts reported zero cached prompt tokens.

The c64 control did not satisfy the stronger preregistered gate. Its internally
generated 64-row sequential token oracle matched only **38/64** requests when
the same prompts ran concurrently. All responses were complete, cache-zero,
and collision-free, so the generic harness labeled it an output-isolation
qualified shape variant. That weaker classification is not sufficient for this
campaign. The campaign was stopped before the second c64 server and before any
WDC candidate.

The runner now requires `oracle_exact_all`, not merely complete isolated token
streams. A separate control-only diagnostic tests the same binary with scoped
Q4_K reorder disabled to determine whether reorder is the divergence source.
