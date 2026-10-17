# Packet 64 orchestration

Prepared October 17, 2026 on CPU. This directory adds orchestration around the
existing sealed packets. No GPU or systemd unit was launched during preparation,
and none of the four frozen trees was edited. Live device overlap is untested.

The coordinator starts it **once**, from this checkout, with:

```bash
cd /home/steve/llm-optimizations
systemd-run --user --unit=packet64-orchestration \
  --property=Restart=no --property=Nice=19 \
  --property='CPUAffinity=8-15 24-31' \
  --property=KillMode=process --property=SendSIGKILL=no \
  --property=ExitType=cgroup --property=TimeoutStopSec=infinity \
  --working-directory=/home/steve/llm-optimizations \
  /usr/bin/bash /home/steve/llm-optimizations/experiments/own-xpu-runtime/ops/packet64-orchestration/orchestrate.sh
```

The outer coordinator stays at nice19 on helper cores. It starts `packet64-chain`
at nice0 on `0-3,16-19`; each companion gets its own `screen-*` unit at nice0
on `4-7,20-23`. All units disable restart and SIGKILL, use `KillMode=process`,
`ExitType=cgroup`, and infinite stop timeout. The approved library path comes
from the coordinator's existing `/tmp/claude-1000/-home-steve/fn-run/p49.env`;
its contents are not logged. All Python invocations use `-B`.

## Sequence and selection

1. Wait for `v3-laneA-d7` and `v3-laneB-d7` to be inactive. Units collected by
   systemd count as inactive only after their work was observed or all six
   window files exist. An absent not-yet-started lane is not completion.
   Also require all six individual `screen-v3-p64-*` services to be inactive.
   The start wait is bounded to four hours; a failure never retries a launch.
2. Require exactly two kernel fault lines, using the actual `FAULT` and
   `DELETED` expressions parsed from `stage1/packet4-prep/driver/window_driver.py`.
   Recheck before commands and launches and throughout both wait loops. A boot
   change, unreadable/empty journal or any other count refuses further work.
3. Read the six d7 outputs under `screen/v3-packet64/evidence/`:
   `p64-1-{prod-ctl,drafthc-ctl,drafthc-batch}-{A,B}`. Require current-boot,
   successful, drained windows with matching lane and selection identity,
   BF16/cache-zero summaries, the twelve registered prompts and all thirteen
   hash-bound receipts (including the separate incident request) with
   `exact_oracle is True`.
4. Compare the class-balanced conventional 99-interval decode median against
   production **on the same lane**. A candidate must be strictly faster on
   both lanes, with all six screens exact. Missing, failed or altered candidate
   evidence falls back to production; invalid production evidence aborts.
   Among eligible candidates choose the largest minimum relative gain across
   the two lanes; ties favor draft-HC/control. Never infer an unscreened
   production/batch combination. These remain diagnostic screen numbers.
5. Write `selection.json` once, then call `fast_reseal.py --placement 1` with
   the selected draft/miss settings. Run `chain_seal.py --verify`,
   `check_inputs.py`, `storage_precheck.py`, `plan_gate.py` and
   `queue_runner.py --plan` in that order. Any failure prevents chain launch.
6. Run exactly the full-chain command from
   [WINDOW.md](../../stage2/packet64-record-bundle/WINDOW.md), including both
   prefix receipts, `--wait-oracle`, and fresh `device-cards01-a`. The packet
   itself owns all admission, per-window checks, cooldowns and stop handling.

Fast reseal is the coordinator's explicitly requested selection operation;
this preparation never executes it. At live execution it writes the packet's
designated active selection/seal files. Screen execution likewise creates new
evidence in the wrapper's registered evidence directory, without editing its
source. The orchestration refuses reused outputs and does not resume a chain.

## Lane B

Before chain launch, passive CPU preflight verifies the lane-aware wrapper's
seal, the existing boot-bound `review-window-04.json`, and both companion
plans. If these fail, the companion is skipped with a reason. The chain's
own mandatory prechecks still apply.

The jobs are `1-split23-production-control` (23/25), followed by
`1-production-control` (another 24/24 sample). Each uses
`screen/v3-packet64-lanes/screen.py`, never the standalone wrapper. Its
`run_lane_b_screen()` takes `lane-B.lock` while holding `protocol.lock` and
checking `hold-lane-B`. It keeps the lease through native exit, shared drain,
postflight and the empty-card check. Timing windows publish the hold before
waiting for B to drain, and keep it until their own postflight completes.
No lane-B native GPU owner survives into a timing window; a waiting CPU
wrapper may remain alive. The orchestration does not take these locks itself,
remove markers, or change the 60-second drain spacing.

Only one companion unit is launched at a time, and its successful
`lane-coordination.json` is required before the next. If the chain completes
first, remaining jobs are skipped. An already-started companion finishes
under its own supervision. Any live failure stops new launches and logs the
owned unit names; no process is killed, reset, restarted or automatically
recovered. The sealed wrappers retain their original watchdogs and refusal
paths, including uncertain-owner markers. Overlap still needs device
qualification; CPU tests are not a speed or device-quality result.

## Logs and CPU reproduction

`orchestrate.log` receives every step, comparison, command output, child-unit
output, refusal and normal/caught-error exit. `selection.json` and the runtime
log are local evidence, ignored by Git. The lock prevents duplicate supervisors.
Uncatchable SIGKILL or a host crash cannot emit an exit line; neither is used.

```bash
nice -n 19 taskset -c 8-15,24-31 python3 -B \
  experiments/own-xpu-runtime/ops/packet64-orchestration/test_orchestrate.py
```

The tests create synthetic receipts in temporary directories and invoke the
actual `orchestrate.sh --dry-run MOCK_JSON` entry. Dry mode uses a mock backend
for every external operation, including journal reads, systemd queries,
resealing, prechecks and launches. The test also replaces `subprocess.run`
with a refusal during the complete simulated workflow. Even an empty mock
cannot fall through to live mode. [dry-run.log](dry-run.log) contains only
synthetic speeds and simulated commands, not lab measurements.

The frozen companion's `ProtocolTests`, `DrainTests` and `AdapterTests` also
passed on CPU (34 tests). These exercise holds, races, stale/crashed owners,
native-owner exit, one-screen leases and postflight refusal using temporary
files and mock process trees. See [validation.json](validation.json),
[tests.log](tests.log) and [CPU closeout](CPU-CLOSEOUT.md).
