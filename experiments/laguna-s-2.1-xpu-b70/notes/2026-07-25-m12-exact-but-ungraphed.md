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

Item 3 was the exactness blocker. Its own comment records why: above width 8 the
path fell through to chunk-prefill, and "the two kernels are close, not bitwise
equal, and Laguna's narrow logit margins can therefore change greedy tokens".
That is why serializing the MoE had not restored exactness.

## Remaining blocker

The audited Breakable graph never captures at width 12: zero
`Captured audited breakable cudagraph` lines across four separate M=12 runs.
Execution therefore runs eager and collapses to 7.72-7.95 tok/s despite the
acceptance gain.

A gated diagnostic on the capture filter shows it is reached on a prefill call
(`mode=PIECEWISE num_tokens=12 verifier=False eligible=None want=12`) but never
on a verifier step. Since speculation demonstrably runs, the likely cause is
that the dispatcher selects `CUDAGraphMode.NONE` for the 12-token verify batch,
so `BreakableCUDAGraphWrapper` returns before consulting the filter at all.

## Next

Determine why the cudagraph dispatcher does not assign a graph mode to the
12-token speculative verify batch while it does for the 8-token one. The
diagnostic hook is committed and gated behind
`VLLM_XPU_LAGUNA_CAPTURE_FILTER_DEBUG=1`; extending it to log the dispatcher's
decision and the descriptor for every verify step is the next step.

If the graph engages at width 12 and cycle time grows less than 6.9%, M=12
exceeds the current record. That is the whole remaining question.
