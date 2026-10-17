# October 17: lane-aware admission for future full chains

The next chain can reserve cards 0+1 for its exactness windows while a masked
screen uses cards 2+3. WS128, WSs and W2m still reserve the whole host. They
write a hold before waiting for the current B screen to finish, then keep B
off until their owners exit and postflight passes. These are prepared changes,
not a device result or a new speed claim.

The reusable code and both seal-time patches are in
[`stage2/chain_admission`](../experiments/own-xpu-runtime/stage2/chain_admission/README.md).
The companion patch is for a new B screen wrapper: the old v3 admission would
otherwise refuse A's shared drain permit. It allows B to compute under a
verified live A exactness reservation while preserving serialized drains and
their 60-second gap. Because fixtures exit on their own, the permit covers
the whole chain window. B may wait to drain, and its existing watchdog still
applies.

The protocol uses a common `hold-lane-B` file, one short lock for admissions,
and a lease for each lane. Flag checks and lease acquisition happen under the
same lock, so a new B screen cannot slip into a timing window. Boot IDs,
process start ticks and unique tokens bind the files to their owners. A failed
or interrupted attempt leaves its markers for coordinator recovery; there is
no automatic deletion, restart or kill.

Every chain native process gets the fixed card mask after its closed
environment check and a fresh driver home. Passive fdinfo checks verify its
actual devices. Model ranks must prove their mapped cards before the first
request. Admission evidence is hash-bound to the original window receipt and
its launched PIDs; both the queue and later prerequisites check it. Timing
numbers from concurrently admitted exactness windows stay diagnostic.

The CPU checks cover the timing policy, card masks and topology, idle and
unknown clients, PID reuse, short unproven owners, B starting during A,
timing waits, crashes, stale holds, cleanup races, shared drain spacing,
receipt tampering and both patch recipes. All 55 tests passed. They ran with
`nice -n 19`, `taskset -c 8-15,24-31` and `python3 -B`, using only temporary
mock devices and CPU processes. [Retained validation](../experiments/own-xpu-runtime/stage2/chain_admission/evidence/cpu-validation.json).

This task made no edit to packet61x, its running unit or its output. Existing
sealed packets and screen v3 were read only. The first `git pull --rebase`
refused an unrelated dirty file; a fetch showed the starting `main` already
matched the remote. That edit was preserved. Reference source bytes are
pinned to the starting commit, so concurrent coordinator edits cannot change
the patch fixture underneath the tests. A later pull completed once the shared
tracked tree was clean.

Next, the coordinator can adopt both patches in fresh wrappers before their
first seals, verify source closure and planned overlap duration, and run the
device windows. Native masking, full-chain quality and actual overlap still
need that device evidence. No GPU, sudo, service, power, memory, swap,
page-cache or reboot operation ran during this preparation.
