# Packet113: independent GDN rows, micro first

Started 2026-10-18 08:42 UTC; two-hour CPU-only time box. Pull refused because
of unrelated dirty orchestration files. Fetch confirmed HEAD equals origin/main
at `5d593e7a84d1d4315aecf7819fef0cf0d7199092`. Existing packets and live queues
are frozen. No GPU, service, host setting or foreign process is touched.

## Current recurrence and opportunity

Packet103's selection uses `rec-both-plus`, packet82b `Kernel<true>` in
`p82b_recurrence.hpp`. Packet97, 103 and 110 carry this implementation. State is
BF16 `[48 value heads][128 value rows][128 key dimensions]`, 786,432 elements
(1,572,864 bytes). There are 16 key/query heads, mapped by `h % 16` in the packed
record layout (the alternate mapping is `h / 3`). Arithmetic is FP32 with strict
rounding and no contraction, with BF16 state and BF16 output writes.

Each of 1,536 workgroups has 128 work-items, four subgroups of 32, one subgroup
per value row. Before each token, subgroups 0 and 1 produce query/key norms,
subgroup 2 lane 0 computes decay, subgroup 3 lane 0 computes beta. The group
shares 258 FP32 values (1,032 bytes) and synchronizes. Each lane then loads four
adjacent BF16 state elements, decays them, sums four left-to-right products,
and reduces the 32 leaves by the fixed adjacent tree (strides 1,2,4,8,16).
The delta `(value - prediction) * beta` updates the state. The same leaf/tree
order produces query-dot-updated-state output. Output and state round to BF16.
For M>1 a global/local barrier precedes the next token; the next token rereads
BF16 bytes. The entry guard uses subgroup broadcasts without a group barrier.

This is **already 48 workgroups per Xe core** if divided over 32 cores, not a
few-groups occupancy shortage. Packet110's 23.958 us and 132.69 GB/s count useful
bytes, not hardware DRAM transactions. Repeated norm/gate work, five-level
shuffle dependencies, the shared-memory rendezvous, register occupancy and
instruction issue are plausible costs; the timing is not a stall-counter proof.
The 5.920 us byte floor is an opportunity bound, not an achievable prediction.

M=2 verify work remains state-dependent: token 1 must consume token 0's rounded
state. It cannot safely run both tokens concurrently. Packet110 measures M=1;
no M=2 timing is inferred from it. The named memory note “Flash-Next second
verify row cost is GDN glue” was located in `/home/steve/.claude/projects/-home-steve/memory/flash-next-second-verify-row-cost-is-gdn-glue.md` during final review.
It concerns the historical vLLM TP4/EP4 serial selector, not this runtime. Its
updates warn that launch counts mispredict graph replay, that a multirow kernel
can differ by one ULP despite apparently identical source, and that later exact
C++ serial work removed the GDN excess. This packet preserves rounding and tests
multirow bytes; it does not import those old timing deltas or selector settings.

## New mechanism and exactness proof

One independent state row per 32-thread workgroup exposes 6,144 groups while
removing shared memory and every workgroup barrier. Each lane still owns the
same four state elements. Query/key/gate work is repeated per row rather than
per four rows, a known cost that the 40% kill gate must overcome. There is no
extra kernel, no global preparation scratch, no cross-group reduction and no
packet107 shared-head prepass. Conv/gated fusion is not mixed into this arm.

The host candidate changes only the independent base/row traversal. Device
normalization, decay, prediction, delta and output retain expression operand
order, FP32 boundaries, deterministic math and the production 32-leaf tree.
The state lane is its sole writer and next-token reader, so no other subgroup
needs its bytes. BF16 conversion and reload remain between tokens. Candidate
and control must match every state/output/control byte, including inactive,
sticky-error, invalid-position, alias, NaN/Inf and subnormal cases, separately
under GNU and Intel. A source proof does not substitute for compiled gates.

## Milestone 1

The initial single-token leaf checks pass twice under each compiler: 208 full
state/output checks per process, both head mappings, 13 scenarios and aliased
and separate state. Intel's packet107 NaN-payload failure is explicitly covered.
Multi-token checks, complete-layer builds and coordinator proposal are next.
Builds use packet94's serial compiler turn, nice 19, CPUs 8–15/24–31, stdin
`/dev/null`, and an 8 GiB cap only inside CPU CLI processes. Build budget 150 MB.

## Milestone 2 — micro compiled, sealed and proposed (08:53 UTC)

GNU, Intel and device complete-layer binaries compile. GNU and Intel each pass
**two fresh CPU processes**, each with 572 whole-layer boundary/state checks
and 768 full-state recurrence cases. M=1,2,4, both head mappings, both alias
modes, sixteen finite/exceptional/control scenarios and four consecutive calls
are covered. Every process compares about 1.2 GB of state/output bytes; the
transcripts retain hashes only after raw byte equality. GNU/Intel NaN payloads
are compared to their own unchanged production, never normalized across builds.
The complete-layer finite transcripts agree across all four processes.

The device micro binary includes the same 768 cases before timing. It uses the
copied packet110 complete GDN layer, compares every mutable allocation after
each pair, alternates current/candidate order, and measures both contexts
128 and 4096. There are 10 warm-up and 40 measured pairs per context. Warm-up
initializes kernels only; this is explicitly synthetic layer diagnostic timing,
not the realistic model suite or a model throughput claim.

Both jobs pass CPU planning on a temporary queue. The new coordinator proposal
is [proposed-p113-micro-B.txt](../experiments/own-xpu-runtime/ops/lane-queue/proposed-p113-micro-B.txt).
Expected duration is **240 seconds per process**, watchdog **1,200 seconds**
(5x). The wrapper reserves lane B, restricts native access to card2, checks
faults/ownership/drain, and preserves a 19 GiB disk floor plus its log budget.
No live queue was edited and no device job was launched by this task.

Fifteen Python policy/refusal checks pass, including missing byte cases, wrong
order, incomplete pairs, invalid event accounting, CPU receipts passed as device
results, per-context/order losses and import-time resource-cap preservation.
The build is **66,586,092 bytes**, below 150 MB. Peak compiler child RSS is
under 800 MiB; all CPU CLIs use the requested 8 GiB cap. Generated binaries are
ignored; the first milestone accidentally tracked the two small leaf binaries,
corrected in this milestone while preserving them locally under `build/retained-*`.
Their source, commands, hashes and prior commit remain available.

**Device exactness and speed remain unmeasured.** The gate is hash-bound to both
fresh-process windows, all exceptional and whole-layer transcripts, event
endpoints and the sealed executable. Each context and alternating-order stratum
must be at most 0.6 times production in each process. A failure closes this arm;
only a pass allows the packet111/103x runtime dimension, startup/oracle gates,
seals and v5 one-load proposal. None of those later steps is claimed here.

Evidence: [CPU leaves](../experiments/own-xpu-runtime/stage2/packet113-gdn-row/evidence/cpu-leaf.json),
[complete layers](../experiments/own-xpu-runtime/stage2/packet113-gdn-row/evidence/cpu-layers.json),
[device build](../experiments/own-xpu-runtime/stage2/packet113-gdn-row/evidence/build-device.json),
[queue plans](../experiments/own-xpu-runtime/stage2/packet113-gdn-row/evidence/queue-plans-final.json).

## Final CPU handoff — 08:57 UTC

Final review tightened CPU provenance: fresh output directories are mandatory,
and each process records its binary and build-receipt hashes before launch.
All four final processes pass again, including exact exceptional transcripts
across each compiler's repeats. Earlier successful runs remain as evidence.
The final CPU subprocess peak RSS is 1216952 KiB. The complete
synthetic layer and recurrence transcripts also agree across GNU and Intel in
this full-harness build; the separate leaf builds retain their compiler-specific
production NaN payloads.

Precision flags are present on both SYCL compilation and link commands;
packet110's source hashes remain unchanged. The final seals and two temporary
queue plans pass. [Final review](../experiments/own-xpu-runtime/stage2/packet113-gdn-row/evidence/final-review.json)
and [CPU preparation closeout](../experiments/own-xpu-runtime/stage2/packet113-gdn-row/CPU-PREPARATION-CLOSEOUT.md)
retain the handoff. The micro gate explicitly reports **pending**, with
`integration_allowed=false`. Packet111 is now committed (`83d5518ba`) and is
the conditional integration base after a qualifying micro; no integration or
v5 runtime proposal was built ahead of that gate.
