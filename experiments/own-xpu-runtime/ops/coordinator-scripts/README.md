# Coordinator scripts (own-runtime IQ3 campaign)

These are copies of the coordinator's working scripts from `/tmp/claude-1000/-home-steve/fn-run/`, taken 2026-10-19 because a reboot wipes `/tmp`. They encode the lane and hold procedures used tonight. Paths inside them still point at `/tmp/claude-1000/...` (log files, scratchpad); copy them back there, or edit `LOG`/`S`, before use.

| Script | Use |
| --- | --- |
| `onecard-chain.sh <packet> <orchestration> [--check]` | One-card record chain waiter: derives unit/output/fault-review from the packet's READY/WINDOW.md; seal + verify_ready; holds both lanes; drain spacing; fresh fault review; hash-checked launch; freezes Codex from WS; the deadline path thaws Codex and keeps PAUSE. |
| `onecard-chain-quiet2.sh` | The same, freezing Codex from before K1a. Quiet reruns are **not** a paging fix (review 35). |
| `smoke-then-v5r.sh <codex-prefix> <READY> <smoke> <v5> <lane> <launch UTC> [rehearse path]` | After a Codex job exits with a fresh READY (`ready_for_device` true): plan + rehearse + queue the smoke, then the v5 after an exact smoke. |
| `q-after-codex.sh` | The same for a single proposal. |
| `hold-onecard4.sh` | Whole-host one-card session: waits for a two-card sequence, then smoke → v5 (all Codex frozen) → census, with deadlines; always releases. |
| `chain-58aj.sh` | Waits for a Codex handoff, then `--check`, then the chain. |
| `codex-launch2.sh NAME` | Codex exec (cores 8–15/24–31, nice 19, stdin /dev/null) with one resume after an API capacity error. |
| `monitor-loop3.sh` | Event monitor: lane events, markers/holds/latches, teardown, GPU fault count, Codex exits, chain units, waiter logs. |
| `stale-sweep2.sh` | Archives dead-owner lane markers/latches after 60 s, only when faults are unchanged and the lane is idle. |
| `rh-gate.py` | Rehearsal gate tolerating only ≤ 25 GB floors and the preparation-probe WARN (used while opsreview7 was mid-edit). |
| `autoq-ready.sh`, `post-58ahb-launch.sh` | Older helpers kept for reference. |

The lane restart procedure after a FAILED or refused job: wait for stale-sweep (faults unchanged), archive `done-X.txt`, `reset-failed` the screen units, then start a new `lanequeue-X<n>` unit with `systemd-run --user`.
