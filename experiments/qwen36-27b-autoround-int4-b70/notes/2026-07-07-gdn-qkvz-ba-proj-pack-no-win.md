# 2026-07-07: GDN qkvz+ba projection packing microbench no-win

## Classification

Diagnostic microbench only. This is not an endpoint benchmark, not a quality
run, and not a LocalMaxxing submission.

## Hypothesis

Qwen27 has 48 GDN / linear-attention layers. Each GDN target-body forward
currently executes separate input projections for:

- `in_proj_qkvz`: `hidden=5120 -> qkvz=16384`;
- `in_proj_ba`: `hidden=5120 -> ba=96`.

Packing `ba` rows into the large `qkvz` projection would increase output width
by only `96 / 16384 = 0.586%`, while deleting one tiny projection call per GDN
layer. This is distinct from the prior
`VLLM_XPU_GDN_REUSE_QKVZ_BA_QUANT` no-win, because that path reused activation
quantization but still performed two GEMMs.

## Artifact

Reusable script:

```text
scripts/bench-qwen27-gdn-proj-pack.py
```

Result:

```text
data/qwen36-27b-autoround-int4-b70-baselines/qwen27-gdn-proj-pack-microbench-20260707T095215Z.json
```

The benchmark uses synthetic AutoRound/INC W4A16 tensors with the same logical
shape and post-load layout as `INCXPULinearMethod`:

- current path: `int4_gemm_w4a16(qkvz)` + `int4_gemm_w4a16(ba)`;
- candidate path: one `int4_gemm_w4a16(qkvzba)` plus output slicing.

## Result

| rows | current two GEMMs | packed one GEMM | saved/layer | projected 48-layer saving |
|---:|---:|---:|---:|---:|
| 1 | `0.0806 ms` | `0.0780 ms` | `0.0026 ms` | `0.127 ms` |
| 2 | `0.0815 ms` | `0.0785 ms` | `0.0029 ms` | `0.141 ms` |
| 4 | `0.0823 ms` | `0.0790 ms` | `0.0034 ms` | `0.162 ms` |
| 8 | `0.0839 ms` | `0.0797 ms` | `0.0042 ms` | `0.202 ms` |

The explorer pre-gate was `>=0.025 ms/layer` (`>1.2 ms` across 48 layers).
Measured rows=4 saving is only `0.0034 ms/layer`, about `7.4x` below the
microbench gate. Against the current step-cost budget, this is also far too
small: reaching `100 tok/s` at current accepted depth needs about
`12.787 ms/step` saved.

## Decision

Close GDN `qkvz`+`ba` projection packing for now. It is likely technically
possible, but the measured one-layer signal is too small to justify loader and
endpoint risk. Do not implement the vLLM packed projection unless a future
trace shows this section has become a larger real endpoint bucket.

Next credible >100 tok/s work should focus on:

1. accepted-depth improvement beyond MTP3, because MTP3 is capped near
   `98.6 tok/s` even with the optimistic branch envelope at current step cost;
2. multi-ms target-body/verifier cost reductions, not sub-0.5ms projection
   cleanup.
