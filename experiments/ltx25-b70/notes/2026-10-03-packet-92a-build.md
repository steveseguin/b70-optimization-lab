# Packet 92a: is the pipeline bound by its shared interpreter? (build, 2026-10-03)

Built offline. **Not launched.** R = `/mnt/fast-ai/bench-results/ltx25-baseline-20260913`.

This packet implements the diagnostic from
[the process-split design](2026-10-03-process-split-design.md), section 1, on
91b's code.

## What the packet adds

Starting from `prepared-encoder-decode-91b`, the packet adds:

- `source/scripts/ltx_gil_probe.py`
- `graphs/scheduler-knob.json`

It changes `ltx_pipeline.py` and the sampler, decode and encode nodes (plus
their node copies), and the embedded checker. Nothing else changes: every
graph arm and the oracle are as in 91b.

None of the instruments touches a tensor, a stream, a device, RNG state or
the order of GPU work. Every helper catches everything, following the same
never-raise discipline as the busy-window helpers.

### 1. Per-thread CPU

- **Per job.** `ltx_pipeline._worker_loop` records `time.thread_time()`
  around `job.fn()`; it appears as `detail.cpu_seconds` in every
  encode, sample and decode receipt.
- **Per request.** Each node's `_apply` records `apply_cpu_seconds` (the
  prompt thread).
- **Per thread.** Sampler, decode and encode receipts carry
  `gil.cpu`: utime+stime of every thread of the process, read from
  `/proc/self/task/*/stat` with 10 ms ticks, named from `threading`.
  - Lane threads are named `ltx-sample-*`, `ltx-encode-*`,
    `ltx-decode-*` and `ltx-preview-writer`.
  - The prompt thread registers as `lane-prompt:prompt`.
  - The probe thread is excluded from the lane sum.

### 2. Lock-wait probe

- **What it measures.** Thread `ltx-gil-probe` sleeps 0.5 ms in a loop and
  records each overshoot into a geometric histogram (ratio 2^¼, 4 µs-16 s).
  The overshoot is the time spent waiting to get the interpreter lock back,
  plus OS wake-up.
- **Draining.** Sampler receipts and knob receipts drain the histogram. The
  analyzer skips each arm's first sampler drain, because it spans the gap
  between arms.
- **Own cost.** Measured offline on this host: **0.0125 CPU-s per wall-s,
  about 1,800 samples/s, idle overshoot median 0.064 ms.**
- **Caveat.** A thread that wants the lock makes the holder hand it over at
  the next switch interval. The probe can therefore add at most one forced
  hand-off per switch interval to the contention it measures.

### 3. Switch-interval knob (`LTXSchedulerKnob`, graph `graphs/scheduler-knob.json`)

- **When it applies.** `sys.setswitchinterval` is applied only when
  `ltx_pipeline.busy()` is 0, meaning no job is queued or running. Finished,
  uncollected tail jobs do not count.
- **When it refuses.** It waits up to 60 s, then refuses and writes a receipt
  with the reason.
- **What else it records.** Each knob receipt also drains the lock-wait
  histogram and snapshots per-thread CPU. Every sampler, decode and encode
  receipt records `gil.switch_interval_s`.
- **Restoring 5 ms.** Any node that latches a failure restores 5 ms
  (`restore_default`). The runner also sets 5 ms after the last arm, and
  again after any failed arm.

## Gate

`--check-only`, with server_args elided:

```
gate rc=0
{
  "status": "inactive-startup-check-passed",
  "run_dir": ".../encoder-server-gil-92a",
  "packet_manifest_sha256": "b201580c08ea6e540a4b2bee70b1fd4a4e8480c254c37391e5be07773d329fb9",
  "limits": "No device discovery, locks, process changes or GPU work; exclusive preflight occurs only at launch"
}
```

- **Packet:** `R/prepared-encoder-gil-92a`, **manifest sha256
  `b201580c08ea6e540a4b2bee70b1fd4a4e8480c254c37391e5be07773d329fb9`**.
- **Checks:** no stale pins, and custom-node imports resolve.

## Launch

The server is launched with timers off: the busy-window timers cost about 12 %
per clip, and the packet's own probes are what is being measured.

```
P=/mnt/fast-ai/bench-results/ltx25-baseline-20260913/prepared-encoder-gil-92a
nohup env LTX_BUSY_WINDOWS=0 /home/steve/.venvs/ltx25-baseline/bin/python -B $P/launch/serve-encoder.py --packet $P --manifest-sha256 b201580c08ea6e540a4b2bee70b1fd4a4e8480c254c37391e5be07773d329fb9 --run-name encoder-server-gil-92a > /mnt/fast-ai/bench-results/ltx25-baseline-20260913/encoder-server-gil-92a.log 2>&1 &
nohup bash /home/steve/llm-optimizations/experiments/ltx25-b70/scripts/run-campaign-92a.sh > /mnt/fast-ai/bench-results/ltx25-baseline-20260913/campaign-92a.log 2>&1 &
```

`run-campaign-92a.sh` runs on one server, on the control placement (decode on
xpu:3 only, `pipe-samp2-tsh`):

| Step | Prompts | Index base | Switch interval | Clips verified |
| --- | --- | --- | --- | --- |
| warm | 3 | 209089 | 5 ms (default) | 0 (fills) |
| idle baseline | - | - | 5 ms | knob drain, 30 s idle, knob `f92a-idle` |
| s05a | 40 | 209189 | 5 ms | 37 |
| s01 | 40 | 209289 | 1 ms | 37 |
| s20 | 40 | 209389 | 20 ms | 37 |
| s05b | 40 | 209489 | 5 ms | 37 |
| final knob | - | - | 5 ms | - |

- **Between arms:** a 30 s settle, a queue-empty check, then the knob. A
  refused knob leaves the server up with exit 5.
- **Exactness:** checked per arm by the fixtures client. An oracle mismatch
  (rc 3) is recorded and the next arm runs. Any other arm failure resets the
  knob to 5 ms and leaves the server up.
- **Sync:** after every arm and every 10 completed prompts.
- **Bounds:** every client call runs under `timeout`.
- **Commits:** receipts are committed, not pushed.
- **Stop:** only on proven quiescence, as in 91b. The queue must be empty
  and every sample, decode and save job must have its done marker. Exit
  codes are listed in the script.

## Reading the result

```
/home/steve/.venvs/ltx25-baseline/bin/python -B /home/steve/llm-optimizations/experiments/ltx25-b70/scripts/analyze-gil-92a.py \
  /mnt/fast-ai/bench-results/ltx25-baseline-20260913/encoder-server-gil-92a \
  /home/steve/llm-optimizations/experiments/ltx25-b70/data/gil-92a
```

For each arm the analyzer prints:

- exactness and the stream interval median/mean;
- sampler, encode and decode job medians;
- lane CPU-s per wall-s and the busiest single lane thread (both from the
  /proc snapshots between the arm's first and last sampler receipt);
- lock-wait median/p95 and the probe's own CPU.

It then prints the verdict, with each preregistered threshold next to the
measured number.

- **CONFIRMED** needs all of these:
  - lane CPU ≥ 0.85 in both 5 ms arms, with no thread above 1.0;
  - lock-wait median ≥ 1 ms in both 5 ms arms, with the idle median below
    0.2 ms;
  - sampler or decode job median moving by ≥ 8 % between the 1 ms and 20 ms
    arms.
- **REFUTED** needs lane CPU ≤ 0.6, lock-wait median below 0.3 ms, and both
  job medians within 3 % between the 1 ms and 20 ms arms.
- **INDETERMINATE** otherwise. The next step is then 92b (decode in a child
  process).

## Tests (CPU only, lane venv, no XPU)

| Test | Result |
| --- | --- |
| `test-packet92a-gil-probe-cpu.py` | 8/8 |
| `test-packet91-decode-placement-cpu.py` | 11/11 (server-identity fixtures now include `ltx_gil_probe.py`) |
| `test-packet90c-instrumentation-stdlib.py` | 6/6 |
| `test-ltx-graph-capture-stdlib.py` | pass |
| `test-ltx-pipeline-lookahead.py` | 7/7 |
| `test-packet-custom-node-imports-cpu.py` | pass |

The 92a tests cover:

- the probe starts once, drains consistently and stays cheap;
- percentiles read the histogram correctly;
- the CPU snapshot names threads and sees a busy thread;
- no helper raises under a broken `/proc`, a broken `setswitchinterval` or a
  broken `busy()`;
- the knob refuses while busy, applies when idle, and range-checks its value;
- a latched decode failure restores 5 ms;
- receipts carry the switch interval and CPU fields;
- the analyzer's verdict logic and CPU arithmetic.

## Unverified offline

- **The /proc tick counts on the live server.** `thread_time` and the 10 ms
  per-thread ticks may count time spent in driver ioctls differently from
  Python work. This is the design note's open question.
- **Whether `setswitchinterval` changes anything at all here.** Some torch
  XPU calls may hold the lock regardless of the interval. A null shift is
  then weaker evidence than the thresholds assume, which is why the CPU and
  lock-wait rules must also agree before the verdict is REFUTED.
- **The probe's perturbation under load.** It was measured idle only. The
  live receipts report its CPU per arm.
- **Arm order is fixed (5, 1, 20, 5 ms).** The repeated 5 ms arm measures
  drift but does not randomise against it.
