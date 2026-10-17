# Packet 57: coordinator diagnostic window

Preparation is CPU only. The command below is for the coordinator after
packet 55 releases cards 2+3 and its roughly 97 GiB host working set. This window
requires a quiet whole host and at least 97 GiB available before loading each
fresh pair on cards 0+1. Nothing here stops another unit.

One invocation runs **K0 → KD → W57-control → W57-attribution**. K0 exercises
new binary readiness on both cards without kernel execution. KD uses the
existing draft byte-comparison machinery: one bounded CPU reference and two
fresh device owners against unchanged packet 49 target captures. K1a/K1b/K2
operator evidence and W0p handoff evidence are inherited from the completed,
hash-pinned packet 56 chain; all numerical kernel and controller source bytes
are unchanged. The new native host code contains observation changes only.

Both WS-style arms use all 12 fixed prompts, the 128-token cap, a fresh rank
pair, complete per-request reset, zero cached tokens and the same packet 49
oracle. No fixture capture is added inside the timing sample. Control uses
packet 56's `token` timing path, including its existing deferred draft event
queries; it is not an event-free engine. The second arm records only generated
indices 9–16, including full draft sites and target layers 19/22 on rank 0 and
23/24 on rank 1. Layers 19/23 are QSA; 22/24 are GDN. Every target token must still
match the oracle, and matched arm output hashes and acceptance must agree.

This is diagnostic only. No output from either arm is eligible for speed
promotion or submission. GPU event times are read at existing waits/drains;
there are no new kernel barriers. Profiling and event bookkeeping still alter
overlap. The final report keeps the actual control and instrumented cycle
times, their ratios, and any scaled class allocation explicitly as estimates.
GPU clocks are never compared across cards. Draft embedding row decode/read
is CPU work within D; the draft does not recompute target PLE.

Rank 0's profiling queue is enabled for the whole instrumented arm, while
detailed event recording is limited to the fixed sample. Rank 1 already
enables queue profiling in the control for its draft checks. The full-cycle
comparison therefore also reports perturbation outside the detailed sample.

CPU-only command inspection:

```bash
P=experiments/own-xpu-runtime/stage2/packet57-attribution
nice -n 19 taskset -c 4-15,20-31 python3 -B "$P/p57_window.py" --plan
```

The exact coordinator command, from the repo root, is below. Supply the actual
reviewed UTC kernel-fault boundary for this boot in `REVIEWED_THROUGH`; it is
never inferred or used to waive a later fault. Preserve the already-approved
`LD_LIBRARY_PATH`.

```bash
P=/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet57-attribution
OUT=/home/steve/own-xpu-runtime-results/packet57-attribution/build/device-cards01-a
systemd-run --user --unit=packet57-attribution-cards01-a \
  --property=Type=exec --property=Nice=0 \
  --property=KillSignal=SIGTERM --property=KillMode=control-group \
  --property=SendSIGKILL=no --property=TimeoutStopSec=infinity \
  --working-directory=/home/steve/llm-optimizations \
  taskset -c 0-3,16-19 env -i PATH=/usr/bin:/bin OMP_NUM_THREADS=2 \
  LD_LIBRARY_PATH="$LD_LIBRARY_PATH" \
  python3 -B "$P/p57_window.py" --authorized-device-window \
  --faults-reviewed-through "$REVIEWED_THROUGH" --output "$OUT"
```

Budget: **about 88 minutes planned (5,265 s including cooldowns), 8 h total
cooperative deadline**. Stage work estimates are 1 min K0, 30 min KD and 20 min per
suite arm. Individual watchdogs are 10 min, 3 h, 2 h and 2 h, bounded by the shared 8 h
deadline. Actual duration is unmeasured for packet 57. Cooldowns are 90 s after
K0 and 305 s after each remaining stage, including the last. These are admission
budgets, not latency predictions. The wrapper polls exact fault signatures,
checks fresh owner teardown, does not retry, and always records a final passive
kernel check. A deadline requests cooperative exit through inherited helpers;
it never authorizes a hard kill, driver reset or reboot.

Only the registered fresh output is accepted. Keep failed evidence and any
retained owner; do not rename the path to retry. `window.json` records overall
status, each stage has its own receipt, and `attribution-summary.json` joins
host cycle timings with the sampled per-rank `sites.jsonl` event rows. Empty or
missing required attribution fails the diagnostic completeness check.
