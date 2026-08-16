# Reproduce Qwen3.8 27B Q4_K_M target-only TP2 on two B70s

This recipe reproduces the 2026-08-15 two-card ASRock Arc Pro B70 result. It
uses Q4_K_M target weights with no MTP, DFlash, draft model, prompt reuse, or
other speculation.

## Promoted result

- Conventional 99-interval median: **`48.885968 tok/s`**
- Conventional p10: `48.313255 tok/s`
- Historical 100-event compatibility median: `49.379765 tok/s`
- Full-output after-TTFT median: `49.082534 tok/s`
- Full-output wall median: `48.277657 tok/s`
- TTFT median: `169.750 ms`
- Quality gate: 12/12 complete output hashes exact against the matched route,
  every `cached_tokens=0`, and both realistic/fresh-response gates passed.

The optional `GGML_SYCL_MMQ_Q4K_REORDER=1` route was tested across the same 12
prompts and was `0.0535%` slower. It is deliberately unset in the promoted
configuration. The gain comes from transferring the previously accepted TP2,
recurrent, attention, collective, and launch-fusion stack to Qwen3.8's
unchanged Qwen3.5-family tensor shapes.

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
`4302fb59969a5d8cf9f8e5f55fdd4506d0ed2126`. Qwen3.8 has the same 64-layer,
three-GDN-to-one-attention geometry as Qwen3.6, so the exact-shape gates admit
it without source edits.

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

The structured result and exact output oracle are in
[`2026-08-15-q4km-tp2-target-summary.json`](../../experiments/qwen38-27b-b70/data/2026-08-15-q4km-tp2-target-summary.json).
