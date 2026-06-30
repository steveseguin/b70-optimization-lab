# 2026-06-30 Record-Identity Spec Profile Refresh

Status: diagnostic only. Do not submit or promote this row.

## Run Identity

- label:
  `gemma4-q8-gpu0-record-refresh-specprofile-strict128-20260630T002301Z`
- summary:
  `data/gemma4-q8-gpu0-record-refresh-specprofile-strict128-20260630T002301Z/summary.json`
- server stdout:
  local ignored log
  `data/gemma4-q8-gpu0-record-refresh-specprofile-strict128-20260630T002301Z/server.stdout.log`
- server log:
  `/mnt/fast-ai/bench-results/gemma4-26b-a4b-q8/servers/gemma4-q8-gpu0-record-refresh-specprofile-strict128-20260630T002301Z.server.log`
- target/verifier: Gemma 4 26B A4B IT `UD-Q8_K_XL`
- draft: Gemma MTP `Q4_0`, `n_max=3`, `n_min=2`, `p_min=0.0475`
- runtime: llama.cpp `c926ad098` patched Gemma stack, one B70
- key env/config:
  `FLASH_ATTN=on`, `CTX_SIZE=32768`, `GGML_SYCL_ENABLE_VMM=1`,
  `UBATCH_SIZE=1024`, `LLAMA_SYCL_F16_P021_SMALL_NCOLS=1`,
  `LLAMA_SPEC_VERIFY_BULK_SAMPLED_IDS=1`,
  `LLAMA_GEMMA4_MOE_FUSED_DOWN_WEIGHTED_SUM_REORDER_VDR2=1`,
  `LLAMA_SERVER_SPEC_PROFILE=1`, `LLAMA_MTP_DRAFT_PROFILE=1`

## Validity

The fixed realistic cold gate passed. This is still diagnostic only because
profiling is enabled and `MAX_TOKENS=128` was used to keep the profile run
short.

- canary: `32` repeats, pass
- fixed realistic suite: pass
- cached tokens: all zero
- prompt reuse/history acceleration: none
- primary metric, tokens 1-100 after TTFT:
  - median: `114.05619435553182 tok/s`
  - p10: `103.63778560276732 tok/s`
  - mean: `117.14718705268119 tok/s`
- full-output after TTFT median: `114.27755742297356 tok/s`
- wall full-output median: `97.40436316820961 tok/s`
- TTFT median: `179.51940704369918 ms`

The current headline remains the non-profiled full512 record:
`121.41411987308553 tok/s` in
`data/gemma4-q8-gpu3-q8lmhead-noreorder-control-full512-20260629T224927Z/summary.json`.

## Profile Findings

Server/spec profile at the end of the run:

| Phase | Time ms | Calls | Tokens | Avg ms | Avg token |
| --- | ---: | ---: | ---: | ---: | ---: |
| target decode | `38529.540` | `1211` | `9526` | `31.816` | `4.045` |
| target prompt | `19773.561` | `280` | `5839` | `70.620` | `3.386` |
| target generation | `18755.979` | `931` | `3687` | `20.146` | `5.087` |
| draft | `2665.342` | `1211` | `2756` | `2.201` | n/a |
| process | `26.218` | `1211` | n/a | `0.022` | n/a |
| sample accept | `3.770` | `921` | n/a | `0.004` | n/a |
| common accept | `9.503` | `921` | n/a | `0.010` | n/a |
| emit | `3.069` | `787` | n/a | `0.004` | n/a |

Target decode phase profile:

- calls: `1211`
- tokens: `9526`
- total: `38528.364 ms`
- process ubatch: `36833.360 ms`
- post extract: `1665.577 ms`
- sampled extract: `1665.262 ms`

Draft decode phase profile:

- calls: `926`
- tokens: `927`
- total: `2673.038 ms`
- process ubatch: `2205.954 ms`
- post extract: `453.455 ms`
- sampled extract: `446.878 ms`
- `h_nextn_extract_ms=6.399`

MTP state:

- `process_calls=1211`
- `process_tokens=9526`
- `verify_rows=9526`
- `draft_decodes=925`
- `fast_topk_calls=925`
- `vocab_scanned=0`
- `sampler_calls=0`
- `hidden_rows=0`
- `handoff_rows=0`
- `deferred_pending_h_skips=0`

## Interpretation

The draft path and host sampler/accept bookkeeping are not the limiting factors
in the current record identity. Target/verifier graph compute dominates, and
the one measurable host-side tax is the backend sampled-token extraction
boundary. The extraction path already uses compact sampled IDs and
`LLAMA_SPEC_VERIFY_BULK_SAMPLED_IDS=1`, so a patch that merely copies fewer
integers is unlikely to help. A useful sampled-ID patch would need to remove or
overlap the backend read/synchronization, or compare draft candidates against
target sampled IDs on the backend while preserving exact target-verifier
semantics.

Do not reopen the following based on this profile alone:

- host sampler loop cleanup;
- smaller sampled-ID vector copies;
- n-gram/history/prefix reuse;
- draft-side top-k or hidden handoff tweaks;
- bonus-row skip/late-head/prefix2 lanes already closed negative.

Current practical next patch target remains target graph cost: exact verifier
LM-head or routed MoE reduction that removes real work without changing the Q8
target/verifier lane.

## Follow-up: Accept-Side Sync Profile

Status: diagnostic only. Do not submit or promote this row.

After the profile above, a default-off timing wrapper was added around the two
backend-argmax speculative-verifier `llama_synchronize(ctx)` sites in
`common/sampling.cpp`. The wrapper is controlled by
`LLAMA_SPEC_VERIFY_SYNC_PROFILE=1`; with the flag unset it calls the same
`llama_synchronize(ctx)` and is behaviorally unchanged. Patch artifact:
`../../../../patches/gemma4-26b-a4b-q8-b70/20260630-spec-verify-sync-profile.patch`.

Run identity:

- label:
  `gemma4-q8-gpu0-syncprofile-strict128-20260630T004214Z`
- summary:
  `data/gemma4-q8-gpu0-syncprofile-strict128-20260630T004214Z/summary.json`
- server stdout:
  local ignored log
  `data/gemma4-q8-gpu0-syncprofile-strict128-20260630T004214Z/server.stdout.log`
- server log:
  `/mnt/fast-ai/bench-results/gemma4-26b-a4b-q8/servers/gemma4-q8-gpu0-syncprofile-strict128-20260630T004214Z.server.log`
- env deltas from the profile run above:
  `LLAMA_SPEC_VERIFY_SYNC_PROFILE=1`

Validity stayed clean under the diagnostic profile settings:

- canary: `32` repeats, pass
- fixed realistic suite: pass
- cached tokens: all zero
- prompt reuse/history acceleration: none
- primary metric, tokens 1-100 after TTFT:
  - median: `113.95290453798177 tok/s`
  - p10: `107.71537888722078 tok/s`
  - mean: `115.84490802082824 tok/s`
- full-output after TTFT median: `113.78286141066025 tok/s`
- wall full-output median: `97.99480352584561 tok/s`
- TTFT median: `178.94259752938524 ms`

Critical profile result:

```text
spec verify sync profile: calls=896, rows=3581, sync_ms=1.734,
avg_call_ms=0.002, avg_row_ms=0.000
```

End-of-run target/draft profile stayed aligned with the previous profile:

- target decode: `38524.013 ms`, `1211` calls, `9518` tokens,
  `31.812 ms/call`, `4.047 ms/token`
- target process ubatch: `36812.233 ms`
- target sampled extraction: `1681.758 ms`
- draft: `2647.720 ms`, `1211` calls, `2748` draft tokens,
  `2.186 ms/call`
- draft sampled extraction: `447.369 ms`

Interpretation: the explicit accept-time synchronize is essentially free. The
measured `sampled_extract_ms` cost is not waiting in the later sampler accept
loop; it is in the backend sampled-output read/enqueue boundary, graph tail, or
the work needed to make the tiny sampled-ID tensor visible to the host. A
device-side accept-prefix design may still be architecturally clean, but this
profile lowers its expected near-term payoff. The record path should prioritize
real verifier graph reductions: exact LM-head work removal, routed MoE boundary
work, or backend output-read avoidance that actually removes the extraction
boundary rather than moving the final `llama_synchronize(ctx)`.
