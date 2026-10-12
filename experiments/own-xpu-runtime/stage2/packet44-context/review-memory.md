# Independent memory arithmetic review

CPU-only source/receipt review. No device was opened or discovered. No device
binary ran. The existing 24/24 layer placement fits all three capacities with
full BF16 cache storage and at least 1,500,000,000 allocation bytes free. No
layer move or precision change is required.

## Evidence and units

All numbers are bytes (decimal GB only when explicitly stated). Physical card
capacity is 34,242,297,856. Subsequent inspection of packet38's ignored build
tree closed the initial rank0 uncertainty: all three completed WS/W2m-native/
W2s-native windows have an identical **27,253,499,452-byte rank0 live owner
allocation census**. W2s-native's rank1 target census is **27,854,569,876 bytes**.
WS and W2m-native rank1 are both **31,199,840,970 bytes** including exactly
**3,345,271,094 draft bytes**. Removing draft allocations produces an identical
label/size/category/lifetime inventory to the W2s rank1 census.

Every census's live device allocation sum equals its recorded total. All six
rank launch records specify context 256, resident memory and the prepared host
path. Their completed native receipts pass arithmetic identity
`iq3-p17-detmath-v2` and safe teardown. All three windows bind the same target
binary and measured dispatch. This is inspection of historical device evidence;
**no packet44 device ran**.

`memory-plan.json` now contains hash-bound metadata for all six censuses plus
15 deduplicated, byte-exact gzip/base64 source snapshots: three unique censuses,
six launches, three native rank receipts and three window receipts. Each archive
has original and compressed SHA256 and original byte length. The generator
verifies every archive and checks the census/launch/native/window relationships.
A clean clone can recover the exact evidence without the original ignored tree.

The original admission limits are deliberately preserved by explicit reserves:
**46,500,548 bytes on rank0** and **1,228,800 bytes on rank1**. These are planning
reserves, not observed allocations. The latter is the difference between the old
flat rank1 ledger and the actual rank1 census. The former preserves the previous
27.3 GB rank0 ceiling. Neither reserve represents cache precision loss or changed
placement. The driver-residency figure in packet38's `FUTURE.md` is a different
metric and is not substituted for the owner census.

The draft split remains weights 3,326,953,472, cache 606,208 and fixed
scratch/controls/buffers 17,711,414 at capacity 256.

## Exact cache arithmetic

`packet3/step/plan.hpp:163`–166 allocates keys and values at
`context × kvh × ad`, raw index at `context × id`, and pooled index at
`ceil(context/4) × id`. Real geometry has `kvh=2`, `ad=256`, `id=128`.
BF16 uses two bytes. Per QSA layer, this is:

- Keys: 1,024 × capacity; values: 1,024 × capacity.
- Raw index: 256 × capacity; pooled index: 256 × ceil(capacity/4).
- Sum at the admitted multiples of four: **2,368 × capacity**.

| Capacity | K+V/layer | Raw/layer | Pooled/layer | Total/layer | All 12 target layers | Target plus draft |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 256 | 524,288 | 65,536 | 16,384 | 606,208 | 7,274,496 | 7,880,704 |
| 4,096 | 8,388,608 | 1,048,576 | 262,144 | 9,699,328 | 116,391,936 | 126,091,264 |
| 32,768 | 67,108,864 | 8,388,608 | 2,097,152 | 77,594,624 | 931,135,488 | 1,008,730,112 |

Six target QSA layers belong to each rank. The draft adds one on rank1.
`mtp.hpp:129` borrows the resident target head, so there is no extra device head
allocation. CPU streaming/capture instead adds 839,321,600 bytes, which is
explicitly excluded from this resident-device plan.

## Rollback, scratch and RoPE

`rank.hpp:63`–72 banks GDN/conv state only. The existing rank0 alternate bank
is 29,601,792 bytes and is already part of its supplied allocation base.
`ROLLBACK.md:38`–43 explains QSA append/redo: a speculative half writes only its
new K/V/raw rows, and the new pooled row at a four-token boundary. Redo writes
the same locations. There is no cache-sized shadow allocation. Maximum written
append bytes across six rank0 layers are 6 × (1024+1024+256+256) = 15,360;
these are existing cache slots, not additional memory.

Selection IDs remain 2,051 × 4 = 8,204 bytes per QSA layer. Attention score and
probability workspaces remain 2 × 24 × 2,051 × 4 = 393,792 bytes per owner.
`main.cpp:787`–803 also allocates fixed controls, snapshots, prepared FP32 input,
8 MiB GEMV scratch and 256 MiB operator scratch. These fixed allocations are
already in the target baseline. The draft fixed buffers and scratch are
17,711,414 bytes (`mtp.hpp:117`–118). The host pinned copy slab is 4 MiB per
rank and is not device allocation memory.

The new global RoPE table is 32,768 × 128 = 4,194,304 bytes per rank, replacing
4,096 × 128 = 524,288. Therefore **3,670,016 extra bytes per rank at every
capacity** are included. The draft borrows the target's RoPE table.

## Exact modeled allocations and preserved admission limits

The modeled allocations use the exact historical C256 baseline plus the exact
cache and global RoPE growth. They are allocation calculations for the new
capacities, not new device measurements. Adding the explicit reserve gives the
unchanged admission ceiling consumed by `memory_gate.py`.

| Capacity | Rank | Modeled target | Draft | Modeled total | Reserve | Admission ceiling | Free after ceiling |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 256 | 0 | 27,257,169,468 | 0 | 27,257,169,468 | 46,500,548 | 27,303,670,016 | 6,938,627,840 |
| 256 | 1 | 27,858,239,892 | 3,345,271,094 | 31,203,510,986 | 1,228,800 | 31,204,739,786 | 3,037,558,070 |
| 4,096 | 0 | 27,311,728,188 | 0 | 27,311,728,188 | 46,500,548 | 27,358,228,736 | 6,884,069,120 |
| 4,096 | 1 | 27,912,798,612 | 3,354,364,214 | 31,267,162,826 | 1,228,800 | 31,268,391,626 | 2,973,906,230 |
| 32,768 | 0 | 27,719,099,964 | 0 | 27,719,099,964 | 46,500,548 | 27,765,600,512 | 6,476,697,344 |
| 32,768 | 1 | 28,320,170,388 | 3,422,259,510 | 31,742,429,898 | 1,228,800 | 31,743,658,698 | 2,498,639,158 |

Rank1 at 32,768 has 2,499,867,958 modeled free bytes before its explicit
1,228,800-byte reserve. The preserved admission ceiling leaves 2,498,639,158
bytes, clearing the requested allocation floor by 998,639,158 bytes.
Driver overhead and actual residency remain device-window checks; this review
does not measure either. Any additional device allocation introduced after
this review must update the ledger, and the strict census admission will reject
an over-plan rank before its first model HALF.

`memory_plan.py` regenerates `memory-plan.json`. `memory-plan-gates.json`
records 27 CPU checks: 12 rank/context/draft admission successes, 12 one-byte
over-plan rejections, and three unsupported-context rejections. The wrapper
must pass its requested context to `memory_gate.check`; its default of 256
exists only for inherited callers and cannot admit a larger census by accident.
