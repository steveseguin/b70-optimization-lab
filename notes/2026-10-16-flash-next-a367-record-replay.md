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

**Result: failed. The watchdog tripped and the client never ran.**

- At 22:24:08, during weight load (shard 11 of 131), one 0.5 s sample took 1.738 s. Every other gap was at most 0.521 s. This tripped `sampler delayed >1.5s`, and one SIGINT went to the API server at 22:24:10.
- Cause: every sample read `/proc/<pid>/cmdline` for every session process. That read takes the target's mmap lock, which a worker holds while stalled in a FUSE page fault on the USB model mount.
- The API server deferred the SIGINT until engine init finished. Loading, profiling and Triton compilation completed. Then the engine shut down in order: all four workers reported "XPUWorker shutdown: done" at 22:38:13, and every process was gone at 22:38:33 with returncode 1 (KeyboardInterrupt traceback).
- That overran the 300 s soft teardown limit, so `teardown-incomplete.json` was written. The overrun was wait time, not a stuck device.
- The 305 s watch completed, with zero GPU fault lines.
- Evidence: `window-20261016T194524Z/attempt-b/`.

**Fix `7aca7df2a`.** The sampler reads `comm`/`status`/`cgroup` each sample and reads `cmdline` only until a worker's rank is known, caching it per pid. A new test fails if cmdline is re-read. 233 CPU tests pass with zero seal mismatches. The seal changed from `78556b50` to `bb473f8e`; the preregistration is unchanged.

The memory sentence is identical except for the seal hash. It was recorded under the owner's standing instruction "if you run into an issue, fix the issue. simple" (`owner-approval-replay-20261016-b.json`).

## Third launch: replay c (22:50:24, run `a367r-20261016T224454Z`)

- Health pass ended 22:47:53 (zero faults).
- The 22:13:55 payload receipt was still valid.
- Admission passed and the server started at 22:50:47.

My launch shell's command line contained conflict-pattern words: the health script path `ltx25-b70` and the venv path `vllm-xpu`. It exited before the supervisor's final scan. Launches now go through script files.

**Result: PASSED. The record reproduces bit-for-bit.**

| Field | Replay c | Record (A367, 2026-09-13) |
|---|---|---|
| Prompt SHA256s | 12/12 equal | — |
| Output SHA256s | **12/12 equal** | — |
| Fresh-response and final-gate booleans | all equal; final gate passed | — |
| Class-balanced median (99 intervals after TTFT) | **47.109780 tok/s** | 46.854250 |
| All-prompt median | 46.534274 tok/s | 46.322147 |

- `replay.json`: passed, ready, clean_exit and gap_complete all true. The checker printed "PASS: bit-identical outputs and all gates hold".
- Timeline (UTC): ready 23:08:50 (model load 677 s, graph capture 45 s, engine init 322.6 s); client 23:09:41-23:15:37 (rc 0); one SIGINT 23:15:37; all owners gone at 23:15:50 with returncode 0; 305 s watch complete; zero GPU fault lines.
- Host memory need through generation: 104,784,640 KiB. The minimum MemAvailable was 14.17 GB at shutdown (generation 14.39 GB), about 1.9 GB above the 12,000,000 KiB live reserve.
- Worst sampler gaps: 1.433 s (23:12:13, generation) and 1.263 s (23:08:39, server becoming ready). Every other gap was at most 0.525 s. The cmdline cache removed the load-phase stalls, but a remaining `/proc`/cgroup read can still block close to the 1.5 s trip. **Next packet:** take MemAvailable on its own fixed cadence and do the per-rank/cgroup scan in a separate thread, so attribution reads cannot delay the watchdog sample.

**No localmaxxing submission.** +0.5% over the record is inside this host's 3-10% run-to-run drift, from one server, on the unchanged identity. It confirms the record; it does not beat it.

Evidence:

- `data/2026-10-16-flash-next-a367-replay/window-20261016T224454Z/run/` (raid originals hash-pinned);
- `/mnt/raid-models/bench-results/a367r-20261016T224454Z/`.
