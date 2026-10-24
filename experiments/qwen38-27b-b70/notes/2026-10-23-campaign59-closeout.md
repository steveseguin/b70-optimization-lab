# Campaign 59 — exact counting memo qualifies on the matched seed-2 control

<!-- campaign-closeout -->

## Question and identity

Does exact per-message token-count memoization preserve the agent's result when the opening
filesystem observation is fixed? Two fresh two-card Qwen3.8-27B FP8 servers, full-precision KV,
MTP5, piece 832, K32V/ctxkeeper 1.3.0; the existing 2M hostile seed 2 with sandbox-root mtime
fixed to campaign 55's observed minute. Memo off then on, October 23, 09:39–12:43 EDT.
[Preregistration](2026-10-23-campaign59-matched-memo.md). This is a cache-enabled agent wall
measurement with a named controlled fixture, not a cold model-throughput benchmark.

## Outcome

**All registered gates pass. Restore `COUNT_MEMO=1` for the lab harness; `COUNT_MEMO=0` restores
upstream counting.** Independent review rehashed all 38 provenance files and directly compared
the NOTES/archive sequences and graded answers. The same comparisons also match campaign 55.

| Measure | Memo off, c59a | Memo on, c59b |
| --- | --- | --- |
| Answers | 420/423 | Identical 423-answer map, 420 correct |
| NOTES | 152 versions | Every version identical |
| Archived text | 2,578 records | Every record identical |
| Wrong STATE lines | 2/8,582 | Same two, each lasting one version |
| Forgery targets / corrections | All 97 kept / 16 applied | Same |
| First-to-last main-request wall | 5,545 s (92m25s) | 4,992 s (83m12s) |
| Main + notes model time | 4,487 s | 4,490 s |
| Between-step residual | 790 s | 234 s |
| Runner wall | 93m01s | 83m47s |

The matched request-clock wall saving is **553 s, 9.97%**, above the registered 8% bar.
Model time changes by 0.07%; the saving is client counting. The candidate's 234 s between-step
residual passes the revised ≤350 s prediction. Both audits pass without changing their code.

## What worked

The fixed sandbox observation reproduces the entire campaign-55 text/answer result, both with
and without the memo. It resolves the comparison confound identified in campaign 58. The default
change passed a CPU check for installation, count equality before/after message mutation, and
restoring the untouched upstream function with `COUNT_MEMO=0`. Earlier fake-server jobs retain
their byte-identical requests, trajectories, usage, graders and snapshots.

Both servers stopped cleanly, stop confirmed, with no matching fault signatures in their retained
kernel logs. No resident server was restored.

## What failed or remains uncertain

Nothing here erases campaign 58's failed seed-2 gate or its missed <150 s prediction. Campaign 59
is a separately registered controlled environment. Equality here means saved model text and answers,
not real-run HTTP-byte identity; the byte-identical HTTP claim belongs only to the CPU fake-server jobs.

The original three answer misses and two wrong STATE lines persist. Between-step work is reduced,
not gone: mean gaps without notes rise from 0.14 s early to 0.51 s late with the memo, versus
0.21→1.21 s without it. Larger histories and arbitrary tasks remain unproven.

Timing definitions must remain separate: Harbor trial wall is 92m40.66s→83m26.77s; the request-clock
and runner walls are above. Do not mix those measures or overwrite older published measurements.
No public model speed figure or external page is changed by this closeout.

## Evidence and patches

- [Complete comparisons and provenance](../data/2026-10-23-context-campaign59/comparison.json).
- [Time budget](../data/2026-10-23-context-campaign59/time-budget.json),
  [off audit](../data/2026-10-23-context-campaign59/c59a-audit.json),
  [on audit](../data/2026-10-23-context-campaign59/c59b-audit.json),
  [server states](../data/2026-10-23-context-campaign59/server-health.json).
- [Memo implementation and default](../scripts/context/clm_baselines.py),
  [CPU wiring receipts](../data/2026-10-23-campaign59-preflight/),
  [campaign 58 closeout](2026-10-23-campaign58-closeout.md).

Full local logs remain under `/mnt/fast-ai/bench-results/context-longrun-20261016/campaign59-control/`;
raw histories are identified and hashed in the comparison receipt.

## When to revisit

Reopen memo exactness on a changed tokenizer/harness or an observed count mismatch. Residual client
cost is a separate future lever. Next work follows the north star's practical correctness question:
campaign 60's real-agent notes failure, then source-evidence verification.
