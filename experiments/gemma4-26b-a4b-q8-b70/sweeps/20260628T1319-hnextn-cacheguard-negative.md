# 2026-06-28 - Gemma 4 26B Q8 h_nextn cache-guard attempt (negative)

## Goal

Try to move the strict fresh-response Gemma 4 26B A4B `UD-Q8_K_XL` 1x B70 lane from the current `98.34 tok/s` record toward a reliable `>100 tok/s` by removing a duplicate synchronous `h_nextn` row read in MTP full-accept cycles.

The idea came from a source audit: with `LLAMA_MTP_DEFER_TARGET_H_NEXTN=1`, `common_speculative_impl_draft_mtp::process()` copies the verifier batch's final `h_nextn` row into `pending_h`; `accept()` may then copy the same row again if the cycle full-accepted the draft. The patch recorded the cached row index and skipped the accept-time copy when it matched.

## Patch Shape

Source file: `/home/steve/src/llama.cpp-gemma-record-repro-c926/common/speculative.cpp`

Temporary changes:

- add `pending_h_row`;
- set it when `process()` stashes `pending_h`;
- in `accept()`, skip `llama_copy_embeddings_nextn_ith()` when the requested row already matches;
- add `accept_copy_skips` to the MTP profile log.

The patch was reverted after the screen because the win was too small and the measured run was below the existing record family.

## Validation Run

Run directory:

`data/gemma4-q8-gpu0-hnextn-cacheguard-screen-20260628T131902Z/summary.json`

Server log:

`/mnt/fast-ai/bench-results/gemma4-26b-a4b-q8/servers/gemma4-q8-gpu0-hnextn-cacheguard-screen-20260628T131902Z.server.log`

Identity:

- target: `/mnt/fast-ai/llm-models/gemma4-26b-a4b-it-q8-gguf/gemma-4-26B-A4B-it-UD-Q8_K_XL.gguf`
- draft: `/mnt/fast-ai/llm-models/gemma4-26b-a4b-it-q8-gguf/MTP/gemma-4-26B-A4B-it-Q4_0-MTP.gguf`
- strict fresh realistic suite, each prompt once, `cached_tokens=0`;
- `MAX_TOKENS=128`, `REALISTIC_METRIC_TOKENS=100`;
- current record env identity: VDR2 Q8 reorder, bulk sampled verifier IDs, `n_max=3`, `n_min=2`, `p_min=0.0475`, `UBATCH_SIZE=1024`, `LLAMA_SYCL_F16_P021_SMALL_NCOLS=1`.

Results:

- canary: `8/8` repeats across json/sort/arithmetic/code, all pass;
- strict fresh gate: pass, all `cached_tokens=0`;
- median `tok_s_1_100_after_ttft`: `97.4419817053517`;
- p10 `86.8133017609438`;
- mean `96.85223422830397`;
- full-128 after-TTFT median `97.71159007166766`;
- TTFT median `179.8045 ms`.

Profile signal:

- the optimization did fire (`accept_copy_skips=304` near the end of the run);
- but `accept_copy_ms=3.495 ms` over roughly `4756` target tokens, so the duplicate accept copy is not a material bottleneck;
- target generation and draft decode dominate instead.

## Decision

Negative / neutral. Do not promote. Do not run a full 512-token confirmation from this patch.

Reason:

- the saved copy time is far too small to bridge `98.34 -> >100`;
- the strict 128-token screen was below the record family;
- keeping the patch default-on could add maintenance risk for no measurable gain.

Next implication: stop chasing host `h_nextn` copy micro-optimizations. A reliable `>100` likely needs reducing target generation body cost, draft decode cost, or improving verified accepted-token shape rather than trimming accept bookkeeping.

## Follow-up Full512 Four-Lane Screen

After the early 128-token screen, the cache-guard was accidentally still active
in the local llama.cpp source. I rebuilt/relinked the patched server and ran a
strict full512 four-lane screen to settle whether it could be a reliability win.

Stamp: `20260628T144003Z`

Run directories:

- `data/gemma4-q8-gpu0-strict-hnextn-cacheguard-u7-full512-20260628T144003Z/summary.json`
- `data/gemma4-q8-gpu1-strict-hnextn-cacheguard-u7-full512-20260628T144003Z/summary.json`
- `data/gemma4-q8-gpu2-strict-hnextn-cacheguard-u7-full512-20260628T144003Z/summary.json`
- `data/gemma4-q8-gpu3-strict-hnextn-cacheguard-u7-full512-20260628T144003Z/summary.json`

Common identity:

- target `UD-Q8_K_XL`; draft `Q4_0-MTP`;
- `n_max=3`, `n_min=2`, `p_min=0.0475`, `UBATCH_SIZE=1024`;
- direct draft argmax IDs with unroll 7;
- bulk sampled verifier IDs;
- VDR2 Q8 reorder, route cache, selected softmax/fused, weighted sum, RMS reuse,
  `LLAMA_SYCL_F16_P021_SMALL_NCOLS=1`;
- strict realistic suite, each prompt once, `cached_tokens=0`, 512 max output,
  median tokens 1-100 after TTFT.

All four lanes passed canaries and the strict fresh-response gate, but throughput
was below the current record family:

| lane | median 1-100 tok/s | p10 | mean | full512 median | wall median | TTFT median |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| gpu0 | 94.633 | 86.469 | 95.665 | 91.438 | 87.971 | 179.3 ms |
| gpu1 | 96.815 | 87.076 | 95.804 | 92.979 | 89.273 | 180.1 ms |
| gpu2 | 94.925 | 85.941 | 94.823 | 91.861 | 88.819 | 180.7 ms |
| gpu3 | 95.085 | 87.088 | 97.079 | 92.035 | 88.290 | 179.4 ms |

Conclusion strengthened: **negative**. The patch is not just too small; in the
full strict run it trails both the promoted `98.34` record and the recent
`99.37` control. The active code path was reverted after this screen. Preserve
the notes/results as a dead-end record; do not promote this change.
