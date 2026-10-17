# A367 glue01 row-copy screen

CPU-built only. Two fresh servers, control then candidate, once each. No model,
GPU, health probe or service ran during preparation. The coordinator owns future
launches. [Launch sequence](LAUNCH-RUNBOOK.md), [preregistration](preregistration.json).

Control preserves the sealed replay server command/environment exactly. Candidate
uses a separate copy of the clean export with only patch 01 and
`Q38_M2_GLUE_ROW_COPY=1`. Patch 02/03 remain off. The same GEMM, BF16 KV, model,
placement, exact serial GDN, MTP1, CCL twoshots/4096 and graph sizes `[1,2]` remain.
The only additional candidate plumbing is the spawn-safe byte-gate entry and its
receipt directory. [Full source export manifest and one-file delta](source-export.json).
The clean export and replay/calibration/census/driver packets are immutable.

Each timed realistic suite runs first: all twelve fixed prompts once, 512-token
cap, zero cached tokens, exact full token arrays/text/stopping reasons against
A367 plus the unchanged checker. The subsequent battery retains recovery canary,
seven quality outputs (including the original code-execution miss), sixteen exact
repeats, needle, original short diagnostics and two repeats of both p2048/o128
and p4096/o128 at capacity 4352. The oracle is never regenerated on the candidate.
Speed is reported, never a pass condition. A single pair cannot establish a new
record or candidate fresh-server determinism. Unavailable device step timing and
M1/M2 counts are explicitly unavailable, never inferred from output counts.

The CPU operator gate executes the actual old/new methods against byte mocks:
144 cases, including guard fallbacks. This does not prove CCL arithmetic. The
candidate therefore runs 72 byte cases on each of four ranks during its own
warmup, using its existing communicator before any prompt: eager and captured
M1/M2 calls, changed inputs, repeat graph replay, signed zeros, cancellation,
subnormals and NaN payloads. Both rows must match as raw bytes, preserve inputs,
and return fresh output. Row shape/stride/group, 256-byte alignment and the 5120
byte second-row offset are checked. CCL settings are frozen; internal native
algorithm selection is not separately traced. Four complete passing rank receipts
are mandatory before the cold client starts and when checking results.

The lifecycle/sampler comes from census commit `7a5176c5d`, with trace code and
its exit-crash allowance excluded. The 0.5 s sampler reads host memory and queues
rows; it does no RAID I/O. Separate threads handle attribution (cmdline once),
file writes and live gates. Samples are verified and copied after exit. One API
PID SIGINT, entire-session exit and 305 s kernel watch apply on success/failure.
No hard kill, retries, automatic server restore or host-setting changes exist.
Record server profile is nice 0/all online CPUs/OMP1; CPU preparation uses
nice 19/cores 4–15,20–31. The client stays nice 0 on those coordinator cores.

The 114840824 KiB start floor and 12000000 KiB live reserve bind the exact seal and
preregistration. The coordinator records the owner's standing instruction using
the generated approval sentence; each arm still needs its own fresh window,
health and payload receipts. A fixed campaign and seal-scoped one-use claims
prevent arm retry/relabeling. Failed control blocks candidate. Budgets remain
1800 s load, 2700 s client, at most 3600 s authorization; expiry may prevent finishing
the battery and is a failure, never permission to renew automatically.

[Resolved fault](resolved-fault.json) is the sole exception: the two exact lines
at 01:09:16 UTC on boot 2cba7160, hash-bound to their original full text and the
01:09:46–01:09:51 four-card probe. The journal uses the preserved short-ISO format.
Admission requires precisely that multiset, both lines before the probe, four
passing cards and zero during-probe faults. New launch health may report two
prior lines only for this resolution. A third, duplicate, changed or later fault
refuses. Watcher baseline excludes exactly the recorded pair; any new fault
latches the run. It cannot waive current-boot FAULT.json files or another incident.
A new clean boot can use no resolution and zero faults. No device result is
claimed by this CPU packet.
