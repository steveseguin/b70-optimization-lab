# Tiny runtime classes and geometry candidates

This is an inventory, not a claim that one geometry is faster. T1 must establish the floor, and K2 must measure each actual class. The inherited selection is packet29's dispatch plus packet37's recorded changes. These source files are read-only inputs.

| Runtime class | Current source / shape | Prepared comparison |
|---|---|---|
| silu_div4, silu_product, routed/shared activations, HC act | `packet29-merged/native.cpp` `ng::Kernel`, WG128 SG32, 1,024 local floats, cooperative guard barriers; `kernels.hpp` activation | Exact per-element statement body with range, WG32 SG32 or WG256 SG32; remove unused cooperation |
| HC mix | same native kernel / `ng::mix` | Same four-term summation and sigmoid order, mapped to independent elements |
| moe combine | same native kernel / `ng::moe_combine` | Same expert loop and two BF16 rounding points, independent elements |
| GDN convolution | same native kernel / `ng::conv` | One independent channel, identical token/tap/history loop and BF16 stores; range/WG32/WG256 |
| GDN gated norm | same native kernel / `ng::gated_norm`, WG128 SG32 with local tree | WG32 and WG256; exact same `ng::group` body, barriers, local storage and tree nodes |
| QSA prepare | same native kernel / `ng::prepare`, WG128 SG32 | WG32/WG256 with unchanged cooperative body |
| QSA append/pool | same native kernel / `ng::pool`, WG128 SG32 | WG32/WG256 with unchanged cooperative body |
| HC norm stages | `specialised_submit.cpp` / `specialised::body`, two plain-range launches | Existing-range baseline plus WG32/WG256 comparators in `extras-notes.md`; no expensive-shape claim before T1 |
| unfused attention/FFN combines | `adapter.cpp` / `simple_body<Op::hc_combine>`, plain range | Existing-range baseline plus WG32/WG256 comparators in `extras-notes.md`; algebra and rounding remain inherited |
| streams | `adapter.cpp` broadcast `simple_body<Op::hc_mix>`, plain range | Existing-range baseline plus WG32/WG256 comparators in `extras-notes.md` |
| QSA select | `round2_submit.cpp`, two WG32 SG32 cooperative stages | WG32/WG256 exact cooperative stage comparators, independently gated; see `extras-notes.md` |
| status checks, begin/commit | `adapter.cpp` `Glue`, WG128 SG32 and `max(8192,h)` local floats | Flat exact status/commit/stream candidates with dedicated argument binding and CPU proof; see `extras-notes.md` |

All direct leaf candidates retain the unchanged `ng::group` per-element source statements. Only group/lane-to-index mapping changes. Sticky error/active and invalid-position checks are retained. The cooperative variants retain even the original guard barriers and local scratch, changing only work-group width. Candidate argument shape + pointers are below 1,024 bytes.

`tiny_cpu.cpp` reads existing packet29 fusion fixtures, compares the frozen reference Core to the incumbent, then compares each geometry's complete output/status bytes to the incumbent. It adds widths 1,17,31,33,127,129,640,2560 and inactive/sticky/invalid-position/NaN inputs. `tiny_timing.cpp` calls the original `ng::submit` through `Device::compute` for the incumbent, and owns each candidate through the same ledger. Device equality runs across every supported existing fixture. Timings use an explicit full-size single-token allow-list (including HC act width320), with F32-gain capacity256 variants for convolution, gated norm, QSA prepare and pool. Pool is checked at positions3 and255; preceding pooled state is seeded consistently and then independently checked against Core recomputation. Timings use these, 200 repetitions, alternating order; each timing arm starts from restored buffers outside timing. Tiny payloads do not exceed 8 MiB in these timing cases.

Integration vocabulary remains `packet26.dispatch.v1`: new named class choices must be added explicitly (e.g. `p42.tiny.range`, `p42.tiny.wg32`, `p42.tiny.wg256`). No default is selected before K2. Class names continue to be the runtime's existing class keys; a fixture filename is evidence, not a new dispatch key.

CPU gates passed on GCC and strict icpx: 240 fixtures and 720 geometry comparisons per process, two fresh processes each. Total: 960 Core-vs-incumbent checks and 2,880 candidate byte comparisons. Output digests agree across all four runs. Default icpx NaN payload selection needs strict host flags for the Core proof; the diagnostic is preserved, and native device byte gates remain mandatory.

Cooperative candidates are compile-time operation specializations of the frozen incumbent body. `tiny_source_gate.py` mechanically proves the copied statements differ only in template dispatch, `if constexpr`, and qualification of the operation named `select`. Merely assigning a template constant into a host-side Shape did not specialize the captured device dispatch; that rejected intermediate assembly compiled unrelated operation arms. The final device lambda calls `cooperative_group<Code>` directly.

The drop-in `p42tiny::submit<WG>` accepts and forwards dependency events exactly as `ng::submit`; size/lifetime/device validation remains on the incumbent submission path. Every inherited and generated convolution fixture also gets a `.inplace` clone: argument 4 aliases history argument 1. CPU Core, CPU incumbent, and candidates all read/write the same history bytes. Device timing uses the production `.inplace` fixture, restores input history only once (never uploads the separate output placeholder over it), and snapshots actual aliased output bytes. Pool already reads and updates its retained state through the same slots.

Final offline GEN evidence (`tiny-assembly.json`; static totals, never a latency model):

| Exact operation | range instructions/messages | WG32 instructions/messages | WG256 instructions/messages | SLM/barriers |
|---|---:|---:|---:|---|
| activation | 950/9 | 965/9 | 965/9 | none / none |
| HC mix | 1909/15 | 1921/15 | 1921/15 | none / none |
| moe combine | 620/11 | 632/11 | 632/11 | none / none |
| GDN conv | 707/23 | 723/23 | 723/23 | none / none |
| GDN gated norm | — | 2353/95 | 851/72 | original local tree and barriers retained |
| QSA prepare | — | 1800/287 | 1383/238 | original local tree and barriers retained |
| QSA pool | — | 1697/143 | 801/96 | original local tree and barriers retained |

Range compiler-wrapper entries are also retained; direct-body counts above are not a claim that the wrapper is bypassed. Direct candidates have zero SLM pointer arguments/messages and zero barriers. Cooperative captures occupy192bytes versus208bytes direct (236with the range wrapper). The unchanged dynamic incumbent emits12241/18622 static instructions across its two GEN variants, 122/282SLM messages and21504private bytes. Specializing the cooperative operation leaves only801–2353instructions and128private bytes, while preserving its local reduction and barriers. Whole-dispatch versus per-operation totals establish emitted specialization, not dynamic speedup. The card decides.
