# Packet133 CPU preparation and coordinator handoff

Bundle8 is bundle7 plus packet130 suffix interleave. There are exactly two
sealed selections, with an explicit mapping from public `interleave` to the
unchanged native `layer-interleave` value. The previous two-card record remains
58.223834 tok/s, `cmvdx8urg0068rf01vvb32bcs`; this preparation claims no gain.

`copy_bundle.py` copies frozen packet124c with symlinks intact. Its audit uses
`find -type l` and retains all 182 targets, including the oracle authority.
Native source changes are the exact packet130 files in `inputs/suffix-native.json`.
Its already-qualified v5 GNU/device binaries are copied byte-for-byte, and
`reuse_build.verify_native()` checks their full CPU/source closure and both
native selections. The local CPU byte fixtures run afresh twice under GNU and
Intel; local full-size initialization and all 22 startup paths run afresh.

`argument_gate.py` and `queue_gate.py` are hard requirements: eleven real
Python window paths, 31 intercepted native argv lists, the retained K2 replay,
old-code refusals, twelve real input preflights, six real oracle subprocesses,
prefix admission and malformed-receipt refusals. Synthetic receipts exist only
in disposable CPU scratch. Device execution is intercepted and cannot qualify
an output or a speed.

`ready.json` stays false until a composed twelve-prompt 64-token smoke and both
v5 brackets pass. Lane B reads packet130's registered `device-v5-B`; lane A
reads this packet's `v5/evidence/device-v5-A`. The reader validates original
artifacts, native identity and boundaries, and recomputes both candidate rates
against every control. Every candidate repeat needs at least +0.5%; the three
controls must stay within 3%. Selections and per-prompt acceptance counts must
match across lanes. Missing evidence refuses. No packet124c chain outcome or
packet118 composite substitutes for these gates.

The single [proposed lane-A bracket](../lane-queue/proposed-p133-v5-A.txt) is
planned on a temporary copy. It is not in a live queue. Estimate: 12–20 minutes;
watchdog: 80 minutes. `stage2/packet133-record-bundle/v5/bracket_job.py --kind
smoke --lane A` is the separate composed smoke entry; its registered output is
`v5/evidence/device-smoke-A`. Both modes require coordinator authorization,
a current fault-review receipt and source-bound CPU preparation. The driver
embeds its closed environment. No caller-supplied library variables are needed.
The bracket's initial smoke prerequisite is the already-qualified identical
packet130 candidate smoke; the local composed smoke is independently mandatory
before the chain.

Preparation commands, each under nice19, CPUs 8–15/24–31, Python `-B`,
`OMP_NUM_THREADS=2` and stdin `/dev/null`:

1. Bundle: `reuse_build.py`, then `cpu_prepare.py cpu_gate.py prepare_chain.py full_shape.py startup103.py`.
2. Here: `seal_view.py`, `proposal_plan.py`, `prepare.py`.
3. `argument_gate.py`, `launch_limit_gate.py`, `orchestrate.py`, `final_audit.py`.
4. Later, after device receipts arrive: only `orchestrate.py --evidence-only`
   and `verify_ready.py`. Changed sources invalidate the CPU receipts.

The fresh chain command is embedded in `ready.json` and calls `device-entry.sh`.
That entry and `chain_entry.py` require verified readiness before the queue
starts. Existing whole-host timing, faults, graceful teardown and getrlimit
checks stay in force. No automatic retries, services or live-queue edits occur
in preparation.

`prepare_submission.py --chain <registered finished chain> --output <fresh
submission folder>` builds the portable result and attestation.
`submission.py --help` exposes the complete submission CLI. The notes name the
superseded record, exact oracle, quantized model, BF16 KV, fixed non-benchmark
prefix, and honest 128-token scope (`realistic_final_gate.passed=false`).
Only a complete faster qualifying chain can produce a submission; nothing is
posted by preparation. Packet131 remains disabled and needs a future packet.
