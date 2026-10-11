# MoE boundary proof with the production router-padding fix

**October 11 v5 proof completed:** the fixed experimental TP4 line loads and
profiles cleanly, 15,895 receipts/rank, zero failed checks/new kernel faults,
and container exit 0. [Fourth-incident closure and proof limits](../../../../notes/2026-10-11-fourth-incident-closed.md).
Calibration still refuses qualification for unknown VRAM reserves; this was
one zero-generation profile with warmup/capture bypassed. The commands below
are the preserved load-only proof plan, not the next generation screen.
That next step needs a separately sealed bounded boundary-on variant.
Earlier “pending” statements below describe the pre-proof state.


**October 11, v4 result:** all four raw `[64,10]` router tensors contained
signed int32 `-1` in all 640 slots. The strict boundary stopped before native
alignment; rank 3 won the STOP-file race. The source trace identifies V2 dummy
padding reaching a native aligner that lacks a negative-ID guard. This is a
padding-contract defect, not a rank-3 placement defect.
[Evidence, root cause and limits](../../../../notes/2026-10-11-moe-boundary-caught-router-ids.md).

The repository's [production compatibility fix](../overlay-fix-router-padding/README.md)
is included byte-for-byte in this v5 diagnostic package. Screen 1b XPU routers
now route padded rows normally. The boundary's `[0,512)` check is unchanged;
all other boundary/watchdog/admission checks remain enabled. Production native
qualification and full-model output gates are still pending. No GPU ran in
this repair. Earlier v1–v4 stages and run evidence remain immutable.

## Preregistered single-window plan

Use production TP4/EP4, official FP8 weights, attempt-6 placement, MTP1 and
16-bit KV unchanged. Run `calibrate-load` with `SCREEN1B_MOE_BOUNDARY=1`, the
96 GB loading guard and every existing host-memory, disk, exclusive-card,
source/image, health-receipt and boot-fault admission check. Submit **zero
generation requests**. The existing 64-token startup profile (including its
ordinary MTP profile and sampler) is the only forward. The worker hook bypasses warmup and graph capture, and any later model execution fails before submission.

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
synchronizations; independent fresh-heartbeat watcher; worker warmup/capture
bypass and rejection of subsequent forwards. The compilation identity now
matches attempt 8 exactly: mode 0 (`CompilationMode.NONE`), graph mode
`FULL_DECODE_ONLY`, one configured warmup, capture sizes `[1, 2]`, empty
compile sizes, XPU graph flag 1, and no `--enforce-eager`. The startup profile
already selects eager execution internally (`need_eager=is_profile`); the
diagnostic worker returns before the configured warmup/capture can run. TP4/EP4,
512 global/128 local experts, model/quantization, MTP1 profile, 64 tokens,
context 4,352, KV bytes 376,569,856/rank, BF16-family KV, placement, NEO flags,
allocator settings and memory guards stay fixed. CPU process OMP threads are 2.
The gap and extra synchronization intentionally change diagnostic scheduling.

## Future authorized window command — not run by this task

Set `HEALTH_RECEIPT` to the coordinator's fresh passing receipt and
`PREVIOUS_STOP_UTC` to the verified actual stop (`YYYY-MM-DD HH:MM:SS UTC`).
These two commands require those values; do not reuse the old health receipt
or assume the earlier stop time is still current. Existing admission checks
and the 305-second gap still apply. Do not pass historical owner acceptance
to bypass the fourth-incident halt.

**Both stage and run directories must be fresh.** Never edit or reuse the
failed `/mnt/fast-ai/bench-results/flashnext-moe-boundary-package-20261011T04`
or `/mnt/fast-ai/bench-results/flashnext-moe-boundary-package-20261011-compilation-v2`;
also preserve both `flashnext-moe-boundary-*-20261011-source-paths-v3` directories.
Their bytes and failed-window evidence remain preserved. If either destination
below already exists, choose a new unique suffix in both commands.

```sh
nice -n 19 env OMP_NUM_THREADS=2 PYTHONDONTWRITEBYTECODE=1 SCREEN1B_MOE_BOUNDARY=1 \
  python3 -B /home/steve/llm-optimizations/experiments/qwen38-flash-next-fp8-b70/reopen-20261008/overlay-moe-boundary/build_patch.py \
  --stage /mnt/fast-ai/bench-results/flashnext-moe-boundary-package-20261011-router-padding-v5

nice -n 19 env OMP_NUM_THREADS=2 PYTHONDONTWRITEBYTECODE=1 \
  SCREEN1B_SOURCE_REPO=/home/steve/llm-optimizations \
  SCREEN1B_MOE_BOUNDARY=1 SCREEN_PRIVILEGED_FD_SCAN=1 \
  python3 -B /mnt/fast-ai/bench-results/flashnext-moe-boundary-package-20261011-router-padding-v5/screen.py \
  run --mode calibrate-load --loading-ram-guard-gb 96 \
  --health-receipt "${HEALTH_RECEIPT:?set fresh health receipt path}" \
  --previous-stop-utc "${PREVIOUS_STOP_UTC:?set verified previous stop UTC}" \
  --run-dir /mnt/fast-ai/bench-results/flashnext-moe-boundary-window-20261011-router-padding-v5 --execute
```

The controller creates one owned user unit using Nice=19 and OMP_NUM_THREADS=2.
Its entrypoint refuses this staged overlay unless the enable variable is 1.
Container receipt paths are `/screen/moe-boundary/` and `/screen/watcher.json`,
which map to the new run directory. STOP and FAULT are siblings of those paths.
The stage includes the sealed production router fix; prior stages, evidence and latches are never modified.

Historical CPU validation after the source-path repair: **128 passed, zero failures/errors/skips**;
[source-bound receipt](../evidence/moe-boundary-paths-cpu-20261011/validation.json).
The [124-test compilation receipt](../evidence/moe-boundary-compilation-cpu-20261011/validation.json)
remains historical evidence; its predictor test stopped before the failing census read.
The [original 122-test receipt](../evidence/moe-boundary-cpu-20261011/validation.json)
is retained under its original seal.
`test_window.py` exercises command identity, explicit enable,
the real staged `build_prediction` identity path (synthetic metadata; stop at
the allocation census), refusal of the old graph mode, zero-generation-only
admission, watcher freshness/latches, gap timing,
terminal markers, and runtime warmup/extra-forward refusal with synthetic
objects. It imports neither vLLM nor Torch and does not initialize any device.
`test_staged_paths.py` imports the complete staged controller and runs the
README's `run --execute` admission path from an unrelated working directory,
with an explicit stop before the first Docker operation. It uses real package
seals, placement/candidate calculations, runtime source hashes and installed
model config/index plus bounded headers (131 shards; no tensor payloads).
Every input open must name an existing file; the test also requires every seal
member, model header, source hash member and historical placement census to
have been opened. Disk capacity, idle cards, socket binding and journal are
CPU doubles, and a synthetic health receipt goes through the real validator;
this is not live host admission. Relative receipt and tiny synthetic model
metadata paths, missing source-repo refusal and dormant client/routing paths
have separate checks. The installed model metadata and pinned source tree are
required for this lab integration test. Native behavior remains unqualified
until the authorized window is run.

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

## Compilation repair and resealing, October 11

At 04:00:23 UTC the coordinator's old staged controller failed before launch:
`ValueError('v5 prediction requires compilation NONE / FULL_DECODE_ONLY')`.
That message names a required pair, not two alternatives: compilation mode 0
and graph mode FULL_DECODE_ONLY. The diagnostic had changed the graph mode to
NONE, graph flag to 0, warmups to 0, capture sizes to empty and added
`--enforce-eager`. Its tests checked those flags in isolation but never called
the staged memory predictor. The repair restores all five attempt-8 settings;
`memory_plan.py`, production `screen.py`, runtime hooks and the production
overlay remain unchanged. No prediction/admission rule has been relaxed.

The new CPU integration tests create a real external stage, build its command,
and exercise its actual `build_prediction` through `launch_identity`. They
compare the complete predictor identity (except command hash) and compilation
CLI tail to the frozen production calibrate-load builder, then confirm the
old graph mode is still refused. No real checkpoint or allocation census is
needed for this prelaunch regression check. The runtime bypass and
extra-forward refusal tests remain in the suite.

After changing copies, regenerate the derived seal, check it, and run the CPU
suite above (including `test_artifacts.py`'s builder, fresh-stage hash and exact
patch-application tests). Do this before creating a coordinator stage:

```sh
nice -n 19 env OMP_NUM_THREADS=2 python3 -B experiments/qwen38-flash-next-fp8-b70/reopen-20261008/overlay-moe-boundary/build_patch.py
nice -n 19 env OMP_NUM_THREADS=2 python3 -B experiments/qwen38-flash-next-fp8-b70/reopen-20261008/overlay-moe-boundary/build_patch.py --check
```

Diagnostic overlay manifest SHA256: `2879f61968e86a79d13cbfdf3e14fdc951805cb87482878832c8a97937a510cb`.

Patch manifest SHA256: `cb3d7f54f404ae4076998139547f0b3d5ca704a19328f2228400ff5022713dfb`.


## Source-path repair and staged-command audit, October 11

At 04:08:41 UTC the coordinator's compilation-v2 stage passed admission/disk
checks, then refused while reading the historical placement census under
`/mnt/fast-ai/bench-results/data/`. The failure was in
`placement_plan.enumerate_candidates`, called at the end of `build_prediction`:
`HERE.parent` meant the original lane directory before staging, but the
bench-results directory afterward. The actual tracked census is
`experiments/qwen38-flash-next-fp8-b70/data/20260913-q38-expert-host-placement-a315-census-5gib-mc2-per-rank.json`
under the source repository. The controller's existing environment override
did not reach that imported helper. The prior identity test stopped before
allocation and therefore never exercised this read.

The variant now seals a shared `source_paths.py`. Host repository inputs use
`SCREEN1B_SOURCE_REPO`; a staged package without that variable refuses rather
than guessing a checkout from its parents. Only the variant copies changed;
the production controller, predictor, overlay and historical stages retain
their bytes. Prediction arithmetic, input hash requirements and admission
thresholds are unchanged; the diagnostic seal includes the new support files.

| Input or command path | Resolution after staging |
| --- | --- |
| Historical placement census and four routing census files | Source repo + `experiments/qwen38-flash-next-fp8-b70/data/` |
| Git main check, model-verification script and pinned owner-acceptance location | Source repo; controller already used the override, now shares the resolver |
| Relative health/calibration/owner receipt arguments | Source repo; absolute paths unchanged; normalized before worker handoff |
| Explicit relative model root, bounds override, bounds source root, predictor launch JSON | Source repo; absolute model/runtime paths unchanged; shard filenames remain relative to their model root |
| Image plan, bounds/contract defaults, tuned placement map (`placement-attempt6-v5.json`), certified map, Python overlay, all seal/support members | Stage directory, checked against the diagnostic seal; never redirected to production copies |
| Protocol benchmark clients, exact-depth fixture, realistic suite and output authorities | Source repo; dormant in this zero-generation diagnostic |
| vLLM tuned GEMM configuration lookup | Container runtime `configs/`; this command supplies no `VLLM_TUNED_CONFIG_FOLDER` override |
| Entrypoint, package and model bind mounts | Absolute stage/model paths; `/screen-package`, `/model`, `/screen` container paths unchanged |
| Run output, caches, watcher receipts, STOP/FAULT and worker controller | Fresh run directory and stage; absolute worker paths and source-repo environment forwarded |

`vram_plan.generate` also resolves routing inputs through the source repo;
its output stays in the supplied package and it is not invoked by the screen.
Never regenerate files in an existing sealed coordinator stage. Use the fresh
router-padding-v5 stage/run commands above with current coordinator admission.


## Run 1 cancellation and cause retention, October 11

The [run-1 audit and memory comparison](../../../../notes/2026-10-11-moe-boundary-run1-cancelled.md)
cover 04:27–04:38 UTC. The controller wrote STOP at 04:32:32.809 UTC;
all 1,101 boundary rows passed, and no MoE forward was reached. Host pressure
peaked at 65.615 GB, available RAM stayed above 58.564 GB, no allocation refusal
or memory-watchdog event was saved, and the independent watcher stayed clear
through the post-exit gap. The benign `delayed_fput hogged CPU` messages begin
after STOP and do not match the fault classifier.

The original controller exception is **not recoverable** from these receipts.
`supervise_locked` held it only in memory, then its `finally` block sent the
generic completion/failure stop and replaced it with the nonzero-exit error.
A transient stale heartbeat, journal/read failure or another controller check
cannot be distinguished. Do not raise a timeout, memory ceiling or watchdog
age based on this run, or label the root-owned receipt directory as the cause.

The v4 packet changes only controller evidence/stop handling:

- Before cleanup, write and fsync `controller-first-failure.json` and print the
  same record to the unit journal. It includes phase, timestamps, traceback,
  watchdog/stop state and snapshots of STOP, FAULT and the heartbeat. A rejected
  heartbeat also carries the **exact evaluated** receipt and evaluation time.
- Put the actual exception in a new controller STOP. Preserve an existing
  worker/watcher STOP with exclusive creation; never overwrite its first cause.
- Keep `calibration-load.json.failure` and the raised exception tied to the
  first failure. Record a cleanup error separately in `cleanup_failure` and
  `controller-cleanup-failure.json`. Receipt-write failure still reaches the
  one-shot graceful stop and the original exception remains visible.

The 96 GB load ceiling, 24 GiB available-RAM watchdog, three-second heartbeat,
30-minute load bound, five-minute shutdown bound, 305-second gap, model,
placement and all native hooks are unchanged. The repair can expose a recurring
refusal; it does not establish that a fresh native load will pass it.

**136 CPU tests pass, zero failures/errors/skips.** The CPU suite additionally drives the complete staged supervision/finally path
with process, clock, HTTP, memory and host-state doubles. It covers the original
exception plus an unclean exit, command timeout, failed evidence writes,
cleanup-only failure, first-writer STOP retention, stale heartbeat evidence and
benign-kernel-line classification. No Docker, systemd, server, HTTP or device
operation is executed by those doubles. See the [validation receipt](../evidence/moe-boundary-run1-cancelled-20261011/validation.json).

After the coordinator's next admitted run, inspect `controller-first-failure.json`
first, then `controller-cleanup-failure.json`, calibration and rank receipts.
If file writing failed, use the unit journal's `controller_failure` record.
No unchanged source-paths-v3 rerun: retain that stage and use the fresh v4 pair
above. Native first-forward localization remains pending.

## Router-padding repair and proof identity, October 11

The only production behavior change is in the two router `_get_padding_mask`
helpers: with `B70_SCREEN1B=1` on XPU, return `None` to the existing native
router. No sentinel is clamped, remapped to expert zero, or accepted by the
boundary. No routing formula, weight, map, alignment size, PLE buffer, GEMM,
KV precision, compilation flag or admission threshold changes. Compared to
v4, profile padding now performs ordinary expert computation, so its runtime
and memory plateau must be measured anew under the existing limits.

`test_router_padding.py` reproduces v4's exact all-minus-one hash with CPU
operator doubles, exercises the actual production helpers and wrappers,
checks mixed/valid/tied routes and unchanged active-row weighted output,
and passes the unchanged router boundary on all four rank maps. It verifies
that only the intended helper/import AST changed and replays the production
patch exactly. Native kernels and whole-model parity remain untested here.
Current CPU result: **143 passed, zero failures/errors/skips**;
[source-bound receipt](../evidence/moe-boundary-router-ids-20261011/cpu-validation.json).
The staged-command test still runs the complete CPU admission/prediction
path and stops before Docker. Reseal with `build_patch.py`, then `--check`,
and run the restricted CPU suite before using the two fresh commands above.
