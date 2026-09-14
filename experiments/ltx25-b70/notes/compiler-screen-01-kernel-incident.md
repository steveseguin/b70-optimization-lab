# Host kernel lockup after the first eager control

September14: the native compiler campaign is halted by a host kernel incident.
It submitted only `compiler-screen-01-r01-eager-boat`. The server completed
the original eager graph; the client never finished postflight/oracle checks.
No compiled block was executed, no compiler candidate was created, and no
compiler numerical or speed result is established.

The server completed25 frames at256x256/24fps using the original8+3 steps.
Preview readiness was138.8018s, including model loading; client profile completion
was142.2092s. Server history records success at05:15:41.889 UTC. This initialization
timing is neither a warm speed result nor completed strict qualification. The raw
archive and preview are preserved; there is no parity receipt or permission to
prune them. The preceding encoder screen's25/25 exact results remain intact.

The first watchdog report at05:16:10 UTC says CPU13 had been stuck26 seconds in
client PID96119. Its repeated stack is `smp_call_function_many_cond`, through
cross-CPU TLB flush and `brk`/memory unmapping. Rsyslog CPU6 subsequently reports
the same synchronization wait through `mprotect`. RCU stalls and blocked systemd
and fstrim tasks follow. These identify observed wait paths and host-wide impact;
they do not establish the underlying cause or implicate compilation, GPU reset,
OOM, storage, or power settings. The excerpt has no explicit GPU reset/AER/OOM.

Root created the shared `FAULT.json` latch after reading these reports, blocking
further harness/node requests, and sent one SIGINT to the owned client. The client
remained in its kernel wait with exit unconfirmed. PID95931 remained present;
its endpoint reported an empty queue. No automatic reboot, driver reset,
application restart, power change, swap toggle or page-cache change followed the
incident. The original application's earlier single reload was to load the
prepared compiler code, before this fault.

The client progress file still says `running` because its kernel-stuck process
cannot finalize the file. **The fault latch and this incident record override
that stale progress. Do not submit another GPU request.** An independent known-file
audit confirmed that graph422 used `mode=eager`, `candidate_id=null`,
`qualified_stage_count=0`, and the compiler receipt directory has no call files.

The launcher watchdog's existing pattern covers GPU faults but missed explicit
host soft-lockup/RCU/hung-task reports. A separate
[additive detection patch](../patches/encoder-kernel-host-fault-detector.patch)
now passes [eight CPU tests](../data/kernel-fault-detector-cpu-01.json), including
replay of the actual incident and rejection of generic words. It was applied
only to a temporary launcher copy; the live packet is unchanged. A future
sealed runtime must include and revalidate it. It is not a fix for the kernel
fault. Avoid broad `ps`/`pgrep` or
`/proc/*/cmdline` scans during this incident: three read-only diagnostics blocked
in `__access_remote_vm` while inspecting the affected process. Prefer bounded
known files and kernel logs. Leave the fault latch intact until recovery and
health are established under the user's operating constraints.

Evidence: [incident summary](../data/compiler-screen-01-kernel-incident/summary.json),
[checksum inventory](../data/compiler-screen-01-kernel-incident/inventory.json),
[original log/receipt archive](../data/compiler-screen-01-kernel-incident/evidence.json.gz).
The gzip JSON archive preserves22 original text files and passed SHA256 roundtrip
verification. Full evidence remains under
`/mnt/fast-ai/bench-results/ltx25-baseline-20260913`.

Repository checks for the implementation passed document/manifest links and
whitespace checks. Global literal-pin audit reported87 matching/231 drifted pins
with no absent targets, including unrelated historical Qwen helper pins; those
were left unchanged. The compiler packet's own1,227-file inventory, copied
launcher check,14 CPU facade checks and10 receipt checks passed before launch.
Those preparation results do not waive this incident or qualify the native gate.
