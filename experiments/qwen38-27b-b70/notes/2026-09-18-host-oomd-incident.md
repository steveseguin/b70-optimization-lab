# The host ran out of memory and systemd-oomd killed the user's desktop session

On the night of September 17 (EDT) two memory-hungry jobs overlapped on this
15 GiB host: a kernel compile inside a Docker container and the first GPU run of
the MiniMax-H3 video lane, which loads a 27 GB text encoder. Host memory ran
out. The compiler was killed first, and then `systemd-oomd` -- the userspace
out-of-memory daemon, which kills on *memory pressure* rather than on an
allocation failure -- worked its way up the user's session and killed the
desktop, and finally the user manager itself (`user@1000.service`).

Killing the user manager killed every `systemd-run --user` unit with it, which
on this host is how all unattended lab work runs. So three queued sessions, the
service restore, and the session monitors all died at once.

**No GPU was involved.** There is no `xe` fault, CAT error, engine reset or
coredump line anywhere in the kernel log for this window. Both cards are free
and no container is running. This is a host-RAM incident, not a repeat of the
September 16/17 GPU faults.

**Everything is halted, and nothing will be restarted by the agent.** The FP8
two-card service has been down since 02:43 UTC and is still down. See "What must
happen next" below.

## Timeline (UTC; the host's own clock is EDT = UTC-4)

| Time | Event |
| --- | --- |
| Sep 18 02:43:12 | FP8 two-card service on 18124 stopped by the MiniMax-H3 session, as designed. Its restore step immediately failed with `[Errno 98] Address already in use` -- the port race again (see below) -- so the service never came back. |
| 03:03:51 | The r312d **variant b** kernel build started in a Docker container (8 GiB cap, `JOBS=2`). |
| 03:05:07 | The build's `icpx` frontends were OOM-killed: `icpx: error: unable to execute command: Killed` in the recipe log. The session log printed `rc=0` (wrong -- see the harness defect below) but its own artefact check caught it: `variant b: no library`. |
| 03:05:07 | The MiniMax-H3 first-light run started in the same second (`smoke_h3.sh one`, `STEPS=8`, run `smoke-20260918T030507Z`), under `systemd-run --user --scope --property=MemoryMax=4G`. |
| 03:05:11 | It reached phase `encode.load` -- the 27 GB INT8 text encoder. **Its log has nothing after this line.** |
| 03:06:52 | `systemd-oomd` killed `app-gnome-update-notifier`: memory pressure on `/user.slice/user-1000.slice/user@1000.service` at 58.07% for more than 20 s (limit 50%). |
| 03:09:15 | `systemd-oomd` killed `org.gnome.Shell@wayland.service` -- the user's desktop -- at 82.46% pressure, and `org.gnome.SettingsDaemon.Housekeeping`. |
| 03:09:59 | `systemd-oomd` killed `user@1000.service/init.scope`: **the user manager itself** (pid 2101, SIGKILL). `user@1000.service` is now `failed (Result: signal)`. |
| 03:10:10 | `gnome-keyring-daemon` killed. |
| 03:18:41 | The kernel's `oom_reaper` reaped the orphaned python 137924 (the MiniMax runner). GDM then started a fresh greeter session `c1`. |

## Root cause

Two jobs whose real host-RAM needs were never measured were allowed to run at
the same time on a host with 15 GiB of RAM:

1. **The kernel build** wanted more than its 8 GiB container cap with `JOBS=2`
   (two `icpx` frontends compiling SYCL template code at once). The container
   limit contained *it*, so the kernel OOM-killer took the compilers -- that part
   worked as intended.
2. **The MiniMax-H3 text-encoder load** wants roughly 27 GB of host reads to
   materialise a 25.3 GiB resident encoder, and it was run under
   `--property=MemoryMax=4G`.

The `MemoryMax=4G` was meant as a tripwire: the idea was that the cgroup limit
would kill the runner before it hurt the host. It did the opposite. A cgroup
that is far below what the process actually wants does not fail fast -- it
thrashes, reclaiming and re-faulting pages continuously, and **sustained
reclaim is exactly the signal `systemd-oomd` kills on**. So the tripwire
manufactured the pressure that then propagated up `/user.slice/user-1000.slice`
and got the desktop and the user manager killed.

The reason a userspace daemon could kill the user manager at all is a host
configuration: `ManagedOOMMemoryPressure` is enabled on `user@1000.service`
through the drop-in `10-oomd-user-service-defaults.conf`. That makes the whole
user session -- including its own manager -- a candidate for pressure kills.

## What died

- `user@1000.service` (the user manager, pid 2101). Still `failed (Result:
  signal)`. It respawns on the user's next login; nothing else brings it back.
- The GNOME session: shell, settings daemon housekeeping, keyring, update
  notifier. The user is looking at a fresh GDM greeter.
- **Every `systemd-run --user` unit**, because they were children of that
  manager:
  - `fp8-r312d-session6-20260918` -- died *before* its service-restore step, which
    is why the FP8 service is still down;
  - `r312d-build-bc-20260918` -- the variants b/c rebuild at `JOBS=1`, killed at
    build object 2 of 8;
  - `fp8-r312d-session7-20260918` -- armed and waiting, never ran;
  - the session monitors.
- The MiniMax-H3 runner (python 137924), orphaned at 03:09:59 and reaped by the
  kernel at 03:18:41.

## What is still down

- **The FP8 two-card service on port 18124.** Down since 02:43:12 UTC, not
  restored. This is the longest the service has been down on this boot and it is
  not down on purpose any more.
- **r312d variants b and c.** Neither library exists. Variant b (upstream IGC
  2.34.4 / ocloc 26.18) and variant c (b plus the sycl-tla revision `87f6850`
  that the kernel CMake pins) are built by
  `experiments/qwen38-27b-b70/docker/rebase-v0290/build-kernels-0.1.14.1-r312d-multiq-toolchain.sh`
  and both were killed.
- **lc-3 never ran** and is still gated on an exact r312c census, which it does
  not have (see the [review findings](2026-09-16-fp8-review-findings.md)).
- **The MiniMax-H3 lane** has no first-light result. It got as far as beginning
  the encoder load and nothing after.

## The port race bit us again

The service restore at 02:43 failed on `[Errno 98] Address already in use`.
`serve.py`'s port probe binds without `SO_REUSEADDR`, so a socket left in
`TIME_WAIT` by the server that was just stopped blocks the bind for up to 60
seconds. A `stopped` state file is not evidence that the port is free. This is
the same race already written up in [DO-NOT-REPEAT](../DO-NOT-REPEAT.md); the
fix is to poll `ss -ltn` for `:18124` until it is gone before starting, and it
still is not in every restore path.

## The harness lied about the build

The session script captured the build's return code through a construction that
reported `rc=0` for a run whose compilers had been `Killed`. The build was only
caught because the script separately checked for the artefact and reported
`variant b: no library`.

Any exit code captured through an intervening subshell or pipeline is the exit
code of the wrong thing. Two rules, both now in
[DO-NOT-REPEAT](../DO-NOT-REPEAT.md): capture `$?` on the very next line with no
subshell between, and **gate on the artefact, not on the exit code** -- a build
either produced the library or it did not.

## What must change before the MiniMax lane runs again

All of these are preconditions, not suggestions:

1. **Measure the runner's real host-RAM need first, on a CPU-only pass** with no
   GPU, no container beside it, and no `MemoryMax`. Record peak RSS for the
   `encode.load` phase specifically.
2. **That measured peak must sit well under free host RAM** before a GPU run is
   armed. If it does not, the loader has to change: stream the encoder tensor by
   tensor to the GPU instead of materialising it in host memory.
3. **No `MemoryMax` below the measured need.** A cgroup limit under the real
   working set is not a safety net; it is a pressure generator, and pressure is
   what `systemd-oomd` kills on. Either size the limit above the measured peak or
   use a watchdog that reads `/proc/meminfo` and kills the runner on low
   *available* memory.
4. **Never beside a compiler container.** One job at a time on this host.
5. **The FP8 service stays down** for the run, and the restore waits for the port
   to be free.

## What the user needs to decide

- **When to log in.** The user manager only comes back on login. Nothing can be
  re-queued before that.
- **The order of the re-queue afterwards**, one at a time, service down between
  them: the service restore first, then the variants b/c build. No MiniMax run
  beside a build.
- **Whether to change the host's oomd configuration.** Today
  `ManagedOOMMemoryPressure` on `user@1000.service` (drop-in
  `10-oomd-user-service-defaults.conf`) is what allowed `systemd-oomd` to kill
  the user manager and take the desktop with it. Turning it off for
  `user@1000.service` would make a future runaway job kill itself rather than the
  session -- at the cost of losing the pressure backstop. This is a host-level
  change and a user decision; the agent has not touched it.

## Evidence

`/mnt/fast-ai/bench-results/host-oom-20260917T2310/`:

- `journal-2255-2320.txt` -- the full journal window covering all of the above;
- `oomd.txt` -- the `systemd-oomd` kill records with the pressure percentages;
- `user-manager-status.txt` -- `user@1000.service` in its failed state;
- the session-6 log and the `smoke-20260918T030507Z` log (the one that stops at
  `encode.load`);
- `pressure-now.txt`, `free-now.txt` -- the host after the dust settled.

The build's own recipe log, with the `icpx ... Killed` lines, is
`/mnt/fast-ai/build/kernels-r312d-multiq-toolchain-20260918-b.log`.
