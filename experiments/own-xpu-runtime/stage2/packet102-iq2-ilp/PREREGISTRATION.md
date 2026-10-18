# Packet102 preregistration

Question: can independent IQ2 grid loads overlap without changing FP32 values
or sums, and can one subgroup reuse activations between gate and up?

Source: copied packet97 bundle; `copy-lineage.json` records original bytes.
New code: `p102_expert.hpp`. No existing packet or shared wrapper is edited.
Control: wide64 plus halfcache (`exp-halfcache`), `iq3-p49-split32-v1`.
B1: `exp-lookup-batch2`, `exp-lookup-batch4`.
B2: `exp-gateup-shared` (batch one, independent gate/up chains).
B3: `exp-lookup-batch2-shared`, `exp-lookup-batch4-shared`.

No table movement, compressed KV, reassociation, new weights or changed down.
GNU and Intel compare raw chains, trees and output bytes in fresh repeats.
Offline linked BMG assembly must show earlier independent lookups and no spills.
Full-size CPU startup must exercise actual allocation and capture paths on
both ranks, including deliberate extent/alignment and selection refusals.

Micro is built and proposed first. Full production shape, forty alternating
pairs per candidate, poisoned correctness destinations, exact output/status,
15% lower kernel time overall and in each ordering. Only a passing candidate
may reach its own v4 B control/candidate/control bracket, then A confirmation.
Frozen v5 cannot switch these kernels (packet98b). Records run on A.

All execution in this preparation is CPU-only, nice 19, CPUs 8-15,24-31,
8 GiB address-space cap, packet94 serial compiler turn, build below 300 MB.
No queue enqueue, services, GPU initialization or host-setting changes.
