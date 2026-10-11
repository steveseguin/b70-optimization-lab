# Default-off MoE boundary diagnostic — CPU prepared, not executed

This separately sealed variant investigates sketch A of the
[attempt-8 audit](../../../../notes/2026-10-11-attempt8-moe-first-forward-audit.md).
It does not replace the production overlay. The fourth-incident halt remains;
an owner-authorized four-card window and valid existing admission are required.
The old owner acceptance does not authorize a launch after the fourth incident.

## Preregistered single-window plan

Use production TP4/EP4, official FP8 weights, attempt-6 placement, MTP1 and
16-bit KV unchanged. Run `calibrate-load` with `SCREEN1B_MOE_BOUNDARY=1`, the
96 GB loading guard and every existing host-memory, disk, exclusive-card,
source/image, health-receipt and boot-fault admission check. Submit **zero
generation requests**. The existing 64-token startup profile (including its
ordinary MTP profile and sampler) is the only forward. Warmup and graph capture
are disabled, and any later model execution fails before submission.

An independent CPU kernel watcher begins before container startup. It retains
the probe watcher's precise fault signatures, reports every 0.5 seconds, and
latches STOP/FAULT on a fault, lost journal access or its 2,700-second bound.
The boundary requires a clear same-boot journal receipt no older than three
seconds, synchronizes explicitly, rechecks the latch and only then reads back.
A missing native USM/context query remains explicitly unavailable evidence.

Load/readiness has the existing 30-minute bound. On clean readiness measure
the existing 20-second memory plateau. Then request one graceful stop, wait
at most 300 seconds for container exit, and require all four teardown receipts.
There is no forced kill, retry, reset, second launch, or recovery probe. Keep
the watcher through exit and a **305-second quiet gap**; an unresolved shutdown
preserves ownership for the coordinator. Admission also requires a verified
previous-stop UTC at least 305 seconds old. Every experiment directory is new.

Interpretation is preregistered:

- A boundary exception with a failed invariant and receipts before GEMM is
  evidence for hypothesis 1 (indices/remap) or 4 (ownership/metadata), depending
  on the check. A stale watcher or incomplete diagnostic is an inconclusive
  safety refusal, not evidence of a malformed model tensor.
- A complete clear receipt set and a synchronized first-GEMM completion on all
  four ranks, followed by a fault, exonerates the **checked index/span/ownership
  invariants** of hypotheses 1/4 for that call. It does not prove native mapping,
  USM registration or lifetime correctness that Python cannot query.
- A complete profile, clean plateau, four clean teardown receipts and clean
  watcher gap means the diagnostic run completes and supplies its memory
  plateau. It is neither a speed number nor a lossless-output qualification.
- A fault before validated first-GEMM completion remains inconclusive. Save
  its evidence and coredump before any owner-directed recovery.

Identity deltas from attempt 8: a separately pinned diagnostic manifest;
raw-alignment/remap/workspace/eleven-pointer receipts and explicit queue
synchronizations; independent fresh-heartbeat watcher; XPU graph flag 0,
compilation graph mode NONE, zero capture warmups and enforce-eager;
worker warmup/capture bypass and rejection of subsequent forwards. TP4/EP4,
512 global/128 local experts, model/quantization, MTP1 profile, 64 tokens,
context 4,352, KV bytes 376,569,856/rank, BF16-family KV, placement, NEO flags,
allocator settings and memory guards stay fixed. CPU process OMP threads are 2.
The gap and extra synchronization intentionally change diagnostic scheduling.

## Future authorized window command — not run by this task

The placeholder paths/timestamp must be replaced with the coordinator's fresh
receipt and actual prior stop. Do not pass the historical owner acceptance to
bypass the fourth-incident halt. A fresh authorized boot with a clean journal
and a fresh passing health receipt needs no owner-acceptance exception.

```sh
p=/home/steve/llm-optimizations/experiments/qwen38-flash-next-fp8-b70/reopen-20261008
stage=/mnt/fast-ai/bench-results/flashnext-moe-boundary-package-UNIQUE
run=/mnt/fast-ai/bench-results/flashnext-moe-boundary-window-UNIQUE
nice -n 19 env OMP_NUM_THREADS=2 PYTHONDONTWRITEBYTECODE=1 \
  SCREEN1B_MOE_BOUNDARY=1 python3 -B "$p/overlay-moe-boundary/build_patch.py" --stage "$stage"
nice -n 19 env OMP_NUM_THREADS=2 PYTHONDONTWRITEBYTECODE=1 \
  SCREEN1B_SOURCE_REPO=/home/steve/llm-optimizations \
  SCREEN1B_MOE_BOUNDARY=1 SCREEN_PRIVILEGED_FD_SCAN=1 \
  python3 -B "$stage/screen.py" run --mode calibrate-load \
  --loading-ram-guard-gb 96 --health-receipt /PATH/TO/FRESH-HEALTH.json \
  --previous-stop-utc 'YYYY-MM-DD HH:MM:SS UTC' \
  --run-dir "$run" --execute
```

The controller creates one owned user unit using Nice=19 and OMP_NUM_THREADS=2.
Its entrypoint refuses this staged overlay unless the enable variable is 1.
Container receipt paths are `/screen/moe-boundary/` and `/screen/watcher.json`,
which map to the new run directory. STOP and FAULT are siblings of those paths.
Existing production files, prior evidence and latches are never modified.

CPU validation: **122 passed, zero failures/errors/skips**; [source-bound receipt](../evidence/moe-boundary-cpu-20261011/validation.json).
`test_window.py` exercises command identity, explicit enable,
zero-generation-only admission, watcher freshness/latches, gap timing,
terminal markers, and runtime warmup/extra-forward refusal with synthetic
objects. It imports neither vLLM nor Torch and does not initialize any device.
Native behavior remains unqualified until the authorized window is run.

`test_boundary.py` runs synthetic good/bad inputs for alignment, ownership,
workspace and all eleven pointer roles; it executes the extracted production
Python wrappers with CPU operator doubles. Baseline, diagnostic-off and
boundary-on outputs match byte-for-byte for alignment, expert apply, GEMM and
workspace allocation. `test_artifacts.py` checks the unchanged off-path kernel
AST, the nonlocal early return, production hashes, exact patch application and
staged package hashes. This does not compile or qualify a native Triton kernel.

```sh
nice -n 19 env OMP_NUM_THREADS=2 MKL_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 \
  PYTHONDONTWRITEBYTECODE=1 /home/steve/.venvs/ltx25-baseline/bin/python -B \
  experiments/qwen38-flash-next-fp8-b70/reopen-20261008/overlay-moe-boundary/run_cpu_tests.py
```

The test runner forbids render-device opens, XPU public entry points, network
connections and non-Git subprocesses. Its temporary directories are removed.
The watcher keeps a failure latched while observing shutdown and the gap;
restored journal access never turns that run into a pass. A missing exit marker
or unreadable journal at the deadline leaves the window failed/incomplete.
