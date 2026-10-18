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
verify row cost is GDN glue” was not present in available local memory or repo
Markdown; the source-level dependency is recorded here without inventing it.

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
