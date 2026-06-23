# Codex GDN Spec Parity Fix

Date: 2026-06-20

## Root Cause

The XPU GDN verifier path did not leave speculative recurrent state columns
equal to a one-token-at-a-time target-model decode. The original native
`_xpu_C.gdn_attention` interface only accepts one state index per sequence and
writes one final recurrent state. It has no way to receive the full
`spec_state_indices_tensor` table, so it cannot satisfy the verifier contract
for every target/draft/bonus column.

The first Python fix made the state columns exact by looping over speculative
positions and calling the heavy FLA chunk kernel once per position per layer.
That passed the synthetic recurrent-state check but failed the real endpoint
canary and was far too slow: the canary diverged at repeat 20/96 and throughput
fell to about 6.46 tok/s.

The definitive fix requires the spec column table to be handled inside the
native captured recurrent path, not by a Python per-position loop.

## Iteration 2 Changes

Implemented a native spec-decode path in `vllm-xpu-kernels`:

- added a `_xpu_C.gdn_attention_spec_decode` entry point that accepts
  `spec_state_indices_tensor`, `spec_query_start_loc`, `spec_token_indices`,
  `num_accepted_tokens`, and the conv/recurrent states;
- added spec-aware conv and recurrent kernels that step through each request's
  verifier positions sequentially and write the output/state for each spec
  column;
- changed the kernels to compute the accepted source column directly from
  `num_accepted_tokens`, avoiding separate helper kernels for accepted-state
  and base-conv-state materialization.

Updated `vllm/_xpu_ops.py` so XPU spec rows call the new native spec op instead
of the Python `_xpu_gdn_exact_spec_recurrent` per-position loop. No-spec native
decode was left on its existing path.

Also tested two follow-up acceleration attempts:

- a native indexed no-spec decode op to avoid Python `index_select` /
  `index_copy_` around `_xpu_C.gdn_attention`;
- a fused spec kernel combining conv, projection, gating, and recurrent update
  in one launch.

Neither follow-up was canary-safe.

## Validation

Direct-source native spec path, short endpoint probe:

```bash
cd /home/steve/llm-optimizations
MODEL_PATH=/mnt/fast-ai/qwen36-quark-int8-fp8-mtp-hybrid \
SERVER_LAUNCHER=scripts/launch-qwen36-quark-int8-accepted.sh \
VLLM_QWEN35_MTP_FORCE_FP8_BLOCK=1 \
VLLM_EXTRA_ARGS='--speculative-config {"method":"mtp","num_speculative_tokens":1}' \
COMPILATION_CONFIG='{"cudagraph_mode":"PIECEWISE","max_cudagraph_capture_size":128}' \
XPU_GRAPH=1 VLLM_XPU_ENABLE_XPU_GRAPH=1 VLLM_XPU_FORCE_GRAPH_WITH_COMM=1 \
VLLM_XPU_GRAPH_NOOP_COMM_CAPTURE=1 VLLM_XPU_GDN_NATIVE_FALLBACK=prefill \
VLLM_XPU_GDN_PREFILL_RECURRENT_FALLBACK=1 VLLM_XPU_DISABLE_PREFILL_CUDAGRAPH_REPLAY=1 \
VLLM_XPU_GREEDY_SAMPLE_TOPK_FALLBACK=1 VLLM_XPU_INT8_MOE_MIXED_WORKSPACE=1 \
GPU_MEMORY_UTILIZATION=0.95 ABLATION_FAST_GRAPH_AUTOCONFIG=0 \
VLLM_XPU_GDN_PROMOTE_ACCEPTED_SPEC_STATE=1 \
VLLM_XPU_GDN_NONSPEC_POSTPROCESS_ACCEPTED_STATE=0 \
JSON_REPEATS=7 COLOR_REPEATS=0 \
bash scripts/run-qwen36-ablation-candidate.sh tp4-mtp-k1-direct-source-json7
```

Result:

- json-canary: 7/7
- color-canary: 0/0, not run in this short probe
- corrected throughput: 42.3866 tok/s
- after-first throughput: 42.4695 tok/s
- decode latency: 25.885 ms/token

Earlier native spec path with postprocessing enabled:

- label: `tp4-mtp-k1-parity-fix-v2`
- corrected throughput: 56.9265 tok/s
- decode latency: 26.8588 ms/token
- json-canary failed at repeat 0
- color-canary did not complete cleanly because the server/device exited

Native indexed no-spec decode acceleration attempt:

- label: `tp4-mtp-k1-indexed-nonspec-json7`
- corrected throughput: 41.1101 tok/s
- json-canary failed at repeat 1

Fused spec kernel acceleration attempt:

- label: `tp4-mtp-k1-fused-json3`
- json-canary failed at repeat 1
- the server exited before the color probe could connect

Synthetic direct-source partial-acceptance check:

- z path matched exactly;
- core/recurrent outputs still showed small floating-point drift
  (`core` max absolute diff about `6e-05`, recurrent state diff about `4e-04`).

## Current Blocker

The native spec-table expansion is parity-capable on a short endpoint JSON
probe, but it is still far below the hard throughput target. The best
canary-safe native result was 42.3866 tok/s, versus the requested target of
roughly within 20% of the 93.55 tok/s no-spec baseline.

The remaining cost is still inside the captured native spec path: each GDN
layer/spec row materializes intermediate `q/k/v/b/a` tensors and launches the
spec conv plus spec recurrent kernels. Removing the Python per-position loop
fixed the catastrophic 6 tok/s path, but this two-kernel-plus-intermediate
native path is still about 2x too slow.

The attempted one-kernel fused native path is the likely required performance
direction, but the first implementation was not canary-safe. The most likely
remaining issue is an ordering/math mismatch in the fused path around
conv-state sourcing/writes, BA/Z gating, or recurrent-state publication for
partially accepted requests.

No commit was made because the required endpoint canary target was not met.

## Iteration 3 Changes

Implemented the untried sequence-path direction:

- added a diagnostic Python sequence-spec path in
  `vllm/model_executor/layers/mamba/gdn_linear_attn.py` that treats each
  request's verifier rows as one sequence via `spec_query_start_loc`;
- changed native `_xpu_C.gdn_attention_spec_decode` so spec rows are compacted
  and passed through the ordinary prefill/sequence GDN conv path once per layer,
  using `spec_query_start_loc`;
- preserved the accepted source state into the running column before the
  sequence call, then published per-position conv and recurrent state columns
  explicitly for partial acceptance;
- fixed recurrent sequence precision in the spec kernel by keeping the fp32
  accumulator live across a verifier sequence and only casting when storing
  per-position states;
- tried static GDN spec metadata for PIECEWISE graph replay, reusing the
  existing preallocated spec buffers for this spec-only path.

The XPU kernels were rebuilt with
`scripts/build-vllm-xpu-kernels-xpu-c-only.sh`, then `_xpu_C.abi3.so`,
`libgrouped_gemm_xe_2.so`, and `libgdn_attn_kernels_xe_2.so` were copied into
`vllm_xpu_kernels/`.

## Iteration 3 Validation

Required endpoint canary:

- label: `tp4-mtp-k1-parity-fix-v3`
- stamp: `20260620095119`
- corrected throughput: `45.3594 tok/s`
- json-canary: failed, `2/96` completed, first mismatch at repeat 1:
  `{"answer":"12","unit":"widgets"}`
- color-canary: failed after `3/96`; the server/device exited after the JSON
  mismatch
- summary:
  `/home/steve/llm-optimizations/data/qwen36-ablation-tp4-mtp-k1-parity-fix-v3-summary-20260620095119.json`

Static PIECEWISE metadata short probe:

- label: `tp4-mtp-k1-seq-v3-static-meta-json2`
- stamp: `20260620102149`
- corrected throughput: `51.8910 tok/s`
- json-canary: failed, `1/2` completed, first mismatch at repeat 0:
  `{"answer": "42", "历史悠久 Pioneer": "widgets"}`
- color-canary: `0/0`, passed by construction

Partial-accept diagnostic:

- label: `tp4-mtp-k1-seq-v3-all-or-nothing-json2`
- env: `VLLM_XPU_SPEC_DECODE_ALL_OR_NOTHING=1`
- stamp: `20260620102849`
- corrected throughput: `39.6901 tok/s`
- json-canary: passed, `2/2`
- color-canary: `0/0`, passed by construction

Earlier diagnostic contrast:

- cold JSON2 with metrics skipped passed;
- after-metrics JSON2 without tensor tracing failed;
- after-metrics JSON2 with GDN tensor digest tracing passed, but that trace
  performs CPU tensor reads/synchronization and masks the failure.

## Iteration 3 Blocker

The sequence path still does not pass the required endpoint canary and remains
far below the requested speed band near the `93.55 tok/s` no-spec baseline.
No commit was made.

The narrowest non-masking failure is partial-accept state publication for the
GDN recurrent cache. With normal partial acceptance, the endpoint diverges
after metrics on the JSON canary; with all-or-nothing acceptance, the same
short after-metrics JSON probe passes. The earlier synthetic direct-source
check also had exact z/conv output while core/recurrent state still drifted, so
conv history threading is not the first proven divergent state.

The remaining bad state is therefore the SSM/recurrent state column consumed
after a partial accept/reject boundary. For `num_speculative_tokens=1`, this is
the transition that chooses column 0 for accepted length 1 versus column 1 for
accepted length 2. The first endpoint-visible wrong token in the static-metadata
probe is completion token index 8, where the `unit` key is replaced by
`历史悠久 Pioneer` after several prior tokens were correct.

I could not capture a trustworthy per-layer first-difference line: every
state-tensor trace that reads conv/SSM values back to CPU changes the timing and
makes the short after-metrics JSON probe pass. Existing non-invasive evidence
points to SSM/recurrent publication after partial acceptance, not conv state,
but the exact GDN layer cannot be named from a non-masking trace.

## Iteration 4 Changes

Implemented the ReplaySSM spec-verify recurrent reconstruction as native
`_xpu_C` SYCL kernels:

- added `_xpu_C.gdn_replayssm_spec_decode` in `vllm-xpu-kernels`;
- fused the validated torch algebra for output-only reconstruction, history
  replay, chunked `(I + A)^-1` delta-rule transform, checkpoint flush, and
  ring writes;
- supported fp32/bf16/fp16 SSM checkpoint state and separate fp32/bf16/fp16
  `d_cache`/`k_cache` dtypes;
- matched the torch fallback's checkpoint rounding semantics by rounding
  checkpoint state through the activation dtype before compute and writing the
  rounded checkpoint state back even on non-flush requests;
- added `_xpu_C.gdn_replayssm_commit_pending` to fuse the pending accept cursor,
  early-flush metadata, and conv-state base-window update that had remained as
  torch `index_select`/`cat`/`gather`/`index_copy_` operations.

Updated `vllm/model_executor/layers/mamba/gdn_linear_attn.py` so the
ReplaySSM path calls the native recurrent kernel for `max_spec_len <= 2` and
`max_cache_len in (2, 4)`, and calls the native commit kernel when available.
The old torch implementations remain as env-gated fallbacks.

The XPU kernels were rebuilt with
`/home/steve/llm-optimizations/scripts/build-vllm-xpu-kernels-xpu-c-only.sh`,
then `_xpu_C.abi3.so` and `libgrouped_gemm_xe_2.so` were copied into
`/home/steve/src/vllm-xpu-kernels/vllm_xpu_kernels/`.

## Iteration 4 Validation

Focused native-vs-torch parity:

- endpoint-shaped initial state case: `q=[1,2,4,128]`,
  `v=[1,2,8,128]`, fp32 checkpoint/cache state:
  - `out` max diff: `0.0`
  - checkpoint state max diff: `0.0`
  - `d_cache` max diff: `4.77e-07`
  - `k_cache` max diff: `0.0`
  - `g_cache` max diff: `4.77e-07`
- endpoint-shaped nonzero-history/flush case:
  - `out` max diff: `0.0`
  - checkpoint state max diff: `2.38e-07`
  - `d_cache` max diff: `3.58e-07`
  - `k_cache` max diff: `0.0`
  - `g_cache` max diff: `1.19e-07`
- native commit kernel matched the torch helper exactly for contiguous and
  strided `conv_state` fixtures.

Micro-timing for `_xpu_C.gdn_replayssm_spec_decode` with endpoint dimensions:

- `~0.020 ms` per native recurrent call after warmup.

Endpoint attempts:

- stamp `20260620165239`: server stayed up after the cache dtype fix, but live
  metrics showed `0.1-0.2 tok/s` and zero draft accepts; stopped early.
- stamp `20260620170855`: after checkpoint rounding/writeback fix, first draft
  acceptance recovered briefly, but live generation stayed `0.1-0.3 tok/s` and
  acceptance alternated between accepted and rejected intervals; stopped early.
- stamp `20260620171916`: native commit kernel initially crashed because the
  real `conv_state` is a strided view; fixed by honoring strides instead of
  requiring contiguity.
- stamp `20260620172526`: after strided `conv_state` support, the endpoint
  stayed up but live generation throughput remained only `0.1-0.4 tok/s`.
  Spec metrics alternated between intervals such as:
  - Mean acceptance length `2.00`, accepted `1/1`
  - Mean acceptance length `1.00`, accepted `0/2`
  - Mean acceptance length `1.50`, accepted `1/2`
  - Mean acceptance length `2.00`, accepted `2/2`

The required json/color canaries were not allowed to complete on the slow
Iteration 4 runs; the live throughput was already orders of magnitude outside
the requested speed band and the runs were stopped to avoid burning the full
512-token probes.

## Iteration 4 Blocker

The fused recurrent ReplaySSM kernel itself is not the speed blocker: direct
timing is around `0.020 ms` per call for the endpoint shape. The remaining
endpoint speed bottleneck is the conv/spec scaffolding that is still executed
through torch before the recurrent kernel:

- `temp_conv_state = torch.cat((zeros_like(conv_state[:1]), ...))`
- `conv_state.index_select(...).clone()`
- `causal_conv1d_update(...)` over that temporary slot-copy state
- `_xpu_gdn_gather_padded_spec(...)`
- `torch.where(...)`
- `self._gdn_replayssm_conv_pending.index_copy_(...)`

This is exactly the unfused "conv state thread as a sequence, no slot-copy"
part of the requested work. The recurrent reconstruction and cursor/flush
metadata are now native and parity-matched, but the current path still builds a
temporary conv-state table and writes pending conv history through torch for
every GDN layer and verify step. That keeps the endpoint at `0.1-0.4 tok/s`
instead of near the `93.55 tok/s` baseline.

The next required kernel is a native sequence-threaded causal-conv/spec staging
path that consumes the base conv state plus raw spec sequence directly and
produces `q/k/v/a/b` and pending conv history without Python torch
materialization or slot-copy state. No commit was made because the endpoint
gate did not pass.

## Iteration 5 Changes

Implemented the ReplaySSM conv/spec staging fusion requested by Iteration 4:

- added `_xpu_C.gdn_replayssm_stage_conv`;
- threaded causal-conv state as a sequence across each request's speculative
  positions, reading the base conv window directly from the real strided
  `conv_state`;
- supported non-contiguous endpoint `mixed_qkv` input via source strides;
- wrote staged contiguous `q/k/v/a/b` tensors for the existing native
  ReplaySSM recurrent kernel;
- wrote raw padded rows directly into `_gdn_replayssm_conv_pending`;
- kept the previous torch staging path behind
  `VLLM_XPU_GDN_REPLAYSSM_STAGE_CONV_TORCH_FALLBACK=1`.

Rebuilt with
`/home/steve/llm-optimizations/scripts/build-vllm-xpu-kernels-xpu-c-only.sh`
and copied `_xpu_C.abi3.so` plus `libgrouped_gemm_xe_2.so` into
`/home/steve/src/vllm-xpu-kernels/vllm_xpu_kernels/`.

## Iteration 5 Validation

Focused native-vs-torch parity:

- endpoint-shaped strided `mixed_qkv` and DS-layout strided `conv_state`
  fixture passed against the old torch staging sequence;
- endpoint-sized stress fixture (`B=1`, `S=2`, local `conv_dim=2048`,
  `conv_state` stride `(294912, 1, 2048)`) ran 100 native calls on XPU without
  a fault;
- direct synchronized microbenchmark for endpoint shape, non-contiguous
  `mixed_qkv` stride `(4096, 2)`, and strided `conv_state` stride
  `(294912, 1, 2048)`: `_xpu_C.gdn_replayssm_stage_conv` averaged
  `0.0203 ms/call` over 1000 calls;
- short endpoint trace confirmed `gdn_replayssm_stage_conv` was selected on
  real requests (`mixed_qkv` was not contiguous, all other guards passed);
- short endpoint trace accepted `2/2` drafted tokens while using native
  staging.

Speed gate did not pass, so the required 96/96 json and 96/96 color canary was
not run to completion:

- no-trace endpoint probe
  `qwen36-ablation-tp4-mtp-k1-replayssm-stage-native-p64o32-notrace-20260620181740`
  reported corrected throughput `0.361 tok/s` and skipped canaries;
- all-rank timing probe
  `qwen36-replayssm-convfused-profile-allranks-p64o4-20260620183134`
  reported corrected throughput `0.649 tok/s` and skipped canaries.

Profiling result:

- first speculative decode step is dominated by one-time ReplaySSM cache/graph
  warmup, especially `qwen3_next.gdn.replayssm.ensure_state` and first
  `stage_conv_native` launch; all-rank decision:
  `gdn ensure_state 215.689 ms`, runner-up `gpu_model_runner.draft_total
  192.958 ms`, with large rank skew;
- after excluding the first spec decode step, steady all-rank p64/o4 timing
  showed rank-0 top regions:
  - `gpu_model_runner.forward_total`: `18.735 ms`
  - `gpu_model_runner.model_forward`: `18.572 ms`
  - `gpu_model_runner.draft_total`: `5.233 ms`
  - `qwen3_next.gdn.replayssm.commit_pending`: `1.034 ms`
  - `qwen3_next.gdn.replayssm.stage_conv_native`: `0.903 ms` total across 30
    GDN layers (`~0.030 ms/layer`)
  - `qwen3_next.gdn.replayssm.recurrent_native`: `0.810 ms` total across 30
    GDN layers (`~0.027 ms/layer`)

The old torch conv/spec staging sequence is no longer the steady-state
dominant op. The speed gate is still missed because the endpoint has large
first-spec-step warmup/recapture plus draft/proposer/runtime overhead, and the
client/vLLM decode histogram still reports multi-second decode time that is
not explained by steady native GDN kernel timings. No commit was made because
the required speed/canary gate did not pass.

## Iteration 6 Changes

Implemented the graph-capture lifecycle change in vLLM only:

- preallocated ReplaySSM spec rings for every GDN layer immediately after KV
  cache binding, before CUDA graph warmup/capture;
- moved ReplaySSM pending commit/cursor advancement out of the spec forward
  path and into the post-verify runner path, using sampler accepted counts;
- left the old in-forward commit behind
  `VLLM_XPU_GDN_REPLAYSSM_COMMIT_IN_FORWARD=1` for diagnostics only;
- copied ReplaySSM rings/cursors during Mamba COW slot promotion instead of
  resetting them unconditionally, with reset retained as the failure fallback.

Rebuilt with
`/home/steve/llm-optimizations/scripts/build-vllm-xpu-kernels-xpu-c-only.sh`
and copied `_xpu_C.abi3.so` plus `libgrouped_gemm_xe_2.so` into
`/home/steve/src/vllm-xpu-kernels/vllm_xpu_kernels/`.

## Iteration 6 Validation

Lightweight code checks:

- `.venv/bin/python -m compileall -q` on touched vLLM files passed;
- `git diff --check` on touched vLLM files passed;
- `uv run ruff format ...` was not usable in this environment because it tried
  to build editable vLLM and failed with `CUDA_HOME is not set`.

Required endpoint canary attempt:

- run stamp `qwen36-ablation-tp4-mtp-k1-replayssm-graphcaptured-20260620190018`;
- startup log confirmed `Preallocated ReplaySSM spec rings for 30 GDN layers
  (max_spec_len=2)` before PIECEWISE graph capture;
- server captured PIECEWISE graphs successfully;
- live throughput stayed around `0.1-0.4 tok/s`, far below the `~65 tok/s`
  minimum speed gate;
- the run was stopped during the long `p512/o512` metrics phase rather than
  burning tens of minutes on a known-failing speed result; no 96/96 canary
  claim was made.

Targeted all-rank timing profile:

- run stamp `qwen36-replayssm-graphcaptured-profile-allranks-p64o4-20260620191714`;
- corrected output throughput: `0.2377 tok/s`;
- vLLM decode histogram: `6423.13 ms/generation-token`;
- decision: runtime dominated by `gpu_model_runner.draft_total` at
  `1371.591 ms`, rank skew `114.650 ms`; runner-up
  `gpu_model_runner.compute_logits` at `0.749 ms`;
- spec decode bucket after this change:
  - `gpu_model_runner.forward_total`: mean `37.568 ms`, median `16.183 ms`,
    max `116.213 ms`;
  - `gpu_model_runner.model_forward`: mean `37.431 ms`, median `16.021 ms`,
    max `116.067 ms`;
  - `gpu_model_runner.draft_total`: mean `1296.899 ms`, median `12.169 ms`,
    max `5678.253 ms`;
  - `gpu_model_runner.sample_total`: mean `811.146 ms`, median `0.777 ms`,
    max `3485.257 ms`;
  - `gpu_model_runner.rejection_sampler`: mean `811.074 ms`, median
    `0.717 ms`, max `3485.157 ms`.

The first captured spec step is the concrete remaining outlier:

- step 2, rank 0: `draft_total 5678.253 ms`,
  `rejection_sampler 3101.785 ms`, `forward_total 93.059 ms`;
- step 2, rank 1: `draft_total 5022.935 ms`,
  `rejection_sampler 2961.897 ms`, `forward_total 86.535 ms`;
- step 2, rank 2: `draft_total 4969.505 ms`,
  `rejection_sampler 3485.157 ms`, `forward_total 114.832 ms`;
- step 2, rank 3: `draft_total 4945.830 ms`,
  `rejection_sampler 3419.965 ms`, `forward_total 116.213 ms`.

Later spec steps show the graph-captured target forward is mostly steady:

- step 5 rank 0: `forward_total 15.275 ms`, `draft_total 3.234 ms`;
- step 5 rank 2: `forward_total 15.255 ms`, `draft_total 3.120 ms`;
- step 6 rank 0: `forward_total 16.576 ms`, `draft_total 2.937 ms`;
- step 6 rank 3: `forward_total 15.164 ms`, `draft_total 16.040 ms`.

There is still a smaller later outlier:

- step 6 rank 2: `draft_total 47.894 ms`,
  `spec_decode.greedy_sample_total 12.795 ms`,
  `spec_decode.propose.model_forward_first 9.284 ms`,
  `forward_total 14.999 ms`.

Conclusion: ReplaySSM `ensure_state` and conv staging are no longer the visible
steady bottleneck, and the target forward is graph-captured enough to reach
`~15-17 ms` on steady spec steps. The endpoint speed gate is still missed
because the first post-prefill spec step blocks for multi-second
draft/rejection-sampler runtime across all TP ranks, with occasional smaller
draft/proposer outliers later. No commit was made because the required
speed/canary gate did not pass.

## Iteration 7 Warmup Isolation Attempt

Finding from the fast-but-incorrect full-sampler warmup:

- `SpecDecodeMetadata.make_dummy()` created all-zero target/bonus/logit indices.
  For k=1 this aliases every verifier row onto logit row 0 during warmup. That
  is not representative of real decode, where target rows are
  `[0, 2, 4, ...]`, bonus rows are `[1, 3, 5, ...]`, and logits rows cover the
  full flattened sampled-token layout.
- ReplaySSM warmup/capture left per-slot state dirty. The previous reset path
  only cleared cursor metadata for selected slots and did not clear the
  `d/k/g` replay rings or `conv_pending` contents. A warmup that touches slot 0
  can therefore leave synthetic pending state visible to the first real request.
- Max-batch synthetic proposer warmup with long dummy sequence metadata was not
  safe on this XPU setup: it over-stressed the runtime and later produced
  out-of-resource/device-lost behavior on the first real request.

Implemented isolation changes in vLLM:

- added a full ReplaySSM spec-state clear hook that zeroes replay `d/k/g` rings,
  cursor metadata, pending metadata, and pending conv rows for all slots after
  profiling, graph capture, and isolated warmups;
- replaced all-zero dummy spec metadata with a realistic k=1 flattened layout;
- added a post-capture isolated sampler warmup that uses fresh logits and warms
  the same full sampler/rejection/padded-prep path as the unsafe warmup, then
  clears the Triton sampler scratch cache and ReplaySSM warmup state;
- added an isolated proposer warmup limited to batch size 1 by default, with an
  override knob for broader shapes once the XPU resource behavior is stable.

Lightweight validation:

- `.venv/bin/python -m compileall -q vllm/v1/worker/gpu_model_runner.py
  vllm/model_executor/layers/mamba/gdn_linear_attn.py` passed;
- `git diff --check -- vllm/v1/worker/gpu_model_runner.py
  vllm/model_executor/layers/mamba/gdn_linear_attn.py` passed.

Endpoint validation status:

- reduced warmprobe before the post-capture sampler warmup still ran at only
  `0.1-0.3 tok/s`;
- an attempted timing probe left `xpu-smi dump` stuck in uninterruptible `D`
  state, after which vLLM startup no longer reached first log output even with
  launcher preflight disabled;
- no 96/96 json canary, 96/96 color canary, or speed-gate acceptance is claimed
  for this iteration, and no commit was made.

## Iteration 8 Serving Crash Fix and Stop at Third Layer

Fixed the first real-request crash:

- root cause was host-side worker OOM during the first real request, not a
  Python exception from the GDN layer;
- `/var/log/kern.log` showed `Out of memory: Killed process ... VLLM::Worker_TP`
  for the earlier failing serving run;
- ReplaySSM spec rings are allocated outside the KV tensor pool, so the KV block
  count was too high at `GPU_MEMORY_UTILIZATION=0.95`;
- `vllm/v1/core/kv_cache_utils.py` now accounts for XPU ReplaySSM scratch bytes
  per KV block when `VLLM_XPU_GDN_REPLAYSSM_SPEC=1` and speculative decoding is
  enabled.

Validation of the crash fix:

- `git diff --check -- vllm/v1/core/kv_cache_utils.py` passed;
- `.venv/bin/python -m py_compile vllm/v1/core/kv_cache_utils.py` passed;
- `pre-commit run ruff-check --files vllm/v1/core/kv_cache_utils.py` passed;
- smoke run
  `qwen36-ablation-tp4-mtp-k1-replayssm-serve-smoke-20260620231637` survived
  the first real request and emitted SpecDecoding metrics.

Native stage-conv correctness issue found and fixed:

- full run `qwen36-ablation-tp4-mtp-k1-replayssm-serve-20260620232243` no
  longer crashed, but failed canaries and speed:
  - corrected output throughput: `49.372457560819704 tok/s`;
  - json canary failed on repeat 1;
  - color canary failed on repeat 1;
- disabling graphs still failed, so this was not a PIECEWISE replay issue;
- enabling only `VLLM_XPU_GDN_REPLAYSSM_STAGE_CONV_TORCH_FALLBACK=1` made a
  one-repeat json probe pass, while native recurrent/commit stayed enabled;
- standalone probes showed the native `gdn_replayssm_stage_conv` produced BF16
  one-ULP to two-ULP q/k/v differences from the validated Triton
  `causal_conv1d_update` fallback;
- root cause: Triton rounds each BF16 x BF16 product before adding to the FP32
  accumulator, while the native SYCL stage kernel multiplied after promoting
  both operands to FP32;
- `vllm-xpu-kernels/csrc/xpu/gdn_attn/spec_decode.hpp` now accumulates
  `static_cast<float>(T(x * w))` for the ReplaySSM stage-conv kernel;
- rebuilt with
  `/home/steve/llm-optimizations/scripts/build-vllm-xpu-kernels-xpu-c-only.sh`
  and copied `_xpu_C.abi3.so` into
  `/home/steve/src/vllm-xpu-kernels/vllm_xpu_kernels/`.

Stage-conv parity after the kernel rebuild:

- small BF16 parity cases, including mixed sequence lengths, are bitwise clean:
  q/k/v max diff `0.0`, nonzero count `0`;
- Qwen-shaped TP4 staging parity is bitwise clean:
  q/k/v max diff `0.0`, a/pending max diff `0.0`;
- Qwen-shaped non-contiguous `mixed_qkv` split-view parity is also bitwise
  clean:
  q/k/v max diff `0.0`, pending max diff `0.0`.

Endpoint result after the stage-conv fix:

- smoke run
  `qwen36-ablation-tp4-mtp-k1-replayssm-serve-stagefix-smoke-20260621001227`
  completed startup, PIECEWISE capture, and real traffic without EngineDead;
- the original serving crash is fixed;
- json canary still failed 1/1:
  `{"answer":  + 3":"42,"unit":"widgets"}`;
- color canary still failed 1/1:
  `blue, green, red, yellow`;
- SpecDecoding metrics were emitted during the smoke:
  - json request: accepted `1`, drafted `2`, acceptance `50.0%`;
  - color request: accepted `5`, drafted `8`, acceptance `62.5%`;
- no `UR_RESULT_ERROR_OUT_OF_RESOURCES`, no `UR_RESULT_ERROR_DEVICE_LOST`, and
  no OOM marker appeared in the checked kernel log tail for this run.

Stop reason:

- layer 1 fixed: first-request serving crash from unaccounted ReplaySSM scratch;
- layer 2 fixed: native ReplaySSM stage-conv BF16 product rounding mismatch;
- the remaining canary corruption is now a third distinct serving-path layer,
  likely in ReplaySSM spec state lifecycle/commit/recurrent integration or MTP
  verifier/proposer state alignment rather than in stage-conv arithmetic or
  graph replay.

Remaining issue set:

- correctness: endpoint canaries still fail after stage-conv is bitwise aligned
  with the fallback;
- acceptance: end-to-end acceptance remains far below the earlier
  math-validated 100% expectation;
- speed: full 96/96 gate was not rerun after the smoke failure, and the latest
  measured full run before the stage fix was only `49.37 tok/s`, below the
  `~65 tok/s` lower bound.

No commit was made because the required endpoint gate did not pass.

## Follow-up (2026-06-22): ReplaySSM + XPU graph was fast but not valid

The ReplaySSM correctness path (snapshot/restore on partial-reject and
full-accept, `--mamba-cache-mode align`) passed BOTH canaries but ran fully
**eager** at ~13 tok/s. Two findings explained the gap, but did not produce a
valid `>150 tok/s` result:

1. **Snapshot/restore copies were NOT the bottleneck.** Batching the per-layer
   `state[block_id].clone()` / `.copy_(saved)` loops into single
   `torch._foreach_copy_` calls (new helper `_xpu_batched_restore_snapshots` +
   batched snapshot in `_xpu_snapshot_mamba_running_states_for_spec`,
   `gpu_model_runner.py`) is correctness-neutral but moved throughput only
   13.08 -> 13.26 tok/s (noise). It was later reverted because it did not help
   the endpoint and was not the root cause.
2. **Eager execution was the bottleneck.** The MTP run never captured an XPU
   graph. Enabling it required overriding the launcher default
   `VLLM_XPU_DISABLE_PREFILL_CUDAGRAPH_REPLAY=1` to `=0`, because the
   `align`/ReplaySSM spec-decode batches register as **non-uniform**, and
   `PREFILL_REPLAY_OFF=1` skips every non-uniform PIECEWISE capture
   (`gpu_model_runner.py:12318`). With the flag at 1, all 19 captures were
   skipped (`finished in 1 secs, took 0.00 GiB`), so decode hit an uncaptured
   shape and tried to capture at runtime ->
   `RuntimeError: CUDA graph capturing detected at an inappropriate time`
   (`compilation/cuda_graph.py:1595`). With `=0`, capture actually ran
   (`finished in 14 secs`) and decode replayed the graph.

Smoke result `tp4-mtp-k1-replayssm-iter14-graph-capnonuni` (8+8 canaries,
2 metric repeats):

- json-canary: 8/8, color-canary: 8/8
- corrected throughput: **76.35 tok/s** (was 13.08), decode **13.10 ms/token**
  (was 76.44), inter-token 13.12 ms, iteration_tokens_per_step 1.97
- cleared only the old "within 20% of baseline" floor:
  `93.55 * 0.8 = 74.84` and `76.35 > 74.84`. This is **not** the actual
  spec-decode target; the real target remains `>150 tok/s`, and this smoke
  later failed full correctness gates.

### CORRECTION: the `max_capture=128` config above fails color AT SCALE

The 8+8 smoke passed, but the **full 96/96** run of the `max_cudagraph_capture_size=128`
config FAILED color: `json 96/96`, but `color` produced **1 garbage output ~1 in 30
requests** (e.g. `伪 伪 伪 ...` or a spurious prefix token like `_kategori`/`institution`/`aff`
followed by the correct `blue, green, orange, red`). Throughput held at ~73-76 tok/s.

Isolation runs (all original code, graph on):

- The corruption is **inherent to graph+spec**, not the `_foreach_copy_` change: a
  control run with the original per-tensor clone/copy loops failed identically. The
  `_foreach_copy_` change was therefore **reverted** (it gave ~0 throughput benefit).
- Generic cudagraph knobs did not fix it: `cudagraph_copy_inputs=true` crashes warmup
  (inductor `index out of bounds`); `VLLM_XPU_SYNC_CUDAGRAPH_REPLAY=1` +
  `VLLM_XPU_CUDAGRAPH_STRONG_OUTPUT=1` only reduced severity (garbage -> single prefix
  token) and halved throughput (75 -> 43 tok/s); `VLLM_XPU_ZERO_FRESH_GDN_STATE=1` had
  no effect.
- The corruption is always the **first decode token, right after prefill**. Root cause:
  with `VLLM_XPU_DISABLE_PREFILL_CUDAGRAPH_REPLAY=0` (needed so the non-uniform
  spec-decode shapes are captured instead of skipped), **prefill itself gets captured**
  — and captured prefill on XPU is exactly what the `=1` default exists to prevent.

### PARTIAL: cap capture size so prefill stays eager (fixes garbage, NOT robust)

Set `max_cudagraph_capture_size=4`. Decode-spec batches are tiny (1 seq x 2 tokens =
size 2), so sizes 1/2/4 are still captured (fast decode preserved), but prefill
(30-512 tokens) exceeds 4 and runs **eager** -> no captured prefill. This DID
eliminate the first-token garbage corruption (signature changed away from `伪`/garbage).

But it is **NOT a robust pass**. Initial run `iter19-graph-capsmall` (32 json + 96
color) passed 96/96 color — but that was luck at the lower bug rate. The full lock
`iter19-graph-capsmall-full` (96 json + 96 color), SAME config, **FAILED**:

- json failed at request 82 (wrong field values), color failed at request 22:
  `blue, green, red, yellow` (the **full-accept double-processing** signature, i.e.
  the exact bug `RESTORE_DRAFT_FULL_ACCEPT_GDN_STATE` fixes in eager mode).
- throughput still ~76 tok/s.

So there are **two** graph-vs-eager races:

1. captured-prefill garbage  -> fixed by `max_cudagraph_capture_size=4`;
2. **eager full-accept restore racing the captured decode replay** (~1/50-1/100)
   -> NOT fixed. The restore is an eager `state[block_id].copy_(saved)` between
   captured decode replays; under graph the rollback intermittently fails to take,
   so the next step double-processes the bonus token -> plausible-but-wrong output.

`VLLM_XPU_SYNC_CUDAGRAPH_REPLAY=1` (tried at max=128) only reduced severity and
halved throughput (75 -> 43, below the 74.84 gate), so a global sync is not viable.

### Bottom line / status

- **Eager (no graph)** = the only robustly correct ReplaySSM config:
  `iter10/iter11`, json 96/96 + color 96/96, but **~13 tok/s**. This is a
  correctness reference only, not a performance answer.
- **Graph** reaches **~75 tok/s**, still below the `>150 tok/s` target, and the
  eager spec-decode state ops (snapshot / full-accept restore / commit) race the
  captured decode replay, producing intermittent wrong output. Not shippable
  as-is.
- Proper fix is deeper: make the spec-decode restore/commit graph-compatible
  (e.g. fold the rollback into the captured region, or a targeted low-cost sync
  only around the restore), or make decode-spec batches uniform so they use a
  graph-safe path. Not a config knob.

Repro for the (partial) graph config:

```bash
cd /home/steve/llm-optimizations
VLLM_XPU_GDN_REPLAYSSM_SPEC=1 \
VLLM_XPU_SPEC_DECODE_RESTORE_DRAFT_PARTIAL_REJECT_GDN_STATE=1 \
VLLM_XPU_SPEC_DECODE_RESTORE_DRAFT_FULL_ACCEPT_GDN_STATE=1 \
VLLM_EXTRA_ARGS="--no-async-scheduling --mamba-cache-mode align" \
COMPILATION_CONFIG='{"cudagraph_mode":"PIECEWISE","max_cudagraph_capture_size":4}' \
XPU_GRAPH=1 VLLM_XPU_ENABLE_XPU_GRAPH=1 VLLM_XPU_FORCE_GRAPH_WITH_COMM=1 \
VLLM_XPU_GRAPH_NOOP_COMM_CAPTURE=1 \
VLLM_XPU_DISABLE_PREFILL_CUDAGRAPH_REPLAY=0 \
SERVER_LAUNCHER=/home/steve/llm-optimizations/scripts/launch-qwen36-quark-int8-hybrid-mtp.sh \
FI_TCP_IFACE=eno1 CCL_KVS_IFACE=eno1 GPU_MEMORY_UTILIZATION=0.95 \
JSON_REPEATS=96 COLOR_REPEATS=96 \
bash scripts/run-qwen36-ablation-candidate.sh <label>
```
