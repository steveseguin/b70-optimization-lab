# Screen 1b graceful teardown — unapplied CPU-reviewed candidate

**Not applied, not native-qualified, and not permission to launch. GPU work
remains halted after the second incident of this boot.** This implements the
[production cleanup plan](../../notes/2026-10-09-exit-lifecycle-analysis.md).
The live overlay, installed runtime, loading guard and saved runs are unchanged.

## Review artifact and scope

[teardown.patch](teardown.patch) is relative to `reopen-20261008/` and includes
all modified files and the refreshed overlay manifest. [copies/](copies/)
contains the resulting module copies; it is not a standalone runnable package.
[patch-manifest.json](patch-manifest.json) pins every before/after file and the
image. [build_patch.py](build_patch.py) only seals/verifies this review directory;
it never applies the patch. A CPU test applies it to a disposable temporary
package, compares every result to its copy, and checks the package hashes.

The added GPUWorker and XPUWorker files match the pinned v0.30.0 image's files
byte for byte before modification. [base-runtime/](base-runtime/) preserves
those source files. Verification used two device-free, network-free containers
whose only command was `/bin/cat`; neither imported Torch nor initialized a
runtime. The source and image identity is in the patch manifest. Unchanged
upstream child-wait overrides remain dependencies of the existing overlay.

Scope is Screen 1b: `B70_SCREEN1B=1`, V2 XPU runner, spawned TP4 multiproc,
DP1, synchronous scheduling (`--no-async-scheduling`). Worker initialization
refuses asynchronous scheduling before device initialization. Model bytes,
arithmetic, placement, BF16 KV, admission thresholds and loading RAM guard
are unchanged. The non-Screen-1b path retains its original behavior except
optional-attribute checks in GPUWorker shutdown.

## Release order

1. A signal only records cancellation intent. The existing CPU monitor wakes
   the worker's RPC queue; a running RPC returns before release. Load cancellation
   unwinds through the existing guarded-copy drain. Repeated SIGINT/SIGTERM
   cannot raise through cleanup. Worker exception frames unwind before cleanup.
2. Close RPC queues. GPUWorker stops transfer services, profiler and elastic
   executor. Drain all streams on this rank. Release graph owners and the
   upstream workspace, rotary and static-forward registries.
3. Keep host owners alive while removing expert pointer tables, original and
   restored parameter UVA aliases, and generic UVA `parameter.data`. Drain
   again. Close the PLE memoryview, checkpoint mmaps and cache metadata before
   dropping pinned PLE slabs and step buffers. Clear model/PLE registries and
   all runner fields; collect garbage and drain again.
4. Release XPU pools, then the worker/wrapper references, then model-parallel
   and distributed groups. Finally call this rank's `torch.xpu.synchronize()`,
   `torch.xpu.empty_cache()`, public `torch.accelerator.empty_host_cache()`, and
   a final `torch.xpu.synchronize()` after allocator release calls.
5. Append one `rank_teardown_complete` event to `loader-PID.jsonl` and print one
   `SCREEN1B_TEARDOWN` JSON line per rank. Each includes rank/PID and UTC, Unix
   nanoseconds and monotonic nanoseconds for all 17 release phases. A process
   that never initialized XPU emits only `rank_teardown_uninitialized`; it
   cannot qualify a successful native release.

The XPU runner is published before its constructor, and allocation owners are
registered before model loading finishes. A missing runner still uses the
same partial-release path, including upstream global cleanup before pool
release. A release failure stops the sequence and parks the worker without
retrying, even if recording the failure also raises. No completion receipt
is issued for that path. EngineCore keeps cooperative handlers while waiting
for workers; the existing parent wait never times out into TERM/KILL. Concurrent monitor and
main-thread shutdown callers serialize and both wait for the children; failed
parent waits also preserve the supervising process.

The entrypoint restores inherited INT/TERM defaults before CPU setup and
latches interruptions before `exec`. Controller and watchdog share one STOP
then SIGINT path, including container-creation races. Docker metadata uses
`--stop-signal=SIGINT --stop-timeout=-1`; the controller still sends one explicit
SIGINT and inspects rather than using a timed Docker stop. Its 300-second
bound reports an unfinished shutdown and preserves the container. Normal and
`calibrate-load` exits require four complete ordered rank receipts, a clean
container exit without OOM, and a clean kernel postflight before `clean_exit`.
No calibration receipt may call an exit clean based only on container code 0.

## What this does not guarantee

This patch establishes explicit Python ownership and shutdown ordering. A
receipt proves those calls returned; **it does not prove zero native USM
mappings or destruction of every Level Zero/SYCL/UR queue**. Triton global
modules and runtime-owned contexts/queues still depend on normal interpreter
and native finalization. No undocumented queue-destroy operation is invented.
Even all caches emptied is not a native allocator/mapping census. The kernel
postflight is a snapshot, not continuous monitoring after process exit.

**An OOM kill, SIGKILL, fatal native crash, host failure or external supervisor
kill cannot be made graceful by Python handlers.** OOM must be prevented
upstream by the loading RAM guard, pre-allocation admission and watchdog
margin; this patch does not loosen any of them. A hung native synchronization
is preserved for owner intervention, not killed. CPU tests cannot establish
native cleanup safety, complete partial-init coverage, correctness/performance,
or a cure for the four historical incidents.

The probe [production-decision table](../probe/README.md#exit-lifecycle-discrimination--prepared-not-executed)
controls what each later authorized outcome permits. Before adoption: owner
resolution of the boot fault, separately admitted matched probe evidence,
then reviewed native normal/partial-load/SIGINT/SIGTERM/calibrate-load exits
with all four receipts and kernel evidence, and the lane's unchanged exact
output and fresh-server gates. Do not replace the frozen runtime with this
candidate or publish a speed claim from these CPU checks.

## CPU validation and review

[Validation receipts and logs](evidence/): lane **207 passed, 6 explicitly
skipped out of 213**; probe **26 passed**; candidate **49 passed**, no failures
or errors. The six exclusions are the real-checkpoint boundary test and all
five `worker_init_rehearsal.py` tests: they access protected model storage or
use `torch.xpu`. The existing rehearsal therefore does not fit this task.

The replacement fixture rehearsal executes the candidate's actual
AST-extracted `WorkerProc.worker_main` for ranks 0–3, with fake workers,
allocator and XPU APIs, plus partial load, RPC exception, SystemExit,
KeyboardInterrupt, broken pipes and real CPU SIGINT/SIGTERM. It does not load
the model or execute Torch. Separate tests execute the copied GPUWorker and
XPUWorker shutdown methods with fake services and pools, check alias-before-owner
free order, PLE close idempotence, failure preservation, watchdog signaling,
receipt refusal and temporary patch application.

```sh
p=experiments/qwen38-flash-next-fp8-b70/reopen-20261008/overlay-fix-teardown
python3 -B "$p/build_patch.py" --check
OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 /home/steve/.venvs/ltx25-baseline/bin/python -B "$p/run_cpu_tests.py" lane
python3 -B "$p/run_cpu_tests.py" probe
python3 -B "$p/run_cpu_tests.py" teardown
```

An independent ordering subagent reviewed the source and re-reviewed the fixes:
no remaining blocking ordering issue in this declared scope. The review found
and corrected repeated-signal unwinding, parent default-signal restoration,
retained parameter/global aliases, partial construction, diagnostic failures
and pipe-close errors that could bypass cleanup. A separate subagent tested
service/runner/pool ordering. [Review record](evidence/review.md).
