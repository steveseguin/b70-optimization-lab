# October 18: record a clean teardown even when Python fails afterwards

The CPU regression reproduces the reported failure: K2's children have exited,
then selection postprocessing raises, and the old adapter leaves both an
undrained shared record and a lane marker. The copy-forward helper completes
the same drain/release path as success after checking exit and faults. The
experiment still fails and the original Python error is re-raised.

This is new support under
[`stage2/common-teardown`](../experiments/own-xpu-runtime/stage2/common-teardown/README.md).
No existing packet, screen, operational file, live marker, queue or latch was
changed. Nothing was launched on a device; no service, sudo or host setting was
used. Packet124c was not created: its source-bound build/startup receipts,
selection seals and registration require a separate preparation cycle estimated
above the 30-minute copy allowance. The module, tests, checker and both
integration patches are the brief's fallback deliverable.

## Where completion was skipped

The reported hourly-review-23 incident was packet124-chain-a K2 at 11:52 UTC.
That operational timestamp comes from the brief; this task did not read or
alter the live coordination files. The code references examined were
packet124b, the shared chain-admission template and the v4 screen wrapper.
The initial fetched `HEAD` was `0c0ff615aaaebbff7195c8a80e178fa35a19a5d3`.
Exact source hashes are retained in the new template manifest.

- In packet124b's `window.py`, `run_fixtures()` polls/reaps its children before
  returning. K2 then calls `pin_production_dispatch()`. `main()` catches the
  Python exception at line 589, saves `passed=false` and returns 1 at line 606.
- `window_adapter.run_window()` binds the receipt only for code 0. That binding
  calls `WindowAdmission.complete()` at line 85: finish the owner monitor,
  check model READY proof, check foreign clients, call `DrainPermit.complete()`,
  then `Reservation.complete(drained=True)`. Its `__exit__()` only closes locks.
  A nonzero return or raised exception therefore skips both completion calls.
- `drain_gate.py:64` is the shared `drained=true` writer, including the completion
  timestamp. `lane_admission.py:146` removes only matching-token markers and
  releases lane locks under the protocol lock. The chain-admission template has
  the same success-only structure. Its frozen bytes remain unchanged.
- `queue_runner.validate_success()` at line 107 rejects nonzero/failed windows
  and verifies the bound admission. The runner's exception handler writes STOP.
  It has no authority to manufacture a drain proof. Neither gate is changed.
- v4 `conditions.Teardown.__exit__()` at line 119 writes both the shared record
  and worker `teardown.json` only when no exception escapes. The worker's
  `drain()` normally catches a close error, drains again, then re-raises outside
  the context; an exception escaping that cleanup still skips the writer.
- v4 `screen_main()` releases the lane after confirmed worker exit and before
  aggregation. Errors before that release latch when a child existed, even
  if it has exited. Errors before launch can also strand the outer reservation.
  The parent already separates post-release report failure from device failure;
  the new template extends that boundary to proven clean error teardown.

## What the new copy does

The chain template attaches its Watch to the admission, retains and re-raises
the original exception after saving the failed receipt, and handles legacy
nonzero returns without turning them into success. Its error path requires an
owned drain permit, matching launched/monitored PID sets, absent `/proc/PID`
directories (including no zombies or reused PIDs), exited CPU children, the
full five-second postflight and fresh kernel checks. It then uses the same
monitor, READY, client census, drain writer and matching-token lease release
as the success path. The admission's `passed` field stays false.

The screen template gives the worker Teardown an explicit proof callback. It
checks every rank's process handle, retained-owner list, PID disappearance and
selected-pair client census. It uses the parent's approved kernel cursor from
before worker startup and the parent's unchanged fault classifier. The error
proof reads that whole suffix. A consumed fault
cannot disappear through a second check. Both normal and error completion use
the extracted original writer while holding the original lock.

The v4 parent accepts only its own worker's boot/PID/output-bound completed
teardown and completed supervisor postflight. It invokes the original release
callback before recording report failure and re-raising. A prelaunch refusal
can release only its own reservation, with an explicit launch-attempt guard;
it never rewrites the prior shared drain. A refused drain, missing proof or
new fault keeps the old refusal/latch behavior. Sticky checks retain faults,
stops and journal errors rather than consuming and forgetting them.

This is not crash recovery: SIGKILL, a vanished owner, failed admission before
chain supervision exists, unproven owner isolation, filesystem write failures
and uncertain processes still require the existing handling. No latch is
cleared. The 60-second shared cooldown and queue failure/STOP gates remain.
The old v4 cooldown expression remains a separate required copy-forward fix.

## CPU validation

Run from the repository root:

```bash
nice -n 19 taskset -c 8-15,24-31 python3 -B \
  experiments/own-xpu-runtime/stage2/common-teardown/v1/run_cpu_tests.py </dev/null
nice -n 19 taskset -c 8-15,24-31 python3 -B scripts/check_teardown_on_error.py \
  experiments/own-xpu-runtime/stage2/packet124b-record-bundle --kind chain </dev/null
```

The second command intentionally reports `NOT_VERIFIED` and exits 1: the frozen
packet was not patched. The checker requires exact helper and integration
hashes, not a filename or a comment claiming the fix. Temporary patched chain
and screen copies report `CARRIED`; altered helpers, dead hooks and symlinks
fail. Changed integration bytes need a reviewed new version.

All 41 CPU tests pass. Both patches pass `git apply --check`, apply cleanly to
temporary source copies, and those copies pass the carry checker. The frozen
packet124b and v4 trees both report `NOT_VERIFIED`, as intended.

The tests use fake children, `/proc` trees, render-FD records and journal lines,
with real temporary locks/JSON writes. They include the old-code negative
control and execute K2's actual post-fixture branch, injecting the selection
exception at `pin_production_dispatch()`. The patched branch preserves that
same exception object, performs postflight and releases; an injected new kernel
fault retains the undrained record and fault latch. Worker and parent tests
cover clean errors, live children, wrong drain identity, prelaunch refusal,
failed report, missing isolation/READY proof and normal success. The harness
blocks subprocesses, signals, network and writes outside scratch.

Validation results and the final test count are retained beside the helper in
`v1/evidence/cpu-tests.log`. CPU evidence does not qualify a device run or make
an existing packet carry this fix. Adoption and normal packet resealing are next.
