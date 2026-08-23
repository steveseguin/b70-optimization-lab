# Ornith 1.5 35B-A3B: fixed-2048 reordered DMMV is negative

Date: 2026-08-23 EDT

Status: **CLOSED PERFORMANCE NEGATIVE — retain the generic WG4 kernel**

Ornith is derived from the Qwen family, so its accepted one-token decode graph
was profiled before transferring another Qwen-shaped optimization. The steady
graph contains 231 generic reordered quantized DMMV calls; 151 (65.4%) use
exactly 2,048 input columns:

- 131 Q4_K calls, led by recurrent alpha/beta, attention gate, and attention
  Q/K/V projections;
- 20 Q6_K calls, led by attention Q/K/V and the output head.

The default-off candidate instantiated dedicated Q4_K and Q6_K ESIMD kernels
with the eight `QK_K=256` blocks fixed at compile time. It retained the
accepted four-worker assignment, each worker's block order, `mac_pair`, local
reductions, and leader summation order. The intent was limited to loop
unrolling and constant address arithmetic.

Correctness passed. A four-token smoke run recorded 456 candidate hits. The
canonical 128-token candidate recorded 19,180 hits and produced transcript SHA
`2e7965fcdc273f0433df359cff5188ae3585426fd32f28536121d1b5e35dad18`,
identical to both the same-binary flag-off control and the accepted record.

The mirrored depth-zero `tg128`, seven-repetition A/B/B/A screen was negative:

| Arm | Decode (tok/s) | Within-run standard deviation |
| --- | ---: | ---: |
| Control A | 133.788793 | 1.786234 |
| Fixed-2048 A | 133.511399 | 2.026809 |
| Fixed-2048 B | 132.310094 | 1.392879 |
| Control B | 132.799828 | 2.086472 |

Control mean was 133.294311 tok/s and candidate mean was 132.910747 tok/s,
a **-0.288%** change. This did not justify fresh-server escalation. The likely
interpretation is that the compiler already handles the short generic loop
well, while the extra specialized kernels add instruction/cache cost.

The incremental rejected patch is
`../patches/llamacpp-ornith15-dmmv-fixed2048-performance-negative-20260823.patch`.
Raw engine records are under `../data/ornith-fixed2048-*`; the captured debug
dispatch log is `../data/ornith35b-dmmv-steady-decode-debug-20260823.log.gz`.
No public recipe flag changed. Source and all accepted binaries were restored
to their recorded hashes after the screen.
