# Qwen3.6 MoE Sidecar Readiness

## Current Decision

The all-rank layer-family timing points at the W8A8 MoE path, not collectives,
as the next best no-quality-loss optimization target for c1 decode. The next
engineering path stays on a resident/persistent MoE layerlet until replay data
contradicts it.

## Existing Replay Evidence

- File-backed oneDNN layer-9/rank-0 MoE island:
  `data/qwen36-onednn-moe-island-layer9-r1-20260612ay/onednn_moe_island_result.json`.
  GEMM1 mean `34.462620 us`, GEMM2 mean `24.756200 us`.
  `gemm1_vs_xpu_max_abs_diff`, `gemm2_vs_xpu_max_abs_diff`, and
  `onednn_island_vs_xpu_fused_moe_max_abs_diff` were all `0.0`.
- Resident two-GEMM pair:
  `data/qwen36-onednn-moe-island-layer9-r1-resident-pair-rerun-20260612az.json`.
  Pair mean `54.340054 us`, p50 `49.954 us`, min `28.714 us`, with exact raw
  checksums for both GEMM outputs.
- Multi-window oneDNN island:
  `data/qwen36-onednn-moe-island-layer9-r1-multiwindow-20260612bc/multi_window_onednn_moe_island_result.json`.
  `16/16` windows were exact. Aggregate max abs diffs were all `0.0`.
  Mean GEMM1 across windows was `53.810433 us`; mean GEMM2 was `33.440583 us`.
- Offset/active-offset layer-floor replay:
  `data/qwen36-replay-digest-moe-layerfloor-offsetactive-20260613f.json` and
  `data/qwen36-moe-fusion-target-budget-offsetactive-20260613h.md`.
  Current exact `xpu_fused_moe` was `315.291681 us/layer`.
  Exact fused-prologue offset-GEMM was `209.052431 us/layer`.
  Exact fused-prologue active-offset-GEMM was `211.169644 us/layer`.
  The candidate target for >200 tok/s is `189.100588 us/layer`, so the
  current exact lower-bound candidates are useful but not endpoint-ready.

## Rank Skew Check

`data/qwen36-rank-route-forward-overlay-20260613n.json` rejects the simple
route-skew explanation. Route counters were identical across ranks for all 40
layers, while forward-end wait still varied:

| rank | mean forward-end wait ms |
|---:|---:|
| 0 | 4.214303 |
| 1 | 4.470655 |
| 2 | 4.769202 |
| 3 | 4.820472 |

This keeps the focus on implementation overhead, dispatch boundaries, and
possibly rank/device execution variance rather than rank-specific route
distribution.

## Source Readiness Change

Patch artifact:
`patches/vllm-xpu-qwen36-onednn-sidecar-end-offsets-20260613.patch`.

The Python sidecar helper `_make_onednn_grouped_offsets` in
`/home/steve/src/vllm-xpu-kernels/vllm_xpu_kernels/fused_moe_interface.py`
now returns cumulative end offsets, matching the exact oneDNN grouped-memory
runner. Smoke result:
`data/qwen36-onednn-sidecar-offset-helper-smoke-20260613.json`.

This is sidecar-readiness only. The accepted endpoint is unaffected unless the
opt-in oneDNN sidecar probe/execution path is enabled.

## One-GEMM Execute Prototype

Patch artifact:
`patches/vllm-xpu-qwen36-onednn-sidecar-execute-onegemm-20260613.patch`.

This extends the existing sidecar probe with an opt-in
`VLLM_XPU_MOE_ONEDNN_SIDECAR_EXECUTE` mode:

- `0`, `false`, `off`, `dry`: descriptor/USM-wrap probe only.
- `gemm1` or `1`: execute oneDNN grouped GEMM1 into `gemm1_output`.
- `gemm2` or `2`: execute oneDNN grouped GEMM2 into `gemm2_output`.

The default remains no execution. The probe still requires the existing
sidecar env gate, max-call gate, rank/layer filters, and no active stream
capture.

Validation artifact:
`data/qwen36-onednn-sidecar-execute-build-smoke-20260613.json`.

- Targeted C++ build succeeded in
  `/home/steve/src/vllm-xpu-kernels/build/qwen36-sidecar-probe-20260612`.
- The built extension registered the new schema with `int execute_mode`.
- A direct synthetic XPU smoke through standalone `importlib` was blocked by
  oneDNN engine creation: `RuntimeError: could not create an engine` with
  `bad engine kind`. This is the same shared oneDNN engine path used by the
  vLLM process, so the next runtime test should run inside the normal vLLM
  endpoint context, not via standalone import.

Follow-up parity logging patch:
`patches/vllm-xpu-qwen36-onednn-sidecar-parity-log-20260613.patch`.
Validation:
`data/qwen36-onednn-sidecar-parity-log-smoke-20260613.json`.

When execute mode is `gemm1` or `gemm2`, the Python probe now clones the target
scratch tensor before sidecar execution and logs:

- target scratch tensor name,
- pre-execute f32 checksum,
- post-execute f32 checksum,
- `max_abs_diff_f32` between post-execute oneDNN scratch and pre-execute XPU
  scratch.

This adds an intentional diagnostic sync for that single gated call. Promotion
requires `max_abs_diff_f32 == 0.0`.

## Next Tasks

1. Done: run the one-GEMM execute prototype inside a normal vLLM process
   context with `VLLM_XPU_MOE_ONEDNN_SIDECAR_EXECUTE=gemm1`, max calls `1`,
   rank `0`, and `layers.9`.
2. Done: require `parity.max_abs_diff_f32 == 0.0` for GEMM1.
3. Done: repeat for GEMM2 and require `parity.max_abs_diff_f32 == 0.0`.
4. Extend to resident two-GEMM execution with cached descriptors/primitives.
5. Add activation/quant2 and gather/combine parity until the full island
   returns `max_abs_diff=0.0` versus `xpu_fused_moe`.
6. Only then run endpoint A/B. Promotion requires exact canary token IDs,
   four measured repeats after warmup, peak VRAM/power/thermal provenance, and
   the accepted quality gates.

## Success Gate

The non-speculative layerlet needs to beat roughly `189 us/layer`, ideally with
one resident/fused dispatch boundary. If a replay-exact layerlet cannot beat
that budget, shift the next >200 tok/s effort toward exact target-verified
speculation parity.

## Live Endpoint Sidecar GEMM Parity

Date: 2026-06-13.

Summary artifact:
`data/qwen36-onednn-sidecar-execute-live-sycl8-20260613.json`.

Launcher patch artifact:
`patches/qwen36-sidecar-launcher-sycl8-runtime-20260613.patch`.

The first endpoint-side one-GEMM execute attempt used the earlier sidecar build
from `/home/steve/src/vllm-xpu-kernels/build/qwen36-sidecar-probe-20260612`.
That build pulled in oneAPI 2026 and linked `_xpu_C.abi3.so` against
`libsycl.so.9`. In the accepted PyTorch/vLLM runtime lane, the extension could
not infer the XPU device type. When forced toward the oneAPI 2026 runtime, the
import failed with an unresolved `urDeviceWaitExp` symbol from
`LIBUR_LOADER_0.12`.

Runtime lesson: sidecar builds must stay in the PyTorch-compatible SYCL 8 lane.
Do not source global oneAPI 2026 into the accepted vLLM process.

Rebuilt sidecar:

```bash
BUILD_DIR=/home/steve/src/vllm-xpu-kernels/build/qwen36-sidecar-probe-sycl8-20260613 \
INSTALL_PREFIX=/tmp/qwen36-sidecar-probe-sycl8-20260613 \
ONEAPI_VARS=/opt/intel/oneapi/compiler/2025.3/env/vars.sh \
JOBS=4 GDN_KERNELS=ON CLEAN=1 \
scripts/build-vllm-xpu-kernels-xpu-c-only.sh
```

The new `_xpu_C.abi3.so` links against `libsycl.so.8`. With the vLLM launcher
LD path active, import, schema registration, and vLLM XPU platform detection
passed. Plain `ldd` outside that launcher still reports missing oneAPI/PyTorch
runtime libraries, so use the launcher environment for validation.

GEMM1 endpoint-side parity:

- tmux tag: `sidecar-exec-gemm1-20260613`
- JSONL:
  `data/qwen36-onednn-sidecar-execute-gemm1-live-20260613--2043961.jsonl`
- layer: `language_model.model.layers.9.mlp.experts`
- `execute_mode`: `1`
- `execute_ok`: `1`
- `construct_us`: `15`
- `execute_wait_us`: `3244`
- parity target: `gemm1_output`
- `before_checksum_f32`: `-1768229.0`
- `after_checksum_f32`: `-1768229.0`
- `max_abs_diff_f32`: `0.0`

GEMM2 endpoint-side parity:

- tmux tag: `sidecar-exec-gemm2-20260613`
- JSONL:
  `data/qwen36-onednn-sidecar-execute-gemm2-live-20260613--2045166.jsonl`
- layer: `language_model.model.layers.9.mlp.experts`
- `execute_mode`: `2`
- `execute_ok`: `1`
- `construct_us`: `8`
- `execute_wait_us`: `14433`
- parity target: `gemm2_output`
- `before_checksum_f32`: `-8468.5048828125`
- `after_checksum_f32`: `-8468.5048828125`
- `max_abs_diff_f32`: `0.0`

The `elapsed_ms` fields in these one-shot logs include diagnostic clone/sync
work and possibly one-time setup effects. They are not promotion-grade
steady-state layerlet timing.

The accepted endpoint was restored after the sidecar probes:

- tmux: `qwen36-tp4-accepted-restored-after-sidecar-gemm-20260613`
- launch log:
  `/tmp/qwen36-quark-int8-tp4-accepted-restored-after-sidecar-gemm-20260613.log`
- no-thinking text smoke:
  `data/qwen36-quark-int8-tp4-accepted-restored-after-sidecar-gemm-quality-nothink-smoke-20260613.json`
- result: `pass_all=true`, `baseline_match_all=true`

Next engineering gate: implement a resident two-GEMM sidecar path with cached
descriptors/primitives and a parity-only diagnostic mode. Only then should the
activation/quant2 and gather/combine stages be pulled into the same island.

## Cached Two-GEMM Sidecar Diagnostic

Date: 2026-06-13.

Patch artifact:
`patches/vllm-xpu-qwen36-onednn-sidecar-both-cached-20260613.patch`.

Summary artifact:
`data/qwen36-onednn-sidecar-both-cached-live-20260613.json`.

Build:

```bash
BUILD_DIR=/home/steve/src/vllm-xpu-kernels/build/qwen36-sidecar-both-sycl8-20260613 \
INSTALL_PREFIX=/tmp/qwen36-sidecar-both-sycl8-20260613 \
ONEAPI_VARS=/opt/intel/oneapi/compiler/2025.3/env/vars.sh \
JOBS=4 GDN_KERNELS=ON CLEAN=1 \
scripts/build-vllm-xpu-kernels-xpu-c-only.sh
```

Result: build passed. New extension:
`/home/steve/src/vllm-xpu-kernels/build/qwen36-sidecar-both-sycl8-20260613/_xpu_C.abi3.so`,
size `55794984` bytes, linked against `libsycl.so.8`.

Import/schema check passed in overlay
`/tmp/qwen36-vllm-xpu-sidecar-overlay-both-import-20260613`.
The parser maps `both`, `two_gemm`, and `3` to execute mode `3`, and vLLM
still detects `XPUPlatform xpu`.

Implementation:

- Add `execute_mode=3` for a diagnostic two-GEMM sidecar call.
- Cache oneDNN grouped matmul primitive/descriptors by
  `(device, m, k, n, num_experts, dst_dtype, weight_layout)`.
- Submit GEMM1 and GEMM2 through one sidecar call and wait once after GEMM2.
- Expand stats from 24 to 32 fields:
  - `24`: GEMM1 cache hit
  - `25`: GEMM1 construct us
  - `26`: GEMM1 execute/submit us
  - `27`: GEMM2 cache hit
  - `28`: GEMM2 construct us
  - `29`: GEMM2 execute/wait us
  - `30`: both-wall us
  - `31`: cache size
- Python parity now supports multiple targets for `execute_mode=3`.

First live probe:
`data/qwen36-onednn-sidecar-execute-both-cached-live-20260613--2055696.jsonl`.

- `MAX_CALLS=2`
- Both calls passed exact parity for `gemm1_output` and `gemm2_output`.
- Call 1: `num_rows=8192`, `num_moe_inputs=65536`, `both_wall_us=19871`,
  no cache hits, cache size `2`.
- Call 2: `num_rows=48`, `num_moe_inputs=384`, `both_wall_us=1351`,
  no cache hits, cache size `4`.
- This validated the `both` mode, but not cache reuse because the two shapes
  differed.

Repeat live probe:
`data/qwen36-onednn-sidecar-execute-both-cached-repeat-live-20260613--2056910.jsonl`.

- `MAX_CALLS=5`
- All five calls passed exact parity for both GEMM outputs.
- Call 1: `num_rows=8192`, `both_wall_us=21116`, no cache hits.
- Call 2: `num_rows=48`, `both_wall_us=1138`, no cache hits.
- Call 3: `num_rows=8`, `both_wall_us=1088`, no cache hits.
- Call 4: `num_rows=1`, `both_wall_us=309`, no cache hits, cache size `8`.
- Call 5: `num_rows=1`, `both_wall_us=66`, GEMM1 cache hit `1`,
  GEMM2 cache hit `1`, GEMM1 execute `24 us`, GEMM2 execute `29 us`,
  cache size `8`.

Interpretation:

- This is a real correctness step and a useful timing signal for the two-GEMM
  boundary.
- It is not yet a production speed win. The sidecar still runs after the
  accepted `xpu_fused_moe` path and the parity mode clones/synchronizes output
  tensors for diagnostics.
- The useful result is that repeated decode-shape oneDNN grouped GEMM
  primitives can be cached and both GEMMs can complete inside one diagnostic
  boundary with exact scratch parity.

Accepted endpoint restored afterward:

- tmux: `qwen36-tp4-accepted-restored-after-sidecar-both-20260613`
- model endpoint: `qwen36-35b-a3b-fp8`, max model length `32768`
- no-thinking smoke:
  `data/qwen36-quark-int8-tp4-accepted-restored-after-sidecar-both-quality-nothink-smoke-20260613.json`
- result: `pass_all=true`, `baseline_match_all=true`, `repeat_pass=true`

Next gate: move the sidecar boundary earlier so the oneDNN GEMM1 output feeds
activation/quant2 and then cached GEMM2, still under exact parity mode. Only
after that should we include gather/combine and run endpoint A/B.

## GEMM1 Replacement Gate

Date: 2026-06-13.

Artifacts:

- `patches/vllm-xpu-qwen36-onednn-sidecar-replace-gemm1-20260613.patch`
- `data/qwen36-onednn-sidecar-replace-gemm1-live-20260613.json`
- `data/qwen36-onednn-sidecar-replace-gemm1-live-20260613--2059780.jsonl`
- `data/qwen36-onednn-sidecar-replace-gemm1-quality-live-20260613--2060920.jsonl`
- `data/qwen36-quark-int8-tp4-sidecar-replace-gemm1-quality-nothink-smoke-20260613.json`
- `data/qwen36-quark-int8-tp4-sidecar-eager-control-quality-nothink-smoke-20260613.json`
- `data/qwen36-quark-int8-tp4-accepted-restored-after-replace-gemm1-quality-nothink-smoke-20260613.json`

Implementation:

- Added opt-in `VLLM_XPU_MOE_ONEDNN_SIDECAR_REPLACE_GEMM1=1`.
- Replacement is active only with `VLLM_XPU_MOE_ONEDNN_SIDECAR_EXECUTE=gemm1`.
- The hook runs after accepted GEMM1 and before activation/quant2.
- oneDNN writes into the live `gemm1_output` buffer, then the existing
  activation/quant2 and GEMM2 path consumes that buffer.
- The normal post-gather sidecar probe is skipped while replacement mode is
  active, avoiding a second diagnostic sidecar invocation.

Validation:

- `python3 -m py_compile` passed for `fused_moe_interface.py`.
- Short completion probe: 5 live layer-9 rank-0 calls, all exact parity,
  `max_abs_diff_f32=0.0`.
- Repeated decode-shape replacement call reported stats construct `6 us` and
  execute/wait `44 us`.
- No-thinking quality with replacement failed arithmetic: expected `60`,
  observed `58`.
- Crucial control: no-thinking quality on the same sidecar/eager endpoint with
  sidecar probing disabled also failed the same arithmetic case with the same
  observed `58` and the same output hash.
- Accepted graph endpoint restored on `18080` and passed:
  `pass_all=true`, `baseline_match_all=true`, `repeat_pass=true`.

Decision:

- Do not promote this as a speed path yet.
- GEMM1 replacement parity is exact, and the quality failure is not attributed
  to replacement because the eager no-replacement control produces the same
  drift.
- The current sidecar/eager endpoint is therefore not a sufficient quality
  oracle for promotion. The next gate needs graph-compatible tensor parity or a
  replay harness that compares full-island output against accepted-path tensors.

Next:

1. Compare final `gemm2_output` and gathered output after replacement, not just
   `gemm1_output`.
2. Add a replay harness using captured accepted-path inputs so the full island
   can be validated outside the endpoint scheduler/eager mismatch.
3. Once full-island parity is exact, measure without diagnostic clone/sync.

## Live Both-Mode Gathered-Output Parity

Date: 2026-06-13.

Artifacts:

- `patches/vllm-xpu-qwen36-onednn-sidecar-both-gather-parity-20260613.patch`
- `data/qwen36-onednn-sidecar-both-gather-parity-live-20260613.json`
- `data/qwen36-onednn-sidecar-both-gather-parity-live-20260613--2066195.jsonl`
- `data/qwen36-quark-int8-tp4-accepted-restored-after-both-gather-parity-quality-nothink-smoke-20260613.json`

Implementation:

- Extended the live sidecar diagnostic only.
- For `VLLM_XPU_MOE_ONEDNN_SIDECAR_EXECUTE=both`, after oneDNN writes GEMM1
  and GEMM2 scratch outputs, Python gathers the sidecar GEMM2 output into a
  temporary output tensor.
- The diagnostic compares that temporary gathered output against the accepted
  already-gathered output and logs it as `target=gathered_output`.
- The accepted output tensor is not mutated by this extra parity check.

Result:

- Five live layer-9/rank-0 calls were recorded.
- Each call logged three parity targets: `gemm1_output`, `gemm2_output`, and
  `gathered_output`.
- Max abs diff was `0.0` for all three targets across all calls.
- Repeated decode-shape call showed cached oneDNN primitives:
  `gemm1_cache_hit=1`, `gemm2_cache_hit=1`, `gemm1_execute_us=24`,
  `gemm2_execute_us=31`, `both_wall_us=69`, cache size `8`.
- Accepted endpoint restored afterward and passed the no-thinking baseline
  smoke: `pass_all=true`, `baseline_match_all=true`, `repeat_pass=true`.

Decision:

- This closes the live diagnostic parity gap for the sampled full island:
  GEMM1, GEMM2, and gathered output are exact.
- It is still not a speed result because the diagnostic runs after the existing
  accepted MoE path and pays clone/sync/temporary-gather overhead.
- Next promotion gate is a resident replacement island using this same
  three-target parity check before timing.

## Two-GEMM Live Replacement Gate

Date: 2026-06-13.

Artifacts:

- `patches/vllm-xpu-qwen36-onednn-sidecar-replace-both-20260613.patch`
- `data/qwen36-onednn-sidecar-replace-both-live-20260613.json`
- `data/qwen36-onednn-sidecar-replace-both-live-20260613--2070387.jsonl`
- `data/qwen36-quark-int8-tp4-sidecar-replace-both-quality-nothink-smoke-20260613.json`
- `data/qwen36-quark-int8-tp4-accepted-restored-after-replace-both-quality-nothink-smoke-20260613.json`

Implementation:

- Added opt-in `VLLM_XPU_MOE_ONEDNN_SIDECAR_REPLACE_BOTH=1`.
- The Python wrapper calls the sidecar before existing W8A8 GEMM1 and before
  existing W8A8 GEMM2.
- Each replacement call uses an explicit execute-mode override:
  `1` for GEMM1 and `2` for GEMM2, so the launcher can keep
  `VLLM_XPU_MOE_ONEDNN_SIDECAR_EXECUTE=off`.
- The path is fail-closed per GEMM. If the sidecar helper returns `None`
  because the op is unavailable, rank/layer filters do not match, stream
  capture is active, or an exception disables the sidecar, the existing XPU
  W8A8 GEMM runs for that GEMM.
- After the capped log count is reached, `required_execution=True` keeps the
  sidecar executing for matching calls without adding more JSONL rows.
- The normal post-gather diagnostic sidecar probe is skipped while two-GEMM
  replacement is active, avoiding an accidental extra sidecar invocation.

Validation:

- `python3 -m py_compile` passed for
  `/home/steve/src/vllm-xpu-kernels/vllm_xpu_kernels/fused_moe_interface.py`.
- Endpoint launched in eager sidecar mode on `18081` with replacement gated to
  rank `0`, `layers\.9\.`.
- Short completion returned successfully and the endpoint remained healthy.
- JSONL captured `32` replacement records: `16` GEMM1 and `16` GEMM2.
- No sidecar errors or disable messages were found in the server log.
- Final logged decode-shape stats:
  - GEMM1: cache hit `1`, construct `6 us`, execute/wait `47 us`
  - GEMM2: cache hit `1`, construct `5 us`, execute/wait `39 us`
- Median logged wrapper elapsed time was about `0.420 ms` for GEMM1 and
  `0.345 ms` for GEMM2. These include Python/logging/sync effects and are not
  promotion-grade timing.
- Replacement-mode parity fields are expected to be nonzero because the
  diagnostic clones pre-write scratch, then compares it with the sidecar output.
  The exactness proof remains the earlier diagnostic `execute=both` gathered
  parity gate where all sampled targets had `max_abs_diff_f32=0.0`.
- The no-thinking smoke on the sidecar/eager replacement endpoint matched the
  known eager-control weakness: exact OK, copy phrase, JSON, and repeat
  stability passed, but arithmetic returned `58` instead of accepted `60`.
- Accepted graph endpoint was restored on `18080` and passed the same
  no-thinking smoke with `pass_all=true`, `baseline_match_all=true`, and
  `repeat_pass=true`.

Decision:

- Keep the two-GEMM replacement gate as a useful plumbing step.
- Do not promote or benchmark it as a speed win yet.
- The next correctness gate must compare replacement output against a reference
  tensor in the same request, or replay accepted-path captured tensors outside
  the endpoint scheduler. Text quality on the eager sidecar endpoint is not
  enough because that endpoint has a known arithmetic canary mismatch even
  without replacement.

Next:

1. Add replacement-vs-reference parity using separate scratch buffers, not
   pre-write scratch.
2. Compare final gathered output under replacement before any broader rank or
   layer rollout.
3. Once exact, run a narrow timing A/B without diagnostic clone/sync.
4. If timing is promising, broaden layer/rank coverage incrementally and run
   the accepted quality/reliability protocol before any Localmaxxing update.
