# Packet 124 CPU contract

Parent is sealed 123b, manifest
`5bdc0956f69259a99ca82849280e73b8bd2a80e28ff421ce5d61122e8a74d433`.
This is an inactive experiment packet, not a GPU-qualified speed or quality claim.
No launch, check-only, live endpoint, unit or device operation is part of the build.

## Selected change

Keep sampler 20/28 on xpu:0/1, text on xpu:2/3, upsampler on xpu:0,
audio and the original video VAE on xpu:3. Select the inherited decoder-only
BF16 display replica on xpu:2. Admit this placement at 169 using the new measured
phase envelope. The legacy 169 display-on-3 arm remains refused. The inherited
auxiliary-xpu2/display3 arm remains available with the worker off.

`LTX_DISPLAY_WORKER=serial|parallel` defaults to `serial`.
Parallel is restricted to 145/169, two-way20-28, frame/cone, dg0,
legacy auxiliaries and eager display on xpu:2. No arithmetic or weight changes,
new graphs, precision changes, partial display, dropped frames or fallback.

The serial form uses the parent's ordered decode worker. The parallel form has
one anchor FIFO and one display/completion FIFO, each with two waiting slots,
bounded blocking submission and one shared failure latch. The original job,
anchor stage and done event are retained. Only final completion publishes the
record/result and releases done. Pending, drain and wait-for include both stages.
A stalled queue faults after the inherited bound; it never retries or kills.

Eager and graph qualification controls drain and execute inline. Repeat and live
chunks execute the new path: cone -> anchor publication -> commit/A preparation
-> successor-A wait -> B preparation -> early native audio -> bounded transfer
-> display replica -> cone/display byte comparison -> hashes/capture/record ->
preview. Early audio runs while the successor sampler is active; it no longer
holds the cone worker at the end of display. Its approximately 2.57 MiB waveform
at 169 remains on CPU. Audio, cone, native reference decode and encoder work
share the existing encoder lock in this mode. Replica arithmetic on xpu:2 has
its own decoder instance. Native video noise uses a fresh per-device generator
seeded zero. Audio decode introduces no random sampling.
The inherited replica receipt's `single_decode_thread=true` means replica calls
remain serialized. Qualification and live calls can use different worker threads;
the qualification drain prevents concurrent calls on the replica.

Every four-card snapshot, residency/ownership check, fault gate, source pin,
no-eviction rule and storage guard remains. New 145/169 replica admission retains
0.75 GiB above the unchanged floors, including before/after each replica decode.
Parallel receipt snapshots and 169 legacy-replica snapshots must also meet that
margin. There is no host setting change or cache clearing to make an arm fit.

## Identity and evidence

All 220 numerical identities and all 3,960 qualification graphs remain equal to
123b after normalizing packet namespace and clip IDs. New prefix is `stream124-`;
clip bases are 12400000/12401000. Worker selection is a bound server option in
status, receipts, decodes, previews and the qualification verdict, not a request
field. Nondefault run names end in `-dwparallel`.

Qualification requires three-chain identity of video/audio/stage-A latents,
images, waveform and anchors. The repeat chain exercises early audio and the
parallel worker. All nine qualification images compare against the original
uncached xpu:3 decode; copied replica weights must be bitwise equal. At every
live chunk the xpu:2 display last frame must equal the xpu:3 cone bytes. That
last-frame check supplements, and does not replace, the full-image gate.
145 also retains the sealed same-length output reference. Native 169 legacy
placement, concurrency and full-model identity remain to be qualified.

Decode evidence records configured and actual completion workers, handoff/start
and actual early-audio timestamps. `audio_done` is the real audio completion;
`decode_done` is the later of audio and video completion. Hash timing starts at
`decode_done`. Serial timestamp equalities stay unchanged. The verifier refuses
parallel repeat evidence that actually completed inline or has forged ordering.

The 169 replica reserve is 6.5 GiB, already the inherited default. The explicit
`LTX_DISPLAY_REPLICA_TRANSIENT_GIB=6.5` documents it; it does not lower a reserve.
145 keeps 5.640625 GiB. Per-call physical-free and cumulative peak/reservation
growth checks remain; cumulative peaks are not called isolated phase peaks.

Clients pin the inner `plan_sha256` from the sealed plan envelope, not the plan
file hash. A CPU regression checks every `PACKETS` entry with a plan pin against
its sealed plan. Historical fake123 now reports that same inner value.

## Build and validation boundary

Use `/home/steve/.venvs/ltx25-baseline/bin/python -B`, with OMP/MKL threads capped
at four. `run_tests_124.py` guards device opens, live sockets and process signals
before imports and guarded children. Client suites use cooperative fake children
and non-8188 loopback test ports. CPU fakes establish control flow and failure
handling, never GPU performance or full-model output equality.

The builder recursively verifies the parent, freezes the author inventory,
checks disk admission, creates the destination exclusively and preserves every
changed parent byte under `provenance/packet123b/`. Recursive verification checks
all files, source closure, manifest semantics, and absence of Python caches.
Final counts and identities belong to the build receipt. Existing run trees,
parent packets and `/home/steve/ltx-stream` remain read-only throughout this task.
