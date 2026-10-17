# Packet 55 independent preparation review

October 17, 2026. Read-only source review by a separate Codex agent, with this
note as its only edit. No GPU, model payload reads, builds, benchmark runs,
services or host changes were performed by the reviewer. This reviews prepared
measurement code; it does not certify unrun device windows or one-card speed.

## Findings during review

- **Simultaneous routes must keep selected cache slots alive.** The first
  analyzer processed ten selected experts as unrelated sequential accesses. An
  early miss could evict a resident expert selected later in that same route,
  creating a false miss. `analysis/locality.py::LayerCache.route` now snapshots
  misses and protects the complete selection during admission. Both training
  and evaluation use it. The analysis owner added and ran LRU/LFU regression
  cases with residents `[1,2,3]` and routes `[4,1]` / `[1,4]`; both charge one
  miss. The retained nine-test CPU receipt covers this correction and a full
  synthetic converter-to-analyzer contract with seven binding-tamper refusals.
- **A 256-token cap is not proof of 256 generated tokens.** The route window,
  converter and analyzer now derive `requested_scope_complete` from actual
  counts. Natural early EOS is preserved without suppression or retries, but
  cannot be described as a completed 24 × 256 collection.
- **Speculative commands can stop before their last layer.** Final review
  found that a newly added converter check required all 23 rank-0 layers for
  every command. Packet49c legitimately cancels a speculative prefix at any
  launch after a verified mismatch. The corrected converter binds native
  timing receipts, permits ordered speculative prefixes only when marked
  cancelled, and uses uncancelled commands for committed-position coverage.
  The analyzer's nine-test receipt now includes a five-layer cancelled prefix
  and refusal after timing-file tampering. A route logged just before
  cancellation is observed routing demand, not proof that all selected expert
  kernels completed.

## Reviewed conclusions

The CPU vector lanes represent separate output rows. Each row preserves the
eight-value logical lane order, separate FP32 multiply/add, adjacent SG32
reduction, gate/up BF16 boundaries, normative deterministic SiLU and final
BF16 down output. The reference fixtures use packet49c's production compact
IQ2_S/IQ4_NL arithmetic and its original IQ3_S layer-2 path, plus the frozen
packet46 output digest. The retained corrected receipt records two equal
fresh-process runs with 54,001 checks each. This is CPU fixture equality;
actual GPU comparison and device exceptional status behavior remain open.

The CPU benchmark distributes row tiles across pinned workers, so 4/6/10
miss batches can use more workers than experts. It includes team/barrier,
input and output handling in measured dispatch latency, and calls its rate
packed bytes processed rather than DRAM bandwidth. The 16-thread case is
explicitly 12 physical cores plus four SMT siblings under the admitted CPU
set. Its quiet-window acknowledgment covers other packets; the shared lock
alone cannot exclude packet49d.

The H2D benchmark requests a native copy-only queue and separate same-device
compute queue. It verifies changed payloads outside timing and brackets copy
work with device timestamps. Route-to-resident includes list preparation and
completion; pageable-bank staging is correctly excluded and remains an added
design cost. The enclosing host wall interval supports the documented
envelope-overlap lower bound without comparing clock epochs. Synthetic compute
overlap does not qualify overlap with production expert work. Selected-card
PCI checks, passive ownership admission, bounded allocations and graceful
retention on uncertain completion are present. Hardware support and actual
timings still require the coordinator's window.

The route overlay copies existing router output IDs/probabilities after
submission and drain; it does not rewrite arithmetic kernels. All instrumented
request timings are diagnostic. The planned sanity request binds its token
comparison to the packet49 oracle receipt and result hash. Its routes are
separate from calibration input. The converter preserves repeated speculative
visits and checks complete committed layer/position coverage. GPU execution is
still needed to establish the planned token equality and actual route coverage.
The retained CPU smoke compares two fresh synthetic engines, each processing
two requests across a reset: tokens and guesses match, each diagnostic request
logs 14 routes including two draft routes, and 206 target boundary buffers
plus ten draft buffers match. It does not substitute for the full-model gate.
Native compilation is complete. The launch gate now verifies the source-closure
record before launch: binary and build-receipt hashes, tooling, prepared input
bundles, 133 native and 126 host project dependencies. This includes the
injected `kernel_guard.hpp` outside the copied tree and private host validation
headers; the guard is also tied to packet49c's retained compilation receipt.
The documented clean-environment coordinator command agrees with the runner's
parser and the inherited controller's 256-token/context bounds.

The analyzer trains on twelve independent prompts, resets the trained snapshot
for each of twelve held-out prompts, keeps benchmark tokens out of training,
charges preload and prefill separately, and counts repeated speculative work.
All policies explicitly use fixed per-layer quotas; these results must not be
presented as a global eviction-policy experiment. Payload and allocated slot
bytes are distinct, and layer 2 uses its larger expert size. The resident draft
is reported separately from target cache demand.
Pure CPU misses do not refill the GPU cache: the frozen static cache is the
direct CPU-only scenario. Adaptive LRU/LFU admission requires a paid transfer
or a separately specified hybrid. Simulating admission for every observed
router, including a subsequently cancelled layer, can improve later hits;
that scenario is not a universal upper bound for other cancellation policies.

`ONE-CARD-FEASIBILITY.md` keeps unknown GPU, mailbox and contention costs
pending. Its CPU, streaming and hybrid equations express explicit overlap
assumptions, charge same-card draft work, and avoid turning the two-card speed
into a one-card prediction. The first proposed streaming layer is an exact
control implementation, not a measured winner.
Equal expert byte counts do not imply equal serialization: the CPU kernel
reads raw GGUF rows, while ordinary packet49c GPU experts use the compact
layout. Streaming must pay staging/repacking or explicitly admit a prepacked
bank and its startup cost. The revised feasibility document leaves those
costs pending and does not assume duplicate full host expert banks fit.

## Remaining launch conditions

The route runner correctly refuses by default because packet49c's official
MTP weights are outside the user's admitted IQ3 directory. The documented
source exception needs the owner's decision before the coordinator can enable
that window. This review does not grant it. Route source/binary preparation
has passed; its identity gate is required again before launch. The selected
cards and host memory must be admitted by the coordinator, and CPU throughput
must run only while all GPU windows are stopped.

No remaining source-level blocker was found in the reviewed CPU, H2D,
route runner, corrected converter/cache analysis or feasibility formulas.
Source review does not replace the pending device, throughput, coverage
and end-to-end quality gates.
