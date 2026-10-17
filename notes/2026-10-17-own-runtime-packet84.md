# Packet84 record bundle 2 — October17

Packet84 copies packet80 without editing it. The coordinator baseline is ordered
cleanup, wide HC, production route/norm, wide64 experts and rank1 at24/24.
Independent choices add packet81 expert reads, packet82 recurrence and packet83
Q4 or smaller draft prefixes. The unchanged target still verifies every token.

Milestone1: GNU-host and Intel-device builds passed. No device binary was run.
Full-size CPU allocation/dispatch checks and dual-compiler byte checks are in
progress. The build is about112MB so far, below the1.5GB limit. Work uses nice19,
CPUs8–15/24–31, python3 -B, stdin /dev/null and an8GiB process bound.

The initial git pull --rebase refused because other packets have work in progress.
A fetch showed HEAD and origin/main identical; no other work was stashed or moved.
The explicit coordinator pins override the earlier local packet80 route selection.
The new draft choices stay at production until both screen lanes confirm them.

[Bundle](../experiments/own-xpu-runtime/stage2/packet84-record-bundle/README.md)
and [orchestration](../experiments/own-xpu-runtime/ops/packet84-orchestration/README.md).
