# Packet58h feasibility — October 18, 2026 UTC

Decision: **do not build**. Both the retained host-admission gate and the
evidence-based +20% timing gate fail. The declared layout below has exact byte
arithmetic, but is not an implemented or measured allocation census.

## Identity and baseline

Parent: frozen packet58g; one B70, Unsloth UD-IQ3_XXS target,
`iq3-p49-split32-v1` packet49 arithmetic, full BF16 KV, context 4096,
18,000,000,000-byte expert cache. Its KD, WS and WS128x device windows pass
and contain identical allocation censuses. No target quantization, arithmetic,
KV precision or output oracle change is proposed.

The WS128x class-balanced statistic is **24.012783717 tok/s**. Its reciprocal,
**41.644484529 ms/token**, is a modeling anchor, not a measured mean latency.
WS128x is a shared-host exactness window with 128-token outputs; its timing is
diagnostic and the strict 512-token realistic final gate is false. This work
does not promote it, replace it with a later WS128 result, or touch that run.

The brief describes copy-on-miss, but the saved window explicitly selects
`zero-copy` / `--miss-mode zerocopy`. The engine reads missing expert weights
from pinned host memory, then fills and publishes the device cache between
positions. This differs from a fully resident target or a demand copy before
each missing expert calculation. Timing assumptions preserve that identity.

The draft inventory comes from packet84's retained full-size allocation census.
It is the existing one-token MTP draft with draft-HC and the 91,392-row prefix,
not packet83's Q4/smaller-prefix alternatives. Its expert weights are INT8 with
FP32 group-16 scales, produced by the existing loader from the official FP8
draft tensors. They are separate from the IQ3 target experts. Target verification
would still be mandatory for every emitted token; no new quality gate ran here.

## Exact added weights and working memory

All values are decimal bytes unless GiB is written. Every weight allocation row
is retained in `feasibility.json`, derived from the compressed packet84 census.

| Draft allocation | Bytes |
| --- | ---: |
| Three routed expert banks | 3,145,728,000 |
| Attention, indexer and their norms | 102,894,592 |
| HC and its norms | 39,608,320 |
| Input merge projections and norms | 26,265,600 |
| Router and shared expert | 12,456,960 |
| **All draft weights** | **3,326,953,472** |
| BF16 KV/index state at 4096 context | 9,699,328 |
| All draft buffers and workspace | 17,711,414 |
| Pinned publication and hidden-state staging | 20,492 |

Each routed bank is `512 * 640 * (2560 + 2560/16*4)` = 1,048,576,000
bytes; transposed down geometry has the same total. These experts can join the
host pool and share its cache machinery, but cannot alias target weight bytes.
Each draft expert consumes 6,144,000 bytes across its three projections.
The existing cache uses variable-sized 256-byte-aligned blocks; this is not
an assumption that a draft expert fits a target-sized slot. Draft pointer
indirection and its submit checks would still require implementation.

The target's full expanded head is already **839,321,600 bytes**:
248,320 rows × 3,380 bytes. Its first 91,392 rows occupy 308,904,960 bytes,
but sharing those rows adds **zero** device or host weight bytes. Merely
retaining the existing draft placement guard would not enable this path:
one-card head ownership must be explicitly admitted if this arm is revisited.

The draft reads the existing target embedding mapping. No second embedding
weight table is needed. Its private 5,120-byte embedding output is already in
the workspace count. RoPE can also reuse the existing immutable allocation.
Draft HC/norms are its own weights, not aliases of target HC/norms.

Official draft inputs total 2,698,026,496 file bytes. The loader reads bounded
tensors, at most 62,914,560 bytes, then retains the converted resident/pinned
weights. The original 256 MiB staging allowance is retained. No permanent
residency of all these source pages is needed after load, so they are not
silently added as another pinned copy; normal reclamation is allowed without
cache drops or settings changes. The existing full target lookup-page
residency allowance remains in timing admission.

## Verification and rollback reservation

A declared conservative one-card design keeps the existing canonical target
state untouched while two private rows retain the prefixes after the confirmed
input and after the proposed input. The second row must consume the first
row's temporal state and causal KV. They are consecutive positions, not two
independent guesses. Prefix selection copies only the verified state back.
All sticky errors must be checked before selection; failure cannot be erased.

We reserve full census extents rather than guessing smaller scratch bounds:

| Added private allocation | Bytes |
| --- | ---: |
| Two target mutable rows, 2 × 471,023,348 | 942,046,696 |
| One complete draft mutable backup, including BF16 KV | 27,410,742 |
| Two 4096-entry copy tables, 32 bytes per entry | 262,144 |
| **Total private-state reservation** | **969,719,582** |

One target row includes 295,612,132 workspace bytes, 59,019,280 recurrent-state
bytes and 116,391,936 BF16 KV/index bytes. The canonical original is the
before-pair prefix; both private rows already contain their own complete
recurrent banks. No additional alternate-bank pair or full target snapshot is
charged a second time. This reservation is deliberately conservative and is
not a proof that the existing packet71 controller can be pasted into 58g.

The private-state reservation fits the existing 1 GiB transaction allowance
with **104,022,242 bytes remaining**. Original workspace plus draft workspace
also fits the existing separate 1 GiB workspace allowance. Therefore the
admission calculation does **not** charge these reservations twice. Host copy
descriptors, launch/lookup/history metadata and cache bookkeeping stay within
the unchanged 1 GiB process and 16 MiB cache-metadata allowances. Allocator
overhead is bounded by those allowances, not presented as measured exact RSS.

Cache contents are immutable weights; discard must fence readers and preserve
valid current cache generations, not restore stale pointers over overwritten
cache slots. A full submit-time extent gate and state/teardown checks would be
required for any later build. No such build or new gate is claimed here.

## Device and host admission

Actual post-load KD/WS/WS128x census: **24,287,732,980 device bytes** and
**48,633,091,712 pinned host bytes**, including 48,627,712,000 expert bytes.
The original conservative device bound is 26,409,219,600 bytes. The comparison
keeps both the 1.5 GB device reserve and the **8 GiB host reserve**.

| Proposed layout | Resident draft experts | Draft experts share existing cache |
| --- | ---: | ---: |
| Extra actual device payload, including private banks | 4,324,083,796 | 1,178,380,372 |
| Extra directly owned host payload | 20,492 | 3,145,773,188 |
| Proposed actual device payload | 28,611,816,776 | 25,466,113,352 |
| Proposed conservative device bound | 29,745,872,400 | 26,600,193,552 |
| Device margin after reserve | 754,127,600 | 3,899,806,448 |
| Extra host admission charge | 3,336,673,292 | 3,336,747,140 |
| **Whole-host timing admission required** | **121,645,581,340** | **121,645,655,188** |

For the shared-cache design, 3,145,728,000 draft expert bytes move to pinned
host memory while the **18 GB cache stays unchanged**. Three pointer tables
add 24,576 device bytes and 24,576 staging bytes; route readback adds 120 host
bytes. Admission reserves 49,152 device table bytes, keeping the parent's
double-generation allowance. Draft experts displace target experts in that
same cache; no free cache-hit-rate improvement is assumed.

Both options fit device accounting. Neither fits retained whole-host timing
admission with margin. The original timing requirement is 118,308,908,048
bytes. Available RAM at the original admissions was:

| Evidence window | MemAvailable | Resident-option shortage |
| --- | ---: | ---: |
| KD | 120,565,194,752 | 1,080,386,588 |
| WS | 120,916,029,440 | 729,551,900 |
| WS128x | 120,528,850,944 | 1,116,730,396 |

This uses even the most favorable retained snapshot. Preserving the observed
646,889,472-byte shadow envelope in addition to full device backing increases
the resident timing requirement to **122,292,470,812 bytes**. Exactness-only
admission would be about 88.97 GB and is a different test; it does not qualify
whole-host timing. It still cannot overlap a lane-B screen requiring 97 GiB.
Swap never counts toward admission.

This is a failure of the **retained conservative admission**, not proof that
physical RAM could never hold a differently budgeted implementation. Replacing
allowances with a newly proved complete census is a separate hypothesis; this
analysis does not silently reduce them, the cache or either reserve.

The passive snapshot in `inputs.json` had 119,648,227,328 available bytes.
It also found **blocks 53–56 offline and block 57 online**. A read of all block
states found only those four offline blocks, each 2 GiB. This differs from the
brief's stipulated 10 GiB exclusion. Nothing was changed. We do not treat the
online block as newly authorized RAM or suggest enabling excluded memory to
make this arm fit. Even the unadjusted observed snapshots fail admission.

## Timing model and sensitivity

Transfer the packet77/85 draft command cost **D = 1.794747301 ms** and
acceptance **a = 0.787401575** as assumptions, not one-card measurements.
For a blocking one-token draft with a confirmed frontier input and a two-row
target verification, the optimistic reward is `1+a` tokens per cycle:

```text
hit cycle = D + V2
mean cycle = D + V2 + (1-a)*R
predicted tok/s = 1000*(1+a) / mean cycle
```

One card serializes both target halves and drafting. No cross-rank overlap is
credited. The zero-rollback scenarios also omit draft feedback/repair and
additional cache/state-copy costs, making them optimistic. An actual MTP
implementation must still advance draft state correctly after an accepted
second input; any extra pass costs more.

The existing packet68c screen has **39 consecutive, differing-route samples
per rank**, with byte identity. Duplicate-input/equal-route samples are excluded.
Medians, in milliseconds:

| Proxy | Rank 0 M1 | Rank 0 M2 | Rank 1 M1 | Rank 1 M2 |
| --- | ---: | ---: | ---: | ---: |
| Device execution sum | 12.5557 | 21.8869 | 13.8630 | 23.0330 |
| Prepared replay wall | 12.7310 | 22.1411 | 14.1011 | 23.3429 |

The combined device ratio is **1.700307**. Applying it to the baseline token
time predicts **24.62 tok/s**, about **+2.58% over 24.0**, even before rollback.
The +20% threshold allows `V2 <= 60.267807 ms`, or **1.447198×** the baseline
token time, with zero rollback. The measured proxy ratio is materially larger.

| Explicit model assumption | Predicted tok/s |
| --- | ---: |
| Transfer the measured differing-route M2/M1 ratio, no rollback | 24.6188 |
| Charge all existing one-card overhead once per pair; add only device M2−M1 | 28.8568 |
| Same optimistic assumption, prepared replay wall M2−M1 | 28.7867 |
| Device-difference scenario plus rejection-weighted packet68 restore | 28.7600 |
| Wall-difference scenario plus rejection-weighted packet68 restore | 28.6904 |
| Existing causal71c M2 command costs; omit every one-card penalty | 27.3129 |
| Two serial unchanged M1 evaluations, no rollback | 21.0076 |

The device-only optimistic case barely clears 28.8, leaving **0.122123 ms per
cycle** for everything omitted. The existing packet68 restore median is
0.980923 ms. Charging it only on rejection adds **0.208543 ms/cycle**, already
more than that margin. Restore is a cross-implementation sensitivity, not a
measured lower bound on every future prefix-selection mechanism. The prepared
wall proxy already misses the threshold even with free rollback.

The causal71c command proxy is 31.955315496 + 31.691651211 = 63.646966707 ms.
Its controller and state handling differ; this does not predict exact 58h
speed. It shows the risk in treating device operator sums as a complete
causal verification cycle. Packet79's relocated two-card draft and packet83's
changed draft bytes do not transfer their performance or reopen their losses.

58g did not collect isolated operator timing: its generated-token receipts
have zero `gemv_device_ms` and `non_gemv_device_ms`. Consequently, subtracting
the separate packet68c M1 sum from 41.6445 ms does **not** measure PCIe or cache
overhead. The favorable constant-overhead models merely assume that difference
is paid once per pair. They also assume no added draft misses, target evictions,
route-union traffic, state-copy latency or host cost. Existing evidence cannot
support all of those assumptions strongly enough to justify a +20% build.

## Evidence, verification and scope

`inputs.json` maps each archived input to its original path and SHA256. The
archives include all three original 58g windows, their deduplicated complete
census, WS128x summary, the packet84 draft census, draft manifest, packet68c raw
M1/M2 rows, packet68 restore rows and packet85 model. Frozen implementation
files are separately hash-pinned. Original source checks and deterministic
CPU recomputation pass; an independent read-only review checked the arithmetic.

No GPU, model payload, compiler, service, sudo, signal, reboot, host-setting
change, live queue, publication or external submission was used. The requested
build, packet49 output gates, full-shape submit checks, seals and launch line
are conditional on feasibility. They were intentionally not created after
the gate failed. See [closeout](CLOSEOUT.md) for the concrete revisit condition.
