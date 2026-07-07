# 2026-07-07 - Qwen27 Direct Q-Gate Q/K Norm + RoPE Kernel No-Win

## Question

Can we reduce Qwen3Next full-attention overhead by replacing the Python sequence

1. split `q_gate`, `k`, `v` from packed projection output;
2. split `q_gate` into `q` and `gate`;
3. run Gemma/Qwen RMSNorm on `q` and `k`;
4. apply RoPE to `q` and `k`;

with one XPU kernel that reads the strided `q_gate` / `k` views directly and
writes contiguous `q`, `gate`, and `k_out`?

This specifically targeted the 16 full-attention layers in the current
`webhie/Qwen3.6-27B-int4-AutoRound` recipe. The checkpoint is dense
`qwen3_5_text`, not MoE, so this was a target-body micro-optimization rather
than speculation or LM-head work.

## Baseline

Current valid headline remains:

- model: `webhie/Qwen3.6-27B-int4-AutoRound`;
- recipe: ReplaySSM MTP3/cg8, target INT8 LM-head BF16 scales, draft INT4
  LM-head BF16 scales, conservative PyTorch slot-management fallback;
- strict fresh result: `68.23626314761921 tok/s` median tokens 1-100 after
  TTFT, p10 `62.316569643325344`, mean `67.82964696710413`,
  `cached_tokens=0` on every prompt, repeat64 quality passed;
- LocalMaxxing: `cmr9atqb800msqr01u760xh0t`.

## Artifacts

- benchmark script:
  `scripts/bench-qwen27-qgate-qk-rope.py`;
- pre-experiment source snapshots:
  `patches/qwen36-27b-autoround-int4-b70/source-snapshots/vllm-active-before-qgate-qkrope-kernel-20260707T045654Z.patch`;
  `patches/qwen36-27b-autoround-int4-b70/source-snapshots/vllm-xpu-kernels-active-before-qgate-qkrope-kernel-20260707T045654Z.patch`;
- no-win source patches:
  `patches/qwen36-27b-autoround-int4-b70/vllm-qwen27-qgate-direct-qkrope-no-win-20260707.patch`;
  `patches/qwen36-27b-autoround-int4-b70/vllm-xpu-kernels-qwen27-qgate-direct-qkrope-no-win-20260707.patch`;
- microbench data:
  `data/qwen36-27b-autoround-int4-b70-baselines/qwen27-qgate-qkrope-temppack-microbench-20260707T045552Z.json`;
  `data/qwen36-27b-autoround-int4-b70-baselines/qwen27-qgate-direct-qkrope-rawgemma-microbench-20260707T050501Z.json`;
- endpoint strict screen:
  `data/qwen36-27b-autoround-int4-b70-baselines/qwen27-qgate-direct-qkrope-screen-20260707T051020Z-candidate-summary-20260707T051020Z.json`;
  run dir:
  `/mnt/fast-ai/bench-results/qwen36-27b-autoround-int4-b70/candidates/qwen27-qgate-direct-qkrope-screen-20260707T051020Z-20260707T051020Z`.

## Microbench Result

The first attempted route used the existing `_C.fused_qk_norm_rope` op by
temporarily packing `q`, `k`, and `v` into the layout it expects. That lost:
packing/extract overhead made it slower than the native split RMSNorm + rotary
sequence.

The second route added a native op,
`_C.fused_qgate_qk_norm_rope`, that consumes the strided `q_gate` and `k` views
directly and writes contiguous outputs. It used GemmaRMSNorm semantics inside
the kernel (`x * (1 + weight)`) so the endpoint path could pass the raw norm
weights without per-forward `weight + 1` allocation.

Raw-Gemma microbench medians:

| tokens | native rms+rms+rotary | direct fused qgate op | delta | max q/k abs diff |
|---:|---:|---:|---:|---:|
| 1 | `0.112176 ms` | `0.0563755 ms` | `-0.0558005 ms` | `0.015625 / 0.015625` |
| 2 | `0.1132725 ms` | `0.0531 ms` | `-0.0601725 ms` | `0.03125 / 0.0234375` |
| 4 | `0.1135835 ms` | `0.0529195 ms` | `-0.060664 ms` | `0.015625 / 0.03125` |
| 8 | `0.1129575 ms` | `0.0530445 ms` | `-0.059913 ms` | `0.03125 / 0.015625` |
| 16 | `0.1134385 ms` | `0.052854 ms` | `-0.0605845 ms` | `0.03125 / 0.015625` |

Interpretation: the native kernel is a real local microbench win and validates
that avoiding the temporary pack was the right kernel shape. The absolute
saving is still small: roughly `0.06 ms` per full-attention layer, `16` layers,
so only about `~1 ms` per target forward before graph/integration effects.

## Endpoint Strict Screen

Endpoint env was the current best recipe plus:

- `VLLM_XPU_QWEN3NEXT_FUSED_QGATE_QK_ROPE=1`;
- `VLLM_XPU_MROPE_TEXT_ONLY_FASTPATH=1`;
- runtime kernel binary temporarily swapped to the experimental build, with a
  `/tmp` backup and restored after the run.

The server loaded, compiled, graph-captured, and passed the strict fresh
mechanics:

- smoke passed, `cached_tokens=0`;
- fixed realistic suite passed the final gate;
- every prompt was run once, no warmed/history/cache acceleration;
- quality was skipped because this was an endpoint speed screen.

Result:

- median `66.9532727585989 tok/s`;
- p10 `61.10434017039801`;
- mean `67.29662701471533`;
- TTFT median `489.2983204917982 ms`.

This is below the current valid `68.236 tok/s` record and below the current
recipe subtiming support row (`68.296 tok/s`, quality skipped). No quality run
or LocalMaxxing submission was made.

## Decision

Closed as **no-win** for the current endpoint recipe.

Likely reason: the fused section is too small and/or already graph-amortized;
the endpoint path pays new allocations and graph/codegen shape effects for
`q`, `gate`, and `k_out`, so the tiny full-attention section gain does not
translate to the strict response metric. The local kernel idea is sound, but
not enough to move Qwen27 by itself.

## Cleanup

- Active vLLM source was reverted to its pre-experiment state.
- Active `vllm-xpu-kernels` source was reverted for `csrc/ops.h`,
  `csrc/torch_bindings.cpp`, and `csrc/fused_qknorm_rope.cpp`.
- Active `_C.abi3.so` runtime binary was restored from
  `/tmp/_C.abi3.so.pre-qgate-endpoint-20260707T050927Z`.
- Patches and results above are preserved for future reference.

## Follow-Up Guidance

Do not repeat a Python-level Q/K norm/RoPE route for Qwen27 unless it changes
the graph allocation/aliasing story. A future attempt would need one of:

- write into buffers that the following attention op can consume without extra
  allocations or graph guard cost;
- fuse more of the full-attention path than Q/K norm + RoPE alone, e.g. include
  output gate application or attention input staging;
- pursue the larger buckets first: verifier LM-head full-logits waste,
  accepted tokens per verifier step, or deeper target-body kernel reductions.
