# Laguna M=12 — exact and speculating, but the graph does not engage

Date: 2026-07-25 America/Toronto

Status: **partial. Exactness achieved at M=12 with real speculation. Throughput
blocked: the Breakable graph never captures at width 12, so execution is eager
and measures 7.72-7.95 tok/s.** Decode rate on the record path remains
**93.990 tok/s**. Nothing promoted.

## Achieved

M=12 (DFlash depth 11) is **bitwise exact against the canonical q=1 teacher**
on the full 512-token 13-prompt real cold suite, `all_exact: True`, all
`cached_tokens=0`.

Speculation genuinely runs at depth 11 — this was verified from the server
metrics rather than assumed, because "exact vs a q=1 teacher" would be
trivially true if speculation had silently disabled itself:

| metric | M=8 record | M=12 |
| --- | ---: | ---: |
| `spec_decode_num_drafts_total` | 1718 | 1606 |
| `spec_decode_num_draft_tokens_total` | 12026 (7.0/draft) | 17666 (11.0/draft) |
| `spec_decode_num_accepted_tokens_total` | 4644 | 4750 |
| emitted per cycle | 3.703 | **3.958 (+6.9%)** |
| acceptance rate | 38.6% | 26.9% |

**The acceptance thesis is confirmed.** Depth 11 yields +6.9% emitted tokens per
cycle, against the +7.8% projected from the measured conditional chain. Deeper
speculation pays because the chain does not decay, exactly as the earlier
analysis predicted.

## Width pins found and parameterized

All now derive from `VLLM_XPU_LAGUNA_EXACT_MAX_M`, default 8, so the record
path is unchanged at every one:

1. `_xpu_batched_m1_linear` — the `1..8` row cap on the stride-zero BMM
2. Laguna `batched_exact_rows` — the MoE batched-exact gate
3. `flash_attn` exact speculative attention — `1 < max_seqlen_q <= 8`
4. Laguna graph contract — `cudagraph_capture_sizes == [8]`
5. `_validate_laguna_m8_breakable_graph_config` — `spec_depth` and `capture_sizes`
6. `_laguna_m8_breakable_graph_capture_filter` — `num_tokens == 8`
7. `_laguna_m8_eligible` — unpadded, scheduled, and spec-token counts

**Correction (same day):** item 7 was stated as complete and was not. A fourth
guard, `scheduler_output.num_scheduled_tokens.get(req_id) == 8`, remained
hardcoded one line below one that had been parameterized. At M=12 that alone
forces graph eligibility false. It is the actual blocker; the dispatcher theory
recorded below was wrong. Found by external review, not by this analysis.

Item 3 was the exactness blocker. Its own comment records why: above width 8 the
path fell through to chunk-prefill, and "the two kernels are close, not bitwise
equal, and Laguna's narrow logit margins can therefore change greedy tokens".
That is why serializing the MoE had not restored exactness.

## Remaining blocker

The audited Breakable graph never captures at width 12: zero
`Captured audited breakable cudagraph` lines across four separate M=12 runs.
Execution therefore runs eager and collapses to 7.72-7.95 tok/s despite the
acceptance gain.

**Root cause, corrected:** a missed hardcoded `== 8` in `_laguna_m8_eligible`
(`num_scheduled_tokens.get(req_id)`). The dispatcher hypothesis below was
wrong; the filter never saw a verifier step because eligibility was already
false upstream.

## Measurement identity defect

The measurement leg wrote `vllm_commit` and `kernel_commit` from the frozen
record constants while only checking that the worktrees were clean, not that
their HEADs matched. Every `identity.txt` produced by the M=12 runs is
therefore false and none of them can support promotion. Fixed to record the
actual worktree HEADs and to mark itself a measurement leg rather than a record
leg. The exactness and acceptance evidence above stands, since it rests on
token ids and server metrics rather than on identity.txt.

## Baseline correction

The approved record is **94.920039** tok/s. The 93.990 figure measured this
session is a single confirmation leg, not the baseline, and must not be used as
the comparison point.

## Next, with the arithmetic corrected

+6.9% emitted per cycle applied to the approved 94.920 record projects roughly
**101.5 tok/s** at unchanged cycle time. Graphing M=12 is therefore **necessary
but not sufficient** for a 102 target, and that projection further assumes M=12
cycle time does not grow at all, which is optimistic. A further measured gain —
the width-two tree, whose +12.0 point top-2 coverage is already measured — is
still required on top.
