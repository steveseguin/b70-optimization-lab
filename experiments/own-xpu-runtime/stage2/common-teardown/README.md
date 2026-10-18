# Teardown after a Python failure

[Version 1](v1/teardown_on_error.py) is a copy-forward helper. A failed window
can record a clean drain and release its own lane while still failing the
experiment. Existing packets, screens, seals and live coordination are untouched.

The helper requires reaped children, the existing isolation/client checks and
clean kernel checks. A zombie, reused PID, live child, unreadable process state,
missing proof or new fault keeps cleanup unconfirmed. It never kills a process,
removes a fault latch or recovers another owner's stale marker. The original
error is re-raised; a nonzero return remains nonzero.

To adopt in a **new, unsealed copy only**:

1. Copy `v1/teardown_on_error.py` beside the new wrapper's Python files.
2. For a packet124b-derived chain, apply
   [chain-integration.patch](v1/chain-integration.patch) to the new copy. For a
   v4-derived screen, apply [screen-integration.patch](v1/screen-integration.patch)
   to the new copy, including its worker and `conditions.py`. Use `git apply
   --check` first, with paths directed to that new copy. Never apply at an
   existing packet or screen path.
3. Run the CPU regressions below. Run `scripts/check_teardown_on_error.py
   NEW_COPY --kind chain` (or `--kind screen`) to check the helper **and** its
   entry wiring. The checker reads bytes, never imports the candidate. Exact
   known copies report `CARRIED`; changed integrations report `NOT_VERIFIED`
   and need explicit review. A helper file alone is insufficient.
4. Keep the separate `scripts/check_drain_fix.py NEW_COPY` cooldown gate. This
   change does not qualify the old v4 negative-sleep expressions. Preserve or
   copy forward that fix separately; these templates do not waive its gate.
5. Include the helper and every changed entry in the new packet's source seal.
   Prepare fresh identities, receipts, startup checks and chain output through
   that packet's normal CPU workflow. `CARRIED` is not a seal or device clearance.

For example, from the repository root after creating a new unsealed copy, the
patch check uses `git apply --check --directory=PATH_TO_NEW_COPY
experiments/own-xpu-runtime/stage2/common-teardown/v1/chain-integration.patch`.
After that check passes, the same command without `--check` applies it.
Run preparation with nice 19, CPUs 8–15/24–31, Python `-B`, stdin `/dev/null`.

```bash
nice -n 19 taskset -c 8-15,24-31 python3 -B \
  experiments/own-xpu-runtime/stage2/common-teardown/v1/run_cpu_tests.py </dev/null
```

The test harness forbids subprocesses, signals, network connections and writes
outside its temporary directory. Tests execute the patched adapter, K2
post-fixture branch, v4 parent and worker drain with fake processes, fdinfo and
journal input. Real file locks and atomic JSON writers operate only in scratch.

[templates.json](v1/templates.json) records reference and patched hashes.
[build_templates.py](v1/build_templates.py) regenerates the review patches here;
it never edits those references. Treat v1 as a versioned artifact after adoption;
new integration shapes or changes should get a new version and tests.

No packet124c was prepared: recreating and checking the bundle's source-bound
CPU/startup receipts, selection seals and registration was estimated to exceed
the brief's 30-minute copy allowance. This ships the requested module, tests,
checker and integration patches. See the [work note](../../../../notes/2026-10-18-own-runtime-ops-teardown-on-error.md).
