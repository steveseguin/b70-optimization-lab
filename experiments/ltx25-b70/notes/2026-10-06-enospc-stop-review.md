# Packet 97 disk-full incident: shutdown review

The owner paused LTX for consolidation. The active launcher was verified
read-only through `/proc/2652074/cmdline` as packet 97, run
`encoder-server-place-97-two-way-w2-b1-p1-dxpu2-r2`, manifest
`6e232f72a9835727323c383bc9baaa167844b58dc6400a5de43a3b9eb4e44b9f`.
Do not assume that PID remains valid in a later session.

The coordinating agent observed an empty queue but coverage receipt
`consolidation-20261006-idle1` still reported `pipeline_busy=1` and
`pipeline_running=1`, matching `d97-idle-enospc` from about nine hours earlier.
The run log contains disk-full errors during tensor/evidence writes and the
message `Previous VAE graph failure; halt submissions and inspect evidence`.
New requests remain stopped. The coordinator initially withheld a stop signal
until the blocked worker could be identified; the later stack evidence and
single-signal incident plan are recorded below.

## What the exact loaded source establishes

The files below were read from the sealed local packet, not imported or run:
`/mnt/fast-ai/bench-results/ltx25-baseline-20260913/prepared-encoder-place-97`.

- `source/scripts/ltx_pipeline.py`, `_worker_loop`: after a job starts,
  `_RUNNING` increments. Its nested `finally` sets `job.done` and decrements
  `_RUNNING` even when the job fails. `record_failure` catches evidence-write
  exceptions. Thus one busy/running job is not explained merely by a missing
  on-disk done marker; a worker has not finished its job/failure handling.
- `source/scripts/pipeline_decode_node.py`: a decode job can wait on a native
  or replica lock, capture/replay sharing, device synchronization, or the
  bounded preview-writer queue. These are possible locations, not a diagnosis.
- `source/main.py:55`: `faulthandler` is enabled for fatal errors. A traceback
  on SIGINT is registered only when `--debug-hang` is enabled, and still raises
  `KeyboardInterrupt`; it is not a nonterminating diagnostic.
- `launch/serve-encoder.py`, `server_args`: this launcher does not pass
  `--debug-hang`. No supported SIGUSR stack-dump hook was found in the checked
  launcher, main or pipeline diagnostic helper. Do not send an arbitrary
  signal assuming it prints a stack.
- `source/main.py:582`: normal `KeyboardInterrupt` exits the event loop and
  shuts down the asset manager. It does not drain or join LTX pipeline workers;
  `_ensure_worker` creates daemon threads. SIGINT is therefore not a substitute
  for the campaign's pre-stop quiescence proof.

A read-only `/proc/2652074/task/*/wchan` sample found the main thread in
`ep_poll` and nearly all other sampled threads in `futex_do_wait`, with a few
sleeping. A futex wait does not distinguish a Python event/lock from an Intel
runtime wait. This inspection does **not** prove that the remaining worker is
CPU-only, blocked on an unsignaled event, or safe to interrupt.

No debugger was attached, no signal sent, and no model/accelerator code run
by this source-audit agent. The normal stop protocol remains
`scripts/run-campaign-97.sh:222`: prove queue and worker quiescence, recheck the
fault latch and PID/start identity, then one SIGINT with a bounded wait and
no hard-kill escalation. Passive OS wait information alone was insufficient
to distinguish the blocked worker's activity.

## Later evidence: CPU progress-display lock stall

The coordinator subsequently captured
[`ltx-python-stacks.txt`](../../../data/maintenance/consolidation-20261006/ltx-python-stacks.txt)
with a bounded `timeout 15 py-spy dump --nonblocking` invocation. It succeeded
without pausing the process or injecting code. It shows:

- `ltx-sample-0` in `tqdm.std.acquire → refresh → update → __iter__`, between
  iterations of `sample_euler_ancestral_RF`.
- `tqdm_monitor` blocked acquiring the same class of progress-display lock.
- Both encoders, the other sampler, both decoders and the preview writer
  waiting for jobs; the prompt worker is waiting on its empty queue and the
  main thread is in the asyncio selector.

This identifies a CPU lock stall rather than an unknown location inside the
sampler. The installed `tqdm/std.py:1353` acquires its display lock, calls
`display()`, then releases the lock without a `finally`. A display write that
raises ENOSPC can therefore leave the lock acquired. This is a source-backed
explanation consistent with the incident, not proof of which thread originally
held the leaked lock. The installed `tqdm/_monitor.py` uses a nonjoining
`_atexit_signal`, so its exit hook does not itself wait for the blocked monitor.

The Python stack alone did not prove that every prior asynchronous GPU command
had finished. The coordinator independently sampled eight DRM clients over
ten seconds: each client's `drm-cycles-*` counters stayed stable and all
`drm-active*` values were zero. Total-cycle counters advanced with wall-clock
time; that is not active GPU work. Together with the idle workers and roughly
nine hours without progress, this supported a **CPU-lock incident shutdown**,
not a claim that the normal pipeline `running=0` gate passed.

The coordinator then sent exactly one SIGINT, retaining the bounded wait and
no-escalation rule. Shutdown succeeded. The final
[`ltx-stop.json`](../../../data/maintenance/consolidation-20261006/ltx-stop.json)
records `process_gone=true` after the zombie was reaped. Postflight found no
port-8188 listener, no render-node holders and no kernel GPU fault. No new
server was started; no hard kill, restart, reboot or host-setting change was
used for the shutdown. These operational observations are recorded by the
coordinator; this source-audit agent did not send the signal.

## Evidence preservation

The incomplete run's empty summary and truncated engine log are retained in
[`../data/consolidation-20261006.json`](../data/consolidation-20261006.json).
There is no timed-throughput receipt from which to reconstruct a result.
The separately recovered packet-98 helper passed 24 guarded CPU tests; that
recovery does not repair or alter the running packet-97 process.

The coordinating agent separately reported that the external disk mounted
read-only, but a vendor SMART bridge command produced an error, a kernel USB
reset and a read I/O error. It was unmounted with no writes. That attempt does
not qualify the external backup as healthy or justify deleting local copies.
Use the main storage incident receipt for exact command/output and follow-up;
this audit did not mount the disk or execute the bridge command.
