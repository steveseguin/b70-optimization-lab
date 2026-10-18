# Packet100: exact DOWN load locality

Two lossless locality candidates and production are built and sealed. Both
compilers pass two fresh byte runs; all 34 full-size startup checks pass,
including real arena admission and the packet97/99 composition corners. Three
seals, fifteen Python checks and all five temporary queue plans pass. The build
uses about 151 MB. No GPU, service, live queue or host setting was changed.

**The next device step is blocked on missing route bytes.** Packet77/86 saved
1,152 route hashes (576 distinct vectors), but none of 3,516 retained raw route
files matches. The prepared micro refuses to run without those exact inputs.
No speed, device-quality or record claim exists. Records remain lane A only.

## What production reads

IQ4_NL has 32 weights per native 18-byte block (2-byte FP16 scale, 16 code
bytes). K=640 means 20 blocks. The existing load-time repack stores 320 code
bytes then 40 scale bytes, retaining a 360-byte row stride. One expert has
2560 rows: 921,600 bytes (900 KiB); 512 experts occupy 471,859,200 bytes.
Eight to ten different experts touch 7,372,800–9,216,000 weight bytes per
projection. The selected weights are read once per invocation, apart from
hardware cache-line overlap; no arithmetic-level reuse is introduced here.

WG64 contains two SG32 subgroups. Each subgroup owns 16 output rows, two
physical lanes per row, with 16 logical chains per lane. Each workgroup owns
32 rows; there are 80 groups per expert slot, 800 groups for ten slots. The
linear group ID is slot-major. This specifies submitted ordering, not a promise
about actual GPU workgroup dispatch order. Within each row, step 0/1/2 and four
blocks per physical lane retain k=8*logical_lane+256*step and j=0..7.

Each physical lane loads four code words for one 32-weight block at a time.
Code addresses within a lane are contiguous. Across a subgroup, neighboring
row pairs are 360 bytes apart, with the second lane 64 bytes ahead. This is not
one contiguous subgroup span. With an aligned allocation, every other row's
code start is only 8 mod 16; 32-bit loads are still aligned. The new layout
makes every code vector 16-byte aligned and adjacent rows contiguous within a
block plane; each physical-lane half-subgroup reads a 256-byte row span.

Each slot has a different 640-element BF16 activation vector, only 1,280 bytes.
It is reused across all 2560 rows and 80 workgroups for that slot; all ten
vectors occupy 12,800 bytes. There is no explicit SLM activation cache. Reuse
can be served by hardware caches, but source alone does not establish L1/L3
hit rates or the installed driver's cache policy.

## What packet86 proves and does not prove

Serving all slots from expert zero cuts rank1 DOWN from 1.208 to 0.849 ms per
half (0.359 ms). It shrinks distinct weights by 8–10x and repeatedly revisits
the same pages/cache lines. This is strong repeated-address locality evidence,
not a measurement distinguishing L3 capacity, TLB misses, DRAM page hits, or
prefetch distance. No counters or eviction test in those receipts identifies
which one dominates. The constant-grid view does not change IQ4 DOWN at all:
IQ2 lookup-grid cost is a gate/up question, owned by packet99.

E3 is closed at -0.46%; packet81 load-count and packet65 occupancy are not
reopened. E4 gate/up slot coalescing cannot help production's unique top-k
expert IDs, and DOWN inputs remain distinct even for duplicate IDs. The router
ranks a permutation of the 512 indices, so each valid top-ten ID is unique.
This is a source proof, not a measured duplicate-frequency claim.

[Preregistration](../experiments/own-xpu-runtime/stage2/packet100-down-locality/PREREGISTRATION.md)
contains gate order and the exact pending device boundary.

The requested initial pull refused unrelated unstaged work. Fetch confirmed
main equal to origin/main; no unrelated file was stashed or included. Root had
about 19 GB free. The compiled engine build is 113,480,723 logical bytes before
additional gate tools. All compilation uses packet94's shared turn lock.

## Completed gates and handoff

Each compiler/repeat compares 36 complete DOWN cases, 62,208 raw FP32 chains,
1,944 full trees, every half-scale bit pattern, and 167,961,600 permutation
bytes. All 68 short/misaligned allocation checks, 14 unsupported-mode checks
and five invalid-selection checks refuse. The smallest startup arena margin
across compatibility corners is 630,519,094 bytes; no memory budget changed.
The three standalone performance views use unchanged weight bytes/extent.

Linked offline BMG code has 128 GRFs and 79 static load lines for every arm.
Instruction counts are 2981 (production), 3016 (interleave), and 2984 (tile16).
There are no scratch load/store instructions. The code therefore changes
addresses/scheduling without lowering load count; no device speed follows from
these static observations. Full instructions are retained compressed.

The microbenchmark is compiled, not executed. It uses actual shipped kernel
bodies and full 512-expert banks, exact FP32/BF16/status checks, 40 alternating
pairs per real route vector and an equal device-only cache scrub before every
timed arm. Synthetic weights/activations remain explicitly diagnostic. All
route strata and both order halves must take at most 85% of production time.
The archived inputs cover final per-layer states only, not a full token trace.

The five proposed jobs are a lane-B micro and separate B grids/A confirms for
each candidate. Every proposal passed the real plan on a temporary queue.
No proposed job was enqueued. The shared v4 wrapper supplies the 64-token smoke
and all thirteen exact checks. Record/K2-merge/submission helpers explicitly
refuse until a later qualified bundle; CPU seals never authorize promotion.

[Final verification](../experiments/own-xpu-runtime/stage2/packet100-down-locality/evidence/final-verification.json),
[implementation and commands](../experiments/own-xpu-runtime/stage2/packet100-down-locality/README.md),
[CPU closeout](../experiments/own-xpu-runtime/stage2/packet100-down-locality/CPU-PREPARATION-CLOSEOUT.md),
[raw-route inventory](../experiments/own-xpu-runtime/stage2/packet100-down-locality/evidence/route-inputs.json).

Initial implementation/build milestone: b81a83bec, pushed immediately. Existing
build scratch was later removed from Git tracking without deleting local bytes;
its staged removals were included by concurrent commit 97f9200a4. The retention
note records the restoration path. No other packet was changed by this work.
