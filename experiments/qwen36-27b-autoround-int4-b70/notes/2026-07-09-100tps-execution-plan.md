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

## Phase 4: position-specific intrinsic MTP predictors - FC/adapter lanes closed

Architecture correction: this checkpoint resolves to `Qwen3_5MTP`; the legacy
launcher method name `qwen3_next_mtp` is normalized to `mtp`. Its canonical
depth field is `text_config.mtp_num_hidden_layers=1`. Every speculative
position therefore reuses `mtp.layers.0`, and MTP4/MTP5 add verifier rows while
later draft quality collapses.

Cloning full `mtp.layers.N` is not the first experiment: each layer owns a
distinct draft KV cache, so clone-only layers do not reproduce the populated
layer-0 prefix cache without additional writable-cache sharing. The active
endpoint-compatible experiment instead keeps the one proven attention layer
and specializes its full-precision `mtp.fc` input projection by draft depth:

1. clone `mtp.fc.weight` into `mtp.position_fcs.{i}.weight` for each position;
2. keep position 0 frozen in conservative variants so first-draft behavior is
   exactly the current winner, while later positions specialize;
3. train on target-owned hidden-state/token trajectories, using
   conditional-prefix loss and holding the fixed realistic suite out;
4. declare `text_config.xpu_mtp_num_position_fcs` in a candidate overlay and
   select the FC by the zero-based `spec_step_idx` in active `Qwen3_5MTP`;
5. start graph-off with
   `--model-loader-extra-config '{"enable_weights_track":true}'`, then
   acceptance-gate on cold unique prompts before endpoint tuning;
6. test MTP4/MTP5 only if visible tokens/step materially exceeds `2.747` and
   projects to a plausible `100 tok/s` endpoint.

The first three-position mechanical artifact already passed:

- actual XPU training and safetensors export;
- evaluator readback and step routing;
- Qwen3.5 endpoint load with missing-weight tracking;
- cold OpenAI smoke and a one-prompt, 512-token, `cached_tokens=0` request;
- graph-off diagnostic throughput `52.595 tok/s` (not promotable; tiny smoke
  training and quality intentionally skipped).

The completed five-position FC matrix improved acceptance and transferred to a
separate unseen corpus, but did not pass the endpoint pre-gate: the best
all-FC candidate measured `2.763428` visible tokens/step on training-heldout
starts and `2.773804` on unseen v6b, versus about `2.747` for the current MTP3
endpoint. Two extra verifier rows would cost more than this small depth gain can
recover, so FC-only specialization is closed without an endpoint run. See
`2026-07-09-position-fc-mtp5-transfer-insufficient.md`.

The position-specific residual-adapter successor is also closed before an
endpoint run. Four ranks over `65,536` starts peaked at `2.810669` visible
tokens/step on separate unseen v6b data. A second rank-512 epoch across four
learning rates reached only `2.857300` on training-heldout data, while larger
rates regressed. Both are below the fixed `3.3` endpoint-trial gate and far
below the `5.1-5.2` acceptance-only requirement. See
`2026-07-10-position-adapter-converged-no-endpoint.md`.

The full target-conditioned MTP refinement lane is also closed. Direct cloned
replacement fell from a `2.218` base to at most `1.866`; a zero-preserving
scalar/vector gate recovered base behavior but peaked at only `2.241883`, far
below `3.3`. See `2026-07-10-direct-stacked-refinement-no-win.md` and
`2026-07-10-gated-stacked-refinement-no-win.md`.

Acceptance-only adaptation is exhausted for this checkpoint. The active lane
is target-body cost: use aggregate graph-none synchronized regions to rank
linear attention, full attention, and MoE/MLP. Level Zero `unitrace` was tried
in both online and offline modes, but per-kernel event tracing expanded graph
replay so severely that eight tokens did not finish in 15 minutes; do not spend
more runs on that profiler integration.

Training requirements remain:

1. train each position on target-owned hidden-state/token trajectories, with
   the fixed realistic suite held out from training;
2. split heldout data by prompt/family for promoted training, not only lexical
   file order;
3. require endpoint acceptance traces because earlier shared-FC offline gains
   did not transfer to the strict suite.

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
- Continue through the active learned-predictor/kernel phases until the strict
  100 tok/s gate passes
  or a concrete kernel/backend blocker is demonstrated and recorded.
