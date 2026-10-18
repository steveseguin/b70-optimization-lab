# What the production source and offline compiler establish

The actual path is `main.cpp` → `p49d::expert` → `p49d_expert.hpp`.
The dispatch JSON’s inherited names alone do not identify this kernel.
Packet64 already uses packet53b’s banked logical-lane mapping and already
launches all ten selected experts together. Repeating that batching is not a
new candidate.

| Production property | IQ2_S gate/up | IQ4_NL down |
| --- | ---: | ---: |
| Columns per row | 2,560 | 640 |
| Rows/expert | 640 | 2,560 |
| Selected experts | 10 | 10 |
| Compact row pitch | 820 bytes | 360 bytes |
| Useful weight bytes/launch | 10,496,000 (both projections) | 9,216,000 |
| Workgroups/launch | 200 | 200 |
| Work-items/group | 256 | 256 |
| SG32/group | 8 (four gate/up pairs) | 8 |
| Output rows/group | 32 paired | 128 |
| Physical lanes/row/stream | 4 | 2 |
| Logical chains/physical lane | 8 | 16 |
| Total subgroups/launch | 1,600 | 1,600 |

Useful weight bytes are not measured DRAM traffic: input, table reads, cache
line fetches and metadata reuse matter. The supplied packet57 attribution is
about 72 µs gate/up and 57 µs down. Equal effective bandwidth in two formats
is consistent with a memory-issue bottleneck, but does not prove occupancy is
the sole limit.

On a **conditional 32-core model**, the launch distributes an average of
6.25 workgroups and 50 subgroups per core over its entire execution. These
are scheduled totals, **not simultaneous resident occupancy**. WG64/WG128
keep the same 1,600 total subgroups; they change residency granularity and
the tail. They do not create additional total rows or logical work.

The production source loads one chain’s packed data, then dependent table
entries and activations, before its ordered multiplies/adds. There is no
explicit next-block pipeline. For IQ2 each chain asks for an index/sign pair,
high byte, scale byte and half, then two codebook words and eight BF16 inputs.
IQ4 asks for a half and two code words, then eight inputs. Hardware outstanding
requests per lane, actual bandwidth transactions and resident subgroups cannot
be measured without a coordinator device window; they remain unknown.

`wide64` batches raw operands only. IQ2 shares four code words, two high bytes,
two scale bytes and one half across eight adjacent logical chains. IQ4 shares
four code words and one half across four chains. It retains the compact pitch,
BF16 boundaries, original `step → chain → j` accumulation, adjacent lane tree,
route validity, status stores and atomic error semantics. Vector reads require
only the existing four-byte row alignment. K640’s final 128 elements remain
bounded; no padding or weight layout change is introduced.

`prefetch64` loads a raw `k+256` tile before decoding the current tile. Each
logical lane retains its own original `k,j` sequence, although independent
chains are visited in a different order. Offline assembly retains earlier
loads but waits on next-tile destinations before current decode. This proves
load placement only, **not overlap with arithmetic or more outstanding memory
requests**. It also increases static instruction count. Device timing decides.

## Offline compiler evidence

[Register receipt](register-report.json) compiles the **actual checked expert
translation unit** for BMG-G31 with the engine’s strict floating-point flags.
[Assembly summary](evidence/assembly-summary.json) and compressed assemblies
retain the result. All ten kernels use 128 configured GRFs with zero spill
metadata and zero scratch messages. Configured GRFs are not a measurement of
actual occupancy or the installed driver’s JIT decisions.

| Choice | Gate instructions / load instructions | Down instructions / load instructions |
| --- | ---: | ---: |
| production | 2,469 / 79 | 3,368 / 103 |
| wg64 | 2,468 / 79 | 3,360 / 103 |
| wg128 | 2,469 / 79 | 3,360 / 103 |
| wide64 | 1,993 / 51 | 2,955 / 79 |
| prefetch64 | 3,305 / 145 | 5,418 / 160 |

These are static instruction counts including control flow, not dynamic
executed counts or projected speedups.

Gate/up are already in one launch. Down depends on all 640 rounded activated
rows from other workgroups, so fusing it into gate/up would need a legal global
synchronization scheme. None is added. Activation fusion alone targets only
about 4.7 µs and cannot meet this class bar; it is not expanded into a campaign.
Persistent workgroups, per-workgroup SLM table staging, free-order reductions
and V16 gate/up remain closed by packets52/53/53b.

## Performance denominator

Packet57’s approximately 0.192 ms class includes routing and combining.
Gate/up plus down account for approximately 0.129 ms. Reducing only those two
by 30% would save about 0.039 ms, roughly 20% of the full class, and fails this
packet’s bar. The comparison therefore sums all actual class events in each
complete target half before aggregating. Draft events and cancelled partial
halves cannot become a fast class sample. No cross-device timestamps are
subtracted. See the executable definition in `expert_composition.py`.
