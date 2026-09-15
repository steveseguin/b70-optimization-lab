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
| 19:27:22 | Research container started with the qualified FP8/MTP1 arguments; its environment lacked five variables every qualified service sets (see below). |
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
  oneCCL) issued the exports, and why their backing grew during load. See the
  launch environment omission below.
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

- Do not relaunch this research recipe or the 09:27 freeze candidate unchanged.
  Both omitted five qualified environment variables (below), and an image-side
  cause is not excluded. Any diagnostic launch needs a watchdog that reads
  `/proc/meminfo` directly and kills the container on low available memory
  without waiting on Docker or the journal.
- Metadata validation remains unrun: no native gate, RPC or endpoint arm
  executed. It needs a base image that loads on this 16 GB host.
- Next admitted steps: one bounded standard health check, then restore the
  qualified R304 FP8/MTP1 service on port 18124 in `final-service` and repeat
  the full strict output check. The health check passed, but the restore
  stopped on a GPU fault during load; see the
  [restore fault note](2026-09-15-fp8-restore-gpu-fault.md).

## Launch environment omission (found after the first report)

A CPU-only comparison of the images and launch records, run after this note was
first written, found a launch difference. The environment findings below were
rechecked against the actual container records.

- Every qualified FP8 service container carries
  `PYTORCH_ALLOC_CONF=expandable_segments:True`, `FI_PROVIDER=tcp`,
  `FI_TCP_IFACE=lo`, `PYTHONHASHSEED=0` and `TORCHINDUCTOR_DETERMINISTIC=1`:
  the September 14 restored service and both restores on this boot (19:19 and
  01:58).
- The research launch had none of them.
  [run-mtp-lossless-server.py](../scripts/run-mtp-lossless-server.py) builds its
  environment from `amd-transfer-fp8-20260914/control-identity.json`, whose
  recorded environment omits all five. The 09:27 freeze candidate's launch
  (`amd-transfer-fp8-20260914/candidate-dflash/launch.json`) omits them too.
- The research load stalled during model construction. Qualified loads log
  "Filesystem type for checkpoints" in the same second as the attention backend;
  the research log never reached it, so no checkpoint file was opened.
- Its device open was the only one on this boot to log
  `Using 46-bit DMA addresses` (both cards, 19:28:23).
- Package comparison: torch 2.13.0+xpu, compute runtime 26.27.39122.11,
  oneCCL 2022.0.0, the SYCL/UR/UMF runtime and vllm-xpu-kernels are identical
  across the qualified, research and freeze images. vLLM differs (0.29.0 versus
  0.29.1rc1.dev47+gdc36fcce9), with no new pinning or IPC found on this model's
  load path.

Leading hypothesis, not verified: without expandable segments, torch allocates
device memory through USM in a context holding both GPUs. The Level Zero adapter
then makes each allocation resident on the peer GPU, which the compute runtime
implements by exporting a dma-buf, and xe's export populates system pages. An
upstream source change is not excluded, because the research and freeze images
share that source.

The research launcher now refuses to start until its environment contract
carries the five variables. Before any retry, run a bounded no-model diagnostic
on the research image under a host-memory watchdog: allocate 2 GiB on one GPU
with both GPUs visible and count dma-buf exports, then repeat with
`PYTORCH_ALLOC_CONF=expandable_segments:True` and with only one GPU visible.

## Evidence

Raw root `/mnt/fast-ai/bench-results/fp8-mtp-recovery-metadata-20260914`:

- `research-incident/image-comparison/` keeps the package lists and source
  comparison behind the section above.
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
