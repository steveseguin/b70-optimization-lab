# Qwen3.8 official FP8 TP2 HTTP concurrency R2 result

Classification: **failed harness postprocessor; no values published**.

R2 attempt 1 completed the excluded warmup and all 127 measured requests. The
endpoint harness reported `output-isolation-qualified-shape-variant`: every
response contained 128 complete token IDs, all cache counters were zero, and
no output matched the frozen sequential oracle of another base task. Cleanup
was clean.

The frozen R2 postprocessor nevertheless returned `failed-closed`. It treated
the compact oracle rows as if they had to contain raw `token_ids` arrays. The
compact file intentionally contains only `token_ids_sha256`, so it reported
`oracle_rows_64_complete=false` and `complete_token_id_identity_all=false`
despite the endpoint harness having verified every measured raw response
against those hashes.

This is a real harness defect, not permission to reinterpret R2 as passed. Its
rates and latencies remain excluded. The retained
[`qualification.json`](../data/qwen38-fp8-tp2-http-concurrency-20260826-r2-attempt1/qualification.json)
is the authoritative failed result. A
[`diagnostic reclassification`](../data/qwen38-fp8-tp2-http-concurrency-20260826-r2-attempt1/diagnostic-reclassification-with-fixed-classifier.json)
shows that the corrected classifier understands the exact retained result, but
it is not publication evidence.

The repair moves qualification into a standalone tested tool with three
separate cases: raw pilot oracle accepted, compact frozen oracle accepted for a
publication attempt, and a raw oracle rejected as a substitute for the frozen
compact file. R3 must be preregistered and use two new fresh servers.
