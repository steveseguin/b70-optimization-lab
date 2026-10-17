# Packet82: GDN recurrence analysis

CPU-only, October 17, 2026. Analysis completed before candidate changes.
Arithmetic identity: `iq3-p49-split32-v1`. Production is **rows4-shared**,
not the older scalar `production` selection. Packet70 reuses packet65's
binary. Its recurrence, round2 and detmath headers match packet75 and packet65
byte for byte ([identity](evidence/production-source-identity.json)).

## Traffic and work per token

48 value heads, 16 key heads; each value head has 128 rows × 128 columns.
Stored state and output are BF16, intermediate arithmetic is FP32. State is
rounded back to BF16 after **every token**, even within a multi-token call.
The state layout is already contiguous along the subgroup's key dimension;
there is no state transpose to remove.

| Logical traffic per layer | Bytes |
| --- | ---: |
| State: 786,432 elements, read | 1,572,864 |
| State: write | 1,572,864 |
| QKV BF16, including the value vector | 20,480 |
| Two BF16 gate inputs | 192 |
| Two FP32 parameter vectors | 384 |
| BF16 output | 12,288 |
| Total unique data read + write | 3,179,072 |

Per head state is 32,768 bytes; read + write is 65,536 bytes. Across 18 GDN
layers per rank, state traffic is 56,623,104 bytes (54 MiB), or 57,223,296
bytes with the listed inputs/output. Controls and redundant accesses are
additional. Each four-row workgroup rereads 512 Q/K bytes and its gates:
786,432 Q/K bytes are requested across 1,536 groups, despite only 8,192
unique Q/K bytes. SLM and caches mean logical accesses are not DRAM counters.
No state compression is proposed.

Packet77 reports rank0 35.83 us/call and rank1 34.89 us/call, from sampled
call medians. Its 0.6450/0.6281 ms per half multiply these by 18; they are
estimates, not timed sums of every layer. **44.48/45.68 GB/s count useful
reads only.** Including listed writes gives about 88.72/91.10 GB/s. The
555 GB/s reference gives 5.73 us for these bytes, leaving approximately
0.542/0.525 ms per half as an optimistic reference gap, not 0.59 ms of
promised recoverable time. These rank costs overlap and cannot be added to
predict a model speedup. Source: [packet77 attribution](../screen/v4-lanes/evidence/packet77-attribution-B-a/run/attribution-summary.md),
its raw `sites.jsonl`, and packet77 `byte_formulas.py`.

The exact update is decay first, then prediction on the decayed state:
`v_i = BF16_state_i * decay`; `pred = tree(v_i * k_i)`;
`delta = (input_value - pred) * beta`; `v_i = v_i + delta * k_i`;
`y = tree(v_i * q_i)`. Each tree starts with four left-to-right terms from
+0 per lane, followed by the adjacent 32-leaf tree (five levels).

Per state row: 128 × 7 + 2 × 31 + 2 = **960 ordinary FLOPs**.
That is 5,898,240 per layer. Each group's duplicated Q/K normalization costs
960 arithmetic operations (384 are strict divisions), plus two square roots.
The ordinary gate envelope adds five operations per group. Total is
**7,380,480 ordinary arithmetic operations**, plus 3,072 square roots and,
for ordinary finite gates below 20, 4,608 exp and 1,536 log evaluations.
These exp/log calls use the repository's long compensated FP32 polynomials;
they are not single native instructions. Branches for large gates, tiny
arguments, subnormals and nonfinite inputs change the executed FLOP count.
Explicit polynomial FMA counts as two FLOPs; no contraction is allowed in
state chains. Thus the ordinary count must not be presented as a complete
executed instruction count or a bandwidth-only roof.
[Machine-readable counts](evidence/arithmetic-counts.json).

## Fresh BMG-G31 offline compilation

Intel 2026.0 device-only compile, linked device libraries, SPIR-V translation,
and CPU-only ocloc, all serial under nice19, the requested affinity and 8 GiB
address-space ceiling. No GPU was opened. Source/header hashes, commands and
compressed assembly are retained in [register report](register-report-production.json).
Peak child RSS: 364,220 KiB.

| Assembly property | Production rows4 |
| --- | ---: |
| Static instructions | 2,892 |
| Integer / float / math ALU annotations | 594 / 2,138 / 29 |
| UGM load / store lines | 19 / 4 |
| SLM load / store lines | 4 / 5 |
| Strict reciprocal / square-root instructions | 27 / 2 |
| Configured GRFs | 128 |
| Flag spill stores / loads | 10 / 14 |
| Scratch spill messages | 0 |
| Static barrier sites | 3 |

Counts include mutually exclusive and exceptional paths and are not dynamic
counts. Flag spills are present; they must not be described as scratch-memory
spills. [Instruction mix](evidence/instruction-mix.json).

WG128, SG32, four state rows/group, 1,536 groups and 6,144 subgroups/layer.
That is **48 scheduled groups per each of 32 Xe cores**, not too few groups.
SLM is 1,036 bytes/group. 128 configured GRFs and small SLM do not establish
actual resident occupancy; hardware occupancy/stall counters are unmeasured.
The producer subgroup does almost all preparation while three subgroups wait.
Two barriers execute for one token; a third runs between successive tokens.
State vector loads/stores already lower to two d32 messages per four BF16
values. Blind vectorization or increasing group count is not supported.

## Limiter and decision

The supported working diagnosis is **dependent preparation/reduction latency
and underused subgroups inside a workgroup**, especially the deterministic
gate math, rather than insufficient workgroups or demonstrated DRAM saturation.
Production's subgroup0 performs both normalization chains and all strict
divisions, then its lane0 serially evaluates softplus, decay and beta before
the other three subgroups can update state. Prediction reduction must finish
before delta, state update before output reduction, and BF16 stores before the
next token. That dependence cannot be reassociated under the exact-order gate.
A single launch is present; measured smaller neighboring kernels around 5–7 us
make launch overhead alone an insufficient explanation of a 35 us recurrence,
although its share is not isolated by CPU analysis.

Packet67 rec-head moved preparation to a **48-workgroup prepass** (only 1.5
scheduled groups/core), followed by a dependent second launch. It materialized
49,920 bytes of FP32 head scratch and made all update subgroups read it through
global memory instead of SLM. It removed repeated math but retained the long
serial producer chain and added launch/dependency/global-read costs. Its
measured −11.8% (combined −21.8%) closes that implementation; CPU evidence
supports these costs as an explanation, not a measured decomposition of the
loss. No new rec-head prepass is proposed.

Proceed with two **single-launch** exact-order candidates from copied packet75
sources: (1) move independent decay and beta calculations to separate waiting
subgroups; (2) also put Q and K normalization on separate subgroups. Keep
WG128, the same state layout, loads/stores, five-level trees, strict divisions,
detmath calls and BF16 token boundaries. This shortens the serial preparation
chain without a new launch, scratch allocation or arithmetic identity. Reject
if offline evidence introduces scratch spills or byte checks differ; screen
only after both compiler repeats, multi-token state checks, full-shape startup,
selection-consumer tests and seals. Actual device exactness and speed remain
pending. CPU compilation cannot prove that the scheduler overlaps this work.

## Boundaries

Requested pull --rebase refused unrelated dirty orchestration/packet80 edits.
Fetch confirmed HEAD equalled origin/main; nothing was stashed or edited there.
Root has about 20 GiB free. This specifically authorized build stays below
1 GB without cleanup; no model payload, service, GPU, sudo, settings change or
kill is used. Foreign compiler processes were absent before offline compilation.
