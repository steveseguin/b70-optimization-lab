# The class-consistent FP16 linear on the server: R290 to R293

2026-09-11. Data: `data/2026-09-11-qwen35-4b-r290-classpad-on-the-server.json`, R293 columns in
`data/2026-09-09-qwen35-4b-concurrency-throughput-matrix.json`. Images and patches in
`experiments/qwen38-27b-b70/docker/` (`r290`, `r291`, `r292`, `r293`). Background:
`2026-09-09-the-fp16-linear-chunk-is-a-throughput-tax.md`.

## The result

On the R293 image with `VLLM_XPU_FP16_LINEAR_CLASSPAD=1`, this lane's unquantized FP16 linears run in one
measured oneDNN M-class per weight shape instead of R224's 32-row pieces. Measured on the server:

| | R224 (published) | R293 | |
| --- | ---: | ---: | --- |
| strict gates G1/G2/G3, TP1 and TP2 | 12/12 | **12/12** | lossless by every gate |
| one card, MTP0, 5 ms stagger, fragile suite, c64 | 1280/1280 at 1702 tok/s | **1280/1280 at 2104** | harness-certified, +23.6% |
| two cards, MTP0, 5 ms stagger, fragile suite, c64 | 1280/1280 at 2711 | **1280/1280 at 3164** | harness-certified, +16.7% |
| one card, depth 3, c64 | 1201 | **1831** | +52% |
| one card, depth 3, c16 | 1089 | **1353** | +24% |
| two cards, depth 3, c64 | 2021 | **2694** | +33% |
| two cards, MTP0, c64 | 2778 | **3317** | +19% |
| one card, depth 3, single user (strict) | 177.4 | 168.0 | -5.2% |
| one card, MTP0, single user (strict) | 102.6 | 96.5 | -6.0% |
| two cards, depth 3, single user (strict) | 240.9 | 225.9 | -6.2% |

Identity on one card is R224's at every rung: MTP0 near-exact to c64 (255/256), depth 3 exact through c16.
On two cards one prompt, `cache-c000`, sits on a tie at token 39 under the R293 arithmetic and diverges
once per pass from c2 up; every other rung and prompt behaves as under R224. The two-card stagger recipe
(chain 16, `r10`) is byte-exact at 3164 tok/s.

The speculation crossover moves. Under R224 depth 3 stopped paying at c16 because every extra user added
a full re-read of the 1.2 GB vocabulary projection per 32 rows; under R293 depth 3 leads MTP0 to about c32
on one card (1608 against 1625) and c24-c32 on two.

## How it got here

**R290** (chain 13) removed the tax and passed the gates, but lost one-card MTP0 exactness from c20 up and
cost 12% at single user. The op was bit-exact offline for every shape the server logged; the census was the
fault. It fingerprinted a class by row 0 of one random input, and on the server that merged rows 33-192 of
the 2560x4096 out-projection into one class and admitted 385-512 - the region where the small-N shapes'
kernels are split-K and run-to-run nondeterministic (`probes/census-small-shapes.py`). Prefill chunks of
several prompts land there, so the state after prefill differed between passes. The pad path also
allocated a zero block and concatenated on every call, about 75 times a step.

**R291** (chain 14, trimmed to q1/q5/q3) fingerprints on three inputs, verifies each class for
determinism and position/pad invariance at its first, middle and last member before it can be canonical,
falls back to R224 pieces for a shape with no eligible class, and pads from persistent buffers. It
restored exactness - MTP0 256/256 at c64, the stagger recipe 1280/1280 at 2100 tok/s - and read 8-9%
under R224 at single user.

**R292** drops the per-call zeroing of pad rows (stale rows verified harmless: 0 of 630 trials across all
seven server shapes, `probes/validate-r292-stale-pad.py`). **R293** chooses, for weights under 256 MiB,
the eligible class with the smallest first member: the out-projection had been padding one row to 97
because the most populous class starts there. Single user is now 5-6% under R224; the floor of this design
is one copy kernel plus a 33-row GEMM per unquantized projection per step.

## Serving recommendation

Two modes on one image, both lossless by the gates:

- `VLLM_XPU_FP16_LINEAR_CLASSPAD=0` (R224 behaviour): the published single-user headline, 177.4 tok/s.
- `VLLM_XPU_FP16_LINEAR_CLASSPAD=1`: any server expected to see more than about eight users. Depth 3 to
  about c32, no speculation above; add the 5 ms admission stagger for byte-exact output. One card 2104
  tok/s exact at c64; two cards 3164.

The 9B and 27B lanes run the same R224 op and the same oneDNN GEMM; their ladders above 32 rows carry the
same tax and the same fix applies, unmeasured there.

## A row-invariant GEMM would remove the pad; a naive one is too slow (2026-09-11)

The 5-6% single-user cost of R293 is one copy plus a 33-row GEMM per projection. The only way to remove it is a
GEMM whose reduction order does not depend on M at all. `probes/triton-fp16-gemm-probe.py` is a Triton fp16 GEMM
with a fixed K block and no split-K, so that property holds by construction: bit-identical rows at every M from 1
to 320, deterministic, and (at M=64) bit-identical to oneDNN's own output. It is not fast enough. On the 4B
vocabulary shape the best of four tilings is 2.33 ms at M=1 against oneDNN's 2.12 (+10%, worse than the pad's
+0.11 ms), 3.1 ms at M=32 (2.23), 3.6-6.2 at M=64 (2.46) and 12.7-34 at M=256 (2.87); on the per-layer shapes it
is 1.3-2x slower at M=1 and up to 10x on the out-projection. Closing the gap is real kernel work (register tiling,
prefetch, a 2D block layout for the weight), beyond this lane. Recorded so the next person does not repeat the
easy version.
