# Screen v4 lanes

CPU-prepared wrapper for future packets. No GPU, model, service or live chain
ran during preparation. This copies `screen/v3-packet64-lanes` and carries
packet70's private screen change that releases lanes before reporting. Existing
packets, screens and ops files are frozen and were not edited.

## Refused teardown still stops this worker's ranks

`conditions.Teardown` accepts a refusal cleanup callback. Any error after the
shared flock is acquired, including an undrained previous record, malformed
state, missing cooldown data or a failed state write, runs that callback before
releasing the flock. `tp2_worker.drain` sends the existing cooperative `!` stop
through its own transport, then calls the existing 65-second bounded close.
It sends no process signal and never touches another worker's ranks.

The original refusal is raised after cleanup. Local `run/teardown.json` records
`drained: false`, `gate_refused: true` and the reason, plus confirmed local exit
or the stop error. The other lane's shared record remains unchanged. A refused
gate is never converted into a successful run, even when our ranks exit safely.
There is no second drain attempt for this refusal. If an owner does not exit
within the bound, the inherited worker supervision remains alive for the
coordinator; it does not hard-kill the owner or silently abandon it.

This handles admission refusal *under an acquired flock*. An OS failure that
prevents opening/acquiring the lock cannot provide a serialized drain permit.
No software wrapper can guarantee an unresponsive device exits; the bounded
stop and retained-owner evidence remain the recovery contract.

## CPU reports cannot poison a completed device phase

The worker stages exact request receipts, then drains. The parent verifies the
drain receipt, worker exit and process identity, checks device clients and fresh
kernel postflight, and releases both the lane reservation and legacy v3 lane
lock. Only then does it read/validate report inputs, aggregate results and write
summary files. Report/validator failures return failure and record
`report-failure.json` with `device_failure: false`; they leave no lane marker,
fault latch or undrained teardown record. They never turn into a quality pass.

Pre-drain failures, unproven teardown and failed postflight remain conservative.
Per-request exact-output checks still run in the worker. The incident64 plus
12 x 128 request sequence and receipt bytes are unchanged. Summaries retain
v3's compatible schema; window/lease and wrapper seal identities identify v4.

## How new packets adopt v4

1. Prepare the new packet's binary/selection/dispatch seal and matching placement
   audit. For a lineage/placement already admitted by this wrapper, point its
   new screen jobs at this directory's `screen.py`, with that packet's
   `--lineage`, `--seal`, `--binary` and `--dispatch`. Give each job a fresh
   output below this directory's `evidence/`. Both A and B are supported;
   placement, timing and paired-screen options remain available.
2. Run its `--plan` commands on CPU using `nice -n 19 taskset -c 8-15,24-31`.
   A new lineage or placement may need a private copy: retain the inherited
   seal and placement checks, add the packet's matching audited selection, adapt
   paths in a **new** directory, rerun the CPU tests and produce a new seal.
   The v4 seal does not authorize modified copies or unregistered placements.
3. Verify v4 before handoff:
   `nice -n 19 taskset -c 8-15,24-31 python3 -B experiments/own-xpu-runtime/stage2/screen/v4-lanes/cpu_seal.py --verify`.
   The active seal is `wrapper-seal.json`, identical to
   `placement-validation/wrapper-seal.json`. `predecessor-wrapper-seal.json`
   is historical provenance only.
4. The coordinator supplies the current fault-review receipt and authorized
   window, keeps the existing lane affinity/systemd/memory/ownership rules,
   and launches only the new jobs. Existing queued jobs keep their old wrappers.
   Keep the shared v3 teardown root, lane locks and coordination root: changing
   their location would break serialization with running packets.

For a future chain, see [CHAIN-PATCH.md](CHAIN-PATCH.md) and the unapplied
[patch](chain-window-drain.patch). The inherited `integration.patch` and
`screen-integration.patch` are v3 reference fixtures, not v4 adoption commands.
`placement-jobs.txt` retains the eight inherited CPU placement examples with
fresh v4 output paths. The current packet61x example refuses because its
`window.py` differs from the historical placement audit. That refusal is retained
in `validation-attempt1/inherited-plan-refusal.json`; no audit was silently
repinned. These examples do not authorize device execution.

## CPU verification

From the repository root:

```bash
nice -n 19 taskset -c 8-15,24-31 python3 -B -m unittest discover \
  -s experiments/own-xpu-runtime/stage2/screen/v4-lanes -p 'test_*.py' -v
```

The seal builder runs the complete suite and retains its log, source closure,
build receipt and byte-identical request fixtures in `placement-validation/`.
The tests use mocked device interfaces and temporary CPU children only. One
refusal test uses the actual transport stop/close methods on two pipe-polling
CPU children, checks the flock during stop and wait, and proves a third child
is untouched. No test reads model weights or launches a native device binary.
Device validation and speed remain unmeasured.
