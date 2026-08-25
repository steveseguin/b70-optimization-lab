# b2dd TP1 eager-MTP expansion preregistration

Status: **preregistered, not launched**. This packet does not change website
coverage or any historical performance result.

The passed eager-MTP2 sensitive parent now unlocks its exact frozen expansion.
Stage E1 is TP1 eager MTP2, F16 KV, graph off: one fresh-cache 25-prompt
natural-EOS short benchmark, the complete quality battery, nonzero speculation
acceptance, and exact all-25 equality to the qualified eager-MTP0 target oracle.
Stage E2 is dependent on E1 passing and is the one authorized eager-MTP4 short
actual. Rather than spend that single actual on only two prompts, the same one
fresh server runs the full short benchmark and complete quality battery, with
the same acceptance and all-25 target-oracle gates. Decode speed is recorded
but never decides correctness or whether E2 runs.

E2 is one actual globally, not one per retry number. It may start under rN only
when no earlier E2 output or cache exists; after any E2 evidence is created,
another MTP4 launch requires a separately reviewed preregistration. The
launcher scans all r1-r99 E2 roots and caches before launch and fails closed if
it finds one.

Both stages use the immutable b2dd/1e90 image on GPU 0 at TP1/PP1/DP1/c1,
float16 KV, max-model-len 32768, chunked prefill, async scheduling, prefix cache
off, graph variables scrubbed, and `PYTHONHASHSEED=0`. MTP identity is exact
`qwen3_next_mtp` at depth 2 or 4. Every stage and retry receives a nonexistent
ext4 output root, cache, and port. Outputs are never resumed or overwritten.

The launcher is inert unless given `--execute`, a stage, an attempt, and its
exact acknowledgement. At launch it requires clean pushed local/live `main`,
the exact image, every frozen input and parent evidence hash, idle GPU/runtime
state, and the host/GPU0 locks. After a run, local HEAD/branch/worktree and
cleanup remain gating. An unrelated push to live `origin/main` during a stage
is recorded but cannot mutate or invalidate the already-frozen process.

The short suite remains outside the numeric active-context axis. Neither the
configured 32768 maximum nor these runs fill a context-zero or 32K point. Every
attempt remains durable, including quality, oracle, acceptance, speed, init, or
cleanup failures. No result may lower or replace protected historical speeds.

The exact identities, parent receipts, hashes, roots, ports, gates, and frozen
interpretation are in
[`2026-08-25-qwen38-b2dd9ce73d-tp1-eager-mtp-expansion-r1.json`](../data/2026-08-25-qwen38-b2dd9ce73d-tp1-eager-mtp-expansion-r1.json).
