# Packet138 — cross-layer expert prefetch, phase 1

The coordinator completed the lane-B capture on October 18. **All 624 captured
output tokens match their references.** CPU replay matches every same-layer
router logit and route across 27,648 rows, with no mismatches.
The one-card record remains packet58p's 26.228599 tok/s. No phase-2 design is
admitted: the completed real-capture simulation fails the preregistered gain
and causal-traffic gate. All 45 cases have late copies. The most favorable
projection is +5.75%, but it still has 248 late copy batches; the same predictor
loses time under less favorable assumptions. [Full results](RESULTS.md),
[phase-1 closeout](phase1-closeout.md), [do-not-repeat entry](DO-NOT-REPEAT.md).

The [new proposal](../../ops/lane-queue/proposed-p138-capture-B.txt) is for the
coordinator's lane B (physical cards 2+3), one TP2 load. The external coordinator
queued it after preparation; this task did not edit the live queue. Plan
5–15 minutes with a 3,600-second watchdog (4× the upper estimate). The shared
lane lease, fault handling, device mask, memory admission and cooperative drain
remain in force. `screen-packet138-capture-B.service` is the actual lanequeue
unit name. Both intercepted native launches check getrlimit and closed masks;
CPU resource caps are never installed by imported runtime modules.

## Fixed capture

The first 48 generated tokens of all twelve packet55 **test** prompts, covering
six classes. A separate incident-retrospective sanity request checks every token
against packet49 and is excluded from prediction/cache analysis. Each held-out
token must match packet55's pinned saved target output. Those twelve references
are device reference evidence under the same arithmetic, not independent CPU
oracle certifications. Packet49 is verified through the original
`oracle-binding.json` and `shared_oracle.py`; its external symlink is not flattened
into a source map. No prompts are fitted or selected by observed prediction quality.

The entry unit and route wrapper are copied from frozen packet100b. All original
kernel objects and target arithmetic stay unchanged. The two parent data symlinks
are preserved. The copy adds only ordered diagnostic copies at actual target
router, DOWN and layer-combine sites. Only normally accepted HALF work qualifies;
wrong speculative work is overwritten by redo. No host read or wait is added
inside a token. Flush happens once after each exact request. Full state dumps
remain omitted and the new diagnostic buffer alone is excluded from rollback.

Every rank file has 48 steps × 24 layers × **26,744 bytes**:

| Offset | Bytes | Content |
| --- | --- | --- |
| 0 | 120 | Ten unchanged DOWN routes, uint32 expert/begin/count |
| 120 | 5,120 | Current layer router input, 2,560 BF16 values |
| 5,240 | 20,480 | Layer output residual, four streams × 2,560 BF16 values |
| 25,720 | 1,024 | Actual router logits, 512 BF16 values |

Metadata binds rank, step, absolute position, input token and SHA256. Actual
logits are BF16, as consumed by the unchanged route kernel. A full residual has
four hyperconnection streams: none is silently substituted for a single hidden
state. Thirteen requests produce **801,036,288 raw bytes**, leaving room for
logs within the hard 1 GB capture cap. Two 30,809,088-byte device buffers are
included in the copied allocation ledger. No model bytes, precision or KV change.

## CPU evidence and reproduction

Prefix CPU commands with `nice -n 19 taskset -c 8-15,24-31 python3 -B` and redirect
stdin from `/dev/null`. Run `prepare_inputs.py`, `build_engine.py`, `full_shape.py`,
`cpu_gate.py`, `argument_gate.py`, `seal.py`, then `queue_plan.py`.
All compiler calls use the shared `ops/compile_turn.py` turn. Builds remain
below 300 MB and CPU memory below 4 GiB; root must have at least 25 GB free.
The argument probe needs unlimited virtual address space to reproduce the native
exec gate; it allocates only small CPU metadata and reports peak RSS.

Both compiler builds and two fresh synthetic byte checks per compiler pass.
Both ranks pass actual full-size allocation and capture-site binding with CPU
payload/backend mocks. Twelve Python tests cover corruption, identity, route
uniqueness, independent inputs, memory bounds, pending evidence, watchdog, unit
naming, and interrupted drain. The real worker reaches both intercepted native
execs with unchanged resource limits. The temporary queue plan passes. These
checks establish preparation, not device output equality or speed.

Only the coordinator may consume the proposal. After clean release,
`capture_inputs.py` binds the complete capture; analysis requires those real bytes.
The CPU replay first reproduces same-layer router logits and routes
exactly, then reports next-layer recall at widths 10, 12 and 16. A residual prediction
is available later than the router-input prediction and gets only its remaining
causal transfer window. Wrong and late prefetches cost traffic too.

Proceed to phase-2 design only with at least +3% projected gain over the modeled
58v control throughout the registered sensitivity range, with traffic fitting
every assumed causal window. Missing capture remains pending. The 58g/58p
receipts have no measured per-layer clocks: assumptions are explicit and a
conditional design recommendation is not a device performance qualification.
Prediction and simulated rates are diagnostic projections, not measurements or
a benchmark. See [CPU analysis and assumptions](ANALYSIS.md).

Credit: pre-gating and cross-layer expert prediction ideas from MoE-offloading
literature; independent lab implementation. Existing 58i frequency-prefetch and
58h MTP closures remain. [Preregistration/work note](../../../../notes/2026-10-18-own-runtime-packet138.md).
