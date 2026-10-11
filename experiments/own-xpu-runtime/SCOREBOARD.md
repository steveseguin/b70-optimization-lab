# Our Intel Xe runtime — measured state, 2026-10-11 08:15 UTC

**The runtime answers correctly on a card, slowly, and not yet bit-exactly.** This page
covers Unsloth UD-IQ3_XXS, the **quantized compressed version**, with full 16-bit KV.
The first real-model run on card 3 produced the oracle's first eight tokens at about
59 s per position; its hidden states differ from the CPU oracle in low bits because the
card's `exp`/`log`/`1/sqrt` are not glibc's. Parallel non-GEMV kernels now cost about
**23 ms per token** instead of 52 s. Best planning rate: **about 14–16 tok/s** (41 ms
GEMV + 23–31 ms non-GEMV, sequential two-card, unmeasured as a whole); reference
runtime: **28.49 tok/s**. Receipts follow below.

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
independent model-equation proof. **Device parity with that oracle fails: 0/48 layer
fixtures** ([comparison][devcmp]), although all eight generated tokens agree. Cause,
measured by [packet 15's window][p15exact]: the packet 4 core on the card equals the
same core on the host in only 50/72 fixtures, and every differing case contains
`exp`, `log`, a `1/sqrt` chain or trig. The parallel kernels equal the core on the
same card 72/72 in two fresh owners. Identity v2 ([packet 17][p17], deterministic
`exp`/`log`, host RoPE table) is in preparation; [decision note][v2note].

**First real-model device run.** [Packet 13][p13] streamed layers through card 3:
87 prompt positions, then tokens **332, 37947, 1653, 10082, 3508, 8812, 25, 23288**
(`**Incident Retrospective: Production`), 5,247 s in total, clean teardown
([receipts][p13dev]). A generated position cost **59 s wall: 52 s non-GEMV
interpreter, 0.10 s GEMV, 3.9 s weight streaming**. This is a correctness diagnostic,
not a speed configuration.

**Non-GEMV after packet 15 (card 3, [timing][p15time]).** One new token through one
layer: GDN **0.461 ms** device (0.612 wall, 14 launches), QSA **0.555 ms** (0.763
wall, 17 launches); before, about 1,220 and 660 ms. Per token: about 23 ms device,
31 ms wall. Largest kernels: route+gather **0.230 ms per layer (11 ms per token)**,
GDN recurrence 0.109 ms, QSA attention 0.144 ms. Synthetic one-row sequences.

**Two cards inside a layer ([packet 14][p14dev], cards 2+3).** Layer 0 over all 87
positions is bit-identical to the one-card device result. GEMV drops to about 0.5 ms
per card per layer, but **41 exchanges cost 1.53 ms per layer**, more than the split
saves. It pays only after the exchanges are merged.

**Do not repeat:** [R2 wide-load variants][r2] regressed; [R6 register/SLM/pipeline
expert decoders][r6] reached only **13.6 / 8.4 / 7.6 GB/s** versus the retained
**66 GB/s** path. [Expanding all experts does not fit two cards][expansion];
keep experts packed and qualify dense-only expansion separately.

**Next, in order:**

1. **[Packet 16][p16], two-card resident decode** with the parallel kernels and
   chained events: the first measured decode tok/s. Planning value 14–16 tok/s.
2. **[Packet 17][p17], identity v2:** device census, deterministic-math equality on
   host and card, then the full-model v2 oracle gate. Needed before any result can be
   called exact.
3. **Route+gather kernel and launch merging:** 11 ms per token in one kernel; 14–17
   launches per layer at about 30 µs each.
4. **Merge packet 14's exchanges** (41 per layer to a few), then repeat its gate.
   Projected up to 1.5× on the GEMV part only.
5. **[Whole-step capture][capture]:** remove remaining host submission gaps.

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
[devcmp]: stage2/packet13-integrate/correctness/device-comparison.json
[p13dev]: stage2/packet13-integrate/receipts-card3-20261011-first-token/window.json
[p15exact]: stage2/packet15-nongemv/receipts-card3-20261011/exact-b/window.json
[p15time]: stage2/packet15-nongemv/receipts-card3-20261011/timing-a/summary.json
[p14dev]: stage2/packet14-tp2/receipts-cards23-20261011-layer/window.json
[p16]: stage2/packet16-decode/README.md
[p17]: stage2/packet17-detmath/README.md
[v2note]: ../../notes/2026-10-11-first-device-answer-and-arithmetic-v2.md
