# Gathered Winner Fusion And Markov Pair Closure

Date: **2026-07-18**

Status: **target winner/commit retained; target-local argmax and all tested
DSpark tiny-pair transports rejected**

## Outcome

The target verifier now selects the winning rank from the four gathered local
top-1 pairs and performs greedy rejection/bonus commit in one native SYCL
operation. The boundary is bitwise exact in 40 changing eager and 40 graph
cases on every B70. Captured latency falls from 16.998-17.415 us to
13.728-13.924 us. Three strict endpoint medians are
**79.122226 / 76.938576 / 79.750144 tok/s**, with a 79.122226 median-of-three,
36/36 fresh cache-zero requests, and 24/24 ordered exact canaries.

This improves the implementation's stability center over the promoted
78.287226 tok/s center, but it does not beat the public 80.820052 tok/s high.
Keep the fusion as a compositional win; do not submit another LocalMaxxing row.

Promoted component identity:

- vLLM `35ce4e8a62e6d553e1aadbe4f48eaf3e64c60e01`;
- XPU kernels `7936e0c4e9cb017cadbead3aac4122a784cc89a3`;
- four-card gate:
  `/mnt/fast-ai/bench-results/deepseek-v4-flash-xpu/native-gathered-pair-rejection-20260718`;
- endpoint:
  `/mnt/fast-ai/bench-results/deepseek-v4-flash-xpu/dspark7-gathered-pair-fusion-candidate-20260718T2130Z`.

## Rejected target-local projection epilogue

A native BF16 sharded-vocabulary argmax/packing operator passed 40/40 eager and
40/40 graph cases on card 0, but its captured 28.935 us was slower than the
25.530 us control. It was rejected before consuming the other cards or a model
load. The complete source/revert history is preserved as vLLM
`639599cfd`/`c27f9a5f9` and XPU `5eaf645`/`1e68774`.

## Rejected DSpark sharded Markov transaction

The next experiment kept W2 sharded, added each rank's local W2 bias, selected
a local top-1 pair, and exchanged only the four pairs instead of gathering the
full vocabulary. Native local and global operations passed 160/160 changing
eager and 160/160 graph comparisons per boundary across the four B70s. The
local eager boundary fell from roughly 94-102 us to 22.5 us and the global
boundary from roughly 84-88 us to 6.7-7.7 us.

The endpoint nevertheless regressed to **73.458134 tok/s** median with
61.531936 p10, about seven percent below the current implementation center. A
single strict suite was sufficient to reject it; two more suites would not
change the architectural conclusion. The flag remains default-off at vLLM
`06c5ef710` and XPU `917a9398d`. Evidence is under
`/mnt/fast-ai/bench-results/deepseek-v4-flash-xpu/dspark7-sharded-markov-argmax-candidate-20260718T2140Z`.

The arithmetic was not the problem. Generic tiny oneCCL collectives fall off
the optimized device path and erase the avoided full-vocabulary traffic. This
reconfirms the earlier tiny-pair rejection already recorded in
`2026-07-18-dspark-replicated-w1-record.md`.

## Process mistake and corrected next action

The handoff and W1-replication note already said that generic tiny-pair
exchange and pre-gather local add were rejected. Rebuilding the same class with
better local kernels supplied a stronger endpoint confirmation, but it should
not have been selected without first diffing the frozen rejected-boundary
inventory. The duplicate cost is recorded in `/home/steve/identified-mistakes/`.

Do not retry pair exchange through ordinary c10d/oneCCL. The only justified
continuation is a fixed-address, topology-specific TP4 max/token transport
with a hardware gate that proves it beats the existing full-width gather. This
is a first concrete communication primitive for the fixed Intel decoder shell,
not another framework collective toggle.

## Fixed-transport follow-up and endpoint rejection

Three fixed-payload transport variants were then measured under the same
four-card topology:

- Raw Level Zero IPC with remote-atomic readiness timed out and returned
  incorrect results. The existing raw IPC all-reduce control failed under the
  same runtime, confirming that this B70/runtime combination does not provide a
  reliable remote-notification primitive for this decoder.
- Parent-brokered Level Zero IPC with a process-side barrier was exact over 80
  changing epochs and reduced the slowest seven-step component from 1.749059 ms
  to 1.249131 ms. This cleared the 0.50 ms admission floor, but required an
  awkward broker and synchronous host coordination.
- A direct process-shared C++ barrier with synchronous D2H/H2D copies was also
  exact over 80 changing epochs. Its isolated seven-step component fell from
  **1.533740 ms to 0.137513 ms**, a **1.396227 ms/cycle** saving.

The strongest component candidate was integrated behind
`VLLM_XPU_DSPARK_HOST_MARKOV_ARGMAX=1` at vLLM `6a77e5940` and XPU kernels
`d10262ea7`. It passed 12/12 ordered exact canaries across the pre/mid gates and
both strict suites were fresh and cache-zero. Endpoint performance nevertheless
regressed to **74.840996** and **75.764457 tok/s** medians. Acceptance remained
in the same approximate range as the control, so the loss is attributed to the
host-synchronous barrier serializing the pipeline and disturbing device/host
overlap, not to a draft-quality collapse.

Keep the host transport default-off. It is useful proof that the payload and
selection arithmetic are cheap, but an isolated collective replacement is not
a decoder win if it blocks every TP rank on the host. The only viable reopening
now requires a device-resident transport built on a proven communication
protocol, or removal of the exchange by a larger fused/replicated transaction;
raw remote atomics, ordinary tiny oneCCL, and host barriers are all closed.

Evidence:

- raw IPC failure and control:
  `/mnt/fast-ai/bench-results/deepseek-v4-flash-xpu/tp4-ipc-max-token-20260718`;
- valid brokered IPC gate: `host-barrier-valid.json` in that directory;
- valid shared-host gate: `host-shm-valid.json` in that directory;
- endpoint:
  `/mnt/fast-ai/bench-results/deepseek-v4-flash-xpu/dspark7-host-markov-argmax-candidate-20260718T2215Z`.

## Faster native build iteration

Rebuilding the full XPU package attempted 676 unrelated attention objects.
For sampler-only edits, compile only
`topk_topp_sampler.cpp.o` and `torch_bindings.cpp.o`, then execute Ninja's
generated final `_xpu_C.abi3.so` link command and copy the extension into the
package. This reduced the edit/build loop to about one minute. The procedure
must remain source-hash and ABI checked; it is an iteration aid, not a distinct
runtime identity.
