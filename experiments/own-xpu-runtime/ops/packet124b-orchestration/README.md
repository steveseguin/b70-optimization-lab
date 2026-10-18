# Packet124b orchestration — unchanged bundle7, repaired K2 projection

This prepares a fresh chain for the identical packet118 bundle7 selection,
with repaired cooldown waiting. It starts nothing. Exactly one composition is
sealed now; no micro lever is enabled.

The evidence reader validates the original packet118 twelve-prompt smoke and
control / candidate / control composites on both A and B. Each candidate must
beat both controls by at least 1.0%, all thirteen checks must be exact, control
acceptance must repeat, and candidate acceptance must agree across lanes.
It rereads actual receipts, not packet118's ready boolean. The copied decision
fixes the original output names. Parent chain status is never consulted:
a failed or finished bundle7 chain does not block this fresh chain.

Selection JSON, memory plan, dispatch and both runtime binaries must match
bundle7. That permits reuse of its composite evidence; the drain fix earns no
new speed claim. The chain still must pass every independent quality window.
The prefix remains 80,128 rows, preregistered on non-benchmark text. Never tune
it from benchmark data. Submission notes disclose it; strict512 remains false
for the inherited, explicitly disclosed 128-token scope.

Run CPU commands from the repository root with `nice -n 19 taskset -c
8-15,24-31 python3 -B`, stdin `/dev/null`:

1. `ops/packet124b-orchestration/prepare.py` (under `experiments/own-xpu-runtime/`)
   binds the fixed decision, local chain seal and input/chain plan.
2. `launch_limit_gate.py` intercepts both real rank exec points for smoke,
   composite and chain; the isolated old 8 GiB cap must fail. Positive probes
   retain all inherited limits and unlimited address space.
3. `orchestrate.py` runs CPU policy, drain and complete submission replay tests
   and writes a source-bound `cpu-tests.json` and current `ready.json`.
4. Later, only `orchestrate.py --evidence-only` is needed to reread evidence.
   It performs no build, device run or CPU test campaign.
5. The coordinator may use the command in `ready.json` only after
   `verify_ready.py` succeeds. This task does not run it.

Both `scripts/check_drain_fix.py` scans are hard readiness gates, over the
entire new bundle and this orchestration directory, including ignored copies.
The deterministic regression proves the original clock-crossing failure.
The chain explicitly imports its fixed local implementation. No manual
other-lane pause is needed for cooldown safety. All existing lane, fault,
teardown, VRAM and exclusive whole-host timing reservations stay in force.
The fresh chain directory is `stage2/packet124b-record-bundle/build/device-cards01-a`.
An existing folder is a refusal, never an implicit resume or automatic retry.
`ready.json` is the current result. `p124-ready.json`, `prepare.log` and
`ready-refusal.log` retain earlier preparation-time refusals; they are history.

`prepare_submission.py --chain <path>` prepares a completed qualifying chain's
portable evidence and payload. `submission.py` supplies the complete shared
submission CLI. No submission is performed during preparation.

## Adding one micro-qualified dimension

See [disabled slots](../../stage2/packet124b-record-bundle/extension-slots.json).
A short follow-up can do the following without changing any frozen parent:

1. Read both original micro receipts and the lane's declared gate. Copy the
   successful source delta, fixed decision and original-byte receipts into new
   local inputs. A stored `passed` flag is insufficient. Packet123 currently
   has no admitted candidate; packet120 requires a new memory plan.
2. Preserve the BASE view **and every file in its sealed source map**. Its
   top-level Python/native files are bound by the startup receipt; editing
   `bundle_selection.py` in place would invalidate BASE. Make a separate local
   source/build closure for the added composition (a sibling packet124 extension
   tree keeps the inherited relative path layout). Copy the small builders into
   that closure, reuse hash-checked immutable objects, and register exactly one
   selection there. Port only the qualified kernel/selector dimension and its
   real-shape/startup consumer checks. Keep target arithmetic, BF16 KV, oracle
   and prefix unchanged. Admit disk space before copying; keep the CPU build
   under the follow-up's declared cap.
3. Build serially through packet94's `compile_turn.py` only if native source
   changes. Run the changed operator's GNU/Intel exact-byte gates, full-shape
   allocation checks and every startup/KD path for the new composition. Extend
   the submission identity and its synthetic replay before sealing that view.
4. Give the new composition its own decision, fresh outputs and smoke/matched
   composites. Replace the BASE-only `jobs`/`evidence_view` rule for that
   decision; never relabel original bundle7 receipts as evidence for new native
   bytes. Snapshot this BASE orchestration before updating its policy, since
   its source hashes are part of the BASE chain receipt. Keep the unchanged
   BASE rule available in that snapshot. Disable execution until all
   declared device and CPU gates pass.
5. Rerun `prepare.py`, the actual exec-limit interception, both drain scans and
   `orchestrate.py` tests. Preserve the BASE seal and old evidence. After the
   new composite results arrive, only the evidence reader should remain.

The inherited `composite_screen.py` entry refuses BASE device execution; no new
composite jobs are required for an identical copy. No live queue is edited.

## Packet124b all-window argument gate

Run `argument_gate.py` after preparation and before `orchestrate.py`. It must
pass K0, K1a, K1b, K2, W0p, KD, W2m, WS, WSs, WS128x and WS128: 31 intercepted
native launch arguments, including both KD device owners and its CPU reference.
The actual window parser, bundle selection, memory configuration, oracle/input,
suite cap and retention checks run. Earlier device receipts, available host
memory, lane admission and loader probes are synthetic; their real admission
remains mandatory at device launch. The CPU gate cannot authorize those states.
Python hashes replace the `sha256sum` subprocess with identical SHA256 checks.

K2's real `pin_production_dispatch` and `p49d_k2.measured_coverage` replay the
retained packet124 receipts in scratch. The frozen packet124 implementation must
fail at its strict selection gate, while the corrected copy must pass all timing,
coverage and dispatch validations. `verify_ready.py` requires this source-bound
gate, the unchanged getrlimit exec guard, drain checks and completed CPU tests.
Later refresh uses only `orchestrate.py --evidence-only` and `verify_ready.py`.
