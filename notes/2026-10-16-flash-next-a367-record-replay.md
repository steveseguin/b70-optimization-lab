# Flash-Next A367 record replay: October 16, 2026

Packet: `experiments/own-xpu-runtime/stage1/packet4-prep/a367-replay/`, built by Codex (`3ebb1e4ee`; build note `notes/2026-10-16-flash-next-a367-replay-build.md`).

- Seal `78556b50…`, preregistration `a7fad58b…`.
- The owner approved the 114,840,824 KiB replay-only start floor ("Approve as written", 22:07 UTC). Record: `data/2026-10-16-flash-next-a367-replay/owner-approval-replay-20261016.json`.

Run `a367r-20261016T194524Z`, receipts in `data/2026-10-16-flash-next-a367-replay/window-20261016T194524Z/`:

- payload re-hash finished 22:13:55;
- health pass ended 22:14:05 (4 cards, zero faults);
- owner-window issued 22:14.

## First launch: refused by my own monitor (22:19:16)

The supervisor refused at the final admission check: "ltx/vLLM/ComfyUI process running". The match was my own foreground check command. Its command line contained `pgrep -f "VLLM::Worker_TP0"`, and the conflict scan (`(?i)(vllm|ltx[^ /]*|comfyui)` over every process argv) matched it.

Nothing launched and no output directory was created. The journal is in `unit-refused-self-match.log`.

Rule while a sealed window is admitting or running: no command line on the host may contain those words. Put checks in script files instead (`profile_check.py`, `conflict_check.py`).

## Second launch (22:20:11, unit `…-b`)

Admission passed and the server started at 22:20:32. Every session process ran at nice 0 on CPUs 0-31 with `OMP_NUM_THREADS=1`, the record's profile. Only the client is pinned to 4-15,20-31.

Result: pending.
