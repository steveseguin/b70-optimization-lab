# Qwen27 100 tok/s execution plan

Date: 2026-07-09

## Objective and completion gate

Move the current one-B70 Qwen3.6 27B AutoRound INT4 record from
`68.23626314761921 tok/s` to at least `100 tok/s` without changing target
model quality or using cache/history effects.

Completion requires:

- the fixed realistic prompt suite, each prompt once as a fresh response;
- `cached_tokens=0` on every request and no prompt/KV/history/response reuse;
- median generated-token throughput for tokens 1-100 after TTFT at or above
  `100 tok/s`;
- repeat64 quality and baseline-output match;
- a same-window/crossover variance check across the four B70 GPUs;
- exact model, quantization, runtime, patch, flags, hashes, logs, and results
  preserved;
- focused commit/push and LocalMaxxing submission only after the full gate.

## Starting point

- target: `webhie/Qwen3.6-27B-int4-AutoRound`;
- target body: AutoRound W4A16, 64 dense layers, including 48 GDN layers;
- target LM-head: runtime INT8 with BF16 scales;
- draft LM-head: runtime INT4 with BF16 scales;
- MTP3/cg8 with exact ReplaySSM state handling;
- accepted depth: `2.746954` verified tokens/step;
- inferred verifier-step cost: `40.2565 ms`;
- current valid result: `68.2363 tok/s`.

At current acceptance, 100 tok/s requires a `27.4695 ms` step, or
`12.787 ms` removed. MTP3 alone cannot exceed four visible tokens/step, so
the plan must reduce target cost before acceptance work can cross 100.

## Phase 1: GDN fused output projection - completed no-win

Integrate `_xpu_C.qwen_gdn_out_proj_int4_w4a16` behind
`VLLM_XPU_GDN_FUSED_OUT_PROJ_INT4=1`. The op combines the per-head gated
RMSNorm workspace producer with the following INC W4A16 output projection.

The full-shape synchronized microbenchmark reduced an **eager PyTorch
reference** from `0.20749 ms` to `0.03114 ms`, but that reference did not
represent the compiled endpoint. Endpoint crossover proved the candidate flat
or slower (`65.07` candidate versus `66.64` control on GPU 0; `65.49` versus
`65.46` on GPU 1). Torch compile already fused the pointwise boundary around
the oneDNN projection. The active integration was removed and the patch/result
were preserved in `2026-07-09-gdn-fused-outproj-endpoint-no-win.md`.

Implementation restrictions:

- XPU and TP1 only;
- INC symmetric INT4 W4A16, group size 128;
- head dimension 128;
- SiLU/swish, `norm_before_gate=True`, no bias;
- contiguous three-dimensional core/gate tensors;
- automatic fallback for traces or unsupported layers;
- default off.

Validation:

1. Python syntax and fullgraph custom-op compile smoke.
2. Real model startup and strict fresh diagnostic.
3. Four-GPU crossover: control/candidate on two GPUs, then swap.
4. If the endpoint delta exceeds variance, repeat64 quality and baseline match.

## Phase 2: backend screens - completed no-win

Two direct backend screens ruled out simple swaps:

- draft LM-head W4A8 including per-token quantization: `1.1703 ms/call`,
  versus current W4A16 `1.1418 ms/call`;
- Xe2 grouped W4A16 versus oneDNN at rows=4: gate/up shape `0.2154` versus
  `0.1990 ms`, down-projection shape `0.1796` versus `0.1113 ms`.

These results leave no endpoint candidate and confirm that oneDNN is already
the best available dense W4A16 primitive for these shapes. A future body kernel
must fuse a materially larger boundary and beat the compiled graph, not only an
eager reference.

## Phase 3: external draft acceptance - completed no-go

Corrected DFlash produced `2.731579` visible tokens/step and only `52.03 tok/s`.
Current ReplaySSM EAGLE3 compressed/full produced `2.047619` and `1.969697`
visible tokens/step. All are below intrinsic MTP3 (`2.746954`) before proposal
cost and are closed for these checkpoints.

## Phase 4: position-specific intrinsic MTP predictors - active

The target checkpoint contains one MTP layer, and every speculative position
reuses `mtp.layers.0`. MTP4/MTP5 therefore add verifier rows while later draft
quality collapses. Implement an endpoint-compatible experiment with distinct
predictors for positions 1..N:

1. clone the existing MTP layer as initialization for each position;
2. train each position on target-owned hidden-state/token trajectories, with
   the fixed realistic suite held out from training;
3. export standard `mtp.layers.{i}` weight keys plus the matching
   `num_nextn_predict_layers` config;
4. make the proposer select `spec_step_idx` without modulo collapse;
5. acceptance-gate graph-off on cold unique prompts before endpoint tuning;
6. test MTP4/MTP5 only if visible tokens/step materially exceeds `2.747` and
   projects to a plausible `100 tok/s` endpoint.

Target output quality is unchanged because every emitted token remains verified
by the declared target. Draft training data, checkpoint hashes, acceptance, and
endpoint results must still be preserved.

## Phase 5: acceptance depth after cost reduction

Only after the verifier step is materially cheaper or the multi-position draft
raises depth, revisit legal branch/regeneration. The current rank-64 optimistic
MTP3 envelope reaches `3.9681` visible tokens/step. At a `31.8-36 ms`
post-fusion step, that envelope becomes roughly `110-125 tok/s` before branch
overhead and has a real overhead budget for a 100 tok/s endpoint.

Any branch implementation must remain target-verified and operate on fresh
responses. No post-hoc oracle, repeated-output history, n-gram warming, or
cached continuation is valid.

## Stop/continue rules

- Preserve every tested patch and result, including compile failures and
  no-wins.
- Close a mechanism only after a measured same-window result or a quantitative
  pre-gate proves it cannot contribute multiple milliseconds or sufficient
  accepted depth.
- Continue from Phase 1 into Phase 2/3 until the strict 100 tok/s gate passes
  or a concrete kernel/backend blocker is demonstrated and recorded.
