# A367 extraction worker driver

CPU preparation only, 2026-10-10. **40 tests pass, zero failures/errors/skips.**
[Test receipt](test-receipt.json), [read-only environment audit](environment-audit.json),
[printed launch plan](launch-plan.json), [conditional window and 45-minute budget](../WINDOW-RUNBOOK.md).
No GPU, vLLM runtime import, server, container, systemd unit, device node,
port 8188, weight download or existing venv change was used in preparation.
The initial 38-test run hit a mock-module cleanup error (torch imported twice);
[that receipt](test-initial-failure.json) is retained. Importing CPU torch once
before mocking `sys.modules` fixed the test harness; the corrected run passed.

## Injection choice and exact source evidence

Chosen: **`--worker-cls packet4_worker.ExtractionWorker`**, a subclass of the
certified XPU worker. `load_model` installs the eager guard and source-bound
adapter before delegating to the original method. The subclass adds observation
and cleanup only. `execute_model` delegates once and returns the same object.
The selected `Qwen4ExpDecoderLayer.forward` adapter also preserves the original
call and result. Duplicate registration is refused, including after failure.

All source lines below refer to **6d8724577dabbee5fa0bbc70c4d927c6174c8d8a**,
not the venv’s ordinary editable checkout. The full per-file SHA256s are in
[preregistration.json](preregistration.json); the preparation rechecked all
2,305 files in `/home/steve/src/vllm-current-main/vllm` without importing them.
The [75-member seal audit](../comparator-identity-audit.json) binds the overlay
chain and rebuilt extension. To inspect a cited line, use `git show
6d872457:vllm/PATH` in the source repository; no checkout or branch is needed.

| Source under `vllm/` | Lines | What proves the choice |
| --- | --- | --- |
| `v1/executor/multiproc_executor.py` | 639–665 | Every rank creates a `WorkerWrapperBase` and calls `init_worker`. |
| `v1/worker/worker_base.py` | 274–277, 343 | `worker_cls` is resolved by qualified name inside that process, then constructed. |
| `platforms/xpu.py` | 359–362 | Only `worker_cls="auto"` is replaced; an explicit class is preserved. |
| `v1/worker/worker_base.py` | 285–305 | A worker extension may not override existing attributes, so it cannot override `load_model`. |
| `plugins/__init__.py` | 16–18, 77–90 | General plugins run in each process and are idempotent, but would need extra rank/lifecycle filtering and registration metadata. No package installation is needed with worker_cls. |
| `models/qwen4_exp/amd/model.py` | 228, 313 | The selected decoder has `layer_idx`; the existing manifest binds its forward method. |
| `v1/worker/gpu_model_runner.py` | 2100–2113 | Target row positions derive from CPU computed-token counts and `query_pos.np`. The driver never calls `.cpu()` on device positions for metadata. |
| `v1/worker/gpu_worker.py` | 1245–1258 | Worker target execution synchronously calls the model runner. |
| `v1/worker/gpu_model_runner.py` | 4845–4884 | Target execution returns before the separate sampling/draft path; the scope excludes draft calls. |
| `v1/executor/multiproc_executor.py` | 451–525 | Stock cleanup closes worker death pipes, then eventually terminates/kills. The guard keeps cooperative joining and removes escalation. |
| `v1/utils.py` | 598–650 | Stock process-manager cleanup terminates and later tree-kills; the guard substitutes one SIGINT per concrete child PID and cooperative joining. |
| `v1/engine/utils.py` | 35, 198, 241–254 | Imported cleanup alias and weakref finalizer; bootstrap replaces the alias before manager construction. |
| `v1/worker/xpu_worker.py` | 179–193 | Original XPU shutdown releases runner and allocator resources. |
| `v1/worker/gpu_model_runner.py` | 6912–6938 | Original runner shutdown synchronizes, releases model/cache/workspace and synchronizes again. |

`server_entry.py` installs the cleanup guards at module scope, so Python spawn
imports them as `__mp_main__` before entering EngineCore/WorkerProc. The CPU
subprocess tests exercise that bootstrap with mocked vLLM modules, then execute
the **actual pinned init_worker function AST** with mocked dependencies. All
four ranks resolve the subclass, register once, call a CPU model once, preserve
its result, reject second registration, save a real Recorder fixture and remove
hooks during shutdown. These tests do not prove XPU dispatch or native teardown.
We deliberately did not attempt importing the live vLLM package to discover
whether it opens a device; the source audit and mocks avoid that possibility.

`sitecustomize` was considered but not chosen: Python may report and suppress
its import errors, and it runs in unrelated interpreter roles. `worker_cls`
provides an explicit rank-owned lifecycle and propagates registration failures.
No venv package, entry-point metadata or existing runtime file is modified.

## Evidence scope

The driver captures only the first target decoder layer’s raw outer boundary
at naturally encountered M1/M2/M6, with actual CPU positions and valid rows.
This narrow sample avoids weights and unbound internal state. The registered
hook selection is one of the existing 44 hooks, not a claim that all 44 ran.
Reference mappings stay null; numeric replay is **UNTESTED**. The 8 GiB budget
is split into 2 GiB per rank including a 4 MiB reserve for control receipts.

`oracle_assert` requires all 64 output IDs to equal the frozen answer’s first
64 IDs, cached_tokens exactly integer zero, and a length stop. It never edits
or truncates the frozen oracle file. A mismatch/missing array, early EOS, cache
hit, cap failure, fault or incomplete teardown makes the window VOID. Each
rank independently checks the same prefix at shutdown. No call to the older
`Recorder.finish` is made: that API requires the full 512-token answer and
cannot honestly certify this 64-token screen. `window-extraction.json` is a
separate scoped receipt; generic packet-4 replay remains a later step.

The command and environment are explicit allowlists. No inherited optimization
knobs are accepted. Arithmetic settings match A367; the identity lists eager
execution, worker observations, selection/budget, one chat/max64/nonstream,
cleanup/watch guards and the task-required nice19/OMP2 settings. OMP2 is an
explicit override of A367’s OMP1. Trace output is disabled; private cache/IPC
paths are temporary and are removed only after every owner exits. No measured
speed or quality certification is inferred from this identity check.

## Admission receipt contract

The driver never creates its own authorization. The coordinator supplies a
JSON owner-window flag with these fields (timestamps are Unix seconds):

```json
{
  "schema": "own-xpu-runtime.packet4.owner-window.v1",
  "authorized": true,
  "halt_resolved": true,
  "host": "steve-b70s",
  "boot_id": "CURRENT-BOOT-UUID",
  "issued_unix": 0,
  "expires_unix": 0,
  "previous_teardown_completed_unix": 0,
  "preregistration_sha256": "SHA256-OF-preregistration.json",
  "health_path": "/absolute/fresh-health.json",
  "health_sha256": "SHA256-OF-fresh-health.json",
  "payload_sha256": "SHA256-OF-fresh-payload-receipt.json",
  "output": "/absolute/nonexistent-window-directory",
  "firmware": "OBSERVED-FIRMWARE",
  "pci_ids": ["0000:23:00.0", "0000:27:00.0", "0000:43:00.0", "0000:47:00.0"]
}
```

Placeholders are not accepted. The window expires within an hour, the health
receipt within ten minutes, and the payload receipt within an hour. Health
must use the existing `ltx.four-card-health.v1` format, match boot/kernel, pass
all four unique cards, and contain no earlier or during-probe fault lines.
All known latches and process owners are rechecked immediately before launch.
A changed/missing owner flag or expired authorization during the run requests
shutdown; it is not permission to retry. A local flock serializes this driver;
the owner supplies exclusivity against other lanes, which do not share that
lock. Neither the flag nor the health receipt waives any current halt.

The fresh payload receipt is separately supplied by the coordinator after
verifying every official model file; required fields are `passed: true`,
`all_files_sha256_verified: true`, `model_root` equal to the admitted path,
`revision: "bcd9f01ddc9cff2316eb84281bebcd5b058bddce"`, and `verified_unix`.
Keep its detailed file hashes with it. Admission additionally verifies the
historical full-verification receipt pin, config/index hashes and 131 shards.
This preparation neither reads weights nor fabricates a payload receipt.

Kernel/library/source versions and model metadata may be audited on CPU with
`run_extraction_window.sh --audit`; the script defaults to no action unless one
of `--plan`, `--audit` or `--execute` is supplied. See the runbook for the exact
health and launch commands and the current remaining admission list.

## Receipts and checks

The window retains identity, command/env, environment audit, request/response,
parent and per-rank oracle verdicts, rank registration/fixtures/teardown,
bootstrap guard receipts, full before/latest kernel logs, watcher/STOP/FAULT,
parent exit, complete stop with next-launch time, and final receipt. Failure
retains evidence. A cleanup timeout waits without escalation and emits manual
recovery evidence; a parent exit alone is never completed teardown. No scratch
is deleted while an owner may remain. Coredump contents are never cleared.

Re-run CPU validation (all temporary directories are automatically removed):

```bash
nice -n 19 env OMP_NUM_THREADS=2 PYTHONDONTWRITEBYTECODE=1 /home/steve/.venvs/vllm-xpu/bin/python -B experiments/own-xpu-runtime/stage1/packet4-prep/driver/run_tests.py
```

The tests exercise supported source dispatch in fresh subprocesses, mock
model hooks, exact-once registration, CPU scheduling metadata, graph refusal,
all primary admission refusals, seals, command/environment isolation, journal
fault/read failures, one-SIGINT/no-escalation cleanup and VOID-on-mismatch.
The original recorder/adapter source files are unchanged. No native model,
quality gate, runtime speed, full-state census or live health pass is claimed.
