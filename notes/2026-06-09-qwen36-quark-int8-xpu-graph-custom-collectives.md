# Qwen3.6 Quark W8A8 INT8 XPU Graph Baseline

Date: 2026-06-10

## Result

Current quality-preserving Qwen3.6 35B-A3B result:

- Model: `nameistoken/Qwen3.6-35B-A3B-Quark-W8A8-INT8`
- Local path: `/mnt/fast-ai/llm-cache/hf/models--nameistoken--Qwen3.6-35B-A3B-Quark-W8A8-INT8/snapshots/cced56592e8c8935f8220836b4baa04dfd389118`
- Hardware: 4x Intel Arc Pro B70 32GB
- Engine: local vLLM XPU TP4 plus local `vllm-xpu-kernels`
- Runtime: Quark W8A8 INT8 weights, BF16 activation/runtime dtype, 32K context
- Candidate: XPU PIECEWISE graph capture plus clone-safe custom-op all-reduce collectives
- Active manual backend: tmux session `qwen36-graph-tp4-customar-clone-32k`, backend `127.0.0.1:18080`, frontdoor `127.0.0.1:8000`

This uses the same model and quantization as the prior slow run. No smaller model, 4-bit path, speculative decoding, expert dropping, context reduction, or output-quality tradeoff was used.

## Performance

Single-request streaming completions, 512 prompt tokens and 512 output tokens, four repeats:

- Mean output tok/s after first chunk: `94.519964`
- Mean end-to-end output tok/s: `93.210510`
- Mean client TTFT: `76.098 ms`
- Mean vLLM TTFT: `74.910 ms`
- Conservative prefill lower bound from TTFT: `6728 tok/s`

Earlier quick chat/non-stream checks on the same backend measured about `95.3 tok/s` after warmup for 256 output tokens.

Concurrency benchmark, 512 prompt tokens and 256 output tokens per request:

| Concurrency | Aggregate output tok/s wall | Aggregate output tok/s after first text | Mean TTFT |
| ---: | ---: | ---: | ---: |
| 1 | `92.32` | `95.08` | `0.080s` |
| 2 | `162.80` | `167.04` | `0.114s` |
| 4 | `303.04` | `310.98` | `0.200s` |
| 8 | `538.09` | `550.64` | `0.344s` |
| 16 | `888.51` | `904.45` | `0.700s` |
| 32 | `1408.86` | `1433.30` | `1.051s` |
| 48 | `1604.00` | `1622.33` | `1.418s` |

The earlier quick chat concurrency probe with shorter prompts measured `~2080 aggregate tok/s` at 48. The reproducible harness above is the baseline to compare future candidates against.

## Quality

`scripts/qwen36-text-quality-suite.py` passed on the frontdoor endpoint:

- exact `OK`: pass
- exact phrase copy: pass
- arithmetic: pass
- compact JSON field semantics: pass
- 16-repeat deterministic hash stability: pass
- 8K-class long-context needle recall: pass, `7617` prompt tokens

One earlier 8-repeat attempt had a single malformed color-list response through the frontdoor. A direct 12-repeat isolation run was stable, and the final 16-repeat quality gate passed. Keep repeat-hash stability in the promotion gate; treat any recurrence as a reliability blocker.

Direct backend chat requests expose Qwen thinking text unless routed through the frontdoor with `enable_thinking=false`. Completion benchmarks are unaffected. Production should keep the frontdoor metadata aligned with this slot so chat quality tests match deployed behavior.

After reverting the rejected fused-kernel candidate and restarting the known-good backend, a restore smoke also passed exact canaries, compact JSON semantics, 4-repeat hash stability, and a 2K-class long-context needle check. Artifact: `data/qwen36-quark-int8-graph32k-restore-smoke-20260609.json`.

## Commands

Quality:

```bash
source /home/steve/.venvs/vllm-xpu/bin/activate
scripts/qwen36-text-quality-suite.py \
  --base-url http://127.0.0.1:8000 \
  --model qwen36-35b-a3b-fp8 \
  --tokenizer /mnt/fast-ai/llm-cache/hf/models--nameistoken--Qwen3.6-35B-A3B-Quark-W8A8-INT8/snapshots/cced56592e8c8935f8220836b4baa04dfd389118 \
  --repeat-runs 16 \
  --long-context-tokens 8192 \
  --output-json data/qwen36-quark-int8-graph32k-quality-20260609.json
```

Restore smoke:

```bash
source /home/steve/.venvs/vllm-xpu/bin/activate
scripts/qwen36-text-quality-suite.py \
  --base-url http://127.0.0.1:8000 \
  --model qwen36-35b-a3b-fp8 \
  --tokenizer /mnt/fast-ai/llm-cache/hf/models--nameistoken--Qwen3.6-35B-A3B-Quark-W8A8-INT8/snapshots/cced56592e8c8935f8220836b4baa04dfd389118 \
  --repeat-runs 4 \
  --long-context-tokens 2048 \
  --output-json data/qwen36-quark-int8-graph32k-restore-smoke-20260609.json
```

Concurrency:

```bash
source /home/steve/.venvs/vllm-xpu/bin/activate
scripts/bench-openai-concurrency.py \
  --base-url http://127.0.0.1:8000 \
  --tokenizer /mnt/fast-ai/llm-cache/hf/models--nameistoken--Qwen3.6-35B-A3B-Quark-W8A8-INT8/snapshots/cced56592e8c8935f8220836b4baa04dfd389118 \
  --prompt-tokens 512 \
  --output-tokens 256 \
  --warmups 1 \
  --concurrency 1 \
  --concurrency 2 \
  --concurrency 4 \
  --concurrency 8 \
  --concurrency 16 \
  --concurrency 32 \
  --concurrency 48 \
  --output-json data/qwen36-quark-int8-graph32k-concurrency-20260609.json
```

Single-request metrics:

```bash
source /home/steve/.venvs/vllm-xpu/bin/activate
scripts/measure-openai-endpoint-metrics.py \
  --base-url http://127.0.0.1:18080 \
  --model qwen36-35b-a3b-fp8 \
  --tokenizer /mnt/fast-ai/llm-cache/hf/models--nameistoken--Qwen3.6-35B-A3B-Quark-W8A8-INT8/snapshots/cced56592e8c8935f8220836b4baa04dfd389118 \
  --prompt-tokens 512 \
  --output-tokens 512 \
  --prompt-kind text \
  --mode stream \
  --repeats 4 \
  --warmup-output-tokens 64 \
  --skip-vram \
  --out data/qwen36-quark-int8-graph32k-single-metrics-20260609.json
```

MoE INT8 kernel-stage microbench:

```bash
source /home/steve/.venvs/vllm-xpu/bin/activate
export PYTHONPATH=/home/steve/src/vllm:/home/steve/src/vllm-xpu-kernels:${PYTHONPATH:-}
scripts/bench-qwen36-int8-moe-kernels.py \
  --rows 1,2,4,8,16,32 \
  --iterations 50 \
  --warmup 10 \
  --output-json data/qwen36-quark-int8-moe-kernels-20260609.json
```

Rejected fused-candidate diagnostic:

```bash
source /home/steve/.venvs/vllm-xpu/bin/activate
export PYTHONPATH=/home/steve/src/vllm:/home/steve/src/vllm-xpu-kernels:${PYTHONPATH:-}
scripts/bench-qwen36-int8-moe-kernels.py \
  --rows 1,2,4,8,16,32 \
  --iterations 50 \
  --warmup 10 \
  --enable-fused-silu-quant \
  --output-json data/qwen36-quark-int8-moe-kernels-fused-siluq-20260609.json
```

Preallocated scratch diagnostic:

```bash
source /home/steve/.venvs/vllm-xpu/bin/activate
export PYTHONPATH=/home/steve/src/vllm:/home/steve/src/vllm-xpu-kernels:${PYTHONPATH:-}
scripts/bench-qwen36-int8-moe-kernels.py \
  --rows 1,2,4,8,16,32 \
  --iterations 50 \
  --warmup 10 \
  --output-json data/qwen36-quark-int8-moe-kernels-prealloc-20260610.json
```

## Artifacts

- Profile: `configs/model-slots/qwen36-35b-a3b-quark-int8-graph32k.env`
- Summary: `data/qwen36-quark-int8-graph32k-customar-20260609.json`
- Quality: `data/qwen36-quark-int8-graph32k-quality-20260609.json`
- Restore smoke: `data/qwen36-quark-int8-graph32k-restore-smoke-20260609.json`
- Concurrency: `data/qwen36-quark-int8-graph32k-concurrency-20260609.json`
- Single-request metrics: `data/qwen36-quark-int8-graph32k-single-metrics-20260609.json`
- MoE INT8 kernel-stage microbench: `data/qwen36-quark-int8-moe-kernels-20260609.json`
- Rejected fused SiLU+quant MoE microbench: `data/qwen36-quark-int8-moe-kernels-fused-siluq-20260609.json`
- Preallocated scratch MoE diagnostic: `data/qwen36-quark-int8-moe-kernels-prealloc-20260610.json`
- vLLM focused patch: `patches/vllm-qwen36-quark-w8a8-int8-xpu-graph-20260609.patch`
- vLLM XPU kernels patch: `patches/vllm-xpu-kernels-qwen36-quark-w8a8-int8-xpu-20260609.patch`
- Rejected fused SiLU+quant quality artifact: `data/qwen36-quark-int8-graph32k-fused-siluq-quality-20260609.json`
- Mixed-workspace runtime smoke: `data/qwen36-quark-int8-mixedws-smoke-20260610.json`
- Mixed-workspace runtime speed: `data/qwen36-quark-int8-mixedws-single-metrics-20260610.json`
- Mixed-workspace graph/allreduce analyzers: `data/qwen36-quark-int8-mixedws-aot-allreduce-boundaries-20260610.json`, `data/qwen36-quark-int8-mixedws-aot-collectives-20260610.json`
- Runtime-candidate source snapshots: `patches/vllm-qwen36-quark-int8-runtime-candidates-20260610.patch`, `patches/vllm-xpu-kernels-qwen36-quark-int8-runtime-candidates-20260610.patch`

## 2026-06-10 Follow-up Screens

### Mixed INT8 MoE Workspace

Candidate:

- vLLM source adds `VLLM_XPU_INT8_MOE_MIXED_WORKSPACE=1`.
- The XPU INT8 MoE backend requests simultaneous BF16 and INT32 scratch from `current_workspace_manager()`.
- `vllm-xpu-kernels` accepts an optional `scratch` dictionary for `xpu_fused_moe`.
- The runtime math is unchanged: same remap, same per-token INT8 quant, same W8A8 grouped GEMMs, same activation, same gather.

Validation:

- Smoke quality passed on the frontdoor endpoint: exact canaries, compact JSON semantics, repeat stability, and 2K-class long-context recall.
- Single-request p512/n512 direct-backend speed measured `93.805644` output tok/s after first chunk, `93.622430` corrected after first chunk, and `92.521667` end-to-end.

Decision:

- Reject for now. It is quality-safe, but it did not beat the promoted `94.519964` after-first and `93.210510` end-to-end baseline.
- Lesson: allocator/scratch reuse helped the isolated MoE microbench, but full-model graph replay is not currently bottlenecked enough on those Python-level temporary allocations to show an endpoint win.

### RMSNorm Plus INT8 Quant Fusion

Candidate:

- vLLM source adds an opt-in `VLLM_XPU_FUSE_RMS_INT8_QUANT=1` pattern around `vllm_ir.rms_norm.default` plus `_xpu_C.per_token_quant_int8_xpu`.
- The replacement uses `_C.rms_norm_dynamic_per_token_quant`.
- The XPU platform gate allows `fuse_norm_quant` only when this env is set.

Direct kernel findings:

- For hidden size 2048, the fused kernel was faster than unfused RMS plus quant in a direct microbench:
  - rows1: `21.75 us` unfused, `12.99 us` fused, `-40.27%`
  - rows4: `19.60 us` unfused, `10.51 us` fused, `-46.40%`
  - rows18: `18.92 us` unfused, `11.90 us` fused, `-37.11%`
  - rows32: `19.78 us` unfused, `12.56 us` fused, `-36.52%`
- The kernel requires BF16 weight. The live Qwen3.6 graph normalizes with a FP32 transformed weight, so direct checks saw small INT8 quant drift:
  - rows1: max q diff `1`, differing q values `137/2048`
  - rows4: max q diff `1`, differing q values `596/8192`
  - rows18: max q diff `1`, differing q values `2693/36864`
  - rows32: max q diff `1`, differing q values `5171/65536`
  - rows128: max q diff `1`, differing q values `20765/262144`

Endpoint findings:

- After adding fake/meta coverage and guarding CUDA-only FP8 patterns on XPU, the endpoint compiled and served with `VLLM_XPU_FUSE_RMS_INT8_QUANT=1`.
- The compiled graph still contained zero `rms_norm_dynamic_per_token_quant` calls and retained the original `vllm_ir.rms_norm.default` plus `per_token_quant_int8_xpu` boundaries.
- Therefore the pattern did not match the actual Qwen3.6 graph and no quality/speed promotion benchmark was run.

Decision:

- Reject/no-op for now. The direct kernel has enough speed to be worth revisiting, but only if the pattern matches the real graph and preserves the FP32-weight normalization semantics closely enough to pass the quality gate.
- The restored promoted baseline is running again in tmux session `qwen36-graph-tp4-customar-clone-32k`.

### Graph Boundary Scan

The old c10d analyzers report zero collectives under the promoted custom-op route. That is expected: the graph no longer contains c10d `all_reduce` calls at those sites.

A direct compiled-graph string scan on the mixed-workspace cache showed the live large boundaries remain:

- about 220 dense `per_token_quant_int8_xpu` assignments
- about 220 dense `int8_gemm_w8a8` assignments
- about 101 `vllm_ir.rms_norm.default` assignments
- about 81 custom `torch.ops.vllm.all_reduce` assignments
- about 40 `torch.ops.vllm.moe_forward_shared` assignments

The next high-probability single-request targets are dense RMS/quant/GEMM boundaries and exact MoE epilogue work, not the old c10d all-reduce path.

## Lessons

- The original `~16.7 tok/s` limit was dominated by missing graph replay around the decode path, not by model quality or quantization.
- PIECEWISE XPU graph capture is the large quality-preserving win: `~92 tok/s`.
- Clone-safe custom collectives add a smaller clean gain: `~95 tok/s`; warning-prone aliasing paths should stay rejected unless exact-output and runtime safety are proven.
- TTFT is already low for 512-token prompts. The next single-request gains are decode-side: W8A8 dense/MoE kernels, activation/quant boundaries, and collective boundaries.
- `xpu-smi dump` can stall tight profiling. Use `--skip-vram` in `measure-openai-endpoint-metrics.py` and sample memory separately with `xpu-smi stats -j`.
- An opt-in fused MoE SiLU plus second-stage INT8 quant candidate improved the isolated activation/quant microbench for decode-shaped rows, but failed the text quality gate. With `VLLM_XPU_FUSED_MOE_FUSE_SILU_QUANT=1`, the arithmetic canary returned `58` instead of `60`; repeat stability and long-context recall still passed, so the issue is numeric drift rather than randomness. Decision: reject and keep the env unset unless a later implementation proves baseline-equivalent outputs.
- The focused Qwen3.6-shaped MoE INT8 microbench derives `hidden_size=2048`, full `moe_intermediate_size=512`, TP4 `inter_size=128`, `num_experts=256`, and `topk=8` from the checkpoint config. In the accepted env, synthetic decode rows 1/2/4/8 measured `298.96/304.89/272.78/283.87 us` total `xpu_fused_moe` time, with manual staged output exactly matching (`max_abs_diff=0.0`). Rows 16/32 measured `371.08/538.66 us` as GEMM started dominating.
- The rejected fused SiLU+quant diagnostic measured faster full MoE totals for rows 1/2/4/8 (`238.91/232.35/229.18/260.70 us`) but produced kernel-level drift vs the accepted staged path (`max_abs_diff` about `0.53-0.75`). This reinforces that the next activation/quant fusion must reproduce the current two-step rounding and scale semantics, not merely approximate them.
- Preallocated BF16/INT32 scratch reuse in the staged diagnostic path was exactly output-equivalent to `xpu_fused_moe` (`max_abs_diff=0.0`) and measured rows 1/2/4/8 at `210.15/206.06/206.46/240.51 us`. In the same run, this removed `15.4/17.2/16.6/8.5%` versus the non-preallocated staged totals; compared with the prior accepted artifact, those rows are `29.7/32.4/24.3/15.3%` lower. Rows 16/32 measured `322.35/489.85 us`.
- Productionizing scratch reuse needs a mixed-workspace interface. vLLM's current modular MoE workspace path exposes only a small set of same-dtype workspaces, but the accepted INT8 MoE path needs BF16 activations, INT32 routing maps, INT8 quantized activations, and FP32 scale buffers.
- The mixed-workspace runtime route implemented that interface and stayed quality-safe, but endpoint speed was slightly worse than the promoted baseline. Do not promote scratch reuse until the full-model benchmark improves, not merely the isolated MoE microbench.
- RMSNorm plus INT8 per-token quant has a real direct-kernel opportunity, but the currently available fused kernel changes the norm-weight dtype semantics for this Qwen graph and the first endpoint pattern did not match. Treat this as a pattern/semantics research item, not a production knob.
- With custom-op all-reduce collectives enabled, c10d call scanners are no longer sufficient. Use compiled-graph op scans and endpoint metrics to decide what still matters.

## Next Targets

Single-request speed remains the priority:

1. Profile per-token decode boundaries after graph replay to separate dense W8A8 GEMM, MoE grouped GEMM, activation/quant, and all-reduce time.
2. Fix or redesign the RMSNorm plus INT8 quant pattern only if it preserves the live FP32-weight norm semantics, then prove it with the text quality suite and a baseline-output comparison.
3. Fuse the MoE activation plus second-stage quant path between MoE GEMM1 and GEMM2 only if the fused path matches the unfused rounding/scaling behavior closely enough to pass the text quality suite and baseline hash comparison.
4. Revisit mixed-dtype scratch/workspace reuse only when it improves endpoint speed, not just isolated MoE timings.
5. Tune small-M dense W8A8 decode GEMM and scratchpad reuse for the M=1 path.
6. Re-test collective variants only with the text quality suite plus baseline hash comparison; do not use non-clone aliasing shortcuts unless PyTorch alias constraints are satisfied.
7. Keep aggregate throughput secondary but tracked with the 1/2/4/8/16/32/48 concurrency harness.
