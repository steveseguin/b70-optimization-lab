# 2026-07-06 - Qwen27 draft proposer timing split

## Context

Current valid Qwen27 recipe remains:

- `webhie/Qwen3.6-27B-int4-AutoRound`
- TP1 on one B70
- XPU graph `PIECEWISE`, `max_cudagraph_capture_size=8`
- MTP3 with ReplaySSM exact GDN
- runtime target INT8 LM-head with BF16 scales
- runtime draft INT4 LM-head, group 128, BF16 scales

Valid strict record remains `67.519 tok/s` median tokens 1-100 after TTFT
(`cmr8rg5d900glqr01g4fesy6i` on LocalMaxxing). A repaired-source support run
landed at `67.338 tok/s`; a timing sanity run landed at `67.498 tok/s`.

## New diagnostic labels

Patch snapshot:

- `patches/qwen36-27b-autoround-int4-b70/source-snapshots/vllm-active-before-draft-handoff-timing-20260706.patch`
- `patches/qwen36-27b-autoround-int4-b70/source-snapshots/vllm-draft-proposer-timing-labels-20260706.patch`

The labels are default-inert and only active with `VLLM_XPU_DECODE_TIMING=1`.
They split CPU handoff and the MTP proposer body.

## Runs

`qwen27-draft-handoff-timing-20260706T104620Z`

- strict gate: pass; `cached_tokens=0`; quality skipped intentionally
- median diagnostic throughput: `60.755 tok/s` (not a record claim; sync timing)
- CPU handoff is tiny:
  - draft token CPU copy launch: `0.066 ms/step`
  - draft CPU event wait: `0.024 ms/step`
  - draft CPU tolist: `0.030 ms/step`
  - valid-count copy/wait/tolist combined: about `0.124 ms/step`
- decision: do not chase CPU handoff for the 65 -> 100 gap.

`qwen27-proposer-gap-timing-20260706T105148Z`

- strict gate: pass; `cached_tokens=0`; quality skipped intentionally
- median diagnostic throughput: `59.588 tok/s` (not a record claim; broader sync)
- synchronized proposer split:
  - target model forward wrapper: `23.46 ms/step`
  - draft proposer wrapper: `21.18 ms/step` under intrusive sync timing
  - draft greedy sample total: `1.356 ms/sample row`, 3 rows per MTP3 step
  - draft greedy compute logits: `1.184 ms/sample row`
  - MTP next/first forward context total: about `2.49 ms/step`
  - rejection sampler: `0.401 ms/step`
  - all prepare/copy/metadata pieces are sub-ms individually

The sync labels perturb absolute runtime, but they expose a real draft LM-head
cost hidden by async host timing: roughly `3.5-4.1 ms/MTP3 step`. This is a
medium-sized opportunity, not enough by itself to reach `100 tok/s`.

## Decision

Closed:

- CPU handoff / `tolist` / valid-count copy: not material.
- Generic Python metadata/copy pieces inside the proposer: too small.

Still worth work:

1. Draft greedy LM-head reduction: avoid three full draft logits per MTP3 step
   if exact top-1 can be produced more cheaply.
2. Accepted tokens per target step: current mean acceptance length is about
   `2.6-2.8`; reaching `100 tok/s` likely needs a stronger drafter or deeper
   verified speculation, not only micro-optimizing MTP3.
3. Target forward/GDN state path: target forward remains the largest required
   bucket at about `23-24 ms/step`; any exact reduction there has high leverage.

Next concrete lane: either prototype a draft-side exact top-1 path for INT4
LM-head, or return to accepted-token-per-step work with a stronger target-matched
drafter. Do not publish these timing runs as headline throughput.

## Draft INT4 LM-head microbench

`scripts/bench-qwen27-draft-int4-lmhead.py` was added as a standalone
diagnostic for the exact current draft-head primitive:

- hidden `[rows, 5120]`
- packed W4 logical `[5120 / 8, 248320]`
- BF16 per-group scales, group size `128`
- dense logits through `torch.ops._xpu_C.int4_gemm_w4a16`
- argmax over the dense logits

Run:

```bash
ZE_AFFINITY_MASK=0 ONEAPI_DEVICE_SELECTOR=level_zero:0 \
  /home/steve/.venvs/vllm-xpu/bin/python \
  scripts/bench-qwen27-draft-int4-lmhead.py \
  --rows 1,2,3,4 --warmup 10 --iterations 30 \
  --output-json data/qwen36-27b-autoround-int4-b70-baselines/qwen27-draft-int4-lmhead-microbench-20260706T110212Z.json
```

Median results:

| rows | dense logits | dense logits + argmax | argmax delta |
| ---: | ---: | ---: | ---: |
| 1 | `1.138 ms` | `1.185 ms` | `0.047 ms` |
| 2 | `1.155 ms` | `1.206 ms` | `0.051 ms` |
| 3 | `1.159 ms` | `1.214 ms` | `0.055 ms` |
| 4 | `1.167 ms` | `1.207 ms` | `0.040 ms` |

Interpretation:

- The draft proposer calls greedy sampling sequentially: `6412` draft samples
  for `2124` spec steps in
  `qwen27-proposer-gap-timing-20260706T105148Z`, so MTP3 pays the row-1 head
  path about three times per step.
- Current dense INT4 head plus argmax is already about `1.18 ms` for one row.
  A true fused W4A16 top-token op can save only the avoidable dense-logit write
  and separate argmax, so the endpoint upside is bounded to roughly
  `<= 3.5 ms/step` even if the replacement were perfect.
- This is still a valid tactical target, but it is not by itself a route from
  `~67 tok/s` to `100+ tok/s`. The larger route still needs better accepted
  tokens per target step, a stronger drafter, or target-forward reduction.

## Experimental INT4 top-ID native prototype: closed no-win

A scalar native XPU prototype was built as
`torch.ops._xpu_C.int4_gemm_w4a16_top1` to test whether avoiding dense
`[rows, vocab]` logits could beat oneDNN for the draft MTP LM-head. The
prototype returns `(top_ids, top_values)` and was compared directly against
`int4_gemm_w4a16(...).argmax(-1)`.

Build/runtime lessons:

- Do **not** build this vLLM XPU extension with the umbrella oneAPI 2026
  runtime for the current torch stack. The 2026 build linked `libsycl.so.9`;
  it either segfaulted on import or broke oneDNN engine creation when mixed
  with the torch `libsycl.so.8` runtime.
- Compatible build path was compiler `2025.3` plus a G31-only AOT relink:
  `VLLM_XPU_AOT_DEVICES=bmg-g31-a0` and
  `VLLM_XPU_XE2_AOT_DEVICES=bmg-g31-a0`. Generic `bmg` maps to `20.1.0`
  (`bmg-g21-a0`), while `bmg-g31-a0` maps to `20.2.0`; B70 reports device
  id `0xE223` and `256` EUs, so G31 is the right target to test.
- Full all-target AOT links (`pvc,bmg,bmg-g21-a0,bmg-g31-a0`) can spend many
  minutes in `ocloc`; narrow B70 experiments should use G31-only relinks unless
  a portable artifact is explicitly needed.

Patch/result artifacts:

- before-source snapshot:
  `patches/qwen36-27b-autoround-int4-b70/source-snapshots/vllm-xpu-kernels-before-int4-topid-20260706T110614Z.patch`
- no-win prototype patch:
  `patches/qwen36-27b-autoround-int4-b70/source-snapshots/vllm-xpu-kernels-int4-topid-prototype-no-win-20260706.patch`
- smoke:
  `data/qwen36-27b-autoround-int4-b70-baselines/qwen27-draft-int4-topid-smoke-20260706T1231Z.json`
- compact full microbench:
  `data/qwen36-27b-autoround-int4-b70-baselines/qwen27-draft-int4-topid-microbench-20260706T1232Z.json`

Median results from the compact full microbench:

| rows | ID match vs dense argmax | dense logits | dense logits + argmax | experimental top-ID |
| ---: | :---: | ---: | ---: | ---: |
| 1 | yes | `1.170 ms` | `1.218 ms` | `9.652 ms` |
| 2 | yes | `1.160 ms` | `1.200 ms` | `19.371 ms` |
| 3 | yes | `1.165 ms` | `1.213 ms` | `28.386 ms` |
| 4 | yes | `1.163 ms` | `1.218 ms` | `38.246 ms` |

Decision:

- Closed as **no-win**. The scalar prototype is exact for token IDs on the
  random test tensors but is about `8x` slower for row 1 and scales almost
  linearly with rows because it does scalar dot products rather than oneDNN/XMX
  tiled GEMM.
- Active `_xpu_C` was restored to the known-good pre-prototype extension after
  the benchmark; the top-ID source edits were removed from the active kernel
  tree and preserved only as the patch artifact above.
- If this lane is ever reopened, it needs a real XMX/DPAS/oneDNN-class producer
  or a oneDNN graph fusion that avoids dense writeback. Another scalar scan is
  not credible.

Next action: stop wrapper-level draft LM-head work and move to higher-leverage
work: stronger accepted-token-per-target-step mechanisms, legal branch/regenerate
infrastructure with exact GDN state, or target-forward/kernel reduction.

## Follow-up sync diagnostic: recurrent MTP-next is not an 11 ms eager kernel

Run:

- label: `qwen27-mtp-forward-syncdiag-20260706Tcont`
- summary:
  `data/qwen36-27b-autoround-int4-b70-baselines/qwen27-mtp-forward-syncdiag-20260706Tcont-candidate-summary-20260706Tsyncdiag.json`
- raw strict-suite JSON:
  `data/qwen36-27b-autoround-int4-b70-baselines/qwen27-mtp-forward-syncdiag-20260706Tcont-realistic128-chat-tokenids-qwensuite-20260706Tsyncdiag.json`
- server log:
  `/mnt/fast-ai/bench-results/qwen36-27b-autoround-int4-b70/candidates/qwen27-mtp-forward-syncdiag-20260706Tcont-20260706Tsyncdiag/server.stdout.log`
- MTP-next dispatch trace:
  `/mnt/fast-ai/bench-results/qwen36-27b-autoround-int4-b70/candidates/qwen27-mtp-forward-syncdiag-20260706Tcont-20260706Tsyncdiag/mtp-next-dispatch.jsonl`

This was a diagnostic-only strict fresh run. The final gate passed mechanically
(`cached_tokens=0` on all 12 prompts), but quality was intentionally skipped and
the inserted synchronization perturbs throughput, so do not promote it:

- median: `65.592 tok/s`, p10 `60.179`, mean `65.386`
- TTFT median: `486.882 ms`
- graph capture: `PIECEWISE`, 5 captures, `0.32 GiB`
- MTP-next trace: 24/24 recurrent dispatches were `PIECEWISE`, `batch_size=1`,
  `input_batch_size=1`, `num_actual_tokens=1`, `max_query_len=1`

Timing summary with synchronization only on
`spec_decode.propose.model_forward_first|next`:

| label | count | avg ms |
| --- | ---: | ---: |
| `gpu_model_runner.forward_total` | 2148 | `23.697` |
| `gpu_model_runner.model_forward` | 2148 | `23.640` |
| `gpu_model_runner.draft_total` | 2148 | `17.565` |
| `spec_decode.propose.model_forward_first` | 2148 | `0.747` |
| `spec_decode.propose.model_forward_next` | 4306 | `0.674` |

Interpretation:

- The earlier apparent `~11 ms` recurrent MTP-next result was async timing
  attribution. It is not evidence that recurrent MTP-next is falling out of XPU
  graph or running as an 11 ms eager kernel.
- The narrow synchronized labels prove the MTP layer calls themselves are
  sub-millisecond in this graph-dispatched shape.
- The large `draft_total` under this diagnostic is not a clean endpoint bucket:
  the sync labels inside it force ordering and make the enclosing host timer
  absorb dependency waits from target/sample/state work. It should not be used
  as a normal per-step cost estimate.

Closed:

- Do not optimize `model_forward_next` as an 11 ms kernel bug.
- Do not spend endpoint runs trying to "restore graph" for recurrent MTP-next;
  the dispatch trace already shows `PIECEWISE`.

Still credible:

1. Improve accepted tokens per target step with a stronger target-matched
   drafter or legal branch/regenerate support.
2. Reduce the target verifier forward / GDN exact-state transaction cost.
3. Add a real graph-safe GDN/DeltaNet state tape or equivalent transaction if
   deeper speculation depends on exact state rollback/commit.
4. Treat text-only recurrent `input_ids` MTP and static metadata reuse as small
   bounded cleanups only; previous quick attempts stalled graph capture, and
   the expected gain is sub-ms per MTP3 step.
