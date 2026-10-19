# Packet151: discarded sibling cost

CPU gates are being finalized for an **upper-bound diagnostic**. No GPU was
launched and no timing measurement is claimed. The record remains 58.798 tok/s.

This private tree starts from packet136's bundle8 source, through packet149's
vendored one-load harness. It retains the drain fix, native limits gate and
closed launch environment. Earlier packet trees and live queues are untouched.
The deterministic alternate is `(kept_token + 1) % vocabulary_size`; it is
not a draft second-choice measurement. The draft itself stays unchanged.

The candidate shares large dense and routed-expert weight loads using the lab's
packet68c paired accumulators, ported to bundle8's cached FP32 expert scales.
Each row keeps the original ordered reductions and BF16 stores. HC, small
projection tuples, fused shared-down and non-matrix sites currently use two
serial production submissions within the layer. **upper bound (partial M=2: HC/small tuples/shared-down/non-matrix serial).** Serial extra submissions can overstate sibling cost. This scope is sufficient to reopen packet132 at or below the threshold; a larger cost is inconclusive.

A private state image is recopied from the current prefix before each alternate
half, with separate scratch, recurrence, KV, PLE and host-history handling.
The extra preparation is included in half wall time. Candidate output is
always discarded. Snapshot exclusion, bank rotation, cancellation, request
reset and prepared-command lifetime require the integrated state gate.

The proposed diagnostic order is production / sibling / production / sibling /
production, with one model load. All views must pass the unchanged packet49
oracle and identical per-prompt proposals and acceptance. CPU arithmetic tests
cannot establish device equality. The analyzer refuses missing or empty half
and sibling timing streams, including in the smoke. It reports device event
sums separately from inclusive half wall time, token intervals and class-balanced
rates; cancelled halves are counted and the cost uses matched complete positions.

The fixed cost threshold is 1.952 ms. A completed, admitted measurement at or
below it permits packet132 policy work on packet114 independent text only.
Above it means “inconclusive upper bound; full M=2 needed”, never closure. No calibration or prompt selection uses the 12-prompt suite.

Disk planning is 240 MB per view, 1.2 GB for five views: at most three times
packet149's measured 402 MB bracket. The 25 GB device free-space floor stays;
CPU preparation stops below 30 GB. New builds stay below 300 MB and CPU
processes have a 4 GiB address-space cap. Compilation uses ops/compile_turn.py.

See [work note](../../../../notes/2026-10-19-own-runtime-packet151.md).
