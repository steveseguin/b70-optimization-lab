# Round 5 — exact expanded weights and the output head

CPU preparation for the Unsloth UD-IQ3_XXS **quantized compressed version**.
No GPU executable, server, Docker, systemd, device node or port was used.
No download or write to the model store. Device execution belongs to the
coordinator. This is an operator candidate, not an integrated model runtime,
new quality decision, measured speedup or publication.

## What the receipts actually establish

Packet9's [raw timing receipt](../packet9-kopt4/receipts-card3-20261011/timing.json)
gives a GEMV-only sequential two-card projection of **60.423 ms / 16.550 tok/s**
for its split-expert mode, versus the separate 28.49 tok/s reference. Its
packed-byte 590 GB/s lower bound is 8.392 ms, reciprocal ceiling 119.16 tok/s.
Those comparisons do not establish full-model output agreement.

Two prose errors matter for this round. The [census](../../../qwen38-flash-next-ud-iq3xxs-b70/packet1/tensor-census.json)
identifies the fast router as **F32**, not F16. It identifies `output.weight`
as **Q6_K, 248320 rows × K2560, 521,472,000 packed bytes**, not F16/BF16 or
1.27 GB. Head plus final HC reads 528,435,200 packed bytes; packet9's 5.466 ms
whole-sequence result therefore represents about 96.7 GB/s, not 232 GB/s.
The round2/3 router's 289–376 GB/s is evidence that simpler arithmetic can
stream faster; it does not guarantee expanded-int8 throughput.

## Exact format, version 1

[expanded.hpp](expanded.hpp) is our header-only C++ load-time transform and
shared CPU/device scalar contract. [expansion.py](expansion.py) is the independent
Python reference using [dequant.py](../../stage1/packet1b/loaders/dequant.py)
as truth. Normative tables retain the [format-data attribution and MIT license](../../stage1/packet1b/loaders/FORMAT.md).
No upstream runtime code is used as a base.

Every row contains three contiguous regions, in this order:

1. **Codes:** K int8 two's-complement decoded integers, except Q3_K has K/2
   bytes of signed four-bit nibbles, low nibble first in contiguous element
   order. Q3 values are -4 through 3; three bits suffice mathematically, but
   four-bit alignment avoids straddling bytes. Original IQ grid/sign indexing
   and planar K-grid indexing disappear at load time.
2. **Cached scales:** K/group little-endian FP32 values, calculated using the
   exact source equation and rounding after each multiplication. These are
   derived metadata, not a re-quantization. The kernel reads these directly.
3. **Original scale fields:** for each original block, original two F16 bytes
   followed by its scale fields. Q8/IQ4_NL: no extra field; IQ2_S: eight
   original packed scale bytes; IQ3_S: four; Q3_K: twelve; Q6_K: sixteen signed
   bytes; IQ4_XS: its six scale bytes. IQ3_XXS stores its eight original scale
   nibble *values* as eight bytes; sign bits have moved into the signed codes.
   This region is retained for auditing and included in residency, but is
   not fetched by GEMV. There is no padding; bytewise scale loads handle
   unaligned row strides safely. Raw F32/F16/BF16 rows remain unchanged.

The smallest **direct signed integer width** differs from the information
needed for a codebook index. IQ2 magnitudes are {8,25,43}, not {1,3,5}; IQ3_S
has odd magnitudes 1..15; IQ3_XXS has {4,12,20,28,36,44,52,62}. IQ4 levels span
-127..113. Their complete signed-value sets need 7, 5, 7 and 8 direct bits.
An index+sign could use 3 bits for IQ2, 4 for IQ3_S/XXS, or 4 for IQ4, but
would require another lookup or integer reconstruction. This candidate chooses
byte integers to remove that work. It does not claim minimum entropy storage.

| Grid | Minimum direct bits | Stored code bits | Scale group | Resident B/weight | Expansion | Fetched B/weight |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Q8_0 | 8 | 8 | 32 | 1.187500 | 1.1176× | 1.125 |
| Q3_K | 3 | 4 | 16 | 0.804688 | 1.8727× | 0.750 |
| Q6_K | 6 | 8 | 16 | 1.320312 | 1.6095× | 1.250 |
| IQ3_XXS | 7 | 8 | 32 | 1.164062 | 3.0408× | 1.125 |
| IQ4_NL | 8 | 8 | 32 | 1.187500 | 2.1111× | 1.125 |
| IQ3_S | 5 | 8 | 32 | 1.148438 | 2.6727× | 1.125 |
| IQ2_S | 7 | 8 | 16 | 1.289062 | 4.0244× | 1.250 |
| IQ4_XS | 8 | 8 | 32 | 1.156250 | 2.1765× | 1.125 |

Resident bytes include both cached FP32 scales and the original scale fields.
For Q6_K, for example, one 256-value row uses 256 + 64 + 18 = 338 bytes instead
of 210; GEMV reads 320. IQ3_XXS, Q3_K and IQ4_XS are format coverage only,
absent from this checkpoint's production census.

### Arithmetic identity

Load-time caching preserves `(d * subscale) * q` and the IQ half-step
multiplication order exactly. The last weight-scale multiplication still
rounds to FP32. Finite IQ signs can fold into nonzero signed integers without
changing any bit, including signed zero. Infinite IQ scales keep the signed
multiplication. NaN IQ scales preserve
the cached quiet-NaN bits explicitly, matching the packed CPU oracle; see the
[October 11 exactness repair](#october-11-exactness-repair). No F16/BF16 weight shadow,
weight approximation, compressed KV or changed model is introduced.

**One FMA per weight cannot satisfy the requested unchanged FP32 arithmetic.**
A true FMA removes a rounding point. The kernel performs a scale multiply,
then activation multiply, then accumulator add, all separate. Q3 needs one
nibble shift/mask and sign extension; byte formats need signed widening, with
no codebook. Builds use `-fno-fast-math -ffp-contract=off
-fdenormal-fp-math=ieee`. Exactness compares FP32 bits and final 16-bit bits.

SG32 assigns eight consecutive columns per lane and advances 256 columns.
It uses the unchanged adjacent-lane tree. Split4 uses contiguous 256-column
tile ranges and `(p0+p1)+(p2+p3)` in 16 bytes of workgroup local memory, in the
same launch. Each order is checked against the **matching packed GGUF-path
order** from packet7/9; split4 is not asserted identical to unsplit SG32 or
the original packet2 reduction. Full-model CPU-oracle/token parity remains
required. Exact dequantized values alone do not prove full-model output parity.

## Residency policy

The existing placement keeps embedding and PLE lookup off device and includes
both copies of replicated HC projections. No MTP is included. The complete
[32K one-user reserve](../../../qwen38-flash-next-ud-iq3xxs-b70/packet1/memory-admission.json)
is **8,154,079,512 bytes**: full 16-bit KV/state, index, rollback, scratch,
graph/static buffers, staging and driver/allocator allowances.
[analysis.py](analysis.py) recomputes every tensor and replica into
[analysis.json](analysis.json); decimal GB below.

| Policy | Total weight expansion | Weights GB | Weights + reserve GB | Under 64 decimal GB? |
| --- | ---: | ---: | ---: | --- |
| packed | 1.0000× | 53.304620 | 61.458699 | yes, arithmetic only |
| dense | 1.0354× | 55.193940 | 63.348020 | yes, arithmetic only |
| dense_plus_iq2_experts | 2.4685× | 131.582702 | 139.736782 | no |
| all_resident_quantized | 2.9632× | 157.954388 | 166.108468 | no |

**Use dense-only expansion.** Dense includes the head, shared experts, HC,
GDN/QSA and PLE projections; all 512 routed experts per layer stay packed.
Expanding all IQ2_S experts does not fit. There is no routing-dependent choice
or dropped expert. The off-device 29.322 GB file backing stays unchanged.

For an explicit 24/24 sequential layer split, with replicated HC on both
cards and head on card 2, weights are **27,285,635,840 / 27,908,304,640 bytes**.
Splitting the estimated reserve equally gives **31,362,675,596 /
31,985,344,396 bytes**. This even fits a conservative 32,000,000,000 bytes/card
on paper, narrowly on card 2. The historical usable two-card capacity is
68,484,595,712 bytes, leaving 5,136,575,720 bytes in aggregate. No device
capacity was queried. Reserve distribution, actual native peaks, prefill and
host staging remain unmeasured: these are arithmetic checks, not a native fit
verdict. Bounded row/slab expansion must replace packed rows as loading
progresses; keeping a second full packed model is outside this budget.

## Kernels, head and dispatch

[kernels.cpp](kernels.cpp) implements SG32 and local split4 for every expanded
format. Each workgroup has four subgroups: four rows in SG32 or one row split
four ways. No global partial buffer or second reduction launch is required.
The full head exposes 62,080 SG32 groups or 248,320 split4 groups. Both are
candidates; speed determines the choice only after each passes its oracle.

[dispatch.json](dispatch.json) binds the inherited 25-key table. Dense shapes
keep its SG32/split4 arithmetic choice; raw matrices keep their old kernels.
Both head orders are timed explicitly. Routed gate/up, down and ordered
weighted sum use packet9's packed fused **SG32** path in both modes, because
the measured block was faster than split4. The modes differ only in the head
split; repeated layer timings are controls, not independent optimizations.
All bindings use Arena ownership, checked bounds and forbidden writable aliases.

The expanded head occupies **839,321,600 bytes**, of which **794,624,000 bytes**
are code and cached-scale traffic. Predicted head time is **2.13–2.76 ms**
at a hypothetical 376–290 GB/s plus a 17 µs allowance. This meets the <=3 ms
target in that scenario; the device result may not.

## Projection — unmeasured scenarios

For every dense job: `fetched bytes / assumed GB/s + 0.017 ms × native passes`.
The 17 µs term is deliberately conservative planning allowance, **not a
measured empty-launch cost**; it may double-count some useful execution time.
Packed experts use the median of the two packet9 SG32 fused-block receipts
(~0.298 ms). Dense byte counts use expanded codes/scales, not archived metadata.
No memory-bandwidth doubling is applied to two sequential cards.

| GEMV-only item | At 376 GB/s | At 290 GB/s |
| --- | ---: | ---: |
| Ordinary GDN, 25 launches | 0.937 ms | 1.015 ms |
| PLE GDN, 27 launches | 1.068 ms | 1.176 ms |
| Upgraded GDN, 25 launches | 0.920 ms | 0.994 ms |
| QSA, 26 launches | 0.933 ms | 1.006 ms |
| Head + final HC, 3 launches | 2.184 ms | 2.817 ms |
| 34 ordinary + PLE + upgraded + 12 QSA + head | 47.219 ms/token | 51.565 ms/token |
| Reciprocal projection | **21.18 tok/s** | **19.39 tok/s** |

The earlier 119.16 tok/s ceiling applies to the **old packed bytes**, not this
larger representation. These scenarios still fall below the 28.49 reference.
Expert decoding and small dense-operation costs remain larger levers after
this test. None of these numbers is a measured context point, model throughput,
quality result or public benchmark. Nonlinear operators, state/KV, transfers,
host lookup latency and real dependency scheduling remain outside the projection.

## Tests and two coordinator commands

[build-receipt.json](build-receipt.json) retains CPU counts, fresh-process
repeat, compiler flags, dependency checks and every source/fixture/binary hash.
The repaired preparation runs 36 Python protocol/bounds tests; 27 hash-matched
packet2 fixtures; **4,394,270 value/row comparisons including 5,790 rows**;
eight independent Python format cases spanning all codebook entries and special
half scales; **1,024 specialized and runtime-type format GEMV row checks**
against materialized and packed CPU oracles; and **108 MockDevice dense cases**
through the shared allocation,
upload, launch, FP32/16-bit comparison and release path. Both SYCL targets are
compiled only. The host executable is checked for absence of device libraries.

The coordinator's exactness gate contains **126 cases**, 63 per order:
54 changed-input fixture GEMVs; eight format cases checking decoded FP32 bits
and GEMV FP32/BF16 bits, including IQ4_XS; and one full 248320×2560 head using
four exact stored head rows tiled to that geometry. Timing likewise uses small
read-only source samples tiled to real shapes, not a full-payload model run.
One warmup and 20 event samples, per-operation head timing, full GEMV sequences,
nonempty packed expert-block summaries and two fresh owners per representative
shape are required. A matching successful hash-bound exactness receipt is
mandatory. All native events and queue gaps count. Prepared down inputs do
not claim the missing SiLU/product dependency is executed.

After scratch cleanup, the coordinator recreates CPU inputs first:

```bash
P=experiments/own-xpu-runtime/stage2/packet10-kopt5
nice -n 19 ionice -c 3 env OMP_NUM_THREADS=2 python3 -B "$P/validate.py" --keep-build
```

In the installed oneAPI environment, after independent card-3 health and
ownership admission, run these **two commands**, once each, in order:

```bash
nice -n 19 ionice -c 3 env OMP_NUM_THREADS=2 python3 -B "$P/tests/device_window.py" --authorized-device-window --card 3 --output "$P/build/card3-exactness-repair1"
nice -n 19 ionice -c 3 env OMP_NUM_THREADS=2 python3 -B "$P/tests/device_timing.py" --authorized-device-window --card 3 --exactness "$P/build/card3-exactness-repair1/window.json" --output "$P/build/card3-timing-repair1"
```

The inherited cooperative watcher retains journal evidence, stops on faults,
latches unsafe/incomplete windows, never retries, and preserves ownership if
drain fails. These commands do not replace coordinator admission. Timing
comparisons are warm operator diagnostics; full-model lossless and realistic
cold-prompt gates remain separate. No candidate is enabled as a runtime default.
[Preparation closeout](CLOSEOUT.md) and [closed assumptions](DO-NOT-REPEAT.md).

## October 11 exactness repair

The coordinator's **05:18:46 UTC** card-3 window failed after 57 completed
checks in `expanded_sg32`, at `IQ3_S/format GEMV FP32`. This was a real
byte mismatch: the latch and exactness classification were correct. The
[original receipts](receipts-card3-exactness-20261011/card3-exactness/window.json)
record no kernel faults and clean teardown. **They did not retain the device
row or either differing value.** No exact device row or delta can be recovered
from those receipts; the CPU reproduction below is separately labeled.

The exact saved [IQ3_S format fixture](receipts-card3-exactness-20261011/IQ3_S.case)
is 64 rows × 256 columns, with BF16 inputs `float(i % 31 - 15) / 32`.
An optimized, compile-time IQ3_S CPU path reproduces a failure on **zero-based
row 23, SG32**, whose F16 scale is `0xfe00` (negative quiet NaN): expanded
FP32 is **`0x7fc00000`**, while packed and Python-materialized CPU results are
**`0xffc00000`**. Their little-endian bytes are `00 00 c0 7f` and
`00 00 c0 ff`; XOR is `0x80000000`. This is a NaN sign mismatch, so a finite
numeric delta or ULP distance is not meaningful. The
[repair evidence](exactness-repair.json) retains the failing and passing CPU
runs, compiler flags, assembly excerpt and original receipt hashes.

**Root cause:** the exceptional-scale branch expressed sign application as
`(scale * abs(q)) * (q < 0 ? -1.0f : 1.0f)`. With compile-time specialization,
icpx 2026.0 lowers the conditional sign multiplication to a sign-bit XOR.
That flips a NaN's sign; the packed CPU multiplication propagates its sign.
The saved assembly shows the conditional `xorps` with `0x80000000`. Ordinary
finite sign folding is still exact. Both host and SYCL compilation already
used `-fno-fast-math -ffp-contract=off -fdenormal-fp-math=ieee`, with no
`-fp-model` override. Disabling FMA alone did not prevent this transformation.

The other suspected mechanisms were checked: IQ3_S caches
`d * (1 + 2 * nibble)` and then multiplies the code, matching the packed
order; low/high nibbles select consecutive 32-weight groups; cached scales
are read little-endian; and lane, adjacent-lane and split trees match their
packed oracles. The failed format fixture has one complete 256-weight block
per row, so it has no partial chunk. Earlier CPU geometry checks still cover
long rows and short raw/32-weight-format tails.

**Fix:** return the cached quiet-NaN bits explicitly for the three IQ formats
that shared the faulty branch. Keep finite and infinite signed-scale
multiplication, all packed bytes, scale order, and reduction trees unchanged.
No comparison tolerance, NaN canonicalization of results, or oracle change
was introduced. The same regression fails against the original implementation
and passes with the fix. Device confirmation remains pending; CPU evidence
cannot prove which row failed in the original device run.

**Test gap closed:** the previous CPU format checks compared expansion bytes
and individual decoded values with a runtime type. They never accumulated
these special-scale format fixtures through the compile-time-specialized
consumer used by the device kernel. `tests/format_regression.hpp` now runs
all eight exact format fixtures through that specialization and the runtime
expanded path, checking FP32/BF16 bits against the materialized Python values
and the packed SG32/split4 oracle (IQ4_XS has no packed packet7 path). The
specialization intentionally inlines the scalar consumer: merely wrapping
`expanded::row` in a template can still call the runtime-type function and
miss the defect. Mock readback and Python receipt tests ensure first-mismatch
indices, raw words and deltas survive into the native error, window and latch.
For GEMV, the reported `element` is the zero-based output row; for dequant it
is the flattened weight index.

The original `build/card3-exactness` and `build/device-fault-latch.json` remain
untouched. A byte-verified copy is also retained under
`receipts-card3-exactness-20261011/`, including the coordinator's build receipt.
CPU validation uses `validate.py --build-dir "$P/build/repair-validation"`,
which deletes only that fresh scratch directory. Alternate build roots cannot
be used for device admission or to bypass the original latch.

Before the two commands above, the coordinator must review/archive the old
build and latch with its recovery receipt, then recreate the default build
using `validate.py --keep-build` and admit card 3. The fresh output names avoid
overwriting the failed window. Timing requires the new exactness pass; the
old failure remains part of this packet's record.

## Device results — card 3, 2026-10-11 06:0x UTC (boot 13858eef), after the NaN-sign repair

Exactness: all expanded-format cases PASS (expanded_sg32, expanded_split4) and the
head GEMV; zero kernel fault lines. Receipts: [receipts-card3-20261011/](receipts-card3-20261011/)
(first run's failure evidence in receipts-card3-20261011-run1/).

| GEMV-only projection, two-card sequential | GDN ms | QSA ms | head+final HC ms | ms/token | tok/s |
| --- | ---: | ---: | ---: | ---: | ---: |
| round 4 (packed, fused experts) | 1.14 | 1.07 | 5.47 | 60.4 | 16.5 |
| round 5 expanded_sg32 | 0.89 | 0.77 | **2.19** | 43.3 | 23.1 |
| round 5 expanded_split4 | **0.78** | 0.77 | 3.27 | 41.0 | **24.4** |
| reference llama.cpp (two cards) | | | | 35.1 | 28.49 |
| 590 GB/s ceiling | | | | 8.4 | 119 |

Dense-only exact expansion (1.035x bytes, fits two cards) plus the fast head
cut the projection from 60.4 to about 41 ms/token. Mixing the best of both
variants (split4 layers, sg32 head) would be ~39.9 ms = ~25 tok/s GEMV-only.
