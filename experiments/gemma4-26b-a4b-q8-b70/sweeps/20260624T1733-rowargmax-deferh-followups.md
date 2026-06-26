# 2026-06-24T1733 - Row-Argmax/Defer-H Followups

Goal: continue the fresh-response Gemma 4 26B A4B Q8 lane after the fused
target LM-head argmax experiment proved slower. These runs keep the Q8 target
and Q8 verifier, use the Q4_0 Gemma MTP draft only as a speculative source, and
do not use warmed n-gram/history continuation.

Later update: this note is chronological. Any "current" record language in
older sections means current at that point in the experiment sequence. The later
selected-softmax/weighted-sum Q8 record is `103.2992004295621 tok/s` fresh row0
(`cmqsylo2l011nqr011yydjvne`), documented in
`results/gemma4-26b-a4b-q8-b70/reproduce.md`.

Active source baseline:

- llama.cpp worktree:
  `/home/steve/src/llama.cpp-gemma-record-stack`
- server binary:
  `/home/steve/src/llama.cpp-gemma-record-stack/build-sycl-b70-aot-bmg-g31/bin/llama-server`
- source features enabled:
  `LLAMA_SPEC_VERIFY_BACKEND_ARGMAX_IDS=1`,
  `LLAMA_MTP_DEFER_TARGET_H_NEXTN=1`,
  `LLAMA_MTP_DRAFT_DIRECT_ARGMAX_IDS=1`,
  `LLAMA_MTP_DRAFT_DIRECT_ARGMAX_UNROLL=7`,
  `LLAMA_GEMMA4_MTP_QONLY_ATTN_INPUTS=1`
- common runtime:
  `MTP_N_MAX=7`, `MTP_N_MIN=2`, backend sampling off,
  `MTP_DRAFT_FAST_ARGMAX=1`, draft threads/batch `32/32`,
  `BATCH_SIZE=1024`, `UBATCH_SIZE=1024`, `THREADS=8`, `POLL=100`,
  `GGML_SYCL_ENABLE_VMM=0`, `GGML_SYCL_DISABLE_GRAPH=0`,
  `GGML_SYCL_DISABLE_OPT=0`, `--ctx-checkpoints 0`
- record shape: `filled-long`, actual `588` prompt / `512` output tokens.

Validity: headline candidates use the first fresh measured request only. These
runs have `--cache-ram 0`, `--ctx-checkpoints 0`, no n-gram/history draft, and
the MTP draft operates on the current request before Q8 target verification.

## Screen Batch 1

| Run | Change | Canary | Fresh row0 tok/s | Wall tok/s | Decision |
| --- | --- | ---: | ---: | ---: | --- |
| `gemma4-q8-gpu0-rowargmax-deferh-pmin010-screen-20260624T173350Z` | `MTP_P_MIN=0.10` | 128/128 | 100.824 | 87.845 | valid, below `p_min=0.14` and near row-argmax/defer baseline |
| `gemma4-q8-gpu1-rowargmax-deferh-pmin014-screen-20260624T173350Z` | `MTP_P_MIN=0.14` | 128/128 | **101.390** | 88.237 | screen win; sent to full validation |
| `gemma4-q8-gpu2-rowargmax-deferh-draftkv-q8-screen-20260624T173350Z` | draft K/V `q8_0/q8_0` | 128/128 | 41.941 | 39.493 | reject; compressed draft KV is catastrophic here |
| `gemma4-q8-gpu3-rowargmax-deferh-draftkv-q4-screen-20260624T173350Z` | draft K/V `q4_0/q4_0` | 128/128 | 41.946 | 39.516 | reject; same failure class as q8 draft KV |

Takeaways:

- Slightly stricter `p_min=0.14` may be a small win on top of target
  row-argmax + deferred target `h_nextn`. It needs full 384-row canary plus
  multi-repeat support before promotion.
- Draft KV compression should not be retried on this identity unless the MTP
  draft KV/cache path itself changes. Both q8 and q4 draft K/V were roughly
  `2.4x` slower than the current fresh record.

Follow-up launched immediately:

- Full validation for `p_min=0.14`.
- Neighbor screens for `p_min=0.13`, `0.15`, and `0.16`.

## Screen Batch 2: `p_min` Neighborhood

| Run | Change | Canary | Fresh row0 tok/s | Wall tok/s | Decision |
| --- | --- | ---: | ---: | ---: | --- |
| `gemma4-q8-gpu1-rowargmax-deferh-pmin013-screen-20260624T173546Z` | `MTP_P_MIN=0.13` | 128/128 | 101.020 | 87.786 | valid, below `p_min=0.14` |
| `gemma4-q8-gpu2-rowargmax-deferh-pmin015-screen-20260624T173546Z` | `MTP_P_MIN=0.15` | 128/128 | 99.224 | 86.070 | reject; too strict |
| `gemma4-q8-gpu3-rowargmax-deferh-pmin016-screen-20260624T173546Z` | `MTP_P_MIN=0.16` | 128/128 | 99.122 | 86.285 | reject; too strict |

`p_min=0.14` remains the active candidate. The improvement over the previous
row-argmax/defer screen is small (`101.39` vs `101.20` tok/s), so promotion
depends on full validation holding a clear row-0 improvement over the current
`98.617` LocalMaxxing record.

## Full Validation And Promotion

`gemma4-q8-gpu0-rowargmax-deferh-pmin014-full-20260624T173546Z` held the
screen win under the full gate:

- chat canary: **384/384** pass;
- first measured fresh request: **101.42819815648124 tok/s** after TTFT,
  **88.37363393397331 tok/s** wall, TTFT `0.7456772890291177 s`;
- support rows: `8` p512/o512 repeats, mean **100.76942425937877 tok/s**,
  min `99.14362693811911`, max `102.0457439959257`;
- freshness: `--cache-ram 0`, `--ctx-checkpoints 0`, server log repeatedly
  forces full prompt re-processing, and all benchmark rows report
  `usage.prompt_tokens_details.cached_tokens=0`;
- quality: Q8 target/verifier remains authoritative. Only the draft model is
  Q4_0, and no n-gram/history continuation source is used.

LocalMaxxing accepted the row-0 fresh-response payload:

- ID/status: `cmqsd2jpn00pwqr017fq21akz` / `APPROVED`;
- queue:
  `data/localmaxxing-gemma4-26b-a4b-q8-b70-llamacpp-mtp-n7-q8target-q40draft-rowargmax-deferh-pmin014-fresh-20260624.queue.json`;
- response:
  `data/localmaxxing-responses/gemma4-26b-a4b-q8-b70-llamacpp-mtp-n7-q8target-q40draft-rowargmax-deferh-pmin014-fresh-20260624.submit.log`.

Decision: promoted as the current valid fresh-response one-B70 Q8-target
Gemma 4 26B A4B record. It supersedes `cmqs7uyqb00lnqr01u9dtv63r`
(`98.617 tok/s`) for the same filled-long p512/o512-style shape.

## Screen Batch 3: Post-Promotion Followups

These screens used the promoted `p_min=0.14` row-argmax/defer-H stack and one
fresh measured request per GPU. All used `--cache-ram 0`, `--ctx-checkpoints 0`,
no n-gram/history continuation, and Q8 target verification. Headline comparison
is against the promoted fresh row-0 record, `101.42819815648124 tok/s`.

| Run | Change | Canary | Fresh row0 tok/s | Wall tok/s | TTFT s | Decision |
| --- | --- | ---: | ---: | ---: | ---: | --- |
| `gemma4-q8-gpu0-rowargmax-deferh-pmin014-deviceh-screen-20260624T175116Z` | `LLAMA_MTP_DRAFT_DEVICE_H_HANDOFF=1` | 512/512 | 100.895 | 87.761 | 0.759 | valid but below record; reject |
| `gemma4-q8-gpu1-rowargmax-deferh-pmin014-psplit005-screen-20260624T175116Z` | `MTP_P_SPLIT=0.05` | 512/512 | 99.334 | 86.679 | 0.753 | reject; split threshold slows the current stack |
| `gemma4-q8-gpu2-rowargmax-deferh-pmin014-psplit010-screen-20260624T175117Z` | `MTP_P_SPLIT=0.10` | 512/512 | 100.751 | 87.832 | 0.747 | valid but below record; reject |
| `gemma4-q8-gpu3-rowargmax-deferh-pmin014-poll75-screen-20260624T175116Z` | `POLL=75` | 512/512 | 98.932 | 86.475 | 0.745 | reject; lower polling did not improve fresh throughput |

Takeaways:

- Device-H draft handoff is not a win on the current Q8 target/Q4_0 MTP stack.
- `MTP_P_SPLIT` did not recover acceptance or draft cost enough to beat the
  plain `p_min=0.14` record.
- Polling at `75` regressed; keep `POLL=100` unless another code path changes
  scheduling behavior.

## Screen Batch 4: Fine `p_min`, `n=8`, Draft Batch Threads

These screens used the same fresh-response validity rules as Batch 3. The first
attempt to detach this batch without `setsid` was killed before server logs were
created; the valid results below are from the relaunched `20260624T180101Z`
batch.

| Run | Change | Canary | Fresh row0 tok/s | Wall tok/s | TTFT s | Decision |
| --- | --- | ---: | ---: | ---: | ---: | --- |
| `gemma4-q8-gpu0-rowargmax-deferh-pmin0135-screen-20260624T180101Z` | `MTP_P_MIN=0.135` | 512/512 | 99.340 | 86.487 | 0.766 | reject; worse than `0.13` and `0.14` |
| `gemma4-q8-gpu1-rowargmax-deferh-pmin0145-screen-20260624T180101Z` | `MTP_P_MIN=0.145` | 512/512 | 100.741 | 87.644 | 0.759 | valid but below record |
| `gemma4-q8-gpu2-rowargmax-deferh-pmin014-n8-screen-20260624T180101Z` | `MTP_N_MAX=8`, direct unroll `8` | 512/512 | 65.914 | 60.204 | 0.737 | reject; deeper MTP draft is far too expensive |
| `gemma4-q8-gpu3-rowargmax-deferh-pmin014-dtb28-screen-20260624T180101Z` | `MTP_DRAFT_THREADS_BATCH=28` | 512/512 | 99.106 | 86.636 | 0.744 | reject |

Takeaways:

- The `p_min=0.14` value remains the best validated threshold neighborhood.
- Increasing direct unroll to `8` is a clear loss despite valid canaries; it
  increases draft work more than it improves acceptance for fresh responses.
- Draft batch threads `28` is not useful versus `32`.

## Screen Batch 5: Control And Main Thread Count

This batch keeps the promoted `p_min=0.14` row-argmax/defer-H stack and varies
only the main llama.cpp `THREADS` value. It was launched with `setsid` so the
harnesses were not reaped by the parent shell.

| Run | Change | Canary | Fresh row0 tok/s | Wall tok/s | TTFT s | Decision |
| --- | --- | ---: | ---: | ---: | ---: | --- |
| `gemma4-q8-gpu0-rowargmax-deferh-pmin014-control-screen-20260624T180559Z` | control, `THREADS=8` | 512/512 | 100.439 | 87.372 | 0.762 | valid variance check; below record |
| `gemma4-q8-gpu1-rowargmax-deferh-pmin014-th4-screen-20260624T180559Z` | `THREADS=4` | 512/512 | 100.737 | 87.762 | 0.751 | valid but below record |
| `gemma4-q8-gpu2-rowargmax-deferh-pmin014-th12-screen-20260624T180559Z` | `THREADS=12` | 512/512 | 101.046 | 87.749 | 0.768 | close but below record |
| `gemma4-q8-gpu3-rowargmax-deferh-pmin014-th16-screen-20260624T180559Z` | `THREADS=16` | 512/512 | 101.014 | 87.777 | 0.764 | close but below record |

Takeaway: keep `THREADS=8` as the documented record identity for now. `12` and
`16` are plausible near-equivalents but did not produce a fresh row-0 record.

### Full follow-up: `THREADS=16` with immediate command lists

`gemma4-q8-gpu2-rowargmax-safer-immediatecl1-th16-current-20260624T193301Z`
screened at `102.165 tok/s` with a 512-row canary, so it received a full
promotion-depth rerun after the fresh/warmed validity clarification:

- run: `gemma4-q8-gpu2-rowargmax-safer-immediatecl1-th16-full2-20260624T231804Z`
- canary: **1536/1536** pass;
- first fresh p512/o512 row: **99.574647 tok/s** after TTFT,
  **87.123384 tok/s** wall, TTFT `0.734852 s`, `cached_tokens=0`;
- best support row: `101.589434 tok/s` after TTFT, still below the promoted
  `101.602390 tok/s` record;
- repeated-row mean: `101.004142 tok/s`.

Decision: valid but not a record. Do not submit to LocalMaxxing. The earlier
`102.165` screen was normal run-to-run variance and did not hold under the
promotion gate. Keep `THREADS=8` in the promoted identity unless a future
full-gate run beats the current row-0 record.

## Source Experiment: Verifier Multi-Row Argmax Crash

Attempted patch:
`patches/gemma4-26b-a4b-q8-b70/20260624T1810-llamacpp-gemma4-spec-verify-argmaxrows-crash.patch`.

Intent: replace the verifier direct-argmax path's one `ggml_view_1d` +
`ggml_argmax` output per verifier row with a single `ggml_argmax` over the
whole verifier logits tensor, then let the existing sampled-row copy path copy
multiple ids from one tensor. This was meant to reduce graph nodes and backend
copies without changing verifier math.

Runs launched at `20260624T181034Z`:

| Run | Change | Result | Decision |
| --- | --- | --- | --- |
| `gemma4-q8-gpu0-argmaxrows-rowargmax-deferh-pmin014-th8-screen-20260624T181034Z` | multi-row verifier argmax, `THREADS=8` | server aborts on first canary request | crash, invalid |
| `gemma4-q8-gpu1-argmaxrows-rowargmax-deferh-pmin014-th12-screen-20260624T181034Z` | multi-row verifier argmax, `THREADS=12` | server aborts on first canary request | crash, invalid |
| `gemma4-q8-gpu2-argmaxrows-rowargmax-deferh-pmin014-th16-screen-20260624T181034Z` | multi-row verifier argmax, `THREADS=16` | server aborts on first canary request | crash, invalid |
| `gemma4-q8-gpu3-argmaxrows-rowargmax-deferh-pmin014-repeat-screen-20260624T181034Z` | multi-row verifier argmax, repeat | server aborts on first canary request | crash, invalid |

Failure signature:

- no valid canary or benchmark rows were produced;
- server logs all reach `server is listening`, then abort immediately after the
  first slot is selected;
- assertion:
  `/home/steve/src/llama.cpp-gemma-record-stack/src/llama-context.cpp:1821:
  GGML_ASSERT(ggml_nelements(tensor) >= 1) failed`;
- supporting logs:
  `/mnt/fast-ai/bench-results/gemma4-26b-a4b-q8/servers/*argmaxrows*181034Z*.server.log`.

Likely cause: the new path assumes `res->t_logits` is a non-empty matrix whose
`ggml_argmax` result has one element per verifier row. At least one startup
canary path exposes a zero-element or incompatible sampled-row tensor to
`copy_tensor_async_ints_by_row`. Treat this patch as invalid until the row shape
guard/fallback is fixed and a one-GPU canary smoke passes.

## Source Experiment: Guarded Verifier Multi-Row Argmax

Follow-up patch:
`patches/gemma4-26b-a4b-q8-b70/20260624T1815-llamacpp-gemma4-spec-verify-argmaxrows-guard-neutral.patch`.

Change: gated the multi-row verifier `ggml_argmax(res->t_logits)` path on
`ggml_is_matrix(res->t_logits) && res->t_logits->ne[1] > 0` so zero-output
startup/canary graphs do not publish an empty sampled-row tensor.

Validation:

- one-GPU smoke `gemma4-q8-gpu0-argmaxrows-guard-smoke-20260624T181449Z`:
  4/4 canary rows, one fresh benchmark row, `cached_tokens=0`, no crash;
- 4-GPU screen launched at `20260624T181546Z`, all `512/512` canary rows.

| Run | Change | Canary | Fresh row0 tok/s | Wall tok/s | TTFT s | Decision |
| --- | --- | ---: | ---: | ---: | ---: | --- |
| `gemma4-q8-gpu0-argmaxrows-guard-pmin014-th8-screen-20260624T181546Z` | guarded argmaxrows, `THREADS=8` | 512/512 | 100.678 | 87.487 | 0.767 | valid, below record |
| `gemma4-q8-gpu1-argmaxrows-guard-pmin014-th12-screen-20260624T181546Z` | guarded argmaxrows, `THREADS=12` | 512/512 | 101.118 | 88.166 | 0.744 | valid, below record |
| `gemma4-q8-gpu2-argmaxrows-guard-pmin014-th16-screen-20260624T181546Z` | guarded argmaxrows, `THREADS=16` | 512/512 | 101.326 | 88.209 | 0.751 | valid, below record |
| `gemma4-q8-gpu3-argmaxrows-guard-pmin014-repeat-screen-20260624T181546Z` | guarded argmaxrows repeat | 512/512 | 101.420 | 88.275 | 0.752 | valid, just below `101.428` record |

Decision: neutral/safe but not a record. Do not promote into the active record
stack. Revert the working hunk before the next source experiment so subsequent
screens compare against the known `101.42819815648124 tok/s` baseline.

## Source Experiment: Direct-Unroll Sampled Offset Outputs Crash

Attempted patch:
`patches/gemma4-26b-a4b-q8-b70/20260624T1824-llamacpp-gemma4-mtp-direct-offset-sampled-crash.patch`.

Intent: avoid the Gemma4 MTP assistant's direct-unroll sampled-token concat
chain (`sampled_all = concat(sampled_all, sampled, 0)`) by exposing each scalar
sampled token as a separate graph output and copying it into a fixed offset in
the existing direct-sampling output buffer. This was gated behind
`LLAMA_MTP_DRAFT_DIRECT_ARGMAX_OFFSET_OUTPUTS=1`.

Result:

- smoke: `gemma4-q8-gpu0-offsetsampled-smoke-20260624T182358Z`;
- server loaded and became ready, then aborted on the first canary request;
- assertion: `common/sampling.cpp:198: GGML_ASSERT(logits != nullptr) failed`;
- preceding error: `get_logits_ith: invalid logits id 38, reason: no logits`;
- no valid canary or benchmark rows were produced.

Decision: invalid/crash. Do not continue this exact patch. The failure indicates
the direct-sampling/logits plumbing reached an ordinary sampler path with logits
disabled. Even if fixed, this approach replaces one contiguous sampled-token
copy with multiple scalar output copies, so the payoff is uncertain. Revert the
working hunk and keep the current concat-based direct-unroll path as the active
sampling baseline.

## 2026-06-26T0640: Record-Neighborhood Four-GPU Screen

This screen used the later selected-softmax + weighted-sum Q8 record family
(`MTP_N_MAX=7`, `MTP_N_MIN=2`, Q8_K_XL target, Q4_0 MTP draft,
`LLAMA_GEMMA4_MOE_SELECTED_SOFTMAX=1`,
`LLAMA_GEMMA4_MOE_WEIGHTED_SUM=1`, direct draft argmax IDs/unroll7,
q-only assistant inputs, verifier backend argmax IDs, deferred target
`h_nextn`, immediate command lists, VMM off, graph on, `--cache-ram 0`,
`--ctx-checkpoints 0`). The current valid Q8 fresh-response record is
`103.2992004295621 tok/s` row 0 from
`gemma4-q8-gpu0-selectedsoftmax-weightedsum-pmin0136-full-20260625T031510Z`;
later rows or warmed/support rows are not headline candidates.

| Run | Change | Canary | Fresh row0 tok/s | Mean support tok/s | Max support tok/s | Decision |
| --- | --- | ---: | ---: | ---: | ---: | --- |
| `gemma4-q8-gpu0-recordcontrol-th8-pmin0136-screen-20260626T0640Z` | control, `THREADS=8`, `MTP_P_MIN=0.136` | 512/512 | 102.136 | 102.187 | 102.326 | valid negative; below record |
| `gemma4-q8-gpu1-th8-pmin01363-screen-20260626T0640Z` | `THREADS=8`, `MTP_P_MIN=0.1363` | 512/512 | 100.507 | 101.463 | 103.207 | valid negative; warmed/support row approached record but row0 did not |
| `gemma4-q8-gpu2-th16-pmin0136-screen-20260626T0640Z` | `THREADS=16`, `MTP_P_MIN=0.136` | 512/512 | 100.304 | 100.897 | 102.930 | valid negative; four-way TH16 underperformed |
| `gemma4-q8-gpu3-th8-pmin01364-screen-20260626T0640Z` | `THREADS=8`, `MTP_P_MIN=0.1364` | 512/512 | 102.106 | 101.547 | 102.106 | valid negative; below record |

All four row-0 benchmark requests reported `cached_tokens=0`; none used
history/ngram acceleration. The control row was also below the solo full record,
so four-way concurrent screens are still useful for rejecting bad variants but
should not be treated as final ranking evidence near the frontier. Promotion
still requires a clean solo run whose fresh row 0 beats `103.2992004295621`,
followed by the full 1536-row canary gate and LocalMaxxing payload review.

### Solo follow-up: `THREADS=16`, `MTP_P_MIN=0.1362`

The near-record audit suggested one clean solo check of the `THREADS=16` /
`p_min=0.1362` neighborhood, because four-way concurrent screens under-ranked
the control. The first launch
`gemma4-q8-gpu0-solo-th16-pmin01362-screen-20260626T054034Z` was a harness
mistake: it was started as a normal background child and was reaped before the
server initialized. It produced only empty startup files and is not a model
result.

Valid relaunch:
`gemma4-q8-gpu0-solo-th16-pmin01362-screen-20260626T054237Z`.

- canary: **512/512** pass;
- fresh row0: **102.44915018469486 tok/s** after TTFT,
  wall `89.39052456703189 tok/s`, TTFT `0.7300751829752699 s`;
- support mean: `102.3417473612983 tok/s`, max support row
  `102.45621588154003 tok/s`;
- freshness: row0 `usage.prompt_tokens_details.cached_tokens=0`;
- server log:
  `/mnt/fast-ai/bench-results/gemma4-26b-a4b-q8/servers/gemma4-q8-gpu0-solo-th16-pmin01362-screen-20260626T054237Z.server.log`.

Decision: valid negative. `THREADS=16` / `p_min=0.1362` does not beat the
`103.2992004295621 tok/s` record, so do not submit to LocalMaxxing and do not
promote.
baseline.

## Invalid Batch: Missing Verifier Sampled-Row Path

After reverting the guarded verifier sampled-row hunk too aggressively, the
binary still accepted `LLAMA_SPEC_VERIFY_BACKEND_ARGMAX_IDS=1` but no longer
produced verifier sampled IDs. Because direct-verifier mode disables raw logits,
the ordinary sampler asked for logits and crashed:

- batch timestamp: `20260624T182744Z`;
- labels:
  `gemma4-q8-gpu0-rowargmax-deferh-pmin014-control2-screen-20260624T182744Z`,
  `gemma4-q8-gpu1-rowargmax-deferh-pmin014-nmin1-screen-20260624T182744Z`,
  `gemma4-q8-gpu2-rowargmax-deferh-pmin014-nmin3-screen-20260624T182744Z`,
  `gemma4-q8-gpu3-rowargmax-deferh-pmin014-dtb40-screen-20260624T182744Z`;
- assertion: `common/sampling.cpp:198: GGML_ASSERT(logits != nullptr) failed`;
- preceding error: `get_logits_ith: invalid logits id 38, reason: no logits`.

Decision: invalid/non-result. Do not count these as parameter evidence.

## Source Fix: Safer Verifier Sampled-Row Argmax Restored

Patch:
`patches/gemma4-26b-a4b-q8-b70/20260624T1830-llamacpp-gemma4-spec-verify-rowargmax-safer-current.patch`.

The verifier sampled-row block is required whenever
`LLAMA_SPEC_VERIFY_BACKEND_ARGMAX_IDS=1` is used without the separate fused
Gemma4 verifier-output env. Restored it with the stricter shape assertions from
the subagent audit:

- return early only for zero-output graphs;
- assert F32 matrix, contiguous layout, positive vocab dimension, and
  `logits->ne[1] == n_outputs`;
- publish `ggml_argmax(res->t_logits)` as `res->t_sampled_rows[0]`.

Smoke:
`gemma4-q8-gpu0-rowargmax-safer-smoke-20260624T182953Z` passed 4/4 canary rows,
reported `cached_tokens=0`, and measured a single fresh row at
`102.11221569178186 tok/s` after TTFT. This is promising but only a smoke; full
validation was launched immediately as
`gemma4-q8-gpu0-rowargmax-safer-pmin014-full-<stamp>`.

Full validation:
`gemma4-q8-gpu0-rowargmax-safer-pmin014-full-20260624T183044Z` passed the full
promotion gate:

- chat canary: **1536/1536** rows pass (`384` repeats x `4` cases);
- first measured fresh request: **101.4817054635395 tok/s** after TTFT,
  **88.58172166538733 tok/s** wall, TTFT `0.7347291180049069 s`;
- support rows: `8` p512/o512 repeats, mean **101.24898926956536 tok/s**,
  min `99.4556226366289`, max `102.0987495323234`, stdev
  `0.7708151931735473`;
- freshness: `--cache-ram 0`, `--ctx-checkpoints 0`, no n-gram/history source,
  and all benchmark rows report `usage.prompt_tokens_details.cached_tokens=0`;
- quality: Q8 target/verifier remains authoritative. Only the MTP draft model
  is Q4_0.

LocalMaxxing accepted the row-0 fresh-response payload:

- ID/status: `cmqsf630x00r1qr01d1usfo2d` / `APPROVED`;
- queue:
  `data/localmaxxing-gemma4-26b-a4b-q8-b70-llamacpp-mtp-n7-q8target-q40draft-rowargmax-safer-deferh-pmin014-fresh-20260624.queue.json`;
- response:
  `data/localmaxxing-responses/gemma4-26b-a4b-q8-b70-llamacpp-mtp-n7-q8target-q40draft-rowargmax-safer-deferh-pmin014-fresh-20260624.submit.log`.

Decision: promoted as the current valid fresh-response one-B70 Q8-target Gemma
4 26B A4B record. It supersedes `cmqsd2jpn00pwqr017fq21akz`
(`101.42819815648124 tok/s`) by a small but validated fresh row-0 margin.

## Screen Batch 7: Safer Verifier `p_min` Micro-Sweep

After promoting the safer verifier sampled-row path, reran a tight `MTP_P_MIN`
screen around the `0.14` optimum. These are valid fresh-response screens, not
headline records: each run uses one fresh benchmark row, `--cache-ram 0`,
`--ctx-checkpoints 0`, no n-gram/history source, Q8 target verification, and
all row-0 benchmark usages report `cached_tokens=0`.

Current record for comparison:
`gemma4-q8-gpu0-rowargmax-safer-pmin014-full-20260624T183044Z`,
`101.4817054635395 tok/s` first fresh request after TTFT.

| Run | Change | Canary | Fresh row0 tok/s | Wall tok/s | TTFT s | Decision |
| --- | --- | ---: | ---: | ---: | ---: | --- |
| `gemma4-q8-gpu0-rowargmax-safer-pmin0138-screen-20260624T184741Z` | `MTP_P_MIN=0.138` | 512/512 | 99.410 | 86.815 | 0.747 | valid loss |
| `gemma4-q8-gpu1-rowargmax-safer-pmin0140-control-screen-20260624T184741Z` | `MTP_P_MIN=0.140` control repeat | 512/512 | 98.628 | 86.075 | 0.757 | valid loss/noise; does not challenge full record |
| `gemma4-q8-gpu2-rowargmax-safer-pmin0142-screen-20260624T184741Z` | `MTP_P_MIN=0.142` | 512/512 | 101.372 | 88.004 | 0.767 | valid near miss, below record |
| `gemma4-q8-gpu3-rowargmax-safer-pmin0143-screen-20260624T184741Z` | `MTP_P_MIN=0.143` | 512/512 | 101.134 | 87.852 | 0.765 | valid near miss, below record |

Decision: no promotion and no LocalMaxxing submission. The micro-threshold
space appears noise-limited around `0.14`; use these runs as evidence to pivot
back to structural draft-path work rather than further scalar `p_min` tuning.

Important: in the active direct-unroll path,
`common/speculative.cpp` reads the graph-produced greedy sampled IDs directly
and treats each as probability `1.0`; `MTP_P_MIN` does not gate individual draft
steps there. That explains why these p-min screens are noise-limited and should
not be repeated unless the direct-unroll sampling path changes.

## Screen Batch 8: Fused Output Argmax And Deeper Direct-Unroll

These screens target the structural >150 tok/s gap without using history/cache
reuse. All variants remain fresh-response speculative decoding: the draft model
generates candidates for the current request, and the Q8 target/verifier checks
them before acceptance. Each row below passed the 512-row chat canary screen and
reported row-0 `cached_tokens=0`.

| Run | Change | Canary | Fresh row0 tok/s | Wall tok/s | TTFT s | Decision |
| --- | --- | ---: | ---: | ---: | ---: | --- |
| `gemma4-q8-gpu0-rowargmax-safer-fusedoutargmax-screen-20260624T185318Z` | `LLAMA_GEMMA4_MTP_FUSED_OUTPUT_ARGMAX=1`, `n=7`, direct-unroll7 | 512/512 | 99.346 | 86.915 | 0.737 | valid loss; current fused argmax path is not a win |
| `gemma4-q8-gpu1-rowargmax-safer-n8unroll8-screen-20260624T185318Z` | `MTP_N_MAX=8`, direct-unroll8 | 512/512 | 65.999 | 60.247 | 0.741 | valid severe loss |
| `gemma4-q8-gpu2-rowargmax-safer-n9unroll9-screen-20260624T185318Z` | `MTP_N_MAX=9`, direct-unroll9 | 512/512 | 70.796 | 64.219 | 0.741 | valid severe loss |
| `gemma4-q8-gpu3-rowargmax-safer-n10unroll10-screen-20260624T185318Z` | `MTP_N_MAX=10`, direct-unroll10 | 512/512 | 74.420 | 67.153 | 0.745 | valid severe loss |

Decision: no promotion and no LocalMaxxing submission. Increasing direct-unroll
depth beyond 7 is counterproductive on this graph: extra serial assistant
passes cost more than the additional accepted-token opportunity. The plain
fused-output-argmax toggle is also below the record, so future fused work needs
a source-level implementation change, not another env-only rerun.

Subagent/source audit conclusion: the current direct-unroll graph removes the
outer per-token driver loop, but it still serially executes a full Gemma4
assistant stack once per unrolled draft step. Since the recurrence is real
(`token[i+1]` depends on greedy `token[i]` and `h_next[i]`), exact batching is
not available without changing semantics. The next fresh-valid experiment is an
env-gated approximate assistant layer taper: keep early draft steps full-depth
and run later unrolled draft steps through fewer assistant layers, relying on
the Q8 target verifier to reject bad drafts. If acceptance stays high enough,
this directly attacks the seven serial assistant passes without using warmed
history.

## Source Experiment: Assistant Layer Taper

Patch artifact:
`patches/gemma4-26b-a4b-q8-b70/20260624T1900-llamacpp-gemma4-mtp-layer-taper-experiment-current.patch`.

Change: added env-gated direct-unroll layer taper in
`src/models/gemma4-assistant.cpp`:

- `LLAMA_GEMMA4_MTP_LAYER_TAPER_AFTER`;
- `LLAMA_GEMMA4_MTP_LAYER_TAPER_LAYERS`.

Default behavior was unchanged. For example, `AFTER=2, LAYERS=3` keeps draft
steps 0-1 full-depth on the 4-block MTP assistant and runs steps 2+ through only
3 blocks before the output head. This is approximate draft generation, but
fresh-valid because the Q8 target still verifies every accepted token and the
draft source does not use history/cache from previous benchmark repeats.

Validation screens:

| Run | Change | Canary | Fresh row0 tok/s | Wall tok/s | TTFT s | Decision |
| --- | --- | ---: | ---: | ---: | ---: | --- |
| `gemma4-q8-gpu0-rowargmax-safer-taper-after2l3-screen-20260624T185950Z` | full/full/3-layer taper | 512/512 | 60.318 | 55.448 | 0.746 | valid severe loss |
| `gemma4-q8-gpu1-rowargmax-safer-taper-after1l3-screen-20260624T185950Z` | full/3-layer taper | 512/512 | 55.028 | 50.902 | 0.754 | valid severe loss |
| `gemma4-q8-gpu2-rowargmax-safer-taper-after1l2-screen-20260624T185950Z` | full/2-layer taper | 512/512 | 28.333 | 27.225 | 0.736 | valid severe loss |
| `gemma4-q8-gpu3-rowargmax-safer-taper-after3l2-screen-20260624T185950Z` | full/full/full/2-layer taper | 512/512 | 50.619 | 47.128 | 0.749 | valid severe loss |

Decision: revert the working hunk. Taper preserves canary quality because the
target verifier rejects bad drafts, but acceptance drops enough that throughput
collapses. This rules out shallow approximate assistant passes as a route to
`>150 tok/s` on the current benchmark.

## Screen Batch 10: Current-Stack MTP Draft Quant Recheck

After the safer verifier row-argmax record, reran the MTP draft quant family on
the **current** row-argmax/defer-H stack. The older draft-quant sweep was on a
mid-90 tok/s stack, so it did not fully answer whether higher-precision MTP
drafts interact better with the current 101 tok/s path.

First launch at `20260624T190924Z` used `LLAMA_DEVICES=SYCL1/2/3` for the
nonzero-GPU lanes. That is invalid under this harness because
`ONEAPI_DEVICE_SELECTOR=level_zero:<gpu>` exposes the selected card as `SYCL0`
inside each process. Those three lanes exited at argument parsing with
`invalid device: SYCL{1,2,3}` and are launch failures, not benchmark results.
GPU0/Q4_0 was valid and completed.

Corrected relaunch at `20260624T191035Z` used `LLAMA_DEVICES=SYCL0` and
`MTP_DRAFT_DEVICE=SYCL0` inside each selected process. Common identity:

- target/verifier: `gemma-4-26B-A4B-it-UD-Q8_K_XL.gguf`;
- current safer verifier row-argmax + deferred target `h_nextn` source stack;
- `MTP_N_MAX=7`, direct-unroll7, `MTP_N_MIN=2`, `MTP_P_MIN=0.14`;
- backend draft sampling off, `LLAMA_MTP_DRAFT_FAST_ARGMAX=1`;
- q-only assistant attention inputs, f16 target/draft KV;
- `BATCH_SIZE=1024`, `UBATCH_SIZE=1024`, `THREADS=8`, `POLL=100`,
  VMM off, SYCL graph enabled, `--ctx-checkpoints 0`;
- 512 canary rows and one fresh measured `filled-long` row per lane;
- all benchmark row-0 usages reported `cached_tokens=0`.

| Run | Draft | Canary | Fresh row0 tok/s | Wall tok/s | TTFT s | Decision |
| --- | --- | ---: | ---: | ---: | ---: | --- |
| `gemma4-q8-gpu0-rowargmax-safer-draftq40-control-current-20260624T190924Z` | `Q4_0-MTP` control | 512/512 | **101.589** | 88.462 | 0.748 | tiny screen repeat above current record; full validation launched before any claim |
| `gemma4-q8-gpu1-rowargmax-safer-draftq4km-current-retry-20260624T191035Z` | `Q4_K_M-MTP` | 512/512 | 100.893 | 87.648 | 0.767 | valid loss |
| `gemma4-q8-gpu2-rowargmax-safer-draftq5km-current-retry-20260624T191035Z` | `Q5_K_M-MTP` | 512/512 | 98.690 | 86.005 | 0.765 | valid loss |
| `gemma4-q8-gpu3-rowargmax-safer-draftq6k-current-retry-20260624T191035Z` | `Q6_K-MTP` | 512/512 | 100.558 | 87.608 | 0.753 | valid loss |

Decision: Q4_0 remains the best MTP draft quant for the current stack. Higher
precision drafts do not improve acceptance enough to pay for their extra draft
cost. The Q4_0 control screen is only `+0.106%` over the current promoted
`101.4817054635395 tok/s` result, so it is treated as a variance/repeat
candidate and requires promotion-depth validation before any LocalMaxxing
submission.

Full repeat:
`gemma4-q8-gpu0-rowargmax-safer-pmin014-control-fullrepeat-20260624T191431Z`
repeated the exact Q4_0 control at promotion depth:

- canary: **1536/1536** pass;
- benchmark row 0: **101.03988237911875 tok/s** after TTFT,
  `88.28581085996103` wall tok/s, TTFT `0.7320404289639555 s`;
- support mean/min/max: `99.9925454880047` /
  `99.22289110377561` / `101.09857281340831` tok/s;
- cached-token check: all 8 benchmark rows reported `cached_tokens=0`.

Decision: no record and no LocalMaxxing submission. The one-row
`101.58856918659554` screen was normal variance, not a reproducible
improvement over the current `101.4817054635395 tok/s` record.

## Screen Batch 11: Current-Stack Control, Threads, And Smaller One-Shot Batch

Followed the full-repeat loss with four more fresh-response screens on the
current safer stack. These keep the same validity rules as Batch 10: Q8 target
verification, Q4_0 MTP draft, `--cache-ram 0`, `--ctx-checkpoints 0`, no
ngram/history source, 512 canary rows, and row-0 `cached_tokens=0`.

| Run | Change | Canary | Fresh row0 tok/s | Wall tok/s | TTFT s | Decision |
| --- | --- | ---: | ---: | ---: | ---: | --- |
| `gemma4-q8-gpu0-rowargmax-safer-b896u896-current-20260624T192434Z` | `BATCH_SIZE=896`, `UBATCH_SIZE=896` | 512/512 | 99.461 | 86.228 | 0.790 | valid loss; smaller reserve does not help |
| `gemma4-q8-gpu1-rowargmax-safer-control-current-20260624T192434Z` | exact control on GPU1 | 512/512 | 100.974 | 87.839 | 0.758 | valid loss; GPU1 is not a faster replica for this identity |
| `gemma4-q8-gpu2-rowargmax-safer-th12-current-20260624T192434Z` | `THREADS=12` | 512/512 | 99.227 | 86.114 | 0.786 | valid loss |
| `gemma4-q8-gpu3-rowargmax-safer-th16-current-20260624T192434Z` | `THREADS=16` | 512/512 | 101.399 | 87.994 | 0.769 | valid near miss, below record |

Decision: no promotion. `THREADS=16` is close but below the current record and
not worth full validation unless a later source/runtime change shifts the same
identity upward. `BATCH/UBATCH=896` loses enough to make the smaller one-shot
reserve hypothesis weak; `768` remains a lower-priority screen only.

## Screen Batch 12: Runtime Command-List / Copy-Engine Toggles

Tested low-level runtime toggles on the current safer stack. Common validity:
fresh-response draft-MTP, Q8 target verification, Q4_0 MTP draft,
`--cache-ram 0`, `--ctx-checkpoints 0`, no ngram/history source, 512 canary
rows, and row-0 `cached_tokens=0`.

| Run | Change | Canary | Fresh row0 tok/s | Wall tok/s | TTFT s | Decision |
| --- | --- | ---: | ---: | ---: | ---: | --- |
| `gemma4-q8-gpu0-rowargmax-safer-b768u768-current-20260624T192836Z` | `BATCH_SIZE=768`, `UBATCH_SIZE=768` | 512/512 | 101.387 | 88.192 | 0.756 | valid near miss, below record |
| `gemma4-q8-gpu1-rowargmax-safer-immediatecl1-current-20260624T192836Z` | `UR_L0_USE_IMMEDIATE_COMMANDLISTS=1` | 512/512 | **102.058** | 88.740 | 0.753 | screen win; full validation launched |
| `gemma4-q8-gpu2-rowargmax-safer-syclcopy0-current-20260624T192836Z` | `SYCL_PI_LEVEL_ZERO_USE_COPY_ENGINE=0` | 512/512 | 101.343 | 88.153 | 0.756 | valid near miss, below record |
| `gemma4-q8-gpu3-rowargmax-safer-urcopy0-current-20260624T192836Z` | `UR_L0_USE_COPY_ENGINE=0` | 512/512 | 101.245 | 88.132 | 0.752 | valid near miss, below record |

Decision: `UR_L0_USE_IMMEDIATE_COMMANDLISTS=1` is the only candidate worth
promotion-depth validation. The copy-engine toggles and `BATCH/UBATCH=768`
are not records on one-row screens.

## Screen Batch 13: Immediate Command-List Followups

While the `UR_L0_USE_IMMEDIATE_COMMANDLISTS=1` full validation ran on GPU1,
used the other cards for follow-up screens. Same current safer stack and
fresh-response validity as above.

| Run | Change | Canary | Fresh row0 tok/s | Wall tok/s | TTFT s | Decision |
| --- | --- | ---: | ---: | ---: | ---: | --- |
| `gemma4-q8-gpu0-rowargmax-safer-immediatecl1-repeat-current-20260624T193301Z` | `UR_L0_USE_IMMEDIATE_COMMANDLISTS=1` repeat | 512/512 | 101.610 | 88.509 | 0.746 | valid screen above record; weaker than GPU1 screen |
| `gemma4-q8-gpu2-rowargmax-safer-immediatecl1-th16-current-20260624T193301Z` | `UR_L0_USE_IMMEDIATE_COMMANDLISTS=1`, `THREADS=16` | 512/512 | **102.165** | 88.571 | 0.769 | best screen; full validation launched |
| `gemma4-q8-gpu3-rowargmax-safer-immediatecl1-syclcopy0-current-20260624T193301Z` | `UR_L0_USE_IMMEDIATE_COMMANDLISTS=1`, `SYCL_PI_LEVEL_ZERO_USE_COPY_ENGINE=0` | 512/512 | 101.966 | 88.690 | 0.752 | valid screen above record; below `THREADS=16` candidate |

Decision: full validation is now running for both `immediatecl1` and the
stronger `immediatecl1+THREADS=16` identity. Do not submit either unless the
promotion-depth run holds row-0 fresh throughput above the current record with
all benchmark rows showing `cached_tokens=0`.

Full validations:

| Run | Change | Canary | Fresh row0 tok/s | Support mean | Wall tok/s | TTFT s | Decision |
| --- | --- | ---: | ---: | ---: | ---: | ---: | --- |
| `gemma4-q8-gpu1-rowargmax-safer-immediatecl1-full-20260624T193222Z` | `UR_L0_USE_IMMEDIATE_COMMANDLISTS=1`, `THREADS=8` | 1536/1536 | **101.60238982389097** | 100.83458420322299 | 88.50781195831634 | 0.7455485599930398 | valid new fresh-response record |
| `gemma4-q8-gpu2-rowargmax-safer-immediatecl1-th16-full-20260624T193844Z` | `UR_L0_USE_IMMEDIATE_COMMANDLISTS=1`, `THREADS=16` | 1536/1536 | 101.41050472622814 | 100.59377779846547 | 88.53691730607966 | 0.7341118030017242 | valid loss versus new record |

Both full runs had `cached_tokens=0` on all 8 benchmark rows. The `THREADS=16`
screen did not reproduce at full depth; it stays a near-miss only.

LocalMaxxing submission for the new record:

- label:
  `gemma4-26b-a4b-q8-b70-llamacpp-mtp-n7-q8target-q40draft-rowargmax-safer-deferh-pmin014-immediatecl1-fresh-20260624T1932`;
- ID/status: `cmqshlz8j00s0qr01f7lr24oh` / `APPROVED`;
- queue:
  `data/localmaxxing-gemma4-26b-a4b-q8-b70-llamacpp-mtp-n7-q8target-q40draft-rowargmax-safer-deferh-pmin014-immediatecl1-fresh-20260624.queue.json`;
- response:
  `data/localmaxxing-responses/gemma4-26b-a4b-q8-b70-llamacpp-mtp-n7-q8target-q40draft-rowargmax-safer-deferh-pmin014-immediatecl1-fresh-20260624.submit.log`.

Decision: promoted as current valid fresh-response one-B70 Q8-target record,
superseding `cmqsf630x00r1qr01d1usfo2d` /
`101.4817054635395 tok/s` by a small but promotion-depth-validated margin.
Continue optimizing; the research target is still `>150 tok/s`, and this is an
incremental runtime scheduling win rather than a structural MTP-speed solution.

## Screen Batch 14: Immediate Command-List Combination Cleanup

After accepting the `immediatecl1` record, tested the remaining
immediate-command-list combinations. Same current safer stack and
fresh-response validity rules as above.

| Run | Change | Canary | Fresh row0 tok/s | Support mean | Wall tok/s | TTFT s | Decision |
| --- | --- | ---: | ---: | ---: | ---: | ---: | --- |
| `gemma4-q8-gpu0-rowargmax-safer-immediatecl1-urcopy0-current-20260624T195010Z` | `UR_L0_USE_IMMEDIATE_COMMANDLISTS=1`, `UR_L0_USE_COPY_ENGINE=0` | 512/512 | 99.290 | n/a | 86.530 | 0.760 | valid loss |
| `gemma4-q8-gpu1-rowargmax-safer-immediatecl1-th12-current-20260624T195010Z` | `UR_L0_USE_IMMEDIATE_COMMANDLISTS=1`, `THREADS=12` | 512/512 | 101.374 | n/a | 88.311 | 0.747 | valid loss versus new record |
| `gemma4-q8-gpu2-rowargmax-safer-immediatecl1-b768u768-current-20260624T195010Z` | `UR_L0_USE_IMMEDIATE_COMMANDLISTS=1`, `BATCH/UBATCH=768` | 512/512 | 101.170 | n/a | 87.678 | 0.779 | valid loss |
| `gemma4-q8-gpu3-rowargmax-safer-immediatecl1-syclcopy0-full-20260624T195010Z` | `UR_L0_USE_IMMEDIATE_COMMANDLISTS=1`, `SYCL_PI_LEVEL_ZERO_USE_COPY_ENGINE=0` | 1536/1536 | 101.431 | 101.193 | 88.408 | 0.744 | full-depth valid loss |

Decision: the plain `UR_L0_USE_IMMEDIATE_COMMANDLISTS=1`, `THREADS=8`,
copy-engine-default identity remains current. Copy-engine toggles, `THREADS=12`,
`THREADS=16`, and smaller one-shot batch sizes did not hold a better
promotion-depth result.

## Batch 15: immediate-command-list `p_min` refinement around current record

After the `UR_L0_USE_IMMEDIATE_COMMANDLISTS=1` full record, screened nearby
`MTP_P_MIN` values with the same Q8 target / Q4_0 draft / direct-unroll7 /
q-only / safer verifier / defer-H identity. All runs used one benchmark repeat,
`filled-long` 588/512 shape, `cached_tokens=0`, and 32 canary repeats.

| Run | `MTP_P_MIN` | Canary | Fresh row 0 tok/s | Wall tok/s | Decision |
| --- | ---: | ---: | ---: | ---: | --- |
| `gemma4-q8-gpu0-rowargmax-safer-immediatecl1-pmin0139-screen-20260624T200449Z` | 0.139 | 128/128 | 101.021 | 87.804 | valid loss |
| `gemma4-q8-gpu1-rowargmax-safer-immediatecl1-pmin0141-screen-20260624T200449Z` | 0.141 | 128/128 | 101.120 | 87.837 | valid loss |
| `gemma4-q8-gpu2-rowargmax-safer-immediatecl1-pmin0142-screen-20260624T200449Z` | 0.142 | 128/128 | 99.451 | 86.571 | valid loss |
| `gemma4-q8-gpu3-rowargmax-safer-immediatecl1-pmin0145-screen-20260624T200449Z` | 0.145 | 128/128 | 100.993 | 87.977 | valid loss |

No value beat the current full-validated fresh-response record
`101.60238982389097 tok/s` (`cmqshlz8j00s0qr01f7lr24oh`). Keep
`MTP_P_MIN=0.14` as the promoted setting.

## Batch 16: longer-output fresh screens

Screened longer completions with the same promoted immediate-command-list stack
to check whether row-0 after-TTFT decode improves as the generation extends.
These are valid fresh-response screens (`cached_tokens=0`), but only one
benchmark row each, so they are directional unless promoted with full canaries
and repeats. Longer outputs improved wall throughput by amortizing TTFT, but
the after-TTFT headline did not beat the current `101.60238982389097 tok/s`
record.

| Run | Max tokens | Canary | Cached tokens | Fresh row 0 tok/s | Wall tok/s | Completion tokens | Decision |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| `gemma4-q8-gpu0-rowargmax-safer-immediatecl1-o768-screen-20260624T200835Z` | 768 | 64/64 | 0 | 101.238 | 91.990 | 768 | valid loss |
| `gemma4-q8-gpu1-rowargmax-safer-immediatecl1-o1024-screen-20260624T200835Z` | 1024 | 64/64 | 0 | 99.650 | 92.661 | 1024 | valid loss |
| `gemma4-q8-gpu2-rowargmax-safer-immediatecl1-o1536-screen-20260624T200835Z` | 1536 | 64/64 | 0 | 100.639 | 95.710 | 1536 | valid loss |
| `gemma4-q8-gpu3-rowargmax-safer-immediatecl1-o2048-screen-20260624T200835Z` | 2048 | 64/64 | 0 | 100.724 | 96.128 | 1600 | valid loss |

Decision: do not chase max-token length as a headline speed lever under the
current scalar MTP loop. It is useful for wall-throughput service reporting,
but not for the fresh-response after-TTFT record.

## Batch 17: fresh-only `ngram-mod,draft-mtp` combined speculation

Tested `ngram-mod` before `draft-mtp` with one benchmark repeat only. This is
fresh-response valid only for row 0: n-grams may come from the prompt or the
already-generated prefix in the same response, but not from previous benchmark
repeats. Support repeats were intentionally disabled to avoid warmed-history
pollution.

All runs used the promoted Q8 target / Q4_0 draft / direct-unroll7 / q-only /
safer verifier / defer-H / immediate-command-list stack, `n=7`, `n-min=2`,
`p-min=0.14`, backend sampling off, 16 canary repeats, `filled-long` 588/512,
and row-0 `cached_tokens=0`.

| Run | `ngram-mod` match/min/max | Canary | Fresh row 0 tok/s | Wall tok/s | N-gram contribution | Decision |
| --- | --- | ---: | ---: | ---: | --- | --- |
| `gemma4-q8-gpu0-fresh-ngram6-mtp-current-screen-20260624T201350Z` | `6/2/32` | 64/64 | 65.319 | 59.551 | generated 1068, accepted 209 tokens | valid fresh loss; n-gram overhead/rejections dominate |
| `gemma4-q8-gpu1-fresh-ngram8-mtp-current-screen-20260624T201350Z` | `8/2/32` | 64/64 | 67.101 | 60.993 | used enough to slow heavily | valid fresh loss |
| `gemma4-q8-gpu2-fresh-ngram10-mtp-current-screen-20260624T201350Z` | `10/2/32` | 64/64 | 98.490 | 85.946 | 1 draft / 2 accepted tokens | valid fresh loss; effectively MTP plus overhead |
| `gemma4-q8-gpu3-fresh-ngram12-mtp-current-screen-20260624T201350Z` | `12/2/32` | 64/64 | 99.257 | 86.391 | no n-gram draft accepted | valid fresh loss; effectively MTP plus overhead |

Decision: do not use combined `ngram-mod,draft-mtp` for a fresh-response
headline on this benchmark. Short matches can draft from the fresh response but
are too wrong/expensive; longer matches do not contribute enough before MTP.
Keep the earlier high n-gram rows labeled warmed/history only.

## Batch 18: direct-unroll depth under current stack

Screened direct argmax-ID unroll depth with the promoted immediate-command-list
stack. All runs used one benchmark repeat, 16 canary repeats, `filled-long`
588/512, and row-0 `cached_tokens=0`.

| Run | `MTP_N_MAX` / unroll | Canary | Fresh row 0 tok/s | Wall tok/s | Benchmark acceptance | Decision |
| --- | ---: | ---: | ---: | ---: | --- | --- |
| `gemma4-q8-gpu0-immediatecl1-unroll5-screen-20260624T201610Z` | 5 | 64/64 | 87.959 | 78.030 | 424/433 accepted, mean length 5.87 | valid loss; too few tokens per draft |
| `gemma4-q8-gpu1-immediatecl1-unroll6-screen-20260624T201610Z` | 6 | 64/64 | 94.943 | 83.403 | 436/449 accepted, mean length 6.81 | valid loss |
| `gemma4-q8-gpu2-immediatecl1-unroll7-control-screen-20260624T201610Z` | 7 | 64/64 | 101.104 | 87.922 | 445/462 accepted, mean length 7.74 | valid control below full record noise |
| `gemma4-q8-gpu3-immediatecl1-unroll8-screen-20260624T201610Z` | 8 | 64/64 | 66.066 | 60.313 | 451/472 accepted, mean length 8.64 | valid loss; extra layer/work overwhelms added accepts |

Decision: keep `MTP_N_MAX=7` and direct unroll 7. The next structural path is
not "more MTP layers"; it must reduce per-draft decode cost or add a cheap
fresh-valid extension after the MTP draft.

## Batch 19: experimental MTP -> n-gram append chain

Tested a source-level experiment that lets `ngram-mod` append tokens after an
existing `draft-mtp` draft instead of replacing it. The patch was saved for
reference at
`patches/gemma4-26b-a4b-q8-b70/20260624T2020-llamacpp-spec-chain-ngram-append-experiment.patch`
and was gated by `LLAMA_SPEC_CHAIN_NGRAM_APPEND=1`. It was tested with
`SPEC_TYPE=draft-mtp,ngram-mod`, one benchmark repeat only, `cached_tokens=0`,
and the same promoted Q8 target / Q4_0 MTP draft / direct-unroll7 / q-only /
safer verifier / defer-H / immediate-command-list stack.

| Run | `ngram-mod` match/min/max | Canary | Fresh row 0 tok/s | Wall tok/s | N-gram contribution | MTP contribution | Decision |
| --- | --- | ---: | ---: | ---: | --- | --- | --- |
| `gemma4-q8-gpu0-chainappend-ngram6-mtp-current-screen-20260624T202024Z` | `6/2/32` | 64/64 | 50.476 | 46.958 | 1360 generated / 86 accepted tokens | 1241 generated / 971 accepted tokens | valid fresh loss; n-gram append floods verifier with low-value drafts |
| `gemma4-q8-gpu1-chainappend-ngram8-mtp-current-screen-20260624T202024Z` | `8/2/32` | 64/64 | 51.201 | 47.522 | 1173 generated / 78 accepted tokens | 1248 generated / 978 accepted tokens | valid fresh loss; same overhead/rejection pattern |
| `gemma4-q8-gpu2-chainappend-ngram10-mtp-current-screen-20260624T202024Z` | `10/2/32` | 64/64 | 98.420 | 85.694 | 7 generated / 2 accepted tokens | 1355 generated / 1082 accepted tokens | valid fresh loss; effectively MTP plus overhead |
| `gemma4-q8-gpu3-chainappend-ngram12-mtp-current-screen-20260624T202024Z` | `12/2/32` | 64/64 | 98.378 | 85.734 | 7 generated / 2 accepted tokens | 1355 generated / 1082 accepted tokens | valid fresh loss; effectively MTP plus overhead |

Decision: do not promote the chain-append code. It is preserved as a failed
patch artifact, but the active llama.cpp source was reverted to the current
record stack after the run. Fresh-response n-gram extension remains unattractive
for this prompt: short matches are too noisy and long matches appear too late to
move the row-0 headline.

## Batch 20: post-revert current-stack profile/control

After reverting the failed chain-append source hook, rebuilt
`llama-server` and ran a compact profile/control to confirm the active runtime
was back on the current record stack.

Run:
`gemma4-q8-gpu0-current-profile-after-chainappend-revert-20260624T202538Z`

- canary: 64/64
- fresh row 0: 101.049 tok/s after TTFT, 88.247 wall tok/s
- prompt/completion: 588/512
- cached tokens: 0
- `MTP_DRAFT_PROFILE=1`
- profile tail on the benchmark row:
  - target-slot eval: 5066.82 ms / 512 tokens = 101.05 tok/s
  - draft acceptance: 445 accepted / 462 generated, mean acceptance length 7.74
  - MTP profile cumulative: `draft_decode_ms=1353.822` over 194 draft decodes,
    `process_ms=11.354`, `accept_copy_ms=1.981`, no sampler/vocab scan cost

Decision: runtime is back on the valid record family. The cost model is also
clearer: this lane is not acceptance-bound or CPU-sampler-bound. The draft
assistant decode is about 1.35 s of a 5.07 s post-TTFT generation, so deleting
all draft cost would still not reach the `>150 tok/s` target by itself. Further
fresh-response progress needs a larger structural improvement: lower target
verification cost, a more parallel verifier/draft layout, or a target precision
lane that is explicitly accepted as quality-equivalent. Minor threshold,
thread, n-gram, or argmax-output tweaks are expected to remain below record.

## Batch 21: current-stack lower MTP-draft quantization screen

Screened lower-precision MTP draft files under the active Q8_K_XL target stack:
row-argmax safer verifier, deferred target H/next-N, direct argmax IDs with
unroll 7, q-only MTP attention inputs, immediate command lists, p-min 0.14, one
benchmark repeat, `filled-long` 588/512, and row-0 `cached_tokens=0`.

The target/verifier stayed `gemma-4-26B-A4B-it-UD-Q8_K_XL.gguf`, so these are
valid fresh-response screens for the current headline family.

| Run | Draft model | Canary | Fresh row 0 tok/s | Wall tok/s | Decision |
| --- | --- | ---: | ---: | ---: | --- |
| `gemma4-q8-gpu0-current-draftq2k-screen-20260624T202806Z` | `Q2_K-MTP` | 64/64 | 96.354 | 84.225 | valid loss |
| `gemma4-q8-gpu1-current-draftq3ks-screen-20260624T202806Z` | `Q3_K_S-MTP` | 64/64 | 93.322 | 81.908 | valid loss |
| `gemma4-q8-gpu2-current-draftq3km-screen-20260624T202806Z` | `Q3_K_M-MTP` | 64/64 | 98.308 | 85.383 | valid loss; best of this batch but below 101.602 |
| `gemma4-q8-gpu3-current-draftq3kl-screen-20260624T202806Z` | `Q3_K_L-MTP` | 64/64 | 97.629 | 85.363 | valid loss |

Decision: keep `Q4_0-MTP` for the promoted Q8_K_XL target lane. Draft quant is
not the remaining bottleneck under the current stack; lower draft precision
does not recover enough latency and can lose acceptance/shape efficiency.

## Batch 22: Q8_0 target side lane under the current MTP stack

Screened `gemma-4-26B-A4B-it-Q8_0.gguf` as a separate target/verifier lane.
This remains an 8-bit target, but it is not the same quality identity as the
current `UD-Q8_K_XL` headline; keep it separate unless explicitly accepted as
quality-equivalent. All benchmark rows had `cached_tokens=0`.

The harness was also updated to record
`LLAMA_SPEC_VERIFY_FUSED_OUTPUT_ARGMAX` in both the server log and
`summary.json`, because the first fused-verifier screen had an ambiguous
identity.

| Run | Target / draft | Notable knob | Canary | Fresh row 0 tok/s | Wall tok/s | Decision |
| --- | --- | --- | ---: | ---: | ---: | --- |
| `gemma4-q80target-gpu0-current-q40mtp-screen-20260624T203147Z` | Q8_0 target / Q4_0 MTP | current stack | 64/64 | 100.467 | 89.492 | valid side-lane loss; below Q8_K_XL 101.602 |
| `gemma4-q80target-gpu2-current-q80mtp-screen-20260624T203147Z` | Q8_0 target / Q8_0 MTP | current stack | 64/64 | 97.410 | 86.870 | valid loss |
| `gemma4-q80target-gpu0-fusedverify-q40mtp-identity-screen-20260624T203435Z` | Q8_0 target / Q4_0 MTP | `LLAMA_SPEC_VERIFY_FUSED_OUTPUT_ARGMAX=1` | 64/64 | 89.104 | 80.291 | valid loss; fused output argmax is slower on B70 |
| `gemma4-q80target-gpu3-nospec-baseline-screen-20260624T203147Z` | Q8_0 target / no spec | baseline only | 64/64 | 25.201 | 24.471 | informational only; not a candidate |

Decision: do not promote the Q8_0 target lane. The current Q8_K_XL target/Q4_0
MTP record remains faster and has the preferred quality identity. The fused
target-output argmax path is real and logged now, but it is a loss rather than
a verifier-cost breakthrough.

## Batch 23: flash-attention and INT8 KV cache screens

Screened flash attention and q8_0 KV-cache variants under the promoted
Q8_K_XL target/Q4_0 MTP stack. These are fresh-response screens with row-0
`cached_tokens=0`.

| Run | Flash | Target KV | Draft KV | Canary | Fresh row 0 tok/s | Wall tok/s | Decision |
| --- | --- | --- | --- | ---: | ---: | ---: | --- |
| `gemma4-q8-gpu1-current-flashon-screen-20260624T203527Z` | on | f16/f16 | f16/f16 | 64/64 | 98.729 | 86.364 | valid loss |
| `gemma4-q8-gpu2-current-q8kv-screen-20260624T203528Z` | off | q8_0/q8_0 | q8_0/q8_0 | n/a | n/a | n/a | invalid/crash; llama.cpp requires flash-attn for V cache quantization |
| `gemma4-q8-gpu3-current-kq8-vf16-screen-20260624T203528Z` | off | q8_0/f16 | q8_0/f16 | 64/64 | 87.206 | 77.502 | valid loss |
| `gemma4-q8-gpu0-current-flashon-q8kv-screen-20260624T203708Z` | on | q8_0/q8_0 | q8_0/q8_0 | 64/64 | 92.314 | 81.200 | valid loss |
| `gemma4-q8-gpu1-current-flashon-kf16-vq8-screen-20260624T203708Z` | on | f16/q8_0 | f16/q8_0 | 64/64 | 98.334 | 85.732 | valid loss |
| `gemma4-q8-gpu2-current-flashon-kq8-vf16-screen-20260624T203708Z` | on | q8_0/f16 | q8_0/f16 | 64/64 | 96.401 | 84.601 | valid loss |
| `gemma4-q8-gpu3-current-flashon-targetf16-draftq8kv-screen-20260624T203708Z` | on | f16/f16 | q8_0/q8_0 | 64/64 | 98.815 | 86.366 | valid loss; best of this batch but below record |

Decision: keep flash attention off and keep f16 KV for the promoted Q8_K_XL
headline. INT8 KV does not improve this single-session decode shape on B70,
even when flash attention is enabled to satisfy V-cache quantization.

## Batch 24: logged fused verifier on the headline Q8_K_XL target

The GGUF header shows the current `UD-Q8_K_XL` target uses a tied
`token_embd.weight` / output head stored as `Q8_0`, so the existing
Gemma4-specific `LLAMA_SPEC_VERIFY_FUSED_OUTPUT_ARGMAX=1` path is applicable to
the headline target. Re-ran it after adding the fused-verifier env to the
harness identity.

| Run | Canary | Fresh row 0 tok/s | Wall tok/s | Decision |
| --- | ---: | ---: | ---: | --- |
| `gemma4-q8-gpu0-current-fusedverify-identity-screen-20260624T203936Z` | 64/64 | 89.911 | 79.670 | valid loss |

Decision: do not promote the current `mul_mat_argmax` verifier path. It avoids
materializing full logits, but the SYCL fused argmax kernel is slower than the
regular output matmul plus backend argmax path for this shape. The remaining
fresh-response speed gap is not accessible through the existing fused verifier
knob.

## Batch 25: Balanced sampled-token concat in Gemma4 MTP direct unroll

Patch:
`patches/gemma4-26b-a4b-q8-b70/20260624T2047-llamacpp-gemma4-mtp-balanced-sampled-concat-experiment.patch`.

Intent: test whether the Gemma4 assistant direct-unroll sampled-token chain
(`sampled_all = concat(sampled_all, sampled, 0)` each step) was adding graph
overhead. The experiment added an opt-in
`LLAMA_GEMMA4_MTP_BALANCED_SAMPLED_CONCAT=1` path that collects the seven
sampled-token tensors and builds a balanced concat tree at the end. The
current Q8 target/Q4_0 MTP record stack was otherwise unchanged.

Both runs were fresh-response screens: `--cache-ram 0`, `--ctx-checkpoints 0`,
`usage.prompt_tokens_details.cached_tokens=0`, one measured p512/o512 request,
and canaries clean.

| Run | Change | Canary | Fresh row 0 tok/s | Wall tok/s | TTFT s | Decision |
| --- | --- | ---: | ---: | ---: | ---: | --- |
| `gemma4-q8-gpu0-balancedconcat-control-screen-20260624T2047` | control, balanced concat unset | 256/256 | 101.571 | 88.291 | 0.758 | valid control, close to current record variance |
| `gemma4-q8-gpu1-balancedconcat-on-screen-20260624T2047` | `LLAMA_GEMMA4_MTP_BALANCED_SAMPLED_CONCAT=1` | 256/256 | 101.321 | 88.156 | 0.755 | valid slight loss |

Decision: reject and do not promote. The patch is preserved as an experiment
artifact, but the live source/harness opt-in should not remain active because
it adds maintenance surface without a win. The direct-unroll sampled concat is
not the current Q8 fresh-response bottleneck.

## Batch 26: post-cleanup current-stack controls and polling screens

After reverting the balanced sampled-token concat experiment from live source,
re-ran the current promoted Q8_K_XL target / Q4_0 MTP stack plus three small
runtime variations. All runs used one measured p512/o512 request with
`--cache-ram 0`, `--ctx-checkpoints 0`, `filled-long` prompts, and row-0
`usage.prompt_tokens_details.cached_tokens=0`; these are fresh-response
measurements, not warmed/history-accelerated repeats. Canaries completed 256
rows cleanly in every run.

| Run | Change | Canary | Fresh row 0 tok/s | Wall tok/s | TTFT s | Decision |
| --- | --- | ---: | ---: | ---: | ---: | --- |
| `gemma4-q8-gpu0-current-control-after-clean-screen-20260624T2056` | post-cleanup control | 256/256 | 101.335 | 88.202 | 0.752 | valid control; below 101.602 record, within normal variance |
| `gemma4-q8-gpu1-current-draftpoll0-screen-20260624T2056` | `--spec-draft-poll 0` | 256/256 | 99.254 | 86.418 | 0.766 | valid loss |
| `gemma4-q8-gpu2-current-poll125-screen-20260624T2056` | `POLL=125` | 256/256 | 99.254 | 86.599 | 0.754 | valid loss |
| `gemma4-q8-gpu3-current-terminal-logits-only-screen-20260624T2056` | `LLAMA_MTP_DRAFT_TERMINAL_LOGITS_ONLY=1` | 256/256 | 99.510 | 86.689 | 0.761 | valid loss/no-op; no matching source usage found |

Decision: no promotion. Keep the current immediate-command-list Q8 record
stack unchanged. Polling changes and the terminal-logits-only env do not improve
fresh-response throughput. The remaining gap to `>150 tok/s` is not accessible
through these runtime knobs; it requires reducing target verification/accept
overhead, changing the verifier/draft architecture, or an explicitly
quality-accepted faster target identity.

## Batch 27: server-side speculative profile of current Q8 stack

Patch artifact:
`patches/gemma4-26b-a4b-q8-b70/20260624T2101-llamacpp-server-spec-profile-current.patch`.

Intent: add a gated diagnostic profile (`LLAMA_SERVER_SPEC_PROFILE=1`) around the
server speculative loop to split fresh p512/o512 time into draft generation,
target verifier decode, MTP process, verifier sample/accept, common accept, and
emission. This is a profiling patch only; it should not be treated as a promoted
runtime optimization. The harness now forwards/logs `LLAMA_SERVER_SPEC_PROFILE`
so diagnostic runs are self-identifying.

Run:
`gemma4-q8-gpu0-current-serverprofile-20260624T2104Z`. Canaries were
intentionally skipped (`CANARY_REPEATS=0`) to keep this diagnostic fast, so this
is not a headline validity run. The measured p512/o512 row is still a fresh
request: one repeat, `--cache-ram 0`, `--ctx-checkpoints 0`, and row-0
`cached_tokens=0`.

| Metric | Value |
| --- | ---: |
| Fresh row 0 tok/s after TTFT | 101.974 |
| Wall tok/s | 88.502 |
| Prompt eval | 745.15 ms / 588 tokens |
| Generation eval | 5020.87 ms / 512 tokens |
| Acceptance | 444 accepted / 462 generated, mean acceptance length 7.73 |
| Draft profile | `draft_decode_ms=494.659`, `process_ms=1.385`, `accept_copy_ms=0.662` |
| Server profile draft | 495.049 ms / 69 calls / 462 draft tokens |
| Server profile target decode | 5266.581 ms / 69 calls / 1117 target tokens |
| Server profile MTP process | 1.419 ms |
| Server profile verifier sample/accept | 0.275 ms / 66 calls |
| Server profile common accept | 0.686 ms / 66 calls |
| Server profile emission | 0.462 ms / 66 calls |

Decision: this confirms the current Q8 stack is target-verifier-forward bound.
CPU verifier argmax, compact sampled-token extraction, accept bookkeeping,
deferred `h_nextn`, and emission are already below 2 ms total for the measured
request. Deleting all draft work would only move the run toward roughly the
high-130 tok/s range; `>150 tok/s` requires reducing the target verifier decode
cost or increasing fresh-valid accepted tokens per verifier cycle without
history/warmed continuation effects. Do not spend more time on p-min, polling,
thread, draft-quant, n-gram-history, or sampled-token plumbing unless a source
patch changes this cost model.

### Batch 27 correction: split prompt vs generation target decode

Patch artifact:
`patches/gemma4-26b-a4b-q8-b70/20260624T2121-llamacpp-server-spec-profile-split-current.patch`.

The first server profile counted prompt and generation target decode together.
That made the `1117 target tokens` line easy to misread as generation-only
verifier work. A follow-up profiling patch split target decode into prompt and
generation buckets based on whether any slot is in `SLOT_STATE_GENERATING`.

Run:
`gemma4-q8-gpu0-current-serverprofile-split-20260624T212128Z`. Canaries were
again intentionally skipped (`CANARY_REPEATS=0`), so this is diagnostic only,
not a headline validity run. The measured p512/o512 row remained fresh:
`cached_tokens=0`, one repeat, `--cache-ram 0`, and `--ctx-checkpoints 0`.

| Metric | Value |
| --- | ---: |
| Fresh row 0 tok/s after TTFT | 101.429 |
| Wall tok/s | 88.096 |
| Prompt eval | 745.58 ms / 588 tokens |
| Generation eval | 5047.66 ms / 512 tokens |
| Acceptance | 445 accepted / 462 generated, mean acceptance length 7.74 |
| Server profile draft | 494.618 ms / 68 calls / 462 draft tokens |
| Server profile total target decode | 5294.724 ms / 68 calls / 1116 target tokens |
| Server profile target prompt | 745.124 ms / 2 calls / 588 tokens |
| Server profile target generation | 4549.600 ms / 66 calls / 528 tokens |
| Server profile process/sample/accept/emit | 2.485 ms total |

Corrected interpretation: generation target verifier decode is still the
dominant cost, but the live generation verifier work is **528 rows**, not 1116.
The MTP loop averages exactly 8 target rows per generation verifier call
(`528/66`) and costs `68.933 ms/call` (`8.617 ms/row`). Draft generation is
`7.274 ms/call`; process/sample/accept/emission remain noise.

This makes the next useful source target narrower: reduce the cost of the
8-row target verifier decode, or find a fresh-valid way to accept more than
about 7.7 tokens per verifier cycle. Runtime knobs and draft-side sampler
plumbing are already exhausted for the current Q8 identity.

### Batch 28: target decode phase profile and SYCL node profile

Patch artifacts:

- `patches/gemma4-26b-a4b-q8-b70/20260624T2125-llamacpp-server-target-phase-profile-current.patch`
- `patches/gemma4-26b-a4b-q8-b70/20260624T2135-llamacpp-sycl-node-profile-current.patch`

Target phase profile run:
`gemma4-q8-gpu0-current-targetphase-profile-20260624T212452Z`.
Canaries were intentionally skipped; the p512/o512 measured row was still a
fresh request (`cached_tokens=0`, one repeat, `--cache-ram 0`,
`--ctx-checkpoints 0`).

| Metric | Value |
| --- | ---: |
| Fresh row 0 tok/s after TTFT | 101.287 |
| Target decode phase | 5293.292 ms / 68 calls / 1116 rows |
| Target `process_ubatch` | 5154.273 ms |
| Target post-extract | 133.785 ms |
| Target sampled extract | 133.761 ms |
| Draft decode phase | 515.257 ms total |
| Draft `process_ubatch` | 468.038 ms |
| Draft `h_nextn` extract | 5.520 ms |
| Draft sampled extract | 38.599 ms |

The extra phase split confirms the same conclusion as Batch 27: the cost lives
inside target `process_ubatch`, not verifier sampling, sampled-token extraction,
draft `h_nextn`, or response emission.

SYCL node profile run:
`gemma4-q8-gpu0-sycl-nodeprofile-20260624T213527Z`. This is diagnostic-only:
the profiler disables graph and waits around SYCL nodes, so its `72.103 tok/s`
fresh row is not comparable to the headline lane.

Top cumulative nodes at graph 144 showed the verifier target path dominated by
MoE and output projection work:

- `MUL_MAT_ID:ffn_moe_gate_up-0`: 86.564 ms / 21 calls.
- `MUL_MAT:result_output`: 55.696 ms / 123 calls.
- `MUL_MAT:node_2795`: 53.345 ms / 20 calls.
- `MUL_MAT_ID:node_2756`: 50.398 ms / 21 calls.
- `MUL_MAT_ID:node_59`: 47.339 ms / 21 calls.
- `MUL_MAT:ffn_moe_logits-0`: 41.230 ms / 21 calls.

Source inspection after this profile found why verifier batches are expensive:
`ggml_sycl_mul_mat_id` has a single-token fused path only when `ne12 == 1`.
The Gemma verifier uses multi-token target batches (`ne12 == 8`), so it takes
the generic path with host ID copy, CPU grouping, gather, per-expert matmul,
and scatter. That made a multi-token `MUL_MAT_ID` fast path worth testing.

### Batch 29: multi-token SYCL `MUL_MAT_ID` fast path is rejected

Patch artifact:
`patches/gemma4-26b-a4b-q8-b70/20260624T2155-llamacpp-sycl-mulmatid-multitoken-moe-current.patch`.

Intent: add a gated multi-token SYCL `MUL_MAT_ID` path for verifier-shaped
Gemma MoE batches (`src1=[n_embd,1,n_tokens]`, `ids=[n_expert_used,n_tokens]`,
`2 <= n_tokens <= 8`) behind
`LLAMA_SYCL_MUL_MAT_ID_MULTI_TOKEN_FAST=1`. The implementation compiled
successfully in the B70 AOT SYCL build and passed `git diff --check`.

Read-only subagent audit found no obvious compile blocker and agreed the path
should activate for verifier batches with the env flag enabled. It also flagged
two guard gaps to fix before any future revival: the fast path should locally
verify `dst` shape/strides and should not trust unchecked device expert IDs
without a fallback or bounds protection.

Fresh smoke with fast path enabled:
`gemma4-q8-gpu0-mulmatid-multitoken-fast-smoke-20260624T215651Z`.

Control with the same rebuilt binary and flag unset:
`gemma4-q8-gpu0-current-control-20260624T215834Z`.

| Run | Canaries | Fresh tok/s after TTFT | p512/o512 eval time |
| --- | ---: | ---: | ---: |
| Fast path enabled | 32/32 x 4 cases (128 rows) pass | 76.265 | 6713.28 ms / 512 |
| Same binary, flag off | 8/8 x 4 cases (32 rows) pass | 99.414 | 5150.04 ms / 512 |

Decision: reject. The generic multi-token `MUL_MAT_ID` path is slow, but this
first fused kernel is slower still for the real verifier workload. Keep the
patch as a negative artifact, do not enable the flag, and do not submit or
promote. Any future revival needs a lower-cost expert grouping/reuse design,
not this one-kernel-per-token/expert mapping.

Graph-eligibility follow-up:
`gemma4-q8-gpu0-mulmatid-multitoken-graph-smoke-20260624T221137Z`.

Additional patch artifact:
`patches/gemma4-26b-a4b-q8-b70/20260624T2220-llamacpp-sycl-mulmatid-multitoken-graph-current.patch`.

This revision fixed the local `dst` shape/stride guard gap and allowed
eligible multi-token `MUL_MAT_ID` nodes through the SYCL graph compatibility
check. It still ran behind `LLAMA_SYCL_MUL_MAT_ID_MULTI_TOKEN_FAST=1`.

Result: canaries passed (`8 x 4 = 32` rows), and the p512/o512 benchmark was a
fresh request (`cached_tokens=0`), but throughput was only **76.023 tok/s
after TTFT** (`68.573 tok/s` wall), with server-side eval time
`6734.61 ms / 512` and `graphs reused = 96`. This is essentially the same
loss as the first fast-path smoke (`76.265 tok/s`) and far below the current
valid Q8 headline (`101.602 tok/s`).

Decision remains reject. Making the fused `MUL_MAT_ID` path graph-eligible does
not rescue it; the fused kernel itself is too slow for the real verifier
shape. Preserve the patch and result, but keep the flag off and do not promote
this code path.

### Batch 30: post-graph-patch runtime screens

After the rejected `MUL_MAT_ID` fast-path smoke, verified that the env-gated
patch does not damage the default path with the flag off, then used the four
GPUs for a light runtime screen. All rows below are fresh p512/o512 first
requests (`cached_tokens=0`), one measured request, `--cache-ram 0`,
`--ctx-checkpoints 0`; canaries were light (`4 x 4 = 16` rows) and passed.

| Run | Change | Fresh row 0 tok/s | Wall tok/s | Decision |
| --- | --- | ---: | ---: | --- |
| `gemma4-q8-gpu0-current-control-postgraphpatch-20260624T221311Z` | flag-off control after rejected graph patch | 101.401 | 88.573 | default path still healthy |
| `gemma4-q8-gpu0-current-control-repeat2-20260624T221654Z` | current repeat | 99.690 | 86.850 | valid low repeat; no promotion |
| `gemma4-q8-gpu1-current-th16-repeat2-20260624T221654Z` | `THREADS=16` | 102.104 | 88.688 | one-row high, but prior same-lane full validation averaged only 100.594; do not promote from a screen |
| `gemma4-q8-gpu2-current-b1280u1280-screen-20260624T221654Z` | `BATCH_SIZE=1280`, `UBATCH_SIZE=1280` | 99.277 | 86.141 | valid loss |
| `gemma4-q8-gpu3-current-b1536u1536-screen-20260624T221654Z` | `BATCH_SIZE=1536`, `UBATCH_SIZE=1536` | 101.350 | 88.033 | valid but below record |

Decision: no runtime promotion. Larger batch/ubatch values do not help this
fresh-response shape, and `THREADS=16` remains a noisy one-row high rather than
a validated improvement. The durable Q8 headline remains the
`101.602 tok/s` immediate-command-list recipe.

### Batch 31: verifier bonus-row suppression and terminal split are rejected

Read-only subagent audits agreed that the remaining bottleneck is target
verifier work, especially the full-vocab output projection rows after the
Gemma target forward. Two bounded experiments tested whether reducing or
splitting verifier output rows could beat the current `n=7` MTP lane.

Patch artifacts:

- `patches/gemma4-26b-a4b-q8-b70/20260624T2227-llamacpp-spec-verify-no-bonus-row-current.patch`
- `patches/gemma4-26b-a4b-q8-b70/20260624T2231-llamacpp-spec-verify-split-terminal-row-current.patch`

Both patches were reverted from the live source after testing; they remain as
negative artifacts only.

#### No-bonus verifier row

Intent: gate `LLAMA_SPEC_VERIFY_NO_BONUS_ROW=1` so the target verifier does not
materialize the final bonus-token output row. The target still decoded the
terminal draft token with `output=false`, so this only removed the output row,
not the terminal token's MoE body. It also changed the server cadence by
emitting fewer tokens per verifier cycle.

Four-lane fresh screen, all with light canaries passing (`4 x 4 = 16` rows):

| Run | Change | Fresh tok/s after TTFT | Wall tok/s | Decision |
| --- | --- | ---: | ---: | --- |
| `gemma4-q8-gpu0-control-postnobonus-screen-20260624T2228Z` | current control | 101.218 | 88.106 | healthy control |
| `gemma4-q8-gpu1-nobonus-n7-screen-20260624T2228Z` | no-bonus, `n=7` | 82.868 | 73.825 | reject |
| `gemma4-q8-gpu2-nobonus-n8-screen-20260624T2228Z` | no-bonus, `n=8` | 69.188 | 62.843 | reject |
| `gemma4-q8-gpu3-nobonus-n9-screen-20260624T2228Z` | no-bonus, `n=9` | 54.716 | 50.671 | reject |

Decision: reject. Suppressing the bonus output row alone is much slower than
the current recipe. It does not avoid the terminal token's target MoE work and
loses the bonus-token throughput shape.

#### True terminal-row split

Intent: gate `LLAMA_SPEC_VERIFY_SPLIT_TERMINAL_ROW=1` so the first target pass
decodes `sampled + D0..D5`, verifies `D0..D6`, and only on full accept runs a
one-token terminal decode for `D6` to produce the bonus token and update MTP
pending hidden state. This preserves full-accept semantics while skipping the
terminal target row on partial rejects.

The first attempt crashed during canary because the server assertion still
required `spec_i_batch.size() == n_draft + 1`; that was fixed in the tested
patch. The valid rerun:
`gemma4-q8-gpu1-splitterminal-n7-profile-screen2-20260624T2232Z`.

Result: canaries passed (`4 x 4 = 16` rows), and the measured p512/o512 request
was fresh (`cache-ram 0`; no cache reuse), but throughput was only
**79.731 tok/s after TTFT** (`71.578 tok/s` wall), far below the `101.602 tok/s`
headline. Server profile explains the loss:

- control profile (`gemma4-q8-gpu0-control-splitprofile-screen-20260624T2231Z`):
  target generation `6533.679 ms / 98 calls / 784 tokens`, about
  `66.67 ms/call` and `8.33 ms/token`;
- split-terminal profile: target generation `8088.933 ms / 173 calls / 758 tokens`,
  about `46.76 ms/call` but **10.67 ms/token**.

Decision: reject. The smaller verifier first pass is cheaper per call, but the
extra terminal decodes nearly double generation decode-call count and increase
target generation time per useful token. Do not promote this split unless a
future implementation can fuse or cheaply queue the terminal row without an
extra full decode call.

Current implication: output-row tricks are exhausted at this level. The next
fresh-response improvements need a real reduction in target verifier compute,
not just output masking: a faster exact multi-token Gemma MoE verifier path,
better output projection/argmax fusion than the rejected fused-output attempt,
or a quality-safe draft strategy that raises accepted tokens without increasing
target rows.

### Batch 32: host/draft thread scheduling after current record

After the `101.60238982389097 tok/s` fresh-response record, a cheap four-GPU
screen tested nearby host and draft-thread scheduling knobs under the same
record identity. All headline values below are the first fresh p512/o512-style
row only with `cached_tokens=0`; repeated or warmed rows were not used.

Common identity: Q8 target + Q4_0 MTP draft, `MTP_N_MAX=7`, `MTP_N_MIN=2`,
`MTP_P_MIN=0.14`, backend sampling off, direct argmax IDs/unroll7, q-only
assistant inputs, verifier backend argmax IDs, deferred target `h_nextn`,
`UR_L0_USE_IMMEDIATE_COMMANDLISTS=1`, `BATCH_SIZE=1024`,
`UBATCH_SIZE=1024`, `POLL=100`, VMM off, SYCL graph enabled,
`--ctx-checkpoints 0`.

| Run | Variant | Canary | Fresh row0 tok/s | Wall tok/s | TTFT s | Decision |
| --- | --- | ---: | ---: | ---: | ---: | --- |
| `gemma4-q8-gpu0-current-th6-screen-20260624T234116Z` | `THREADS=6` | 32/32 | 101.215354 | 88.079299 | 0.754423 | valid loss |
| `gemma4-q8-gpu1-current-th10-screen-20260624T234116Z` | `THREADS=10` | 32/32 | 100.853111 | 87.423276 | 0.779874 | valid loss |
| `gemma4-q8-gpu2-current-dt16-screen-20260624T234116Z` | `MTP_DRAFT_THREADS=16`, batch 32 | 32/32 | 99.140350 | 86.442428 | 0.758622 | valid loss |
| `gemma4-q8-gpu3-current-dtb16-screen-20260624T234116Z` | `MTP_DRAFT_THREADS_BATCH=16`, draft 32 | 32/32 | 99.411301 | 86.624442 | 0.760252 | valid loss |

Decision: these scheduling tweaks do not beat the current valid fresh-response
record. Keep `THREADS=8`, `MTP_DRAFT_THREADS=32`, and
`MTP_DRAFT_THREADS_BATCH=32` for the record recipe.

### Batch 33: CPU affinity screen

Read-only audit found that CPU placement had not been isolated on the final
record stack. This batch used `taskset` around the same record identity as
Batch 32. All headline values below are first fresh p512/o512-style rows with
`cached_tokens=0`.

| Run | CPU affinity | Threads | Canary | Fresh row0 tok/s | Wall tok/s | TTFT s | Decision |
| --- | --- | ---: | ---: | ---: | ---: | ---: | --- |
| `gemma4-q8-gpu0-affinity0-7-th8-screen-20260624T234621Z` | `0-7` | 8 | 32/32 | 101.375346 | 88.437640 | 0.738853 | valid loss |
| `gemma4-q8-gpu1-affinity8-15-th8-screen-20260624T234622Z` | `8-15` | 8 | 32/32 | 101.423996 | 88.431406 | 0.741683 | valid loss |
| `gemma4-q8-gpu2-affinity16-23-th8-screen-20260624T234622Z` | `16-23` | 8 | 32/32 | 98.653850 | 86.425055 | 0.734345 | valid loss; sibling-heavy placement likely bad |
| `gemma4-q8-gpu3-affinity0-15-th16-screen-20260624T234622Z` | `0-15` | 16 | 32/32 | 101.388961 | 88.537378 | 0.733009 | valid loss |

Decision: affinity affects the noisy frontier but does not beat the promoted
fresh-response record. Avoid the `16-23` slice for record attempts; otherwise
default scheduler placement remains acceptable.

### Batch 34: main-thread fine sweep

This batch tested untried `THREADS` values around the noisy `THREADS=16`
screen high. Same current record identity as Batches 32-33; all headline
values are first fresh p512/o512-style rows with `cached_tokens=0`.

| Run | Threads | Canary | Fresh row0 tok/s | Wall tok/s | TTFT s | Decision |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| `gemma4-q8-gpu0-current-th14-screen-20260624T234756Z` | 14 | 32/32 | 99.532998 | 86.552583 | 0.771456 | valid loss |
| `gemma4-q8-gpu1-current-th15-screen-20260624T234756Z` | 15 | 32/32 | 99.480289 | 86.621387 | 0.764032 | valid loss |
| `gemma4-q8-gpu2-current-th17-screen-20260624T234756Z` | 17 | 32/32 | 101.482068 | 88.128617 | 0.764464 | valid but below record |
| `gemma4-q8-gpu3-current-th18-screen-20260624T234756Z` | 18 | 32/32 | 100.974894 | 87.961092 | 0.750188 | valid loss |

Decision: no promotion. The earlier `THREADS=16` screen high remains a noisy
outlier; neighboring thread counts do not beat the promoted record.

### Batch 35: high-side draft-thread sweep on final stack

Read-only audit suggested checking high-side draft-thread settings on the
current record stack. This batch used the same valid fresh-response identity as
Batches 32-34. Headline values are the first p512/o512-style row only with
`cached_tokens=0`; repeated or warmed rows are not used for headline claims.

| Run | Variant | Canary | Fresh row0 tok/s | Wall tok/s | TTFT s | Decision |
| --- | --- | ---: | ---: | ---: | ---: | --- |
| `gemma4-q8-gpu0-current-dt28-screen` | `MTP_DRAFT_THREADS=28`, batch 32 | 32/32 | 99.186466 | 86.547881 | 0.753806 | valid loss |
| `gemma4-q8-gpu1-current-dt36-screen` | `MTP_DRAFT_THREADS=36`, batch 32 | 32/32 | 99.032917 | 86.133128 | 0.774288 | valid loss |
| `gemma4-q8-gpu2-current-dtb36-screen` | draft 32, `MTP_DRAFT_THREADS_BATCH=36` | 32/32 | 101.554788 | 87.944532 | 0.780238 | valid but below record |
| `gemma4-q8-gpu3-current-dtb40-screen` | draft 32, `MTP_DRAFT_THREADS_BATCH=40` | 32/32 | 101.199834 | 87.968610 | 0.760961 | valid loss |

Decision: no promotion. `dtb36` is close to the `101.60238982389097 tok/s`
record, but still below it and not worth a full validation run. Runtime thread
and affinity sweeps are now exhausted enough to stop spending GPU time on them.
The remaining route to a meaningful fresh-response gain is source-level target
verifier work, especially Gemma MoE/router paths, not host scheduling.

### Batch 36: intermediate batch / ubatch geometry screen

This batch tested the remaining audit-suggested batch geometry settings on the
same current record stack. Headline values are first fresh p512/o512-style rows
with `cached_tokens=0`; no warmed or repeated continuation rows are counted.

| Run | Batch | UBatch | Canary | Fresh row0 tok/s | Wall tok/s | TTFT s | Decision |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| `gemma4-q8-gpu0-current-b1152u1152-screen` | 1152 | 1152 | 32/32 | 101.276347 | 88.055649 | 0.759030 | valid loss |
| `gemma4-q8-gpu1-current-b1344u1344-screen` | 1344 | 1344 | 32/32 | 99.284496 | 86.354109 | 0.772177 | valid loss |
| `gemma4-q8-gpu2-current-b1536u1024-screen` | 1536 | 1024 | 32/32 | 100.842599 | 87.592775 | 0.768012 | valid loss |
| `gemma4-q8-gpu3-current-b1024u768-screen` | 1024 | 768 | 32/32 | 99.495833 | 86.786201 | 0.753611 | valid loss |

Decision: no promotion. Keep the promoted `BATCH_SIZE=1024`,
`UBATCH_SIZE=1024` recipe. Runtime geometry, host scheduling, draft-thread,
affinity, `p_min`, `n_max`, and output-row tricks have all failed to produce a
fresh-response improvement over the `101.60238982389097 tok/s` record.

### Current profile after runtime sweeps

Diagnostic run `gemma4-q8-gpu0-current-mtp-server-profile` used
`LLAMA_MTP_DRAFT_PROFILE=1` and `LLAMA_SERVER_SPEC_PROFILE=1` on the current
record identity. It is not a record run, but the measured row was still a fresh
request (`cached_tokens=0`, one p512/o512-style benchmark row).

| Metric | Value |
| --- | ---: |
| Fresh row0 tok/s after TTFT | 99.570184 |
| Wall tok/s | 87.158830 |
| Canary | 8/8 |
| Benchmark acceptance | 445 accepted / 459 generated, mean acceptance length 7.74 |
| Final server profile draft | 926.058 ms / 196 calls / 907 draft tokens |
| Final server profile target decode | 14998.904 ms / 196 calls / 2865 target rows |
| Final server profile target generation | 8585.052 ms / 130 calls / 1037 rows |
| Final target decode phase `process_ubatch` | 14673.501 ms |
| Final target sampled extract | 311.537 ms |

Interpretation: the remaining gap is target verifier compute inside
`process_ubatch`; draft decode, host processing, acceptance, sampled-row copy,
and response emission are smaller. Future work should focus on source-level
Gemma target verifier paths (MoE/router and `MUL_MAT_ID` behavior), not more
runtime knob sweeps.

### Route-profile diagnostics for `MUL_MAT_ID`

Added default-off SYCL diagnostic instrumentation to the llama.cpp stack to
measure how many routed MoE rows and unique experts the generic
`ggml_sycl_mul_mat_id` path sees. Patch snapshots:

- `patches/gemma4-26b-a4b-q8-b70/20260625T000652Z-llamacpp-sycl-mulmatid-route-profile-current.patch`
- `patches/gemma4-26b-a4b-q8-b70/20260625T001738Z-llamacpp-sycl-mulmatid-route-profile-bucketed.patch`

Diagnostic runs, both fresh-response and not record submissions:

| Run | Canary | Fresh row0 tok/s | Wall tok/s | TTFT s | Notes |
| --- | ---: | ---: | ---: | ---: | --- |
| `gemma4-q8-gpu0-current-mulmatid-routeprofile` | 32/32 | 102.051381 | 88.973931 | 0.737414 | aggregate route profile only |
| `gemma4-q8-gpu0-current-mulmatid-routeprofile-bucketed` | 8/8 | 102.086969 | 89.105617 | 0.730659 | bucketed by token count |

Bucketed route-profile result at the end of the fresh p512/o512-style row:

| Bucket | Calls | Avg tokens | Avg routed rows | Avg global unique experts | Avg repeated rows | Avg max expert rows |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `tok2_8` | 5040 | 7.857 | 62.857 | 25.784 | 37.073 | 6.508 |
| `tok33p` | 540 | 98.778 | 790.222 | 60.144 | 730.078 | 69.322 |
| `tok1` | 20 | 1.000 | 8.000 | 8.000 | 0.000 | 1.000 |

Interpretation: the steady verifier bucket is effectively the 8-token path
(`src1=[704,8,8]`, `dst=[2816,8,8]`). It routes about 63 rows but still touches
about 26 unique experts per `MUL_MAT_ID` call, so each active expert receives
only a few rows on average. This explains why the earlier broad
`LLAMA_SYCL_MUL_MAT_ID_MULTI_TOKEN_FAST` attempt was not a win: simply grouping
rows by expert does not make large, efficient matmuls; it creates many tiny
expert groups and launch/dispatch overhead remains dominant. The next source
experiment should target the 8-token verifier shape specifically, either by
fusing the per-expert work for this narrow shape or by reducing the generic
host wait/gather/scatter overhead around `MUL_MAT_ID`. More runtime sweeps are
unlikely to move the record.

### Batch 37: grouped Q8_0 multi-token `MUL_MAT_ID` is rejected

Patch snapshot:

- `patches/gemma4-26b-a4b-q8-b70/20260625T004122Z-llamacpp-sycl-mulmatid-grouped-q8-0-current.patch`

Change: added a default-off SYCL Q8_0 grouped multi-token `MUL_MAT_ID` path
behind `LLAMA_SYCL_MUL_MAT_ID_MULTI_TOKEN_GROUPED_Q8_0=1`. The experiment
keeps the existing per-token/per-slot output order, covers both Gemma gate/up
(`src1` rows per token = 1) and down projection (`src1` rows per token =
`n_expert_used`), and uses a route-leader rule so the first routed row for an
expert computes the matching token/slot group while duplicate route rows exit
early. The code built successfully in
`/home/steve/src/llama.cpp-gemma-record-stack/build-sycl-b70-aot-bmg-g31`.

Fresh-response results:

| Run | Change | Canary | Fresh row0 tok/s | Wall tok/s | TTFT s | Decision |
| --- | --- | ---: | ---: | ---: | ---: | --- |
| `gemma4-q8-gpu0-mulmatid-grouped-q80-smoke` | grouped Q8_0 path enabled | 32/32 | 90.306307 | 79.873160 | 0.740570 | reject |
| `gemma4-q8-gpu1-control-post-groupedpatch-smoke` | same build, grouped flag off | 8/8 | 99.805947 | 87.318372 | 0.733645 | control, no default-path regression |

Both measured rows are fresh p512/o512-style requests with
`usage.prompt_tokens_details.cached_tokens=0`; neither uses n-gram/history
continuation. The grouped path is correct on the canary but substantially
slower than both the same-build control and the current promoted fresh record
(`101.602390 tok/s`).

Decision: keep the patch snapshot as a failed experiment, but do not promote
or submit. This result says the generic grouped `MUL_MAT_ID` path remains
better than this custom route-leader MMV shape even after avoiding the broad
host wait/sort approach. Future MoE work should move up a level: either fuse a
Gemma4 fixed-shape verifier MoE path that accumulates selected experts directly
into `moe_out`, or fuse router top-k plus selected-weight normalization so the
downstream MoE kernels receive better device-side route metadata. Do not spend
more time on another per-row `MUL_MAT_ID` replacement unless profiling shows a
different shape than the current 8-token verifier bucket.

### Batch 38: selected-logit softmax is correct but not a headline record

Patch snapshot:

- `patches/gemma4-26b-a4b-q8-b70/20260625T0050-llamacpp-gemma4-moe-selected-softmax-current.patch`

Change: added `LLAMA_GEMMA4_MOE_SELECTED_SOFTMAX=1`, a default-off Gemma4 MoE
router path that uses `SOFTMAX_WEIGHT` with `norm_w=false` instead of the
default full-expert `SOFTMAX` with selected-weight renormalization. This is
mathematically equivalent for Gemma4's current router because top-k selection is
monotonic over logits and:

`softmax(all_logits)[selected] / sum(softmax(all_logits)[selected]) == softmax(selected_logits)`.

The first smoke looked promising:

| Run | Canary | Fresh row0 tok/s | Wall tok/s | TTFT s | Decision |
| --- | ---: | ---: | ---: | ---: | --- |
| `gemma4-q8-gpu0-moe-selected-softmax-smoke` | 32/32 | 101.687018 | 88.707142 | 0.736744 | screen win only |

Full validation did not hold as a headline record:

| Run | Canary | Fresh row0 tok/s | Support-row mean | Support-row max | Decision |
| --- | ---: | ---: | ---: | ---: | --- |
| `gemma4-q8-gpu0-moe-selected-softmax-full` | 1536/1536 | 99.842703 | 101.245173 | 101.777193 | valid but no headline record |

Validity notes:

- The eligible headline is row 0 only. It reports
  `usage.prompt_tokens_details.cached_tokens=0`, but it is below the current
  `101.602390 tok/s` LocalMaxxing record.
- Later repeated p512/o512 rows also report `cached_tokens=0`, but they reuse
  the same prompt/output shape and are support rows only under the fresh-response
  rule. They must not be averaged into a fresh-response headline or submitted as
  a new record.
- Quality held: the full run passed 1536/1536 canary rows.

Decision: keep the patch as a correct, low-risk optimization candidate, but do
not submit or promote as a record. The next cheap router experiment is replacing
`ggml_argsort_top_k` with `ggml_top_k` for the safe Gemma4 selected-softmax
case. That may remove full argsort work, but it can reorder selected experts,
so it must be canary-gated and treated as a separate experiment.

### Batch 39: `ggml_top_k` router selection is rejected

Patch snapshot:

- `patches/gemma4-26b-a4b-q8-b70/20260625T0102-llamacpp-gemma4-moe-selected-softmax-topk-current.patch`

Change: added `LLAMA_GEMMA4_MOE_TOP_K=1`, a default-off graph path that uses
`ggml_top_k` instead of `ggml_argsort_top_k` only for the safe Gemma4
selected-softmax case (`LLAMA_GEMMA4_MOE_SELECTED_SOFTMAX=1`,
`SOFTMAX_WEIGHT`, no expert bias/groups, `n_expert_used <= 32`). Warmup and
unsupported cases fall back to the old argsort path.

| Run | Canary | Fresh row0 tok/s | Wall tok/s | TTFT s | Decision |
| --- | ---: | ---: | ---: | ---: | --- |
| `gemma4-q8-gpu0-moe-selected-softmax-topk-smoke` | 32/32 | 99.712232 | 87.135831 | 0.741107 | reject |

The run is valid fresh-response (`cached_tokens=0`) and quality-clean, but it
is slower than the current record and the selected-softmax-only smoke. The
likely explanation is that `TOP_K` avoids full sort work but returns unsorted
experts, changing the expert-slot accumulation order and/or missing the
backend's optimized argsort+view path. Do not promote. The router-only cheap
levers are exhausted for now; the next serious source target is the
explorer-recommended fused down-projection + route-weight multiply +
expert-slot sum.

### Batch 40: post-down MoE weighted-sum op is correct but slower

Patch snapshots:

- `patches/gemma4-26b-a4b-q8-b70/20260625T012904Z-llamacpp-gemma4-moe-weighted-sum-current-stack.patch`
- `patches/gemma4-26b-a4b-q8-b70/20260625T012904Z-results-harness-gemma4-moe-weighted-sum-env-capture.patch`
- `patches/gemma4-26b-a4b-q8-b70/20260625T013307Z-llamacpp-gemma4-moe-weighted-sum-fixed-current-stack.patch`

Change: added a default-off `LLAMA_GEMMA4_MOE_WEIGHTED_SUM=1` path that leaves
the existing selected-expert down projections unchanged, then replaces
`experts * weights` plus the per-expert view/add aggregation tail with a single
`GGML_OP_MOE_WEIGHTED_SUM` F32 reduction op. This tested whether the cheap MoE
aggregation tail was worth fusing before attempting the more invasive
`mul_mat_id_wsum` path that would fuse quantized down projection, route-weight
multiply, and selected-expert accumulation.

| Run | Canary | Fresh row0 tok/s | Wall tok/s | TTFT s | Decision |
| --- | ---: | ---: | ---: | ---: | --- |
| `gemma4-q8-gpu0-moe-weighted-sum-smoke` | 32/32 | 99.076992 | 86.790627 | 0.731556 | invalid implementation |
| `gemma4-q8-gpu0-moe-weighted-sum-fixed-smoke` | 32/32 | 101.914054 | 89.034618 | 0.726731 | screen only |
| `gemma4-q8-gpu0-moe-weighted-sum-fixed-full` | 1536/1536 | 100.156309 | 87.667661 | 0.728228 | valid, no record |

Important correction: the first smoke was an implementation mistake, not a
valid test of the intended fusion. The graph originally computed
`experts = ggml_mul(experts, weights)` and then fed that already weighted tensor
into `ggml_moe_weighted_sum(experts, weights)`, so route weights were applied
twice and the old multiply node was still present. The fixed patch moves the
fused op before `ffn_moe_weighted`, consumes unweighted down-projection output,
and skips the old `mul + view/add` tail.

Validity notes:

- All measured headline rows above are fresh-response rows:
  `usage.prompt_tokens_details.cached_tokens=0`.
- Run identity captured `llama_gemma4_moe_weighted_sum=1`, so the experiment is
  distinguishable from the current record config.
- Quality held for the full fixed gate (`1536/1536` canary rows), but the full
  fresh row settled at `100.156309 tok/s`, below the current valid fresh record
  (`101.602390 tok/s`). Do not submit the lucky fixed smoke row; it did not hold
  under full validation.

Decision: keep the default-off patch as a correct research artifact, but do not
promote it as the active record path. It removes some graph nodes, but the
tail-only fusion is too small to reliably beat the existing schedule. Future MoE
fusion should skip this intermediate tail-only form and move to the
subagent-recommended full fused selected-down path: `mul_mat_id_wsum` consuming
down-expert weights, hidden states, selected expert IDs, and selected route
weights, producing the final MoE contribution directly.

### Batch 41: fused selected-down weighted-sum path is correct but not faster

Patch snapshots:

- `patches/gemma4-26b-a4b-q8-b70/20260625T021258Z-llamacpp-gemma4-moe-fused-down-weighted-sum-current-stack.patch`
- `patches/gemma4-26b-a4b-q8-b70/20260625T023418Z-llamacpp-gemma4-moe-fused-down-weighted-sum-scale-current-stack.patch`

Change: added a default-off `LLAMA_GEMMA4_MOE_FUSED_DOWN_WEIGHTED_SUM=1` path
with a new `GGML_OP_MOE_SELECTED_DOWN_WEIGHTED_SUM` SYCL op. The intent was the
full MoE tail fusion that Batch 40 deliberately avoided: consume selected down
expert weights, route IDs, route weights, and hidden states, then emit the final
MoE contribution directly.

Important engineering notes:

- The first implementation could create an op that the SYCL scheduler did not
  assign during the common empty warmup path. The fix was not a fake CPU
  fallback; it was stricter graph-side support guards matching the backend:
  contiguous selected IDs/weights, expected strides, selected count shape ties,
  supported hidden/down dimensions, and scale shape/stride checks.
- The branch fires on decode layers for the common shape
  `cur=[704,8,1,1]`, selected IDs `[8,1,1,1]`, selected weights `[1,8,1,1]`,
  and down weights `q8_0[704,2816,128,1]`. Layer 29 is skipped because its
  down weight is `bf16`. Prefill/multi-token buckets are skipped by guard
  because their selected IDs are not the supported contiguous decode shape.
- The scale-aware guarded path is correct, but the extra packing/quantization
  work in the fused op does not beat the existing `MUL_MAT_ID` route on the
  headline p512/o512 fresh decode shape.

| Run | Canary | Fresh row0 tok/s | Wall tok/s | Decision |
| --- | ---: | ---: | ---: | --- |
| `gemma4-q8-gpu0-moe-fused-down-wsum-smoke` | 128/128 | 101.606057 | 88.660977 | screen-level tie; not promoted because later scale-aware guarded runs were slower |
| `gemma4-q8-gpu0-moe-fused-down-wsum-scale3-guard-smoke` | 128/128 | 99.434317 | 87.001101 | valid loss |

Decision: keep the patch and notes as a useful negative result, but do not
submit or promote this path as a record. If revisiting MoE fusion, avoid the
current Q8_1 scratch/packing approach and consider a direct Q8_0-weight x F32
hidden fused kernel for the fixed decode shape, or first prove with profiling
that `MUL_MAT_ID` is still material after the verifier/MTP argmax wins.

### Batch 42: four-way fresh-response screen after MoE fusion work

Purpose: use all four B70s to screen the current record lane and the two
surviving MoE toggles under the fresh-response rule. All rows below are row 0
of a one-request p512/o512 filled-long benchmark, with
`usage.prompt_tokens_details.cached_tokens=0`. Because these are single-row
screens, they only promote a candidate to full validation; they are not
LocalMaxxing-submittable records by themselves.

Common identity: Q8 target UD-Q8_K_XL, Q4_0 MTP draft, `MTP_N_MAX=7`,
`MTP_N_MIN=2`, `MTP_P_MIN=0.14`, backend sampling off, fast/direct argmax IDs
with unroll 7, q-only Gemma4Assistant attention inputs, safer verifier
row-argmax IDs, deferred target `h_nextn`, `--ctx-checkpoints 0`,
`UR_L0_USE_IMMEDIATE_COMMANDLISTS=1`, `BATCH_SIZE=1024`,
`UBATCH_SIZE=1024`, `POLL=100`, VMM off, SYCL graph enabled.

| Run | Variant | Canary | Fresh row0 tok/s | Wall tok/s | Decision |
| --- | --- | ---: | ---: | ---: | --- |
| `gemma4-q8-gpu0-current-control-repeat-20260625T0254Z` | control, `THREADS=8` | 512/512 | 101.498445 | 88.505863 | valid loss vs `101.602390` record |
| `gemma4-q8-gpu1-current-th16-repeat-20260625T0254Z` | control, `THREADS=16` | 512/512 | 100.826442 | 87.823134 | valid loss |
| `gemma4-q8-gpu2-selectedsoftmax-weightedsum-combo-screen-20260625T0254Z` | `LLAMA_GEMMA4_MOE_SELECTED_SOFTMAX=1`, `LLAMA_GEMMA4_MOE_WEIGHTED_SUM=1` | 512/512 | **102.280773** | 89.151502 | promoted to full validation; not a record unless the 1536-row gate holds |
| `gemma4-q8-gpu3-selectedsoftmax-fuseddown-combo-screen-20260625T0254Z` | `LLAMA_GEMMA4_MOE_SELECTED_SOFTMAX=1`, `LLAMA_GEMMA4_MOE_FUSED_DOWN_WEIGHTED_SUM=1` | 512/512 | 101.512082 | 88.451825 | valid loss |

Decision: run the selected-softmax plus weighted-sum combo through the same full
gate as the current record (`384` canary repeats = `1536/1536` chat rows,
`BENCH_REPEATS=8`). Do not submit the screen row unless the full gate confirms
row-0 improvement. The fused-down combo remains rejected for the current
headline path.

### Batch 43: selected-softmax + weighted-sum full gates and threshold screens

Validity rule for this batch: headline throughput is the **first measured
fresh-response row only** (`rows[0]` in `p512o512.json`) and must have
`usage.prompt_tokens_details.cached_tokens=0`. Later benchmark repeats are
support/stability data only; they are not averaged into the headline because
the benchmark prompt/output repeats. All runs below use prompt cache disabled
(`--cache-ram 0`) and context checkpoints disabled (`--ctx-checkpoints 0`).

Common identity: Q8 target UD-Q8_K_XL, Q4_0 MTP draft, `MTP_N_MAX=7`,
`MTP_N_MIN=2`, backend sampling off, fast/direct argmax IDs with unroll 7,
q-only Gemma4Assistant attention inputs, safer verifier backend row-argmax IDs,
deferred target `h_nextn`, `LLAMA_GEMMA4_MOE_SELECTED_SOFTMAX=1`,
`LLAMA_GEMMA4_MOE_WEIGHTED_SUM=1`, `BATCH_SIZE=1024`, `UBATCH_SIZE=1024`,
`THREADS=8`, `POLL=100`, VMM off, SYCL graph enabled, and
`UR_L0_USE_IMMEDIATE_COMMANDLISTS=1`.

| Run | Variant | Gate | Fresh row0 tok/s | Wall tok/s | Cached tokens | Decision |
| --- | --- | ---: | ---: | ---: | ---: | --- |
| `gemma4-q8-gpu3-selectedsoftmax-weightedsum-pmin0138-full-20260625T030632Z` | `MTP_P_MIN=0.138` | 1536/1536 | 100.276523 | 87.725793 | 0 | valid loss; support rows were higher but warmed/repeated and not headline |
| `gemma4-q8-gpu2-selectedsoftmax-weightedsum-pmin014-full-rerun-20260625T030826Z` | `MTP_P_MIN=0.14` | 1536/1536 | **102.030961** | 88.507912 | 0 | current full-valid improvement over `101.602390`; keep as candidate unless superseded by pending full gates |
| `gemma4-q8-gpu0-selectedsoftmax-weightedsum-pmin0136-full-20260625T031510Z` | `MTP_P_MIN=0.136` | 1536/1536 | **103.299200** | 89.848908 | 0 | new best full-valid fresh row so far; same-config full repeat launched |
| `gemma4-q8-gpu1-selectedsoftmax-weightedsum-pmin0135-screen-20260625T031510Z` | `MTP_P_MIN=0.135` | 512/512 | 102.416368 | 89.169930 | 0 | screen-only; promoted to full gate |
| `gemma4-q8-gpu3-selectedsoftmax-weightedsum-dtb36-screen-20260625T031639Z` | `MTP_P_MIN=0.14`, `spec-draft-threads-batch=36` | 512/512 | 102.274223 | 89.143679 | 0 | screen-only; promoted to full gate |
| `gemma4-q8-gpu2-selectedsoftmax-weightedsum-pmin0134-screen-20260625T032131Z` | `MTP_P_MIN=0.134` | 512/512 | 102.236986 | 89.244051 | 0 | screen-only; promoted to full gate |

Completed follow-ups:

| Run | Variant | Gate | Fresh row0 tok/s | Wall tok/s | Cached tokens | Decision |
| --- | --- | ---: | ---: | ---: | ---: | --- |
| `gemma4-q8-gpu1-selectedsoftmax-weightedsum-pmin0135-full-20260625T032028Z` | `MTP_P_MIN=0.135` | 1536/1536 | 100.349643 | 87.637711 | 0 | valid loss; promoted screen did not hold |
| `gemma4-q8-gpu3-selectedsoftmax-weightedsum-dtb36-full-20260625T032112Z` | `MTP_P_MIN=0.14`, `spec-draft-threads-batch=36` | 1536/1536 | 102.107724 | 89.043918 | 0 | valid, below `p_min=0.136` |
| `gemma4-q8-gpu2-selectedsoftmax-weightedsum-pmin0134-full-20260625T032505Z` | `MTP_P_MIN=0.134` | 1536/1536 | 102.266451 | 89.186867 | 0 | valid, below `p_min=0.136` |
| `gemma4-q8-gpu0-selectedsoftmax-weightedsum-pmin0136-full-repeat-20260625T032710Z` | `MTP_P_MIN=0.136`, repeat | 1536/1536 | 102.318668 | 89.268466 | 0 | repeat confirms the config beats the old `101.602390` record, but does not beat the first `103.299200` row |

Additional screens after the full gates:

| Run | Variant | Gate | Fresh row0 tok/s | Wall tok/s | Cached tokens | Decision |
| --- | --- | ---: | ---: | ---: | ---: | --- |
| `gemma4-q8-gpu1-selectedsoftmax-weightedsum-pmin0136-dtb36-screen-20260625T033209Z` | `MTP_P_MIN=0.136`, draft batch threads `36` | 512/512 | 100.259943 | 87.554048 | 0 | reject |
| `gemma4-q8-gpu3-selectedsoftmax-weightedsum-n8-pmin0136-screen-20260625T033209Z` | `MTP_N_MAX=8`, unroll `8` | 512/512 | 66.290498 | 60.556974 | 0 | reject; deeper draft is catastrophic |
| `gemma4-q8-gpu1-selectedsoftmax-weightedsum-pmin0136-nmin1-screen-20260625T033643Z` | `MTP_N_MIN=1` | 512/512 | 102.361795 | 89.232127 | 0 | valid but below current best; no full promotion |
| `gemma4-q8-gpu2-selectedsoftmax-weightedsum-pmin0136-nmin3-screen-20260625T033643Z` | `MTP_N_MIN=3` | 512/512 | 102.352447 | 89.269944 | 0 | valid but below current best; no full promotion |
| `gemma4-q8-gpu0-selectedsoftmax-weightedsum-n5-pmin0136-screen-20260625T033819Z` | `MTP_N_MAX=5`, unroll `5` | 512/512 | 88.785024 | 78.781551 | 0 | reject |
| `gemma4-q8-gpu3-selectedsoftmax-weightedsum-n6-pmin0136-screen-20260625T033819Z` | `MTP_N_MAX=6`, unroll `6` | 512/512 | 95.904520 | 84.382323 | 0 | reject |

Decision: the selected-softmax + weighted-sum combo is the first default-off
MoE source change to produce a full-valid fresh-row improvement. The best
full-valid headline remains
`gemma4-q8-gpu0-selectedsoftmax-weightedsum-pmin0136-full-20260625T031510Z`
at **103.299200 tok/s** after TTFT, with `1536/1536` canary rows and
`cached_tokens=0`. Deeper MTP drafts (`n=5/6/8`) are rejected for this stack;
the good window is still `n=7`, `n_min=2`, `p_min` near `0.136`.

Target/verifier flag screens on the same `p_min=0.136` record stack:

| Run | Variant | Gate | Fresh row0 tok/s | Wall tok/s | Cached tokens | Decision |
| --- | --- | ---: | ---: | ---: | ---: | --- |
| `gemma4-q8-gpu0-selectedsoftmax-weightedsum-pmin0136-softcapargmax-screen-20260625T034837Z` | `LLAMA_SPEC_VERIFY_SOFTCAP_ARGMAX=1` | 512/512 | 102.306714 | 89.129472 | 0 | valid loss; post-LM-head softcap/argmax is not the remaining limiter |
| `gemma4-q8-gpu1-selectedsoftmax-weightedsum-pmin0136-fusedoutargmax-screen-20260625T034837Z` | `LLAMA_SPEC_VERIFY_FUSED_OUTPUT_ARGMAX=1` | 512/512 | 90.428922 | 80.091577 | 0 | reject; fused LM-head argmax path is much slower on this stack |
| `gemma4-q8-gpu2-selectedsoftmax-weightedsum-pmin0136-th16-screen-20260625T034837Z` | `THREADS=16` | 512/512 | 102.448406 | 89.284997 | 0 | valid but below record |
| `gemma4-q8-gpu3-selectedsoftmax-weightedsum-pmin0136-prioritizedmmv-screen-20260625T034837Z` | `GGML_SYCL_PRIORITIZE_DMMV=1` | 512/512 | 96.200485 | 84.537960 | 0 | reject |

Diagnostic profile
`gemma4-q8-gpu0-selectedsoftmax-weightedsum-pmin0136-profile-20260625T034630Z`
kept the same interpretation as earlier profiles: target generation /
`process_ubatch` dominates; draft decode and host-side accept plumbing are
small. The profile run was not a headline candidate (`8/8` canary only and
profile overhead), but its fresh row still had `cached_tokens=0` and measured
`100.419 tok/s`.

`MUL_MAT_ID` and fused-down follow-up screens on the same record family:

| Run | Variant | Gate | Fresh row0 tok/s | Wall tok/s | Cached tokens | Decision |
| --- | --- | ---: | ---: | ---: | ---: | --- |
| `gemma4-q8-gpu0-selectedsoftmax-pmin0136-mulmatidfast-screen-20260625T035435Z` | `LLAMA_SYCL_MUL_MAT_ID_MULTI_TOKEN_FAST=1` + weighted-sum | 512/512 | 76.536808 | 68.940870 | 0 | reject; broad multi-token fast path is much slower |
| `gemma4-q8-gpu1-selectedsoftmax-pmin0136-mulmatidfast-noreorder-screen-20260625T035435Z` | `LLAMA_SYCL_MUL_MAT_ID_MULTI_TOKEN_FAST=1`, `LLAMA_SYCL_MUL_MAT_ID_MULTI_TOKEN_NO_REORDER=1` + weighted-sum | 512/512 | 76.319580 | 68.713639 | 0 | reject |
| `gemma4-q8-gpu2-selectedsoftmax-pmin0136-mulmatidgroupedq80-screen-20260625T035435Z` | `LLAMA_SYCL_MUL_MAT_ID_MULTI_TOKEN_GROUPED_Q8_0=1` + weighted-sum | 512/512 | 90.846792 | 80.368315 | 0 | reject |
| `gemma4-q8-gpu3-selectedsoftmax-pmin0136-fuseddownwsum-screen-20260625T035435Z` | selected-softmax + `LLAMA_GEMMA4_MOE_FUSED_DOWN_WEIGHTED_SUM=1` at `p_min=0.136` | 512/512 | 99.628112 | 87.022945 | 0 | reject; fused-down path remains slower than selected-softmax + weighted-sum |

Decision: do not revive the broad `MUL_MAT_ID` fast paths or current
Q8_1-scratch fused-down path for this stack. The useful source target remains a
new fixed-shape Gemma verifier kernel that accumulates selected down experts
directly for the common 8-token path while preserving exact Q8 target weights,
selected expert IDs, and route weights.

## 2026-06-25 late: existing fused-down follow-up hooks

Build used the current llama.cpp SYCL stack at
`/home/steve/src/llama.cpp-gemma-record-stack`:

```bash
source /opt/intel/oneapi/setvars.sh --force >/dev/null 2>&1
cmake --build build-sycl-b70-aot-bmg-g31 --target llama-server -j 4
```

Patch snapshot:
`patches/gemma4-26b-a4b-q8-b70/20260625T2238Z-llamacpp-gemma4-moe-fused-down-directf32-parslots-current.patch`.

These screens tested two already-present experimental gates under
`LLAMA_GEMMA4_MOE_FUSED_DOWN_WEIGHTED_SUM=1`:

- `LLAMA_GEMMA4_MOE_FUSED_DOWN_WEIGHTED_SUM_DIRECT_F32=1`: skip the Q8_1
  scratch route for the selected-down weighted-sum fusion and read the current
  activation as direct F32.
- `LLAMA_GEMMA4_MOE_FUSED_DOWN_WEIGHTED_SUM_PARALLEL_SLOTS=1`: alternate
  parallel slot scheduling for the same fused-down weighted-sum path.

Common identity: Q8 target UD-Q8_K_XL, Q4_0 MTP draft, `MTP_N_MAX=7`,
`MTP_N_MIN=2`, `MTP_P_MIN=0.136`, selected-softmax, weighted-sum,
q-only draft attention inputs, deferred target `h_nextn`, direct draft argmax
IDs/unroll 7, backend verifier argmax IDs, `BATCH_SIZE=1024`,
`UBATCH_SIZE=1024`, `THREADS=8`, `POLL=100`, immediate command lists enabled,
fresh row 0 only, and `cached_tokens=0`.

| Run | Variant | Gate | Fresh row0 tok/s | Wall tok/s | TTFT s | Cached tokens | Decision |
| --- | --- | ---: | ---: | ---: | ---: | ---: | --- |
| `gemma4-q8-gpu0-selectedsoftmax-pmin0136-fuseddown-directf32-screen-20260625T2238Z` | fused-down weighted-sum + direct F32 current activation | 512/512 | 100.829267 | 88.052095 | 0.736849 | 0 | reject; slower than `103.299200` record |
| `gemma4-q8-gpu1-selectedsoftmax-pmin0136-fuseddown-parslots-screen-20260625T2238Z` | fused-down weighted-sum + parallel slots | 512/512 | 102.236624 | 88.922724 | 0.749818 | 0 | reject; valid but below record |

Decision: neither follow-up is promoted to a full gate or LocalMaxxing
submission. This reinforces the earlier conclusion that the current fused-down
Q8_1-scratch family is not the profitable path. The useful next source target
remains reducing target-side generation / `process_ubatch` cost without
disturbing the selected-softmax + weighted-sum record path.

## 2026-06-25 late: near-record thread and threshold screens

Follow-up screen batch after the fused-down losses. These runs intentionally
combined the strongest near-miss runtime axis (`THREADS=16`) with nearby
`p_min` / draft-batch settings. They use the same record-family identity as the
`p_min=0.136` selected-softmax + weighted-sum run: Q8 target, Q4_0 MTP draft,
`n_max=7`, `n_min=2`, backend sampling off, q-only draft attention, deferred
target `h_nextn`, direct draft argmax IDs/unroll 7, backend verifier argmax IDs,
`BATCH_SIZE=1024`, `UBATCH_SIZE=1024`, `POLL=100`, immediate command lists,
fresh row 0 only, and `cached_tokens=0`.

| Run | Variant | Gate | Fresh row0 tok/s | Wall tok/s | TTFT s | Cached tokens | Decision |
| --- | --- | ---: | ---: | ---: | ---: | ---: | --- |
| `gemma4-q8-gpu0-selectedsoftmax-weightedsum-pmin0136-th16-repeat-screen-20260625T2254Z` | repeat `MTP_P_MIN=0.136`, `THREADS=16` | 512/512 | 103.255213 | 89.304571 | 0.774602 | 0 | valid near-miss, but still below `103.299200`; no full promotion |
| `gemma4-q8-gpu1-selectedsoftmax-weightedsum-pmin0135-th16-screen-20260625T2254Z` | `MTP_P_MIN=0.135`, `THREADS=16` | 512/512 | 102.328532 | 88.889738 | 0.756453 | 0 | reject |
| `gemma4-q8-gpu2-selectedsoftmax-weightedsum-pmin0137-th16-screen-20260625T2254Z` | `MTP_P_MIN=0.137`, `THREADS=16` | 512/512 | 101.947626 | 88.741112 | 0.747405 | 0 | reject |
| `gemma4-q8-gpu3-selectedsoftmax-weightedsum-pmin0136-th16-dtb36-screen-20260625T2254Z` | `MTP_P_MIN=0.136`, `THREADS=16`, draft batch threads `36` | 512/512 | 100.236100 | 87.587578 | 0.737638 | 0 | reject; `dtb36` regresses badly with `THREADS=16` |

Decision: `THREADS=16` is close enough to keep as a variance/reference lane, but
it has now produced `102.448406` and `103.255213` screens, both below the
standing full-valid `103.299200` row. Do not burn a full gate unless a future
screen actually exceeds the record under the fresh-row rule.

## 2026-06-25 late: fine threshold/thread screens and current-hook closes

Fresh-response validity rule remains unchanged: only `rows[0]` from
`p512o512.json` is eligible for headline throughput, and it must show
`usage.prompt_tokens_details.cached_tokens=0`. Later repeated rows are
warmed/repeated-output support data only.

Fine `p_min` / thread screens on the selected-softmax + weighted-sum record
family:

| Run | Variant | Gate | Fresh row0 tok/s | Wall tok/s | TTFT s | Cached tokens | Decision |
| --- | --- | ---: | ---: | ---: | ---: | ---: | --- |
| `gemma4-q8-gpu0-selectedsoftmax-weightedsum-pmin01358-screen-20260625T2308Z` | `MTP_P_MIN=0.1358`, `THREADS=8` | 512/512 | 102.111721 | 88.776572 | 0.753172 | 0 | reject |
| `gemma4-q8-gpu1-selectedsoftmax-weightedsum-pmin01362-screen-20260625T2308Z` | `MTP_P_MIN=0.1362`, `THREADS=8` | 512/512 | 102.762579 | 89.342714 | 0.748383 | 0 | best of this batch but below `103.299200`; no full promotion |
| `gemma4-q8-gpu2-selectedsoftmax-weightedsum-pmin0136-th12-screen-20260625T2308Z` | `MTP_P_MIN=0.136`, `THREADS=12` | 512/512 | 102.031789 | 88.722544 | 0.752755 | 0 | reject |
| `gemma4-q8-gpu3-selectedsoftmax-weightedsum-pmin0136-th10-screen-20260625T2308Z` | `MTP_P_MIN=0.136`, `THREADS=10` | 512/512 | 100.484941 | 87.527988 | 0.754267 | 0 | reject |

Under-tested hooks from the source audit on the current record family:

| Run | Variant | Gate | Fresh row0 tok/s | Wall tok/s | TTFT s | Cached tokens | Decision |
| --- | --- | ---: | ---: | ---: | ---: | ---: | --- |
| `gemma4-q8-gpu2-selectedsoftmax-weightedsum-pmin0136-mtpfusedoutargmax-screen-20260625T2312Z` | `LLAMA_GEMMA4_MTP_FUSED_OUTPUT_ARGMAX=1` | 512/512 | 100.416509 | 87.776875 | 0.734208 | 0 | reject |
| `gemma4-q8-gpu3-selectedsoftmax-weightedsum-pmin0136-deviceh-screen-20260625T2312Z` | `LLAMA_MTP_DRAFT_DEVICE_H_HANDOFF=1` | 512/512 | 102.315323 | 89.276364 | 0.730863 | 0 | reject; lower TTFT but not enough decode gain |
| `gemma4-q8-gpu0-selectedsoftmax-weightedsum-pmin0136-topkcombo-screen-20260625T2316Z` | `LLAMA_GEMMA4_MOE_TOP_K=1` stacked with selected-softmax + weighted-sum | 512/512 | 100.278444 | 87.601203 | 0.738885 | 0 | reject |
| `gemma4-q8-gpu1-selectedsoftmax-weightedsum-pmin0136-control-repeat-screen-20260625T2316Z` | control repeat of the current record-family env | 512/512 | 102.194763 | 89.257783 | 0.726153 | 0 | valid control; below record |

Decision: these runs close the obvious remaining runtime and existing-hook
lanes around the current source stack. None beat the full-valid
`103.299200` fresh row, so there is no LocalMaxxing submission and no full gate
promotion. Future work should avoid retesting these gates unless the source
stack changes materially. The remaining useful optimization target is reducing
target-side Gemma generation / `process_ubatch` cost while preserving the Q8
target and fresh-response validation discipline.

## 2026-06-26 early: batch/ubatch retest around the record lane

Four-way batch/ubatch retest on the selected-softmax + weighted-sum record
family. These were launched after two failed detached `screen`/`nohup` attempts
(`...-screen-20260626T031600Z` and `...-screen-20260626T031709Z`, launch
failures only; do not count). The successful runs used the managed exec
launcher and completed `512` chat-canary rows each (`pass_all=true`).

Common identity: Q8 target UD-Q8_K_XL, Q4_0 MTP draft, `n_max=7`, `n_min=2`,
`MTP_P_MIN=0.136`, selected-softmax, weighted-sum, q-only draft attention,
deferred target `h_nextn`, direct draft argmax IDs/unroll 7, backend verifier
argmax IDs, `THREADS=8`, `POLL=100`, immediate command lists enabled, and
fresh row 0 from `p512o512.json` only. These local llama.cpp rows do not emit
the OpenAI `usage.prompt_tokens_details.cached_tokens` field, so they are
screen-only evidence rather than new headline submissions.

| Run | Variant | Gate | Fresh row0 tok/s | Wall tok/s | TTFT s | Cached token field | Decision |
| --- | --- | ---: | ---: | ---: | ---: | --- | --- |
| `gemma4-q8-gpu0-selectedsoftmax-weightedsum-pmin0136-b768u768-exec-20260626T031843Z` | `BATCH_SIZE=768`, `UBATCH_SIZE=768` | 512/512 | 102.014199 | 88.658920 | 0.756031 | not emitted | reject |
| `gemma4-q8-gpu1-selectedsoftmax-weightedsum-pmin0136-b896u896-exec-20260626T031843Z` | `BATCH_SIZE=896`, `UBATCH_SIZE=896` | 512/512 | 101.780421 | 88.510667 | 0.754176 | not emitted | reject |
| `gemma4-q8-gpu2-selectedsoftmax-weightedsum-pmin0136-b1152u1152-exec-20260626T031843Z` | `BATCH_SIZE=1152`, `UBATCH_SIZE=1152` | 512/512 | 102.374823 | 88.924000 | 0.756496 | not emitted | best of batch, still below `103.299200`; reject |
| `gemma4-q8-gpu3-selectedsoftmax-weightedsum-pmin0136-b1280u1280-exec-20260626T031843Z` | `BATCH_SIZE=1280`, `UBATCH_SIZE=1280` | 512/512 | 102.266257 | 88.993058 | 0.746719 | not emitted | reject |

Decision: no batch/ubatch value here beats the standing full-valid
`BATCH_SIZE=1024`, `UBATCH_SIZE=1024` record (`103.299200`). Do not promote any
of these to a full gate and do not submit to LocalMaxxing.

## 2026-06-26 early: fused GEGLU -> selected-down weighted-sum source patch

Source experiment from the Goodall audit: add a default-off backend op
`GGML_OP_MOE_GEGLU_SELECTED_DOWN_WEIGHTED_SUM` and env flag
`LLAMA_GEMMA4_MOE_FUSED_GEGLU_DOWN_WEIGHTED_SUM=1`. The idea was to fuse the
Gemma4 routed `GEGLU` activation with the Q8_1 staging before the selected-down
weighted-sum dot, while leaving the existing selected-down Q8_0 dot schedule
mostly intact.

Artifacts:

- source patch snapshot:
  `patches/gemma4-26b-a4b-q8-b70/20260626T0330Z-llamacpp-gemma4-moe-fused-geglu-down-weightedsum-current.patch`
- build: `llama-server` rebuilt successfully in
  `/home/steve/src/llama.cpp-gemma-record-stack/build-sycl-b70-aot-bmg-g31`
  after bumping the local `GGML_OP_COUNT` table asserts from `101` to `102`.
- harness: `scripts/run-gemma4-26b-first-baseline.sh` and
  `scripts/run-gemma4-26b-llamacpp-replica.sh` now record the new env flag in
  run identity / server logs.

Screen result:

| Run | Variant | Gate | Fresh row0 tok/s | Wall tok/s | TTFT s | Cached tokens | Decision |
| --- | --- | ---: | ---: | ---: | ---: | ---: | --- |
| `gemma4-q8-gpu0-selectedsoftmax-weightedsum-pmin0136-fusedgegludown-screen-20260626T0345Z` | selected-softmax + weighted-sum + `LLAMA_GEMMA4_MOE_FUSED_GEGLU_DOWN_WEIGHTED_SUM=1` | 512/512 | 92.186425 | 81.468307 | 0.730689 | 0 | reject; severe regression from `103.299200` |

Decision: do not promote. The fused GEGLU/down op is correctness-preserving on
the screen but materially slower, likely because the new fused staging path
breaks the profitable scheduling/memory behavior of the existing record stack.
Keep the default-off patch as a negative artifact; do not enable it in record
runs.

## 2026-06-26 early: QAT-inspired transfer sweep plan

The QAT/Q4XL side lane repeatedly reaches `~132-136 tok/s` fresh row0, but it
uses a lower/different target quantization and is **not** a valid Q8 headline
for the current objective. Its transferable runtime pattern is mostly
`BATCH_SIZE=512`, `UBATCH_SIZE=512`, `THREADS=16`, `POLL=100`, plus the same
draft-MTP shape. The current Q8 selected-softmax + weighted-sum record family
has not tested that exact `B/U=512` transfer, nor the strongest near-miss
combination `THREADS=16` + `MTP_P_MIN=0.1362`.

Launch a four-way screen with common record identity: Q8 target UD-Q8_K_XL,
Q4_0 MTP draft, `n_max=7`, `n_min=2`, selected-softmax, weighted-sum, q-only
draft attention, deferred target `h_nextn`, direct draft argmax IDs/unroll 7,
backend verifier argmax IDs, immediate command lists, `CANARY_REPEATS=128`,
`BENCH_REPEATS=4`, `BENCH_PROMPT_MODE=filled-long`, and fresh row0 only.

Planned candidates:

| Candidate | Purpose |
| --- | --- |
| `BATCH_SIZE=512`, `UBATCH_SIZE=512`, `THREADS=16`, `MTP_P_MIN=0.136` | direct transfer from the faster QAT lane |
| `BATCH_SIZE=512`, `UBATCH_SIZE=512`, `THREADS=8`, `MTP_P_MIN=0.136` | isolate whether `B/U=512` helps Q8 without thread change |
| `BATCH_SIZE=1024`, `UBATCH_SIZE=1024`, `THREADS=16`, `MTP_P_MIN=0.1362` | combine the `THREADS=16` near-miss (`103.255`) with the `p_min=0.1362` near-miss (`102.763`) |
| `BATCH_SIZE=1024`, `UBATCH_SIZE=1024`, `THREADS=16`, `MTP_P_MIN=0.136`, `POLL=75` | test whether QAT's near-neutral lower poll value improves the strongest Q8 thread lane |

Promotion rule: only run a full `1536/1536` canary + `BENCH_REPEATS=8` gate if
screen fresh row0 beats `103.299200` and row0 is a fresh request with
`cached_tokens=0`.

Results:

| Run | Variant | Gate | Fresh row0 tok/s | Mean tok/s | Max any row | Wall row0 | TTFT s | Cached tokens | Decision |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| `gemma4-q8-gpu0-selectedsoftmax-weightedsum-b512u512-th16-pmin0136-screen-20260626T0354Z` | `B/U=512`, `THREADS=16`, `MTP_P_MIN=0.136` | 512/512 | 100.478277 | 100.481633 | 100.724136 | 85.009783 | 0.927207 | 0 | reject |
| `gemma4-q8-gpu1-selectedsoftmax-weightedsum-b512u512-th8-pmin0136-screen-20260626T0354Z` | `B/U=512`, `THREADS=8`, `MTP_P_MIN=0.136` | 512/512 | 100.234922 | 100.236989 | 100.379836 | 84.701783 | 0.936737 | 0 | reject |
| `gemma4-q8-gpu2-selectedsoftmax-weightedsum-th16-pmin01362-screen-20260626T0354Z` | `B/U=1024`, `THREADS=16`, `MTP_P_MIN=0.1362` | 512/512 | 100.186033 | 102.007774 | 103.271173 | 87.504728 | 0.740620 | 0 | reject; warmed rows near record, but row0 is the only valid fresh headline |
| `gemma4-q8-gpu3-selectedsoftmax-weightedsum-th16-poll75-pmin0136-screen-20260626T0354Z` | `B/U=1024`, `THREADS=16`, `POLL=75`, `MTP_P_MIN=0.136` | 512/512 | 102.147500 | 101.786312 | 102.357021 | 88.881950 | 0.748090 | 0 | reject |

Decision: no full gate and no LocalMaxxing submission. `B/U=512` does not
transfer from QAT/Q4XL to the Q8 target lane; `THREADS=16 + p_min=0.1362` is not
a fresh-response win despite a near-record warmed row.

## 2026-06-26 early: near-tie repeat and `p_min=0.1362` batch combinations

Follow-up screen after the QAT-transfer losses. This focuses on the subagent
audit's remaining runtime gaps: repeat the previous `THREADS=16` near-tie,
repeat base `MTP_P_MIN=0.1362` with four benchmark rows, and combine
`MTP_P_MIN=0.1362` with the least-bad larger batch sizes from the prior
`p_min=0.136` batch sweep.

Common identity remains the Q8 target / Q4_0 MTP draft selected-softmax +
weighted-sum record stack, `n_max=7`, `n_min=2`, q-only draft attention,
deferred target `h_nextn`, direct draft argmax IDs/unroll 7, backend verifier
argmax IDs, immediate command lists, `CANARY_REPEATS=128`, `BENCH_REPEATS=4`,
`BENCH_PROMPT_MODE=filled-long`, and fresh row0 only.

| Run | Variant | Gate | Fresh row0 tok/s | Mean tok/s | Max any row | Wall row0 | TTFT s | Cached tokens | Decision |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| `gemma4-q8-gpu0-selectedsoftmax-weightedsum-th16-pmin0136-repeat4-screen-20260626T0405Z` | `THREADS=16`, `MTP_P_MIN=0.136`, `B/U=1024` | 512/512 | 100.138375 | 101.590771 | 102.242915 | 87.345950 | 0.748824 | 0 | reject |
| `gemma4-q8-gpu1-selectedsoftmax-weightedsum-pmin01362-repeat4-screen-20260626T0405Z` | `THREADS=8`, `MTP_P_MIN=0.1362`, `B/U=1024` | 512/512 | 102.175233 | 101.744816 | 102.299016 | 88.917640 | 0.747138 | 0 | reject |
| `gemma4-q8-gpu2-selectedsoftmax-weightedsum-b1152u1152-pmin01362-screen-20260626T0405Z` | `THREADS=8`, `MTP_P_MIN=0.1362`, `B/U=1152` | 512/512 | 100.325799 | 101.754112 | 102.923018 | 87.719911 | 0.733386 | 0 | reject |
| `gemma4-q8-gpu3-selectedsoftmax-weightedsum-b1280u1280-pmin01362-screen-20260626T0405Z` | `THREADS=8`, `MTP_P_MIN=0.1362`, `B/U=1280` | 512/512 | 102.048156 | 101.173086 | 102.048156 | 88.857538 | 0.744793 | 0 | reject |

Decision: no full gate and no LocalMaxxing submission. Runtime knob
recombination around the current record is effectively exhausted; future work
should be source/profile driven rather than more `p_min`/batch/thread repeats.

## 2026-06-26 early: sampled extraction cleanup + filtered multi-token `MUL_MAT_ID`

Source/harness patch snapshots:

- `patches/gemma4-26b-a4b-q8-b70/20260626T0430Z-llamacpp-gemma4-mulmatid-filter-sampled-extract.patch`
- `patches/gemma4-26b-a4b-q8-b70/20260626T0430Z-results-harness-mulmatid-filter-env-capture.patch`

Changes tested:

- `llama-context.cpp`: avoid building `seq_to_output_row` when the verifier path
  only has `res->t_sampled_rows` (direct argmax IDs) and no scalar
  `res->t_sampled`. This is semantics-preserving: all target Q8 sampled rows are
  still copied, but a small unused CPU mapping path is skipped.
- `ggml-sycl.cpp`: add default-off
  `LLAMA_SYCL_MUL_MAT_ID_MULTI_TOKEN_FILTER={gate_up,down}` to isolate the
  previous all-or-nothing `LLAMA_SYCL_MUL_MAT_ID_MULTI_TOKEN_FAST=1` regression.
  Graph eligibility and runtime fallback use the same filter.
- Harnesses now capture the `LLAMA_SYCL_MUL_MAT_ID_MULTI_TOKEN_*` env fields in
  launcher identity / summaries.

Common identity: Q8 target UD-Q8_K_XL, Q4_0 MTP draft, `n_max=7`, `n_min=2`,
`MTP_P_MIN=0.136`, selected-softmax, weighted-sum, q-only draft attention,
deferred target `h_nextn`, direct draft argmax IDs/unroll 7, backend verifier
argmax IDs, immediate command lists, `BATCH_SIZE=1024`, `UBATCH_SIZE=1024`,
`THREADS=8`, `POLL=100`, `CANARY_REPEATS=128`, `BENCH_REPEATS=4`,
`BENCH_PROMPT_MODE=filled-long`.

Fresh headline rule: only `p512o512.json` row 0 counts as fresh-response
throughput. Later rows are warmed/repeat support only. All row 0 measurements
below report `usage.prompt_tokens_details.cached_tokens=0`.

| Run | Variant | Gate | Fresh row0 tok/s | Mean tok/s | Max any row | Wall row0 | TTFT s | Decision |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| `gemma4-q8-gpu0-sampledmap-control-screen-20260626T0430Z` | sampled-map cleanup only | 512/512 | 102.171602 | 102.267469 | 102.389610 | 88.892887 | 0.748564 | reject; below `103.299200` record |
| `gemma4-q8-gpu1-mulmatidfast-gateup-screen-20260626T0430Z` | `MUL_MAT_ID_MULTI_TOKEN_FAST=1`, filter `gate_up` | 512/512 | 76.718836 | 76.448671 | 76.718836 | 69.070558 | 0.738990 | reject; severe regression |
| `gemma4-q8-gpu2-mulmatidfast-down-screen-20260626T0430Z` | `MUL_MAT_ID_MULTI_TOKEN_FAST=1`, filter `down` | 512/512 | 102.224029 | 101.337033 | 102.294628 | 89.196458 | 0.731531 | reject; close but below record |
| `gemma4-q8-gpu3-mulmatidfast-gateupdown-screen-20260626T0430Z` | `MUL_MAT_ID_MULTI_TOKEN_FAST=1`, filter `gate_up,down` | 512/512 | 76.548614 | 75.932129 | 76.548614 | 68.955206 | 0.736550 | reject; severe regression |

Decision: no full gate and no LocalMaxxing submission. The sampled-map cleanup
is neutral/slightly negative. The filtered multi-token route confirms the
`gate_up` side is the source of the large regression; `down` alone is
near-neutral but still not a fresh-response record. Future source work should
not continue the current all-or-nothing multi-token route. Better next targets:

- add a non-grouped per-slot Q8_0 multi-token `MUL_MAT_ID` specialization for
  `ne11 == n_expert_used` without the grouped scan/tmp overhead; or
- fuse only the final MoE down-projection scatter plus weighted-sum epilogue
  while keeping the existing profitable generic per-expert matmul schedule.

## 2026-06-26 early: skip early MoE weights graph expansion

Patch snapshots:

- `patches/gemma4-26b-a4b-q8-b70/20260626T0438Z-llamacpp-gemma4-skip-early-weights-expand.patch`
- `patches/gemma4-26b-a4b-q8-b70/20260626T0438Z-results-harness-skip-early-weights-env-capture.patch`

Change: add default-off `LLAMA_GEMMA4_MOE_SKIP_EARLY_WEIGHTS_EXPAND=1` to skip
the early `ggml_build_forward_expand(gf, weights)` in the Gemma4
`LLAMA_GEMMA4_MOE_WEIGHTED_SUM=1` path. Hypothesis: the weighted-sum op consumes
`weights` directly, so the early expansion may add graph scheduling overhead.

Screen result:

| Run | Variant | Gate | Fresh row0 tok/s | Mean tok/s | Max any row | Wall row0 | TTFT s | Cached tokens | Decision |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| `gemma4-q8-gpu0-skipearlyweights-screen-20260626T0438Z` | skip early weights expansion | 512/512 | 102.338400 | 102.168913 | 103.216482 | 85.088500 | 1.014255 | 1 | reject |

Decision: no full gate and no LocalMaxxing submission. The run is below the
`103.299200` record and not a valid fresh headline because the OpenAI usage
reported `cached_tokens=1` for every benchmark row. The screen also missed the
record-family `--spec-draft-threads 32 --spec-draft-threads-batch 32
--ctx-checkpoints 0` args, so it is useful only as a negative scheduling
probe. Do not pursue this knob unless retesting with a record-identical launch
after other source changes.

## 2026-06-26 early: non-grouped per-slot Q8_0 `MUL_MAT_ID` for down projection

Patch snapshots:

- `patches/gemma4-26b-a4b-q8-b70/20260626T0456Z-llamacpp-gemma4-mulmatid-per-slot-q80-current.patch`
- `patches/gemma4-26b-a4b-q8-b70/20260626T0456Z-results-harness-per-slot-q80-env-capture.patch`

Change: add default-off `LLAMA_SYCL_MUL_MAT_ID_MULTI_TOKEN_PER_SLOT_Q8_0=1` for
the Q8_0, multi-token, `src1->ne[1] == ids->ne[0]` `MUL_MAT_ID` shape used by
Gemma4 down projection. Test with `LLAMA_SYCL_MUL_MAT_ID_MULTI_TOKEN_FILTER=down`.
This avoids the grouped Q8_0 duplicate-route scans and temp accumulation while
preserving the target Q8 verifier semantics. Graph eligibility was updated so
the path can be captured when active.

Screen identity restored the record-family args:
`--spec-draft-threads 32 --spec-draft-threads-batch 32 --ctx-checkpoints 0`.

| Run | Variant | Gate | Fresh row0 tok/s | Mean tok/s | Max any row | Wall row0 | TTFT s | Cached tokens | Decision |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| `gemma4-q8-gpu0-mulmatid-per-slot-down-screen-20260626T0456Z` | per-slot Q8_0 `down` fast path | 512/512 | 102.407711 | 101.674863 | 103.088484 | 89.371059 | 0.729300 | 0 | reject |

Decision: no full gate and no LocalMaxxing submission. Correct and fresh, but
below the `103.299200` record. It is slightly better than the earlier `down`
filtered grouped path (`102.224029`) but not enough. This suggests the grouped
scan/tmp overhead is not the dominant remaining cost; the better high-ceiling
target is the separate materialized `ffn_moe_down` route-output write plus
`MOE_WEIGHTED_SUM` read/reduce pass.

## 2026-06-26 early: down `MUL_MAT_ID` matmul schedule with fused weighted epilogue

Patch snapshots:

- `patches/gemma4-26b-a4b-q8-b70/20260626T0515Z-llamacpp-gemma4-fuseddown-matmul-epilogue-current.patch`
- `patches/gemma4-26b-a4b-q8-b70/20260626T0515Z-results-harness-fuseddown-matmul-epilogue-env-capture.patch`

Change: add default-off
`LLAMA_GEMMA4_MOE_FUSED_DOWN_WEIGHTED_SUM_MATMUL_EPILOGUE=1` under the existing
`LLAMA_GEMMA4_MOE_FUSED_DOWN_WEIGHTED_SUM=1` graph op. Instead of using the
direct fused Q8_0 down kernels, this path keeps the generic per-expert
`MUL_MAT_ID` schedule:

- copy selected expert IDs to host and counting-sort routed rows by expert;
- gather `cur[slot, token]` rows into a contiguous source buffer;
- run one `ggml_sycl_mul_mat` per active expert into a contiguous routed-output
  buffer;
- replace the generic route scatter plus separate `MOE_WEIGHTED_SUM` pass with
  one final kernel that reads routed rows, applies selected weights and optional
  down scales, and writes `[n_embd, n_tokens]`.

The goal was to preserve the tuned per-expert matmul behavior while eliminating
the materialized `[n_embd, n_expert_used, n_tokens]` route-output write/read
between down projection and weighted sum.

Screen identity used the record-family args:
`--spec-draft-threads 32 --spec-draft-threads-batch 32 --ctx-checkpoints 0`.

| Run | Variant | Gate | Fresh row0 tok/s | Mean tok/s | Max any row | Wall row0 | TTFT s | Cached tokens | Decision |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| `gemma4-q8-gpu0-fuseddown-matmul-epilogue-screen-20260626T0515Z` | fused-down graph op, matmul schedule + fused weighted epilogue | 512/512 | 102.329380 | 101.855357 | 102.482530 | 89.196077 | 0.736712 | 0 | reject |

Decision: no full gate and no LocalMaxxing submission. The path is correct and
fresh, but below the `103.299200` record and also below the simpler per-slot
down-only fast path (`102.407711`). This indicates that replacing the final
scatter/weighted-sum pass is not enough; the host ID copy/counting-sort and
per-expert matmul launch pattern remain the limiting cost for this shape.

## 2026-06-26 early: `THREADS=16` fine p-min sweep around the record lane

No patch; this was an env/config sweep on the current record-family source
stack with the new fused-down matmul-epilogue path left disabled.

Rationale: the prior `THREADS=16`, `p_min=0.136` screen reached
`103.255213` fresh row0, close to the current `103.299200` record. Run a narrow
four-GPU sweep around the record p-min region while preserving the fresh
headline rule.

Common identity: `MTP_N_MAX=7`, `MTP_N_MIN=2`, Q8 target, Q4_0 MTP draft,
selected softmax, weighted sum, Q-only MTP attention inputs, deferred target
`h_nextn`, direct draft argmax IDs/unroll 7, backend verifier argmax IDs,
`THREADS=16`, `BATCH_SIZE=1024`, `UBATCH_SIZE=1024`, `POLL=100`,
`CANARY_REPEATS=128`, `BENCH_REPEATS=4`, `BENCH_PROMPT_MODE=filled-long`.

| Run | p-min | Gate | Fresh row0 tok/s | Mean tok/s | Max any row | Wall row0 | TTFT s | Cached tokens | Decision |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| `gemma4-q8-gpu0-th16-pmin01359-screen-20260626T0525Z` | 0.1359 | 512/512 | 102.031764 | 102.008132 | 103.104945 | 88.756438 | 0.750550 | 0 | reject |
| `gemma4-q8-gpu1-th16-pmin01360-screen-20260626T0525Z` | 0.1360 | 512/512 | 100.531385 | 101.550641 | 102.280241 | 87.762027 | 0.741021 | 0 | reject |
| `gemma4-q8-gpu2-th16-pmin01361-screen-20260626T0525Z` | 0.1361 | 512/512 | 102.168239 | 102.233999 | 102.615585 | 88.926795 | 0.746203 | 0 | reject |
| `gemma4-q8-gpu3-th16-pmin01362-screen-20260626T0525Z` | 0.1362 | 512/512 | 100.323177 | 101.795985 | 102.475157 | 87.489531 | 0.748622 | 0 | reject |

Decision: no full gate and no LocalMaxxing submission. All rows are fresh
(`cached_tokens=0`), but no fresh row0 beats `103.299200`. The `103.104945`
max in the 0.1359 run is a warmed later repeat and is support-only, not a
fresh-response headline. `THREADS=16` remains close but does not displace the
`THREADS=8`, `p_min=0.136` full record.

## 2026-06-26 morning: post-push tight record-lane screens

No patch; these were env/config screens on the current record-family source
stack. The purpose was to continue the Gemma Q8 optimization loop after
publishing the result docs and to obey the stricter fresh-response headline
rule: only benchmark row 0 counts, and only when `cached_tokens=0` and canaries
pass. Later rows are support-only even when faster.

Common identity unless noted: Q8 target, Q4_0 MTP draft, `MTP_N_MAX=7`,
`MTP_N_MIN=2`, selected softmax, weighted sum, Q-only MTP attention inputs,
deferred target `h_nextn`, direct draft argmax IDs/unroll 7, backend verifier
argmax IDs, immediate command lists, `BATCH_SIZE=1024`, `UBATCH_SIZE=1024`,
`POLL=100`, `CANARY_REPEATS=128`, `BENCH_REPEATS=4`,
`BENCH_PROMPT_MODE=filled-long`, `--ctx-checkpoints 0`.

### Four-GPU screen 1: `THREADS=8/10`, tight `p_min`

| Run | Variant | Gate | Fresh row0 tok/s | Mean tok/s | Max any row | Wall row0 | TTFT s | Cached tokens | Decision |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| `gemma4-q8-gpu0-record-control-pmin0136-th8-screen-20260626T055239Z` | record control, `p_min=0.136`, `THREADS=8` | 512/512 | 100.417137 | 101.771590 | 102.452900 | 87.498756 | 0.752780 | 0 | reject |
| `gemma4-q8-gpu1-pmin01355-th8-screen-20260626T055239Z` | `p_min=0.1355`, `THREADS=8` | 512/512 | 103.045106 | 101.564272 | 103.045106 | 89.374226 | 0.760023 | 0 | reject; closest, but still below record |
| `gemma4-q8-gpu2-pmin01365-th8-screen-20260626T055239Z` | `p_min=0.1365`, `THREADS=8` | 512/512 | 100.560008 | 100.997733 | 102.480369 | 87.585108 | 0.754255 | 0 | reject |
| `gemma4-q8-gpu3-pmin0136-th10-screen-20260626T055239Z` | `p_min=0.136`, `THREADS=10` | 512/512 | 102.093298 | 101.608581 | 102.205281 | 88.892982 | 0.744714 | 0 | reject |

Decision: no full gate and no LocalMaxxing submission. The `p_min=0.1355`
lane is the only result close enough to justify another tight sweep; exact
record control was much lower on this run, reinforcing that row0 device/noise
variance is meaningful near the frontier.

### Four-GPU screen 2: subagent-suggested near-record interactions

| Run | Variant | Gate | Fresh row0 tok/s | Mean tok/s | Max any row | Wall row0 | TTFT s | Cached tokens | Decision |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| `gemma4-q8-gpu0-th16-pmin0136-screen-20260626T055728Z` | `THREADS=16`, `p_min=0.136` | 512/512 | 100.583285 | 101.295148 | 102.164747 | 87.615053 | 0.753436 | 0 | reject |
| `gemma4-q8-gpu1-th16-per-slot-down-pmin0136-screen-20260626T055728Z` | `THREADS=16` + per-slot Q8_0 down fast path | 512/512 | 101.301841 | 101.351047 | 102.421900 | 88.130286 | 0.755378 | 0 | reject |
| `gemma4-q8-gpu2-th16-b1152u1152-pmin0136-screen-20260626T055728Z` | `THREADS=16`, `B/U=1152` | 512/512 | 102.482734 | 102.083025 | 103.160111 | 89.096198 | 0.750634 | 0 | reject; best of this screen |
| `gemma4-q8-gpu3-th8-pmin01362-screen-20260626T055728Z` | `THREADS=8`, `p_min=0.1362` | 512/512 | 102.433195 | 102.212935 | 102.433195 | 89.099649 | 0.747995 | 0 | reject |

Decision: no full gate and no LocalMaxxing submission. The subagent-suggested
interactions did not beat the `103.299200` record. `THREADS=16` is no longer
promoted as a likely win; the next low-risk branch is a tight `THREADS=8`
threshold repeat around `p_min=0.1355` plus exact record controls across
devices.

### Four-GPU screen 3: tighter `THREADS=8` sweep around `p_min=0.1355`

| Run | Variant | Gate | Fresh row0 tok/s | Mean tok/s | Max any row | Wall row0 | TTFT s | Cached tokens | Decision |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| `gemma4-q8-gpu0-pmin013545-th8-screen-20260626T060212Z` | `p_min=0.13545`, `THREADS=8` | 512/512 | 102.480786 | 102.397146 | 102.514748 | 88.925801 | 0.761551 | 0 | reject |
| `gemma4-q8-gpu1-pmin013550-th8-repeat-screen-20260626T060212Z` | `p_min=0.13550`, `THREADS=8` repeat | 512/512 | 101.683069 | 100.944081 | 102.145008 | 88.537973 | 0.747576 | 0 | reject |
| `gemma4-q8-gpu2-pmin013555-th8-screen-20260626T060212Z` | `p_min=0.13555`, `THREADS=8` | 512/512 | 102.533177 | 101.323146 | 102.533177 | 89.211239 | 0.745682 | 0 | reject; best of this screen |
| `gemma4-q8-gpu3-pmin013600-th8-control-screen-20260626T060212Z` | exact record threshold control, `p_min=0.13600`, `THREADS=8` | 512/512 | 102.313671 | 102.449246 | 103.196027 | 89.148648 | 0.738998 | 0 | reject |

Decision: no full gate and no LocalMaxxing submission. The tight `p_min`
region did not repeat the `103.045` near-hit, and no row0 exceeded the
`103.299200` record. Stop spending four-GPU lanes on p-min-only tuning unless a
new source/runtime change shifts the baseline; row0 variance is too large and
the current neighborhood appears capped around low `102.x` in fresh mode.

### Diagnostic profile: route mix and MTP timing at the record identity

`gemma4-q8-gpu0-record-profile-route-20260626T060729Z` reran the record-family
identity with diagnostic profiling enabled:

- `LLAMA_SYCL_MUL_MAT_ID_ROUTE_PROFILE=1`
- `LLAMA_SYCL_MUL_MAT_ID_ROUTE_PROFILE_EVERY=25`
- `LLAMA_SERVER_SPEC_PROFILE=1`
- `LLAMA_MTP_DRAFT_PROFILE=1`
- canary: **64/64** pass; p512/o512 row0: **102.399883 tok/s**,
  row1 **102.230418 tok/s**, `cached_tokens=0`.

Artifacts:

- data copy:
  `data/gemma4-q8-gpu0-record-profile-route-20260626T060729Z/summary.json`
- full server log:
  `/mnt/fast-ai/bench-results/gemma4-26b-a4b-q8/servers/gemma4-q8-gpu0-record-profile-route-20260626T060729Z.server.log`

Profile takeaways:

- Draft quality is already excellent on the filled-long shape: benchmark
  acceptance was `445 accepted / 462 generated`, mean acceptance length `7.74`,
  per-position `(1.000, 0.985, 0.970, 0.955, 0.955, 0.939, 0.939)`.
- Draft/sampling overhead is not the remaining ceiling. After the second bench
  request, `draft_ms=1846.121` over `392` calls, while target decode was
  `29175.690 ms` over the same `392` calls.
- Target decode phase profile after the second bench:
  `process_ubatch_ms=28541.532`, `post_extract_ms=617.494`,
  `sampled_extract_ms=617.376`. The dominant cost is target verifier
  `process_ubatch`; sampled-token extraction is a smaller but measurable
  secondary target (~`1.57 ms/call`).
- `MUL_MAT_ID` route profile for decode batches shows the hot verifier shape
  is mostly `tok2_8`: about `7.95` tokens, `8` expert ids per token,
  `~63.6` routed rows, `~25.2` globally unique experts, and `~38.4` repeated
  routed rows. This confirms the current optimization frontier is the tiny
  multi-token MoE verifier path, not p-min or draft acceptance quality.

Decision: diagnostic only, no LocalMaxxing submission. Preserve it because it
redirects future work away from p-min/thread-only sweeps and toward target
`process_ubatch` source work or a safe reduction in sampled-token extraction
overhead.

## 2026-06-26 sampled-row exact-copy verifier micro-patch

Patch artifact:

- `patches/gemma4-26b-a4b-q8-b70/20260626T0622-llamacpp-verifier-sampled-row0-exactcopy.patch`

Idea: when the verifier direct-argmax path produces a single contiguous
`t_sampled_rows[0]` tensor, bypass the generic row-map loop and copy exactly
`n_outputs` `I32` token IDs into `sampling.sampled` from row 0. This targeted
the secondary decode-profile cost seen above (`sampled_extract_ms`, about
`1.57 ms/call`) without changing draft quality or target math.

Validation run:

- label: `gemma4-q8-gpu0-row0-exactcopy-profile`
- canary: **64/64** pass (`256` rows)
- p512/o512, 2 repeats, fresh row0: **102.429787 tok/s**,
  row1 **102.275898 tok/s**, `cached_tokens=0`
- summary:
  `data/gemma4-q8-gpu0-row0-exactcopy-profile/summary.json`
- server log:
  `/mnt/fast-ai/bench-results/gemma4-26b-a4b-q8/servers/gemma4-q8-gpu0-row0-exactcopy-profile.server.log`

Profile result: no practical win. Final target decode profile still shows
`process_ubatch_ms=84333.088` dominating and `sampled_extract_ms=1672.022`
over `1160` accumulated target calls (about `1.44 ms/call`, only a small
movement versus the previous profiled `~1.57 ms/call`). The fresh row0 result
is below the valid record `103.299200 tok/s`.

Decision: preserve the patch and result as a negative/marginal experiment, but
do not promote it into the working stack and do not submit to LocalMaxxing.
Reverted from the source tree before continuing. The next higher-upside target
is the Gemma4 selected-softmax/MoE verifier `process_ubatch` path, not sampled
ID extraction.
