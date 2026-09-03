# Qwen3.8 Flash-Next FP8 A81 preregistration: A80 with a 12 GB supervisor memory floor

Date: 2026-09-03. Byte-identical server to A80 (attempt 81 / port 19753);
only the supervisor's per-second `MemAvailable` floor changes from
16,000,000 to 12,000,000 KiB. Question, design, driver and reading are those
of the A80 preregistration
(`2026-09-03-tp4-mtp1-a80-graph-mtp1-prereg.md`); the negative it answers is
`2026-09-03-tp4-mtp1-a80-memory-floor-negative.md`. Packet: launcher
`d0f2...` (see generator output), client, supervisor and host wrapper as
emitted by `tools/rewrite-q38-a80-to-a81-memory-floor.py`.
