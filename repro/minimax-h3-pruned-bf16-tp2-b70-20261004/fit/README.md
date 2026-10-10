> **SUPERSEDED — 2026-10-10.** The denoiser is Comfy-Org's published `minimax_h3_fl2va_pruned_bf16.safetensors`, already present on turin with the recorded SHA-256. The September AdaLN note analyzes that release; it is not a lab fit procedure. The owner approved this source with the chosen model. No fit recovery or re-download is needed; queued intake entries were removed. This directory/plan is retained as history, not current reproduction instructions. See the [corrected guide](../README.md).

# AdaLN fit recovery, 2026-10-10

**Not reproduced bit-exactly. The new numerical attempt is blocked by absent
inputs on `steve-b70s`; its differences and output hashes are null, not zero.**
The [attempt receipt](attempt.json) records the actual preflight. The
[reconstruction script](recover.py) implements candidate arithmetic and compares
tensor bytes, but is **not an exact producer or a replacement target**.
No model weights, fitted coefficients or numerical target outputs are included.

## Independent assembly search added later on October 10

The [recovery plan](../RECOVERY-PLAN.md) records the exact 66.281 GB official
intake, separate approval-pending Comfy intake, CPU budget, unknowns and no-match
policy. `recover.py --assemble` now derives its own fit, streams the BF16 copies
and assembles the exact saved 532-tensor header layout, then records a complete
file hash for each of 72 default variants. It keeps only a match to the pinned
40,225,724,176-byte denoiser and removes candidate scratch. The real search has
**not run**: no model payload was downloaded. Synthetic assembly and source-header
coverage tests are in [test_assemble.py](test_assemble.py); results are in
[recovery-validation.json](recovery-validation.json). The previous attempt and
validation receipts below remain historical evidence for the comparison tool.

## What was recovered

The [Git search receipt](history-search.json) covers all available refs with
`git log -S` for `AdaLN`, `fit`, `table` and `adaln_t_table`, the lane's deleted
files, script history, and September 16–19 changes. The table investigation
first appears in commit `965065e1b33f3147f205eff18e8918e1da1e88b2` as a checker
and a note. No fit producer, solver version, fitting seed or original build
receipt was found in this search. The ConvRot recovery script reconstructs a
different operation and does not create AdaLN coefficients. Lane run receipts
record the fitted file's path and header digest, not fit parameters.

The September analysis identifies this factorization:

1. Use `t = i/1024`, inclusive `i=0..1024`, unscaled. Embed 256 sinusoidal
   coordinates, cosine before sine, period 10000, frequency shift zero.
2. Compute `S = silu(linear_2(silu(linear_1(embed(t)))))` using the official
   F32 timestep network, dimensions 256 → 5376 → 2688.
3. Compute the mean `mu` over the 1025 rows. Factor `S - mu = U diag(s) V^T`.
   Keep eight components: table `T = U[:, :8] * s[:8]`.
4. For each original projection `W, b`, the inferred conversion is
   `W8 ≈ F16(W @ V[:, :8])`, `b8 ≈ F16(W @ mu + b)`.
5. Runtime uses linear interpolation between adjacent F32 table rows. The
   stored F16 projections are widened for the lane's declared arithmetic.

The basis's sign convention, exact MLP arithmetic, accumulation order, solver,
library/device identity and any fitting weights remain unrecorded. The inferred
factorization alone does not determine the stored bytes.

## Inputs and tensor changes

[Discovery receipt](discovery.json) distinguishes checked paths from excluded
directories. Both receipt-named roots are absent:

- `/mnt/fast-ai/llm-models/minimax-h3/transformer`
- `/mnt/fast-ai/llm-models/minimax-h3-comfy/diffusion_models/minimax_h3_fl2va_pruned_bf16.safetensors`

Bounded filename searches of the listed allowed model/cache/archive roots did
not find H3 weights or the old `adaln_t_table.bin` extraction. Neither protected
download directory was searched. No remote host was accessed or weight bytes
downloaded. This is not proof that the two-card host's files are gone.

[Pinned HF metadata](upstream-metadata.json) retains official shard LFS hashes,
the fitted file's LFS hash, and the license content hash. These are upstream
identities, **not local content verification or per-tensor hashes**. The fitted
candidate file SHA-256 is
`a32572fb90b5508b201ec7c2eddcc184b13ddfd3c6f6d2cf06a0b46535d541b4`;
the historical receipt labels this as a header SHA-256, but the runner actually
hashes the first 1 MiB (including payload), not just the JSON header:
`59916d0f1ea260e0d9e0ce7a3cb2ceb4d59ecbb08a9f2e466de009cbc6fe26c0`.

The following is **historical evidence**, not a new local tensor comparison:

| Tensor group | Official | Fitted |
| --- | --- | --- |
| `time_embedder.linear_1.{weight,bias}` | F32 `[5376,256]`, `[5376]` | Removed |
| `time_embedder.linear_2.{weight,bias}` | F32 `[2688,5376]`, `[2688]` | Removed |
| 50 block AdaLN weights | BF16 `[96768,2688]` | F16 `[96768,8]` |
| 50 block AdaLN biases | BF16 `[96768]` | F16 `[96768]`, includes folded mean |
| `norm_out.linear.weight` | BF16 `[10752,2688]` | F16 `[10752,8]` under `final_layer.adaln_proj.linear` |
| `norm_out.linear.bias` | BF16 `[10752]` | F16 `[10752]`, includes folded mean |
| `adaln_t_table` | Absent | F32 `[1025,8]` |

Other weights are reported unchanged under the lane's name mapping, QKV splits
and SwiGLU row reorder. This task could not re-check that claim or any real
tensor hash. Comparison mode scopes its verdict to AdaLN only; even an
AdaLN match would still require verifying the remaining tensors, official
whole-file pins and the complete output serialization.

## Measured discrepancy already retained

The [September note](../../../experiments/minimax-h3-b70/notes/2026-09-17-adaln-table-exactness.md)
compared a float32 least-squares solution in the **stored table and bias basis**:

| Layer | Max absolute coefficient difference | Max error / stored F16 ULP | F16-rounded coefficients equal |
| --- | ---: | ---: | ---: |
| Block 0 | 0.002846 | 1276 | 66.5% |
| Block 25 | 0.003723 | 1561 | 66.2% |
| Output | 0.002613 | 500 | 66.3% |

Thus “roughly 1300 ULP” in the earlier summary understated the table's worst
reported value: **1561 ULP at block 25**. These are historical coefficient
differences, not newly reproduced results, rounded-candidate ULP counts, or
end-to-end output differences. Original per-tensor hashes and raw fit logs were
not retained in Git.

## CPU comparison command when inputs become available

Use an existing permitted copy of each checkpoint; do not use a directory with
active downloads. Install NumPy `2.2.6` in an isolated CPU environment. The tool
does not download anything, import torch, map entire files, open devices, create
services. Comparison mode does not write model files; the new assembly mode
writes only into an explicitly supplied output location. It streams at most 128 MiB per read (1024-row
default), caps address space at 2 GiB, and forces BLAS/OpenMP to two threads.

```bash
nice -n 19 ionice -c 3 env OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 \
  MKL_NUM_THREADS=2 PYTHONDONTWRITEBYTECODE=1 python3 -B \
  repro/minimax-h3-pruned-bf16-tp2-b70-20261004/fit/recover.py \
  --full-dir /allowed/official/transformer \
  --fitted /allowed/minimax_h3_fl2va_pruned_bf16.safetensors \
  --blocks all --receipt /writable/scratch/h3-fit-attempt.json
```

It records SHA-256 of every consumed tensor and candidate output, shapes,
dtypes, exact-byte equality, max absolute difference and error divided by the
stored value's spacing toward positive infinity. Output coefficients are
rounded to their declared storage dtype before comparison. It does not silently
use tolerance as an exactness gate. Exit 2 means missing/error; 1 means inexact;
0 means all requested AdaLN tensors matched under an independent SVD variant
with `--blocks all`, **not** a whole-denoiser certification.

Candidate arms are F32, F64, and BF16-rounded operands/outputs with F32
accumulation; the last is explicitly **not** true BF16 accumulation. Each uses
independent SVD projection, the September stored-bias normal-equation order, or
F64 least squares in the stored table basis. The latter two are diagnostics
that require the fitted target and cannot reconstruct it independently.
SVD signs use each generated column's largest-magnitude coordinate; the
original sign convention is unknown. `--reverse-grid` tests reduction order on
the same inclusive grid. No alternative timestep grid is documented.
None of these arms ran on real H3 inputs here. True BF16 accumulation and other
solver/device variants remain untested, not rejected by evidence.

[Eight synthetic tests](test_recover.py) passed with NumPy 2.2.6, including a
full-shape synthetic MLP through all three solvers, one-ULP detection, signed
zero, chunked BF16 reading, truncation, forbidden symlinks and missing inputs.
They do not qualify any real fit. Run them with the same `nice`/`ionice`/thread
prefix. Test temporary directories are removed automatically.

## Owner option: distribute only the fitted parameters

An alternative is an AdaLN-only supplement: **103 tensors, 87,317,536 raw bytes**
(about 83.27 MiB), including the shared table **and all 51 weight/bias pairs**.
The 32,800-byte table alone cannot recreate the served variant. A future
extractor must bind the source hash, each tensor hash, layout mapping and
assembled denoiser identity before this could close the input gap.

The governing provision is **Section III, opening paragraph**, of the pinned
[MiniMax H3 Community License](https://huggingface.co/MiniMaxAI/MiniMax-H3/blob/42ed227ee7df40d41602854ae760620d6eb651fe/LICENSE),
which permits redistribution conditionally and “solely within the Applicable
Territory”. Section I.11 includes modifications among Model Derivatives;
II supplies the limited grant. III.1 requires the agreement, III.2 modification
notices, and III.4 the prescribed NOTICE. V.2 requires binding recipient terms;
V.4 bars use/distribution outside the territory. I.5 excludes the EU, UK, South
Korea and US; IV.1 adds the revenue-triggered authorization requirement.

My reading is that fitted parameters remain derivative materials, even when
distributed separately. Owner approval of this alternative and a compliant
distribution arrangement (or separate publisher authorization) are still
needed; an unrestricted GitHub weight upload is not established as permissible.
Comfy-Org remains credited as the source of the original fit. No supplement has
been extracted, uploaded or approved in this task.

The package stays draft: exact input reconstruction, historical byte bindings
and original references, runtime source closure/clean build, independent full
50-NFE repeats, portable paths/stop handling, verified release assets and
clean-host replay are still missing.
