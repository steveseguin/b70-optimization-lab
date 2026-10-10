# MiniMax-H3 fitted-denoiser recovery plan — 2026-10-10

**CPU and metadata preparation only. No model download or real fit was run.**
The reviewer's 22:20 UTC inventory reports both historical H3 roots absent on
NVMe, Corsair and RAID. This job accepts that inventory; it does not rescan the
model stores. The package remains **draft**, while its owner-approved historical
result remains a scoped observation. The October 10 owner decision accepts the
existing fitted model; it does not make an arbitrary new fit the same model or
approve a new third-party source download.

## Official inputs: exactly what the independent reconstruction consumes

Publisher: [MiniMaxAI/MiniMax-H3 at the pinned revision](https://huggingface.co/MiniMaxAI/MiniMax-H3/tree/42ed227ee7df40d41602854ae760620d6eb651fe/transformer).
Revision: `42ed227ee7df40d41602854ae760620d6eb651fe`.
Only `transformer/` is needed for the denoiser reconstruction: all fourteen
shards, their index, and config. Do not download `transformer_ref/`, the official
text encoder, LoRAs, examples, or the entire repository for this fit.

[Fresh metadata receipt](fit/recovery-metadata.json) records pinned HF API
sizes and LFS SHA-256s. The small config and index were fetched as metadata,
their bytes checked against the API Git-blob SHA-1, and their SHA-256s added to
the [official queued catalog](../../model-intake/h3-recovery-20261010-official.json).
These are upstream identities, not verified local model bytes.

| Official file | Bytes | SHA-256 |
| --- | ---: | --- |
| `transformer/config.json` | 546 | `74c11bff524336576096993cbfcdcdc2ef4fa2fa4409df693bdcbc6c666282ae` |
| `transformer/diffusion_pytorch_model-00001-of-00014.safetensors` | 4,825,958,704 | `2d847200c45c09dd7f973c1b096663068408ef851ee0b3711d059b6dc5dcd028` |
| `transformer/diffusion_pytorch_model-00002-of-00014.safetensors` | 4,702,158,032 | `2c4d362eddd2802180ac9c744849eb9ba8d9c8b984bdf9822cb02ed004b29184` |
| `transformer/diffusion_pytorch_model-00003-of-00014.safetensors` | 4,933,368,192 | `949c5aafbbfa5654da730a6a7fafd75adb164d0857b095a30e8bb6d390887d69` |
| `transformer/diffusion_pytorch_model-00004-of-00014.safetensors` | 4,567,069,608 | `eef7616790105ee839766bb2027203bf2c0d87c6aa038dca84145a8675f5ce28` |
| `transformer/diffusion_pytorch_model-00005-of-00014.safetensors` | 4,702,158,080 | `43fdf42d638e8bc6745f713fae80c93bb301807a1a5ae7249344ce28e202a494` |
| `transformer/diffusion_pytorch_model-00006-of-00014.safetensors` | 4,933,368,232 | `6442510b34d173653f0cce5c964b935395a8f7accf0b9cc0aa31aec59805239d` |
| `transformer/diffusion_pytorch_model-00007-of-00014.safetensors` | 4,567,069,608 | `29f48f535c91dac76496ca821eeb16ca24bc4caf3f0cae8b920a89b1f966da6d` |
| `transformer/diffusion_pytorch_model-00008-of-00014.safetensors` | 4,702,158,080 | `c711b096c764bd60f0b8b6ad49518bfab6d614fb788c725add8741c0674a4cd8` |
| `transformer/diffusion_pytorch_model-00009-of-00014.safetensors` | 4,933,368,232 | `44428defe3976cbb87635ad200b958199e739986697cd29fdf27aeb7294b5944` |
| `transformer/diffusion_pytorch_model-00010-of-00014.safetensors` | 4,567,069,608 | `3d44939c374c9da382e9c6877e1946adf7b84e08c7a881c068f228d6849411c9` |
| `transformer/diffusion_pytorch_model-00011-of-00014.safetensors` | 4,702,158,080 | `224d24430b58127a5577721084e0e704a0e74ec96dd7c35bc6fc0994ebd87c33` |
| `transformer/diffusion_pytorch_model-00012-of-00014.safetensors` | 4,933,368,232 | `48fa2bd8fe134eef565ab2464f1c2589a6657cba0d14283dfc06b532f8961f3c` |
| `transformer/diffusion_pytorch_model-00013-of-00014.safetensors` | 4,567,069,608 | `be5b4b1809f9d546ffd4b3fcf41e5c1e02b819125caa6bc105c109b04c051bd3` |
| `transformer/diffusion_pytorch_model-00014-of-00014.safetensors` | 4,644,161,920 | `8fbd5e6c1fb1df7ce988ca90f3d59e7610e465c7517e4b344eda4a214ba4b97d` |
| `transformer/diffusion_pytorch_model.safetensors.index.json` | 64,488 | `ac30a3b58963f2e735d493475fbb81853a5735ec947619648b3e045acda6783e` |

**Official total: 66,280,569,250 bytes (66.281 GB; 61.729 GiB).**
The 14 weights alone total 66,280,504,216 bytes; config + index add 65,034 bytes.

The [publisher index](fit/official-diffusion_pytorch_model.safetensors.index.json)
maps each of 638 tensors to its exact shard. The
[official header inventory](fit/official-tensor-headers.json) records shapes,
dtypes and offsets, fetched with bounded HTTP ranges ending before tensor data.

- The curve consumes `time_embedder.linear_1.weight` F32 `[5376,256]`,
  `time_embedder.linear_1.bias` F32 `[5376]`,
  `time_embedder.linear_2.weight` F32 `[2688,5376]`, and
  `time_embedder.linear_2.bias` F32 `[2688]`. All four are in shard 1.
- Every `transformer_blocks.N.adaln_proj.linear.weight` (N=0..49,
  BF16 `[96768,2688]`) and `.bias` (BF16 `[96768]`) feeds its own fitted
  projection. These span all fourteen shards, so even a full AdaLN-only fit
  needs every shard. `norm_out.linear.weight` BF16 `[10752,2688]` and
  `.bias` BF16 `[10752]` feed the final projection; both are in shard 1.
- All remaining learned tensors are copied as raw bytes in their original dtype:
  **524 BF16 tensors and eight F32 tensors**, not a blanket BF16 cast.
  `proj_in`, `proj_out`, `audio_proj_in` and `audio_proj_out` each retain their
  F32 weight and bias. The mapping
  reverses the lab loader's `build_remap` in
  [run_h3_t2v.py](../../experiments/minimax-h3-b70/scripts/run_h3_t2v.py):
  `transformer_blocks` → `blocks`, `token_refiner.refiner_blocks` →
  `token_refiner.blocks`, Q/K/V concatenate in that order, and SwiGLU swaps
  `[value;gate]` to `[gate;value]`. Input/output projections and norms are renamed.
  There is no floating-point conversion on these copies, including NaN payloads
  and signed zero. Neither block count nor learned BF16 values are pruned.
- One non-learned exception needs explicit treatment: `rope.inv_freq`, F32
  `[16]`, exists only in the Comfy serialization. The official checkpoint omits
  this nonpersistent buffer. The loader reconstructs
  `1 / (10000 ** (arange(0,32,2,float32)/32))`; the recovery tool uses NumPy F32
  power. Its historical last-bit implementation is unknown and can independently
  prevent a whole-file match. It must never be silently ignored by the hash gate.

## Comfy files and proposed source exception for the owner

[Comfy-Org's pinned source card](https://huggingface.co/Comfy-Org/MiniMax-H3/blob/e5eb578a89295337b8ff433a035929ce0279e0b6/README.md)
explicitly describes a repack. **MiniMaxAI is the model author; Comfy-Org is
not.** Revision `e5eb578a89295337b8ff433a035929ce0279e0b6`:

| File | Bytes | HF LFS SHA-256 |
| --- | ---: | --- |
| `diffusion_models/minimax_h3_fl2va_pruned_bf16.safetensors` | 40,225,724,176 | `a32572fb90b5508b201ec7c2eddcc184b13ddfd3c6f6d2cf06a0b46535d541b4` |
| `text_encoders/qwen3vl_32b_minimax_h3_int8_convrot.safetensors` | 27,141,342,152 | `bc2ced0fbea64757fa9acddccfc0b3f4819d1dcf1da6c124d690d368be283923` |
| `vae/minimax_h3_video_vae_fp16.safetensors` | 5,207,808,496 | `7c1f131492e7eddacaac9069a61b81bdd39de5cc96561e677c5eab1cdce5e522` |
| `vae/minimax_h3_video_vae_int8_convrot.safetensors` | 2,811,065,184 | `52a2c8c73583c86e4f41cdcce3a6ad0ea562987bc0bf3d60a0cef5f5c8e60c0e` |

The denoiser and encoder are the two measured-run inputs (67,367,066,328 bytes).
The FP16/INT8 **video VAE pair is a historical preparation dependency**, used by
[recover-convrot-rotation.py](../../experiments/minimax-h3-b70/scripts/recover-convrot-rotation.py)
to reconstruct the encoder rotation; it is not the measured run's video decoder.
The measured decoder uses the official F32 video VAE and official audio VAE.
All four Comfy files total **75,385,940,008 bytes (75.386 GB / 70.209 GiB)**.
The original input, fit and clean-build evidence gaps remain; the LFS identities
are reconstruction pins, not retrospectively measured full-file run hashes.

Proposed justification text for the owner's decision:

> Approve only these four pinned Comfy-Org files for recovery of the existing
> H3 package. The fitted BF16 denoiser removes about 26 GB of large timestep
> projections by replacing them with a rank-8 AdaLN fit, allowing the historical
> two-card setup. The INT8 ConvRot encoder retains H3's first 50 language layers
> and unnormalized layer-50 output, omits the unused LM head and later layers,
> and retains the vision stack; its quantization and rotation are part of the
> measured target. The two VAE conversion files recover that rotation using
> the lab's retained CPU script. Comfy-Org supplied these conversions, not the
> base model or the lab's loader and scheduling optimizations. The official
> release alone does not supply the exact fitted AdaLN coefficients or this
> encoder quantization, and the original fit producer is unknown. Replacing
> either with a newly fitted or quantized file would be a different target.
> Approval is for pinned acquisition and verification, not for assuming official
> model parity, redistributing derived weights, or changing published timings.

**Approval is pending.** Owner rule 5 requires it before this repack is
re-downloaded. Owner acceptance of the historical target is already satisfied;
this separate source exception has not been inferred from it. The
[Comfy queue](../../model-intake/h3-recovery-20261010-comfy-approval-pending.json)
records `owner_source_approval: pending`. No other Comfy variants are queued.
License conditions remain those linked in the [recipe](README.md#license-and-sources).

## Download plan — queued, not executed

Both catalogs use the existing `b70-model-intake-v1` format and explicit
`--catalog`; they are deliberately outside the default `catalog.json` wave.
Every entry is `status: queued`, with `execution_authorized: false` at catalog
and entry level. Here queued means **prepared, not budget/execution approval**.
The intake command refuses those flags before inspecting or writing a store.
An owner decision must be recorded before enabling the Comfy entries. A later
job may enable the official entries when download and storage writes are allowed.

Destinations, relative to the mount root `/mnt/raid-models`:

```
models/intake-20261010/MiniMaxAI--MiniMax-H3/transformer/...
models/intake-20261010/Comfy-Org--MiniMax-H3/diffusion_models/...
models/intake-20261010/Comfy-Org--MiniMax-H3/text_encoders/...
models/intake-20261010/Comfy-Org--MiniMax-H3/vae/...
```

Read-only planning commands (no download):

```bash
nice -n 19 ionice -c 3 env OMP_NUM_THREADS=2 python3 -B scripts/model-intake.py \
  --catalog model-intake/h3-recovery-20261010-official.json plan --root /mnt/raid-models
nice -n 19 ionice -c 3 env OMP_NUM_THREADS=2 python3 -B scripts/model-intake.py \
  --catalog model-intake/h3-recovery-20261010-comfy-approval-pending.json plan --root /mnt/raid-models
```

After the current 82 GB transfer finishes and a future job authorizes writes,
verify mount identity, writable state, capacity and the `.b70-model-store.json`
marker. If missing, initialize it only then. The RAID is not USB; use the
protocol's `--allow-non-usb` only after the external store has been explicitly
reviewed. Do not bypass a refusal or use `--ordinary-only`. After updating the
authorization flags, the planned operation is:

```bash
# FUTURE AUTHORIZED JOB ONLY; never run these during this preparation job.
nice -n 19 ionice -c 3 env OMP_NUM_THREADS=2 python3 -B scripts/model-intake.py \
  --catalog model-intake/h3-recovery-20261010-official.json download \
  --root /mnt/raid-models --allow-non-usb --all-queued
# Separate operation, only after the written Comfy source exception is accepted:
nice -n 19 ionice -c 3 env OMP_NUM_THREADS=2 python3 -B scripts/model-intake.py \
  --catalog model-intake/h3-recovery-20261010-comfy-approval-pending.json download \
  --root /mnt/raid-models --allow-non-usb --all-queued
```

The existing protocol resumes `.part`, checks size and SHA before rename,
then checks direct and ordinary reads and writes `.b70-manifests/` receipts
plus adjacent `.intake.json` identities. This change fixes `.part` verification
for filenames with subdirectories; a synthetic no-network regression test covers
it. After successful verification, retain a `DOWNLOAD-MANIFEST.txt` and seal
weights read-only, as required by the publication standard. No marker, model,
cache, download receipt or other file was written on RAID or Corsair in this job.

This is a fit-recovery queue, not all runnable pipeline inputs. The official
VAEs, tokenizer/processor, scheduler and other config files remain enumerated in
[model-manifest.json](model-manifest.json); runtime restoration is a separate
future intake. Do not silently add the official encoder or reference transformer.

## Reconstruction, variants and exact serialization

[recover.py](fit/recover.py) retains its comparison mode and adds `--assemble`.
It validates the full SHA-256 and size of all fourteen official shards before
fitting. It requires the official tensor inventory, and uses the exact saved
[header bytes](fit/historical-layout.header) for names, dtype, shape, offsets,
ordering, JSON spacing and padding. The header contains **no tensor data**:
55,976 JSON/padding bytes plus the eight-byte length. Header-only SHA-256 is
`d55386f89bed7f9719ae315b4d70d104b9000e7a839d7702c82a97c1835324e6`;
header-with-prefix SHA-256 is
`c426b8dddb8745c52e0e5f511eaf6cba2d8903a3818c3cee448516d968a7b710`.
The historical `denoiser_header_sha256=59916d0f...` hashes the first **1 MiB**
(`file_digest(..., limit=1 << 20)`), including payload; it is not a JSON-header
hash. This job did not fetch that payload or verify that 1 MiB digest.

For `t=i/1024` in **[0,1]**, 1025 inclusive rows, cosine before sine, 256
coordinates and period 10000, compute `S=silu(linear2(silu(linear1(embed(t)))))`.
Mean-center S, take rank-8 SVD, emit F32 `T=U8*singular8`, and fold the mean
and basis into each projection, storing weights/biases as F16. Runtime continues
to linearly interpolate T; the recovery program does not change runtime behavior.

The automatic default search has **72 explicitly recorded variants**:

- Arithmetic: F32 accumulation; BF16 input/output rounding with F32 accumulation;
  and explicitly emulated BF16 accumulation rounded after every K term. The last
  is a software hypothesis, not a claim to reproduce any unspecified hardware
  kernel. F64 is an optional extra screening precision.
- Grid: `arange/1024` and `linspace(0,1,1025)`; these are equal binary fractions,
  retained as distinct method receipts, not independent evidence.
- Reduction order: ascending and descending timestep traversal, restoring table
  rows to ascending order before serialization.
- Projection solver/order: direct `W@V8`; `(M@T)@inv(T.T@T)`; and
  `M@(T@inv(T.T@T))`, with `M=W@S.T+b-f16(W@mean+b)`.
  Unlike the old diagnostic, all use independently generated tables/biases.
- Basis signs: native LAPACK signs and largest-coordinate-positive signs.
  All use rank 8, table size 1025, and the only documented timestep range [0,1].
  No evidence supports a 0..1000 range, alternative table size, weighted grid,
  solver library, seed or complete historical sign convention; those remain
  unknown rather than invented historical settings.

Unchanged BF16 and F32 tensors are streamed once into a disk-backed candidate.
Every arm fills all fitted slots and the derived RoPE slot; then the **complete
40,225,724,176-byte file** is hashed. The receipt is updated after every arm,
including failures (null hash plus error, never a match). Every completed arm
gets its resulting SHA-256 even after a prior match. The tool retains an output
only on exact `a32572fb90b5508b201ec7c2eddcc184b13ddfd3c6f6d2cf06a0b46535d541b4`
equality and rehashes the retained copy. It never uses the existing fitted file
as input to this independent reconstruction. Temporary candidates are removed
on completion or Python exception; existing output files are never overwritten.

Future CPU invocation after input acquisition (output parent must already exist):

```bash
nice -n 19 ionice -c 3 env OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 MKL_NUM_THREADS=2 \
  python3 -B repro/minimax-h3-pruned-bf16-tp2-b70-20261004/fit/recover.py \
  --assemble \
  --full-dir /mnt/raid-models/models/intake-20261010/MiniMaxAI--MiniMax-H3/transformer \
  --output /approved/recovery/minimax_h3_fl2va_pruned_bf16.safetensors \
  --receipt /approved/recovery/fit-search.json
```

No NumPy/BLAS version can be presented as the original producer. Current
synthetic tests used NumPy 2.5.3. The CLI forces two BLAS/OpenMP threads,
sets a 2 GiB address-space limit, reads bounded row slices (128 MiB maximum),
and hashes in 4 MiB blocks; it never mmaps a model or imports a GPU runtime.
Default chunks are 1024 rows. Memory exhaustion fails closed with an error
receipt. Large BF16 accumulator matrices are evaluated as ordered outer products;
that is intentionally slow and bounded, and its wall time is not yet measured.

## Disk and time budget (planning estimates, not benchmarks)

`df -B1 /mnt/raid-models` during preparation reported **5,219,748,356,096 bytes
free** (about 5.22 TB). This is a snapshot, not a reservation. Recheck after the
shared transfer and before any future writes.

- Official fit inputs: 66.281 GB / 61.729 GiB.
- Optional approved Comfy recovery set: 75.386 GB / 70.209 GiB.
- Both input sets: 141.667 GB. One candidate: 40.226 GB; preserving one match
  while continuing the search needs another 40.226 GB. Reserve **at least
  330 GB free** for those files plus the protocol's 100 GiB free-space floor.
  The future runtime VAEs and environment need additional space.
- A `.part` becomes its final filename by rename; do not budget a second full
  copy for that rename. The candidate and retained match are separate copies.
- At an assumed sustained 100 Mbit/s, official download alone takes about
  **88.4 minutes**; at 1 Gbit/s, **8.8 minutes**. Both sets take **188.9 / 18.9
  minutes** respectively, excluding verification and shared-link contention.
  These are byte-count calculations, not measured link speeds or an ETA.
- Hashing the 72 candidate files alone reads **2.896 TB**: about 8.0 hours at
  100 MB/s or 4.0 hours at 200 MB/s. Each arm also rereads about 26 GB of AdaLN
  source data; allow roughly **4.9 TB total search I/O**, plus initial source
  verification/copy and retained-output verification. Rough I/O-only bounds are
  **14 hours at 100 MB/s / 7 hours at 200 MB/s**. CPU SVD, mixed arithmetic and
  especially BF16 accumulator emulation add unmeasured time, potentially days.
  There is no honest measured end-to-end recovery ETA yet. Low I/O priority and
  two CPU threads remain in force; do not increase them to meet an estimate.

## If no variant matches

The September notes identify the affine rank-8 form, **not a fully specified
byte producer**. In particular the stored fit's coefficient differences already
showed that naive least squares is not exact. Accumulation, solver/version,
fit weighting, signs and RoPE serialization can all matter. Exhausting this
finite search does not prove reconstruction impossible; it proves only that
none of the recorded candidates has the required hash.

If no arm matches, **no candidate is installed, timings are not inherited,
and the package stays draft**. With a separately approved acquisition of the
historical Comfy files, their exact hashes can restore the selected target,
while the independent producer remains unrecovered. Alternatively the owner may
choose a **new fitted denoiser version**, with a new full-file hash, explicit
fit method, new quality decision, fresh deterministic references and new matched
performance measurements. It must not replace or rename the old target silently.
A file-hash match alone also does not close the other missing historical receipts,
clean-build, fresh full-suite and publication gates in the current recipe.

## CPU validation

Synthetic assembly uses a fixed independently serialized fixture SHA-256
`d25e2dee3db4f85047c8721f2895d636ed3643fde776fdb044ec06c58dc9ad0f`,
including BF16 NaN payload and signed-zero bytes, tested at multiple chunk sizes.
Tests cover QKV concatenation, SwiGLU order, all-arm hash reporting, mismatches,
partial fit errors, output refusal, malformed layouts, finite independently
fitted tables, repeated fit bytes and real BF16-accumulator rounding semantics.
Intake tests cover nested `.part` verification and refusal of the pending queues.
See [validation receipt](fit/recovery-validation.json). None is a real H3
reconstruction or a quality/performance result. All test scratch is removed.
