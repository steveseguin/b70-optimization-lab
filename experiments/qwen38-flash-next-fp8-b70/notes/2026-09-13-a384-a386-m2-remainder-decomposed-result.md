# Result: A384-A386 - the two-row step's remainder, by block

Preregistration: `2026-09-13-a384-a386-m2-remainder-decomposed-prereg.md`. Diag head `97e90c89`
(= `f1d5cd88` + three zeroing switches), stage v2, exact-mode exports, three exact-2K rows each; control
A369 (33.69 ms). A385 ran before the 11:38 UTC host freeze and its rows survived on the USB drive; A386
ran on the rebuilt chain after the 13:38 UTC reboot.

| arm | zeroed | forward M=2 median (min) ms | sample ms | draft ms | reading |
|---|---|---|---|---|---|
| A369 control | nothing | 33.69 (31.90) | 0.89 | 2.22 | certified ids `afffd211…` |
| A370 | MoE grouped GEMMs | 19.47 (19.40) | 0.87 | 1.86 | GEMMs 14.2 ms |
| A385 | whole MoE block | 14.80 (14.67) | 0.89 | 1.77 | block 18.9 ms; glue + shared expert + collectives = 19.47 − 14.80 = **4.7 ms** |
| A384 | PLE gather + add | 34.20 (31.85) | 0.88 | 2.17 | **0 ms** (inside noise) |
| A386 | LM head (zero logits) | 35.16 (33.17) | 0.66 | 2.13 | not in the timed forward; the sampler got cheaper on zero logits |

## The two-row step, accounted

33.69 ms = MoE GEMMs 14.2 + MoE glue/collectives 4.7 (of which the row-wise all-reduce excess is 1.5,
A378) + QSA 4.7 (module incl. projections, A372) + GDN 2.1 (A371) + HC ~0 (A373) + PLE ~0 (A384) +
**8.0 ms unattributed**. The LM head and the sampler are outside this number (A386). Against one row
(27.2 ms, remainder 6.5), the second row adds 2.9 ms of MoE GEMM (more distinct experts per step), ~1.5
ms of all-reduce, and ~1.5 ms spread over the rest.

## Reading and the next lever

- The largest per-row term is still the MoE grouped GEMM (14.2 ms, 42% of the step), and it is
  weight-bandwidth-bound at two rows: fewer expert bytes per step is the only lever there, and that is
  the acceptance-rate trade, not a lossless one.
- The 8.0 ms unattributed remainder is launch-bound glue spread over the layers (norms, residual and
  HC adds, gate/up split, activation, per-layer quantisation): ~400 small kernels under graph replay at
  ~15-20 µs each. Fusing them changes reduction orders (not lossless by construction), so it is a
  candidate only with a re-certification, and it is not preregistered now.
- The MoE glue (4.7 ms) is the largest lossless-by-construction target: alignment/sort/quantisation
  for two rows plus the per-row all-reduce (two collectives per layer instead of one). A row-invariant
  two-row collective would recover up to 1.5 ms; the alignment path is next to be timed in isolation.
- Broader value first: the long-context TTFT (200 s at 32K, prefill in 64-token batches) is the
  largest user-facing cost on the line and is identity-gated by A381's four hashes; that arm (larger
  `max_num_batched_tokens` on the 33,280-capacity MTP0 server) is preregistered next.
