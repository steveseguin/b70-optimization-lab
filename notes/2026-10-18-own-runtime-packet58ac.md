# Packet58ac — cache publication feasibility closed on CPU

**No build brief.** Publishing only changed entries can preserve the existing
safety rules, but the measurements do not support the required 60% time saving.
The one-card record remains **29.259764 tokens per second**.

The saved run publishes 1,179,648 bytes once per measured token and spends
1.231254 ms packing, submitting and waiting for those tables. The actual
packing loop takes about 0.053–0.060 ms in CPU probes. The requested saving
is 0.738753 ms, so most of it would have to come from device work and waits
that the current receipts do not separate. Fewer bytes alone cannot prove it.

The retained design records changed expert IDs during planning, revokes their
pointers before overwriting cache slots, then publishes completed fills at a
later drained boundary. It preserves host fallbacks and every generation.
The device resolver does not check generations, making those boundaries
essential. Both host compilers pass 480 metadata transactions, including
evictions, duplicate routes, late-fill guards and generation-only changes.
These are CPU checks, not model-output qualification.

Conditional estimates, assuming 64 changed IDs and 0.020 ms of new overhead,
save 0.080–0.327 ms (+0.23–0.97%) across explicitly assumed transfer rates.
They credit no unknown scatter improvement and are not measured GPU gains.
Reopen only with current-identity evidence for enough removable device cost
to leave the complete safe boundary at or below 0.492502 ms/token.

- [Analysis, exact protocol, design and closeout](../experiments/own-xpu-runtime/stage2/packet58ac-cache-publication/ANALYSIS.md)
- [Measured counts, timings, assumptions and hashes](../experiments/own-xpu-runtime/stage2/packet58ac-cache-publication/analysis.json)
- [Saved CPU probe results](../experiments/own-xpu-runtime/stage2/packet58ac-cache-publication/host-probe.json)
- [Reproducer](../experiments/own-xpu-runtime/stage2/packet58ac-cache-publication/replay.py)
- [Do-not-repeat entry](../experiments/own-xpu-runtime/stage2/packet58ac-cache-publication/DO-NOT-REPEAT.md)

Work started from main `d7f6c2c2504a158e666a87e86d63c479beff33ae`.
`git pull --rebase` refused the pre-existing dirty tree; `git fetch origin`
confirmed HEAD equalled origin/main. Unrelated orchestration and packet edits
were preserved. Source extraction, receipt analysis and small standard-C++
probes used nice19, CPUs 8–15/24–31, stdin `/dev/null`, `python3 -B` and a 4 GiB
address-space cap. Maximum probe/compiler child RSS was 284,916 KiB.
Compiler admission was observed without changing ops. Two later probe-refresh
attempts refused an occupied compiler lock; the final replay verified the
saved probe hashes instead. No runtime build, GPU, service, sudo, settings,
model read or live queue action occurred. Existing packet trees stayed frozen.

Validation: both compiler protocol runs passed; saved-record aggregation and
publication byte accounting reproduced; 58y's raw diagnostic wait mean was
independently checked by hash. No public model package or benchmark changed.
