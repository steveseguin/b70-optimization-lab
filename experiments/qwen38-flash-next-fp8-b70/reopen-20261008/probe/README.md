# Single-card probes — CPU prepared, coordinator execution only

**2026-10-09: the owner accepted continued operation on this boot, without a
reboot.** The reviewed teardown patch is applied to the repository overlay.
Native cleanup remains unqualified. No probe was run during this task; GPU
work stays serialized behind LTX and belongs to the coordinator.

The two earlier tiny probes returned exact bytes, then faulted near worker
exit. The image-versus-host UMD comparison did not discriminate; see the
[exit lifecycle analysis](../../notes/2026-10-09-exit-lifecycle-analysis.md).
The indirect/direct gathers and new first-forward test are diagnostics, not
model quality or performance evidence. The separate
[host-pointer proposal](../overlay-fix-hostptr/README.md) remains unapplied.

## Results and corrected commands, 2026-10-10

The coordinator ran the exit probes on card `23:00.0` with image UMD:
clean-exit `20261010b` passed (gather 1, explicit sync 1, cleanup sync 1), and
exit-after-sleep `20261010b` passed (10 s idle, gather 1, explicit sync 1).
Both post-worker watchers passed with zero new counted faults. The first
clean-exit attempt lacked a watcher and is retained as an admission refusal.
First-forward `20261010b` failed before device work: support hashing assumed
`/probe` was beneath `/repo/...`. Its watcher subsequently reached 150 s and
wrote STOP; no FAULT.json. Saved evidence was not rewritten.

[Results and interpretation](../../notes/2026-10-10-exit-probes-result.md):
“Both clean” leaves the October 9 faults unexplained. Those original tiny probes
also released local references before abrupt exit. The live-reference abrupt
arm has no implementation/flag yet. First-forward and TP4 native work remain
unqualified. No production remedy follows from these two passes.

Support hashes now use stable package-relative and `probe/<basename>` keys
from their actual mounts. An explicit pre-worker admission refusal latches
STOP and lets the watcher report **“harness refused before device work”** with
failure status after a fresh clean journal read, without a 150 s wait. Faults
still take precedence; incomplete markers and native stalls retain their bounds.
The overlay pin is unchanged. CPU checks: lane 227 passed/6 skipped, combined
probe 84/1, teardown 49/0, first-forward 37/0 (included in probe).
[CPU evidence](../VALIDATION.md#probe-mount-admission-repair-2026-10-10).

The following corrected commands are **text only**, using NEW empty directories
that this task did not create. Each needs its own coordinator-admitted idle
window and matching host watcher, not a sequential campaign. The health receipt
expires at **2026-10-10 23:44:21 UTC**; replace it with fresh passing health
for any later window. Retain the five-minute gap and stop at the first fault,
refusal or other error. No LTX unit/endpoint operation is part of preparation.

```sh
p=/home/steve/llm-optimizations/experiments/qwen38-flash-next-fp8-b70/reopen-20261008
health=experiments/ltx25-b70/data/resume-20261008/postflight-probe-window-20261010T174416Z.json
owner=experiments/ltx25-b70/data/resume-20261008/fault-archive-20261010T011831Z-owner-accept-receipt.json

# First-forward: new directory, corrected support hashing; printer only.
nice -n 19 env OMP_NUM_THREADS=2 bash "$p/probe/run-first-forward-in-container.sh" \
  --render-node /dev/dri/by-path/pci-0000:23:00.0-render \
  --health-receipt "$health" --owner-acceptance "$owner" \
  --receipt-dir "$p/runs/probe-first-forward-20261010c" \
  --overlay-sha256 e00bb55d8378ecd0065e82a8c3b6fdd59268bd33aae6e0f356ca48f067926f2d

# Separately admitted matched clean repeat; printer only.
nice -n 19 env OMP_NUM_THREADS=2 bash "$p/probe/run-probe-in-container.sh" \
  --render-node /dev/dri/by-path/pci-0000:23:00.0-render \
  --health-receipt "$health" --owner-acceptance "$owner" \
  --receipt-dir "$p/runs/probe-clean-exit-repeat-20261010c" --clean-exit

# Separately admitted immediate abrupt repeat AFTER local-reference release.
# No exit flag selects the original abrupt mode; this is NOT live-USM retention.
nice -n 19 env OMP_NUM_THREADS=2 bash "$p/probe/run-probe-in-container.sh" \
  --render-node /dev/dri/by-path/pci-0000:23:00.0-render \
  --health-receipt "$health" --owner-acceptance "$owner" \
  --receipt-dir "$p/runs/probe-abrupt-immediate-20261010c"
```

Pass `--owner-acceptance "$owner"` to the host watcher too, using exactly the
selected arm's receipt directory. Start it using the coordinator sequence below;
wait for the clean heartbeat before the printed container command. For first-forward:

```sh
# Select exactly ONE of the new receipt directories above for this window.
receipt="$p/runs/probe-first-forward-20261010c"
nice -n 19 env OMP_NUM_THREADS=2 python3 -B "$p/probe/watch_kernel.py" \
  --health-receipt "$health" --owner-acceptance "$owner" --receipt-dir "$receipt"
```

The earlier dated preparation below is preserved as history; its health expired
and its saved run directories must not be reused.

## Prepared for 2026-10-10 (written 2026-10-09)

The three directories below were created **empty**. Git does not track empty
directories; another checkout must create them before coordinator admission.
Saved runs are unchanged. The commands below name the committed owner decision
and the provided post-118b health receipt. These wrappers **print only**;
neither the wrappers nor their output were run by this task. Health still
expires six hours after its end time (2026-10-10 07:34:03 UTC); printing a
command does not admit execution or extend that lifetime.
Use the image UMD for both exit comparisons. Run clean exit first, and consider
the sleep arm only after a clean result and a separately admitted idle window.

```sh
p=/home/steve/llm-optimizations/experiments/qwen38-flash-next-fp8-b70/reopen-20261008
bash "$p/probe/run-probe-in-container.sh" --render-node /dev/dri/by-path/pci-0000:23:00.0-render --health-receipt experiments/ltx25-b70/data/resume-20261008/postflight-pre118b-20261010T0134Z.json --owner-acceptance experiments/ltx25-b70/data/resume-20261008/fault-archive-20261010T011831Z-owner-accept-receipt.json --receipt-dir "$p/runs/probe-clean-exit-20261010" --clean-exit
bash "$p/probe/run-probe-in-container.sh" --render-node /dev/dri/by-path/pci-0000:23:00.0-render --health-receipt experiments/ltx25-b70/data/resume-20261008/postflight-pre118b-20261010T0134Z.json --owner-acceptance experiments/ltx25-b70/data/resume-20261008/fault-archive-20261010T011831Z-owner-accept-receipt.json --receipt-dir "$p/runs/probe-exit-sleep-20261010" --exit-after-sleep 10
```

Pinned image (already selected; no pull or build):
`vllm/vllm-openai-xpu@sha256:e4446310b1d30015e8fdc1a0a2ef1669ac6bef857cbe772487571ed5c1a926a9`.
The applied `overlay-manifest.json` SHA-256 is
`e00bb55d8378ecd0065e82a8c3b6fdd59268bd33aae6e0f356ca48f067926f2d`.
The preserved `teardown.patch` SHA-256 is
`3a9ea39d03d5888ed4c05eadd40c083216bfbe58dc6e35caeee2068d1fb71f62`.
The tiny exit probes read the package's pinned placement helper; they do not
install the overlay. Their existing lifecycle variants remain unchanged.

**Stop rule: the first fault ends submissions. No retry, no second arm after
a fault, no reset.** Also stop on a native crash, failed comparison, stale or
missing watcher, missing evidence or bounded lack of progress. Preserve
receipts and any hung worker; no forced kill or automatic health launch.
The old tiny-probe guardian still has its documented fatal 120-second alarm;
that existing timeout behavior is not native-safe cleanup and must be treated
as a fault/inconclusive result, not a successful test.

The admission mismatch is resolved by explicit `--owner-acceptance` on
Screen 1b, both probe printers/workers, and the shared watcher. Only
[`fault-archive-20261010T011831Z-owner-accept-receipt.json`](../../../ltx25-b70/data/resume-20261008/fault-archive-20261010T011831Z-owner-accept-receipt.json)
at its canonical repository path is accepted, pinned to SHA-256
`7c67c88aee396774ae8c2b29e23dd8366de9ab2375acdafec7b6254f23bbd5b1`
(committed in `317309759`). Its full boot ID, decision text and UTC time are
validated. The baseline is **2026-10-10 01:18:31 UTC**, the receipt time,
not the approximate conversation/archive filename time. Earlier faults remain
visible as excluded evidence; **any classified fault at or after that time
refuses**, even with a later passing health receipt. Unparseable fault times
also refuse. Without this option the original two-incident gate is unchanged.

The coordinator must pass **the same `--owner-acceptance experiments/ltx25-b70/data/resume-20261008/fault-archive-20261010T011831Z-owner-accept-receipt.json`**
to `watch_kernel.py`, alongside the same health path and each probe's receipt
directory. Watcher and worker acceptance hashes must match. Every probe receipt
and watcher output carries `journal_admission` with receipt SHA-256,
`counted_fault_lines`, `excluded_fault_lines`, and counted GPU incidents;
Screen prints and saves that same audit, including refusals. If the journal
was not read, `journal_evidence_available=false` makes that limitation explicit.

Exclusive idle cards, the five-minute stop gap and fresh passing health that
starts after acceptance remain required. No LTX process or endpoint is operated
by these commands' preparation. The current manifest changes only the
`screen.py` support pin; the frozen teardown patch and its original manifest
stay unchanged. [CPU results and preparation incident](../VALIDATION.md#owner-acceptance-admission-2026-10-10).

### Preregistered interpretation

Compare only matched, separately admitted runs. The table does not authorize
executing a second arm after a fault in this sequence. Applying source to the
repository does not qualify it for production.

| Matched result | Preregistered interpretation | Exact production decision |
|---|---|---|
| Clean exit clean; abrupt exit faults | Supports teardown class; does not uniquely identify slab versus internal queue/ring mapping. | Keep the applied source unqualified. The teardown candidate may proceed to separately authorized native validation: normal, partial-load, SIGINT/SIGTERM and calibrate-load exits, four rank receipts, clean kernel evidence and unchanged output/fresh-server gates. A single clean probe does not authorize adoption. |
| Both fault | Allocation/mapping/runtime class remains; cleanup did not cure it. A fault during clean finalization can still be teardown. | Do not launch full production with this applied candidate. Preserve the halt and investigate native release/queue ownership and mapping faults; revise the candidate before another separately admitted test. |
| Both clean | Flaky/other or changed state; historical faults remain unexplained. | No production change or safety certification. Preserve the candidate as unqualified; require a separately admitted matched repeat before choosing a production remedy. |
| Clean exit faults; abrupt exit clean | Cleanup-specific failure or flakiness; no fix established. | Reject adoption of this candidate. Inspect the release phase that failed and revise/test that mechanism before any production run. Do not adopt abrupt exit as a workaround. |
| Sleep remains clean until abrupt exit, then faults | Exit boundary is stronger than elapsed-time explanation; it does not establish live pinned slabs. | Keep the applied source unqualified. Prioritize the ordered-release/native-finalization candidate for separately authorized validation; this outcome alone does not qualify it. |
| Fault during sleep, before exit | Release/idle/asynchronous fault; abrupt interpreter exit is not necessary. | Do not treat graceful interpreter exit as a sufficient remedy or resume production. Investigate release-time mapping/queue behavior and pending runtime work before revising the candidate. |
| Missing marker, timeout, stale watcher, exception or missing evidence | Comparison is inconclusive. | No production decision, patch adoption, automatic retry or full-load launch. Preserve evidence and obtain a separately admitted valid comparison. |

### One-layer single-rank first forward — original preparation (admission later failed)

```sh
p=/home/steve/llm-optimizations/experiments/qwen38-flash-next-fp8-b70/reopen-20261008
bash "$p/probe/run-first-forward-in-container.sh" --render-node /dev/dri/by-path/pci-0000:23:00.0-render --health-receipt experiments/ltx25-b70/data/resume-20261008/postflight-pre118b-20261010T0134Z.json --owner-acceptance experiments/ltx25-b70/data/resume-20261008/fault-archive-20261010T011831Z-owner-accept-receipt.json --receipt-dir "$p/runs/probe-first-forward-20261010" --overlay-sha256 e00bb55d8378ecd0065e82a8c3b6fdd59268bd33aae6e0f356ca48f067926f2d
```

[Worker](single_rank_first_forward_probe.py), [command printer](first_forward_command.py),
[wrapper](run-first-forward-in-container.sh), [original design](../../notes/2026-10-09-attempt7-ordering.md).
This shares the slab probe's health admission, kernel watcher, atomic receipts,
post-worker journal handshake and immutable single-device container command.
The coordinator starts the same watcher described below; this command only
prints and never starts it. The worker applies the hash-verified overlay only
inside its disposable container, before importing the runtime.

One fresh Python child uses rank-0/layer-0 geometry: 64 tokens, 128 experts,
27 host and 101 resident, w13 `[1280,2560]`, w2 `[2560,640]`, and exact pinned
host payloads **88,473,600 / 44,236,800 bytes**. Synthetic FP8 bytes vary by
logical expert and coordinate; deterministic routes use both host and resident
experts. The all-device table control runs first; the mixed-host table arm runs
only after control completion and a fresh clean journal read. Their FP8 math,
block scales, BF16 inputs and routing match, and outputs must match byte for
byte. No checkpoint, PLE, collective, full-model load or model server is used.

Stage receipts, tensor/table addresses, table readbacks, output bytes/hashes,
IR hashes when exposed, worker state/memory, native stderr and cleanup phases
are retained. Synchronization localizes high-level production stages, some of
which contain several native kernels; this is not an instruction-level trace
or a speed measurement. Native context/USM queries and fatal-signal/VM-close
traces can be unavailable and must be labeled as such. Causal separation stays
incomplete without those observations.

The first-forward worker uses the applied ordered rank teardown before normal
exit and validates the rank-0 completion receipt. On a watcher fault or a stuck
native call it preserves ownership and waits for the coordinator. Its 120-second
bound latches STOP rather than killing the worker; this differs from the old
slab probe's fatal alarm. A missing or stale watcher, exception, native crash,
comparison failure or bound prevents further arms. No retry or reset is built in.

| Observation | Interpretation and next boundary |
| --- | --- |
| All-device control fails | Shared compute/dispatch remains implicated; do not submit mixed work. |
| Control clean, only mixed fails | Raises host-table/residency/native-codegen hypothesis; does not identify the exact allocation or instruction. |
| Both outputs exact, failure only during cleanup/exit | Raises lifecycle hypothesis; no safe-teardown claim. |
| Both exact and clean exit/postflight | Clears this one layer/rank only, not 96 allocations, TP4, PLE or model output. |
| Fatal-signal/VM-close trace unavailable | Event ordering remains partial; do not claim no native crash preceded a GPU fault. |

CPU verification after application: **35/35 new first-forward checks passed**
([source-bound receipt](../evidence/teardown-applied-20261010/first-forward.json),
[log](../evidence/teardown-applied-20261010/first-forward.log)). Combined probe
suite: **60 passed, one prohibited child-kill test skipped** out of 61.
Independent source review checked production signatures, geometry, release
ordering and the real rank-receipt gate; native behavior remains untested.
Use the restricted runner to retain the explicit no-kill exclusion:

```sh
p=experiments/qwen38-flash-next-fp8-b70/reopen-20261008
OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 python3 -B "$p/overlay-fix-teardown/run_cpu_tests.py" probe
```

## Coordinator sequence

The owner's decision permits continuing this boot. Arrange an exclusive idle-card window; do not
stop/displace LTX for this probe. Keep the lane's five-minute stop gap. Retain
all fault markers and evidence. The old attempt-7 boot is explicitly refused.
Use the existing matching image; no pull, install, runtime installation or build.
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
The watcher keeps the whole-boot journal and latches STOP. Without explicit pinned owner acceptance, a second incident on
the boot refuses regardless of a passing health receipt. With acceptance, every
classified fault at or after its timestamp refuses. Nothing deletes FAULT.

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

Historical preparation title retained for links. The clean and sleep arms were
subsequently run on October 10; see the dated results above. The live-reference
abrupt variant remains absent.

This preregistered table also governs the dated 2026-10-10 commands above.

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
not execute their output without coordinator admission):

```sh
probe=experiments/qwen38-flash-next-fp8-b70/reopen-20261008/probe
bash "$probe/run-probe-in-container.sh" --render-node /dev/dri/by-path/pci-0000:23:00.0-render --health-receipt /PATH/FRESH-HEALTH.json --receipt-dir /PATH/NEW-CLEAN-RECEIPTS --clean-exit
bash "$probe/run-probe-in-container.sh" --render-node /dev/dri/by-path/pci-0000:23:00.0-render --health-receipt /PATH/FRESH-HEALTH.json --receipt-dir /PATH/NEW-SLEEP-RECEIPTS --exit-after-sleep 10
```

Hold image, UMD, card, allocator policy and gather variant fixed. These commands
select the image UMD. Host UMD requires `--host-umd-overlay` on both compared
arms. No sequential campaign is authorized: a fault stops work, and another
arm requires a separately admitted state under the same guardian/watcher rule.

Use the [dated preregistered interpretation table](#prepared-for-2026-10-10-written-2026-10-09) above.

The owner has resolved the prior boot halt; every new fault ends this probe
sequence. The [applied teardown patch](../overlay-fix-teardown/README.md) has
CPU ordering tests only; no row turns a probe result into production approval.

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

The unrestricted commands from the original preparation are superseded by
the restricted runner above and the [current application validation](../VALIDATION.md#teardown-application-and-probe-preparation-2026-10-09).
Historical evidence below is retained under its original scope.

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
OMP_NUM_THREADS=1 python3 -B experiments/qwen38-flash-next-fp8-b70/reopen-20261008/overlay-fix-teardown/run_cpu_tests.py probe
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
