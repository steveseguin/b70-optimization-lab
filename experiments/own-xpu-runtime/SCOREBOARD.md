# Our Intel Xe runtime — measured state, 2026-10-11

**Kernels work; complete device answers are still unverified.** This page covers
Unsloth UD-IQ3_XXS, the **quantized compressed version**, with full 16-bit KV.
The first real-model run is still reading its prompt. Best GEMV-only planning
rate: **24.4 tok/s**; reference runtime: **28.49 tok/s**; dominant observed cost:
**47 seconds of non-GEMV work per input position**. Receipts follow below.

**Kernel progress.** Effective GB/s means payload bytes divided by device time,
not measured memory-bus traffic. These are warm, fixed-input operator diagnostics
on card 3, not cold-prompt benchmarks. The measured streaming-read ceiling is
[589–593 GB/s, rounded to 590][ceiling]. Cells link through their round headers;
[calculation details and exact variants][snapshot] retain the numbers.

| Class (layer 0 unless stated), GB/s | [R1][r1] | [R2][r2] | [R3][r3] | [R4][r4] | [R5][r5] | [R6][r6] | Winning measured variant; % of 590 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| Q6 QKV / gate | 88 / 79 | 88 / 78 | 123 / 118 | — | 326 / 316 | — | expanded split4; 55 / 54% |
| Q6 attention output | 61 | 81 | 114 | — | 296 | — | expanded split4; 50% |
| Q8 HC down / up | 40 / 81 | 101 / 81 | 101 / 81 | — | 174 / 125 | — | expanded split4; 30 / 21% |
| F32 router | 286 | 288 | 396 | — | 239 | — | constant split4; 67% |
| IQ2_S expert gate / up | 51 / 50 | 50 / 51 | 52 / 52 | — | — | — | constant SG32; 9% |
| IQ4_NL expert down | 68 | 68 | 68 | — | — | — | SG32; 12% |
| Shared expert gate / down | 51 / 73 | 51 / 73 | 53 / 74 | — | 129 / 121 | — | expanded split4; 22 / 21% |
| Tiny HC injection / alpha | 2.7 / 29 | 5.3 / 33 | 9.5 / 56 | — | 7.7 / 44 | — | constant split4; 2 / 9% |
| Whole ordinary expert block | — | — | — | 66 | 66 | 66 | experts_sg32; 11% |
| Full vocabulary head | — | — | — | — | 371 | — | expanded SG32; 63% |

R1–R3 use the best recorded layer-0 variant medians; R5 divides fetched bytes
by the median of two owners' operation medians inside a layer sequence.
**R5 counts expanded bytes**, so bandwidth gains are not speedup ratios.
“—” means no comparable class entry here, not zero or a carried-forward result.
Winners are measured candidates; the active run retains its frozen dispatch.
Small differences across rounds are not speed verdicts. Raw receipts correct
older prose: the router is F32, expert down is IQ4_NL, and the packed head is
[521,472,000 bytes][census], not the older claimed size.

**Model-speed planning, not measured decode.** Sequential two-card placement
runs one layer on one card at a time. Sum representative measured GEMV sequences:
34 ordinary GDN + one PLE GDN + one upgraded GDN + 12 QSA + head/final HC.
Fixed routes and tiled weight fixtures exclude nonlinear work, KV/state,
transfers, host lookup and real dependency costs; bandwidth is not doubled.

| Stage / comparison | ms/token | tok/s | Evidence / limit |
| --- | ---: | ---: | --- |
| R1–R3 | — | — | Individual kernels only; no whole-step projection |
| R4 packed | 60.4 | 16.5 | [GEMV-only projection][r4], experts_split4 sequence |
| R5 expanded SG32 / split4 | 43.3 / 41.0 | 23.1 / 24.4 | [GEMV-only projections][r5]; R6 adds no winning expert variant |
| llama.cpp, two cards / one card | — | 28.49 / 15.94 | [Two-card screen][baseline2], [one-card screen][baseline1]; uncertified, different arithmetic authority |
| Packed-byte ideal ceiling | 8.4 | 119 | [4.951 GB / 590 GB/s][r4]; excludes all other work, **not the expanded-layout ceiling** |

**Transport.** [Pinned H2D][h2d] reaches about **28 GB/s device-side** for
expert-sized copies; same-card D2D reaches **270–540 GB/s** for larger copies
(payload, not read+write). [Peer copies][peer] take **18 µs for 10 KiB** and
**52 µs per exchange round trip**, from the measured **3.14 ms / 60-round**
stress loop. These are transport tests, not a complete tensor-parallel step.

**Correctness.** Device checks passed: [108 initial][initial], then
[272][e1] + [494][e2] + [548][e3] + [28][e4] + [126][e5] + [104][e6]
across the kernel rounds; these include repeated controls, not unique models.
The genuine kernel exactness failure was [a NaN sign flip][repair] in expanded
IQ3_S: compiler sign handling changed the bits. Preserving cached quiet-NaN bits
fixed it; the repaired device checks above passed without relaxing comparisons.
The [CPU full prompt pass matched 48/48 layer hashes][cpu] against frozen-order
oracle **[iq3-p13-r234-sg32-split4-bf16-v1][oracle]**. Shared arithmetic is not
independent model-equation proof. Device parity and fresh full-model repeats
remain open; the [alleged first-token failure][correctness] confused input tokens
with generated output. Separately, packet 15 currently fails its CPU gate.

**First real-model device run.** [Packet 13][p13] streams layers through one
card, processing the prompt then requesting up to eight generated tokens.
At **06:45:09 UTC**, [the frozen log snapshot][snapshot] records **48/87 prompt
positions complete**, still prefill. Input position zero took **61 ms GEMV +
47 s non-GEMV device time + 3.5 s transfer wall time**; total wall time was
**69 s**, including initialization and other host work. This is a first-position
diagnostic, not per-generated-token speed. The growing local
[timings.jsonl][live] is read-only; its input-token rows are not answers.

**Do not repeat:** [R2 wide-load variants][r2] regressed; [R6 register/SLM/pipeline
expert decoders][r6] reached only **13.6 / 8.4 / 7.6 GB/s** versus the retained
**66 GB/s** path. [Expanding all experts does not fit two cards][expansion];
keep experts packed and qualify dense-only expansion separately.

**Next, in order:**

1. **Packet 15, parallel non-GEMV kernels:** attack the observed **47 s** term
   first. Exact CPU comparison currently fails ([recorded status][snapshot]);
   resolve that before device timing. Large potential, no measured speedup yet.
2. **[Packet 14, within-layer two-card work][p14]:** projected **about 1.5×**
   GEMV-plus-exchange benefit under [the 80%-parallel, 60-exchange scenario][tp].
   The more realistic dependency count costs more; full-step gain is unmeasured.
3. **[Whole-step capture][capture]:** remove remaining host submission and
   synchronization gaps after kernels and placement work. Expected direction
   is faster steps; no numeric gain is measured or borrowed from another lane.

[r1]: stage2/packet6-kopt/receipts-card3-20261011/timing/timing.json
[r2]: stage2/packet7-kopt2/receipts-card3-20261011/timing.json
[r3]: stage2/packet8-kopt3/receipts-card3-20261011/timing.json
[r4]: stage2/packet9-kopt4/receipts-card3-20261011/timing.json
[r5]: stage2/packet10-kopt5/receipts-card3-20261011/timing.json
[r6]: stage2/packet11-kopt6/receipts-card3-20261011/timing.json
[ceiling]: stage2/packet7-kopt2/receipts-card3-20261011/ceiling/native.json
[snapshot]: data/scoreboard-20261011.json
[census]: ../qwen38-flash-next-ud-iq3xxs-b70/packet1/tensor-census.json
[baseline2]: ../../results/qwen38-flash-next-ud-iq3xxs-b70/reference-baseline-20261011.md
[baseline1]: ../../results/qwen38-flash-next-ud-iq3xxs-b70/reference-baseline-onecard-uncontended-20261011.md
[h2d]: stage2/packet5-h2d/card3-20261011/native.json
[peer]: stage2/packet12-peer/cards2-3-20261011/receipt.json
[initial]: stage2/packet2/first-device-20261011/device.json
[e1]: stage2/packet6-kopt/receipts-card3-20261011/exactness/window.json
[e2]: stage2/packet7-kopt2/receipts-card3-20261011/exactness/window.json
[e3]: stage2/packet8-kopt3/receipts-card3-20261011/exactness/window.json
[e4]: stage2/packet9-kopt4/receipts-card3-20261011/exactness/window.json
[e5]: stage2/packet10-kopt5/receipts-card3-20261011/exactness/window.json
[e6]: stage2/packet11-kopt6/receipts-card3-20261011/exactness/window.json
[repair]: stage2/packet10-kopt5/exactness-repair.json
[cpu]: stage2/packet13-integrate/correctness/runtime-order-oracle-comparison.json
[oracle]: ../qwen38-flash-next-ud-iq3xxs-b70/packet3-runtime-oracle/arithmetic.json
[correctness]: ../../notes/2026-10-11-first-token-correctness.md
[p13]: stage2/packet13-integrate/README.md
[live]: stage2/packet13-integrate/build/card3-first-token-a/run/timings.jsonl
[expansion]: stage2/packet10-kopt5/analysis.json
[p14]: stage2/packet14-tp2/README.md
[tp]: stage2/packet12-peer/projection.json
[capture]: DESIGN.md#one-captured-decode-transaction
