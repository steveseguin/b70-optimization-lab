# 2026-06-24T1351 Q8 Batch / Thread Followups

## Decision

Promoted at the time, later superseded by
`data/gemma4-q8-gpu0-mtp-n7-directunroll7-qonly-b1024u1024-th8-syclgraph0-full-20260624T144749Z/`
(`98.61718830251647 tok/s` row 0 fresh, LocalMaxxing
`cmqs7uyqb00lnqr01u9dtv63r`):

Earlier promoted run:
`data/gemma4-q8-gpu3-mtp-n7-directunroll7-qonly-b1024u1024-th8-full-20260624T135701Z/`
as the previous valid Q8-target fresh-response single-B70 result:

- row 0 fresh headline: **98.4913689785019 tok/s** after TTFT;
- row 0 wall: `86.19446305286014 tok/s`;
- supporting repeated-request mean: `97.88614261273774 tok/s` after TTFT;
- benchmark shape: 588 prompt tokens, 512 output tokens;
- row 0 `cached_tokens=0`; all rows report `cached_tokens=0`;
- canary: **384/384** chat rows pass;
- LocalMaxxing: `cmqs56wv100kjqr01de3fdspd`.

The result supersedes the previous direct-unroll/q-only Q8-target record
`cmqs4jnx100k6qr01d1iy78kl` (`96.82235022330569 tok/s` row 0 fresh).

## Validity

Headline throughput uses row 0 only. Rows 1-7 are repeated-prompt stability
support and are not averaged into the fresh-response claim. This run uses a
fresh-valid Gemma MTP draft for the current request: no n-gram/history
continuation reuse, no prefix-response reuse, `--ctx-checkpoints 0`, and
`--cache-ram 0`.

The target/verifier remains `gemma-4-26B-A4B-it-UD-Q8_K_XL.gguf`; only the MTP
draft model is Q4_0. Accepted tokens are verified by the Q8 target.

## Promoted Config

Delta from the previous `96.822` direct-unroll/q-only record:

- `BATCH_SIZE=1024` instead of `512`;
- `UBATCH_SIZE=1024` instead of `512`;
- `THREADS=8` instead of `16`;
- `POLL=100` unchanged;
- `GGML_SYCL_ENABLE_VMM=0` unchanged.

Command identity:

```bash
cd /home/steve/qwen36-results-main
LLAMA_SERVER=/home/steve/src/llama.cpp-gemma-record-stack/build-sycl-b70-aot-bmg-g31/bin/llama-server \
GPU_INDEX=3 PORT=18263 LABEL=gemma4-q8-gpu3-mtp-n7-directunroll7-qonly-b1024u1024-th8-full-20260624T135701Z \
GGML_SYCL_ENABLE_VMM=0 BATCH_SIZE=1024 UBATCH_SIZE=1024 THREADS=8 POLL=100 \
MTP_DRAFT_MODEL=/mnt/fast-ai/llm-models/gemma4-26b-a4b-it-q8-gguf/MTP/gemma-4-26B-A4B-it-Q4_0-MTP.gguf \
MTP_N_MAX=7 MTP_N_MIN=2 MTP_P_MIN=0.12 MTP_BACKEND_SAMPLING=0 \
MTP_DRAFT_THREADS=32 MTP_DRAFT_THREADS_BATCH=32 MTP_DRAFT_FAST_ARGMAX=1 \
LLAMA_MTP_DRAFT_DIRECT_ARGMAX_IDS=1 LLAMA_MTP_DRAFT_DIRECT_ARGMAX_UNROLL=7 \
LLAMA_GEMMA4_MTP_QONLY_ATTN_INPUTS=1 \
MTP_EXTRA_ARGS='--ctx-checkpoints 0' BENCH_PROMPT_MODE=filled-long \
CANARY_REPEATS=96 BENCH_REPEATS=8 \
scripts/run-gemma4-26b-mtp-candidate.sh
```

## Screens And Full Runs

| Run | Canary | Fresh row 0 tok/s | Repeated mean | Decision |
| --- | ---: | ---: | ---: | --- |
| `gemma4-q8-gpu0-mtp-n7-directunroll7-qonly-control-screen-20260624T135117Z` | 128/128 | 95.925 | 95.925 | screen only; below previous full record |
| `gemma4-q8-gpu1-mtp-n7-directunroll7-qonly-b1024u1024-screen-20260624T135117Z` | 128/128 | 97.923 | 97.923 | screen win; sent to full |
| `gemma4-q8-gpu2-mtp-n7-directunroll7-qonly-poll75-screen-20260624T135118Z` | 128/128 | 95.693 | 95.693 | screen only; poll=75 not useful |
| `gemma4-q8-gpu3-mtp-n7-directunroll7-qonly-vmm1-screen-20260624T135117Z` | 128/128 | 95.690 | 95.690 | screen only; VMM=1 not useful |
| `gemma4-q8-gpu0-mtp-n7-directunroll7-qonly-b1024u1024-full-20260624T135503Z` | 384/384 | 97.655 | 97.604 | valid improvement but superseded by thread-8 full |
| `gemma4-q8-gpu1-mtp-n7-directunroll7-qonly-b1024u1024-poll75-screen-20260624T135503Z` | 128/128 | 97.160 | 97.160 | screen only; poll=75 still below poll=100 |
| `gemma4-q8-gpu2-mtp-n7-directunroll7-qonly-b1024u1024-vmm1-screen-20260624T135503Z` | 128/128 | 97.100 | 97.100 | screen only; VMM=1 still below VMM=0 |
| `gemma4-q8-gpu3-mtp-n7-directunroll7-qonly-b1024u1024-th8-screen-20260624T135503Z` | 128/128 | 98.847 | 98.847 | fastest screen only; required full validation |
| `gemma4-q8-gpu3-mtp-n7-directunroll7-qonly-b1024u1024-th8-full-20260624T135701Z` | 384/384 | 98.491 | 97.886 | promoted here; later superseded by the `98.617` SYCL-graph-on run |
| `gemma4-q8-gpu1-mtp-n7-directunroll7-qonly-b1024u1024-th8-poll75-screen-20260624T135701Z` | 128/128 | 97.421 | 97.421 | screen only; poll=75 loses |
| `gemma4-q8-gpu2-mtp-n7-directunroll7-qonly-b1024u1024-th8-vmm1-screen-20260624T135701Z` | 128/128 | 96.987 | 96.987 | screen only; VMM=1 loses |

## Learning

`BATCH_SIZE=1024` / `UBATCH_SIZE=1024` is a real improvement for the current
direct-unroll/q-only MTP path. Lowering `THREADS` from 16 to 8 slightly improves
the fresh first row on this shape, likely by reducing CPU scheduler overhead in
the single-slot server path. `POLL=75` and `GGML_SYCL_ENABLE_VMM=1` both lost
again, so the next Q8 work should not spend more time there.

This still leaves the primary research target unresolved: Q8 fresh-response
throughput is now `98.617 tok/s`, but the desired target remains `>150 tok/s`.
The remaining gap is unlikely to close via small launch flags; it likely needs
the assistant-token loop to avoid one full `llama_decode()` per draft token or a
fresh-valid speculation source with much higher accepted tokens per verifier
step.

## Follow-Up Code Negative: Direct Sampled-Copy Fast Path

Patch artifact:
`patches/gemma4-26b-a4b-q8-b70/20260624T1410-llamacpp-mtp-direct-sampled-copy-loss.patch`.

Idea: for the direct argmax-ID MTP path, bypass `build_seq_to_output_row()` and
the generic `copy_tensor_async_ints()` map walk when there is exactly one output
row and one sampled-token tensor. This is semantically equivalent for the
single-sequence direct-unroll path and should reduce a small CPU-side copy/mapping
cost.

Result:

| Run | Canary | Fresh row 0 tok/s | Repeated mean | Decision |
| --- | ---: | ---: | ---: | --- |
| `gemma4-q8-gpu0-mtp-n7-directunroll7-qonly-b1024u1024-th8-directsamplecopy-screen-20260624T140848Z` | 128/128 | 98.591 | 98.591 | screen slightly above current full but below best screen; required full |
| `gemma4-q8-gpu0-mtp-n7-directunroll7-qonly-b1024u1024-th8-directsamplecopy-full-20260624T141012Z` | 384/384 | 96.861 | 97.728 | **rejected**; row 0 fresh is below the promoted record |

The patch was reverted from `/home/steve/src/llama.cpp-gemma-record-stack` after
the full run, and the server binary was rebuilt back to the promoted record
stack. Keep the patch artifact so future agents do not retry this small CPU
shortcut as a likely record breaker.

## Follow-Up Code Negative: Skip Unused Gemma4 Assistant K/V Index Inputs

Patch artifact:
`patches/gemma4-26b-a4b-q8-b70/20260624T1420-llamacpp-gemma4-mtp-skip-unused-kv-idx-inputs-loss-current.patch`.

Idea: the existing `LLAMA_GEMMA4_MTP_QONLY_ATTN_INPUTS=1` path builds
`self_k_idxs` / `self_v_idxs` and SWA variants in `build_attn_inp_kv_iswa()`,
then nulls them in `gemma4-assistant.cpp` because Gemma4 MTP uses shared target
K/V and passes `k_cur` / `v_cur` as `nullptr`. The tested patch moved that skip
into the input builder so those unused tensors were not created or uploaded.

Result:

| Run | Canary | Fresh row 0 tok/s | Repeated mean | Decision |
| --- | ---: | ---: | ---: | --- |
| `gemma4-q8-gpu0-mtp-n7-qonly-skipidx-screen-20260624T141843Z` | 128/128 | 97.884 | 97.884 | **rejected**; below the promoted record |

The loss suggests these tiny input tensors are not on the hot path, or that
the changed graph/input shape disturbed reuse/scheduling enough to erase the
small expected CPU-side gain. The patch was reverted from the llama.cpp
worktree and the server binary was rebuilt back to the promoted record stack.

## Follow-Up Runtime Negative: Higher Direct-Unroll Depths

Idea: the `n=7` direct-unroll path is still far below the `>150 tok/s` target,
so test whether allowing longer fresh MTP drafts produces enough extra accepted
tokens per verifier step to offset a larger assistant graph. This is
fresh-response valid because the draft source is the Q4_0 MTP model operating on
the current request, not prior benchmark history.

Common config: Q8 target, Q4_0 MTP draft, `BATCH_SIZE=1024`,
`UBATCH_SIZE=1024`, `THREADS=8`, `POLL=100`, `VMM=0`, q-only assistant inputs,
direct argmax-ID unroll, `CANARY_REPEATS=32`, `BENCH_REPEATS=1`, filled-long
588/512 shape.

| Run | Canary | Fresh row 0 tok/s | Wall tok/s | Decision |
| --- | ---: | ---: | ---: | --- |
| `gemma4-q8-gpu0-mtp-n8-directunroll8-qonly-b1024u1024-th8-screen-20260624T142319Z` | 128/128 | 64.646 | 58.982 | rejected |
| `gemma4-q8-gpu1-mtp-n10-directunroll10-qonly-b1024u1024-th8-screen-20260624T142319Z` | 128/128 | 73.084 | 66.036 | rejected |
| `gemma4-q8-gpu2-mtp-n12-directunroll12-qonly-b1024u1024-th8-screen-20260624T142319Z` | 128/128 | 76.976 | 69.097 | rejected |
| `gemma4-q8-gpu3-mtp-n16-directunroll16-qonly-b1024u1024-th8-screen-20260624T142319Z` | 128/128 | 88.695 | 78.382 | rejected |

Increasing unroll depth makes the assistant graph more expensive faster than it
improves accepted tokens for this benchmark. The current `n=7` full record
(`98.491 tok/s`, later superseded by `98.617`) remained the promoted
fresh-response result at this point. Do not spend more
time on naive higher `n_max` unless the assistant graph is made substantially
cheaper first.

## Follow-Up Runtime Negative: Lower Direct-Unroll Depths

Idea: after the higher-depth loss, test whether `n=7` is over the local optimum
and whether a smaller assistant graph can improve first-row fresh response
speed despite accepting fewer tokens per verifier step.

Common config: Q8 target, Q4_0 MTP draft, `BATCH_SIZE=1024`,
`UBATCH_SIZE=1024`, `THREADS=8`, `POLL=100`, `VMM=0`, q-only assistant inputs,
direct argmax-ID unroll, `CANARY_REPEATS=32`, `BENCH_REPEATS=1`, filled-long
588/512 shape.

| Run | Canary | Fresh row 0 tok/s | Wall tok/s | Decision |
| --- | ---: | ---: | ---: | --- |
| `gemma4-q8-gpu0-mtp-n3-directunroll3-qonly-b1024u1024-th8-screen-20260624T142556Z` | 128/128 | 72.379 | 65.471 | rejected |
| `gemma4-q8-gpu1-mtp-n4-directunroll4-qonly-b1024u1024-th8-screen-20260624T142556Z` | 128/128 | 78.750 | 70.610 | rejected |
| `gemma4-q8-gpu2-mtp-n5-directunroll5-qonly-b1024u1024-th8-screen-20260624T142556Z` | 128/128 | 84.703 | 75.390 | rejected |
| `gemma4-q8-gpu3-mtp-n6-directunroll6-qonly-b1024u1024-th8-screen-20260624T142556Z` | 128/128 | 90.769 | 79.960 | rejected |

Lowering unroll depth also loses. The current shape is monotonic up to `n=7`
and then degrades badly for naive higher `n`. The next useful work is not more
`n_max` flag sweeping; it is reducing the assistant graph cost or replacing the
serial assistant decode path with a fresh-valid speculation source that accepts
substantially more tokens per verifier step.

## Follow-Up Code Negative: Fixed Sampled-Token Pack Instead Of Concat

Patch artifact:
`patches/gemma4-26b-a4b-q8-b70/20260624T1431-llamacpp-gemma4-mtp-sampled-pack-crash-current.patch`.

Idea: replace the direct-unroll `sampled_all = concat(sampled_all, sampled)`
chain with a fixed `I32[n_unroll]` output tensor and per-step `cpy` nodes into
one-token views. This was meant to remove the sampled-token `GGML_OP_CONCAT`
chain without changing draft-token semantics.

Result: **crashed before readiness** during server model load / scheduler
reserve:

```text
ggml/src/ggml-alloc.c:623: GGML_ASSERT(buffer_id >= 0) failed
ggml_gallocr_allocate_node -> ggml_backend_sched_reserve -> llama_context::decode
```

The likely issue is allocator/backend placement for a plain fixed tensor used as
the destination of view-copy side effects. The patch was reverted immediately,
and the llama-server binary was rebuilt back to the promoted record stack. Do
not retry this exact fixed-destination shape without first solving graph output
buffer assignment for side-effect copy destinations.

## Follow-Up Runtime Negative: `p_split` On Current Q-Only Direct-Unroll Shape

Idea: `--spec-draft-p-split` helped some older Gemma MTP lanes, but had not
been tested on the current promoted Q8 target / Q4_0 draft / direct-unroll /
q-only assistant-inputs recipe. Screen four values in parallel.

Common config: Q8 target, Q4_0 MTP draft, `MTP_N_MAX=7`, `MTP_N_MIN=2`,
`MTP_P_MIN=0.12`, `BATCH_SIZE=1024`, `UBATCH_SIZE=1024`, `THREADS=8`,
`POLL=100`, `VMM=0`, direct argmax-ID unroll 7, q-only assistant inputs,
`CANARY_REPEATS=32`, `BENCH_REPEATS=1`, filled-long 588/512 shape.

| Run | `p_split` | Canary | Fresh row 0 tok/s | Wall tok/s | Decision |
| --- | ---: | ---: | ---: | ---: | --- |
| `gemma4-q8-gpu0-mtp-n7-directunroll7-qonly-b1024u1024-th8-psplit005-screen-20260624T144018Z` | 0.05 | 128/128 | 96.940 | 84.594 | rejected |
| `gemma4-q8-gpu1-mtp-n7-directunroll7-qonly-b1024u1024-th8-psplit010-screen-20260624T144018Z` | 0.10 | 128/128 | 97.622 | 84.966 | rejected |
| `gemma4-q8-gpu2-mtp-n7-directunroll7-qonly-b1024u1024-th8-psplit015-screen-20260624T144018Z` | 0.15 | 128/128 | 97.644 | 85.128 | rejected |
| `gemma4-q8-gpu3-mtp-n7-directunroll7-qonly-b1024u1024-th8-psplit020-screen-20260624T144018Z` | 0.20 | 128/128 | 95.986 | 83.737 | rejected |

All four are fresh-response valid (`cached_tokens=0`) and pass the screen
canary, but none beat the promoted full record (`98.491 tok/s at the time;
later superseded by `98.617`). Do not keep
sweeping `p_split` on this identity unless another code change materially
changes the draft acceptance/cost balance.

## Follow-Up Code Negative: Split Gemma4 Assistant `nextn.pre_projection`

Patch artifact:
`patches/gemma4-26b-a4b-q8-b70/20260624T1445-llamacpp-gemma4-mtp-split-preproj-loss-current.patch`.

Idea: remove the main direct-unroll assistant `inp_xh = concat(x_step, h_in)`
by splitting quantized `nextn.pre_projection.weight` into two block-aligned
views (`W_x`, `W_h`) and computing `W_x*x_step + W_h*h_in`. The Q4_0
pre-projection tensor is `[5632,1024]`; the split point `2816` is Q4_0
block-aligned, so the transform is algebraically valid if the backend accepts
the views. The patch was gated by `LLAMA_GEMMA4_MTP_SPLIT_PREPROJ=1`.

Result:

| Run | Canary | Fresh row 0 tok/s | Wall tok/s | Decision |
| --- | ---: | ---: | ---: | --- |
| `gemma4-q8-gpu0-mtp-n7-splitpreproj-qonly-b1024u1024-th8-screen-20260624T144344Z` | 128/128 | 97.316 | 85.324 | **rejected**; below the promoted record |

The backend accepted the quantized views and correctness held on the screen
canaries, but replacing one concat + matmul with two smaller matmuls + add is
slower on this B70/SYCL stack. The patch was reverted and the binary rebuilt
back to the promoted record stack. This rules out the simple algebraic split as
the path to command-graph/cost wins; a useful concat-free pre-projection would
need a fused two-input matmul/kernel, not two ordinary quantized matmuls.

## Follow-Up Code Negative: Allow Kernel-Backed SYCL `CONCAT` Graph Capture

Patch artifact:
`patches/gemma4-26b-a4b-q8-b70/20260624T1452-llamacpp-sycl-allow-kernel-concat-graph-current.patch`.

Idea: SYCL graph compatibility rejects all `GGML_OP_CONCAT` nodes because
`ggml_sycl_op_concat()` can use a blocking `memcpy().wait()` path. The Gemma4
assistant direct-unroll graph uses dim-0 concat for `x_step + h_in`; the
blocking concat path in `concat.cpp` is specific to contiguous dim-3 concat, so
the experiment added an opt-in `GGML_SYCL_GRAPH_ALLOW_KERNEL_CONCAT=1` gate
that permits non-dim-3 concat nodes through graph compatibility.

Config: same Q8 target / Q4_0 MTP draft / direct argmax-ID unroll 7 / q-only
assistant inputs / `BATCH_SIZE=1024` / `UBATCH_SIZE=1024` / `THREADS=8` /
`POLL=100` / `GGML_SYCL_DISABLE_GRAPH=0` identity as the current record, plus
`GGML_SYCL_GRAPH_ALLOW_KERNEL_CONCAT=1`. Screen used `CANARY_REPEATS=32`,
`BENCH_REPEATS=1`, filled-long 588/512 shape.

Result:

| Run | Canary | `cached_tokens` | Fresh row 0 tok/s | Wall tok/s | Decision |
| --- | ---: | ---: | ---: | ---: | --- |
| `gemma4-q8-gpu0-mtp-n7-directunroll7-qonly-b1024u1024-th8-syclgraph0-concatgraph-screen-20260624T150422Z` | 128/128 | 0 | 89.581 | 79.405 | **rejected**; slower than current `98.617` record |

Server log:
`/mnt/fast-ai/bench-results/gemma4-26b-a4b-q8/servers/gemma4-q8-gpu0-mtp-n7-directunroll7-qonly-b1024u1024-th8-syclgraph0-concatgraph-screen-20260624T150422Z.server.log`.
The run reused graphs and stayed correct, but throughput fell sharply. The
patch was reverted and the llama-server binary rebuilt back to the known record
stack. Do not promote broad concat graph enablement on this evidence; if graph
capture is revisited, instrument exactly which graph is captured and why the
assistant path slows down before trying another concat compatibility relaxation.
