# Source-derived byte model

`byte_model.py` returns read/write bytes for one complete class invocation.
Its formula structure is credited to the lab's packet67 `audit.py`, rechecked
against the copied production sources and updated for packet107's selection.
**No packet67 or packet77 timings are used.** Tensor shapes/types come from
`../packet34-replay-bench/directory.tsv`, pinned in `roofline.json`; that is the
same metadata the complete-layer fixture loads, not a model-payload read.

These are useful-byte floors. They count distinct useful global data within
an operator phase; global producer/consumer intermediates count both writes
and reads. They deliberately do not claim to count every issued load or memory
transaction. Repeated activation loads, shared scales, index reads, codebook
traffic, control words, line overfetch and cache misses need counters to resolve.
A small effective GB/s does not prove a bandwidth bottleneck. In particular,
attention's repeated loads and routing's comparisons can dominate its useful
bytes. The copy roofline is a comparison reference, not the compute roofline.

Weights use the **loaded format**, not GGUF file size or allocation stride:

- Expanded Q6: `rows × (K + 4K/16)` useful code/scale bytes. The retained
  `18K/256` metadata bytes in each expanded row are not loaded by the fast
  dense loop. At K2560 this is 3,200 useful bytes with 3,380 storage stride.
- Expanded Q8: `rows × (K + 4K/32)` useful code/scale bytes; the retained
  original half-scale metadata is likewise excluded from the read floor.
- BF16/F32 matrices: element count × 2/4 bytes.
- Selected IQ2 gate/up: **840 bytes per K2560 row** under E1, rather than the
  old 820-byte packed/plane row. Two banks × ten experts × 640 rows × 840 =
  **10,752,000 weight bytes/call**. The scale cache is exact FP32, not KV.
- Selected IQ4 down: K640/2 code bytes + 2×K640/32 half-scales = 360 bytes/row;
  ten experts × 2,560 rows = 9,216,000 weight bytes/call.

The physical derivations are in [expanded.hpp](../packet10-kopt5/expanded.hpp),
[planar layout](p49b_gemv.hpp), [E1 stride](p90_layout.hpp),
[E1 loads](p90_expert.hpp), [dense loops](p49d_small.hpp),
[dispatch](dispatch-speed6.json) and [selection](selection.json).

Below `W` is the useful weight read derived from those rules, `N` is occupied
context, `M = 4 min(floor(N/4),512) + N mod 4`, and
`T = 24 ceil(M/32) × 258 × 4` is active attention partial scratch bytes.
The numerical formulas apply to ordinary layer3 QSA/layer4 GDN, not exceptional
layer0 types. Decimal byte counts are intentional.

| Class | Read bytes | Write bytes | Current source boundary |
| --- | --- | --- | --- |
| qsa.qgate / k / v / iq | W + 2K | 2 rows | main.cpp `linear`, p33/p28 dense dispatch |
| qsa.ik | W + 2K + 16 rows | 2 rows + 16 rows | split4 producer and finish |
| attention | W + 12,288 + 40,960 + 20,480 + 8 | 5,120 + 40,960 + 20,480 | p39/p49c split4 projection plus stream combine |
| hc.a.norm / hc.f.norm | 40,960 gain + 20,480 streams | 20,480 norm + 1,280 scratch | p60 norm, unique streams floor; tiled rereads excluded |
| hc.a.low / hc.f.low | W(down) + W(inject) + 20,480 norm | 640 low + 640 activation + 8 inject + 64 partials | p60 low/inject tuple |
| hc.a.gate / hc.f.gate | W(up) + 640 activation + 20,480 norm | 20,480 gate + 5,120 mix | p60/p73 wide gate/mix |
| small.ffn.q6 | W(router, shared gate, shared up, shared router) + 5,120 input | 2×(512+640+640+1) | p49d_small.hpp four-member tuple |
| expsgate | 10,752,000 + 5,120 input + 120 routes | 25,600 gate/up + 80 status | p90_expert.hpp |
| expsact | 25,600 gate/up | 12,800 activation | p42 tiny activation |
| expsdown | 9,216,000 + 12,800 input + 120 routes | 51,200 output + 40 status | p49d IQ4 down |
| shexpact | 2,560 gate/up | 1,280 activation | p42 tiny activation |
| shexpdown | W + 1,280 input | 5,120 output | p33 dense segment |
| route | 4,392 | 2,664 | p78_route.hpp; route42.hpp |
| moe | 51,200 experts + 40 probabilities + 5,120 shared + 4 one + 2 shared gate + 5,120 mixture | 10,240 mixture/output | main.cpp mixture then shared blend |
| ffn.combine | 20,480 streams + 5,120 branch + 8 inject | 20,480 streams | specialised combine |
| qsa.prepare | 26,624 inputs + 2,560 gains + 128 RoPE | 26,624 | preparation preserves full16 boundaries |
| qsa.pool | 2,304 inputs + 768 prior raw + 128 RoPE + 512 gain | 2,304 append + 256 pooled | fourth-token path at both measured positions |
| qsa.select | 1,024 query + floor(N/4)×(256 pooled + 4 score) | 8,204 IDs + floor(N/4)×4 score | round2.hpp two stages; repeated rank scans excluded |
| qsa.attention | 24,576 Q/gate + 2,048M KV + 4(M+1) IDs + T partials + 4 count | 12,288 output + T partials + 4 count | p49_qsa_kernel.hpp admit/tiles/combine |
| gdn.qkv / gdn.z | W + 5,120 | 20,480 / 12,288 | p33 dense segment |
| small.gdn.ab | 983,040 alpha/beta weights + 5,120 input | 192 | small_gemv.cpp tuple |
| gdn.conv | 163,840 weights + 20,480 input + 61,440 history | 20,480 output + 61,440 history | p42/parallel conv |
| gdn.recurrence | 384 weights + 20,480 conv + 192 gates + 1,572,864 state | 12,288 output + 1,572,864 state | p82b_recurrence.hpp current rec-both-plus |
| gdn.gated | 512 gain + 24,576 inputs | 12,288 output | production norm/gate |

Route read breakdown: 2×1,024 input + 128 maxima + 128 sums + 2,048 exponentials
+ 40 selected probabilities. Writes: 128 maxima + 128 sums + 2,048 exponentials
+ 40 IDs + 40 probabilities + 240 descriptors + 40 renormalized probabilities.
The same useful arrays remain after route-fast packs its work into one event.
The local bitonic network is not global traffic; its instruction/barrier cost
is reflected in measured time, not invented DRAM bytes.

QSA attention's actual logical KV loads are `24 × M × 256 × 2 × 2`, twelve
times the unique K/V footprint above because twelve query heads share each KV
head. Packet107 local-sharing already lost; the useful-byte floor is no reason
to repeat it. The table does not confuse these logical requests with DRAM.

Each class appears once per sampled complete layer, although a class can have
multiple events. Common classes have separate QSA and GDN timings. The refresh
script fails on an unknown measured class rather than silently dropping it.
