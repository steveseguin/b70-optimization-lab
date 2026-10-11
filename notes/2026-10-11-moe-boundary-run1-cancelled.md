# MoE boundary run 1 — controller cancellation before first forward

<!-- campaign-closeout -->

## Question and identity

Why did the first staged boundary diagnostic cancel construction before reaching
the startup MoE forward? Read-only audit on `steve-b70s`, October 11, of:

- Run: `/mnt/fast-ai/bench-results/flashnext-moe-boundary-window-20261011-source-paths-v3`.
- Stage: `/mnt/fast-ai/bench-results/flashnext-moe-boundary-package-20261011-source-paths-v3`.
- User unit: `flashnext-screen1-20261011T002709`.
- Exited container: `flashnext-screen1-flashnext-moe-boundary-window-20261011-source-paths-v3`.
- Boot: `13858eef-ec68-44ea-a67c-9444933b7100`; official FP8 target, TP4/EP4,
  MTP1, unchanged placement and full 16-bit KV, load-only, zero generation.
- Packet history: `7c85ba72ea`, `110419fcff`, `4310bc1bcc`; source-paths-v3
  overlay manifest `6c9dafd3e265f5adc528408325e2824a5acc64882e51ac1234f348109963062b`.
  Image `vllm/vllm-openai-xpu@sha256:e4446310b1d30015e8fdc1a0a2ef1669ac6bef857cbe772487571ed5c1a926a9`.

The audit used CPU only, nice 19, OMP threads 2; read-only journal and logs of
the existing exited container. No launch, GPU probe, device open, Docker
run/start, service operation, port 8188 or LTX unit was used. Original run and
stage bytes were left untouched.

## Outcome

**The controller was the first STOP writer. Its initiating exception was lost;
the saved evidence cannot establish exactly why its startup loop unwound.**
At 04:32:32.809 UTC `DeferredStop.request` wrote `controller completion or failure`
from `supervise_locked`'s `finally` block. Workers subsequently encountered that
latch during construction and cooperatively drained. The nonzero container exit
was a consequence and the cleanup check then overwrote the original failure.
This is an inconclusive first-forward diagnostic, with no performance or output
qualification. The evidence-retention defect is fixed; the initiating startup
refusal is **not proven fixed**.

### Timeline (UTC)

[Audit index](../experiments/qwen38-flash-next-fp8-b70/reopen-20261008/evidence/moe-boundary-run1-cancelled-20261011/audit.json)
retains source hashes, original mtimes, loader line numbers, boundary endpoints
and memory samples around STOP. Mtimes below are original observed filesystem
times, not Git checkout times. Docker log timestamps are reception times.

| Time | Event and evidence |
| --- | --- |
| 04:27 | Controller unit starts its preflight/hash work. |
| 04:29:19 | Model verification completes, passing. |
| 04:29:21.303 | Controller explicitly admits load-only measurement despite a diagnostic prediction marked REFUSED; journal admission passes. |
| 04:29:21.813676 | Container starts (`container-exit.json.StartedAt`). |
| Before 04:32:31 | Ranks 0/1/2/3 write 279/258/276/288 passing allocation-boundary rows: **1,101 total**, no failed row. |
| 04:32:30.613182 | Last successful `kernel-latest.log` write; no post-admission fault line. |
| **04:32:32.809247** | Controller-owned STOP written; generic reason, no memory-watchdog event. |
| About 04:32:32.820–.846 | Worker `load_failed` receipts name the existing controller cancellation. First saved worker failure is PID 127, monotonic 10299.637313339; TP0 is 10299.654664594. |
| 04:32:33.015307 | SIGINT receipt written, command rc 0, no latch error. This is successful signal-command completion, not a clean model exit. |
| 04:32:34.898468 onward | Three benign `delayed_fput hogged CPU` lines; all follow STOP. |
| 04:32:37.422–40.899 | All four ordered rank teardown receipts complete. Native queue destruction is explicitly unverified. |
| 04:32:52.550589 | API reports engine initialization failure in timestamped container log. |
| 04:33:03.854156 | Container exits 1, `OOMKilled=false`, empty `Error`. |
| 04:33:05.314877 | Controller records verified exit for the watcher. |
| 04:38:10.617529 | Watcher reports clear completion of the 305-second post-exit gap. |
| 04:38:11.195116 | Unit journal prints only `REFUSED/STOPPED: Container exit was not clean`. |

### Candidate causes checked

| Candidate | Evidence and conclusion |
| --- | --- |
| 96 GB loading guard / `v5_final_host_rows` accounting | No `allocation_refused` event in any loader stream. Last TP0 admission: 59,160,727,552 available, 216,268,800 next bytes, 96,000,000,000 pressure limit. The traceback reaches the initial cancellation check before admission arithmetic. This location observes STOP; it does not identify its cause. |
| 24 GiB available-RAM watchdog | `watchdog_reason=null`, no `memory-watchdog-event.json`; lowest sampled availability 58,564,485,120 bytes. No recorded trip. |
| Boundary receipt write / root-owned directory | Every saved boundary row passed, no `BoundaryError` or permission failure in container log. Root-owned 0755 directory and root-owned readable rank files match the root workers that successfully wrote them. Controller writes sibling STOP in the steve-owned run directory, not inside `moe-boundary`. No evidence this ownership caused cancellation. |
| Kernel watcher / benign workqueue lines | No FAULT file; final watcher passed with `new_fault_lines=[]`. The unchanged classifier returns no new faults, and the benign lines appear after STOP. A watcher-latched failure would persist through the final receipt. |
| Prediction says REFUSED | It reports unknown full-serving bounds; calibrate-load explicitly treats prediction as diagnostic. The journal records successful admission and the container subsequently starts. It is not the cancellation trigger. |
| Controller heartbeat freshness / journal timeout / other startup check | Still unresolved. Heartbeat state at cancellation was overwritten by subsequent updates; neither the first exception nor its traceback was persisted. A transient heartbeat refusal is possible, but the final healthy heartbeat cannot prove or disprove it. |

The source explains the loss: the startup `except` stored `failure` and re-raised;
`finally` unconditionally sent a generic stop; its teardown `except` replaced
`failure` and re-raised the nonzero-exit error; `main` caught that error and
printed only its text. Thus neither calibration nor journal retained the first
exception. There is no sound basis to label one remaining possibility as proven,
raise memory limits, extend freshness deadlines or bypass a check.

### Host-memory comparison with attempt 8

GB here is decimal; accounted pressure is whole-host `MemTotal - MemAvailable`,
not a sum of RSS, pins and cgroup counters. Values come from the two actual
sample files, whose hashes are in the audit index.

| Measurement | Boundary run 1 | Attempt 8 |
| --- | ---: | ---: |
| MemTotal, bytes | 124,179,144,704 | 124,179,124,224 |
| Post-hash availability, bytes | 114,789,224,448 | 119,046,037,504 |
| Post-hash pressure, GB | 9.390 | 5.133 |
| Loading peak pressure, GB | **65.615** | **75.448** |
| Minimum loading availability, GB | **58.564** | **48.732** |
| Loading samples / elapsed seconds | 381 / 189.859 | 1,343 / 670.756 |
| Sampled cgroup peak, GB | 11.580 | 59.570 |
| Largest sample interval, seconds | 1.644 | 0.526 |
| Reached full load / startup forward | No | Yes; then GPU faults |

Run 1 started with about 4.257 GB more pressure but ended much earlier. Its
lower peak is not a memory saving or evidence of full-load fit. The 1.644-second
sample gap spans the cancellation transition (monotonic 10297.985742843 to
10299.629385933); it fails calibration's 1.5-second sampling gate after the fact,
but that verdict is calculated during final receipt writing and cannot have
initiated STOP. It also does not establish a three-second heartbeat failure.
Neither run reached a qualifying plateau; do not revise the certified memory
floor from this comparison.

## What worked

The saved placement checks and ordered four-rank teardown remained useful.
The controller, rank receipts, kernel timestamps and whole-host samples separate
cancellation from a GPU fault and rule out the proposed recorded memory trips.
The watcher kept observing through exit and its full quiet gap. No new kernel
fault was recorded in this run window; earlier boot events in journal admission
are historical, not faults during this experiment.

## What failed or remains uncertain

The harness lost the first exception, and earlier CPU tests stopped at admission
or checked individual functions rather than exercising failure through final
cleanup. No raw/remapped routing or first-GEMM receipt exists, so none of the
first-forward hypotheses has been cleared. A fresh admitted run must retain
its actual refusal if one recurs; the present CPU work cannot certify native
success or recover an exception that was never saved.

## Evidence and patches

- [Saved audit, memory comparison, source hashes and receipt excerpts](../experiments/qwen38-flash-next-fp8-b70/reopen-20261008/evidence/moe-boundary-run1-cancelled-20261011/audit.json).
- [Controller unit journal](../experiments/qwen38-flash-next-fp8-b70/reopen-20261008/evidence/moe-boundary-run1-cancelled-20261011/controller-journal.log) and [timestamped container log](../experiments/qwen38-flash-next-fp8-b70/reopen-20261008/evidence/moe-boundary-run1-cancelled-20261011/container.log).
- [Resealed packet/runbook](../experiments/qwen38-flash-next-fp8-b70/reopen-20261008/overlay-moe-boundary/README.md) and [patch](../experiments/qwen38-flash-next-fp8-b70/reopen-20261008/overlay-moe-boundary/boundary.patch).
- [CPU validation and source binding](../experiments/qwen38-flash-next-fp8-b70/reopen-20261008/evidence/moe-boundary-run1-cancelled-20261011/validation.json).
- [Attempt-8 analysis](2026-10-11-attempt8-fourth-incident.md).

**136 CPU tests pass**, including eight new regressions; the suite uses an audit
hook that forbids device opens, network connections and non-Git subprocesses.
Temporary test directories were removed.

The repair fsyncs the first controller exception before shutdown, prints it to
the unit journal, includes the exact rejected heartbeat when applicable, uses
the real exception in controller STOP, preserves an existing first-writer STOP,
and keeps cleanup errors separate in both calibration and diagnostic receipts.
The original exception remains the raised result even if cleanup or calibration
receipt writing fails. All memory, journal, freshness, load, teardown and gap
thresholds remain unchanged; the production overlay and native diagnostic hooks
retain their bytes. This is a causal-evidence repair, not an unproven threshold
change. Raw sample/loader files remain at the original paths with hashes here;
small decisive receipts and logs are retained in Git. No original was deleted.

## When to revisit

Do not rerun the old source-paths-v3 stage. The coordinator can use the runbook's
two fresh first-cause-v4 stage/run commands after current health, stop-gap and
host admission pass. Inspect `controller-first-failure.json` before downstream
teardown errors; a subsequent first-GEMM result is still required to answer the
native boundary question. CPU tests, staging and this closeout grant no GPU
window and do not replace the coordinator's current admission decisions.
