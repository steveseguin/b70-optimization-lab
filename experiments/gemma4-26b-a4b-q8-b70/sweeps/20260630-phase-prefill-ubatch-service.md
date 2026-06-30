# Phase-Specific Prefill Ubatch Service Screen

Date: 2026-06-30
Owner/agent: Codex

## Hypothesis

The short-decode record uses `UBATCH_SIZE=1024`, while long-context service
prefill improves with larger physical prompt chunks. A default-off source patch
could keep generated-token decode behavior at ubatch 1024 while allowing prompt
prefill to use a larger `LLAMA_PREFILL_UBATCH_SIZE`.

This is a service/prefill experiment, not a LocalMaxxing headline lane. A
headline submission would still need to beat the current fixed cold-suite
record (`123.67689864739785 tok/s`) with `cached_tokens=0`.

## Patch Snapshots

- v1 context-only patch:
  `patches/gemma4-26b-a4b-q8-b70/20260630-llama-phase-prefill-ubatch-experiment.patch`
- v2 memory-sized patch:
  `patches/gemma4-26b-a4b-q8-b70/20260630-llama-phase-prefill-ubatch-memory-sized-experiment.patch`

Both patches are default-off unless `LLAMA_PREFILL_UBATCH_SIZE` is set. v2 also
sizes SWA/ISWA attention memory with `max(n_ubatch, n_ubatch_prefill)`.

## Run Identity

Common identity:

- target/verifier: `gemma-4-26B-A4B-it-UD-Q8_K_XL.gguf`
- draft: `gemma-4-26B-A4B-it-Q4_0-MTP.gguf`
- runtime: llama.cpp `c926ad098` Gemma record source stack
- backend: SYCL / Intel Arc Pro B70, one replica per GPU
- context: `CTX_SIZE=32768`
- flash attention: `FLASH_ATTN=on`
- VMM: `GGML_SYCL_ENABLE_VMM=1`
- service prefill selector: `GGML_SYCL_FATTN_DV512_GQA_NCOLS2=8`
- MTP: `n_max=3`, `n_min=2`, `p_min=0.0475`, Q4_0 draft, target-verified
- validity: fixed cold long-context suite, each prompt once,
  `cached_tokens=0`, exact JSON validation, canary pass

Long-context screen command shape:

```bash
cd /home/steve/qwen36-results-main
GGML_SYCL_FATTN_DV512_GQA_NCOLS2=8 \
LLAMA_PREFILL_UBATCH_SIZE=<prefill_ubatch> \
LONG_CONTEXT_CASE_IDS='lc-22000-middle' \
LONG_CONTEXT_MAX_TARGET_PROMPT_TOKENS=24000 \
CANARY_REPEATS=1 \
MAX_TOKENS=96 \
READINESS_TIMEOUT_S=900 \
BASE_PORT=<port> \
STAMP=<stamp> \
LANE_SPECS='<gpu>:<batch>:1024:<tag> ...' \
repro/gemma4-26b-a4b-q8-b70/run-vdr2-long-context-service-gate.sh
```

Short guard command shape:

```bash
cd /home/steve/qwen36-results-main
GGML_SYCL_FATTN_DV512_GQA_NCOLS2=8 \
LLAMA_PREFILL_UBATCH_SIZE=2048 \
CANARY_REPEATS=32 \
MAX_TOKENS=512 \
READINESS_TIMEOUT_S=900 \
BASE_PORT=<port> \
STAMP=<stamp> \
LANE_SPECS='<gpu>:2048:1024:<tag> ...' \
repro/gemma4-26b-a4b-q8-b70/run-vdr2-short-decode-guard.sh
```

The existing multi-lane wrappers cannot set `LLAMA_PREFILL_UBATCH_SIZE` per
lane; run separate invocations when comparing different prefill values.

## Results

### v1: context-only phase ubatch

Candidate:
`BATCH_SIZE=2048`, `UBATCH_SIZE=1024`, `LLAMA_PREFILL_UBATCH_SIZE=2048`.

Artifacts:

- control aggregate:
  `data/gemma4-long-context-service-gate-20260630Tprefill-ubatch-phase-controlA.json`
- candidate aggregate:
  `data/gemma4-long-context-service-gate-20260630Tprefill-ubatch-phase-candidateA.json`

| Lane group | Prefill tok/s avg | Decode tok/s avg | Validity |
| --- | ---: | ---: | --- |
| control `2048/2048` | `951.1858` | `112.9548` | pass |
| v1 candidate `2048/1024 + prefill2048` | `880.2510` | `118.4029` | pass |

v1 is rejected. It passed exact validation and cache-zero, but every long
prefill repeatedly failed the first `2048`-token attempt and retried at
`1024`:

```text
failed to find free space in the KV cache, retrying with smaller batch size,
off = 0, n_batch = 1024, ret = 1
```

Root cause: the patch changed the context split size, but SWA/ISWA memory was
still sized from plain `n_ubatch`, so a `2048` prompt chunk could not fit when
`-ub 1024`.

### v2: memory-sized phase ubatch

v2 uses the same user-facing env, but sizes the SWA/ISWA attention memory using
the larger prefill ubatch. This removes the retry loop.

Artifacts:

- control aggregate:
  `data/gemma4-long-context-service-gate-20260630Tprefill-ubatch-phase-v2-controlA.json`
- `prefill2048` aggregate:
  `data/gemma4-long-context-service-gate-20260630Tprefill-ubatch-phase-v2-candidateA.json`
- `prefill2304` aggregate:
  `data/gemma4-long-context-service-gate-20260630Tprefill-ubatch-phase-v2-prefill2304-A.json`
- `prefill2560` aggregate:
  `data/gemma4-long-context-service-gate-20260630Tprefill-ubatch-phase-v2-prefill2560-A.json`

Long-context `lc-22000-middle`, `30400` actual prompt tokens:

| Lane group | Prefill tok/s avg | Decode tok/s avg | Retry warnings | Validity |
| --- | ---: | ---: | ---: | --- |
| control `2048/2048` | `949.7463` | `112.8034` | `0` | pass |
| v2 `2048/1024 + prefill2048` | `956.7217` | `112.9063` | `0` | pass |
| v2 `2304/1024 + prefill2304` | `946.7823` | `110.7488` | `0` | pass |
| v2 `2560/1024 + prefill2560` | `957.9547` | `110.8018` | `0` | pass |

All valid long-context lanes produced the same output hash:

```text
a2c9ffd867b906c1f59e57e7b647e91bae0909b04f7f8de3883c6fae77dfdf72
```

Short cold-suite guard:

- control aggregate:
  `data/gemma4-short-decode-guard-20260630Tprefill-ubatch-phase-v2-short-controlA.json`
- candidate aggregate:
  `data/gemma4-short-decode-guard-20260630Tprefill-ubatch-phase-v2-short-candidateA.json`

| Lane group | Median tok/s 1-100 avg | Cache-zero | Validity |
| --- | ---: | --- | --- |
| control `1024/1024` | `115.8903` | yes | pass |
| v2 `2048/1024 + prefill2048` | `120.8849` | yes | pass |

The short result is useful but not a new record; the current headline remains
`123.67689864739785 tok/s`.

## Decision

Keep v2 as a preserved service-lane patch candidate, but do not promote or
submit it as a headline record.

Recommended use if this patch is applied for service experiments:

```bash
BATCH_SIZE=2048
UBATCH_SIZE=1024
LLAMA_PREFILL_UBATCH_SIZE=2048
GGML_SYCL_FATTN_DV512_GQA_NCOLS2=8
```

Reasoning:

- v1 is a closed negative because it causes KV retry churn and loses prefill;
- v2 fixes the retry failure and gives UB2048-level long prefill while keeping
  the short guard valid;
- `prefill2304` and `prefill2560` did not improve the balanced service profile
  in the paired screen;
- no LocalMaxxing submission: this is service/prefill evidence and did not
  beat the fixed cold short-decode record.

Future work should only promote this if a full service recipe wants separate
prompt/decode sizing and also passes the full short fixed suite afterward.
