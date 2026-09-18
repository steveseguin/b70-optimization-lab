# Comfy-Org's pruned MiniMax-H3 `adaln_t_table`: exact re-parameterisation, or approximation?

Date: 2026-09-17 · CPU-only investigation · script:
`experiments/minimax-h3-b70/scripts/check-adaln-table.py`
venv: `/mnt/fast-ai/venvs/minimax-h3-cpu` (numpy + safetensors + CPU torch; the script needs only numpy)

## Answer

**It is an approximation — a rank-8 truncated SVD of the mean-centred time-embedding
curve — but a very good one: the worst-case error in any modulation parameter is
8.0e-4 (block 0) / 1.2e-3 (block 25) on values spanning ±3.3 / ±7.3, which is
*smaller* than the error the unpruned bf16 checkpoint already makes against the same
float32 reference (4.0e-3 / 7.1e-3).** So in practice it is lossless relative to the
model's own bf16 noise floor, but it is not algebraically exact.

## What the two forms are

Full model (diffusers `MiniMaxH3Transformer3DModel`), per block:

```
sin(t)  = get_timestep_embedding(t, 256, flip_sin_to_cos=True,
                                 downscale_freq_shift=0, max_period=10000)   # t in [0,1], unscaled
temb(t) = linear_2( silu( linear_1( sin(t) ) ) )          # f32; 256 -> 5376 -> 2688
m(t)    = adaln_proj.linear( silu(temb(t)).to(bf16) )     # [96768] = 6 params x 3 modalities x 5376
```

Sources: `src/diffusers/models/transformers/transformer_minimax_h3.py`
(`MiniMaxH3AdaLayerNormModulation.forward` L124-131, `MiniMaxH3Transformer3DModel.forward`
L641-642, `__init__` L515-518, `MINIMAX_H3_MODALITY_NUM = 3` L38) and
`src/diffusers/models/embeddings.py` (`TimestepEmbedding`, `get_timestep_embedding`),
diffusers git main, cloned read-only to `/mnt/fast-ai/build/diffusers-src`.
Checkpoint keys are the diffusers ones: `time_embedder.linear_1/linear_2` (F32),
`transformer_blocks.N.adaln_proj.linear.{weight,bias}` (BF16), `norm_out.linear.*`
(BF16, the `final_layer.adaln_proj` of the Comfy naming).

Pruned model (ComfyUI, `comfy/ldm/minimax/model.py`, `use_adaln_curves` branch):

```
pos = clamp(t,0,1) * 1024;  i0 = floor(pos)
c(t) = lerp(adaln_t_table[i0], adaln_t_table[i0+1], pos - i0)      # [8], f32
m(t) = W8 @ c(t) + b8                                              # AdalnProj(apply_silu=False), f32
```

`MiniMaxH3Model.__init__` registers `adaln_t_table` and, when it is present, passes
`apply_silu=False` and `adaln_dtype=float32` to every `AdalnProj` and drops
`time_embedder` entirely. So the table already holds the *post-silu* curve, in 8
coordinates, and the projection runs in float32 even though `W8` is stored F16.

## The factorisation, identified exactly

With `S = silu(temb(t))` on the grid `t_i = i/1024, i = 0..1024` -> `[1025, 2688]`:

* The 8 columns of `adaln_t_table` are mutually orthogonal, with norms
  `[7.083, 2.094, 0.746, 0.470, 0.0468, 0.0149, 0.00397, 0.00207]`.
* The singular values of the **mean-centred** `S` are
  `[7.0831, 2.0939, 0.74640, 0.46984, 0.046777, 0.014915, 0.0039718, 0.0020656, 2.600e-4, ...]`
  — identical to those norms.
* All 8 principal cosines between `span(adaln_t_table)` and the top-8 left singular
  subspace of the centred `S` are 1.000000 (7 digits). Against the *uncentred* top-8,
  only 7 cosines are 1 and the 8th is 4.8e-5.

So: `adaln_t_table = U_8 @ diag(s_8)` of `S - mean_t(S)`, on the grid `t = i/1024`,
and `W8 ~= f16( W @ V_8 )`, `b8 ~= f16( W @ mean_t(S) + b )`.

The bias confirms it: `b8` is **not** the full bias (`max|b8 - b_full|` = 2.07 for
block 0, 4.86 for block 25, 0.77 for `norm_out`), but
`max|b8 - f32(W @ mean_t(S) + b_full)|` = 4.9e-4 / 9.7e-4 / 4.8e-4, and `b8` equals
`f16(W @ mean_t(S) + b_full)` bit-for-bit on 99.85% / 99.91% / 99.81% of rows.
The form is therefore an **affine** rank-8 fit (rank 8 + a constant), i.e. effectively
rank 9 against the raw modulation matrix.

## Numbers (grid `t = i/1024`, i = 0..1024; float32 reference)

| | block 0 | block 25 | `norm_out` / `final_layer` |
|---|---|---|---|
| shape | 96768 x 2688 | 96768 x 2688 | 10752 x 2688 |
| range of `m_full` | ±3.2667 | ±7.3233 | ±1.5417 |
| **max abs error** | **7.974e-4** | **1.172e-3** | **6.332e-4** |
| rms error | 8.746e-5 | 7.879e-5 | 9.934e-5 |
| max err / peak \|m\| | 2.441e-4 | 1.601e-4 | 4.107e-4 |
| max rel err on outputs > 5% of peak | 1.795e-3 | 9.876e-4 | 3.284e-3 |
| p99 rel err on those outputs | 4.494e-4 | 4.435e-4 | 4.280e-4 |
| **bf16 checkpoint's own max error** | **4.033e-3** | **7.117e-3** | **1.947e-3** |
| bf16 checkpoint's own rms | 1.722e-4 | 1.587e-4 | 1.766e-4 |

Elementwise relative error is not a useful metric on its own: individual modulation
outputs cross zero, so `max` elementwise relative error is ~85 at points where
`m_full` is ~1e-5. The rows above restrict it to outputs above 5% of peak.

### Error histogram (|err|, block 0, 1/13 subsample of 96768 x 1025)

```
log10|err|   count      share
[-12, -11.3)     932    0.01%
[-9.8,  -9.1)    156    0.00%
[-9.1,  -8.3)   2423    0.03%
[-8.3,  -7.6)  13984    0.18%
[-7.6,  -6.8)  79169    1.04%
[-6.8,  -6.1) 414749    5.44%
[-6.1,  -5.4)1505650   19.73%
[-5.4,  -4.6)2404923   31.52%
[-4.6,  -3.9)2259662   29.62%
[-3.9,  -3.1) 948134   12.43%
```
percentiles: p50 1.58e-5, p90 1.58e-4, p99 3.25e-4, p99.9 4.75e-4, p100 7.29e-4.
Block 25: p50 2.40e-5, p99 2.63e-4, p99.9 4.79e-4, p100 1.06e-3.

### Is the modulation matrix numerically rank <= 8?

Singular values of `M = [m(t_0) ... m(t_1024)]` (bias excluded), block 0:
```
3085.07  267.69  68.836  27.441  16.842  3.3606  0.40708  0.075069  0.036351  0.0087652  0.0061292
```
`sv[8]/sv[0] = 1.18e-5`, rank-8 truncation `||M-M8||_F/||M||_F = 1.22e-5`.
Row-mean-centred (the form the pruning actually uses): `sv[8]/sv[0] = 3.28e-5`,
truncation error 4.10e-5 relative, 1.21e-2 absolute Frobenius.
Block 25: 1.49e-5 / 1.54e-5 raw, 2.96e-5 / 3.65e-5 centred.
`norm_out`: 1.05e-5 / 1.06e-5 raw, 1.94e-5 / 2.48e-5 centred.

So the matrix is **not** exactly rank 8 — the 9th singular value is ~1e-5 of the
first, and non-zero — it is numerically rank-8 only to about 1e-5 relative.
The reason it is so close is that `t` is consumed *unscaled in [0,1]*: with
`max_period = 10000` and 128 frequencies, every sinusoid argument is <= 1 rad, so
`sin(t)` is an extremely smooth, nearly-polynomial curve in `t`, and a 2-layer MLP
of it stays smooth. The singular values of `silu(temb)` fall off roughly a decade
per two components.

### How much of the error is F16 rounding of `W8`?

Solving exactly for the least-squares `W` in the *stored* table basis with the
*stored* bias:

| | block 0 | block 25 | `norm_out` |
|---|---|---|---|
| max \|W8 - W_ls\| | 2.846e-3 | 3.723e-3 | 2.613e-3 |
| rms \|W8 - W_ls\| | 1.038e-4 | 9.342e-5 | 1.297e-4 |
| `f16(W_ls) == W8` elementwise | 66.5% | 66.2% | 66.3% |
| max \|W8 - W_ls\| / ulp(W8) | 1276 | 1561 | 500 |
| error from the F16 rounding alone | 3.710e-4 | 3.577e-4 | 2.729e-4 |
| **same table/bias, float32 W8** | **6.773e-4** | **1.099e-3** | **5.398e-4** |

`W8` is *not* simply `f16` of the exact least-squares fit — it is off by up to ~1300
ulp, i.e. it came from a slightly different (almost certainly bf16/f32-mixed) fit of
the same factorisation. Either way, F16 storage of `W8` contributes only ~3.7e-4 of
the ~8e-4 total (block 0) / ~1.2e-3 (block 25): the dominant term is the rank-8
truncation itself, which a float32 `W8` would only reduce from 7.97e-4 to 6.77e-4.

### Off-grid timesteps

The scheduler (`MiniMaxH3Scheduler`, `shift=12.0` video / `3.0` audio) produces
`t = 1 - sigma` at arbitrary real values, not on the 1/1024 grid. ComfyUI **lerps**
between the two neighbouring table rows. Measured on block 0 (bias-free part,
peak |m| 2.13):

* max `|m(t_{i+1}) - m(t_i)|` across the grid: 8.366e-3
* worst-case nearest-grid **snap** error: 4.191e-3
* worst-case **linear-interp** error (what ComfyUI does): **1.192e-5**

The lerp costs essentially nothing (1.2e-5, ~60x below the rank-8 error), but a
nearest-row snap would cost 4.2e-3 — 5x the rank-8 error and comparable to the bf16
noise floor. Any reimplementation must interpolate, not round.

## What it buys

`adaln_proj` weights 50 x 96768 x 2688 BF16 = 26.01 GB -> 50 x 96768 x 8 F16 = 77.4 MB;
`final_layer`/`norm_out` 57.8 MB -> 172 KB; `time_embedder` 63.3 MB (F32) removed;
table 32.8 KB added. Full transformer 66.28 GB -> pruned file 40.23 GB (-26.05 GB),
matching the measured sizes exactly.

## Reproducing

```
/mnt/fast-ai/venvs/minimax-h3-cpu/bin/python \
  experiments/minimax-h3-b70/scripts/check-adaln-table.py \
  --full-dir /mnt/fast-ai/llm-models/minimax-h3/transformer \
  --pruned-dir <dir with the .bin blobs> --blocks 0,25,final
```
The pruned blobs are pulled with HTTP range requests against the safetensors header
(first 8 bytes = header length, then JSON; data offsets are relative to `8 + len`),
from `https://huggingface.co/Comfy-Org/MiniMax-H3/resolve/main/diffusion_models/minimax_h3_fl2va_pruned_bf16.safetensors`
(header 55976 bytes, 532 tensors, no `__metadata__`, no `time_embedder.*`).
The script streams the full BF16 `adaln_proj` weight in 8192-row chunks and never
holds more than ~200 MB.

## Not verified

* Only blocks 0 and 25 plus `norm_out`; the other 48 blocks were not checked
  (the shared table makes the per-block error bound identical — it is set by the
  4.5e-5 relative residual of `silu(temb)` on the table's subspace — but the
  per-block `W8` fit quality was not individually confirmed).
* `W8` is not reproducible bit-exactly from the full weights: the exact least-squares
  fit differs by up to ~1300 ulp, so Comfy's fitting procedure (dtype, solver,
  possibly a weighted or bf16 fit) is inferred, not reconstructed.
* End-to-end sample quality was not measured — only the modulation vectors.
* ComfyUI's `comfy/ldm/minimax/model.py` was read from `raw.githubusercontent.com`
  at `master` on 2026-09-17; no pin/commit was recorded.
