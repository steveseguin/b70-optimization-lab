# A367 tracer feasibility microtests — 2026-10-16

Prepared for the coordinator; **no GPU test, model, health probe or service ran**.
The [new scripts](../experiments/own-xpu-runtime/stage1/packet4-prep/a367-census/feasibility/)
are outside the census seal: `seal_packet.py` uses `HERE.iterdir()` plus
`is_file()`, not recursion. All 61 existing seal members still match. Sealed
packets, shared runtimes, host settings and device ownership are unchanged.

From the repository root, in the coordinator's admitted execution context:

```bash
bash experiments/own-xpu-runtime/stage1/packet4-prep/a367-census/feasibility/run_feasibility.sh
```

The driver applies `nice -n 19`, `taskset -c 4-15,20-31` and `python3 -B`.
The device interpreter path is inside the script. `--plan` is CPU-only.
Output defaults to `/mnt/raid-models/bench-results/a367-tracefeas-<UTC-stamp>`;
`--output` accepts another unique stamp there. Existing directories are refused.
The driver does not manage services or admission; cards 0–3 must be available.

| Order | Step | Expected time | Wall budget | Expected memory |
|---|---|---|---|---|
| 1 | Graph control | 10–30 s | 90 s | 1–2 GiB host; <256 MiB card 0 |
| 2 | Graph traced, unpaused | 20–60 s | 120 s | Same + 0.25–1 GiB tracer host |
| 3 | Graph traced, paused/resumed | 20–60 s | 120 s | Same as step 2 |
| 4 | Four-rank CCL control | 20–60 s | 150 s | 4–8 GiB host total; <512 MiB/card |
| 5 | Four-rank CCL paused/resumed | 30–120 s | 180 s | Same + 0.25–1 GiB tracer host total |

Total expected: **100–330 seconds**, below ten minutes. These are unmeasured
estimates, not caps. Graph tensors total about 160 KiB. CCL payload is 64 MiB +
4 KiB/rank, plus a 64 MiB validation temporary. Runtime overhead dominates.
The five-step order follows the brief; no extra unpaused CCL run is added.

Graph: eight operations on resident 64×64 FP32 tensors (two adds, multiply,
sine, clamp, matmul, softmax, copy), five warmups, one capture/shared graph pool,
50 eager calls and 50 replays. Capture has no H2D or host reads. ITT marks each
phase and iteration/replay batch (one replay/batch). Synchronization inside each
iteration marker makes timestamp containment valid **only for this microtest**;
its wall times and attribution must not be transferred to the async census.

CCL environment comes directly from the sealed census `command_and_environment`:
all `CCL_*`, `FI_*`, `LD_PRELOAD`, `ZE_AFFINITY_MASK`, and `LD_LIBRARY_PATH`.
Ambient overrides are excluded. The clean A367 source establishes `xccl`
(`platforms/xpu.py:111`) and `file://` rendezvous (`multiproc_executor.py:138`,
`network_utils.py:135`). `parallel_state.py:1660,1685` constructs `FileStore` and
passes `init_method=None, store=store`. Unique rendezvous files use local ext4.
The 4 KiB all-reduce runs **before readiness/resume**, exercising lazy oneCCL
initialization as the server's warmup does (`xpu_worker.py:114`). The 64 MiB
all-reduce follows resume; both synchronize and their sums are checked before
`destroy_process_group`. Every rank records UNIX/monotonic stage timestamps.

Graph readiness follows warmup/capture; CCL readiness follows init/4 KiB on all
ranks. A separate `unitrace --resume <session>` command must return zero with
its acknowledgement before `go` is created. Extra helper log lines are allowed.
After work and CCL teardown, the driver pauses and releases waiting ranks to
exit. Failed sessions also get one final pause. The exact kernel/ITT/verbose/pid
flags and 4096-event buffer match the census; no profiler or xpu-smi is used.

`summary.json` records commands, allowlisted environment, source/script/binary
hashes, every step's status/rc/duration, and control rc/acknowledgements. Pending
steps have null rc. Nonzero exit, overrun or control failure stops later steps.
`OVERRUN` prints and waits; stage watchdogs print `STALL at stage X` after 120 s
and keep waiting. There are **no kills, signals, timeout commands or retries**.
The parent uses `spawn(join=False)` and polls individual processes, avoiding
`ProcessContext.join`, which kills peers on error. Errors request cooperative
exit through a file; native-blocked peers may wait indefinitely. Framework
failures can still terminate a rank. Traces/logs are retained, never truncated.

`feasibility.json` is written when the driver ends. During a stall or afterward:

```bash
nice -n 19 taskset -c 4-15,20-31 python3 -B \
  experiments/own-xpu-runtime/stage1/packet4-prep/a367-census/feasibility/analyze_feasibility.py \
  /mnt/raid-models/bench-results/a367-tracefeas-<stamp>
```

Graph `yes` requires timestamped device `gpu_op` kernels in all 50 eager/replay
iterations, matching kernel-name multisets, both trace variants and clean
lifecycles. `no` means visible eager kernels but no replay kernels in complete
traces. `partial` covers missing/ambiguous evidence, name/count mismatch or
variant disagreement. Host submit events never count. Counts are per replay.
CCL `yes` means paused init/first-collective reached 120 s, with seconds or a
watchdog lower bound and a successful control; `no` requires clean completion
below that threshold. Missing evidence yields null/incomplete. All stage timings
are compared with control; a stall is an observation, not proof of causation.

- Graph `yes` + CCL `no`: consider the conditional graph census after the original
  reference/admission/memory gates. Full-model four-rank attribution is unproven.
- Graph `no`/`partial` + CCL `no`: no graph decomposition is established. A separately
  admitted eager arm may be considered if eager kernels are visible.
- CCL `yes`/incomplete: neither paused full-model trace arm is cleared. Diagnose
  first; no automatic eager fallback. These tests never waive census gates.

All **15 CPU tests passed**, covering arguments, synthetic traces, stage/stall
analysis, summary validation, real CPU-child overrun waiting, fake control
acknowledgements and cooperative exit on failed resume. Shell syntax, Python AST
parsing and the five-step plan passed; the 61 census seal hashes matched.
`unitrace --version` exited 0: `2.4.0 (a5bab309f4ffdd78bd127035c46f5f75371160f8)`.

**`unitrace /bin/true` was not run:** contrary to the brief's CPU-only premise,
the preloaded collector's `tracer.cc::Init` calls `UniTracer::Create`
(`tracer.h:49`), then `InitializeL0` (`utils/utils_ze.h:27`), including
`zeInit(ZE_INIT_FLAG_GPU_ONLY)`. That device-initialization smoke belongs to the
coordinator's device window. No substitute or claimed pass is recorded.

Repeat CPU checks with `nice -n 19 taskset -c 4-15,20-31 python3 -B -m unittest
discover -s experiments/own-xpu-runtime/stage1/packet4-prep/a367-census/feasibility
-p test_cpu.py -v` (one shell command).
