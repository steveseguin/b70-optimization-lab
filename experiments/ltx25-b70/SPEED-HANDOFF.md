# LTX exact-output latency campaign

Forward plan: [north star and staged execution](PLAN.md). Historical stages below
record the completed residency campaign; use the plan for upcoming priorities.

Current September14: packet06 PID39793 is idle on restored dispatch after
32 exact full clips, including all48 compiled blocks. All three selections are
retained. All48 warm previews took about 7.8 seconds and lost a median 1.303
seconds against adjacent restored controls; no speed promotion. Queue and
kernel postflight are clean, with no FAULT latch. See [native screen results](notes/multiblock-screen-01-results.md).
The inactive [adjacent-state reuse03 candidate](notes/adjacent-state-reuse-03-cpu.md)
passed all 60 CPU checks in both parent and candidate. Native GPU quality and
speed remain pending; immutable runtime and bounded client preparation proceed.
CURRENT.md remains authoritative; historical process statements below are superseded.

Historical September14: [kernel incident](notes/compiler-screen-01-kernel-incident.md)
halted the first eager control of the subsequent compiler campaign after graph
completion, before oracle postflight. No compiled execution occurred. The shared
fault latch overrides stale running progress; no new GPU requests. Preserve
PID95931/current evidence and follow CURRENT for recovery state.

September14 update: [encoder screen02](notes/encoder-screen-02-results.md) passed
all25 native GPU clips with strict original-reference equality and all unload
gates. Candidate medians6.38–6.44s show no convincing gain against bracketing
controls6.36/6.64s. Small-state residency fixes the observed accounting drift.
PID78769 remains idle on control after the completed campaign. Compiler runtime
integration is next. This supersedes the historical inactive-packet and pending
maintenance statements below; ordinary necessary application reloads no longer
cause approval pauses. The computer was not rebooted.

The user subsequently made **one second of video in under one second** the actual
goal, with24fps and a256x256 minimum final output. The [first30-request campaign](notes/stability-01-results.md)
passed all10 fixture repeats at6.515s median preview and bounded review storage.
Accounting/transfer candidates are prepared but inactive; the target is not yet met.

Follow-up: [nonblocking stack profile](notes/stack-profile-01-results.md) selects
an [opt-in small-state residency candidate](notes/encoder-small-state-audit.md).
It incorporates the accounting fix under its own option; do not stack both
patches. [Actual LTX block CPU compilation](notes/ltx-block-compile-cpu.md)
also passed exactness with rounding-preservation options. Both need runtime
integration and XPU qualification before a speed claim; preserve PID24848.

Encoder follow-up: [inactive source packet](notes/encoder-runtime-packet.md)
now includes explicit control/crop/small_state/combined variants and the required
clone-policy guard. Seventeen CPU lifecycle tests and four real-loader integration
tests pass; startup/client integration and GPU qualification remain pending.

V2 follow-up: [startup/client integration is complete](notes/encoder-runtime-v2-ready.md),
with 26 additional CPU checks and the copied launcher's read-only check passing.
The source packet remains inactive; a maintenance decision precedes the bounded
GPU comparison. PID24848 and all original reference evidence remain preserved.

Compiler follow-up: the [routed CPU gate](notes/ltx-block-compile-route-cpu.md)
passed, followed by 51 ownership/guard checks with the compiler callback in the
options registry. Both stage shapes and seeds remain exact. The
[native header census](notes/native-block-header-census.md) records full block
sizes and stored dtypes. Native-weight XPU correctness and speed remain
unmeasured; none of this work changes the pending encoder v2 packet.

The [executing-patcher lifecycle follow-up](notes/ltx-block-compile-pre-run-lifecycle.md)
passed 25 CPU checks, closing the recorded owner/late-registry gaps before
compiled dispatch. This gate uses a dispatch spy; lifecycle-metadata compiler
capture and GPU overhead/correctness are still unqualified. The separate
[continuation source audit](notes/continuation-source-boundary.md) identifies
the upsampler's dropped anchor mask and audio-timing work required for streaming.

A subsequent [real bound CPU capture](notes/ltx-bound-lifecycle-capture-cpu.md)
passed one case with the new lifecycle metadata: exact eager/repeated outputs,
one compiled graph and no graph breaks. Native GPU qualification remains
pending. The encoder launcher's read-only check passed again; the next measured
GPU comparison is waiting on the previously requested maintenance decision.

User authorized speed optimization on September 13, 2026, while maintaining
lossless quality. Target is first usable clip ideally immediately, otherwise
within a few seconds. Preserve the native BF16, seed, resolution, frame count,
8+3 schedule and all four raw output tensors. Real-time throughput and time to
first usable clip are separate metrics. Warm first-clip latency is now measured;
continuous real-time throughput has not been achieved.

## Validated result, September 13, 2026, 22:23 EDT

**Selected experimental graph: [resident split](data/speed-resident-split-api.json).**
It uses all four 32 GiB B70s: existing transformer blocks on XPU0/XPU1 (21/27),
text encoder on XPU2, video/audio VAEs on XPU3. Both transformer partitions are
fully resident; the text encoder still partially offloads about 458–600 MB.
Only model components are retained across requests. Text encoding, every sampler
step, decoding and tensor capture execute again on each request.

| Placement / run | Preview ready | Client completion | Exact four-output parity |
| --- | ---: | ---: | --- |
| Single, initial | 59.267 s | 59.564 s | Pass |
| Single, warm | 45.344 s | 46.757 s | Pass |
| Encoder/VAEs separated, initial | 117.738 s | 120.546 s | Pass |
| Encoder/VAEs separated, warm | 31.502 s | 31.808 s | Pass |
| Transformer split, initial | 81.206 s | 82.505 s | Pass |
| Split, boat repeat 1 | 7.102 s | 7.317 s | Pass |
| Split, boat repeat 2 | 6.441 s | 6.752 s | Pass |
| Split, marble seed17 | 6.487 s | 6.795 s | Pass |
| Split, bird seed123 | 6.457 s | 6.678 s | Pass |
| Split with BasicGuider, boat screen | 6.443 s | 6.665 s | Pass; neutral |

Preview readiness is the client-received SaveVideo completion event; client
completion additionally waits for server history. Raw lossless tensors were
ready in 6.307–6.954 s for the four warm selected-graph requests. First placement
runs include construction, loading and first-use costs and are not warm latency.
Original warm boat client times were 55.431/55.021 s; comparing their median to
the two warm split boat client times gives **7.85×**. The original single-card
server times of 54.009/52.774 s use a different timer from preview readiness.

All three split boat executions match each other and the frozen original run.
Marble and bird also match their independent original-graph references. All
four outputs have zero unequal values and maximum difference zero. Strict
determinism is enabled, warning-only mode is off, and no cached execution nodes
were reported. This establishes these three fixtures across the original and
optimized processes, plus same-process repeats; independent cold restarts of
the optimized setup were not tested. Construction receipts saying numerical
validation was pending are superseded by the linked passing comparisons.

The speedup addresses CPU weight transfers: the separate placement retained
14,390.68 MiB of transformer weights off GPU. Its first Euler iteration alone
took 13.41 s; the exact contribution of transfers, cold allocations or mapped
pages was not instrumented. The split removes transformer weight offload and
reduces warm sampler loops to about 2.47 + 0.92 s. In split boat repeat2, node
wall times were text encoding 1.852 s, samplers 2.571 + 1.012 s, audio/video
decode 0.188 + 0.608 s. Do not attribute the earlier first-iteration stall to
conditioning preparation: that executes before the measured sampling loop.

BasicGuider skips unused negative conditioning at CFG1. Its one warm screen
was exact but preview latency was neutral versus the preceding boat control;
retain it as an experiment, not a demonstrated improvement. No further material
graph-only exact optimization was identified in the independent source audit.

The 25-frame clip lasts 1.042 s, so 6.4–7.1 s warm generation is still slower
than continuous real time. Endlessly sustained operation and memory stability
have not been qualified. There is no claim of a theoretical speed maximum.
The selected recipe preserves original BF16 precision, dimensions, frames,
noise seeds and all 8+3 steps, with no approximate denoising cache. FFV1 float
RGB32/PCM float32 export of split boat repeat2 passed independent exact decoding;
that separate export is outside the request timer. MP4 remains a lossy preview.

Evidence: [structured summary](data/speed-resident/summary.json),
[three-run verification](data/speed-resident/split-repeat-verification.json),
[marble parity](data/speed-resident/resident-split-marble/parity.json),
[bird parity](data/speed-resident/resident-split-bird/parity.json),
[lossless export](data/speed-resident/float-lossless.verification.json),
[runtime log](data/speed-resident/server-speed-through-basic.log),
[post-run state](data/speed-resident/postrun-state.json).
Each run directory retains submitted graph, history, identity, capture summary,
profile and parity receipt. Raw tensors and media remain outside Git in the
original evidence root. The server is idle at PID24848, port8188, with split
components retained. No fault/OOM/restart chain or power/memory-setting change
occurred during this campaign.

## Measurement and gate

`scripts/profile-clip.py` uses the existing WebSocket node events and records
node-start intervals, submitted graph, history, PID/boot/source/model identity.
These intervals are approximate wall times, not synchronized kernel timings.
The original cache-none server is used for controls. `scripts/compare-clip.py`
independently rehashes all four archives, checks strict deterministic flags,
finite values, sample rate, unique actual executions and history binding, then
requires every output byte to match. Intentional graph deltas are reviewed and
retained separately. No approximate cache or precision reduction is allowed.

## Initial findings

- `speed-control-01`: 58.283 s client wall; exact against original baseline.
  Transformer construction 12.155 s, encoder construction 5.620 s, negative
  encoding including device load 7.613 s, positive encoding 3.090 s. Sampler
  nodes including preparation/transfers totaled 21.052 s.
- `speed-lean-01`: 59.893 s; all four outputs exact, no demonstrated speed win.
  Removes unused CFG1 negative encoding and 25 PNG preview writes, while
  retaining raw tensors and MP4. First sampler time increased in this trial.
- Capturing native reference scenes `speed-oracle-marble` (seed17) and
  `speed-oracle-bird` (seed123) before changing startup behavior. Boat seed42
  remains the primary repeated timing fixture.

## Next bounded stages

1. Retain only the five loaded model components across separate requests;
   recompute text encoding, sampling and decoding every time. Measure first
   initialization separately from resident operation.
2. Place text encoder on XPU2 and VAEs on XPU3 using stock constructors.
   Leave the transformer on XPU0 with its normal offload for a placement screen.
3. Split the exact existing transformer block objects across XPU0/XPU1 through
   normal ModelPatcher ownership and LTX block replacement hooks. Existing
   numerical block implementation remains unchanged; only ownership and
   transfers change. Require CPU ownership/routing tests before any GPU trial.
4. Promote only candidates matching boat/marble/bird references and repeated
   boat outputs, with measured end-to-end and first-output times. Preserve
   mismatches, timing losses, startup cost and all unsupported assumptions.

## Server constraint

The running baseline server (PID11499) cannot load a new extension or change
cache strategy through a supported live API. Its `--cache-none` disables both
loader and result caches. After completing the reference captures and reviewing
the extension, one planned graceful process migration is needed to install the
resident loader and device-routing experiments. All subsequent variants will
use that one new process. No server retry/restart policy, power changes, swap
changes, page-cache drops, driver reset or reboot is permitted. Any device fault
halts new requests. Existing baseline evidence remains unchanged.

New startup path: `scripts/serve-speed.py`; run identity and startup evidence
will be written under the original evidence root's `speed-server/` directory.
The original `scripts/serve.py` and baseline receipts remain frozen. The capture
gate and fault latch remain shared with the original evidence root.

Migration completed cleanly: PID11499 exited with code0; the new PID24848 owns
port8188 and passed all four small startup checks. No GPU fault occurred.
`planned-server-migration.json` records the single transition. Both extension
ownership/routing tests (six) and resident-loader retention/gate tests passed
on CPU before startup. Extension and launcher hashes are bound into the new
server identity. Further experiments use PID24848 without restarting it.
