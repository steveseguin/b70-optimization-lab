# Packet58ab: port the three-stage target HC to the one-card record

CPU preparation started October 18 at 21:50 UTC. Work is bounded to three
hours; the first smoke proposal is due within 90 minutes. No device, service,
live queue or host setting is changed. Existing packets remain frozen.

The source anchor is packet58z's retained 58x source closure, whose archive
SHA256 is `efd357edc751e929553880b2638cada3fedb869d2f8584c51ce9bc2646d3ab9f`.
The current one-card receipt is 29.259764156562692 tok/s, record
`cmvebtu5f009frf01gsnfi2eh`. It is not a new measurement by this work.

Only packet60's target-HC dispatch and three-stage arithmetic are ported.
Final HC and draft are excluded. Tile16, all 48 layers, 21,552,729,600 cache
bytes, overlap, cache policy, BF16 KV, token cap and the packet49
`iq3-p49-split32-v1` oracle remain fixed. The switch is `hc=production|p60fusion`
at a drained boundary within one model load. A0 remains exact and reported,
but is excluded from drift and speed comparison under the packet58wb rule.

The expected 0.8–1.05 ms/token saving is a planning hypothesis from packet147,
not a measurement. A 50% transfer would fail the 2% gate. CPU checks cannot
establish full-model device equality or a speed result.

Initial pull refused unrelated dirty orchestration files; fetch confirmed
HEAD=origin/main at `d7f6c2c2504a158e666a87e86d63c479beff33ae`. Root had
30.73 GB free. CPU work uses nice19, cores 8–15/24–31, python3 -B and closed
stdin; compiler turns use the shared ops gate. No model payload is read.

Milestone 1: private source closure and HC dispatch are implemented; builds
and proofs are in progress. READY is deliberately absent until final checks.
That source milestone was committed and pushed as `9cc135c73`.

The one-load port needed an explicit plan rebuild at the quiescent boundary:
the production plan absorbs some next-layer HC norms into the preceding
combine. Merely changing dispatch would omit those fusion norms. The control
keeps its original plan; fusion reconstructs the ordinary norm sites and all
plan-pointer indexes before capture. Full-size mocks enforce all 96 HC sides,
288 fusion commands and 48 ordinary layer hooks at both context extents.

The arithmetic fixture passes GNU and Intel, including NaN, infinity, signed
zero, nonfinite weights, inactive/out-of-range controls and sticky errors.
Each compiler repeats exactly, and their complete byte transcripts agree.
The real capture fixture also proves request reset and refusal to erase
sticky/poisoned state. The first fixture teardown exposed a CPU harness bug
(releasing a pinned staging allocation through the device-only accounting
helper); the harness now releases it through its owning arena. No GPU ran.
An inherited tiny DRM-parser test initially invoked its compiler directly;
it now takes the required shared compiler turn.

Both proposals were written within the 90-minute bound and remain unqueued.
The six real entry paths, full-size allocation/submit checks and the unchanged
production-versus-record miniature pass. Native loader checks use the exact
vendored `ops/launch_env.py` library path.

A required tool gate remains blocked: the frozen `ops/rehearse_entry.py
--report` only accepts two-card `screen.main` entries. Both actual one-card
proposals pass loader/parser checks but fail that report-routing prerequisite.
Its failure receipts are preserved. The packet's own real smoke/bracket
summary passes separately, including a changed last-token refusal; this is
not reported as a shared-tool pass. Existing ops remain frozen. The final
READY marker will be written last with `ready_for_device=false`, current
implementation commit and proposal hashes. No device work or queue launch
is authorized by that marker.

Final CPU checks: 111 policy tests; eight HC byte-proof runs across GNU and
Intel; all six real queue entry paths; full-size sparse submit/allocation
checks; two repeated one-load reset brackets; the unchanged production versus
record miniature; and both one-card report summaries. Evidence is retained
under [the packet](../experiments/own-xpu-runtime/stage2/packet58ab-onecard-hcfusion/README.md).
The retained build is about 109 MB, below the 300 MB limit. Peak HC compiler
and fixture RSS is below 0.8 GB. The temporary plans retain a 7,200-second
watchdog against expected 600–900-second smoke and 1,200–1,800-second bracket.
The first smoke proposal was written during the initial CPU proof work,
well inside 90 minutes. This preparation makes no device speed claim.

The first final pin plan refused preserved parent-object symlinks when their
receipt keys named the local links. Receipt generation now pins their resolved,
immutable ELF targets while preserving the links themselves. The failed plan
is retained as `evidence/queue-plan-smoke-before-pin-fix.log`; the corrected
plan must pass the unchanged shared guard.

At 22:20 UTC both corrected temporary lane-A plans passed the unchanged pin
guard and packet plan. Root had 29.47 GB free; the combined 2.68 GB planned
write allowance leaves more than 25 GB. CPU preparation took about 30 minutes.
All source, proof and proposal edits precede the final readiness write. The
shared report-layout failure is the sole unresolved preparation gate.
