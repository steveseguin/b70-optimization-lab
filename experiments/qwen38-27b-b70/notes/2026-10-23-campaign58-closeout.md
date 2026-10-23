# Campaign 58: counting memo saves time, seed 2 is confounded — closeout

## Question and identity

Does exact per-message token-count memoization remove the CLM client's growing overhead without changing
the model's input or quality? Campaign 58 ran October 23, 02:53–05:46 EDT on the two-card host: official
Qwen3.8 27B FP8, campaign 55's TP2/MTP5 server, full-precision KV, K32V, ctxkeeper 1.3.0, both unchanged
2M hostile tasks, thinking on, `COUNT_MEMO=1`, lean client. Each seed had a fresh server; `RESTORE=0`.
This is a cache-enabled long-history agent experiment, not a cold realistic-suite model speed claim.
[Registration](2026-10-23-harness-count-memo.md) and
[receipts](../data/2026-10-23-context-campaign58/).

## Outcome

**The registered gate failed. The memo is withdrawn from the default (`COUNT_MEMO=0`); public wall
figures stay unchanged.** Seed 0 reproduces campaign 55; seed 2 receives different tool text before its
first NOTES request, so this pair cannot isolate a memo effect on that seed.

| Measure | Seed 0 | Seed 2 |
| --- | --- | --- |
| Answers | 423/423 (c55: 423) | 418/423 (c55: 420; prediction 419–421) |
| Unchanged audit | PASS, 0 wrong STATE lines | FAIL, 16 flagged lines (c55: 2) |
| NOTES text vs c55 | All 153 versions identical | Different from version 1; 154 vs 152 versions |
| Audits applied / forgery targets | 16/16 / all kept | 16/16 / all kept |
| Client summary wall | 81 min 15 s (c55: 92 min 40 s) | 83 min 19 s (c55: 93 min 10 s) |
| Between-step residual | 233 s (c55: 898) | 277 s (c55: 796) |
| No-notes call gaps, summed | 414 s (c55: 1,000) | 490 s (c55: 914) |

Wall is the client summary's definition, consistently compared with c55. The runner includes additional
launch/finish work: 81 min 36 s and 83 min 44 s. The time-budget tool measures first main request start
through last main request finish: 4,860 and 4,984 s. Both wall predictions were met, but neither the
between-step residual nor the registered no-notes gap sum met 150 s. The early flat-gap observation
did not hold to the end: last-250-call mean gaps are 0.51 and 0.55 s (first: 0.14 s).

## What worked

Seed 0's whole archived text and all NOTES texts match c55. Its main model time is 2,642 s in both,
notes time 1,717→1,718 s, tool time 130 s in both, around-call work 137→138 s, and between-step work
898→233 s. The 11-minute saving is directly localized to client overhead on this matched seed.
Seed 2 is recorded separately, not used to claim a quality-preserving speedup.

Both servers stopped gracefully, with stop confirmed. Minimum available host RAM was 2.19/2.36 GiB;
the runner reported no GPU fault. Cards were empty at the audit.

## What failed or remains uncertain

Seed 2's identical opening assistant command includes `ls -la /app/`. Its first tool response reports
the parent directory as `Oct 22 16:45` in c55 and `Oct 23 08:21` in c58. Those timestamps are UTC inside
the task container. All 16 saved archive text records through the first NOTES request (`upto=18`) match
after replacing only that timestamp. The first NOTES text then differs, and the first main assistant
text difference follows at archive n=23. The input mismatch is proven; attributing all downstream
differences to it still needs a controlled run. A count-memo defect is not established by this comparison.

The unchanged auditor flags vonedi62 in 13 versions and fatane57, rumi62 and pefaka34 once each.
The fatane57 flag is a parser false positive: `opened at 286 (item 79; was removed item 44; ...)`
contains a historical removal that the parser treats as current. Preserve the frozen audit's 16 and FAIL;
15 substantive wrong lines remain, so correcting that parser would not rescue the gate. No grader or
audit code was changed for this result.

The remaining growing client time needs measurement; duplicate snapshot serialization/writes are a
candidate, not a measured attribution. Keep that lever separate from repairing the controlled comparison.

## Evidence and patches

- [Seed 0 audit](../data/2026-10-23-context-campaign58/c58-seed0-audit.json),
  [seed 2 audit](../data/2026-10-23-context-campaign58/c58-seed2-audit.json).
- [NOTES and first-input comparison](../data/2026-10-23-context-campaign58/c55-c58-notes-and-input-comparison.json),
  [time split](../data/2026-10-23-context-campaign58/time-budget.json),
  [runner summary](../data/2026-10-23-context-campaign58/campaign-summary.log),
  [server states](../data/2026-10-23-context-campaign58/server-health.json).
- [Memo and default withdrawal](../scripts/context/clm_baselines.py),
  [CPU exactness checks](../data/2026-10-23-count-memo/).
  Raw full histories remain under `/mnt/fast-ai/bench-results/context-longrun-20261016/`, with their
  paths and hashes in the receipts; they are not public full-history archives.

## When to revisit

Run seed 2 with memo off and on using identical sandbox metadata, fresh servers, unchanged task text,
unchanged model settings and the same audits. Pin the sandbox root mtime to c55's observed timestamp
before the agent starts; do not filter tool output, change the prompt or change task answers. Verify
the opening observation and full NOTES/answer identity. Keep the memo opt-in until that control passes;
a match alone does not waive either arm's quality audit. No public wall update on campaign 58 alone.
