# Reproduce Qwen3.8 27B Q4_K_M target-only TP2 on two B70s

This recipe reproduces the 2026-08-15 two-card ASRock Arc Pro B70 result. It
uses Q4_K_M target weights with no MTP, DFlash, draft model, prompt reuse, or
other speculation.

## Promoted result

- Conventional 99-interval median: **`49.717503 tok/s`**
- Conventional p10: `49.122833 tok/s`
- Historical 100-event compatibility median: `50.219700 tok/s`
- Full-output after-TTFT median: `49.734644 tok/s`
- Full-output wall median: `48.802352 tok/s`
- TTFT median: `173.574 ms`
- Quality gate: 12/12 complete output hashes exact against the matched route,
  every `cached_tokens=0`, and both realistic/fresh-response gates passed.
- LocalMaxxing: approved as
  [`cmsy530c70cpwms01bl1sjk6g`](https://www.localmaxxing.com/en/runs/cmsy530c70cpwms01bl1sjk6g)
  on 2026-08-18.

The promoted increment fuses each device-local Q4_K dense gate and up mat-vec
with its SwiGLU consumer. A same-binary p64/n256/r5 A/B measured
`49.460273` off versus `50.271708 tok/s` on (`+1.6406%`); the cold endpoint
gain over the prior promoted route is `+1.7010%`. The result also retains the
previously accepted TP2 recurrent, attention, collective, and launch-fusion
stack transferred to Qwen3.8's unchanged Qwen3.5-family tensor shapes.

## Model and source

- model repository: <https://huggingface.co/ggml-org/Qwen3.8-27B-GGUF>
- revision: `0669b98607d47046c7c2b3f801011d54a08cfccf`
- file: `Qwen3.8-27B-Q4_K_M.gguf`
- bytes: `18,973,870,432`
- SHA-256:
  `31629f53165ab6a7dad8c9847dcfd1fdf55829dac1e6e748f4a68581b0033d34`

Restore the accepted source using
[`patches/qwen36-27b-q8-tp2-asrock-b70/README.md`](../../patches/qwen36-27b-q8-tp2-asrock-b70/README.md).
The required base remains mndodd commit
`4302fb59969a5d8cf9f8e5f55fdd4506d0ed2126`. Then apply the incremental
Q4_K TP2 fusion in
[`patches/qwen38-27b-q4km-tp2-asrock-b70/`](../../patches/qwen38-27b-q4km-tp2-asrock-b70/README.md).
Its decoded patch SHA-256 is
`0a27858525f6a402cf9c92d1b93daee0a80e2ffaef9137bf7bce784a549b58b6`.

Build with Intel oneAPI DPC++/C++ `2026.1.1.20260724` using the Release/BMG-G31
configuration in the linked patch packet. Never overlap an AOT build with a
loaded model on a 15–16 GiB host; retain `-j2` and the 6/8 GiB build scope.

## Run

Start the endpoint:

```bash
cd /path/to/b70-optimization-lab
QWEN38_SOURCE_DIR=/path/to/patched/llama.cpp \
QWEN38_BUILD_DIR=/path/to/patched/llama.cpp/build-sycl-aot-bmg-g31-oneapi-2026.1.1 \
QWEN38_MODEL=/path/to/Qwen3.8-27B-Q4_K_M.gguf \
repro/qwen38-27b-q4km-tp2-asrock-b70/run-server.sh
```

Then run the fixed cold suite from another terminal:

```bash
OUT=/path/to/result.json \
repro/qwen38-27b-q4km-tp2-asrock-b70/bench.sh
```

The reference host maps its two B70s as `level_zero:1,0` and addresses them as
`SYCL0,SYCL1`. Confirm enumeration before changing the selector. The launcher
uses equal TP2, F16 KV, FlashAttention, batch 1024, ubatch 256, one slot, cache
RAM zero, context checkpoints zero, and a bounded 8/10 GiB host-memory scope.

For prefill-heavy service work, Matthew Dodd's current settings compose with
this build and improved a p64 probe by `20.68%`, while reducing decode by
`0.28%`. They are optional and are not the decode record:

```bash
export GGML_SYCL_REORDER_IN_GEMM=1
export GGML_SYCL_FORCE_REORDER=1
QWEN38_BATCH=8192 QWEN38_UBATCH=2048 \
  repro/qwen38-27b-q4km-tp2-asrock-b70/run-server.sh
```

The structured promoted result and exact output oracle are in
[`2026-08-15-q4km-tp2-q4k-glu-summary.json`](../../experiments/qwen38-27b-b70/data/2026-08-15-q4km-tp2-q4k-glu-summary.json).
The prior route remains preserved in
[`2026-08-15-q4km-tp2-target-summary.json`](../../experiments/qwen38-27b-b70/data/2026-08-15-q4km-tp2-target-summary.json).
