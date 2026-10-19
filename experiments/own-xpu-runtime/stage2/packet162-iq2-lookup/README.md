# Packet162 — remove the IQ2 grid dependency

**Decision: close these two implementations before device preparation.**
An exact 11-bit integer encoding fits the modeled rank-1 arena, but neither
implementation passes every CPU byte check. Finite cases and the actual native
host kernel's final outputs/status pass; auxiliary NaN chain/tree checks differ.
No device time, model speed, build-brief qualification or READY is claimed.
[Closeout](CLOSEOUT.md), [negative index](DO-NOT-REPEAT.md),
[CPU evidence](evidence/cpu-proof.json), [decision](evidence/decision.json).

The baseline is bundle8, quantized compressed Unsloth UD-IQ3_XXS,
`iq3-p49-split32-v1`, full BF16 KV/state. This is a new lab-authored CPU
experiment. It does not edit the baseline, any old packet, screen, ops or queue.
The normative grid comes from the lab's credited format tables in
`packet2/kernels/grids.hpp`; it is not a new model quantization.

## Current dependency, with source locations

The selected `exp-halfcache+down-tile16` uses
[packet136's E1 gate/up](../packet136-record-bundle/p90_expert.hpp).
Its SHA-256 and the memory plan are pinned in [analysis.json](evidence/analysis.json).

1. Lines 55–65: per physical lane and 256-weight step, load four code/sign
   words, two high-index bytes, two scale bytes and one cached FP32 half scale.
   Four physical lanes cover a row's 32 logical chains. Each lane owns eight.
2. Lines 35–37: combine one code byte with two high bits into a 10-bit index;
   read `iq2_words[2*index]` and `[2*index+1]`.
3. Lines 40–42: extract eight byte magnitudes; apply inline sign bits and the
   unchanged scale expression. There is **no separate sign-table load**.
4. Lines 67–85: multiply by the original BF16 inputs, add in the original
   per-chain order, then use the unchanged adjacent tree and BF16 store.

The two word reads are parallel operands at the same dependency level, not
two serial cache misses. Packet99's linked BMG evidence shows one
`load.ugm.d32x2.a64` message per eight weights. It is global constant data,
not a register-resident table. The chain is **packed metadata load → index
arithmetic → grid load → magnitude/sign/scale → product/add**. E1 removes
FP16 scale conversion, not this dependent grid stage.

| Coverage, one stream unless noted | Logical grid entries / dependent messages | 32-bit grid word accesses |
| --- | ---: | ---: |
| 8 weights | 1 | 2 |
| 16 weights | 2 | 4 |
| 256 weights | 32 | 64 |
| K2560 row | 320 | 640 |
| Gate **and** up, ten experts × 640 rows | 4,096,000 | 8,192,000 |
| 24 such layers | 98,304,000 | 196,608,000 |

Amortized counts are 1/8 grid messages or 1/4 scalar word accesses per weight.
These are logical counts; they are not DRAM transactions or unique bytes.
See the existing [linked diagnosis](../packet99-iq2-grid/DIAGNOSIS.md).

## What was tested

**L0: straight-line Boolean decoding, unchanged 840-byte rows.** Build sixteen
Boolean output planes for the eight ternary magnitudes from the ten index
bits. Reduced decision DAGs share identical subexpressions. Eleven fixed bit
orders were evaluated across the complete grid, not model prompts. The best
has **1,288 nodes**, nominally 3,864 XOR/AND operations, before magnitude,
sign and FP32 work. This replaces the indexed table at source level with
integer logic and no weight-memory growth. It does not relocate or compact
the old table. [Generated circuit](logic_grid.hpp), [candidate](candidate.hpp).
It is exact for all 1,024 grid entries but far too much replacement work to
support a 15% kernel-win forecast. CPU full-shape timings are about 22–40×
production, diagnostic only. No claim about actual Xe lowering is made.

**L1: 11-bit enumerative supergrid, 880-byte rows.** This is a distinct
immutable-weight recoding, not packet140's five-byte cell. The original grid
uses magnitudes {8,25,43}. Its sixteen observed pairs of counts of 25 and 43
have **2,054 possible coordinate permutations**. Remove six permutations
that are absent from the original grid: exactly 2,048 possibilities remain.
Each original 10-bit grid index can therefore be expanded into 11 bits.
At load time, replace its low ten bits in the existing code/high planes and
append one bit per eight weights (40 bytes per K2560 row). Signs, scales and
cached FP32 half scales retain their original bits and offsets.

The kernel undoes the six holes with threshold additions, identifies the
count pair, un-ranks the two coordinate combinations with immediate binomial
coefficients, and reconstructs `8 + 17*d + (d>>1)` for ternary digit d.
No original-grid lookup is required by this algorithm. The integer mapping
is exhaustively checked against all 1,024 original words. The generated
source is not proof that a device compiler would avoid synthesized tables,
scratch or excessive branches; linked lowering would still be required.
[Decoder](enum_grid.hpp), [candidate](enum_candidate.hpp),
[generator and checks](analyze.py).

The candidate preserves V8/WG64/SG32, all 32 sums, independent gate/up metadata,
scale multiplication order, signs, adjacent reduction and BF16 boundaries.
Its source changes are only integer grid reconstruction, the extra bit read,
and the row stride. Arithmetic equality alone is not a compiler byte proof.

### Memory accounting

For **each** rank, `24 × 512 × 640 × 2 × 40 = 629,145,600` additional bytes.
Rank 1's modeled arena goes from 31,425,985,242 to **32,055,130,842** bytes,
leaving **157,123,878 bytes** under the unchanged 30 GiB limit. Rank 0 also
fits this steady-state calculation. This is **not startup admission**: loader
temporaries, allocator alignment and actual device preparation remain untested.
In particular, retaining an old complete 275 MB bank while allocating its
replacement at the end would exceed that final 157 MB allowance. A future
loader must prepare final rows directly from bounded host chunks at initial
load, and prove the real peak; do not quietly add both representations.

Other straightforward lookup-free representations do not fit all layers:

| Magnitude representation per eight weights; signs/scales retained | Extra bytes/rank | Whole layers fitting rank 1 |
| --- | ---: | ---: |
| Eight unsigned bytes, 64 bits | 33,973,862,400 | 0 |
| Eight two-bit digits, 16 bits | 3,774,873,600 | 4 |
| Radix-3 number, 13 bits | 1,887,436,800 | 9 |
| Even-middle-parity supergrid, 12 bits | 1,258,291,200 | 14 |
| L1 enumerative supergrid, 11 bits | 629,145,600 | 24 |

The grid's number of middle magnitudes is always even, so the 12-bit
supergrid contains `(3^8+1)/2 = 3,281` words. These are exact integer
representations, not lower-precision weights. Partial-layer coverage cannot
be treated as full-path savings. Uniform-cost fractional-coverage ceilings in
analysis.json are calculations, not evidence of which actual layers are hot.
No subset cache or hot-layer selection is proposed.

## CPU result and decision

The [harness](cpu.cpp) calls the frozen production `wide_chains` and actual
`p90exp::Kernel::run` alongside private candidates. Both GNU and Intel test
K2560, ten experts, 640 rows each, two independent streams; all 32 raw FP32
chains and final BF16 are compared. The complete native host operation also
checks output/status/error bytes with ordinary routes, an invalid expert and
a partial row range. Each candidate additionally passes **2,097,152 signed
decoded-float checks**, covering every index/sign mask, all scale nibbles and
a deterministic rotation of twelve finite half-scale patterns.

Both finite fixtures pass all comparisons. The third fixture includes signed
zeros, subnormals, infinities and multiple NaN payloads in activations:

| Check | GNU | Intel |
| --- | --- | --- |
| Actual native host output/status, both candidates, all three fixtures and invalid/tail routes | exact | exact |
| L0 auxiliary raw chains | exact | 70,383 differing FP32 words |
| L1 auxiliary raw chains | exact | 70,383 differing FP32 words |
| L1 auxiliary chain-to-BF16 tree | 2,114 differing BF16 words | exact |

The first Intel chain difference is `ffc00000` versus `ffc20000`; the first
GNU auxiliary tree difference is `ffc2` versus `ffc0`. These are NaN payload
differences. Final native-host equality does **not** erase the independent
raw-chain requirement. Conversely, this does not prove a changed model token
or a native production-output regression: the differences were observed in
separately instantiated diagnostic call sites. Their compiler/context cause
has not been isolated. No canonicalization or weakened byte comparison is used.

The L1 finite CPU timing ratio is about **4.1× GNU / 4.9× Intel** in this
single diagnostic execution. Its branches, combinatorial unranking and new
metadata work replace the removed dependency. CPU timing cannot pass or fail
the required **device ≤0.85×** timing gate. The current complete strict CPU
gate is false, device timing is absent, and there is no supported qualifying
speed projection. Thus neither current implementation is admitted to device
preparation. The encoding result is retained for a materially shorter decoder
with complete byte parity, not called impossible or lossy model arithmetic.

Packet141's 1.456 ms is a **diagnostic reading**: its analyzer refused the
touch-count evidence; the coordinator separately summed raw events. Packet86's
~0.57 ms bound is a non-exact ablation on an older composition. They establish
the opportunity, not a guaranteed lossless saving. At those provisional costs,
the micro gate needs 0.2184 ms/half removed, or 38.3% of the entire ablation
pool after paying replacement costs. A +3% record projection still needs
the packet160 critical-path replay and real transfer evidence. We award none.

## Existing closures carried forward

| Excluded lever | Binding evidence |
| --- | --- |
| Table relocation/compaction | [packet99 DNR](../packet99-iq2-grid/DO-NOT-REPEAT.md); all six IQ2 micro arms fail, including compact-global+halfcache 1.2608× |
| Grid-word prefetch | [packet95 DNR](../packet95-expert-dequant/DO-NOT-REPEAT.md) and later [packet140 inventory](../packet140-body-lever/ANALYSIS.md); E3 closed |
| Lookup batching/shared input | [packet102 DNR](../packet102-iq2-ilp/DO-NOT-REPEAT.md); 0.9811×, 1.0016×, 1.0331×, none at ≤0.85 |
| Gate/up tile16, including 104b | [packet104 DNR](../packet104-tile-transpose/DO-NOT-REPEAT.md); 0.893× micro was not a qualifying pass; no new transpose here |
| Persistent/V16 layouts | [packet53 DNR](../packet53-expert-order/DO-NOT-REPEAT.md), [packet53b DNR](../packet53b-virtual/DO-NOT-REPEAT.md); current V8 mapping retained |
| E1 half cache | Already selected in bundle8, held in both comparisons; [packet90 DNR](../packet90-expert-hc/DO-NOT-REPEAT.md) |
| Five-byte N2 cells | [packet140 DNR](../packet140-body-lever/DO-NOT-REPEAT.md) and its N2 analysis; it leaves the grid lookup in place |

[CPU reproduction/proposal](CPU-MICRO.md),
[conditional device micro proposal](DEVICE-MICRO-PROPOSAL.md),
[retention](RETENTION.md). The device document is deliberately **not a runnable
queue proposal** because the current candidate fails the CPU admission gate.
