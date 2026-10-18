# Packet105s: first head-split device smoke

Proposal: `../../ops/lane-queue/proposed-p105-smoke-B.txt`.
One lane-B candidate load, `head-split-compute`, one cold
`incident-retrospective` request, exactly 64 generated tokens checked against
the packet49 `iq3-p49-split32-v1` oracle prefix. No control, retry, warmup or
full-suite request. This is diagnostic evidence only, never a speed verdict.
It does not qualify the BCS transfer choice or either full grid.

The sealed packet105 sources from commit `39a10d801` and shared pinned v4
wrapper remain unchanged. The wrapper has no subset CLI, so this small driver
adapts its verified source in memory with exact, single-occurrence anchors:
the worker selects its existing first prompt and 64-token request, and the
report expects that single exact request. The wrapper's fault review,
97 GiB admission, live memory guard, lane lease, device monitoring, supervision,
graceful drain and release-before-report remain intact. No rebuild is needed.
The queue retains its reviewed boot/two-fault admission and stops on a third
fault; preparation does not authorize or execute a device run.

The fresh output is
`stage2/screen/v4-lanes/evidence/p105s-B-head-split-compute-incident64-v1`
under this experiment. The driver refuses other output paths. The packet105
B/A grids and every fixed grid output name remain untouched.

After drain, the smoke report rechecks all 64 oracle tokens and the incident
receipt hash. It requires nonempty, balanced transfer receipts for
`hidden-export` and `hidden-import` (5120 bytes each), plus `best-export` and
`prefix-export` (16 bytes each). Raw `p105-transfers.jsonl` files are retained
and hash-bound in the smoke summary and window receipt. Hidden-export timing
includes its producer dependency wait; it is not pure DMA latency.

CPU verification, from the repository root, uses:

```bash
nice -n 19 taskset -c 8-15,24-31 python3 -B experiments/own-xpu-runtime/stage2/packet105s-smoke/test_smoke.py </dev/null
nice -n 19 taskset -c 8-15,24-31 python3 -B experiments/own-xpu-runtime/stage2/packet105s-smoke/plan.py </dev/null
```

The tests mock device execution and check one-request dispatch, exact-prefix
failure, missing transfer receipt refusal, fixed output refusal, and unchanged
lifecycle functions. `plan.py` copies queue code to a temporary directory,
installs only this proposal there, and runs the existing queue planner.
Evidence is retained here; no live queue, service or device is touched.

Initial `git pull --rebase` refused pre-existing unrelated unstaged changes.
`git fetch origin main` then confirmed HEAD and origin/main were identical.
Those changes were preserved.
