# The two public quoted-events runs, repeated on the fixed checker (2026-10-07)

**In plain words:** the 2026-10-06 review found three holes in the scorer behind the "quoted events"
results (a made-up update could pass its quote check; mixed updates could apply out of order; an
unquoted heredoc let shell commands run). The reviewed patch was applied to the live harness
(commit 414eb6374; `test_quoted_delivery.py` 9/9 on the patched files, 4 failures on the unpatched
baseline; `stub-checks.sh` 22 PASS, 0 FAIL). Then the two runs that are published on skindeep.ai were
repeated on the **same task bytes** with the patched harness. Both came out the same.

| Run (quoted agent, 32K budget) | Original (2026-10-06, old checker) | Repeat (fixed checker) |
| --- | --- | --- |
| 480K narrative stream, seed 0 | 10/10, 1,173 s, 578 calls, 36,702 tokens written, peak 22,430 | **10/10, 1,165 s, 577 calls, 36,600 written, peak 19,935** |
| 1,000K narrative stream, seed 0 | 24/24, 2,874 s, 1,236 calls, 111,709 written, peak 22,815 | **24/24, 2,867 s, 1,236 calls, 111,709 written, peak 22,815** |

The million-token repeat is call-for-call identical (same calls, same tokens written, same peak
context); the 480K repeat differs by one call and 102 written tokens. So the checker holes did not
affect either published number: nothing the model sent on these streams went through the removed
fallback path. The repeat does not add a correctness guarantee the review did not grant: quote and
amount checks still do not prove event completeness or operation semantics.

## What was run

* Harness: `experiments/qwen38-27b-b70/scripts/context/` at commit `bbe994c9e` (patch applied in
  414eb6374). Tasks: byte copies of the original task directories (`expected.json` sha256
  `e8fd0d93…` and `d39a5522…`, the same as the canonical manifest records), placed under
  `context-planA-client/rd480q-v2` and `rd1mq-v2`; `--refresh-graders` touched only `grade.py`.
* Server: the Oct 6 launch argv (R314 state-stride image, drafting on, exact prefix cache, tool
  parsers), with ONE change on the successful attempt: `--max-model-len 65536` instead of 262144.
  The first attempt, at 262144, was stopped by the research launcher's host-memory guard at 2.00 GiB
  available 20 min into the 480K trial (no GPU fault lines; `attempt1-MEMORY-GUARD.json`). The
  262K-window server holds about 1 GiB more host RAM than the 33K/65K servers; the quoted agent
  never exceeds ~23K tokens of context plus 4K of output, so the window change cannot alter its
  calls. The 480K trial was restarted from scratch (`runs.attempt1-guard-kill` kept beside it).
* Evidence: `data/2026-10-07-context-reverify/` (validated export: `manifest.json`, `results.md`,
  `site_projection.json`, `sources/`; plus `plan.sh`, `launch.sh`, `server-argv.json`, `campaign.log`,
  `attempts.txt`). Raw trials: `/mnt/fast-ai/bench-results/context-planA-client/{rd480q-v2,rd1mq-v2}`.

## What it does not show

* Nothing about the other legacy cells (the 120K and retention runs were not repeated).
* No new speed claim; elapsed is reported as measured, one pair each.
* The remaining checker limits from the review stand (no semantic verification of events).

Next for the context lane: the retention study on an outside benchmark
(`notes/2026-10-07-longmemeval-retention-prereg.md`).
