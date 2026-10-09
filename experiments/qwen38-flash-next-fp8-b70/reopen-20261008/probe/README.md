# Single-card slab probe — exit variants prepared, launches halted

**2026-10-09: both image NEO 26.27 and host-overlay NEO 26.18 returned exact
bytes, then faulted at the worker exit/postflight boundary. This boot has two
incidents; all GPU launches remain halted pending the owner's decision.**
The UMD version did not discriminate. See the
[exit lifecycle analysis](../../notes/2026-10-09-exit-lifecycle-analysis.md).
The commands below are prepared procedures, not current launch authorization.
This tests the [attempt-7 hypothesis](../../notes/2026-10-08-attempt7-gpu-fault-analysis.md), not model output or performance.
The indirect variant hides the host allocation behind the production signed table.
The direct variant passes and uses the host pointer, local row and selector.
Both use the same 3 MiB pinned allocation, 4096-byte interior view, bytes and row order.
The active overlay and its manifest are unchanged; the [proposed fix](../overlay-fix-hostptr/README.md) is separate.

## Coordinator sequence

First obtain the owner's cleared boot and an exclusive idle-card window; do not
stop/displace LTX for this probe. Keep the lane's five-minute stop gap. Retain
all fault markers and evidence. The old attempt-7 boot is explicitly refused.
Use the existing matching image; no pull, install, production overlay application or build.
Provide a complete `ltx.four-card-health.v1` receipt from this boot, less than
six hours old. No health probe is run by these scripts.

From the repository root, replace the two `/PATH` values and select the owner's
one allowed by-path render node. `run-probe-in-container.sh` **only prints**:

```sh
probe=experiments/qwen38-flash-next-fp8-b70/reopen-20261008/probe
health=/PATH/TO/FRESH-HEALTH-RECEIPT.json
receipt=/PATH/TO/NEW-PROBE-RECEIPTS
mkdir -- "$receipt"
bash "$probe/run-probe-in-container.sh" --render-node /dev/dri/by-path/pci-0000:23:00.0-render --health-receipt "$health" --receipt-dir "$receipt" > "$receipt/command.sh"
cat "$receipt/command.sh"
```

Review the printed Docker command. It uses the lane's immutable image digest,
three exact-allocation aliases and NEO process variables, one render device,
`--rm --pull=never --restart=no --network=none`, and read-only probe/package/health
mounts plus the writable receipt directory. There is no model mount or server.
The read-only package mount supplies the actual production offset function and
lane health validator; it is not installed/applied. The command explicitly sets
`FLASHNEXT_PROBE_ADMIT=1`; invoking Python without that opt-in refuses before Torch.

Only after the coordinator admits execution:

```sh
python3 -B "$probe/watch_kernel.py" --health-receipt "$health" --receipt-dir "$receipt" > "$receipt/watcher.log" 2>&1 &
watcher_pid=$!
# Wait briefly for the first clean heartbeat; an absent/failed/stale one refuses.
for attempt in 1 2 3 4 5 6 7 8 9 10; do
    test -f "$receipt/watcher.json" && break
    sleep 0.2
done
bash "$receipt/command.sh"
probe_status=$?
wait "$watcher_pid"
watcher_status=$?
printf 'probe=%s watcher=%s\n' "$probe_status" "$watcher_status"
cat "$receipt/receipt.json"
```

This is one diagnostic launch, four programs and one gather synchronization
(clean-exit adds its separately recorded cleanup synchronization).
Setup transfers and the final blocking CPU copy can synchronize internally.
The CPU guardian never imports Torch; its single device worker has a default
OS SIGALRM after 120 seconds, covering imports, JIT and native waits. This hard
last-resort bound can terminate a busy process and itself cause a driver fault;
a timeout is therefore a fault event, never permission to retry. The guardian
preserves partial receipts and records native signals even if Python cannot
handle them. The journal watcher is bounded to 150 seconds, never signals a
process, and requires one final journal read begun after the worker exits.

**Stop on any error, mismatch, timeout, missing evidence, new fault/CAT/reset/dump
or stale watcher. No automatic retry, direct follow-up, four-rank load or recovery.**
Preserve receipts, logs and dumps; the coordinator applies the host recovery rule.
The watcher keeps the whole-boot journal and latches STOP. A second incident on
the boot refuses regardless of a passing health receipt. Nothing deletes FAULT.

A separately approved direct test uses a **new** receipt directory and the same
sequence, adding `--direct-host-pointer` to the printer command. The standalone
`single_rank_slab_probe_direct.py` selects that same flag; it is not a second
implementation and never runs after an indirect failure automatically.

## Opt-in host UMD comparison (completed; both arms faulted)

For a later coordinator-admitted single-card window, `--host-umd-overlay`
selects exactly the twelve read-only mounts in
[Remedy A](../../notes/2026-10-09-runtime-comparison.md#remedy-a-host-umd-bind-overlay--design-not-executed),
in that order, onto the image's resolved real filenames. The printer hashes
every host source and raises `ValueError` before printing a command if a file
is missing, unreadable or differs from the note's closure SHA-256. It sets
`LD_LIBRARY_PATH=/usr/local/lib:/opt/ucx/lib:/opt/venv/lib` and
`FLASHNEXT_PROBE_UMD=host-26.18.38308`. No host library is changed.

Obtain a **fresh health receipt** for the admitted boot/window and choose a
**NEW receipt directory**. After the five-minute stop gap, prepare the command:

```sh
probe=experiments/qwen38-flash-next-fp8-b70/reopen-20261008/probe
health=/PATH/TO/FRESH-HEALTH-RECEIPT.json
receipt=/PATH/TO/NEW-HOST-UMD-PROBE-RECEIPTS
mkdir -- "$receipt"
bash "$probe/run-probe-in-container.sh" --host-umd-overlay --render-node /dev/dri/by-path/pci-0000:23:00.0-render --health-receipt "$health" --receipt-dir "$receipt" > "$receipt/command.sh"
cat "$receipt/command.sh"
```

Review the command, then use the **same watcher and execution sequence above**,
with these `health` and `receipt` values, only after coordinator admission.
The same stop-on-error/fault rule applies; no automatic retry or direct follow-up.
Reprint immediately before execution so a host package update cannot silently
reuse an earlier hash check. The printed command itself is not a hash validator.

Without the flag, the printed command is byte-for-byte unchanged.
`receipt.json` records `environment.FLASHNEXT_PROBE_UMD`, defaulting to
`image-26.27.39122` when unset, and all `FLASHNEXT_PROBE_RENDER_*` variables.
The overlay command explicitly supplies the host identity. Existing render-node
symlink resolution and the package mount's repository depth are preserved.
The completed UMD comparison retained the original `os._exit` boundary,
timeout, gather and post-worker journal check. The new lifecycle options below
are separate experiments; the default arm still uses abrupt exit.

## Exit lifecycle discrimination — prepared, not executed

The default returns from `run_device` (dropping its local references), then
calls `os._exit(0)`. It does **not** deliberately keep the slab tensor live at
exit. Native allocation caches, Triton modules and runtime queues/context can
outlive those references. The 3 MiB slab exceeds the 1 MiB host-cache threshold;
its mapping lifetime at exit was not measured.

`--clean-exit` preserves allocation, compilation, one gather, one gather sync,
and the blocking readback. On success it drops `operands` and the loop's `tensor`
alias, direct-only buffers if present, then output/table/resident/UVA/view/slab
and CPU results; drops local compiled/kernel references; collects garbage;
synchronizes; empties the XPU cache; and calls the image's public
`torch.accelerator.empty_host_cache()` if present. The receipt records called
or unavailable. It releases the stream wrapper and returns, then calls
`sys.exit(0)` outside the exception handler so normal finalization can run.
Triton's global module cache and runtime-owned queues are left to finalization;
this is not proof they were destroyed. The extra sync is separately counted
as `cleanup_synchronizations`, never hidden in the original gather count.

`--exit-after-sleep N` returns at the original local-reference release boundary,
idles without device calls while checking the watcher, obtains a fresh journal
read after the idle interval, then calls `os._exit(0)`. Thus it separates elapsed
time after release from interpreter exit; it does not test holding the slab live.
N must be finite, 0–30 seconds; modes are mutually exclusive. The original
120-second worker alarm and 150-second watcher bound are not extended. An alarm
or other error invalidates the comparison and retains the original failure
path (no cleanup device calls, abrupt failure exit, no retry).

Receipt `lifecycle` entries retain UTC, Unix and monotonic times for comparison,
`before_free`/`after_free` (clean mode), `before_return`, `after_return`, idle
begin/end (sleep mode), and `before_exit`. `after_free` means requested release
operations returned, not a native mapping census. The guardian still requires
a new kernel read begun after worker death; clean bytes alone never pass.

Prepared **print-only** commands from repo root (distinct NEW directories; do
not execute their output while launches are halted):

```sh
probe=experiments/qwen38-flash-next-fp8-b70/reopen-20261008/probe
bash "$probe/run-probe-in-container.sh" --render-node /dev/dri/by-path/pci-0000:23:00.0-render --health-receipt /PATH/FRESH-HEALTH.json --receipt-dir /PATH/NEW-CLEAN-RECEIPTS --clean-exit
bash "$probe/run-probe-in-container.sh" --render-node /dev/dri/by-path/pci-0000:23:00.0-render --health-receipt /PATH/FRESH-HEALTH.json --receipt-dir /PATH/NEW-SLEEP-RECEIPTS --exit-after-sleep 10
```

Hold image, UMD, card, allocator policy and gather variant fixed. These commands
select the image UMD. Host UMD requires `--host-umd-overlay` on both compared
arms. No sequential campaign is authorized: a fault stops work, and another
arm requires a separately admitted state under the same guardian/watcher rule.

| Matched result | Preregistered interpretation | Exact production decision |
|---|---|---|
| Clean exit clean; abrupt exit faults | Supports teardown class; does not uniquely identify slab versus internal queue/ring mapping. | Keep the production overlay unchanged. The unapplied teardown candidate may proceed to separately authorized native validation: normal, partial-load, SIGINT/SIGTERM and calibrate-load exits, four rank receipts, clean kernel evidence and unchanged output/fresh-server gates. A single clean probe does not authorize adoption. |
| Both fault | Allocation/mapping/runtime class remains; cleanup did not cure it. A fault during clean finalization can still be teardown. | Do not apply or launch full production with this candidate. Preserve the halt and investigate native release/queue ownership and mapping faults; revise the candidate before another separately admitted test. |
| Both clean | Flaky/other or changed state; historical faults remain unexplained. | No production change or safety certification. Preserve the candidate as unqualified; require a separately admitted matched repeat before choosing a production remedy. |
| Clean exit faults; abrupt exit clean | Cleanup-specific failure or flakiness; no fix established. | Reject adoption of this candidate. Inspect the release phase that failed and revise/test that mechanism before any production run. Do not adopt abrupt exit as a workaround. |
| Sleep remains clean until abrupt exit, then faults | Exit boundary is stronger than elapsed-time explanation; it does not establish live pinned slabs. | Keep production unchanged. Prioritize the ordered-release/native-finalization candidate for separately authorized validation; this outcome alone does not qualify it. |
| Fault during sleep, before exit | Release/idle/asynchronous fault; abrupt interpreter exit is not necessary. | Do not treat graceful interpreter exit as a sufficient remedy or resume production. Investigate release-time mapping/queue behavior and pending runtime work before revising the candidate. |
| Missing marker, timeout, stale watcher, exception or missing evidence | Comparison is inconclusive. | No production decision, patch adoption, automatic retry or full-load launch. Preserve evidence and obtain a separately admitted valid comparison. |

All rows keep the current boot halt in force until the owner resolves it.
The [unapplied teardown patch](../overlay-fix-teardown/README.md) has CPU ordering
tests only; no row turns a probe result into production approval.

A missing marker, timeout, stale watcher, unavailable required evidence or
exception is inconclusive. Compare fault timestamps to release/exit markers;
one clean run never certifies production stability.

**CPU validation: 26 probe tests passed**, including both flag parsers, invalid
values/conflicting modes, refusal receipts, watcher-stop behavior and real
CPU fork/finalizer behavior. No Torch import or GPU call was needed for these
tests; they do not validate native cleanup. See [validation](cpu-exit-lifecycle-validation.json).

## Evidence and limits

`receipt.json` retains pointer spans, dtype/shape/stride/storage offsets, CPU
pin flags, original/readback signed table values and addresses, byte hashes,
queue identity, versions, exception/traceback or terminating signal, and IR
paths/hashes. Compilation-only `warmup` saves TTIR/LLVM/SPIR-V before the one
launch; a compile failure can leave IR absent, explicitly recorded. The Triton
cache is also retained. Neither tensor storage length nor CPU tests prove native
allocator reservation size: the exact-size policy is the overlay's Torch path.

The reviewed Python exports have no public launch-context USM query. The receipt
says `unavailable` when the launch stream exposes no context/query binding; it
never relabels pinning as a USM-kind measurement or casts an opaque queue address.
If context/query methods are exposed, both base and interior pointers must report
`host`; an error or different kind stops execution. This optional binding has
only CPU test coverage; current-image availability is unverified.

A tiny pass certifies only these raw bytes on this card/runtime. Full-size MoE,
FP8 arithmetic, TP4, PLE, startup, output parity and fresh-runtime repeats remain
unverified. No speed or lossless-model claim follows.

**Original CPU preparation: 237 passed, zero failures or skips** (213 existing + 15 probe +
9 addressing). [Receipt](cpu-validation.json), [lane log](cpu-lane-tests.log),
[probe log](cpu-probe-tests.log), [addressing log](cpu-hostptr-tests.log).
The independent review checked both the math and the post-worker journal handshake.

Reproduce with the existing venv, without installation:

```sh
/home/steve/.venvs/ltx25-baseline/bin/python -B -m unittest discover -s "$probe" -p 'test_*.py' -v
/home/steve/.venvs/ltx25-baseline/bin/python -B -m unittest discover -s "$probe/../overlay-fix-hostptr" -p 'test_*.py' -v
SCREEN1B_CPU_EVIDENCE_DIR="$probe/cpu-rehearsal" OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 /home/steve/.venvs/ltx25-baseline/bin/python -B -m unittest discover -s "$probe/.." -p 'test_*.py' -v
```

**Host UMD preparation, 2026-10-09: 21 probe tests passed; lane suite discovered
213 tests, with 207 passed and 6 explicitly skipped, zero failures/errors.**
The current task forbids `/mnt/fast-ai` access and `torch.xpu` operations, so
the real-checkpoint boundary test and all five worker-init rehearsals were
excluded. These counts do not revalidate those six tests. All twelve installed
host libraries also passed the printer's SHA-256 check. No container or GPU
probe was launched. The command regression fixture retains the original
printer output, including both coordinator fixes.

Reproduce this restricted validation from the repository root:

```sh
python3 -B -m unittest discover -s experiments/qwen38-flash-next-fp8-b70/reopen-20261008/probe -p 'test_probe.py'
OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 /home/steve/.venvs/ltx25-baseline/bin/python -B - <<'PY'
import unittest
suite = unittest.defaultTestLoader.discover(
    'experiments/qwen38-flash-next-fp8-b70/reopen-20261008', pattern='test_*.py')
def restrict(tests):
    for test in tests:
        if isinstance(test, unittest.TestSuite):
            restrict(test)
        elif (test.id().startswith('test_worker_init_rehearsal.') or
              test.id().endswith('.test_real_checkpoint_boundary_bytes_without_table_allocation')):
            setattr(test, test._testMethodName, unittest.skip(
                'owner hard rule: no /mnt/fast-ai access or torch.xpu rehearsal')(
                    getattr(test, test._testMethodName)))
restrict(suite)
result = unittest.TextTestRunner(verbosity=2).run(suite)
raise SystemExit(not result.wasSuccessful())
PY
```
