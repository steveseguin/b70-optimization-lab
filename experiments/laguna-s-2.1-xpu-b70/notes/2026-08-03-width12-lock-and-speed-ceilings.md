# The width-12 lock, and what actually caps Laguna decode

Date: 2026-08-03 America/Toronto

Status: **measured. Four device runs on recovered hardware. No target met; the
binding constraint is identified and quantified.**

## Measurements taken

All at 32,640-token prompts, cold cache, `gpu_memory_utilization=0.80`, TP4.

| config | decode tok/s | TTFT s | prefill tok/s | accept |
| :--- | ---: | ---: | ---: | ---: |
| q12 (M=12, full stack) — 2026-08-02 baseline | 39.589 | 4.478 | 7345 | 0.47% |
| qdepth d=11 (M=12, 14 selectors off) | **7.25** | 11.043 | 2972 | 0.56% |
| q8 (M=8, m8 selectors on) | **7.10** | 14.402 | 2370 | 0.99% |

Short-context, same session, q12 with exact-prefill chunks on:

| prompt | TTFT s | prefill tok/s | decode tok/s |
| ---: | ---: | ---: | ---: |
| 1,024 | 0.202 | 5169 | 152.3 |
| 4,096 | 0.564 | 7345 | 79.6 |

These reproduce the 2026-08-02 baseline to three decimals, so the harness and
the measurement are sound.

## Finding: the optimized decode path is width-12-locked

`qdepth` at **M=12** with the fused selectors off scores 7.25. `q8` at **M=8**
with the m8 selectors on scores 7.10. Width is not the variable — the selector
set is. Both fall to ~18% of the q12 result.

The q12 configuration enables a stack that neither alternative can:

| selector | q12 | q8 | qdepth |
| :--- | :-: | :-: | :-: |
| `DFLASH_SEGMENTED_GRAPH` | 1 | 0 | 0 |
| `DFLASH_INLINE_ATTENTION_GRAPHS` | 1 | 0 | 0 |
| `DECODE_GRF128` | 1 | 0 | 0 |
| `DECODE_TRANSPOSED_SCALES` | 1 | 0 | 0 |
| `MWIDE_BF16_ROUTER_TOPK` | 1 | 0 | 0 |
| `M12_SHARED_ELEMENTWISE` | 1 | 0 | 0 |

Each is width-12 by construction, and the pins are in source:

- `gpu_model_runner.py:4139` — `"wrong_width": VLLM_XPU_LAGUNA_EXACT_MAX_M != 12`
  refuses the segmented graph at any other width.
- `gpu_model_runner.py:4382` — the capture filter tests
  `batch_descriptor.num_tokens == 12` as a literal, while the neighbouring
  capture-size check at `:4199` is already parameterised on `EXACT_MAX_M`.
- `laguna_dflash.py:90` — the context-KV contract, which the segmented graph
  requires, pins `num_speculative_tokens != 11`.
- `DECODE_TRANSPOSED_SCALES` gates on `num_rows == 12` on the host and
  `total_m == 120` on the device.

Target-side graph capture is **not** the blocker: the q8 run logged
`Replayed audited breakable cudagraph for BatchDescriptor(num_tokens=8, ...)`,
so `M8_BREAKABLE_GRAPH` captures correctly at width 8. What is missing at other
widths is the draft-side segmented/inline attention graphs and the decode
kernels.

## Why this caps every target

A roofline built from the checkpoint config predicts M=12 at 32K as **39.8
tok/s** against **39.589 measured** — under 1% error, so the model is sound.

| context | M=12 roofline | M=1 roofline |
| ---: | ---: | ---: |
| 1,024 | 246.7 | 231.5 |
| 4,096 | 150.0 | 227.7 |
| 32,768 | **68.5** | **197.8** |

At 32K a decode step reads 32.5 GB at M=12 versus 9.2 GB at M=1, because
verifying 12 rows makes the router touch **97 of 256 experts per layer** instead
of 10. Speculation returns 3.6 accepted tokens at 1K, 2.2 at 4K and 1.05 at 32K,
so past roughly 2K it costs more bandwidth than it returns.

The arithmetic therefore says drafting less is worth ~3x at long context. The
measurements say you cannot collect it, because leaving M=12 forfeits the
width-12 decode stack and efficiency falls from 58% of roofline to about 11%.

Both slow runs are launch-bound rather than bandwidth-bound: 32.5 GB in 141 ms
is 230 GB/s, roughly 11% of the 2.12 TB/s available across four cards. q12's
26.5 ms step is 1.23 TB/s, or 58%.

## Target assessment

| target | status |
| :--- | :--- |
| 1000 tok/s prefill | **met** in bulk — 5,169 at 1K, 7,345 at 4K and 32K |
| 100 tok/s decode, no speculation | **reachable in principle** (roofline 197.8 at 32K) but needs a width-1 decode stack that does not exist |
| 250 tok/s decode with speculation | **above the ceiling.** 246.7 at 1K at *perfect* efficiency, falling with context |
| >150 tok/s at 32K with speculation | **physically impossible.** Ceiling is 68.5--78.6 tok/s even at 100% bandwidth |

The two impossible targets are impossible for the same reason: at M=12 the
expert-weight traffic is fixed by top-10-of-256 routing, and no amount of
efficiency work reduces bytes already required.

## The one lever that remains, and its cost

Decode at M=1 reads 9.16 GB per step, of which **5.59 GB — 61% — is BF16
attention weights** (`q/k/v/o_proj`). The INT4 scheme targets only
`gate/up/down`, so attention was never quantised. That 61% is the single
largest reducible term, and it is closed off by the standing constraint against
further quantisation.

## Engineering path, in dependency order

1. Parameterise the two literal width pins
   (`gpu_model_runner.py:4139`, `:4382`) on `EXACT_MAX_M`.
2. Generalise the context-KV depth pin (`laguna_dflash.py:90`) from `== 11` to
   `EXACT_MAX_M - 1`.
3. Port `DECODE_GRF128` and `DECODE_TRANSPOSED_SCALES` off their `num_rows == 12`
   / `total_m == 120` gates.
4. Provide `m1`/`m4` equivalents of the `m8`/`m12` shared-elementwise and router
   families, proved exact first.
5. Only then is a no-speculation or dynamic-depth policy measurable, and only
   then does the ~3x long-context headroom become collectable.

Steps 1--2 are small. Steps 3--4 are the real work and are why 32K decode has
stayed at 39.589 through the whole campaign: the ladder was built on a width-12
verifier because that is the only width where the decode stack exists.

## Boundaries

No quantisation was changed, no cache or speculation setting was used to
inflate a number, and every figure above is a cold-cache measurement of a real
request. The protected `125.4619731637751 tok/s` conventional short-decode
record is untouched.
