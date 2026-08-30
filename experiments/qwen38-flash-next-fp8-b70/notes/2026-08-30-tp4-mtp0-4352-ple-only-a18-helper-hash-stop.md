# Qwen3.8 Flash-Next FP8 A18 helper-hash stop

Date: 2026-08-30
Status: pre-request contract stop; no model result

A18 completed the full 131-shard load, exact PLE placement, cache creation,
warmup, and endpoint health on all four cards. The frozen client then stopped
before its first request because `scripts/qwen38-text-quality-suite.py` had
changed from its preregistered hash. Main commit `c2d4c525a` added an optional
`request_extra` argument and protected-field validation; the existing call
passes no such argument, so its request construction is unchanged, but the
fail-closed hash check correctly rejected unreviewed file drift.

No recovery, quality, timing, exact-4K, or trace request ran. Teardown was
clean and all four cards returned idle. One corrected receive event for the
local NVMe was recorded during warmup; no B70 reset/fault, OOM kill, or runtime
failure occurred. A18 is not a reliability or performance result and changes
no protected result. Its paths remain preserved and will not be reused.
