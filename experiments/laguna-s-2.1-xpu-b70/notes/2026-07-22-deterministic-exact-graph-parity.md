# Laguna S 2.1 deterministic exact graph parity, 2026-07-22

## Outcome first

- **Not promotable:** the only correctly invoked full graph suite matched the
  canonical eager q=1 teacher **0/13**. All 13 requests were cold with
  `cached_tokens=0`; long-then-next failed both rows and the 863-token rollover
  failed at output token 17. A second full start and DFlash were deliberately
  not run after the mandatory per-layer parity gate failed.
- **First coarse boundary:** layer 0 attention output. On rank 0,
  `1687/3072` BF16 elements differed, with maximum absolute error
  `0.0006103515625`, while embedding, attention norm, and its residual were
  bitwise equal.
- **First narrowed operation:** with bitwise-equal layer-0 qkv input on ranks
  0/1/3, Inductor's native Q/K RMSNorm reduction differed from eager. Rank 0 Q
  norm differed in `428/1536` BF16 elements, maximum absolute error `0.0625`.
  Pinning the eager FP32 reduction fixed Q/K norm, RoPE, and attention-kernel
  parity on those ranks.
- **Subsequent exactness chain:** after pinning Q/K norm, gate softplus became
  first (`6/12`, max `0.0009765625`); after pinning softplus, local attention
  `o_proj` BMM became first (`1/3072`, one BF16 ULP); after pinning that BMM,
  fused residual-add + post-attention RMSNorm became first on ranks 0/1/3
  (`579/3072`, max `0.015625`). Rank 2 still has an earlier qkv INT4 GEMM
  one-ULP difference at element 1210: eager `2.0265579223632812e-06`
  (`0x3608`) versus graph `2.041459083557129e-06` (`0x3609`).
- **Why:** graph capture is not merely replaying eager arithmetic. Inductor
  changes FP32 reduction trees and FP32-to-BF16 materialization boundaries,
  and the captured rank-2 qkv path also produces a one-ULP-different INT4 GEMM
  result. The fixed rank-order TP reduction is downstream of these first
  differences and is not their cause.
- **Speed:** the correctly invoked, pre-final-pins q=1 graph suite measured
  `30.99206181468133 tok/s` median for tokens 1-100 after TTFT (p10
  `30.876286555987782`, mean `30.94521158361871`). This is
  `2.09376339721008 tok/s` (`6.33%`) below the approved exact DFlash record
  `33.08582521189141`. The still-inexact final source was not benchmarked.
  DFlash acceptance was not measured and no LocalMaxxing payload was staged.

## Source and runtime identity

- vLLM experiment branch:
  `experiment/laguna-s-2.1-xpu-bringup-20260721`
- starting vLLM commit: `3b13cebbe5`
- final diagnostic vLLM commit: `6a5bcba272060e4be37a49fa6f40844ab99c8180`
- XPU-kernel branch:
  `experiment/laguna-s-2.1-fwht-20260721`
- XPU-kernel commit: `1b2bbcb0fd4c86baa9d27b58814c920122a6ac6c`
- no native-kernel rebuild was required in this pass
- loaded native hashes:
  - `_xpu_C.abi3.so`:
    `87e24739de971f98a81c1dfe108a2c08033e4f4edaa8e79c5f208adb41ec702c`
  - `_moe_C.abi3.so`:
    `f222d3e2d2a8a331e3c85f12e0d02a17aa7a89147bbbcc8ac2c2a816629a405f`
  - `libgrouped_gemm_xe_2.so`:
    `880ca85cd59cb1f7803765710c879ccc34197dafe813d61a7e853a0d23338ee5`

All model, cache, temporary, parity, and run data stayed below
`/media/steve/CorsairExternal/llm-optimization-artifacts/laguna-s-2.1`.
Nothing was written to `/mnt/fast-ai`.

## QKV shape-guard repair

The exact `ColumnParallelLinear` path formerly conditioned the batched M=1
projection on `_xpu_is_exact_decode_or_verifier_rows(input_.shape[0])`. That
made Dynamo specialize a Python loop/branch to the warm-up width 8 and later
fail a dynamic-shape guard. The exact low-width branch now sends the complete
`M<=8` tensor through `_xpu_batched_m1_linear` once. The custom linear method
retains independent M=1 numerical lanes, so this removes the Python
shape-dependent loop/guard without changing row arithmetic. Repeated builds
captured fixed M=8, fixed M=1, and the dynamic range successfully.

## AOT exactness identity repair

The AOT key and a mandatory adjacent `model.identity.json` now include:

- schema `laguna-exact-aot-v2` and model role;
- `VLLM_XPU_EXACT_SPEC_ATTN`;
- `VLLM_XPU_LAGUNA_BATCHED_EXACT_MOE`;
- `VLLM_XPU_LAGUNA_DETERMINISTIC_GRAPH`;
- remote-zero state;
- parity-probe/return-stage state;
- fixed-rank reduction contract `bf16-rank-0-1-2-3-v1`;
- async scheduling state, also added to `SchedulerConfig.compute_hash()`;
- exact speculative-verifier forward-context state.

Loading refuses a missing or unequal manifest, and the existing source-code
validation remains active. Thus a DFlash `--no-async-scheduling` start cannot
load an async q=1 artifact, and legacy artifacts without an identity manifest
cannot load. The latest diagnostic example is:

`/media/steve/CorsairExternal/llm-optimization-artifacts/laguna-s-2.1/cache/vllm/torch_compile_cache/torch_aot_compile/96bd11edfa9c5deab8bf5b102c0a2d5259f50c14216629efe0bad1eb4661b6e0/rank_0_0/model.identity.json`

An earlier suspected `6deac7fc...` stale Laguna target artifact was in fact a
Qwen DFlash draft artifact. The old key was still under-specified, but that
specific cache directory was not the prior Laguna mismatch source.

## Per-layer method and evidence

The diagnostic is default-off (`VLLM_XPU_LAGUNA_PARITY_PROBE=0`). When enabled,
nonpersistent device buffers record embedding; every decoder layer's attention
norm/residual, attention output, post-attention norm/residual, MoE output, and
layer residual; final norm/residual; and logits. Layer-0 attention also records
qkv, Q/K norm, RoPE, attention-kernel output, raw/softplus gate, gated
attention, local `o_proj`, and reduced `o_proj`. An opaque diagnostic copy is
used so graph replay records live values rather than capture-time aliases.

Key packets:

- original eager packet:
  `runs/graph-parity-eager-185dca1-20260722T2000Z/parity`
- original graph packet and comparison:
  `runs/graph-parity-compiled-185dca1-20260722T2010Z/parity-comparison.json`
- current eager packet:
  `runs/graph-parity-postbarrier-eager-4dad41a-20260723T0200Z/parity`
- Q/K divergence:
  `runs/graph-parity-postbarrier-compiled-4dad41a-20260723T0210Z/parity-comparison.json`
- gate-softplus divergence after Q/K pin:
  `runs/graph-parity-exactqknorm-compiled-260c3ee-20260723T0220Z/parity-comparison.json`
- local-output-BMM divergence after softplus pin:
  `runs/graph-parity-exactsoftplus-compiled-4eef151-20260723T0240Z/parity-comparison.json`
- fused post-attention norm divergence after scoped `o_proj` pin:
  `runs/graph-parity-exactoproj-compiled-6a5bcba-20260723T0300Z/parity-comparison.json`

Paths above are relative to the external Laguna artifact root.

## Correct full gate

The canonical teacher includes this request contract:

```json
{"chat_template_kwargs":{"enable_thinking":false}}
```

Earlier graph diagnostics omitted it and emitted a leading `</think>` token;
those comparisons were invalid test invocations, not evidence about graph
arithmetic. The correct invocation was:

```bash
python scripts/bench-openai-realistic-suite.py \
  --base-url http://127.0.0.1:18080 \
  --model laguna-s-2.1-int4 \
  --suite experiments/laguna-s-2.1-xpu-b70/realistic-suite-v1.json \
  --max-tokens 512 --metric-tokens 100 --seed 0 --timeout 1800 \
  --return-token-ids \
  --request-extra-json '{"chat_template_kwargs":{"enable_thinking":false}}' \
  --out "$RUN_DIR/bench.json"
```

Evidence:

- graph run:
  `/media/steve/CorsairExternal/llm-optimization-artifacts/laguna-s-2.1/runs/target-graph-exactrows-4dad41a-q1-start1-20260723T0115Z/bench.json`
- exact comparison:
  `/media/steve/CorsairExternal/llm-optimization-artifacts/laguna-s-2.1/runs/target-graph-exactrows-4dad41a-q1-start1-20260723T0115Z/exact-vs-canonical.json`
- canonical teacher:
  `/media/steve/CorsairExternal/llm-optimization-artifacts/laguna-s-2.1/runs/bulletproof-q1-canonical-cb616c6-6fc06b0-20260722T142908Z/bench.json`

The candidate passed the realistic freshness gate but not exactness:

| gate | start 1 | start 2 |
|---|---:|---:|
| full prompt identity | 0/13 | not run |
| long-then-next | 0/2 | not run |
| 863-token rollover | 0/1 | not run |
| `cached_tokens=0` | 13/13 | not run |

Start 2 was not run because start 1 and the subsequent one-step layer probe
already failed the mandatory exactness gate. DFlash was not started for the
same reason.

## Preserved attempts and disposition

The experiment commits intentionally preserve the negative-result sequence:

- `185dca125` — default-off layer parity instrumentation
- `5bb53b03c` — narrowed layer-0 attention stages
- `c174a98cc`, `53c31e6ab`, `e8fb7d9dc`, `4dad41ac5` — graph-safe,
  attention-local, low-width rounding-boundary experiments
- `260c3ee40` — opaque exact Q/K RMSNorm reduction
- `4eef1514e` — opaque exact gate softplus
- `6a5bcba27` — scoped exact target-attention `o_proj` BMM

A blanket opaque-BMM attempt was preserved in history but rejected at about
`12.7 tok/s`. Even the less serialized correct-contract graph row was already
slower than the approved eager DFlash record. The final source remains on the
experiment branch only, the parity probe is default-off, no payload exists,
and no graph recipe is promoted.

Validation at the final source:

- `git diff --check`: pass
- `ruff check` on changed vLLM Python files: pass
- `python -m compileall` on changed vLLM Python files: pass
- `pytest -q tests/test_envs.py`: `52 passed`

## Next lever

Stop spending the launch-removal budget on progressively opaque whole-model
graph islands. The next bounded lever is the direct-M8 MoE transaction already
identified in the prior handoff: fuse deterministic remap, gather, W1,
activation, W2, and local reduction while retaining the eager exact target
arithmetic and fixed-rank cross-device sum. It attacks the dominant target
work without depending on Inductor to reproduce every RMSNorm/GEMM rounding
boundary.

Postflight stopped the service, removed the parity trigger, and left all four
B70s free. DeepSeek option-4 branches and `preserve/*` tags were not changed.
