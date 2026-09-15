# Metadata research server: host out of memory during model load

The separate newest-base V1/native-MTP control for the metadata campaign
(image `sha256:506fcc26…`, upstream vLLM `dc36fcce9`, port 18129) never became
ready. While its two workers loaded the target weights, host RAM ran out and
the machine stalled for about five hours. No request reached the server, the
metadata client never ran and no GPU fault signature was recorded. This closes
the research stage of the [recovery and metadata plan](2026-09-14-fp8-recovery-metadata-plan.md)
as a failure; it is not a result about the metadata change.

## Timeline (UTC)

| Time | Event |
| --- | --- |
| Sep 14 19:26:38 | Qualified R304 service stopped once for the planned replacement (strict 12/12 had just passed). |
| 19:27:22 | Research container started with the qualified FP8/MTP1 arguments and environment. |
| 19:28:23–24 | Both workers opened the B70s and began loading the model. Last worker log line. Last owner memory sample: 8.65 GiB available, container cgroup 5.5 GiB and rising. |
| 19:40:25 | systemd-journald: under memory pressure, flushing caches. |
| 19:59:04 | Root-filesystem `jbd2` hung-task report (blocked > 122 s). Later kernel lines arrive minutes apart. |
| 19:59:06 | Owner monitor finally raises a `journalctl` timeout; its stop path then stalls in `docker inspect`, attempts no stop and writes `STOP_UNCONFIRMED` hours later. |
| 23:47:55 (journal time) | First global OOM kills: 15 processes of the logged-in desktop session, including `systemd --user` and `dbus-daemon`. |
| Sep 15 00:12–00:31 | OOM kills of login-screen (gdm) session processes. |
| 00:23:22 | OOM kill of one vLLM tensor-parallel worker (anon RSS 0.6 GiB); EngineCore starts shutdown. |
| 00:25:32, 00:39:24 | The remaining worker's allocations fail inside xe dma-buf export. |
| 00:39:35 | Container exits: code 1, Docker `OOMKilled=true`. Memory recovers. |

## Established

- At the first OOM report about **12.65 GiB of the 15.2 GiB RAM** was outside
  the anon, file, slab, page-table, unevictable and free counters, which is
  consistent with driver-held pages. The 12 GiB container limit cannot contain
  those pages because they are not charged to the container's memory cgroup.
- The failing allocation stack was `drm_prime_handle_to_fd_ioctl` →
  `xe_gem_prime_export` → `ttm_bo_setup_export` → `ttm_bo_populate` →
  `xe_ttm_tt_populate` → `ttm_pool_alloc_page`: user space was exporting GPU
  buffer objects as dma-bufs during load, and each export populated system pages.
- No xe memory-fault, CAT error, engine reset or wedged line appears in the
  launch-to-exit window, the ring buffer or the window after exit.
- Postflight at 01:43: same boot, container exit confirmed, no model process on
  either render node (only the restarted login screen's display processes on
  one node), ports 18124/18129 closed, 14.25 GiB available.

## Not established

- Which user-space component (vLLM, torch-xpu, Level Zero/compute runtime or
  oneCCL) issued the exports, and why their backing grew during load.
- Whether the user-reported freeze at 09:27 EDT on September 14 had the same
  cause. That candidate (`3be4c6c9…`) was also built on `dc36fcce9` and also
  stopped during target loading, but its journal recorded no OOM before the
  machine froze.

## Harness defects found

1. `subprocess.run(..., timeout=30)` cannot return while its child is stuck in
   uninterruptible I/O. The owner loop in
   [run-mtp-lossless-server.py](../scripts/run-mtp-lossless-server.py) blocked
   for 30 minutes, so its memory sampling, 20-minute startup deadline and fault
   checks all stopped running, and it never stopped the container.
2. There is no host-memory guard. Startup relies on kernel fault lines, a dead
   container or the deadline, none of which fired.
3. The same blocking calls exist in the shared FP8 helper's monitor loop. They
   are harmless on the qualified image, which does not exhaust host memory.

## Disposition

- Do not launch `dc36fcce9`-based images on this host again unchanged. Any
  diagnostic launch needs a watchdog that reads `/proc/meminfo` directly and
  kills the container on low available memory without waiting on Docker or the
  journal.
- Metadata validation remains unrun: no native gate, RPC or endpoint arm
  executed. It needs a base image that loads on this 16 GB host.
- Next admitted steps: one bounded standard health check, then restore the
  qualified R304 FP8/MTP1 service on port 18124 in `final-service` and repeat
  the full strict output check. The health check passed, but the restore
  stopped on a GPU fault during load; see the
  [restore fault note](2026-09-15-fp8-restore-gpu-fault.md).

## Evidence

Raw root `/mnt/fast-ai/bench-results/fp8-mtp-recovery-metadata-20260914`:

- `research-server/` keeps the owner's original receipts unchanged
  (`state.json` = `stop_unconfirmed`, `stop.json`, `STOP_UNCONFIRMED`,
  `server.log`, `memory.jsonl`, `kernel.log`).
- `research-server/postflight.json` (SHA256
  `24f5de535af8456fae708ab9584f19ec180ee5112d7e7b8c5b52037c53ff27fc`) holds the
  confirmed exit, the filtered OOM and allocation-failure records, memory
  accounting, render owners and listener checks, and hashes of the preserved
  receipts and full windows.
- `research-incident/` holds the full kernel journal windows, the ring buffer
  and the post-exit container inspection. They stay local because they contain
  whole-host process tables.
