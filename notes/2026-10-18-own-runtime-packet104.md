# Packet104: extend the lossless tile16 transpose

Started 2026-10-18 05:37 UTC; 2.5-hour CPU-only time box. Sources are copied
from packet100, never edited there. `source-origin.json` records their bytes.
`git pull --rebase` refused the shared dirty tree; `git fetch origin main`
then showed HEAD and origin/main identical (0 ahead / 0 behind). Foreign
work was preserved. No GPU, service, sudo or host-setting change is authorized.

## First milestone: micro compiled before long CPU gates

Seven separate candidate kernels compile with the unchanged packet100 Intel
flags, checked by-value kernel mirror and packet94 compiler-turn lock. The
build is 27,870,928 bytes, under 300 MB. Proposed job:
`experiments/own-xpu-runtime/ops/lane-queue/proposed-p104-micro-B.txt`.
No live queue was changed and no device binary was executed.

Candidates: target IQ2 gate/up with normal half scales and exact FP32 half
cache; draft INT8 routed gate/up and down; draft BF16 shared gate/up and down;
HC Q8 gate with its two-row/four-stream fused mixture. Byte permutations keep
all metadata, full 16-bit KV, FP32 chains, trees, BF16 stores and epilogues.
These are isolated operator changes intended to compose with down-tile16.
There is no model integration or engine speed claim yet.

The full 384-vector packet100b target-route snapshot is hash verified against
its capture evidence. Both target gate variants consume those real IDs, with
the operation's 640-row extent. The draft operator replays the same target
IDs as an explicit proxy: packet100b did not capture draft routes. Even a
15% proxy gain cannot qualify a draft screen without actual draft-route
evidence. Non-routed shared and HC operations use eight fixed input seeds.

Each candidate compares full FP32 reductions, BF16 outputs, fused outputs,
status and error controls before timing. Forty pairs alternate order in each
stratum. A 512 MiB device scrub precedes each arm; no host cache is changed.
Require <=0.85 candidate/control time overall, in both orders and every
stratum. This remains a synthetic-weight operator diagnostic, never a model
benchmark. The wrapper reserves lane B and admits physical card 2 only;
largest device allocation is below 5 GiB, host scratch below 2 GiB, with the
existing fault/drain/ownership guards and no retries.

## Access-pattern census

Packet100 down uses 16 output rows per subgroup. Each pair of lanes reads the
same code block and scale plane from neighboring rows. The transpose groups
those chunks into nearby addresses, without changing a weight value. Its
measured speed gain supports locality as a mechanism; neither packet100 nor
this packet measures DRAM page hits or L3 reuse counters.

Target IQ2 has eight output rows per subgroup, independent gate/up subgroups,
16-byte code loads, two-byte high/scale reads, and two/four-byte half scales.
The new tile transposes each of those planes separately. It leaves the IQ2
lookup dependency intact. Draft INT8 has the same multi-row pattern (eight
gate/up rows, sixteen down rows); its codes and exact FP32 scales are separate.
Shared down has four output rows per subgroup. Shared gate/up has one and is
a lower-confidence boundary measurement. HC Q8 has two output rows with its
lanes spread across columns; measurement may reject the transpose there.
Dense attention uses one row per subgroup (with fixed split reductions), so
does not match the down pattern and is not opened as another arm.

Closed packets 65, 73, 74, 81, 90, 95, 99 and 102 were read first. No lookup
relocation, prefetch, input packing, new accumulator tree, packed-dense revival,
or occupancy sweep is included.

## Remaining conditional gates

Only a qualified micro candidate advances to GNU + Intel byte identity, full
shape CPU startup/host-reference runs for **every chain window**, actual VRAM
admission, sealed model integration, B grid and A confirmation. KD must use
the same supported host-reference path as the selected composition. Parent
orchestration outputs are not build or seal dependencies. Record chains run
on A. No screens or record chain are admitted by this first milestone.
