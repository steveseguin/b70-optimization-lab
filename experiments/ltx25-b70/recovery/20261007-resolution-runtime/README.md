# 640×384 reference/runtime components — integration in progress

These are **CPU-tested components, not a prepared or GPU-qualified runtime**.
No larger model request has been submitted. The immutable qualified packet99b,
model, original references and failed experiments remain unchanged.

The reviewed [request plan](../20261007-resolution-reference/README.md) fixes
three original fixtures, native BF16, original8+3 steps, accepted text window,
23/25 placement,25frames and640×384. Its plan hash is
`307ff7547b8275c75d7f642673174cac11a45e0d7bc0041958a834544faa8745`.
W1 is the first optimized scheduling configuration. Native sampling/decoding
must run before optimized sampler capture, with independent repeats; the
accepted text encoder remains graph-sharded. This is not an all-eager oracle.

Implemented components:

- `geometry_overlay.py` transforms exactly seven hash-pinned source paths,
  retaining historical guards and adding an explicit phase-bound comparison
  mode. [Source contract](source-contract.md).
- `session.py` admits only exact registered graphs with new execution IDs,
  enforces ordered native/optimized phases, records barriers, and permanently
  halts after a failure. Completed pipeline tails may be released only after
  their identities are durably recorded; unfinished work cannot be cleared.
- `executor_guard.py` delays Comfy's success event until post-request checks
  and the authority's durable completion succeed. A refusal becomes a failed
  history entry. Halt-receipt write failure cannot kill the prompt worker.
- `runtime_observer.py` reads the actual registered node modules and pipeline
  jobs, including completed but uncollected tails. Importing a separate source
  mirror cannot stand in for the active node's ownership state.
- `reference_gate.py` rereads six native executions and all four tensor files,
  verifies distinct executions and exact repeat pairs, and exclusively writes
  a reference receipt. Reading the receipt reconstructs its proof from retained
  artifacts. [Reference contract](reference-gate-contract.md).
- `setup_gates.py` checks actual text-window, coverage, chain/freeze and decoder
  verdicts. A successfully completed setup prompt can still contain a negative
  result. Seeded native/replica decoder consistency remains distinct from real
  reference-clip equality; the old internal speed-only labels are preserved.

`native_safety.py` and its concrete adapter, finite client, and candidate parity
gate are being integrated separately. Required work before device execution:
complete source/launcher closure; real resident-object/memory observations;
guard installation before any native request; exact setup schedule and phase
transitions; reference/candidate receipt wiring; bounded writes/captures and
fresh name/index reservation; one finite server lifecycle with fault halt,
graceful shutdown and postflight. A component test is not a launch admission.

The failure guard must prevent estimated/actual native VAE OOM from reaching
automatic tiled decoding or its cache-flush fallback. Pre-native physical free
thresholds6/6/2/7GiB include provisional allowances, not proven full-model peak
bounds. Actual resident weights and encoder graphs must already be present.
Keep the50GiB disk reserve, fresh4GiB write allowance and32-capture bound.

Tests are adjacent `test_*.py` scripts, run with `python3 -B` individually.
Synthetic schema controls are labeled as such and are not model measurements.
No throughput or visual-quality result is claimed by this folder.
