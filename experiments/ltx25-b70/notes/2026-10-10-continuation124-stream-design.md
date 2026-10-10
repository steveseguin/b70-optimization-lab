# Packet 124: free the cone worker before the previous chunk finishes

The 169-frame run was exact but slower per second of video than 145. The
[saved timeline](2026-10-10-continuation123b-results-169.md) shows the actual cone
cost rose only about 0.12 seconds. Most of its extra on-chain time was a 0.59-second
wait for the previous chunk's audio, hashing and record publication. Display had
already finished before the next cone was queued. Moving display alone would
leave the single software worker occupied.

Packet 124 therefore selects the smallest placement that the measured memory
allows: legacy auxiliaries and the existing display decoder replica on xpu:2,
with an optional separate completion worker. In that path, audio runs earlier,
after B preparation while the next sampler is active; then display and its CPU
tail transfer to a bounded FIFO. The cone worker is available for the next chunk.
Without early audio, its xpu:3 lock would retain about 0.43 seconds of the old
wait, leaving only about 0.19 seconds to recover.

Parent is packet 123b, manifest
`5bdc0956f69259a99ca82849280e73b8bd2a80e28ff421ce5d61122e8a74d433`.
Sources, gates and future command syntax are in
[CONTRACT.md](../recovery/20261010-continuation124-stream/CONTRACT.md) and
[LAUNCH.md](../recovery/20261010-continuation124-stream/LAUNCH.md).
This task performs CPU analysis/build only; the coordinator owns all live work.

## Alternatives, memory and time

Margins are GiB above unchanged xpu:0/1/2/3 floors of 8/8/2/9; at least 0.75 is
required. These are measured-envelope projections, not measurements of packet124.
169 aux-run sampled margins are 2.268/1.798/8.104/2.149. Static owners are 0.927351
GiB upsampler and 0.339622 GiB audio. No removed workspace is credited.

| 169 alternative | Margins 0 / 1 / 2 / 3 | Period forecast, seconds | s/s | Decision |
|---|---|---:|---:|---|
| (a) Auxiliaries on 1, display replica on 2 | 2.268 / **0.531** / 2.210 / 2.149 before aux workspace; card1 **−1.469** after 2 GiB allowance | 6.20–6.75 if memory could fit; no runnable speed forecast | 0.886–0.964, hypothetical only | Refused before launch; static margin already fails |
| (b) Legacy auxiliaries, display replica on 2, serial worker | 1.340 / 1.798 / 2.210 / 1.809 | 6.65–7.15 | 0.950–1.021 | Useful placement control; no reliable win predicted |
| **(b) Same placement, early audio and parallel completion** | **1.340 / 1.798 / 2.210 / 1.809** | **6.20–6.65**, central 6.30 | **0.886–0.950**, central 0.900 | Selected candidate; native gates pending |
| (c) Auxiliaries on 2, exact two-part display on 3 | 2.268 / 1.798 / 6.104 / 2.149 before any new retained split state | No defensible range without an exact split/workspace census | Not established | No exact native split built |
| (c) Defer full display until next cone finishes | Same sampled envelope as above; overlap may add storage | ~6.20–6.85 chain forecast, but ~10–11 s anchor-to-display completion | 0.886–0.979 chain only | Fails display-within-seven-second-period requirement |

The selected arm's adverse scheduling range is 6.65–7.20 s (0.950–1.029 s/s).
Full barriers remain; text uses xpu:2 and may contend with the replica. Moving a
weight owner need not recover its entire allocator reservation. Per-phase native
free samples and every replica admission decide whether the forecast holds.
To beat the coordinator's 145 result, 169 must be below 6.685 s; to beat the older
0.939 s/s result it must be below 6.573 s. A single lucky session is insufficient.

At 145 the selected placement forecasts 5.50–6.10 s per six seconds of new video
(0.917–1.017 s/s). Margins are 1.270 / 1.828 / 3.070 / 1.850 GiB, using the actual
legacy reference and the replica reserve. Little FIFO time exists there to save;
145 is the same-length identity and memory qualification before increasing length.

The xpu:2 replica base is its measured repeated before-decode free minimum
10.710304 GiB, already including replica weights. Subtract 2 GiB floor and
5.640625/6.5 GiB reserve to get 3.069679/2.210304 at 145/169. The measured 121
peak-or-reservation growth was 2.982422 GiB; its linear/quadratic 169 scenarios
are 4.100830–5.638641 GiB. The 6.5 GiB reserve leaves 0.861359 above the larger
scenario. This is the existing 169 default; an explicit environment value is
recommended for clarity, not required to increase it. It cannot certify an
isolated 169 decoder peak. Retained reservation can refuse a later call; no cache
flush or smaller allowance is an acceptable workaround.

Moving both auxiliaries to 1 is also inadmissible at 145: 1.848−1.267=0.581 GiB
before workspace. Splitting the display by slicing input frames is not exact:
causal context, diffusion/attention shapes and rounding can change. An exact
native continuation point needs its own activation census and gates. Deferring
display adds about 5.2–5.8 seconds to sink latency. A deep sink buffer cannot
satisfy the requested completion-within-period constraint by hiding that delay.

## Critical path and sink budget

Measured 169 display runs successor-submit+0.71→4.70 s; next cone queues around
+4.74, but audio and CPU finalization keep its worker busy until +5.32. Early
audio moves approximately 0.43 s to +0.71→1.14, then the replica runs about
+1.14→5.12 on xpu:2. The next cone can start on xpu:3 at approximately +4.74.
The design does not assume a faster video decoder. At the proposed cadence,
one display FIFO consumes less than one chunk period and cannot build a stable
backlog, conditional on measured sink and contention checks.

Previous-anchor→display completion is approximately 1.06 s preparation/go +
0.15 s B preparation + 0.43 s audio + 3.98 s display = 5.62 s. Hashes/record plus
about 0.8 s MP4 publication give roughly 6.55 s to the sink, under seven seconds.
145 is about 5.1 s to the sink against six seconds. These are planning estimates;
require actual per-chunk sink latency and no FIFO growth. No deadline or safety
bound is loosened. The inherited three-second GO bound limits waiting for the
successor, not display execution.

The 5.62 s display estimate is below even the 6.20 s projected production period.
The 6.55 s complete-preview estimate is below seven seconds of video, but can
exceed the central 6.30 s production period. These are different checks: this
design does not claim that a complete MP4 reaches the sink within 6.30 s. If that
stricter sink deadline is required, it remains open and must pass measured timing.

## Gates and CPU work

Default `LTX_DISPLAY_WORKER=serial` preserves 123b worker order. Parallel is
launch-only and tightly scoped; there is no automatic fallback. Original model,
BF16 decoder precision, latent geometry, sampler kernels, target weights, seed,
full snapshots, run-owned storage budget and atomic preview publication remain.

Require copied replica weights bitwise equal; all nine qualification images
against the uncached original xpu:3 decoder; exact three-chain latent/image/audio/
anchor identity, including the parallel repeat chain; and a cross-card last-frame
cone/display byte check on every live chunk. Waveform equality specifically gates
the early audio reorder. Failures latch both queues and stop further admission.
The private early waveform is ~2.57 MiB on CPU at 169, not another GPU workspace.

Clients now expect worker selection and use the inner plan identity. A regression
iterates every existing `PACKETS[...]` plan pin against the sealed plan envelope,
preventing the 123/123b file-hash mistake. The historical fake123 server fixture
was corrected to report the inner value too; no historical live pin was changed.
CPU tests cover bounded transfer, both-worker failure, drains, original events,
no retry, admission, truthful timing and real Runtime execution through fake
Comfy/model owners. They cannot prove native memory, speed or full-model quality.

Final seal, recursive source verification, exact complete-suite counts and logs
are in [continuation124-build.json](../data/resume-20261008/continuation124-build.json).
Full CPU discovery caught an erroneous duplicated scope check in the saved-receipt
reader. It was removed, and a direct serial/parallel reader regression was added.
The first, never-launched build (`91c1d303…`) is preserved under a rejected-build
name; its seal is superseded by `897442d0…`. Original failure logs and corrected
module rechecks remain in the receipt's evidence, following the 123b precedent.
No GPU work, server, launcher, check-only, port8188 operation, systemd operation,
process signal, device open, existing-run/client-tree write or host setting change
is performed for this packet. Unrelated pre-existing untracked files are retained.
