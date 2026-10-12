# Our Intel Xe runtime — measured state, 2026-10-12 01:30 UTC

**Bit-exact on one card and on two; 22.49 tok/s measured on two cards.** For Unsloth
UD-IQ3_XXS, the **quantized compressed version**, full 16-bit KV: the runtime reproduces
its CPU oracle exactly on the cards (64/64 tokens, 384/384 layer fixtures). Two-card
decode, all exact, within one day: **3.15 tok/s** as first sealed, **12.08** after a
linear allocation scan in the two-card backend was replaced by an ordered lookup
([evidence][locscan]), **17.85** with specialised non-GEMV kernels selected class by
class from a timing run on the card ([receipts][p26w2m]), **19.63** (50.2 ms per token)
with the second kernel round, sealed end to end ([packet 27][p27r]), **22.49** (44.3 ms
per token) with the paired expert gate/up kernel and the dense GEMV variants measured on
the card ([packet 29][p29r]). Reference **28.49 tok/s**. GPU kernel time is 41.2 ms per
token; the host issues 2,307 launches one by one (5.4–11.7 µs each depending on what
else the host is doing), so the GPU now waits for the host between small kernels.
[First exact decode and its reading][w2note].

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
same card 72/72 in two fresh owners. A second cause was found at 08:52 UTC: the
correctly-rounded divide/sqrt options were only on the compile line; they take effect
at link ([forensics][linkflags]), so every device binary through packet 16 had
approximate divide and sqrt. Identity v2 ([packet 17][p17]: deterministic `exp`/`log`
within 0.50000005 ULP, host RoPE table) passes the exhaustive host-versus-card check
for both functions when linked correctly; its 72-fixture device gates and the
full-model gate ([packet 18][p18]) wait for the reboot. The v2 CPU oracle agrees with
v1 on 41 of 64 tokens and departs at token 42, where two logits tie exactly at 22.0;
both answers read correctly ([decision note][v2note]).

**First real-model device run.** [Packet 13][p13] streamed layers through card 3:
87 prompt positions, then tokens **332, 37947, 1653, 10082, 3508, 8812, 25, 23288**
(`**Incident Retrospective: Production`), 5,247 s in total, clean teardown
([receipts][p13dev]). A generated position cost **59 s wall: 52 s non-GEMV
interpreter, 0.10 s GEMV, 3.9 s weight streaming**. This is a correctness diagnostic,
not a speed configuration.

**Non-GEMV after packet 15 (card 3, [timing][p15time]).** One new token through one
layer in a synthetic sequence: GDN **0.461 ms** device (14 launches), QSA **0.555 ms**
(17 launches); before, about 1,220 and 660 ms.

**Integrated one-card run with those kernels ([packet 16 W1][p16w1], card 3).** All 48
layer hashes and the token equal packet 13's device result; 485 s for the 87-position
prompt instead of 5,247 s. Per position: **71–92 ms GEMV and 81–112 ms non-GEMV device
time across 3,619 kernel launches**, plus 3.4–3.8 s of weight streaming and 3,463 host
waits (one-card streaming only). The non-GEMV time is about 3.5 times the synthetic
figure because the integrated layer issues about 50 non-GEMV launches, not 14–17: at
roughly 30 µs per launch, **launch count is now the main cost**. Planning value for
two-card resident decode is therefore about 5–6 tok/s as built, not 14–16.

**Two cards inside a layer ([packet 14][p14dev], cards 2+3).** Layer 0 over all 87
positions is bit-identical to the one-card device result. GEMV drops to about 0.5 ms
per card per layer, but **41 exchanges cost 1.53 ms per layer**, more than the split
saves. It pays only after the exchanges are merged.

**Do not repeat:** [R2 wide-load variants][r2] regressed; [R6 register/SLM/pipeline
expert decoders][r6] reached only **13.6 / 8.4 / 7.6 GB/s** versus the retained
**66 GB/s** path. [Expanding all experts does not fit two cards][expansion];
keep experts packed and qualify dense-only expansion separately.

**Where the 41.2 ms of GPU time per token goes** ([measured][p29r], 2,307 launches):
expert down 6.25 ms (48 × 130 µs, no winning candidate yet); expert gate/up 4.02 (was
8.62); route 3.27; QSA attention 3.18; gdn.qkv 2.81; attention projection 2.56; gdn.z
1.73; logits 1.68; gdn.recurrence 1.23; qsa.qgate 1.10; HC gates 2.13; about 9 ms in
some 1,500 launches of 3–15 µs each.

**Three things now limit the token, in this order:**

1. **One card is idle at any moment.** Layers 0–23 run on one card, 24–47 on the other.
   [Packet 32][p32] (Codex, CPU, in progress) turns the runtime into a two-stage
   pipeline, one process per card: the first card starts the next position on a guessed
   token while the second finishes the current one; a wrong guess is discarded and
   redone, so the emitted tokens stay the target's own and the output stays bit-exact.
   A right guess costs half a token time. The guess comes from the model's official
   one-token draft head; [packet 31][p31] (Codex, CPU, in progress) measures on CPU how
   often that head agrees with this quantized target (about 80% on the full-precision
   line). At 75% agreement the model gives about 1.5 times the sequential speed.
2. **The host issues every launch separately.** 12–18 ms per token of host work for
   2,307 launches, part of it avoidable validation and device queries per launch
   ([packet 35][p35], Codex, in progress: prepared launches, cheaper submission forms);
   the rest goes away if a card's half token is recorded once and replayed
   ([packet 34][p34], Codex, in progress: a one-card replay benchmark with the real
   kernels before any integration).
3. **Kernel time.** Expert down (6.25 ms) has resisted eleven exact candidates; a
   generated-code study ([packet 33][p33], Codex, in progress) reads the GPU assembly of
   the winners and losers to build a cost model before the next round.
   [Packet 30][p30] (Codex, in progress) covers route, QSA attention, HC gates and the
   combine/mix merges.

**Measurement hygiene found on 2026-10-12.** Decode windows are now pinned to four
reserved cores and the CPU helper jobs kept off them; token preparation (table lookups
from the memory-mapped model file) page-faulted in three runs while another job read the
same file, costing 4–9 ms per token; K2's rule for conflicting fusions discarded three
measured winners ([details][p29r]).

**Not pursued:** two cards inside one layer (host-fenced exchanges of about 50 µs do
not pay for kernels of 100–200 µs; chaining events between the cards directly is the
leading suspect of the 09:09 fault); the fused generic kernels of packets 21, 23 and 24
(bit-exact, 50–100 times slower per launch, [measurement][k2slow]).

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
[fault]: stage2/packet16-decode/evidence/20261011-w2x-two-card-fault/README.md
[linkflags]: stage2/packet17-detmath/evidence/20261011-wb-a-link-flags/README.md
[p16w1]: stage2/packet16-decode/receipts-card3-20261011-w1/window.json
[p18]: stage2/packet18-decode-v2/README.md
[p19]: stage2/packet19-depcheck/README.md
[p20]: stage2/packet20-launch/README.md
[p21]: stage2/packet21-fused/README.md
[w2note]: ../../notes/2026-10-11-first-exact-two-card-decode.md
[p23]: stage2/packet23-fast/README.md
[p22]: stage2/packet22-replay/README.md
[locscan]: stage2/packet18-decode-v2/evidence/20261011-host-bottleneck-location-scan/README.md
[p24]: stage2/packet24-kernels/README.md
[p26]: stage2/packet26-specialised/README.md
[p25]: stage2/packet25-gemv/README.md
[k2slow]: stage2/packet24-kernels/evidence/20261011-k2-c0-generic-kernels-slow/README.md
[p26w2m]: stage2/packet26-specialised/receipts-cards01-20261011-native-w2m/README.md
[p27]: stage2/packet27-round2/README.md
[p27r]: stage2/packet27-round2/receipts-cards01-20261012-chain/README.md
[p29]: stage2/packet29-merged/README.md
[p28g2]: stage2/packet28-dense/receipts-card2-20261011-g2/timing-table.md
[bounds]: stage2/bounds-20261011-gemv/README.md
[p29r]: stage2/packet29-merged/receipts-cards01-20261012-chain/README.md
[p30]: stage2/packet30-leftovers/README.md
[p31]: stage2/packet31-mtp-acceptance/README.md
[p32]: stage2/packet32-pipeline/README.md
[p33]: stage2/packet33-codegen/README.md
[p34]: stage2/packet34-replay-bench/README.md
[p35]: stage2/packet35-hostpath/README.md
