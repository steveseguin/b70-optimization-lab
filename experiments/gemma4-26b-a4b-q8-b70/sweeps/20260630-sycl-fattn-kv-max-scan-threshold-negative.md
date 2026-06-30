# Gemma 4 26B Q8 B70: FlashAttention KV-max Scan Threshold

Date: 2026-06-30

Status: negative for the current long-prefill lane. Preserve as a diagnostic
patch, but do not disable the existing KV-max mask pre-scan in promoted
recipes.

## Question

After the `DV=512` GQA tile win (`GGML_SYCL_FATTN_DV512_GQA_NCOLS2=8`), test
whether the existing SYCL FlashAttention mask pre-scan is still worth its
overhead for long prefill.

The source patch adds a default-preserving diagnostic knob:

```bash
GGML_SYCL_FATTN_KV_MAX_SCAN_MIN_Q=-1
```

Setting it to `-1` disables the `flash_attn_mask_to_KV_max` scan. With the env
unset, behavior remains the llama.cpp default threshold of `1024`.

Patch artifact:

- `patches/gemma4-26b-a4b-q8-b70/20260630-sycl-fattn-kv-max-scan-threshold.patch`

## Validation

Paired cold long-context diagnostic, one request per lane:

- model: Gemma 4 26B A4B it `UD-Q8_K_XL` target/verifier
- runtime: llama.cpp `c926ad098` plus local Gemma/B70 patches
- hardware: one B70 per lane
- context: `CTX_SIZE=32768`, `FLASH_ATTN=on`
- lane shape: `BATCH_SIZE=2048`, `UBATCH_SIZE=2048`
- suite case: `lc-22000-middle`
- actual prompt tokens: `30400`
- generation: `MAX_TOKENS=96`
- required validity: exact JSON retrieval pass, canary pass, `cached_tokens=0`
- common env: `GGML_SYCL_FATTN_DV512_GQA_NCOLS2=8`

## Result

| Lane | GPU | KV-max scan | Prefill tok/s | Decode tok/s | TTFT s | Valid |
| --- | ---: | --- | ---: | ---: | ---: | --- |
| `20260630Tfattn-kvscan-controlA` | 0 | default on | `955.2365` | `113.4186` | `31.8246` | yes |
| `20260630Tfattn-kvscan-offA` | 1 | disabled | `862.9161` | `113.2116` | `35.2294` | yes |

The output hash matched in both lanes:

```text
a2c9ffd867b906c1f59e57e7b647e91bae0909b04f7f8de3883c6fae77dfdf72
```

Disabling the scan regressed prefill by about `9.7%` on the 30.4K-token case.
Decode was unchanged, as expected.

Aggregate summaries:

- `data/gemma4-long-context-service-gate-20260630Tfattn-kvscan-controlA.json`
- `data/gemma4-long-context-service-gate-20260630Tfattn-kvscan-offA.json`

## Decision

Keep the existing KV-max mask pre-scan enabled for the current GQA8 long-prefill
recipe. The pre-scan cost is more than paid back by skipped attention work on
this Gemma 4 26B long-context shape.

No LocalMaxxing submission: this is a service/prefill diagnostic, not a
fresh-response short-decode headline result.

## Follow-up

Do not spend more time on "disable KV-max scan" for this lane. Better remaining
prompt-processing candidates are:

- microbatch crossover cleanup around `UBATCH_SIZE=2048..2304`;
- SWA-specific tile selection or mask handling;
- prompt-processing ladder validation at 128, 512, 2K, 4K, 8K, 16K, 24K, 32K;
- ensuring any long-prefill setting is guarded by the short realistic decode
  suite before promotion.
