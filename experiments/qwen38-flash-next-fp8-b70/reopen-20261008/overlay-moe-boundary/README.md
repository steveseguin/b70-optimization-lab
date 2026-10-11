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
their bytes and failed-window evidence remain preserved. If either destination
below already exists, choose a new unique suffix in both commands.

```sh
nice -n 19 env OMP_NUM_THREADS=2 PYTHONDONTWRITEBYTECODE=1 SCREEN1B_MOE_BOUNDARY=1 \
  python3 -B /home/steve/llm-optimizations/experiments/qwen38-flash-next-fp8-b70/reopen-20261008/overlay-moe-boundary/build_patch.py \
  --stage /mnt/fast-ai/bench-results/flashnext-moe-boundary-package-20261011-source-paths-v3

nice -n 19 env OMP_NUM_THREADS=2 PYTHONDONTWRITEBYTECODE=1 \
  SCREEN1B_SOURCE_REPO=/home/steve/llm-optimizations \
  SCREEN1B_MOE_BOUNDARY=1 SCREEN_PRIVILEGED_FD_SCAN=1 \
  python3 -B /mnt/fast-ai/bench-results/flashnext-moe-boundary-package-20261011-source-paths-v3/screen.py \
  run --mode calibrate-load --loading-ram-guard-gb 96 \
  --health-receipt "${HEALTH_RECEIPT:?set fresh health receipt path}" \
  --previous-stop-utc "${PREVIOUS_STOP_UTC:?set verified previous stop UTC}" \
  --run-dir /mnt/fast-ai/bench-results/flashnext-moe-boundary-window-20261011-source-paths-v3 --execute
```

The controller creates one owned user unit using Nice=19 and OMP_NUM_THREADS=2.
Its entrypoint refuses this staged overlay unless the enable variable is 1.
Container receipt paths are `/screen/moe-boundary/` and `/screen/watcher.json`,
which map to the new run directory. STOP and FAULT are siblings of those paths.
Existing production files, prior evidence and latches are never modified.

CPU validation after the source-path repair: **128 passed, zero failures/errors/skips**;
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

Diagnostic overlay manifest SHA256: `6c9dafd3e265f5adc528408325e2824a5acc64882e51ac1234f348109963062b`.

Patch manifest SHA256: `f5e6301cc9310d7108f75d5fefac84101ec16f6ce0f19b7de37325ee58621511`.


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
source-paths-v3 stage/run commands above with current coordinator admission.
