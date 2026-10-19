# Packet156 host suffix-slack bound — closeout
<!-- campaign-closeout -->

## Question and identity

Can bundle8 move the token-independent hidden copy, norm and projection to
rank1's existing host insertion after prefix completion, while rank1 awaits
rank0's suffix, and recover at least 0.423078 ms/hit for +2%?

October 19, 2026, CPU-only analysis on steve-b70s. Unchanged two-B70
packet136 bundle8, 24/24 target layers, rank1 draft, fixed 80,128-row draft
prefix, `iq3-p49-split32-v1`, full BF16 KV/state and original packet49 oracle.
The new evidence is packet154's completed lane-B smoke and C/X/C/X/C split,
64 output tokens per each of twelve fixed prompts, not a new candidate run.
The prior 58.798108759182306 tok/s record stays unchanged.

## Outcome

**Reject this host-boundary scheduling arm before runtime implementation.**
The measured critical-path draft dependency is real, but the specified idle
window is too small. The brief's bound is
`min(hidden-branch service, suffix slack) - adoption/dispatch`; bounding slack
below the goal is sufficient without inventing a complete branch-service time.

The [complete packet154 bracket](../packet154-rank1-split/v5/evidence/device-p154c-split-v5-B/bracket-summary.json)
passed all 13 exact checks in each view and unchanged draft proposals, with
**0.061632%** control drift. Its original analyzer was replayed without edits
against every request, reproducing the entire `rank1_split` object exactly.
It selects draft issue/completion/publication as the dominant wait subcause:

| Control view | Rank0 remote wait, ms/interval | Draft overlap, ms/interval | Op9 wait, ms/interval |
| --- | ---: | ---: | ---: |
| 0 | 1.552815 | 1.243769 | 1.262394 |
| 2 | 1.585341 | 1.246313 | 1.265361 |
| 4 | 1.573301 | 1.240570 | 1.259403 |

These host scopes include queue/polling delays; they are not isolated GPU
kernel durations. The control-median explicit rank1 suffix wait is only
**0.000917 ms/interval**. The coordinator brief cited about 1.227 ms draft
overlap in smoke; the retained full smoke report's corresponding aggregate
is **1.247329 ms/interval**. The actual retained bytes and full bracket,
rather than the rounded brief, are the authority used here.

### Deliberately generous bound

The exact insertion is `rank.hpp`'s `e.drain()` return before `head_merge`.
In packet154 this is `b_completion.end`. We match each prefix/suffix record
within its request by **sequence, op and position**, require one command and
one of each scope, and check:

```text
command start <= b_completion <= prefix_pack <= prefix_export
              <= wait_rank0_suffix <= command end
```

Credit **all** time from `b_completion.end` to `wait_rank0_suffix.end` as
free overlap, despite that interval containing required packing, export and
host work. Credit misses as well as hits, and even the boundary windows
outside the measured first-to-64th-token interval. Assume adoption, copying
staged results and dispatch cost zero. A no-next-draft boundary also gets
credit. This overstates what the specified design could recover.

| View | Median credited ms/interval | Worst prompt: all window credit / hit, ms | Counterfactual gain ceiling |
| --- | ---: | ---: | ---: |
| Smoke | 0.049994 | 0.119958 | 0.315694% |
| Control 0 | 0.050955 | 0.084237 | 0.292689% |
| Diagnostic 1 | 0.050978 | 0.083404 | 0.298945% |
| Control 2 | 0.052680 | 0.080053 | 0.315318% |
| Diagnostic 3 | 0.049909 | 0.090094 | 0.303199% |
| Control 4 | 0.050493 | 0.082628 | 0.286716% |

The last column is **counterfactual bound arithmetic, not a measured gain**:
subtract the generous credited time from each prompt's actual 63-interval
duration, calculate its rate, then take the median within each class and the
median of class medians. This is a 64-token diagnostic bound, not the
128-token record or a public benchmark. Every control prompt is below
0.423078 ms/hit even after donating misses' windows to hits. Both diagnostic
views independently agree. No candidate output or speed was measured.

There are 768 same-command windows in smoke and 3,840 in the bracket; 756
and 3,780 respectively are wholly inside the measured interval windows.
Keep the outliers: the smoke's bug-report-synthesis has a 0.960355 ms window.
The rejection is based on full per-prompt totals and class reaggregation,
not a claim that every individual window is below threshold.

## What worked

The unchanged original analyzer validated both actual first-request streams
for every view, with no wall-clock deadline. Missing or empty streams fail;
cold TTFT is irrelevant to whether completed data is valid. The complete
report replay and compressed-receipt replay reproduce the original split
and the new bound. Fourteen tests exercise actual data, including missing/
empty/wrong-rank streams, truncated JSON, stale sequence, duplicate/missing
completion, illegal order, NaN, missing token event, bad cold gate and a
one-hour artificial first-request delay. No test replaces the proof function.

An independent read-only review of the smoke joins and insertion-point
interpretation agreed with the rejection. All 219 prior negative indexes
were searched, and the requested eight families of excluded arms are
distinguished in [DO-NOT-REPEAT.md](DO-NOT-REPEAT.md).

## What failed or remains uncertain

This closes **only the specified host insertion after drain return**. The
device may finish the prefix before the host returns from drain. Those host
scopes do not bound an earlier device-enqueued mechanism; it needs different
completion/publication evidence. No claim of a finished draft lane follows.

The complete hidden branch's current service time remains unmeasured. Old
packet122 norm+projection events are only secondary context: roughly
0.064–0.069 ms, excluding copy/host work and on a different identity. They
were not substituted for a current complete-branch ceiling.

Following the brief's early-close rule and PLAN's failed-bound dispatch,
there is no runtime copy, selection, staged buffer, build, native preparation
probe, both-compiler canonical-state proof, lane proposal, planner admission or
entry rehearsal. Those are **not passed** by this analysis; they were avoided
because the mechanism failed before implementation. No READY-true marker or
lane-B-only packet is produced. A reopening requires the full build contract
and proposals for both lanes.

## Evidence and patches

- [Smoke bound and raw receipt manifest](evidence/smoke-bound.json),
  [complete bracket bound and manifest](evidence/bracket-bound.json).
- [Smoke retained replay](evidence/smoke-retained-replay.json),
  [bracket retained replay](evidence/bracket-retained-replay.json),
  [14 parser tests](evidence/tests.log).
- [Method](analyze_slack.py), [unchanged original analyzer](method/packet154_analyze.py),
  [source pins](evidence/source-pins.json), [prior audit](evidence/prior-audit.json).
- [Resource budget](BUDGET.md), [retention and restoration](RETENTION.md),
  [historical operator context](evidence/historical-hidden-operators.json).

No runtime patch was created. Compressed complete reports and both timing
streams preserve the observations, including negative/outlier evidence.

## When to revisit

Require a measured legal window and complete branch bound supporting at least
0.423078 ms/hit net saving on the current line. An earlier device-queued
design must prove that boundary rather than calling host drain return GPU
completion, and must preserve every ticket, state, reset, cancellation and
no-DRAFT condition in the original brief.

The required next-design pass is complete in [NEXT-DECISION.md](NEXT-DECISION.md).
Packet153's existing snapshot bracket has now returned only +0.3456%/+0.3533%
and did not qualify. The token, suffix-tail and transfer designs have no
new sufficient bound. The PLAN's no-device-candidate outcome applies;
do not launch a duplicate snapshot build or reopen excluded draft geometry,
precision, history or relocation work.
