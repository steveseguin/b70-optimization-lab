# Qwen3.8-27B Q4_K_M TP1: context+KV sweep, and the growing q8_0-KV decode penalty

Date: 2026-08-22. Single Arc Pro B70 (gpu0), llama.cpp SYCL TP1 lane build
(`build-sycl-aot-bmg-g31`), Q4_K_M target-only, flash-attn on. `llama-bench`
pp2048 + tg128 at each depth, 5 reps. Directly answers the user's request for
TP1 decode+prefill sweeps 0->32K and "KV8 vs KV16 differences." Raw data:
`data/2026-08-22-q4km-tp1-context-kv-sweep.json`; chart
`data/2026-08-22-q4km-tp1-context-kv-sweep.svg`.

## Metric note (do not confuse with the promoted number)

These are `llama-bench` raw-engine rates (tg128 decode, pp2048 prefill). They
are NOT the conventional realistic-suite first-100-token median that produced
the promoted **27.82 tok/s** Q4_K_M TP1 lane result. Use this sweep for the
*shape* (rate vs context, and the KV-dtype delta), not as a headline number.
Depth-0 tg128 is 24.81 here vs the 27.82 conventional figure - different
harness and metric, both real.

## Decode (tg128), tok/s

| depth | KV f16 | KV q8_0 | q8 vs f16 |
| ---: | ---: | ---: | ---: |
| 0 | 24.81 | 24.27 | -2.2% |
| 2048 | 24.46 | 22.45 | -8.2% |
| 4096 | 24.25 | 21.05 | -13.2% |
| 8192 | 23.83 | 18.68 | -21.6% |
| 16384 | 23.10 | 14.86 | -35.7% |
| 24576 | 22.42 | 12.40 | -44.7% |
| 32768 | 21.77 | 10.66 | **-51.0%** |

## Prefill (pp2048), tok/s

| depth | KV f16 | KV q8_0 | q8 vs f16 |
| ---: | ---: | ---: | ---: |
| 0 | 825.2 | 817.8 | -0.9% |
| 2048 | 919.7 | 912.2 | -0.8% |
| 8192 | 851.0 | 843.2 | -0.9% |
| 16384 | 779.5 | 772.0 | -1.0% |
| 32768 | 667.8 | 662.6 | -0.8% |

## Findings

1. **The q8_0-KV decode penalty grows with context** - the headline result.
   Near parity at 0 ctx (-2%), it widens monotonically to **-51% at 32K**
   (10.66 vs 21.77 tok/s). The per-token KV dequant work scales with cached
   length, so on this SYCL backend it goes from noise to the dominant decode
   cost as context fills. This is the opposite of the common "KV8 is free
   speed + memory" assumption.
2. **Prefill is KV-dtype-independent** (<1.5% at every depth). Prefill is
   compute-bound; KV storage dtype barely touches it. So the whole q8_0 cost
   lands on decode, not prefill.
3. **f16 KV decode is remarkably flat**: 24.81 -> 21.77 (-12.3%) across
   0->32K. Long context is cheap for decode *if* KV stays f16.
4. **Practical rule (Q4_K_M TP1 on B70):** keep KV at **f16 for speed**;
   choose q8_0 KV only when you must fit longer context into 32 GiB, and
   budget a large long-context decode hit for it. This contrasts with the
   Reddit vLLM report, which ran **fp8 KV** by default - on that newer vLLM
   XPU path fp8 KV may behave differently, but on our llama.cpp SYCL lane
   f16 KV clearly wins for speed.

## Relation to the vLLM TP1 line

The vLLM TP1 matrix is still blocked on the pinned image (see
`2026-08-22-qwen38-tp1-vllm-bringup-finding.md`). This llama.cpp sweep fills
the TP1 context+KV question on our quality-accepted lane in the meantime, and
gives a concrete KV-dtype recommendation the vLLM fp8-KV numbers cannot (they
never had an f16-KV control at depth on single card here).

## Next

- Extend the same sweep to **Q8_0** target (higher-quality weight) for the
  paired weight-vs-KV picture, if a TP1 Q8_0 row is wanted for the board.
- MTP/DFlash TP1 ladder needs the llama.cpp *server* (speculation), not
  llama-bench; separate driver.
- Fold the decode/prefill-vs-context curves into the TP1 package README that
  index.html links.
