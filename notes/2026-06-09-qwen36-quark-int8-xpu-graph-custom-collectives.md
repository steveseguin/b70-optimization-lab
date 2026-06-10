# Qwen3.6 Quark W8A8 INT8 XPU Graph Baseline

Date: 2026-06-09

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

## Artifacts

- Profile: `configs/model-slots/qwen36-35b-a3b-quark-int8-graph32k.env`
- Summary: `data/qwen36-quark-int8-graph32k-customar-20260609.json`
- Quality: `data/qwen36-quark-int8-graph32k-quality-20260609.json`
- Restore smoke: `data/qwen36-quark-int8-graph32k-restore-smoke-20260609.json`
- Concurrency: `data/qwen36-quark-int8-graph32k-concurrency-20260609.json`
- Single-request metrics: `data/qwen36-quark-int8-graph32k-single-metrics-20260609.json`
- vLLM focused patch: `patches/vllm-qwen36-quark-w8a8-int8-xpu-graph-20260609.patch`
- vLLM XPU kernels patch: `patches/vllm-xpu-kernels-qwen36-quark-w8a8-int8-xpu-20260609.patch`
- Rejected fused SiLU+quant quality artifact: `data/qwen36-quark-int8-graph32k-fused-siluq-quality-20260609.json`

## Lessons

- The original `~16.7 tok/s` limit was dominated by missing graph replay around the decode path, not by model quality or quantization.
- PIECEWISE XPU graph capture is the large quality-preserving win: `~92 tok/s`.
- Clone-safe custom collectives add a smaller clean gain: `~95 tok/s`; warning-prone aliasing paths should stay rejected unless exact-output and runtime safety are proven.
- TTFT is already low for 512-token prompts. The next single-request gains are decode-side: W8A8 dense/MoE kernels, activation/quant boundaries, and collective boundaries.
- `xpu-smi dump` can stall tight profiling. Use `--skip-vram` in `measure-openai-endpoint-metrics.py` and sample memory separately with `xpu-smi stats -j`.
- An opt-in fused MoE SiLU plus second-stage INT8 quant candidate improved the isolated activation/quant microbench for decode-shaped rows, but failed the text quality gate. With `VLLM_XPU_FUSED_MOE_FUSE_SILU_QUANT=1`, the arithmetic canary returned `58` instead of `60`; repeat stability and long-context recall still passed, so the issue is numeric drift rather than randomness. Decision: reject and keep the env unset unless a later implementation proves baseline-equivalent outputs.

## Next Targets

Single-request speed remains the priority:

1. Profile per-token decode boundaries after graph replay to separate dense W8A8 GEMM, MoE grouped GEMM, activation/quant, and all-reduce time.
2. Fuse the MoE activation plus second-stage quant path between MoE GEMM1 and GEMM2 only if the fused path matches the unfused rounding/scaling behavior closely enough to pass the text quality suite and baseline hash comparison.
3. Tune small-M dense W8A8 decode GEMM and scratchpad reuse for the M=1 path.
4. Re-test collective variants only with the text quality suite plus baseline hash comparison; do not use non-clone aliasing shortcuts unless PyTorch alias constraints are satisfied.
5. Keep aggregate throughput secondary but tracked with the 1/2/4/8/16/32/48 concurrency harness.
