# Gemma 4 26B Q8 B70: SYCL FlashAttention KV-min Left-Bound Experiment

Date: 2026-07-01

Status: partial long-prefill win, **not promoted**. Preserve the patch and
results, but keep the active source and promoted recipes on the non-KV-min
stack because the fixed short-decode guard showed a repeatable regression risk.

## Question

The current SYCL FlashAttention path already scans the mask to compute a
per-sequence `KV_max` right bound. On Gemma 4 long-context prompts with sliding
window attention, the left side of the attention window is also masked out, so
old KV tiles can be all `-inf` and still get computed. This experiment tested a
mask-derived `KV_min` left bound so the tile loop can start later and skip old
masked KV tiles.

The source patch was default-off through:

```bash
GGML_SYCL_FATTN_KV_MIN_SCAN=1
```

Later screens also tried:

```bash
GGML_SYCL_FATTN_KV_MIN_SCAN_MIN_Q=1024
GGML_SYCL_FATTN_KV_MIN_SCAN_MIN_Q=2048
```

Patch artifact:

- `patches/gemma4-26b-a4b-q8-b70/20260701-sycl-fattn-kv-min-left-bound-experiment.patch`
- sha256:
  `40f75268a9775a6831bf7428c04788cf80c14d7f1288af846ef21458aae3c763`
- lines: `210`

Caveat: the patch file is a source-worktree diff from the current Gemma/B70
stack, not a clean upstream-only patch. It includes context from the existing
`GGML_SYCL_FATTN_KV_MAX_SCAN_MIN_Q` and
`GGML_SYCL_FATTN_DV512_GQA_NCOLS2` service patches. The active source was
reverted after archiving this experiment.

## Common Validation Identity

- model: Gemma 4 26B A4B IT `UD-Q8_K_XL` target/verifier
- runtime: llama.cpp `c926ad098` plus local Gemma/B70 patch stack
- hardware: one B70 per lane, paired control/candidate lanes
- context: `CTX_SIZE=32768`, `FLASH_ATTN=on`, `GGML_SYCL_ENABLE_VMM=1`
- service shape: `BATCH_SIZE=2048`, `UBATCH_SIZE=1024`,
  `LLAMA_PREFILL_UBATCH_SIZE=2048`
- common service env: `GGML_SYCL_FATTN_DV512_GQA_NCOLS2=8`
- long-context gate: deterministic long-context JSON retrieval suite, one cold
  request per case/lane, `cached_tokens=0`, exact fields pass, canary pass
- short guard: fixed realistic cold suite, `MAX_TOKENS=512`,
  `cached_tokens=0`, canary pass

No LocalMaxxing submission was made. These are service/prefill diagnostics and
the patch did not satisfy the "no short decode regression" rule.

## Long-Context Results

### Single near-32K screen

Case: `lc-22000-middle`, `30400` actual prompt tokens, two lanes per group.

| Run | Env | Prefill tok/s avg | Decode tok/s avg | Gate |
| --- | --- | ---: | ---: | --- |
| `20260701Tkvmin-control-screen2` | control | `961.277846` | `113.673561` | pass |
| `20260701Tkvmin-on-screen2` | `KV_MIN_SCAN=1` | `1010.579229` | `113.246670` | pass |

Readout: `+5.13%` prefill, decode essentially flat, exact/cached0/canary
clean.

Artifacts:

- `data/gemma4-long-context-service-gate-20260701Tkvmin-control-screen2.json`
- `data/gemma4-long-context-service-gate-20260701Tkvmin-on-screen2.json`

### Broad screen, first implementation

Cases: `16213`, `22730`, and `30400` actual prompt tokens.

| Actual prompt tokens | Control prefill | KV-min prefill | Delta | Control decode | KV-min decode |
| ---: | ---: | ---: | ---: | ---: | ---: |
| `16213` | `1150.494670` | `1221.700294` | `+6.19%` | `126.901220` | `126.568422` |
| `22730` | `1060.620435` | `1117.490010` | `+5.36%` | `119.522935` | `119.703989` |
| `30400` | `969.843666` | `1020.170748` | `+5.19%` | `113.282419` | `112.839851` |

Artifacts:

- `data/gemma4-long-context-service-gate-20260701Tkvmin-control-broad1.json`
- `data/gemma4-long-context-service-gate-20260701Tkvmin-on-broad1.json`

### Broad screen, gated implementation

The implementation was refined so the extra KV-min scan is only used for large
query lengths. With `MIN_Q=1024`, the long-context prefill gain repeated.

| Actual prompt tokens | Control prefill | KV-min prefill | Delta | Control decode | KV-min decode |
| ---: | ---: | ---: | ---: | ---: | ---: |
| `16213` | `1153.410582` | `1224.281350` | `+6.14%` | `127.079630` | `126.791420` |
| `22730` | `1060.480112` | `1121.573786` | `+5.76%` | `119.560139` | `119.740383` |
| `30400` | `971.291559` | `1022.246643` | `+5.25%` | `113.343805` | `112.918638` |

Artifacts:

- `data/gemma4-long-context-service-gate-20260701Tkvmin2-control-broad1.json`
- `data/gemma4-long-context-service-gate-20260701Tkvmin2-on-broad1.json`

### Broad screen, `MIN_Q=2048`

Raising the threshold kept most of the long-prefill gain but did not solve the
short-decode concern.

| Actual prompt tokens | Control prefill | KV-min prefill | Delta | Control decode | KV-min decode |
| ---: | ---: | ---: | ---: | ---: | ---: |
| `16213` | `1148.973279` | `1207.134718` | `+5.06%` | `126.644985` | `126.554091` |
| `22730` | `1059.408767` | `1116.889990` | `+5.43%` | `119.670383` | `119.585209` |
| `30400` | `967.759431` | `1012.951805` | `+4.67%` | `113.226220` | `112.404770` |

Artifacts:

- `data/gemma4-long-context-service-gate-20260701Tkvmin2048-control-broad1.json`
- `data/gemma4-long-context-service-gate-20260701Tkvmin2048-on-broad1.json`

## Short-Decode Guards

All short guards passed the fixed cold realistic gate, `cached_tokens=0`, and
canary completion. The issue is speed, not correctness.

| Run | Group | Median 1-100 tok/s avg | Lanes |
| --- | --- | ---: | --- |
| `20260701Tkvmin-short-control1` | control | `119.022244` | `117.018890`, `121.025598` |
| `20260701Tkvmin-short-on1` | KV-min | `117.037910` | `113.770163`, `120.305656` |
| `20260701Tkvmin-short-control-xover1` | control | `116.102147` | `116.540758`, `115.663536` |
| `20260701Tkvmin-short-on-xover1` | KV-min | `115.105779` | `112.827856`, `117.383702` |
| `20260701Tkvmin2-short-control1` | control | `117.749545` | `114.494079`, `121.005012` |
| `20260701Tkvmin2-short-on1` | KV-min `MIN_Q=1024` | `116.905214` | `116.561161`, `117.249266` |
| `20260701Tkvmin2048-short-control1` | control | `116.523530` | `117.362873`, `115.684187` |
| `20260701Tkvmin2048-short-on1` | KV-min `MIN_Q=2048` | `114.346935` | `116.260333`, `112.433537` |

Combined first-implementation cross-over:

- controls: `117.562196 tok/s`
- candidates: `116.071844 tok/s`
- delta: `-1.27%`

The `MIN_Q=2048` guard was worse in the paired screen:

- control: `116.523530 tok/s`
- candidate: `114.346935 tok/s`
- delta: `-1.87%`

Short-guard artifacts:

- `data/gemma4-short-decode-guard-20260701Tkvmin-short-control1.json`
- `data/gemma4-short-decode-guard-20260701Tkvmin-short-on1.json`
- `data/gemma4-short-decode-guard-20260701Tkvmin-short-control-xover1.json`
- `data/gemma4-short-decode-guard-20260701Tkvmin-short-on-xover1.json`
- `data/gemma4-short-decode-guard-20260701Tkvmin2-short-control1.json`
- `data/gemma4-short-decode-guard-20260701Tkvmin2-short-on1.json`
- `data/gemma4-short-decode-guard-20260701Tkvmin2048-short-control1.json`
- `data/gemma4-short-decode-guard-20260701Tkvmin2048-short-on1.json`

## Decision

Do not promote KV-min left-bound scanning in the current form.

The long-context prefill gain is real and repeated (`+4.7%` to `+6.1%` on the
validated long-context cases), but the patch does not satisfy the project rule:
service/prefill changes must not lower the fixed short decode guard or target
quality. This patch is a preserved research artifact only.

The active llama.cpp source was reverted to remove all `KV_min` identifiers
after the patch was archived. The remaining source stack keeps the existing
record/service patches (`GGML_SYCL_FATTN_DV512_GQA_NCOLS2=8` and
`GGML_SYCL_FATTN_KV_MAX_SCAN_MIN_Q`).

## Follow-up Ideas

The concept is still promising for long prefill, but the next design needs a
cleaner separation from generation:

- implement a prefill-only dispatch/kernel variant so short decode never sees
  extra KV-min buffer shape, loads, branches, or compile-time effects;
- avoid doubling the existing `KV_max` scratch shape on default/decode paths;
- consider encoding the SWA left bound at launch/host level if the mask shape
  makes it deterministic for Gemma 4, instead of scanning and reading a second
  bound in every tile;
- profile whether a separate large-Q FlashAttention tile kernel can start from
  a compile-time/launch-time left bound with no per-tile minimum work;
- only revisit promotion after a paired four-lane long-context gate and fixed
  short-decode guard both pass, with no quality or `cached_tokens=0` issues.
