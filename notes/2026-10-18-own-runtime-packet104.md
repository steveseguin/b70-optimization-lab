# Packet104: extend the lossless tile16 transpose

Started 2026-10-18 around 05:37 UTC; 2.5-hour CPU-only time box. Sources are copied
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
IDs as an explicit proxy: packet100b did not capture draft routes. As the
brief requests, this replay is the draft operator's 15% screening gate;
subsequent actual model screens must establish whether a gain transfers.
It is never labeled native draft-route timing. Non-routed shared and HC
operations use eight fixed input seeds.

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
lookup dependency intact. The optional packet59 draft INT8 schedule has the
same multi-row pattern, but **is not selected by packet100**. Its selected
draft uses `mtp36::Dense` with one row per subgroup, WG128. Shared down uses
`p33::Kernel<0,BF16,640,1>` with WG32; shared gate/up use mtp36, with separate
activation. Those are lower-confidence boundary measurements, now measured
against their actual selected operation. HC Q8 has two output rows with its
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

## Dispatch audit and corrected micro

The first build used the optional packet59 draft kernels. A source audit and
independent read-only review caught the mismatch with packet100's selected
draft. No micro job had been enqueued or run. The second build uses copies of
the actual `mtp36::Dense` and packet33 shared-down bodies, with unchanged
workgroup geometry and no added activation fusion. Selection and dispatch
snapshots are now explicit build inputs. The old receipt and binary are
retained as superseded preparation evidence, never a timing control.

The corrected binary compiles. Thirteen protocol checks pass, including a
single slow route rejecting an otherwise winning candidate, malformed order,
geometry, exactness, finite timing and drain checks. The real capture binding,
closed-environment micro plan and a temporary lanequeue plan pass. These are
preparation checks, not the conditional GNU/Intel byte-identity gate.

The copied runtime sources now include load-time tile views and matching
dispatch for down-tile16 plus each new candidate. They are **prepared,
uncompiled, unqualified**; `integration-plan.json` says so. The half-cache arm
has a separate half-cache control. KD gets a draft-only host selection with
the target resident-only transpose removed, while keeping all selected draft
choices. The eleven actual chain window names are registered from packet97e,
including both KD startup paths. No model seal or runnable screen exists.

## Complete matching-stream inventory and ninth-arm build

The target's resident `small.ffn.q6` override is another matching stream:
`p49dvirtual::SmallKernel<4>` maps four rows inside each subgroup, with the
unchanged Split4 reduction. Added two independent comparisons: expanded Q6
shared gate/up and F32 expert router. Both time the **complete selected tuple**,
including unchanged sibling operations; neither substitutes an isolated GEMV.
The scalar one-row shared router remains unchanged. Q6 keeps all 3380 bytes
per row (codes, float scales and 180 metadata bytes); router keeps 10240.
The micro checks the full tuple's FP32 reductions and actual BF16 outputs,
including agreement between the two, and verifies output guards.

Nine candidate kernels now compile; the current build is 29,117,472 bytes.
All nine views compose with down-tile16. The selected target shared-down is
packet33 Q8 WG32, one row per subgroup, so it does not match. Attention
`rows4` means rows across separate subgroups; its name does not establish
the packet100 pattern. The detailed inventory is in
[the access census](../experiments/own-xpu-runtime/stage2/packet104-tile-transpose/ACCESS-CENSUS.md).

The micro's actual dependency closure no longer requires the large generated
parent RoPE header or a full runtime build. There are still no measured
packet104 timings, no byte-identity verdict and no model-screen admission.

Read-only review also caught incomplete startup plans that omit a tuple
sibling. The prepared integration now uses one coverage predicate for both
load layout and dispatch: only complete resident Q6 tuples without outside
consumers of the selected banks can transpose. Partial plans retain their
original bytes and kernels; both Q6 banks are admitted together. This fix
still needs the conditional full-window CPU gates after a micro win.
