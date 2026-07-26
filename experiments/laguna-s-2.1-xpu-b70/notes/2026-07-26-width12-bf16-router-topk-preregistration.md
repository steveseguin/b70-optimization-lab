# Laguna width-12 direct-BF16 router top-k preregistration

Date: 2026-07-26 America/Toronto

Status: **standalone lane stopped at the first physical-card component gate.**
The candidate is exact and materially faster, but its `0.498946 ms` paired
median saving missed the preregistered `0.60 ms` floor. No other card and no
endpoint was run. The implementation remains eligible only as a separately
preregistered component of a combined treatment.

## Why this lane is open

The exact M=8 direct-BF16 router specialization already passed a four-card
component gate and removed `0.451-0.482 ms` from each 47-layer cycle. Its
endpoint phase also reduced aggregate target-cycle-normalized time by
`1.030 ms` while remaining 13/13 exact, although that noisy M=8 A1/B1 pair
failed its frozen headline-median gate.

The current width-12 record candidate explicitly forces this specialization
off. The later statement that the width-12 "fusion route" was closed covered
the shared-elementwise and QKNorm/RoPE attention kernels, not router top-k.

Width 12 currently scores `100.524890 tok/s` at `3.9552` emitted tokens per
cycle and a derived `39.35 ms` cycle. Reaching 102 at unchanged acceptance
requires about `0.57 ms` per cycle. Router work grows from eight to twelve
rows, while the existing specialization already saves about `0.46 ms` at
eight rows, so this is a measured scaling hypothesis rather than an
unbounded projection.

## Frozen candidate

Add one default-off selector:

```text
VLLM_XPU_LAGUNA_MWIDE_BF16_ROUTER_TOPK=1
```

It may extend the existing direct-BF16 sigmoid/top-k transaction to exactly
`[12,256]` only when all of these are literal:

- `VLLM_XPU_LAGUNA_EXACT_MAX_M=12`;
- `VLLM_XPU_LAGUNA_BATCHED_EXACT_MOE=1`;
- `VLLM_XPU_LAGUNA_M8_BF16_ROUTER_TOPK=1`; and
- the new width-12 selector is `1`.

The M=8 path and every other row count remain unchanged. The candidate must
retain the established arithmetic contract:

```text
BF16 [12,256] logits
-> exact FP32 widening inside the specialization
-> FP32 sigmoid
-> add FP32 [256] correction bias for selection only
-> lower-expert-ID tie break
-> top 10
-> renormalize the unbiased FP32 sigmoid weights
```

The native lane mapping, XOR reduction order, top-k ordering, output dtypes,
and source-index mapping remain unchanged. Only the grid grows from two to
three four-warp workgroups. There is no approximation, quantization change,
reassociation, alternate tie rule, local-only routing, or acceptance change.

Production dispatch must additionally require Laguna target verification,
256 experts, top 10, normalized sigmoid routing, no router softcap, FP32
correction bias, local router scale 1.0, no EPLB/redundant/hash routing,
PIECEWISE Breakable graph mode, and the exact width-12 verifier row identity.
Any drift is a hard error rather than a fallback.

## Component gate

Before an endpoint, compare the width-12 candidate against the incumbent
literal `BF16.float()` plus FP32 `topk_sigmoid` path on every physical B70.
Use changing random and adversarial BF16 `[12,256]` logits and changing FP32
biases, including:

- rank-9/10/11 ties and lower-ID tie winners;
- expert boundaries 0, 63, 64, 127, 128, and 255;
- adjacent BF16 values around the cutoff;
- adjacent FP32 bias values;
- signed zero and sigmoid saturation; and
- rotations through every row, expert, and top-k slot.

Require raw-byte and `torch.equal` equality for FP32 weights, int32 expert IDs,
and int32 token/expert source indices; repeat determinism; unchanged inputs;
ten distinct in-range IDs per row; and exact `slot * 12 + row` source
mapping.

After correctness, time only the incumbent cast plus top-k against the direct
candidate:

- 20 untimed cycles;
- 31 paired A-B-B-A blocks;
- 64 complete 47-call cycles per arm; and
- no model service or endpoint work.

Every card must independently win at least 24/31 blocks and save at least
`0.60 ms` per 47-layer cycle by paired median. A mismatch, failed card, or
missed timing floor stops the lane before an endpoint.

## Endpoint gate

Only a four-card component pass authorizes one same-session width-12 control
and candidate pair. The sole treatment difference is the new router selector
stack. Both starts remain cold, cache-zero, one active generation, no warmup,
no retry, and use the exact benchmark request construction.

Both legs must independently satisfy:

- 13/13 bitwise equality to the canonical q=1 teacher;
- `cached_tokens=0` for all 13 prompts;
- audited capture and replay topology `146/145` on all four ranks;
- normal decaying acceptance by position;
- clean startup, shutdown, and verified idle boundaries; and
- complete actual source and binary identity.

Promotion requires the candidate to exceed `102 tok/s` on the frozen scored
median. If it does, run one independent second cold confirmation before any
record or submission claim. No favorable retry, prompt removal, capture-window
relocation, cache reuse, or score-definition change is allowed.

## Component result

Kernel commit `906190641d708b8028018c5dde653e265c835348` produced candidate
module SHA256
`154eebd95beb83089b6628a21085e079b730c4474408d8fd2b484c385a0ce5d5`.
The first and only formal component leg ran on physical card zero at:

```text
/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/runs/mwide-bf16-router-component-9061906-41dd691d-20260726/card0/result.json
```

It passed all pre-timing and post-timing exactness checks over the 192-case
width-12 random/adversarial corpus. The candidate was faster in `31/31`
paired blocks:

| metric | incumbent | candidate | paired saving |
| --- | ---: | ---: | ---: |
| median per 47-call cycle | `0.959458 ms` | `0.460524 ms` | `0.498946 ms` |

The timing floor was `0.60 ms`, so `formal_component_pass=false` and the
preregistered early stop fired. Cards one through three and the endpoint were
not run. This is a positive micro-optimization result but not authority to
claim, project, or benchmark a standalone path to 102.
