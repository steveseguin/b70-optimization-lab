# MTP1 Subgroup-Split GEMM1 Incremental Upper-Bound Closure

Date: **2026-07-17**

Status: **closed before implementation against the promoted record baseline**

## Decision

Do not build or integrate the proposed subgroup-split/SLM-exchange paired
GEMM1 producer as a standalone successor to the 63.851301 tok/s record.

The design remains technically coherent and could repair the local-route
occupancy failure of the rejected dual-accumulator producer. It cannot,
however, clear the frozen `0.50 ms/cycle` every-route gate incrementally against
the already-promoted route-direct compact chain.

## Why The Earlier Recommendation Changed

The earlier producer recommendation was made before the QNorm-M2 plus
route-direct portfolio became the qualified record. Its hardware comparisons
used the generic route path as control. Route-direct N64 is now enabled in the
record and already owns most of the all-remote launch/scheduling saving.

Preserved measurements against the generic control are:

- current route-direct all-remote saving: about 0.397-0.414 ms/cycle;
- rejected paired fused-GEMM1 all-remote saving:
  - 0.520384 ms/cycle at GRF256;
  - 0.494581 ms/cycle at GRF128.

The all-remote pattern contains no local gate/up arithmetic. A subgroup-split
producer can improve register pressure only when local expert work exists. On
all-remote it can remove only the already-small activation/launch tail.

Even the non-conservative cross-experiment subtraction of the best fused row
and lowest promoted route floor gives only:

`0.520384 - 0.397270 = 0.123114 ms/cycle`

That is less than one quarter of the required 0.50 ms/cycle. The fresh
post-portfolio trace independently measures the entire routed activation at
only 0.079980 ms/cycle. No plausible SLM implementation can create the missing
all-remote saving because the projection arithmetic it improves is absent.

## Preserved Design

The unbuilt design is retained for a future larger package or specialized
decoder:

- one 64-thread workgroup;
- SG0-SG1 compute an N32 gate fragment;
- SG2-SG3 compute the matching N32 up fragment;
- each thread owns only one B payload and one FP32 accumulator;
- rounded BF16 up fragments cross a roughly 640-byte padded SLM buffer;
- gate owners reproduce exact clamp -> BF16 SiLU -> BF16 multiply;
- ordinary duplicate-route ownership and BF16 rounding remain unchanged.

Its source basis would have been XPU `c069ed8`. No source change, build, GPU
probe, service load, or LocalMaxxing submission was made for the subgroup-split
variant.

## Next Work

Move to the current fixed-M2 producer/allreduce/consumer boundary around the
87 ordered TP4 reductions. The normal-run scope remains roughly 8-9 ms/cycle,
and only 5.75 us saved per boundary is needed to clear 0.50 ms/cycle. The first
step is an exact M=2 real-shape upper-bound harness and captured current-record
tensors. Do not reopen generic oneCCL flag, clone, LL-geometry, recursive
doubling, polling-resident-consumer, or compact in-ring MHC experiments.
