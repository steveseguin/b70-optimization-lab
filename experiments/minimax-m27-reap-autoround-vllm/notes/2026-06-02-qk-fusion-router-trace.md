# 2026-06-02 QK Fusion And Router Trace

Goal: continue REAP MiniMax-M2.7 W4A16 optimization after the restored
quality-clean logits-WS lane settled around the mid-80 output tok/s band.

## Quality Harness Change

Extended `scripts/async-quality-smoke.py` with:

- `--compilation-config-json`, merged recursively into the default compilation
  config.
- `compilation_config` recording in the quality artifact.
- `VLLM_MINIMAX_QK_NORM_XPU_HELPER_FUSION` in selected env capture.

This lets compiler-pass experiments be quality-gated without one-off vLLM
script edits.

Validation:

```bash
python -m py_compile experiments/minimax-m27-reap-autoround-vllm/scripts/async-quality-smoke.py
```

## Q/K Norm Fusion Helper

Settings:

- current conservative REAP logits-WS lane
- `VLLM_MINIMAX_QK_NORM_XPU_HELPER_FUSION=1`
- `pass_config.fuse_minimax_qk_norm=true`
- fresh cache:
  `/mnt/fast-ai/vllm-cache-exp/minimax-m27-reap-qkfusion-helper-20260603T022736Z`

Quality:

- `/mnt/fast-ai/bench-results/minimax-m27-reap-autoround-vllm/quality/async-quality-smoke-qkfusion-helper-logitsws-qk0-20260603T022736Z.json`
- passed, `384` generated tokens, `178` distinct generated token IDs, no
  NUL/control output

Benchmark:

- `/mnt/fast-ai/bench-results/minimax-m27-reap-autoround-vllm/decode-qkfusion-helper/vllm-minimax-m27-autoround-tp4-p512n1536-20260603T023218Z.json`
- `18.29634249600349 s`
- `111.93494002680312` total tok/s
- `83.951205` output tok/s

Decision: reject as a speed path. It is quality-clean but slower than the
restored logits-WS baseline.

## MiniMax Top-8 Router Trace Hook

Added a trace-only llm-scaler patch so the direct MiniMax top-8 sigmoid+bias
helper routes through the existing `submit_kernel` wrapper. With
`LLM_SCALER_MOE_TRACE_KERNELS` unset, behavior is intended to match the previous
queue submission path. With tracing set, the helper now emits:

```text
[llm-scaler][moe-kernel] device=N kernel="minimax m2 top8 sigmoid bias" wait_ms=...
```

Patch record:

- `patches/llm-scaler-minimax-top8-trace-hook-20260602.patch`

Build:

```bash
python setup_moe_int4_only.py build_ext --inplace
```

Import check:

- `custom_esimd_kernels_vllm.moe_int4_ops` loaded from the rebuilt package
- `moe_forward_tiny_cutlass_nmajor_int4_u4_minimax_ws` wrapper present

Quality after rebuild, tracing off:

- `/mnt/fast-ai/bench-results/minimax-m27-reap-autoround-vllm/quality/async-quality-smoke-restored-u4runtime-logitsws-qk0-top8tracepatch-20260603T024215Z.json`
- passed, `384` generated tokens, `179` distinct generated token IDs, no
  NUL/control output

Decode after rebuild, tracing off:

- `/mnt/fast-ai/bench-results/minimax-m27-reap-autoround-vllm/decode-top8tracepatch/vllm-minimax-m27-autoround-tp4-p512n1536-20260603T024341Z.json`
- `18.25435767401359 s`
- `112.1923891584242` total tok/s
- `84.144292` output tok/s

Decision: keep only as diagnostic plumbing. It does not improve no-trace
throughput, but it preserves quality and exposes the router/top-k cost.

## Router Trace Result

Diagnostic run:

- eager, graph off, trace on
- p64/n8, current conservative logits-WS lane
- `/mnt/fast-ai/bench-results/minimax-m27-reap-autoround-vllm/profile/moe-trace-top8-20260603T023751Z/vllm-minimax-m27-autoround-tp4-p64n8-20260603T023751Z.log`

Aggregate kernel waits across 8 decode tokens, 62 layers, 4 devices:

| Kernel | Count | Total Wait ms | Avg Wait ms | Max Wait ms |
| --- | ---: | ---: | ---: | ---: |
| `minimax m2 top8 sigmoid bias` | 1984 | 88.110 | 0.044410 | 0.247114 |
| `moe ws down cutlass int4` | 1984 | 50.453 | 0.025430 | 0.035286 |
| `moe ws up routed cutlass int4` | 1984 | 46.959 | 0.023669 | 0.068839 |

Interpretation: the separate MiniMax top-8 router launch is the largest
measured MoE-side cost in eager tracing. Since each decode token executes this
per layer per rank, removing or fusing this launch is a plausible path to a
meaningful decode-rate improvement. The existing tile and output-side knobs are
not likely to recover 90+ tok/s by themselves.

## Top-8 Register Cleanup

Tried an exact-semantics cleanup in the top-8 kernel:

- `minimax_argmax_and_suppress` now returns only the selected index.
- removed the unused `selected_choice` output and unused `tv[16]` local array.

Patch record:

- `patches/llm-scaler-minimax-top8-register-cleanup-20260602.patch`

Build:

```bash
python setup_moe_int4_only.py build_ext --inplace
```

Repeated eager trace:

- `/mnt/fast-ai/bench-results/minimax-m27-reap-autoround-vllm/profile/moe-trace-top8-cleanup-20260603T025052Z/vllm-minimax-m27-autoround-tp4-p64n8-20260603T025052Z.log`
- p64/n8 trace throughput improved from `66.61265632319932` to
  `75.05051830128576` total tok/s.
- top-8 aggregate wait dropped from `88.110 ms` to `48.278 ms` over `1984`
  calls.

Quality:

- `/mnt/fast-ai/bench-results/minimax-m27-reap-autoround-vllm/quality/async-quality-smoke-top8-register-cleanup-logitsws-qk0-20260603T025247Z.json`
- passed, `384` generated tokens, `179` distinct generated token IDs, no
  NUL/control output

Full decode:

- `/mnt/fast-ai/bench-results/minimax-m27-reap-autoround-vllm/decode-top8-register-cleanup/vllm-minimax-m27-autoround-tp4-p512n1536-20260603T025414Z.json`
- `18.269370577007066 s`
- `112.1001947695731` total tok/s
- `84.075146` output tok/s

Decision: do not promote as a full-decode improvement. The eager trace
improved, but graph replay stayed in the same mid-84 output tok/s band. This
reinforces that removing the router launch, rather than only shaving register
pressure inside it, is likely needed for a sizable production decode gain.

## Next Work

- Prototype a real router/top-k integration path:
  - either fuse top-8 selection with the WS up kernel using a token-level
    synchronized work-group design, or
  - split top-k into a lower-latency exact kernel specialized for
    `NUM_EXPERTS=192`, `TOPK=8`, `n_tokens=1`.
- Keep exact MiniMax routing semantics:
  selection score is `sigmoid(router_logits) + e_score_bias`, routed weight is
  selected `sigmoid(router_logits)` normalized over top-k.
- Quality-gate every router change with async smoke before decode benchmark.
- Do not promote Q/K helper fusion; it is quality-clean but slower.
