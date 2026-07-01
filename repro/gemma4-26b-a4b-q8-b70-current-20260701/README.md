# Gemma 4 26B A4B Q8 Record Identity Note

This folder captures the current best Gemma 4 26B A4B Q8-target B70 result
identity so the top-level README has a reproducible pointer for the `124.977`
row. The full Gemma 26B harness landed on `main`; this branch may need those
scripts imported before the runner below works from a fresh checkout.

This is not yet a standalone public repro folder. It is a record identity note
plus a wrapper for Steve's lab checkout or a branch where the full Gemma harness
has been imported.

## Result

- Model: `unsloth/gemma-4-26B-A4B-it-GGUF`
- Target/verifier file: `gemma-4-26B-A4B-it-UD-Q8_K_XL.gguf`
- Draft file: `gemma-4-26B-A4B-it-Q4_0-MTP.gguf`
- Hardware: one Intel Arc Pro B70 32 GB per replica
- Engine: llama.cpp SYCL/Level Zero, upstream base `c926ad098` plus local
  Gemma record patch stack
- Context: `32768`
- KV: f16
- Primary metric: median generated-token throughput for tokens 1-100 after TTFT
  on the fixed realistic cold prompt suite
- Best row: `124.97714084813418 tok/s`
- LocalMaxxing: `cmr1u77na01k2ld01kalwzs1e`
- Evidence path on the originating machine:
  `data/gemma4-q8-gpu0-finalpostnorm-reproexact-full512-20260701T084728Z/summary.json`

The key validation rules are: fixed realistic suite, one cold request per
prompt, `cached_tokens=0` on every prompt, no history/cache/ngram reuse, and
Q4_0 MTP draft tokens verified by the Q8 target.

## Main Runtime Identity

```text
LLAMA_SERVER=/home/steve/src/llama.cpp-gemma-record-repro-c926/build-sycl-b70-aot-bmg-g31-q8reorder-vdr2/bin/llama-server
ONEAPI_DEVICE_SELECTOR=level_zero:<gpu>
FLASH_ATTN=on
CTX_SIZE=32768
GGML_SYCL_ENABLE_VMM=1
BATCH_SIZE=1024
UBATCH_SIZE=1024
LLAMA_SYCL_F16_P021_SMALL_NCOLS=1
LLAMA_SPEC_VERIFY_BULK_SAMPLED_IDS=1
LLAMA_GEMMA4_MOE_FUSED_DOWN_WEIGHTED_SUM_REORDER_VDR2=1
LLAMA_GEMMA4_FUSED_FINAL_POST_NORM_RESIDUAL=1
--spec-type draft-mtp
--spec-draft-n-max 3
--spec-draft-n-min 2
--spec-draft-p-min 0.0475
--ctx-checkpoints 0
```

## Run

Use the wrapper in this folder:

```bash
cd /home/steve/llm-optimizations
GPU_INDEX=0 PORT=18421 \
  repro/gemma4-26b-a4b-q8-b70-current-20260701/run-record.sh
```

If this branch does not have the Gemma 26B harness scripts, set `HARNESS_ROOT`
to a checkout that does:

```bash
HARNESS_ROOT=/home/steve/qwen36-results-main \
GPU_INDEX=0 PORT=18421 \
  repro/gemma4-26b-a4b-q8-b70-current-20260701/run-record.sh
```

## Service / Prefill Companion

The short-decode record stays on `UBATCH_SIZE=1024`. For long-context service
prefill, the validated separate patch
`GGML_SYCL_FATTN_DV512_GQA_NCOLS2=8` improved the near-30K prompt case from
`702.605` to `947.589 prompt tok/s`, and broad service lanes saw about
`1039.6-1076.0 prompt tok/s`. Keep that service recipe separate from the
LocalMaxxing short-decode headline.
