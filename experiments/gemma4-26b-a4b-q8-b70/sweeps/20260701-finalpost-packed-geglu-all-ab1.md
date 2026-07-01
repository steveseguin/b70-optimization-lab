# 2026-07-01 final-postnorm + packed GEGLU-all A/B

Status: closed negative. Do not promote, full512-confirm, or submit.

## Purpose

Retest the existing default-off packed routed gate/up GEGLU epilogue against
the current promoted final-postnorm record identity.

This is not a new code patch. The source path already exists behind:

```bash
LLAMA_GEMMA4_MOE_GATEUP_GEGLU_EPILOGUE=all
```

The broad packed-GEGLU mode previously lost under the full512 gate before the
final post-norm residual fusion became part of the promoted recipe. This run
checks the interaction without changing source and without repeating pure
config roulette.

## Run Identity

Stamp: `20260701T052815Z-finalpost-packedgeglu-all-ab1`

Common identity:

- target/verifier: Gemma 4 26B A4B IT `UD-Q8_K_XL`;
- draft: Gemma MTP `Q4_0`, accepted tokens verified by the Q8 target;
- runtime: `/home/steve/src/llama.cpp-gemma-record-repro-c926`;
- wrapper: `repro/gemma4-26b-a4b-q8-b70/run-vdr2-selecteddown-record.sh`;
- `FLASH_ATTN=on`, `CTX_SIZE=32768`, `GGML_SYCL_ENABLE_VMM=1`;
- `BATCH_SIZE=1024`, `UBATCH_SIZE=1024`;
- `MAX_TOKENS=128`, `CANARY_REPEATS=64`;
- promoted defaults active, including
  `LLAMA_GEMMA4_FUSED_FINAL_POST_NORM_RESIDUAL=1`,
  `LLAMA_SPEC_VERIFY_BACKEND_ARGMAX_IDS=1`,
  `LLAMA_SPEC_VERIFY_BULK_SAMPLED_IDS=1`, and
  `LLAMA_GEMMA4_MOE_FUSED_DOWN_WEIGHTED_SUM_REORDER_VDR2=1`.

Lanes:

| GPU | Role | Result directory |
| --- | --- | --- |
| 0 | control | `data/gemma4-q8-gpu0-control-strict128-20260701T052815Z-finalpost-packedgeglu-all-ab1/` |
| 1 | packed GEGLU all | `data/gemma4-q8-gpu1-packedgegluall-strict128-20260701T052815Z-finalpost-packedgeglu-all-ab1/` |
| 2 | control | `data/gemma4-q8-gpu2-control-strict128-20260701T052815Z-finalpost-packedgeglu-all-ab1/` |
| 3 | packed GEGLU all | `data/gemma4-q8-gpu3-packedgegluall-strict128-20260701T052815Z-finalpost-packedgeglu-all-ab1/` |

## Decision Criteria

This strict128 A/B is only a screen:

- all lanes must pass the fixed realistic cold gate;
- every request must report `cached_tokens=0`;
- canary must pass;
- the candidate must beat same-window controls by enough margin to justify a
  full512 promotion run.

Do not submit any result from this screen to LocalMaxxing.

## Results

All four lanes passed the fixed realistic cold gate, had `cached_tokens=0` for
every request, and passed the 256-row canary.

| GPU | Role | Gate | Canary | Median 1-100 tok/s | p10 | Mean | Full tok/s | Wall tok/s | TTFT ms |
| --- | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 0 | control | pass | 256/256 | `122.286598` | `105.697973` | `119.612385` | `116.685065` | `100.072730` | `180.526` |
| 1 | packed GEGLU all | pass | 256/256 | `116.511291` | `104.934604` | `118.290174` | `117.468380` | `100.153317` | `179.699` |
| 2 | control | pass | 256/256 | `116.629884` | `107.766050` | `117.673043` | `114.466615` | `96.749505` | `178.852` |
| 3 | packed GEGLU all | pass | 256/256 | `118.719590` | `107.491688` | `117.866244` | `115.050775` | `98.618503` | `179.198` |

Same-window primary averages:

- controls: `119.458241 tok/s`;
- packed GEGLU all: `117.615440 tok/s`;
- delta: `-1.842801 tok/s`.

## Decision

Closed negative. The broad packed GEGLU epilogue remains correctness-safe, but
it does not improve the promoted final-postnorm record identity. This is
consistent with the earlier pre-finalpost broad packed-GEGLU full512 loss.

Do not run a full512 promotion for this interaction. Reopen only if a future
profile shows that the packed GEGLU path changes a newly dominant node or if a
new source change materially alters the routed MoE graph shape.
