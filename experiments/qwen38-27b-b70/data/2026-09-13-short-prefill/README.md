# Short-prefill measurement packet

See the [result and replay instructions](../../notes/2026-09-13-short-prefill-results.md) and [complete summary](summary.json).

The [evidence manifest](evidence/manifest.json) binds five compressed archives and their individual receipts. Extract all archives together, then rerun the collector to verify timing, exact outputs, original-reference parity and completeness without GPUs. This is a diagnostic c1 screen; no runtime default or performance headline was promoted.

The [verification receipt](verification.json) records successful archive extraction, all file/source hashes, and identical recomputation of the summary.
