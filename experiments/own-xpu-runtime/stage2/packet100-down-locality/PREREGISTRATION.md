# Packet100: exact routed DOWN load locality

CPU preparation only, 2026-10-18. Three-hour limit. Base: copied packet97 bundle
sources and its exact inherited object identities. Frozen originals are never
edited. Packet99's independent gate/up header is copied with a SHA256 pin only
to preserve composition; no gate/up optimization is developed here.

Arithmetic: `iq3-p49-split32-v1`; separate FP32 multiply/add, the same 32 logical
chains, each chain's step/j order, adjacent reduction tree, BF16 stores, routes,
status and error behavior. Full BF16 KV and target weights remain unchanged.

## Two mechanisms

- `down-interleave`: permute WG64 group IDs from slot-major to row-tile-major,
  interleaving the ten slots at each 32-row tile. No layout or arithmetic change.
  Hypothesis: balance concurrent expert streams and prefetch distance. Risk:
  increased TLB pressure and poorer spatial locality; this can lose.
- `down-tile16`: transpose codes and half scales within each 16-row tile at
  load. Same bytes and total extent; 20 planes of 16 code bytes per row, followed
  by 20 planes of 2 half-scale bytes per row. Subgroup paired lanes access long
  contiguous runs across rows. No new decode, accumulator, occupancy, input
  packing or lookup-table mechanism.

Production is wide64, hc-wide, ordered, rec-parallel. All packet97 native
composition dimensions are retained. Seventeen explicit startup views cover
production, both candidates, maximal packet97 corners, and both candidates with
each of packet99's six independent gate/up choices. Only the three isolated
views are proposed for performance screens; compatibility is not a speed claim.

## Gates

GNU and Intel each execute two fresh byte runs: full 2560x640 DOWN, 8/10 slots,
invalid routes, row offsets/tails, duplicate IDs with distinct inputs, NaN/Inf,
zero/subnormal activations; raw FP32 chains/tree and exhaustive loader scale
bits. Full-shape startup exercises actual allocation/admission and kernel
selection on both ranks, with only payload/backend mocked. Invalid selection,
short and misaligned DOWN allocations must refuse before compute. Offline BMG
assembly is compiler evidence only. Seals bind all evidence and binary bytes.

Device work is forbidden in this task. Prepare a single-card microbenchmark
using the actual production/candidate operation bodies, full 512-expert banks,
real receipt-bound route vectors, all source prompts/layers, and alternating
control/candidate order. Synthetic weight/input values are diagnostic only.
Require exact FP32/BF16/status/error results and <=0.85 candidate/control kernel
time overall AND in both order halves AND every route stratum before screens.
Do not fabricate routes if raw receipt payloads were not retained.

Each micro-qualified candidate gets a separate B production/candidate/production
bracket, then that same exact winner's A confirmation using the pinned shared
v4 wrapper. All 13 exact checks and unchanged acceptance are mandatory. Fresh
output names, 90-second gaps, no retries. Proposals only; temporary queue plans.
Records run on lane A, and no record chain is created or launched here.

Build <=500 MB; nice19, cores 8-15,24-31, Python -B, stdin closed, <=8 GiB
address space. One compiler through packet94's compile_turn.py. Retain compressed
byte receipts before deleting only this packet's fixture scratch. No services,
GPU, sudo, settings, memory fence, cache, swap, power, reboot or foreign kills.
