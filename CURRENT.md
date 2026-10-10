# Current Workspace State


**2026-10-10, packet 134 census: only the 169-frame graph-off arm clears the full memory screen; CPU validation is running.**
The 145-frame receipt audit confirms exact outputs on31/31 chunks and measured
cone graph growth3.545 GiB, below the old4.506 GiB estimate. The1.36 GB minimum
snapshot margin was on card0. At169, charging both full reserves leaves the
cone-graph/display3 arm short1.843 GiB on card3; the display replica arm is
short5.122 GiB on card2 after split36. The graph-off/native-display3 arm clears,
including0.905 GiB on card3 under the stronger all-phase screen. It is prepared
for qualification, with expected6.5–6.95 s per7 s of video; this is slower per
video-second than the current145 line. No live work changed. Full CPU suites
are in progress; the separate packet135 storage repair remains independent.
[Measured145 budget and169 census](experiments/ltx25-b70/notes/2026-10-10-continuation133b-results-145.md).

**2026-10-10 14:55 UTC, 133b session 1 halted by the storage accounting guard after 73 chunks ("Run storage refuses multiply linked files", `run_storage.py:124`); no fault; 133b relaunching (`s133b-live02`); Codex on packet 135 (guard robustness + offending-path evidence).**
Session 1 figures: median 5.21 s per 6.0 s (0.869 s/s), cone 0.74–0.75 s under the graph, 31/31 byte-identical to 129, exact. The own-writes
scan (123b/126) refuses any regular file with nlink > 1; no packet code calls os.link; 126–129 ran 600-chunk sessions on the same scan, so the
new linked file is specific to 133b's files (capture receipts, text oracle) or transient. One controlled stop; relaunch of the same arm.
Codex 134 (169 census under split36) is also running.

**2026-10-10 14:48 UTC, new best line: 133b at 145 (text layers 36–47 on xpu:2, cone decoder graph, display xpu:3, idle maintenance, GC 60, digest cache): early median 5.213 s per 6.0 s = 0.869 s/s (n = 23), byte-identical to 129 on 31/31 chunks, cone exact, even 5.17 / odd 5.25.**
Qualification verdict 94cd0653ca49 (exact replay c0/c1/c2; first cone capture admitted at Q06 in 21 s; floors held through the repeat chain).
Against the 129 production session 4 (5.522 median, n = 205) the cone graph saves ≈ 0.3 s per chunk (cone 0.74 vs 0.93) and the 2-cycle is
nearly gone. Minimum snapshot margin 1.36 GB, dual snapshots periodic. Results note at ≥ 100 periods. Next (Codex, packet 134): re-census 169
frames under split36 (xpu:3 now has the text shard's 5 GiB back) with the cone graph and display on xpu:3; and whether the 0.75 GiB screening
band leaves room at 169.

**2026-10-10 14:32 UTC, packet 133b sealed (helper and text oracle bundled under `launch/`; six sealed-import tests added); launching 133b at 145 with split36 + cone graph; 129 session 4 (≈ 250 chunks, exact) stopped by one controlled stop.**
133b (commit f44f55a215; manifest `ed908a90…4fd3`; inner plan `b67b1a8f…ab7b`; 1,058 recovery incl. 6 sealed-import tests, 6,351 client,
10 preflight, 22 output comparisons). Root cause of the 133 failure: the helper existed under `resolution/components/` and `source/scripts/`
but neither was on the launcher's initial import path; the author-tree suites masked it. Launch (work dir `s133b-live01`):
`LTX_TEXT_RESIDENCY=split36 LTX_CONE_GRAPH_MEMORY=text-shift LTX_AUDIO_RESIDENCY=legacy LTX_CONE_CAPTURE_RESERVE=parent LTX_DISPLAY_ALLOCATOR_RELEASE=off
LTX_AUX_RESIDENCY=legacy LTX_DISPLAY_WORKER=serial LTX_MAINTENANCE_MODE=idle LTX_GC_INTERVAL_SECONDS=60 LTX_SNAPSHOT_DIGEST_CACHE=1
LTX_STORAGE_SCAN_MODE=background LTX_RUN_WRITE_ALLOWANCE_GIB=16 launch-133b.sh 145 frame 1 cone 1 1 fingerprint - eager-display 0 full xpu:3`.

**2026-10-10, packet 133b packaging repair sealed and fully CPU-validated; native qualification remains pending.**
The launcher could not find a helper already bundled elsewhere in packet 133.
133b puts the unchanged helper and its pinned oracle beside the launcher and
uses its own packet identity. Both import modes passed before sealing. The new
test reproduces the original133 failure without modifying that packet.

All 1,058 recovery tests passed, including six sealed-import tests. All 6,351
client checks across 43 suites passed, as did 32 inner-plan pin assertions,
10 mocked preflight checks and 22 CPU output comparisons. Four stale inherited
identity fixtures were corrected; the first run and the clean rerun are saved.
Recursive verification covers 2,313 bound files, with zero Python caches.
Owned scratch is removed. No launcher, check-only, GPU, live port or unit was
used; packet 133 and existing runs remain untouched. The coordinator retains
control of live work. Native memory, exactness and speed are still unmeasured.

Manifest `ed908a9031a937801d17264edacfe0807bea543badc412a32eb6118daa214fd3`;
inner plan `b67b1a8fe9b3457666190267a3ff020cd3708371d89de60952d1e0f60dafab7b`.
[Rebuild note](experiments/ltx25-b70/notes/2026-10-10-continuation133b-rebuild.md),
[build receipt](experiments/ltx25-b70/data/resume-20261008/continuation133b-build.json),
[future command](experiments/ltx25-b70/recovery/20261010-continuation133b-stream/LAUNCH.md).

**2026-10-10 14:05 UTC, 133 rehearsal failed before device work (`ModuleNotFoundError: text_residency133` from `cone_memory131.validate_scope`, a bare import of a helper the sealed launcher loads by path under another module name); 129 production relaunching now (`s129-live04`); Codex rebuilding 133b with a sealed-launcher import test.**
The CPU suites import from the author tree, so the sealed packet's import path was never exercised; 133b adds a test that imports the sealed
`launch/serve-encoder.py` chain exactly as the launcher does. Off-air from the 13:53 stop until the 129 relaunch qualifies (≈ 14:15 UTC).

**2026-10-10 13:55 UTC, launching 133 at 145: text layers 36–47 (5.08 GiB) moved from xpu:3 to xpu:2 before capture (`LTX_TEXT_RESIDENCY=split36`), no display replica, legacy audio, cone decoder graph (`LTX_CONE_GRAPH_MEMORY=text-shift`).**
Codex's text inventory (`notes/2026-10-10-continuation133-stream-design.md`, commits 983eb2608, 30031ad55): text layers 0–23 on xpu:2
(10.15 GiB) and 24–47 on xpu:3 (10.15 GiB), 480 pinned text graphs, no text state kept between cuts beyond one hash-checked conditioning
result; a fresh encode costs ≈ 0.39 s per cut (every 4 chunks). Ranked options: split36 (zero per-cut cost; projected margins above floor +
band 2.80 GiB on xpu:2 and 2.21 GiB on xpu:3 charging the full 5 GiB reserve) › host-resident shard (1–2 s per cut, graph-pointer issues)
› all text on xpu:2 (not admitted) › scheduled prefetch (no memory) › dropping graph pools (no guaranteed memory). 133 (manifest
`a1f0fb23…4bd6`; inner plan `b230f1db…00d9`; 1,052/1,052 recovery, 6,012/6,012 client, 10/10 preflight, 22/22 runtime comparisons) requires
every fresh encode to match the pinned parent conditioning hashes (2 qualification prompts + 10 kitten scenes; unknown prompts refuse).
129 production session 3 (≈ 450 chunks, exact, no stops) stopped by one controlled stop. Launch (work dir `s133-live01`):
`LTX_TEXT_RESIDENCY=split36 LTX_CONE_GRAPH_MEMORY=text-shift LTX_AUDIO_RESIDENCY=legacy LTX_CONE_CAPTURE_RESERVE=parent LTX_DISPLAY_ALLOCATOR_RELEASE=off
LTX_AUX_RESIDENCY=legacy LTX_DISPLAY_WORKER=serial LTX_MAINTENANCE_MODE=idle LTX_GC_INTERVAL_SECONDS=60 LTX_SNAPSHOT_DIGEST_CACHE=1
LTX_STORAGE_SCAN_MODE=background LTX_RUN_WRITE_ALLOWANCE_GIB=16 launch-133.sh 145 frame 1 cone 1 1 fingerprint - eager-display 0 full xpu:3`;
predicted 5.25–5.35 s (0.875–0.892 s/s); a refusal latches and the 129 line returns.

**2026-10-10, packet 133 sealed and CPU-validated: move twelve text layers to card 2 before capture; native qualification remains pending.**
The proposed 145-frame setup keeps layers 0–35 on card 2 and 36–47 on card 3,
with display back on card 3, no display replica and legacy audio placement.
It moves 5.076 GiB of weights, plus an estimated 1.078 GiB of graph inputs,
away from the decode card without copying weights at each scene cut.
The 9 GiB floor, 5 GiB capture reserve and 0.75 GiB band remain unchanged.
Using saved native-display readings and charging the full reserve, projected
margins above floor plus band are 2.801 GiB on card 2 and 2.211 GiB on card 3.
These are planning estimates, not measured memory released by packet 133.

The option is `LTX_TEXT_RESIDENCY=split36` with `LTX_CONE_GRAPH_MEMORY=text-shift`;
default `legacy` keeps packet 132 behavior. Every fresh text encode must match
the pinned parent conditioning hashes for the two qualification prompts and
ten kitten scenes. All 40 window-probe rows, the frozen 145-frame output table
and existing nine output checks remain mandatory. Unknown prompts refuse.
169 frames remain outside the new option. Native text equality, physical
memory and sustained timing are still unmeasured. The conditional forecast is
5.25–5.35 seconds per six seconds of video, plus unmeasured text-placement and
native-display scheduling effects. No live service state was changed here;
the coordinator retains control of the production line.

All 1,052 recovery tests and 6,012 client checks across 41 suites passed in
the final full runs. Ten mocked preflight checks, 22 runtime output comparisons
and all 30 inner-plan pin assertions passed. Recursive verification covers
2,299 bound files; Python caches are zero and owned scratch is removed.
The initial development failures and their corrections are preserved.
Manifest `a1f0fb23dbba64ea2530b58fb4787f736a602746a1be72a040688bf0eaf74bd6`;
inner plan `b230f1dbd3f799b7f5227ef8ea7a72057a901aa0054be67f3babe664aa8700d9`.
No GPU, model launch, check-only, live-port, unit, signal, host-setting,
existing-run or ltx-stream operation occurred during preparation.

Receipt audit corrects two details in the earlier 132 summary: its refusal was
at conditioning-B-before, and recorded cone reservation growth was 3.545 GiB.
That observed growth is not a peak bound and does not reduce the reserve.
[Design and ranked options](experiments/ltx25-b70/notes/2026-10-10-continuation133-stream-design.md),
[memory evidence](experiments/ltx25-b70/notes/2026-10-10-continuation133-memory-evidence.md),
[build receipt](experiments/ltx25-b70/data/resume-20261008/continuation133-build.json),
[prepared launch](experiments/ltx25-b70/recovery/20261010-continuation133-stream/LAUNCH.md).

**2026-10-10 12:50 UTC, 132 at 145: the cone-graph capture was admitted for the first time, but the streaming floor then refused (xpu:3 9.10 GB free < 9.66 GB floor at qrepeat-c000001); no fault, no latch. The cone graph at 145 is closed as a lever under the current residency; 129 production relaunching (`s129-live03`).**
With the display on the xpu:2 replica and the audio VAE/vocoder on xpu:2, the first cone capture fit (graph chunks 0–2 and repeat chunk 0 ran),
but the captured pool (~4.5 GiB reserved) left xpu:3 at 9.10 GB before the next request against the 9 GiB (9.66 GB) pre-request floor
(`native_safety.SafetyRefusal`, exactly the floor the owner set; not lowered). Codex's "1.05 GiB above the floor after growth" estimate was
≈ 1.6 GB optimistic. xpu:3 carries a 10.15 GiB text shard; without moving text layers off the decode card the graph pool and the floor cannot
coexist at 145. Decision: no further dg1 attempts at 145 with this residency; the production line stays 129 at 145 dg0 (0.92 s/s). Next design
question (packet 133, Codex): text-encoder residency — text is only encoded on scene cuts (text reuse on), so a host-resident or xpu:2-only text
encoder with an exact reload per cut could free 10 GiB on xpu:3 (cone graph, 169 frames) at a per-cut cost to be quantified.

**2026-10-10 12:20 UTC, launching 132 at 145: audio VAE + vocoder moved to xpu:2 (+0.34 GiB on xpu:3), cone decoder graph, display on the xpu:2 replica; projected first-capture margin +0.33 GiB incl. the screening band.**
Codex's 131 audit (commits cebbf51fd, 61e6b16bf): the allocator release reclaimed 0 bytes on xpu:3 (reserved stayed 17.03 GB); the two 121-frame
captures give 4.506 GiB estimated growth at 145 (0.49 GiB under the inherited 5 GiB reserve, which stays because no 145 peak bound exists);
the video encoder move (0.59 GiB) is deferred (shared decoder owner). 132 (manifest `67ec59a5…91ad`; inner plan `fbb1d04b…1e8f`; 960/960
recovery, 5,677/5,677 client, 10/10 preflight) adds `LTX_AUDIO_RESIDENCY=xpu2` with three cross-card waveform byte gates. 129 production
session 2 (≈ 250 chunks, exact, no stops) stopped by one controlled stop. Launch:
`LTX_AUDIO_RESIDENCY=xpu2 LTX_CONE_CAPTURE_RESERVE=parent LTX_CONE_GRAPH_MEMORY=replica-release LTX_DISPLAY_ALLOCATOR_RELEASE=off
LTX_MAINTENANCE_MODE=idle LTX_GC_INTERVAL_SECONDS=60 LTX_SNAPSHOT_DIGEST_CACHE=1 LTX_STORAGE_SCAN_MODE=background LTX_AUX_RESIDENCY=legacy
LTX_DISPLAY_WORKER=serial LTX_DISPLAY_REPLICA_TRANSIENT_GIB=5.640625 LTX_RUN_WRITE_ALLOWANCE_GIB=16 launch-132.sh 145 frame 1 cone 1 1 fingerprint - eager-display 0 full xpu:2`
(work dir `s132-live01`); predicted 5.25–5.35 s (0.875–0.892 s/s) plus the unmeasured audio-placement cost; a memory refusal latches and the
129 line returns.

**2026-10-10, packet 132 sealed; audio-only move prepared for the 145-frame cone graph, native qualification still pending.**
Packet 131's allocator release freed nothing on card 3. Its admission was short
12,451,840 bytes, already including the full screening band. Moving only the
audio VAE and vocoder to card 2 projects 0.340 GiB freed and a 0.328 GiB margin
with the original 5 GiB capture reserve, 9 GiB floor and 0.75 GiB band.
The upsampler stays on card 0. Three native cross-card waveform checks must
pass before capture; all nine existing output checks remain. Audio placement
and its timing can be tested separately from the graph option.

The two 121-frame captures support a 4.506 GiB estimate at 145, but do not
prove its peak memory bound. The proposed 4.76 GiB reserve is recognized and
refused until suitable measured evidence exists. It would lower the budget
by 0.24 GiB, not free physical memory. The larger encoder move is deferred
because its owner is shared with the decoder. No further allocator savings
are demonstrated. The conditional forecast remains 5.25–5.35 s per 6 s of
video (0.875–0.892 s/s), plus the unmeasured audio-placement cost.

The packet is sealed with its parent 131 identity and matching client pins.
All 960 recovery cases passed in the final full run. All 5,677 client checks
across 39 suites passed, including 28 inner-plan pin assertions; an inherited
packet 131 test fixture passed its corrected rerun. Ten mocked preflight checks
and 22 output-hash comparisons across three CPU runtime cases passed.
Recursive verification covers 2,269 bound files, with zero Python caches.
Owned scratch is removed; the two test-fixture corrections and original failure
logs are preserved. No GPU, model launch, live-port,
unit, process-signal, host-setting, existing-run or ltx-stream operation occurred.
The coordinator retains control of live work; no service state was changed.
The next native step is the audio-only option with the parent reserve, under
the coordinator's launch authority. Actual freed memory, waveform exactness,
145-frame capture and sustained timing remain unmeasured here.
[Design](experiments/ltx25-b70/notes/2026-10-10-continuation132-stream-design.md),
[memory evidence](experiments/ltx25-b70/notes/2026-10-10-continuation132-memory-evidence.md),
[build receipt](experiments/ltx25-b70/data/resume-20261008/continuation132-build.json),
[future launch](experiments/ltx25-b70/recovery/20261010-continuation132-stream/LAUNCH.md).

**2026-10-10 11:45 UTC, 131 cone-graph arm refused by its memory guard by 12 MB (no fault); both latches archived with a receipt; 129 production relaunching (`s129-live02`).**
At qgraph-c000000 the cone-graph admission required 15,837,691,904 B free on xpu:3 (5 GiB capture reserve + 9 GiB floor + 0.75 GiB screening)
and found 15,825,240,064 B (margin −12.45 MB) after the display moved to the xpu:2 replica and the allocator release ran. Kernel journal
clean, health unaffected; latches `decoder-graph-116-refused.json` and `display-replica-120-refused.json` archived
(`data/resume-20261008/latch-archive-131-cone-memory-…-receipt.json`: memory guard, not exactness). The 4.5 GiB growth estimate was
right within 0.3 GiB; the gap is the conservative 5 GiB reserve + the screening band. Next (packet 132, Codex): close ≈ 0.4–0.6 GiB on
xpu:3 exactly — relocate the audio VAE/vocoder (0.34 GiB) and any other small xpu:3 resident to xpu:2 (isolating the timing cost that the 123
aux move did not separate), and tighten the capture reserve only to a measured value, never the floor or band.

**2026-10-10 11:35 UTC, packet 131 sealed (cone decoder graph at 145 by moving the display to the xpu:2 replica + guarded allocator release before cone admission); launching it; the 129 production session closed (≈ 500 chunks, exact, 36 s buffer, no stops).**
Codex's xpu:3 inventory (`notes/2026-10-10-xpu3-residency-145.md`, commits d57b669f0, 6dea774ad): text shard 10.15 GiB, video encoder/decoder
0.59/0.78, audio VAE/vocoder 0.10/0.24; 129's minimum physical free by phase 10.85 / 14.36 / 14.30 / 10.86 / 10.86 / 10.81 GiB; the cone-only
capture growth measured 3.43 GB at 121 → est. 4.51 GiB at 145; the first capture needs 14.75 GiB physically free (qualification tail needs
3.3–3.8 GiB reclaimed by the release; unproven), later cones 9.75 GiB; insufficient memory latches (no damage). 131 (manifest `e25d8d62…ed6f`;
inner plan `526f832c…7514`; 899 recovery / 5,013 client / 10 preflight) adds `LTX_CONE_GRAPH_MEMORY=replica-release`. Launch:
`LTX_CONE_GRAPH_MEMORY=replica-release LTX_DISPLAY_ALLOCATOR_RELEASE=off LTX_MAINTENANCE_MODE=idle LTX_GC_INTERVAL_SECONDS=60
LTX_SNAPSHOT_DIGEST_CACHE=1 LTX_STORAGE_SCAN_MODE=background LTX_AUX_RESIDENCY=legacy LTX_DISPLAY_WORKER=serial
LTX_DISPLAY_REPLICA_TRANSIENT_GIB=5.640625 LTX_RUN_WRITE_ALLOWANCE_GIB=16 launch-131.sh 145 frame 1 cone 1 1 fingerprint - eager-display 0 full xpu:2`
(work dir `s131-live01`); conditional target 5.25–5.35 s (0.875–0.892 s/s); fallback 129/131 at 145 dg0 serial xpu:3.
**Owner decision available (not enabled):** `LTX_SNAPSHOT_SCHEDULE=a-xpu3-sync` removes 12 synchronize calls and no checks on eligible chunks;
the three early on-chain snapshots cost 121–125 ms per chunk today (digest cache on); the measured memory sections are ≈ 1.8 ms, the barrier wait
is not separately timed, so the saving is bounded above by ≈ 0.12 s per chunk and may be much less.

**2026-10-10, packet 131 sealed and CPU validated; native graph fit at 145 remains unverified.**
The cone graph already captures just its first decoder method in its own pool.
Its measured 121-frame growth is 3.195 GiB; the 145 estimate is 4.506 GiB.
Moving display to card 2 has room, but qualification still performs full card 3
reference decodes. A new default-off option checks actual memory, releases
unused allocator blocks once if needed, and refuses if the capture allowance
and original floor are not covered. Every native reference and per-chunk byte
check remains. First capture requires 14.75 GiB free; later cones 9.75 GiB.
No freed memory or speed was measured. The conditional target is 5.25–5.35 s
per 6 s (0.875–0.892 s/s).

The three early snapshots now cost about 122 ms. The optional reduced-barrier
schedule drops no checks and targets memory sections totaling about 1.8 ms;
its full saving cannot be measured from these receipts. Keep full snapshots.
The coordinator still owns the live 129 server. No GPU, launch, live-port,
unit, process-signal, host-setting, existing-run or ltx-stream operation occurred.

CPU recovery coverage is 899 cases: 898 passed in the full run, and one stale
options fixture passed after correction in an isolated rerun. There are no
unresolved failures. All 5,013 client checks across 37 suites passed, including
26 inner-plan pin assertions. Two CPU runtime cases produced 11 matching output
hashes; 10 mocked preflight checks passed. Recursive verification covers 2,242
bound files, with zero Python caches; owned test scratch is removed. The broad
literal-pin audit retains 231 unrelated pre-existing Flash-Next drifts.
Native qualification remains for the coordinator. Packet and inner-plan hashes,
logs and exact counts are in the build receipt.
[Inventory](experiments/ltx25-b70/notes/2026-10-10-xpu3-residency-145.md),
[snapshot costs](experiments/ltx25-b70/notes/2026-10-10-continuation131-snapshot-schedule.md),
[design](experiments/ltx25-b70/notes/2026-10-10-continuation131-stream-design.md),
[build receipt](experiments/ltx25-b70/data/resume-20261008/continuation131-build.json),
[future launch](experiments/ltx25-b70/recovery/20261010-continuation131-stream/LAUNCH.md).

**2026-10-10 10:50 UTC, packet 130 sealed (xpu:2 inventory + guarded allocator release); 169 not launched: the reclaim is unverified and the upside over the 145 line is nil.**
Codex's inventory (`notes/2026-10-10-xpu2-residency-169.md`, commits 380fdfe03, d5471ed43): xpu:2 holds text layers 0–23 (10.15 GiB) and other
text state (4.13), the replica weights (0.78), live allocations 3.0–4.4, and 2.4–3.9 GiB reserved-but-unused allocator memory; physical free
at the refusal 7.88 GiB; the 169 replica screen needs 1.37 GiB reclaimed. 130 adds `LTX_DISPLAY_ALLOCATOR_RELEASE=before-admission`
(one cache release before an otherwise failing admission, then a fresh free check; default off; 842/842 recovery, 4,419/4,419 client,
10/10 preflight). Verified freed memory: 0 (CPU-only). Even if 1.5 GiB returns, card 2 clears by 0.13 GiB and the forecast is 0.886–0.950 s/s
against the measured 0.91–0.92 at 145: expected gain ≈ 0 for a 15-minute outage and a likely second latch. Decision: keep 129 at 145 as the
production line; 169 stays a diagnostic option. Next CPU design (131): the xpu:3 residency inventory and whether the cone decode's graph pool
can fit at 145 (cone 0.9 s eager vs ≈ 0.7 graphed), plus the on-chain snapshot schedule option's cost now that digests are cached.

**2026-10-10, packet 130 sealed for CPU-only review; live 169-frame admission remains unverified.**
The saved 169 refusal needs more memory than its message says: it is short
0.616 GiB for the reserve and floor, or **1.366 GiB including the existing
screening margin**. Recovering 0.8 GiB would still fail. Card 2 holds the first
text shard (14.278 GiB), the display copy (0.777 GiB), and live graph/workspace
allocations. Its adjacent snapshots show 2.400–3.856 GiB reserved but unused;
that is a candidate pool, not a promise that those bytes can be released.

The new optional allocator release runs once before an otherwise failing
display admission, then checks physical free memory again. Default off keeps
129's behavior. The operation can release unused allocator blocks across all
cards; it leaves live tensors, graphs, arithmetic and every memory/byte gate
intact. The transient reserve remains 6.5 GiB. No GPU operation, model launch,
unit operation or live request was performed, and existing runs were untouched.
The coordinator still controls the live server.

With a hypothetical 1.5 GiB release, saved card margins become
1.231 / 1.773 / 0.884 / 1.555 GiB after the relevant floors/reserve. Card 2
would clear its screening margin by 0.134 GiB. Forecast for the documented
169-frame parallel-display setup is 6.20–6.65 seconds per seven seconds of
video (0.886–0.950 s/s), plus unknown release cost. Actual reclaimed bytes,
full native equality, sustained memory headroom and repeated speed remain
for coordinator qualification; this preparation verifies no reclaimed GiB.

Parent 129; manifest `14aa145e…0980ed`; inner plan `0d24d0ff…af82ba`.
All **842 recovery tests**, **4,419 client checks in 35 suites**, **10 mocked
preflight tests**, and both final CPU runtime cases pass. All 24 inner-plan pin
assertions pass. Recursive verification covers 2,219 bound files (2,221 total),
with zero Python caches. All 35 client scratch roots and recovery scratch are
removed. Work used nice19, OMP/MKL2 and the pinned bin/python -B.
Links and manifest paths pass; the broad hash audit retains the same 231
existing Flash-Next drifts reported for129.
[Verified inventory and alternatives](experiments/ltx25-b70/notes/2026-10-10-xpu2-residency-169.md),
[design](experiments/ltx25-b70/notes/2026-10-10-continuation130-stream-design.md),
[build receipt](experiments/ltx25-b70/data/resume-20261008/continuation130-build.json),
[future launch and matching client](experiments/ltx25-b70/recovery/20261010-continuation130-stream/LAUNCH.md).

**2026-10-10 10:18 UTC, combined 128 arm (idle + GC 60 + digest cache) measured: n = 61, median 5.528 s (even 5.50 / odd 5.84, p90 6.01) = 0.921 s/s (verdict 0d1d0d811ce2, exact); the two levers overlap rather than add. Packet 129 launched at 145 with the same production configuration (`s129-live01`).**
145-frame line summary (chunks ≥ 10): 121 legacy 5.636 · 123b 5.770 · 126 5.759 · **127 5.467** · 128 (idle, GC 10) 5.493 · 128 (idle + GC 60 + digest) as above.
The production line is therefore ≈ 5.47–5.50 s per 6.0 s of video = **0.91–0.92 s/s**, all configurations byte-exact at the gates. 129 adds
atomic publication for every route-read evidence file (reliability; speed expected equal). Codex is on 130 (xpu:2 headroom for 169).

**2026-10-10 10:10 UTC, packet 129 sealed: every HTTP-route-read evidence file (receipts, decode records, /view captures, identity/halt files) is now published by temp + fsync + rename; the route guard is unchanged.**
Codex (commits 083748b2b, fd3b22b9e; manifest `42e6a745…886c`; inner plan `466039fc…6536`; 796/796 recovery incl. 33 publication tests,
3,850/3,850 client, 10/10 preflight; inventory `recovery/20261010-continuation129-stream/inventory129.md`; its /tmp scratch deleted).
This closes the two exit-7 client stops of the night (preview at chunk 154 on 121, decode record at chunk 80 on 127). Plan: once the
combined 128 arm (idle + GC 60 + digest cache, `s128-gc60-live01`) has ≥ 60 chunks for the record, swap to 129 with the same production
configuration; 129 is reliability-only, speed expected equal to 128.

**2026-10-10 09:57 UTC, 128 idle-maintenance (GC 10) session closed at 70 chunks (verdict 86134e704d4f, exact); launched the combined arm: 128 with idle maintenance + GC 60 + digest cache (`s128-gc60-live01`).**
The GC-10 idle session's final figures (n = 60): median 5.493 s = 0.915 s/s, even 5.45 / odd 5.79, p90 5.97. The combined arm's command:
`LTX_MAINTENANCE_MODE=idle LTX_GC_INTERVAL_SECONDS=60 LTX_SNAPSHOT_DIGEST_CACHE=1 LTX_STORAGE_SCAN_MODE=background LTX_AUX_RESIDENCY=legacy
LTX_DISPLAY_WORKER=serial LTX_RUN_WRITE_ALLOWANCE_GIB=16 launch-128.sh 145 frame 0 cone 1 1 fingerprint - sampler-a 0 full xpu:3`. Target ≈ 5.4 s.

**2026-10-10, packet 129 sealed and fully CPU-validated; the coordinator still owns the live server.**
Receipts, decode records and the other route evidence now appear only after
writing finishes and the file is flushed to disk. Final files cannot be
replaced. The evidence reader and every hash and byte gate stay unchanged.
Capture files, anchors and startup evidence use the same rule; preview
publication keeps packet 123's fix. Private partial files cannot be served by
`/view`. No route consumes an append-only evidence manifest.

Use the 127 production arm at 145 frames with GC60, digest cache, background
storage, legacy auxiliaries and serial display on xpu:3, plus 128's idle option.
The idle option gives no extra delay past its existing 60-second hard bound;
no additional speed gain is claimed. The default client folder is `s129-live01`.
Native qualification and the 169-frame memory refusal remain with the
coordinator. This preparation performed no live operation.

Parent128; manifest `42e6a745…a4886c`; inner plan `466039fc…d06536`.
All **796 recovery tests** pass, including 33 atomic-publication tests. All
**3,850 client checks in 33 suites**, **10 mocked preflight tests**, and **two
complete CPU runtime cases** pass. Recursive verification covers 2,196 bound
files (2,198 total), with zero Python caches. Client pins use the inner plan.
All 33 client scratch roots under `/tmp` are deleted; recovery scratch is also
removed. Work used nice19, OMP/MKL2 and the pinned Python -B. The unrelated
broad pin audit retains the same 231 existing Flash-Next drifts.
[Route/file inventory](experiments/ltx25-b70/recovery/20261010-continuation129-stream/inventory129.md),
[design](experiments/ltx25-b70/notes/2026-10-10-continuation129-stream-design.md),
[build receipt](experiments/ltx25-b70/data/resume-20261008/continuation129-build.json),
[future launch](experiments/ltx25-b70/recovery/20261010-continuation129-stream/LAUNCH.md).

**2026-10-10 09:50 UTC, new best 145-frame line: packet 127 (digest cache + GC 60, serial, xpu:3) measured median 5.467 s = 0.911 s/s (n = 85, exact, verdict cbd91ba8a8cc); 128 (idle maintenance, GC 10) early 5.51 s with the parity gap closed (even 5.49 / odd 5.58, n = 27).**
Session medians at 145 (chunks ≥ 10): 121 legacy 5.636; 123b 5.770; 126 5.759 (n = 241); **127 5.467** (even 5.44 / odd 5.70, p90 6.04);
128 5.511 so far. 127's lever was estimated at 0.03–0.07 s; measured against 126 it is −0.29 s, so the digest cache (immutable signature
digests across the six snapshots) and the 60 s interval together removed most of the per-chunk CPU inspection cost; 128's idle maintenance
closes the parity gap at GC 10. Next: 128 with both (`LTX_MAINTENANCE_MODE=idle` + `LTX_GC_INTERVAL_SECONDS=60` + digest cache) if the
launcher scope admits the combination; target ≈ 5.4 s (0.90 s/s).

**2026-10-10 09:40 UTC, packet 128 sealed: the even-chunk stall is a full Python GC (~252 ms) plus allocator cleanup (~56 ms) landing in the receipt handoff; `LTX_MAINTENANCE_MODE=idle` defers it. Swapping to 128 at 145.**
Codex's overlap analysis (`notes/2026-10-10-continuation-evenchunk-stall.md`, commits 68fe09195, 45f94e8bb): all 119 long handoffs in the
126 session overlap the GC + allocator-cleanup pair; the preview encode finishes earlier and is not the blocker. 128 (parent 127; manifest
`bd6471f7…5ead`; inner plan `d0f849d2…f3d5`; 763 recovery / 3,322 client / 10 preflight CPU checks; synthetic receipt timing 21 ms vs
306 ms) adds `LTX_MAINTENANCE_MODE=idle|parent`: cleanup waits for a 250 ms handoff gap, with mandatory cleanup at the 60 s boundary; no
memory admission change (169 stays refused). Forecast at 145: 5.50–5.75 s, centre 5.60 (0.933 s/s). The 127 session (≈ 100 chunks, exact,
one decode-route race resumed) stopped by one controlled stop; launching `LTX_MAINTENANCE_MODE=idle LTX_GC_INTERVAL_SECONDS=10
LTX_SNAPSHOT_DIGEST_CACHE=1 LTX_STORAGE_SCAN_MODE=background LTX_AUX_RESIDENCY=legacy LTX_DISPLAY_WORKER=serial LTX_RUN_WRITE_ALLOWANCE_GIB=16
launch-128.sh 145 frame 0 cone 1 1 fingerprint - sampler-a 0 full xpu:3` (work dir `s128-live01`). Codex is on 129 (atomic publication of
every route-read evidence file).

**2026-10-10 09:30 UTC, 127 at 145 live (verdict cbd91ba8a8cc); one client stop on the decode route's evidence-guard race (chunk 80), client resumed; disk scratch cleaned.**
At 09:27:44 UTC the decode route answered HTTP 500 ("Evidence changed during read" on the decode record of stream127-s00000080): the same
writer/reader race class as the 04:32 preview incident; 123 made preview MP4/JSON publication atomic but the decode record (and receipts)
are still read while being written. Server healthy (phase stream, no fault, worker 91/91, journal clean); the client's new exit-7 status
capture confirms it. One client restart resumed the chain. Fix queued for the next packet: publish every route-read evidence file by
temp + fsync + rename (decode records, receipts), or re-check identity once after a bounded wait. Also: Codex test scratch under /tmp
(7 GB of packet copies from finished suites) deleted; free space 72 → 79 GB; briefs now require Codex to remove its own scratch.

**2026-10-10, packet 128 sealed and CPU-validated; the coordinator retains control of the live server.**
The saved timestamps identify full Python collection and allocator cleanup as
the repeated receipt delay: all 119 long packet 126 handoffs overlap that pair.
Preview and decode-tail work finish earlier. Packet 128's new optional idle
cleanup waits for a short handoff gap, while keeping mandatory cleanup at the
minute-age boundary and every byte, memory and fault gate. Default parent mode
keeps 127's scheduling. The change is CPU prepared, not live qualified.

Recommend 145 frames with idle maintenance, GC10, background storage, digest
cache1, legacy auxiliaries and serial display3. Forecast 5.50–5.75 seconds per
six seconds of new video, center 5.60 / 0.933 s/s. Fresh-text chunks remain
slower, and forced/automatic collection can still pause the process. The 169
forecast stays conditional: the coordinator's newer 127 memory refusal below
must be resolved first; 128 does not lower its reserve or bypass its guard.
Native byte, memory plateau and two fresh-server speed gates remain open.

Parent127; manifest `bd6471f7…9f5ead`; inner plan `d0f849d2…92f3d5`.
Recursive verification covers 2,171 files with zero Python caches. Validation
covers 763 recovery cases (761 in the full run plus both corrected fixture
rechecks: 17-case module and 7-case class), all 3,322 client checks in 31 suites,
10 mocked preflight checks and 2 complete CPU runtime cases. The actual receipt
handler passed the synthetic 50 ms timing gate at about 21 ms. All inner-plan pins
pass. Development failures and exact counts remain in the build receipt.
CPU only, nice 19, OMP/MKL 2, pinned Python -B; no live operation or protected-tree
write. The unrelated broad pin audit retains 231 existing Flash-Next drifts.
[Analysis](experiments/ltx25-b70/notes/2026-10-10-continuation-evenchunk-stall.md),
[design](experiments/ltx25-b70/notes/2026-10-10-continuation128-stream-design.md),
[build receipt](experiments/ltx25-b70/data/resume-20261008/continuation128-build.json),
[future launch](experiments/ltx25-b70/recovery/20261010-continuation128-stream/LAUNCH.md).

**2026-10-10 09:15 UTC, 127 at 169 (display replica on xpu:2, parallel worker, 6.5 GiB reserve) refused by its own memory guard during qualification; no fault. Back to 127 at 145.**
At qrepeat-c000001 the xpu:2 display replica refused: free 8,465,399,808 B < transient 6.5 GiB + 2 GiB floor (8.5 GiB); the server halted
(`stream-halt.json`), the client stopped (exit 6), latch `display-replica-120-refused.json` written. Kernel journal clean, health probe
passed. The 124 census overestimated xpu:2 headroom at 169 by ≈ 0.6 GB; the reserve cannot be lowered below the census by design, so 169
with the replica is not admissible until xpu:2 memory is found (candidates for a later packet: trim what else sits on xpu:2 — the 123
auxiliaries are on legacy cards, so xpu:2 holds the replica weights 0.83 GB plus sampler/text workspace ≈ 18 GB allocated at qualification).
Latch archived with a review receipt (`data/resume-20261008/latch-archive-display-replica-120-…-receipt.json`: memory guard, not exactness;
the lever stays admitted at 121/145 where it qualified exact). Also: `LTX_GC_INTERVAL_SECONDS=60` and `LTX_SNAPSHOT_DIGEST_CACHE=1` are
scoped by the 127 launcher to the 145/serial/xpu:3 arm only (first 169 rehearsal refused "GC60 scope"). Relaunching the production line:
`LTX_SNAPSHOT_DIGEST_CACHE=1 LTX_STORAGE_SCAN_MODE=background LTX_GC_INTERVAL_SECONDS=60 LTX_AUX_RESIDENCY=legacy LTX_DISPLAY_WORKER=serial
LTX_RUN_WRITE_ALLOWANCE_GIB=16 launch-127.sh 145 frame 0 cone 1 1 fingerprint - sampler-a 0 full xpu:3` (work dir `s127-live01`).

**2026-10-10 09:10 UTC, packet 127 sealed with the 145-frame budget; the 2-cycle is quantified (even chunks: commit → served 0.32 s vs 0.04, text+A-prep 0.68 vs 0.50; whole period 6.10 vs 5.57); launching 127 at 169 with 124's display worker.**
Budget note `notes/2026-10-10-continuation-budget-145.md` (commits f14b3e4f2, 66f78927a): samplers 62 % of the period, all 48 blocks
already under graph replay; six snapshots 0.37 s; the parity penalty ≈ 0.53 s on even chunks (≈ 0.27 s per chunk averaged) sits in the
receipt route's commit → served wait and the pre-sampler path, not in GPU work. 127 (parent 126; manifest `c2564507…359e`; inner plan
`554c8051…cc01`; 720 recovery / 2,807 client / 10 preflight CPU checks) adds `LTX_SNAPSHOT_DIGEST_CACHE=1` (immutable signature digest
cache, est. 0.03–0.07 s; mutable state/fact caching rejected as unsafe). Ranked remaining levers: 169 with 124's parallel display
(0.886–0.950 projected), the even-chunk event-loop block (new brief 128), a 145 cone graph (no safe pool bound yet), sampler split
balance (no profile). The 126 session (≈ 250 chunks, exact, 5.72 s) stopped by one controlled stop; launching
`LTX_SNAPSHOT_DIGEST_CACHE=1 LTX_STORAGE_SCAN_MODE=background LTX_GC_INTERVAL_SECONDS=60 LTX_AUX_RESIDENCY=legacy LTX_DISPLAY_WORKER=parallel
LTX_DISPLAY_REPLICA_TRANSIENT_GIB=6.5 LTX_RUN_WRITE_ALLOWANCE_GIB=16 launch-127.sh 169 frame 0 cone 1 1 fingerprint - eager-display 0 full xpu:2`
(work dir `s127-f169-live01`); fallback is 127 at 145 legacy serial xpu:3.

**2026-10-10 08:53 UTC, packet 127 sealed on CPU; the coordinator keeps control of the live 126 server.**
The new option reuses only a digest of unchanged immutable graph signatures.
Every snapshot still reads fresh tensor state, device facts and memory levels;
the default-off path keeps packet 126 behavior. Later receipts directly link
all 64 long packet 126 handoffs to maintenance. GC60 removes that recurring
handoff delay in packet 125, but fresh-text work remains and its earlier whole
window was neutral. The measured 126 parent gives a revised first-launch
estimate of 5.45–5.70 seconds per six seconds of video (0.908–0.950 s/s), central
5.55 / 0.925. This is a forecast; the 0.90 goal is still open.

Recommend the new digest option with background accounting, GC60, 145 frames,
legacy auxiliaries and serial display on xpu:3. All live byte, memory and
fresh-server speed gates remain with the coordinator. No live operation was
performed. The 169-frame parallel-display combination and a safe 145-frame
cone graph remain unmeasured; the first graph capture is not bounded by a
smaller positive pool cap. Sampler blocks are already graphed.

Parent 126; manifest `c2564507…1dc359e`; inner plan `554c8051…abcc01`.
Recursive verification covers 2,151 files with zero Python caches. Recovery
validation covers 720 unique cases: 718 passed the full run, then all 16 tests
in the corrected parent-fixture module passed, including both failures.
All 2,807 client checks in 29 suites and 10 mocked preflight tests pass.
Client pins use the inner plan hash. Full development failures and rechecks
are preserved. CPU work used nice 19, OMP/MKL 2 and the pinned Python with -B.
[Budget](experiments/ltx25-b70/notes/2026-10-10-continuation-budget-145.md),
[design](experiments/ltx25-b70/notes/2026-10-10-continuation127-stream-design.md),
[build receipt](experiments/ltx25-b70/data/resume-20261008/continuation127-build.json),
[future launch](experiments/ltx25-b70/recovery/20261010-continuation127-stream/LAUNCH.md).

**2026-10-10 08:40 UTC, 126 at 145 measured (verdict a4b739676c5a, exact): median 5.72 s = 0.954 s/s; half of the 122–125 regression recovered; 126 stays live (it keeps the storage and preview fixes).**
n = 56 periods: median 5.722 (123b legacy 5.770; 121 legacy 5.636), even 5.59 / odd 6.10, p90 6.38. The background storage scan removed
≈ 0.05 s; ≈ 0.08 s of the 121→123b difference remains unattributed (candidates left: exit-7 status plumbing, aux plumbing, the 122
replica-reserve option path, atomic preview rename). Decision: keep 126 as the production line (reliability: own-writes allowance,
atomic previews) rather than return to 121 for 0.08 s. Packet 127 (budget + next lever) is sealing.

**2026-10-10 08:22 UTC, packet 126 sealed (request-thread storage walks removed; `LTX_STORAGE_SCAN_MODE=background`); swapping to 126 at 145.**
Codex's regression analysis (`notes/2026-10-10-continuation123b-regression.md`, commits 78a57ca3a, 2287c2bfb): the 123b own-writes
accounting ran filesystem walks on the request thread; the CPU plan-check replay saves 0.144 s per chunk with the scan moved to a
background sampler (the 50 GiB reserve check stays per request); preview fsync was already asynchronous. The claimed +0.15 s aux card-hop
penalty is not established by matched windows. 126 (parent 125; manifest `fe5ce9e0…0aa4`; inner plan `3858a121…92e8`; 696 recovery /
2,353 client / 10 preflight CPU checks). The 125 session (≈ 190 chunks, exact) stopped by one controlled stop; launching
`LTX_STORAGE_SCAN_MODE=background LTX_GC_INTERVAL_SECONDS=10 LTX_AUX_RESIDENCY=legacy LTX_DISPLAY_WORKER=serial LTX_RUN_WRITE_ALLOWANCE_GIB=16
launch-126.sh 145 frame 0 cone 1 1 fingerprint - sampler-a 0 full xpu:3` (work dir `s126-live01`); predicted 5.55–5.75 s (target 5.61–5.64 =
the 121 line). Then 169 on 126 with 124's display worker on xpu:2 and the 6.5 GiB reserve.

**2026-10-10 08:12 UTC, packet 126 sealed on CPU; live qualification remains with the coordinator.**
The saved receipts identify repeated storage walks and larger plan checks as
extra CPU work. Preview fsync was already on a separate worker. Packet 126's
explicit `LTX_STORAGE_SCAN_MODE=background` moves the walks to a helper and
checks the full plan more cheaply, while retaining refusal and mutation checks.
The paired CPU replay saves about 0.144 seconds per chunk's plan checks alone;
it is not a measured model speed. The default `request` mode keeps parent paths.
Use legacy auxiliaries, serial display on xpu:3 and GC 10 for the first 145-frame
comparison: forecast 5.55–5.75 seconds per six seconds of video (0.925–0.958 s/s),
target 5.61–5.64 (0.935–0.940 s/s). Native bytes, memory and speed on two fresh
qualified servers remain open. Matched old windows do not establish a further
0.15-second auxiliary card-hop penalty; exact historical scan/lock/fsync times
were not recorded. The coordinator's GC60-neutral finding below is preserved.

Parent 125; manifest `fe5ce9e0…b60aa4`; inner plan `3858a121…2092e8`.
Recursive verification passed for 2,128 files with zero Python caches. Full
recovery discovery plus its documented fixture recheck validates 696 unique
cases; all 2,353 client checks in 27 suites and 10 mocked preflight tests pass.
Client pins are checked against the sealed inner plan. Both inherited fixture
failures and successful whole-suite/module rechecks remain recorded. Work used
nice 19, OMP/MKL 2 and the pinned Python with `-B`; no GPU, live endpoint, launch,
unit, signal, existing-run/client-tree write or host-setting operation occurred.
The live server and launch sequence remain under the coordinator's control.
[Regression analysis](experiments/ltx25-b70/notes/2026-10-10-continuation123b-regression.md),
[design](experiments/ltx25-b70/notes/2026-10-10-continuation126-stream-design.md),
[build receipt](experiments/ltx25-b70/data/resume-20261008/continuation126-build.json),
[future launch](experiments/ltx25-b70/recovery/20261010-continuation126-stream/LAUNCH.md).

**2026-10-10 08:02 UTC, 125 at 145 (GC interval 60 s) measured: exact (verdict 7c1e8a6ef3b2), neutral; 124 at 145 also neutral; 126 (regression hunt) about to seal.**
125 GC 60, legacy, serial, display xpu:3 (n = 56 periods): median 5.780 s, even 5.73 / odd 6.07 (123b legacy baseline: 5.770, 5.70 / 6.12).
The maintenance interval was not the 2-cycle's main cost; the parity gap and the median are unchanged within noise. 124 at 145 (display
xpu:2, parallel worker, early audio; verdict 24e7fd6c6dbb, n = 35): median 5.746, even 5.57 / odd 6.06 — neutral at 145 as predicted
(its value is at 169). Fastest 145 line remains packet 121 legacy at 5.61–5.64 s (0.94 s/s); packets 122–125 carry a ≈ +0.15 s regression
that Codex's 126 attributes and removes (forecast 5.55–5.75). Next: 126 at 145 (legacy, serial, GC 10, display xpu:3) as soon as it seals,
then 169 on 126 with 124's display worker.

**2026-10-10 07:40 UTC, packet 125 sealed: the 145-frame 2-cycle is a 10-second server maintenance (GC) interval; `LTX_GC_INTERVAL_SECONDS=60` removes most of it. 124 at 145 qualified (verdict 24e7fd6c6dbb); swapping to 125 at 145 next.**
Codex's 2-cycle analysis (`notes/2026-10-10-continuation-2cycle-analysis.md`, commit 5e548dbb6): the growing wait on the slow parity is receipt
commit → first served, matching a 10 s maintenance cycle (also present at 121 frames); packet 125 (parent 124; manifest `3c2ed919…5421`;
inner plan `238695df…9cd2`; 655 recovery / 1,942 client / 10 preflight CPU checks) adds `LTX_GC_INTERVAL_SECONDS=10|60` (10 = parent
cadence). Recommended arm: 145, legacy, serial display worker, display xpu:3, GC 60 → predicted median 5.45–5.75 s (0.908–0.958 s/s) against
the 123b legacy baseline 5.77. Sequence: stop 124 at 145 after 45 chunks (record), launch 125 at 145 (GC 60), then 125 at 169 with 124's
display-xpu:2 parallel worker and the 6.5 GiB reserve. Codex is on packet 126 (the +0.15 s 121→123b regression).

**2026-10-10 07:35 UTC, packet 125 sealed on CPU; live operations remain with the coordinator.**
The saved 145-frame and 121-frame timelines put the alternating delay after the
prompt finishes and the receipt commits, before the receipt is served. A prep
already precedes display, and preview already has a separate worker. The
parent's ten-second garbage collection and allocator cleanup closely predict
the slow handoffs. The later legacy 123b snapshot agrees in all 49 classified
handoffs. These older logs did not time cleanup itself, so this remains a strong
inference that packet 125's new timestamps can confirm.
Packet 125 inherits sealed 124 and offers `LTX_GC_INTERVAL_SECONDS=10|60`:
10 keeps the parent cadence; 60 is restricted to the 145-frame serial display3
path and retains both cleanup calls. Start with legacy auxiliaries. Expected
median is 5.45–5.75 seconds per six seconds of video, targeting 5.55 / 0.925 s/s.
Occasional minute-interval cleanup and fresh-text costs remain; the later
legacy baseline's fast side was 5.689 seconds. Native bytes, memory trends and
speed on two fresh qualified servers remain open. No server was launched.
The seal is `3c2ed919…565421`; inner plan `238695df…149cd2`; 2,109 files verified
recursively, zero Python caches. Full discovery plus documented fixture
rechecks validates 655 recovery cases; all 1,942 client checks in 25 suites and
10 mocked preflight tests pass. Every client plan pin is checked against the
sealed inner hash. Work stayed at nice 19 with OMP/MKL 2. No GPU, live endpoint,
unit, process signal, existing-run/client-tree write or host setting change.
The coordinator's live state and launch sequence remain theirs to manage.
[Analysis](experiments/ltx25-b70/notes/2026-10-10-continuation-2cycle-analysis.md),
[design](experiments/ltx25-b70/notes/2026-10-10-continuation125-stream-design.md),
[build receipt](experiments/ltx25-b70/data/resume-20261008/continuation125-build.json),
[future launch](experiments/ltx25-b70/recovery/20261010-continuation125-stream/LAUNCH.md).

**2026-10-10 07:28 UTC, 123b legacy baseline done (61 chunks, exact, verdict b6bcdae18297); packet 124 launched at 145 frames (display replica on xpu:2, parallel display worker, early audio).**
Launch `LTX_AUX_RESIDENCY=legacy LTX_DISPLAY_WORKER=parallel LTX_RUN_WRITE_ALLOWANCE_GIB=16 launch-124.sh 145 frame 0 cone 1 1 fingerprint - eager-display 0 full xpu:2`
at 07:27 UTC after the gap; client `start-client-124.sh 145 0 cone 1 1 fingerprint none eager-display 0 full xpu:2` with the same variables
(work dir `s124-live01`); qualification running. **Baseline correction:** the 123b *legacy* session measured median 5.770 s (even 5.70 / odd 6.12,
n = 51) against packet 121 legacy 5.61–5.64 s, so packet 123b itself costs ≈ +0.15 s per chunk (atomic preview publication with fsync on the
decode thread, or the per-chunk own-writes accounting walk, or the exit-7/status plumbing) and the aux move another ≈ +0.15 s on top (5.93).
124 inherits 123b's code path, so its comparisons use 5.77 as the baseline; a regression hunt is queued for Codex (packet 126) after 125.
Next: 124 at 169 with `LTX_DISPLAY_REPLICA_TRANSIENT_GIB=6.5` (predicted 0.886–0.950 s/s).

**2026-10-10 07:15 UTC, packet 124 sealed (display on xpu:2 with legacy auxiliaries; early audio; optional parallel display worker); plan: 123b legacy at 145 live → 124 at 145 (parallel + early audio) → 124 at 169.**
Codex's 169 timeline (`notes/2026-10-10-continuation123b-results-169.md`, commit 58a22e4b9) corrects the coordinator's reading: the display
decode usually finished before the next cone was queued; the cone's extra ≈ 0.6 s was the decode worker queueing behind audio decode and
bookkeeping, and the cone itself cost 1.14 s (145: 1.02). Packet 124 (commit b99a7a8ee; manifest `897442d0…26a5`; inner plan
`71fc6e9b…da68`; 623 recovery / 1,550 client / 10 preflight CPU checks; all client plan pins now checked against sealed inner hashes):
display replica on xpu:2 with the auxiliaries in their legacy places (xpu:1 fails admission by margin), audio decode moved earlier, optional
separate display/completion worker. Projections: 145 → 5.50–6.10 s; **169 (parallel + early audio, 6.5 GiB replica reserve) → 6.20–6.65 s
per 7.0 s = 0.886–0.950 s/s** (adverse 7.2 s), margins 1.34 / 1.80 / 2.21 / 1.81 GiB. Packet 125 (the 145-frame even/odd 2-cycle) is in
CPU design. Sequence: let the 123b legacy 145 session collect a baseline, then 124 at 145 (parallel + early audio), then 124 at 169.

**2026-10-10 07:05 UTC, two findings from the 145-frame sessions: an even/odd 2-cycle in the period, and the xpu:2 auxiliary residency costs +0.17 s; swapping to 123b at 145 with the legacy placement.**
Across all four 145-frame sessions the period alternates: legacy placement (packet 121, n = 409 + 306) even-seq median 5.53–5.55 s vs
odd-seq 5.91–5.94 s; aux xpu:2 (123b, n = 31 + 190) 5.64–5.71 vs 6.09–6.16. The slow chunks carry a longer pre-sampler path
(`text+A-prep` 0.63 vs 0.50 legacy, 0.76 vs 0.51 aux) and longer go-wait; chain buckets otherwise equal. Whole-session medians: legacy
5.71–5.76 s (0.95 s/s), aux 5.93 s (0.99 s/s): the residency move (which bought memory margin, +0.6 GB) costs ≈ 0.17 s per chunk,
so it is only worth keeping where the margin is needed (169). Session `s123b-live02` (190 chunks, exact) stopped by one controlled stop;
relaunching 123b at 145 with `LTX_AUX_RESIDENCY=legacy` (keeps the atomic previews and the own-writes allowance) as `s123b-legacy-live01`.
Next design target (packet 125): the 2-cycle — likely the previous chunk's display decode + preview (≈ 3.5 s on the decode thread)
colliding with the next chunk's stage-A prep-ahead and request snapshot on alternate chunks; removing it is worth ≈ 0.2 s per chunk
(→ ≈ 0.92 s/s at 145).

**2026-10-10, packet 124 prepared on CPU; live operations remain with the coordinator.**
The saved 169-frame timeline corrects the earlier diagnosis below: the display
usually finished before the next cone was queued. Audio and bookkeeping kept the
same worker busy for about another 0.6 seconds. The cone itself cost about 1.14
seconds, versus 1.02 at 145 frames; the three-second bound limits waiting for the
next sampler, not display decoding.
Packet 124 keeps the auxiliaries in their legacy places, puts display on xpu:2,
and optionally runs audio earlier with a separate display/completion worker.
Moving the auxiliaries to xpu:1 fails the required memory margin. Start with a
145-frame placement control, then the 145-frame parallel path, then 169 with the
6.5 GiB replica reserve. The 169 forecast is 6.20–6.65 seconds per seven seconds
of video (0.886–0.950 s/s), with projected margins 1.34 / 1.80 / 2.21 / 1.81 GiB
on cards 0–3. These are projections; native bytes, memory and timing remain open.
The final seal is `897442d0…9926a5`; 2,087 files verified recursively, zero Python
caches. The first unlaunched build is preserved as rejected after a CPU test
caught a receipt-reader error. Full recovery discovery and documented rechecks
validate 623 cases; all 1,550 client checks and 10 mocked preflight checks pass.
Client pins use each sealed plan's inner hash, with a regression covering every
plan pin. Exact counts and logs are in the
[build receipt](experiments/ltx25-b70/data/resume-20261008/continuation124-build.json).
No live operation, GPU work, launch, check-only, port/unit access, process signal,
existing-run/client-tree write or host change was performed by this CPU task.
Live placement and operations follow the coordinator's newer entries above.
[Analysis](experiments/ltx25-b70/notes/2026-10-10-continuation123b-results-169.md),
[design and open gates](experiments/ltx25-b70/notes/2026-10-10-continuation124-stream-design.md),
[future launch order](experiments/ltx25-b70/recovery/20261010-continuation124-stream/LAUNCH.md).

**2026-10-10 06:35 UTC, 169 frames measured: exact but 0.975 s/s (loss vs 145's 0.94–0.955); back to 123b at 145 (aux xpu:2).**
169 (verdict 4eeb3b603c94, n = 27 periods): median 6.824 s per 7.0 s of video; cone on the chain 1.73 s (145: 1.02) and the eager display
decode 3.98 s (over its 3 s bound) share xpu:3, so the cone waits behind the previous display; memory held (min margin 1.93 GB, periodic
duals only). Note `experiments/ltx25-b70/notes/2026-10-10-continuation123b-results-169-coordinator.md`. Controlled stop 06:33 UTC, names
archived, 145 aux line relaunching (`s123b-live02`). Next design (packet 124, Codex): 169 with the display decode off xpu:3 within memory.

**2026-10-10 06:12 UTC, 123b at 145 frames with `aux_residency=xpu2` qualified exact (verdict d410928322ba, 32/32 byte-identical to 121); swapping to 169 frames.**
Measured with the upsampler and audio VAE/vocoder on xpu:2 (chunks ≥ 10, n = 23): period median 5.73 s (legacy 5.76), sampler A/B
1.91 / 1.62, cone 1.02 (legacy 0.88), display decode 2.75; minimum snapshot margin **1.98 GB** (legacy 1.39), dual snapshots periodic
only. The 145-frame gate for the residency move is met. Launching the first 169-frame arm:
`LTX_AUX_RESIDENCY=xpu2 LTX_RUN_WRITE_ALLOWANCE_GIB=16 launch-123b.sh 169 frame 0 cone 1 1 fingerprint - sampler-a 0 full xpu:3`
(7.0 s of video per chunk; predicted 5.95–6.65 s = 0.85–0.95 s/s; projected margins xpu:0 1.62–1.93, xpu:3 0.83–1.56 GiB; display
decode forecast 2.72–3.30 s against the 3 s off-chain bound — the quantity to watch). Client `start-client-123b.sh 169 0 cone 1 1
fingerprint none sampler-a 0 full xpu:3` (work dir `s123b-f169-live01`). No earlier reference at 169: three-chain identity is the gate.

**2026-10-10 05:58 UTC, 123b server live at 145 frames with `aux_residency=xpu2`; client preflight pin bug fixed; qualification running.**
Server ready 05:55:17 UTC (status reports frames 145, aux xpu2). The 123b client refused at preflight (exit 8, "plan differs from the
pinned plan"): Codex had pinned the plan file's byte hash (`0537b39f…`) while the server reports the inner `plan_sha256`
(`75e97784…`, also in the build receipt); the never-launched 123 pin had the same defect. Both pins corrected in
`stream/ltx_continuation_client.py` (commit 9f6b4414b; `run_tests_123b.py` 202/205, the three failures are the CPU-runner device-open
audit tests, unrelated). Client started 05:57:49 UTC; this run is the 145-frame qualification of the residency move that gates 169.

**2026-10-10 05:58 UTC, packet 123b sealed (run-own-writes storage allowance); swap to 123b at 145 frames with `LTX_AUX_RESIDENCY=xpu2`.**
Codex sealed 123b (commits af43e4e73, 9fbe0645b; manifest `5bdc0956…d433`; 592 recovery / 1,238 client / 10 preflight CPU checks,
2,064 files): the 3 GiB run allowance now counts the run's own writes (run dir + its output/validation/request entries), with
`LTX_RUN_WRITE_ALLOWANCE_GIB=N` (1–64, default 3) recorded in server options and receipts and checked by the client; the 50 GiB
whole-filesystem reserve stays. 145-frame session 2 (packet 121) stopped by one controlled stop after ≈ 250 chunks, names archived.
Launching `LTX_AUX_RESIDENCY=xpu2 LTX_RUN_WRITE_ALLOWANCE_GIB=16 launch-123b.sh 145 frame 0 cone 1 1 fingerprint - sampler-a 0 full xpu:3`
(upsampler + audio VAE/vocoder on xpu:2; dg0; display xpu:3), client `start-client-123b.sh 145 0 cone 1 1 fingerprint none sampler-a 0 full xpu:3`
with the same two variables (work dir `s123b-live01`). This is the 145-frame qualification of the residency move that the 169-frame
launch requires; predicted period unchanged (5.45–6.20 s), margins xpu:0 2.20 / xpu:3 2.19 GiB projected.

**2026-10-10, packet 123b sealed on CPU; live operations remain with the coordinator.**
The packet now counts this run's own disk use, so other builds and logs cannot
spend its allowance. The separate 50 GiB free-space floor stays unchanged.
The allowance defaults to 3 GiB; `LTX_RUN_WRITE_ALLOWANCE_GIB` accepts 1–64 GiB,
and the client must expect the same value. Packet 123 remains the unchanged
parent. Its residency option, atomic previews and exit-7 status are preserved;
storage refusal still returns HTTP 409 and stops the client with exit 15.
The seal is `5bdc0956…a74d433`: 2,064 files verified recursively, no Python
caches. Validated: 592 recovery cases (full discovery plus three corrected
fixture rechecks), 1,238 client checks and 10 mocked preflight tests. Historical
client-wrapper assertions were updated to match the coordinator's existing
reset-failed lines; no wrapper or unit was operated.
No GPU work, model server, launch, real preflight, port 8188, unit, signal,
existing-run write, live-client write or host change was performed. Device
qualification and the planned swap remain the coordinator's work.
[Design and launch details](experiments/ltx25-b70/notes/2026-10-10-continuation123b-storage.md)
and [sealed build receipt](experiments/ltx25-b70/data/resume-20261008/continuation123b-build.json).

**2026-10-10 05:22 UTC, 145-frame session 2 live (verdict 9a57f69a751f); packet 123 sealed; 123b (storage-allowance fix) in build; then one swap to 145 + residency move, then 169.**
Codex sealed 123 (commit bbcdbc8ce; manifest `db5ea277…340d`; 570 recovery / 995 client / 10 preflight CPU checks, 2,044 files): atomic
preview MP4/JSON publication (closes the chunk-154 read race), exit-7 records server status, and `LTX_AUX_RESIDENCY=xpu2` moving
the upsampler and the audio VAE/vocoder to xpu:2 (default `legacy` = 121/122 placement). Projected margins with the move (GiB above
floors): 145 → xpu:0 2.20 / xpu:1 1.83 / xpu:2 6.44 / xpu:3 2.19; **169 → 1.62–1.93 / 1.57–1.71 / 6.44 / 0.83–1.56**, so 169 is
admitted after a 145 qualification of the move; predicted 169 period 5.95–6.65 s per 7.0 s = 0.85–0.95 s/s (display decode forecast
2.72–3.30 s against the 3 s off-chain bound: watch it). Auxiliary move + xpu:2 display replica is refused by the packet. The
filesystem-wide storage allowance was not changed in 123; Codex is building 123b (parent 123) with a run-own-writes allowance and a
`LTX_RUN_WRITE_ALLOWANCE_GIB` option. Plan: keep 121 at 145 live; one swap to 123b at 145 with `LTX_AUX_RESIDENCY=xpu2` (dg0,
display xpu:3), then 169 on the same packet.

**2026-10-10 05:18 UTC, packet 123 sealed on CPU; live operations remain with the coordinator.**
Packet 123 makes previews appear only after their files are complete. The client
now records server status when a preview read stops it. An optional move of the
upsampler and audio decoder to xpu:2 makes 169 frames a candidate: about 6.2
seconds for seven seconds of new video is the forecast, not a measurement.
First compare 145 frames with the preview fix, then qualify the move at 145
against saved output bytes, then consider 169. The tightest projected margin at
169 is 0.825 GiB above the unchanged xpu:3 floor; real memory and byte checks
still decide. No graph/replica fallback is recommended.
The seal is `db5ea277…8b340d`: 2,044 files verified recursively, no Python caches,
570 recovery cases validated by full discovery and corrected assertion rechecks,
995 passing client checks and 10 mocked preflight checks. No GPU work, launch,
live preflight, port/unit operation, signal, existing-run write or host change
was performed. Native memory savings, exactness and display timing remain open.
The coordinator's new whole-filesystem storage-allowance issue below is inherited
and remains a follow-up; this packet does not fix or weaken that guard.
[Design and launch order](experiments/ltx25-b70/notes/2026-10-10-continuation123-stream-design.md)
and [sealed build receipt](experiments/ltx25-b70/data/resume-20261008/continuation123-build.json).

**2026-10-10 05:08 UTC, client stop on HTTP 409 "storage allowance exhausted" after 420 chunks; server relaunched for a fresh allowance; check must be fixed in 123.**
At 04:59:59 UTC the server refused new requests: `storage_check` requires `free_at_install − free ≤ 3 GiB` **over the whole
filesystem** (`integration.py:795`, `WRITE_ALLOWANCE` sealed in `ltx_duration_guard.py`), so every other writer on the single NVMe
(Codex packet builds and session logs, journals, test scratch) counted against the run; the run directory itself held 25 MB and each
chunk's output ≈ 240 KB. No fault, no latch; the first 145-frame session ended at 420 chunks (0.939 s/s). Decision: no deletion of
user data to satisfy the delta; one controlled server stop and relaunch of the same line (fresh `free_at_install`), names archived
(`output/archive-stream121-f145-live01-…`), run dir renamed `.completed`. Fix queued for packet 123: count the run's own writes
(run dir + its `output/stream*` entries) against the allowance, or make the allowance a launch parameter recorded in receipts; the
50 GiB reserve check stays as is.

**2026-10-10 04:52 UTC, packet 122 sealed (census refined); no swap: the 145 dg0 line stays live; packet 123 in design (free xpu:0 for 169 frames, fix the preview read race).**
Codex's 145-frame analysis (`notes/2026-10-10-continuation121-results-145.md`, commit 96a57a5db; 122 manifest `8b576c86…b7fa`,
489 recovery / 783 client / 10 preflight CPU checks) measured margins above the floors at 145 dg0: xpu:0 1.27 GiB, xpu:1 1.83,
xpu:2 9.71, xpu:3 1.85. Projections: **145 dg1 + xpu:2 replica → xpu:3 −0.68 to −0.25 GiB** (the graph pool scaled to 145 outweighs
the display transient it removes), so that arm is not admissible and will not be launched; **169 dg0 → xpu:0 0.69–1.00 GiB against
the 0.75 GiB required**, missing by ≈ 0.06 GiB, xpu:3 0.49–1.22. 122 adds `LTX_DISPLAY_REPLICA_TRANSIENT_GIB` (explicit reserve,
may only increase the census). Decision: keep streaming 121 at 145 frames dg0 (0.939 s/s, the best admissible line); Codex is
designing packet 123: an exactness-preserving residency change that frees ≥ 0.1 GiB on xpu:0 (sampler split rebalance or moving the
upsampler / text encoder to xpu:2, each as a launch option with its 145 qualification) to admit 169 frames (7.0 s of video per chunk),
plus atomic preview publication and a bounded identity re-check in the preview route.

**2026-10-10, packet 122 sealed on CPU; 169 frames still held back by memory.**
The saved 145-frame readings give more sampler room than the previous estimate,
but 169 still misses the required allowance on two cards. Moving display to the
spare card does not fix that. The next coordinator comparison is 145 frames with
the graph cone and display copy on xpu:2: predicted 5.35–5.90 seconds for six
seconds of new video, conditional on memory and exact-output checks. Retained
storage on xpu:3 may still refuse it. The display copy keeps its 5.640625 GiB
allowance; a new checked launch option can increase it, never reduce it.
The packet has 2,005 recursively verified files, no Python caches, 489 unique
recovery checks validated (full discovery plus corrected/added modules), 783
passing client checks and 10 mocked preflight checks. Final manifest is
`8b576c86…87cb7fa`. No GPU, launch, live preflight, port, unit, process signal,
existing-run write or host change was made. The coordinator's newer preview
read race below is inherited and remains open; the live-work entries are theirs.
[Analysis, margins and checks](experiments/ltx25-b70/notes/2026-10-10-continuation121-results-145.md)
and [launch reference](experiments/ltx25-b70/recovery/20261010-continuation122-stream/LAUNCH.md).

**2026-10-10 04:34 UTC, client stop on an HTTP 500 from the preview route (chunk 154); server healthy; client resumed.**
At 04:32:30 UTC the 121 client stopped itself (exit 7, no retry by design): the preview route answered HTTP 500 because the packet's
evidence guard (`read_regular`: size/inode/mtime/ctime identical before and after the read) saw `preview_00001_.mp4` of
`stream121-s00000154` change during the read, i.e. the preview writer was still finalising the larger 145-frame file when the
client fetched it. Server status: phase stream, no fault, decode worker 165/165, no latch; kernel journal clean; the preview file is
complete (252,936 B). One client restart (an application action; the server was not touched) resumed the chain at seq 156; the
server's own chain never broke. Follow-up for packet 122/123: make the preview route tolerate or wait out the writer (publish by
atomic rename, or retry the identity check once), since the window grows with chunk length.

**2026-10-10 04:25 UTC, packet 121 at 145 frames live: 5.61 s per 6.0 s of new video = 0.935 s/s, exact; the stream runs ahead of real time.**
Launched 04:08:58 UTC (`launch-121.sh 145 frame 0 cone 1 1 fingerprint - sampler-a 0 full xpu:3`), qualification verdict
356b25be584b at 04:17:28 (exact replay c0/c1/c2, measured geometry matches the sealed formulas: 145 frames, 144 new frames = 6.0 s
of video per anchored chunk), client `start-client-121.sh 145 0 cone 1 1 fingerprint none sampler-a 0 full xpu:3` (work dir
`s121-live01`). Steady state (chunks ≥ 10, n = 24): period median **5.612 s** (mean 5.75, p90 6.23) per 6.0 s of video; sampler A 1.91,
sampler B 1.68, cone on the chain 0.87 (eager), text+A-prep 0.51, upsample+B-prep 0.29, receipt 0.10; display decode off-chain 2.72;
dual snapshots periodic only (1/22); minimum snapshot margin 1.39 GB; `cone_equal` true on all. The sink's buffer is growing
(12 s after 29 clips) and holds have stopped. Fixed per-chunk costs amortised as predicted (sampler A+B 3.59 s for +20 % frames vs
3.11 at 121). Next arms: 145 frames with 120's dg1 cap 1.0 + eager display on the xpu:2 replica (cone −0.2 s → ≈ 0.90 s/s), and a
169-frame census refined from these receipts (packet 122, Codex).

**2026-10-10 04:06 UTC, packet 121 (145-frame chunks) sealed; swap from 120 to its first arm (145 frames, dg0, display on xpu:3).**
Codex sealed 121 (commit 11eec57ad; manifest `8f1d4e3b…44dd`; 461 recovery / 571 client / 10 preflight CPU checks; 1,980 files
verified recursively; design `notes/2026-10-10-continuation121-stream-design.md`). Geometry at 145 frames: 6.04 s of video per
anchored chunk, audio latent `[1,8,151,16]`, waveform `[1,2,288480]`; 169 frames stays disabled (conservative xpu:0 margin crosses
its floor). Predicted period at 145: 5.55–6.10 s = 0.92–1.01 s/s. Estimated dg0/xpu:3 margins above floors: xpu:0 0.68–1.04 GiB,
xpu:1 1.6–1.8, xpu:3 1.6–2.2 GiB. The 120 session (1.008 s/s over 100 periods, 121 chunks) is stopped by one controlled stop; the
chain then archives names, probes health, rehearses and launches `launch-121.sh 145 frame 0 cone 1 1 fingerprint - sampler-a 0 full xpu:3`
after the five-minute gap, client `start-client-121.sh 145 0 cone 1 1 fingerprint none sampler-a 0 full xpu:3` (work dir `s121-live01`).
Qualification at 145 frames has no earlier reference: the three-chain identity is the gate. Second arm (next window): 145 frames
with 120's dg1 cap 1.0 + eager display on the xpu:2 replica.

**2026-10-10 03:58 UTC, packet 120 live at 121 frames: 5.029 s per 5.042 s chunk = 0.997 s/s on the first 28 periods; over 100 periods 5.082 s = 1.008 s/s (0.8 % above real time), exact.**
Run `encoder-server-continuation-stream-120-frame-dg1-adcone-bo1-pa1-smfp-…-f121` (dg1 cap 1.0, eager display on a decoder-only
replica on xpu:2, read-ahead 0, snapshots full), launched 03:43:18 UTC after the controlled stop of 118b dg0 session 3 (167 chunks,
5.263 s median). Qualification verdict 0d3305d1a160 at 03:52:06: exact replay c0/c1/c2, xpu:2 display equal to the xpu:3 uncached
eager display, replica weight copy bitwise equal. Steady state (chunks ≥ 10, n = 28 so far): **period median 5.029 s** (118b dg0
tonight 5.263), cone on the chain 0.77 (0.98), upsample+B-prep 0.28 (0.28), receipt 0.10 (0.09), dual snapshots back to the
periodic 1/15, xpu:2 margin ≈ 5.4 GB above its 2 GiB floor with a 4 GiB transient budget (observed growth 3.2 GB per decode).
Byte identity vs 118b: images/last frame/preview **36/36**; `cone_equal` true on all. Work dir `/home/steve/ltx-stream/s120-live01`;
client `start-client-120.sh 121 1 cone 1 1 fingerprint 1.0 eager-display 0 full xpu:2`. Results note `experiments/ltx25-b70/notes/2026-10-10-continuation120-results-121.md` (100 periods: median 5.082, p10 4.81, p90 5.59; identity vs 118b 109/109). Next:
packet 121 (145/169-frame chunks) in CPU design, which with the xpu:3 headroom now freed is the route below 1.0 s/s with margin.

**2026-10-10, packet 121 sealed on CPU: 145 frames prepared; 169 held back by memory.**
Longer chunks spread the fixed work over more video. The receipts also show that
adding all earlier timing buckets would count some work twice. The safer first
comparison is 145 frames with the decoder graph off and display on xpu:3.
Predicted time is 5.55–6.10 seconds for six seconds of new video; this is not a
measured speed. The conservative 169-frame estimate crosses xpu:0's existing
memory floor, so that length stays disabled. The optional display copy on xpu:2
has a larger checked allowance at 145 frames, but its memory and exact output
remain unmeasured. CPU validation covers 461 recovery checks, 571 client checks
and 10 mocked preflight tests; corrected test modules were rerun in full. The
sealed packet has 1,980 verified files and no Python bytecode caches.
No GPU, launch, preflight, port, unit, signal, existing-run write or host change
was made. The coordinator's live-work records remain theirs.
[Design, memory estimates, packet and future launch](experiments/ltx25-b70/notes/2026-10-10-continuation121-stream-design.md).

**2026-10-10 03:30 UTC, Codex's 119 analysis corrects the attribution; packet 120 (display replica on xpu:2) sealed and queued for the next window; packet 121 (145/169-frame chunks) in design.**
The 119 loss is **near-floor safety work, not scheduling**: under dg1 the xpu:3 margin is low, so every request-after and
stage-B snapshot ran the dual walk (+0.08 s request-after, +0.15 s condition-B); the upsampler lives on xpu:0 and was never
slow; read-ahead runs post-commit on the decode thread, not in the HTTP handler (`notes/2026-10-10-continuation119-results-121.md`,
commit 7621aa805). Packet 120 (commit 33f30c17f, manifest `9af9330b…328e`, 426 recovery / 403 client / 10 preflight
CPU checks) adds a decoder-only display instance on xpu:2 (off by default, gated: cross-card display==cone byte check per
chunk, qualification against the xpu:3 uncached eager display, 4 GiB + 2 GiB floor admission on xpu:2) so the display
transient leaves xpu:3 and dg1 may regain its margin; predicted 5.10–5.40 s (central 5.22; adverse 5.35–5.70), read-ahead
dropped from the recommended arm. First launch `launch-120.sh 121 frame 1 cone 1 1 fingerprint 1.0 eager-display 0 full xpu:2`
is chained behind the controlled stop of the current 118b dg0 session at 60 chunks. Codex is designing packet 121: 145- and
169-frame chunks (fixed per-chunk costs ≈ 1.3 s amortise over more video; sampler time grew only 7.5 % from 97 to 121 frames).

**2026-10-10, packet 120 prepared on CPU; cross-card display remains off by default.**
The receipts correct the earlier suspicion: packet 119's extra receipt time came
from near-floor safety inspections. Read-ahead ran on the decode thread after
receipt commit, not inside the HTTP handler. The native upsampler stayed fast;
extra safety inspections also explain the larger B-preparation bucket. Packet 119
remains a loss against 118b dg0, despite matching all 37 compared chunks.
Packet 120 adds a separate display decoder on xpu:2, with full-frame comparisons
against xpu:3 during qualification and the existing per-chunk anchor byte check.
The proposed comparison turns read-ahead off and retains every safety inspection.
CPU validation covers 426 recovery tests, 403 client checks and 10 preflight tests;
one stale test assertion was corrected and its complete 23-test module reran.
Predicted period is 5.10–5.40 seconds at 121 frames, conditional on exact output
and recovered memory margin; an adverse result could be 5.35–5.70 seconds.
Cross-card bytes, peak memory and actual speed remain unmeasured. No GPU, launch,
port, unit, signal, existing-run write or host-setting action was taken. The
coordinator's recorded live line below is unchanged by this CPU task.
[119 analysis](experiments/ltx25-b70/notes/2026-10-10-continuation119-results-121.md)
and [120 design, seal and checks](experiments/ltx25-b70/notes/2026-10-10-continuation120-stream-design.md).

**2026-10-10 03:10 UTC, packet 119 (graph cone + eager display + read-ahead) measured: exact, but a loss; 118b dg0 relaunched.**
119 qualified (verdict 9dac6eb450ba) and streamed 61 chunks (02:56–03:09 UTC), byte-identical to 118b on 37/37 compared
chunks. Steady state (chunks ≥ 10, medians): period **5.42 s** vs 5.28 on 118b dg0; cone on the chain 0.79 (−0.19), but
upsample+B-prep 0.43 (+0.14) and receipt 0.18 (+0.09; the anchor read-ahead appears to read inside the receipt path);
text+A-prep unchanged at 0.50. Controlled stop 03:09:33, no fault; names archived; 118b dg0 (best line, 5.28 s = 1.047 s/s
tonight) relaunches at 03:14:38 UTC as `s118b-live03`. Codex is analysing the 119 receipts (xpu:3 timeline per
configuration) and building packet 120: display decode on a second decoder instance on xpu:2, read-ahead strictly
off the chain, and any ordering lever the timeline shows.

**2026-10-10 02:56 UTC, swap to packet 119 (graph cone + eager display + anchor read-ahead) at 121 frames.**
The second 118b dg0 session streamed 271 chunks (02:18–02:50 UTC, verdict 08301c03a083, period median 5.28 s, no fault,
no slip). Codex sealed 119 on CPU (commit 01aa9a790; manifest `d4b99d33…6890`; 375/375 recovery, 278/278 client, 10/10
preflight; design `notes/2026-10-10-continuation119-stream-design.md`). Its receipt analysis corrects the dg1 reading:
the +0.5 s sits in the native upsampler blocking on the shared device before stage B (display replay 2.12 s finishing
1 ms before condition-B starts), and a snapshot's 0.057 s is mostly CPU state/fact work (sync ≈ 0.9 ms), so the snapshot
option (lever C, off) is unlikely to pay. Levers: `LTX_DISPLAY_SCHEDULE=sampler-a|eager-display|sampler-b` (eager-display
= graph cone, uncached eager full display, per-chunk display==cone byte check kept), `LTX_ANCHOR_READ_AHEAD=0|1`
(verified cached anchor bytes, native reader on any miss), `LTX_SNAPSHOT_SCHEDULE=full|a-xpu3-sync` (off). Controlled
stop 02:50:54, names archived, fresh receipt `postflight-pre119-20261010T025118Z.json`, `--check-only` passed; launch
at 02:55:59 UTC: `launch-119.sh 121 frame 1 cone 1 1 fingerprint 1.0 eager-display 1 full`, predicted period
4.95–5.17 s (central 5.04 = real time). Client `start-client-119.sh 121 1 cone 1 1 fingerprint 1.0 eager-display 1 full`.

**2026-10-10, LTX119 built and sealed on CPU; ready for the coordinator's comparison.**
The packet can keep the faster anchor decode while running display decoding eagerly.
Verified anchor reading can run ahead too. The optional reduction in stage-A
synchronization stays off; its saving is uncertain and selecting it is an owner decision.
All 375 recovery tests, 278 client checks and 10 preflight tests passed. No GPU work,
launch, live-file write or host change was made. The predicted period is 4.95–5.17 seconds
at 121 frames; speed and full-model byte equality still need the coordinator's run.
[Design, sealed packet, checks and launch reference](experiments/ltx25-b70/notes/2026-10-10-continuation119-stream-design.md).

**2026-10-10 02:18 UTC, 118b dg1 cap-1.0 at 121 frames: exact but a loss (5.56 s vs 5.23 dg0); dg0 relaunched as the live line.**
The capped pool captured only `forward_pre_diffusion`, the floor held, cone decode fell 0.96 → 0.76 s, but the stage-B
bucket on xpu:3 rose 0.28 → 0.80 s (display-decode graph replay in front of stage B on the single compute queue, to be
verified). Note `experiments/ltx25-b70/notes/2026-10-10-continuation118b-results-121-dg1-cap1.md`. Controlled stop
02:12:41 UTC after 37 chunks, names archived, dg0 run dir renamed `.completed-20261010T0156Z`, fresh health receipt
`postflight-pre118b-dg0-relaunch-20261010T021306Z.json`, `--check-only` passed; the dg0 line (`… 121 frame 0 cone 1 1
fingerprint -`, 1.037 s/s) relaunches at 02:17:46 UTC. Codex is designing/building packet 119 on CPU from this evidence.

**2026-10-10 02:02 UTC, 118b dg0 session closed (1.037 s/s, byte-identical to 117 on 63/63); 118b launch 2 live: 121 frames, dg1, pool cap 1.0.**
The dg0 run streamed 101 chunks (01:38–01:56 UTC), cone exact 101/101, period median 5.227 s per 5.04 s chunk; its
timing split puts 0.20 s of the 0.50 s pre-sampler path in three on-chain four-card snapshots (0.059 s each in
fingerprint mode: the cost is the synchronize, not the walk), 0.12 s in anchor read + text window, 0.055 s in the stage-A
consume. Note `experiments/ltx25-b70/notes/2026-10-10-continuation118b-results-121-dg0.md`. Controlled stop 01:56:10,
names archived, fresh health receipt `postflight-pre118b-dg1-20261010T0157Z.json`, `--check-only` passed, launched
02:01:15 UTC: run `…-118b-frame-dg1-adcone-bo1-pa1-smfp-…-f121`, client `start-client-118b.sh 121 1 cone 1 1 fingerprint 1.0`
(work dir `s118b-dg1-live01`), sink/relay/preview attached; qualification in progress. Expected: cone decode on the chain
0.69 s under the graph vs 0.915 eager; if xpu:3 refuses the 9.66 GB floor it latches `precompute-118-refused.json` and the
dg0 line returns. The Flash-Next probes (admitted via `--owner-acceptance`) are blocked for the coordinator by the
permission classifier; they need the owner to run them or to approve explicitly.

**2026-10-10 01:47 UTC, one controlled swap 117 → 118b; 118b qualified and streaming at 121 frames (dg0, fingerprint snapshots).**
117 stopped cleanly at 01:33:24 UTC after 63 live chunks (client then server, one SIGINT each, no fault). In the five-minute
gap: fresh health probe passed (`postflight-pre118b-20261010T0134Z.json`); the 118b `--check-only` first failed with
"Runtime files/version differ" because `launch-118b.sh` called the venv as `bin/python3` while the runtime fingerprint pins
`bin/python` (one-line fix, commit 207df4d81), then passed. Launched 01:38:30 UTC, unit `ltx118b-stream-server-20261009`,
run `…-118b-frame-dg0-adcone-bo1-pa1-smfp-…-f121`; qualification verdict 6824dd4a6fae at 01:46:57 UTC: exact replay
c0/c1/c2 identical, every dual snapshot (fingerprint vs walk) agreed, no latch. Client `ltx118b-stream-client-20261009`
(work dir `/home/steve/ltx-stream/s118b-live01`), sink/relay/preview re-attached. Codex 118b rebuild: 299/299 recovery,
193/193 client, 10/10 preflight (commit f79cd9a2e; note `notes/2026-10-09-continuation118b-rebuild.md`). Codex also
landed the Flash-Next teardown patch (6813e2e05, 4a08bbfaf) and an explicit `--owner-acceptance` admission path for the
probe journal gate (d05cabc14; 346 CPU passes): earlier faults stay recorded, any fault at or after the acceptance time
still refuses. Preparation incident: a Codex test mock briefly opened `/dev/dri/renderD128` (card 43:00.0) and blocked in
`drm_read`; the process had exited by 01:48 UTC, no fault line, only the LTX server holds render nodes (VALIDATION.md
"Preparation incident"). The clean-exit / sleep-exit / first-forward probes are admitted on paper and wait for the next
controlled idle window.

**2026-10-10, Flash-Next admission reconciled with the owner's boot decision.**
The gate now accepts the exact saved decision only when explicitly requested.
It keeps earlier fault lines in the record and refuses every new fault. CPU
checks passed: 227 lane, 70 combined probe and 49 cleanup checks; the 35
first-forward checks also passed separately. Seven prohibited tests were skipped.
The three commands are prepared, not run. A faulty new test mock accidentally
opened a render device and blocked CPU test PID 899526; the owner was informed,
and permission to interrupt that PID is pending. No signal was sent. The mock
is fixed and the CPU runner now blocks device opens. LTX was not operated.
[Checks, incident and limits](experiments/qwen38-flash-next-fp8-b70/reopen-20261008/VALIDATION.md#owner-acceptance-admission-2026-10-10).

**2026-10-09, LTX 118b rebuilt and checked on CPU.**
The four review problems are fixed in a new sealed packet. All 299 recovery tests,
193 client checks and 10 preflight tests pass. Packet 118 is withdrawn and was never
launched. This rebuild did not touch live work or devices. The first future comparison
is 121 frames with the decoder graph off, matching 117's 5.40 seconds per chunk.
[Packet, checks and launch reference](experiments/ltx25-b70/notes/2026-10-09-continuation118b-rebuild.md).

**2026-10-10 01:20 UTC, halt resolved by the owner; LTX 117 at 121 frames launched as the live stream server.**
The owner archived `FAULT.json` and accepted continued launches on boot 4aafe57b ("accept"; receipt
`data/resume-20261008/fault-archive-20261010T011831Z-owner-accept-receipt.json`); no reboot. Fresh four-card health
probe passed (`postflight-owner-accept-20261010T0119Z.json`, 4 earlier fault lines, none during the probe). The completed
117 f121 dg0 run dir was renamed `.completed-20261009T0225Z` (receipt committed) and the same run relaunched after a
passing `--check-only`: unit `ltx117-stream-server-20261008`, 121 frames, frame anchor, dg0, cone/overlap/prep-ahead on.
Client `ltx117-stream-client-20261008` (work dir `/home/steve/ltx-stream/s117-live01`, 10 kitten scenes, 40 chunks per
cycle, unbounded) and sink `ltx117-stream-sink` → relay `ltx-relay` (forwarding to the owner's RTMP destination) →
LAN preview `ltx-mjpeg` on :8090 are running. **01:27 UTC: qualification passed** (verdict 508f2f2bac6a, exact replay c0/c1/c2 identical, 4 signatures per route, text window 64); first stream chunks at 01:27:30 UTC, sink playing with short holds (generation at 1.08 s/s is behind real time, as expected), relay forwarding to the owner's destination. In parallel on CPU: Codex rebuilds packet 118b from the BLOCK review and
applies the Flash-Next teardown patch to the overlay. Fault-halt rule unchanged for any further incident.

**2026-10-09, Flash-Next cleanup patch applied; three probes prepared on CPU.**
The reviewed patch now releases buffers in order and records each worker's cleanup.
CPU checks passed: 207 lane, 25 existing probe, 49 cleanup and 35 new one-layer
checks. Seven prohibited checks were skipped. The three receipt folders are
empty; the commands are prepared, not run. Native cleanup is still unproven.
The owner accepted continuing this boot without a reboot. No GPU work was done;
the coordinator owns later probes and keeps them behind LTX. The saved runs are
unchanged. The old watcher still refuses a boot with two incidents, so its
admission needs to be reconciled with that decision before any probe can run.
[Application checks and prepared commands](experiments/qwen38-flash-next-fp8-b70/reopen-20261008/VALIDATION.md#teardown-application-and-probe-preparation-2026-10-09).

**2026-10-09, LTX packet 118 CPU review: BLOCK before first launch.**
The snapshot comparison misses memory verdicts and can use the wrong chunk's check schedule.
The launcher can also retain an unwanted pool cap. An unapplied fix is prepared for a 118b rebuild;
sealed packet 118 is unchanged and the GPU fault halt remains in force.
[Independent review and fix](experiments/ltx25-b70/notes/2026-10-09-continuation118-review.md).

**2026-10-09, Flash-Next attempt 7 ordering reviewed on CPU; GPU halt unchanged.**
The first GPU fault came before the controller stop and all recorded crash reports.
Free memory stayed well above the stop threshold. The failing operation is still
unknown: the logs describe a write fault, and cannot exclude a native crash whose
report arrived late. A one-layer test is designed only, pending the owner's decision.
[Timeline, evidence and limits](experiments/qwen38-flash-next-fp8-b70/notes/2026-10-09-attempt7-ordering.md).

**2026-10-09, Flash-Next teardown patch prepared on CPU; GPU halt unchanged.**
The proposed cleanup patch is saved for review and has not been applied.
It releases owned buffers in order and waits for every worker before exit.
CPU checks: 207 lane tests passed (six prohibited tests skipped), 26 probe
checks and 49 new teardown checks passed. These do not prove native queue
cleanup or safe GPU operation. [Patch, limits and review](experiments/qwen38-flash-next-fp8-b70/reopen-20261008/overlay-fix-teardown/README.md).

**2026-10-09, Flash-Next CPU-only exit review: GPU launches remain halted.**
The host-driver probe also returned correct bytes and then faulted as its worker
exited. That is the second incident on this boot; the owner's decision is still
needed. Changing the driver version did not separate the outcomes. The two tiny
probes point to shutdown, but the older load faults do not prove the same cause:
Screen 1 faulted before its OOM kills, and attempt 7's crash ordering is uncertain.
A normal-exit variant and a delayed abrupt-exit variant are prepared, with 26 CPU
tests passing. Neither ran. The production overlay is unchanged. This supersedes
the earlier proposed host-driver comparison and “while idling” description below.
[Evidence and prepared tests](experiments/qwen38-flash-next-fp8-b70/notes/2026-10-09-exit-lifecycle-analysis.md).

Latest four-card review: **2026-10-07, LTX optimization resumed by the owner**. The dated two-card entries
below remain that host's own research record; this consolidation did not operate it.

## Four-card host now: LTX speed and reliability, unchanged quality

**2026-10-09 04:10 UTC tick:** Codex's attempt-7 ordering note (`notes/2026-10-09-attempt7-ordering.md`, commit
1e68b46b4): the first CCS fault preceded the controller's SIGINT completion by 744 ms and the crash reports by ~18 s, with
46.6 GiB host free, so attempt 7 was **not** an abrupt-exit fault; the recorded fault is a *write* fault on card 47, which
does not establish a host-expert read failure, and the exact cause stays unresolved by the saved logs. A one-layer
single-rank first-forward test with production-size pinned slabs under the teardown patch is designed, not run. Halt holds
(boot 4aafe57b, 4 fault-class lines). Packet 118 sealed and waiting; nothing running on the cards.

**2026-10-09 03:35 UTC tick:** Codex's graceful-teardown overlay patch is prepared and reviewed, **unapplied**
(`reopen-20261008/overlay-fix-teardown/`, commit 8aee5f711; 207 lane + 26 probe + 49 teardown CPU tests pass; handoff
`notes/2026-10-09-teardown-patch-prep.md`). It orders per-rank release (drain, pinned slabs/PLE/tables, synchronize,
pools) before any exit and routes SIGINT/SIGTERM through the same path; OOM/SIGKILL cannot be made graceful and stay
prevented by the loading RAM guard. Halt holds (boot 4aafe57b, 4 fault-class lines, all from the two probes). Packet 118
build still in progress. Next CPU step started: Codex re-reads attempt 7's ordering (the one incident that does not fit
abrupt exit).

**2026-10-09 03:00 UTC tick (halt holds; CPU work continues).** Codex's exit-lifecycle analysis
(`experiments/qwen38-flash-next-fp8-b70/notes/2026-10-09-exit-lifecycle-analysis.md`, commit 929ba2897): the two
probe faults fit a closed-VM fault response (upstream v7.0 `xe_pagefault_service` returns `-ENOENT` for a VM
already marked closed) raised while NEO's direct-submission ring is still active when `_exit` bypasses native
finalization; medium confidence (distro xe source unverified, ring activity unmeasured). Screen 1 faulted before its
OOM kills and attempt 7's ordering is unresolved, so "abrupt exit" is strongly supported for the probes but not proven
for all four incidents. Prepared, not run: `--clean-exit` and `--exit-after-sleep N` probe variants with a preregistered
interpretation table (26 CPU tests). Started next: Codex implements the graceful-teardown overlay patch (unapplied, CPU
tests). Packet 118 built and sealed (not launched): `prepared-continuation-stream-118`, manifest `cb68515a…3f482f6`, 289/289 CPU tests; first launch `recovery/20261009-continuation118-stream/launch-118.sh 97 frame 1 cone 1 1 fingerprint - <fresh receipt>` after its `--check-only` (LAUNCH.md).

**2026-10-09 02:35 UTC, HALT: second GPU fault incident of boot 4aafe57b; owner decision needed (reboot, or accept continuing LTX on this boot).**
The slab probe with the host user-mode driver overlaid into the vLLM image (remedy A) reproduced the first probe
exactly: gather byte-correct, then at the worker's `os._exit` card 23:00.0 logged `-ENOENT` + bcs engine reset
(0.4 ms before the guardian's post-exit timestamp, both times). Driver version cleared; MoE addressing cleared;
what remains is **abrupt process exit with live USM host mappings** (the 14:04 OOM-kill incident fits; the LTX
venv's graceful exits never fault). `FAULT.json` set; post-fault health probe passed on all four cards. Notes
`experiments/qwen38-flash-next-fp8-b70/notes/2026-10-09-slab-probe-hostumd-result.md`. Continuing on CPU:
Codex prepares the `--clean-exit` probe variant and the exit-lifecycle analysis; an Opus agent builds LTX packet
118 (timing split of `submit_to_sampler_start`, fingerprint four-card snapshots proven against the walk, bounded
decoder-graph pool for 121 dg1). LTX 117 at 121 frames stands at **1.08 s/s** (5.40 s per 5.04 s chunk).

**2026-10-09 02:15 UTC, Flash-Next: the slab probe cleared the MoE addressing and pointed at the image runtime; LTX 117 at 121 frames streaming (dg0).**
In the idle gap after the 97-frame run, the Codex-prepared single-card slab probe ran in the vLLM 0.30.0 image on
card 23:00.0: the production table-only indirect gather from an exact-size pinned host slab was **byte-correct**,
then about one second later, while the process idled, the card logged `-ENOENT` and a **bcs (blitter) engine
reset** at an unmapped device address. First fault incident of boot 4aafe57b; the bounded health probe passed;
the direct-pointer variant was not run (it could discriminate nothing). All three faults of this lineage are inside
the image; the LTX venv ran the same cards for a day without one. Codex's runtime comparison
(`notes/2026-10-09-runtime-comparison.md`): the image's NEO 26.27.39122 / IGC 2.38.2 / L0 1.32.0 are **newer**
than the host's 26.18.38308 / 2.34.4 / 1.28.2 that the LTX venv loads; remedy A = bind-mount the host user-mode
driver into the container (CPU ABI check passed, `probe/remedy-a-abi-check-20261009.json`); the probe printer is
gaining an opt-in `--host-umd-overlay`. Next GPU step: the same probe with the host driver, one card, in the next
idle window, same stop rule. LTX: 117 at 121 frames with the decoder graph latched on the xpu:3 floor (9.59 GB vs
9.66 floor, predicted in LAUNCH.md §4; latch archived with a review receipt); the preregistered dg0 fallback
qualified 3/3 exact: **5.40 s per 5.04 s chunk = 1.08 s of work per second of video** (97 f: 1.19; 116b: 1.37), cone exact on 100/100 chunks, floors wide (xpu:3 15.6 GB before decodes). Note `experiments/ltx25-b70/notes/2026-10-09-continuation117-results-121.md`. Sampler A+B are 64 % of the period; `submit_to_sampler_start` (0.52 s, unexplained by the precompute waits) is the next cheapest lever.

**2026-10-09, Flash-Next CPU-only runtime review:** the faulting image uses newer GPU drivers
than LTX, but older Torch and SYCL libraries. All twelve local alternative images keep the
same driver versions. The host libraries pass dependency checks inside the image; a later
single-card comparison is designed but was not run. The old 14:04 fault happened before
the OOM kills, while the tiny probe fault coincided with its GPU worker exiting. These are
not three proven instances of the same teardown bug. LTX remains protected; no GPU work
or host changes were made. [Runtime comparison and unexecuted remedy designs](experiments/qwen38-flash-next-fp8-b70/notes/2026-10-09-runtime-comparison.md).

**2026-10-09 01:30 UTC, resumed after the owner reboot; packet 117 at 97 frames is the new best sharp coherent chain.**
Boot 4aafe57b verified (kernel 7.0.0-39, memory blocks 53–57 offline, lockup panics off, zero xe fault lines);
stale `FAULT.json` archived with a receipt; fresh four-card receipt `postflight-reboot-20261008T2101Z.json`.
Packet 117 (cone anchor decode + stage-B encode overlap + prep-ahead on the frame anchor with the decoder graph)
qualified 3/3 exact, eager chain equal to the 114 reference, and 62/62 stream chunks byte-identical to 116b:
**4.82 s per 4.04 s chunk (1.19 s/s; 116b 5.54, 1.37 s/s)**, cone decode 0.69 s on the chain vs 1.57 full,
`cone_equal` true on all 100 measured chunks, floors kept. Target ≤4.4 s missed: `submit_to_sampler_start`
stayed at 0.51 s. Note `experiments/ltx25-b70/notes/2026-10-09-continuation117-results-97.md`. Controlled stop
01:27:22 UTC. Next: the Flash-Next single-rank slab probe (Codex-prepared, 237 CPU tests) in the idle window,
then packet 117 at 121 frames.

**2026-10-08, Flash-Next attempt 7 prepared on CPU:** large pinned buffers
now request their exact sizes through the runtime's allocator setting. This
removes about **24.25 GB of padding** without changing the stored model bytes.
The estimate is **76.37 GB steadily** and **76.64 GB during loading**, or
**78.79 GB** with extra room for later work. The current row placement and
4 GiB PLE cache stay in place; moving rows back to cards 1–3 is unnecessary
in this budget. A **96 GB load-only guard** is prepared; the watchdog and
answer-generation gates are unchanged. All 213 CPU tests pass. Native fit and output checks still
need measurement. Nothing was launched or committed; LTX and port 8188 were
untouched. [Budget, CPU checks and prepared command](experiments/qwen38-flash-next-fp8-b70/reopen-20261008/ATTEMPT7-BUDGET.md).

**2026-10-08, Flash-Next attempt 6 checked on CPU:** the host buffers are
larger than their tensor sizes because the allocator rounds each one up.
The saved samples match that explanation. Completing the current placement
is estimated to use **100.6 GB steadily**, or **100.9 GB with staging**.
That is above the 97 GB target, so a 96 GB retry is not prepared and the
watchdog stays unchanged. Moving 62/64/62 unchanged expert rows back to
cards 1–3 could save **6.74 GB of host RAM** for **0.92 GB more card memory**;
this is a proposal, not a measured fit. The old shadow-removal explanation
and 78 GB forecast are withdrawn. Nothing was launched or committed; LTX
and port 8188 were untouched.
[Evidence, corrected planner and lossless options](experiments/qwen38-flash-next-fp8-b70/reopen-20261008/ATTEMPT7-BUDGET.md).


**2026-10-08, Flash-Next attempt 6 prepared on CPU:** more unchanged expert
rows now live in host memory, with 2,600 rows on each rank. The startup
utilization is 0.90. The estimate is **77.955 GB host pressure** and
**23.334 GiB engine memory per card**. Counting memory already unavailable
at startup leaves **1.281 GiB below the 90% line** on the tightest card.
Graph and workspace costs remain estimates, so the load measurement and
quality checks are still required. All 193 CPU tests and four rank rehearsals
pass. All existing safety gates stay in place.
Nothing was launched or committed; LTX, host settings and port 8188 were untouched.
[Source evidence, CPU checks and the prepared command](experiments/qwen38-flash-next-fp8-b70/reopen-20261008/ATTEMPT6.md).



**2026-10-08, Flash-Next attempt 5 prepared on CPU:** attempt 4's saved launch
omitted the driver settings that LTX already uses. Its memory samples show
74.063 GB held by the GPU driver at the 90.013 GB host-pressure peak; that
memory rose during construction and went away when the workers drained.
All Screen 1b modes now set the two per-process driver variables. The revised
estimate is **35.505 GB**, not a measured fit. The old 115.87 GB certified
observation stays intact; it is not an irreducible host-buffer requirement.
All **185 CPU tests pass**, and every admission and quality gate remains.
Attempt 5 needs its own fresh health receipt and exclusive launch window.
Nothing was launched or committed; host settings, LTX and port 8188 were untouched.
[Evidence, prediction and command](experiments/qwen38-flash-next-fp8-b70/reopen-20261008/VALIDATION.md#attempt-5-per-process-driver-backing-cpu-only-preparation).


**2026-10-08, Flash-Next calibration loading guard adjusted on CPU:** the
load-only measurement now allows up to 90 GB of host memory in use, through
an explicit launch parameter recorded in its receipts. It no longer stops at
the old 80 GB / 32 GiB line. The watchdog still sends SIGINT below 24 GiB
available, and MTP1 still needs a measured plateau plus 15% within 90 GB.
All 179 CPU tests pass. Memory fit remains unproven; attempt 4 is prepared
with a placeholder health receipt and was not launched. No commits or runtime
operations were made; LTX and port 8188 were untouched.
[Change and CPU validation](experiments/qwen38-flash-next-fp8-b70/reopen-20261008/VALIDATION.md#attempt-4-calibration-loading-threshold).


**2026-10-08, Flash-Next attempt 3 reviewed on CPU:** the first stop came
from rank 1 when host memory in use crossed 80 GB. Rank 0 then noticed the
same stop while building its expert map; the map was not broken. Errors now
retain the original cause. The stronger rehearsal checks the real maps and
certified placement on all four ranks and reproduces the memory stop. All
171 CPU tests pass. Measured use rose from 5.695 GB after hashing to 80.006 GB
partway through construction; the 87.765 GB full-load estimate is still
unproven. Memory fit remains open. The prepared fourth-attempt command is
only a diagnostic retry and may hit the same guard. Nothing was launched or
committed, and LTX was untouched.
[Evidence, memory curve and next command](experiments/qwen38-flash-next-fp8-b70/reopen-20261008/VALIDATION.md#calibrate-load-attempt-3-memory-guard-cancellation).


**2026-10-08, Flash-Next attempt 2 fixed on CPU:** startup stopped because the
loader counted a conversion on the card as temporary host memory. Available
host RAM stayed above 95 GB. The guard now distinguishes those operations;
the stronger CPU rehearsal also found and fixed the same mistake for metadata
that has no stored payload. All 163 CPU tests pass, including real model and
loader construction for four simulated ranks. This does not establish GPU
startup, memory fit or output quality. Nothing was launched. Attempt 3 is
prepared and needs a fresh health receipt from the owner.
[Cause, rehearsal limits and command](experiments/qwen38-flash-next-fp8-b70/reopen-20261008/VALIDATION.md#calibrate-load-attempt-2-worker-init-failure).



**2026-10-08, Flash-Next calibration failure fixed on CPU:** the first mmap
load attempt exited during worker startup. The loader counted the same copy
twice, broke it into thousands of tiny copies, and made waiting workers time
out. Available host RAM stayed near or above 107 GB. The copy guard is fixed;
all 149 CPU tests pass, including a test that reproduces the failure.
No new launch occurred. The next attempt needs a fresh result directory and
uses the passing postflight started at 17:14:58 UTC.
[Cause, tests and next command](experiments/qwen38-flash-next-fp8-b70/reopen-20261008/VALIDATION.md#calibrate-load-attempt-1-worker-init-failure).


**2026-10-08, Flash-Next CPU-only memory adapter:** the unchanged FP8 PLE rows
can now be read from their original files with a 4 GiB total pinned row cache.
Loading has a shared staging cap and per-rank memory receipts. All 126 CPU
tests pass, including small checks against the real checkpoint. The revised
host-memory estimate is **87.765 GB**, not a measured fit. Existing host and
card-memory guards still apply; reading missed rows will add decode latency.
Nothing was launched and LTX was not touched. The next runtime step needs its
own exclusive launch window and load measurement; exact output checks remain
open. [Implementation, command and risks](experiments/qwen38-flash-next-fp8-b70/reopen-20261008/README.md).


**2026-10-08, Flash-Next CPU-only calibration follow-up:** the rescued A367
supervisor trace was found: available RAM fell by **115.87 GB**, so the old
run does not demonstrate a 90 GB fit. Worker RSS and complete live card-memory
peaks are still missing. A load-only measurement mode is now prepared: no
answers generated, half-second memory checks, a 20-second ready plateau, then
one graceful stop. It bypasses the missing prediction only for measurement;
MTP1 needs a passing receipt. Nothing was launched, no credentials were read,
and this work did not touch the LTX service or its port. The owner-approved
sequence and remaining admission checks are in the
[Screen 1b README](experiments/qwen38-flash-next-fp8-b70/reopen-20261008/README.md).


**Live update, 2026-10-08 01:00 UTC (10-07 evening local):** the owner set two
priorities: Flash-Next is not given up (re-open against the matured ecosystem;
"stratra" = Strata, a 1-bit IQ1_M engine at 70–78 tok/s on one B70, not a
lossless comparison; the relevant external work is Lumnus/b70-flash-next on
vLLM v0.30.0 + xpu-kernels 0.1.14.1 with 3-draft MTP at 87.9 tok/s on W4A16,
no FP8 numbers), and LTX must produce a **live RTMP/WHIP stream** (Twitch or
meshcast.io) of continuously generated video, 24/7 as the goal; the owner has
not yet seen any video from this lane. Continuation 111 **passed**: eight of
eight requests verified, three exact four-tensor replay pairs across two
three-chunk chains at 640×384, 145 unique frames per chain; native eager
chunks took 15–24 s each (2–3 fps, reference only, no speed claim, seams and
audio alignment unreviewed). 111 stopped once with SIGINT at 00:54:03 UTC;
four-card postflight passed 00:54:58 UTC, zero fault lines this boot.
[Results](experiments/ltx25-b70/notes/2026-10-08-continuation111-results.md),
[stop receipt](experiments/ltx25-b70/data/resume-20261007/continuation111-stop.json).

**21:45 UTC: packet 117 built and sealed (not launched; blocked by the fault marker).** Four exact levers on the frame-anchor chain, each launch-selectable and byte-gated: cone-restricted anchor decode (same calls and row counts as the full decode for the last frame's dependency cone, other rows zero-filled; 34% of the attention tiles at 97 frames; per-chunk byte check against the full display decode), stage-B encode beside stage A with an xpu:3-only snapshot that keeps checks P1–P8, 121-frame chunks, and prep-ahead of the stage-A encode on the decode thread. 249/249 new tests; manifest `5826174e…`; `--check-only` passes everything up to the fault-marker refusal. Predicted: 4.35–4.9 s per 4.04 s chunk at 97 frames (1.08–1.21 s/s), 1.03–1.15 s/s at 121; the next fixed cost is the six four-card safety snapshots per chunk (0.3–0.5 s), an owner-level safety question. Recommended first launch after the owner's reboot decision: 97 frames, frame, dg1, cone/overlap/prep-ahead on; then 121; then a 97 full/0/0 control. [Design](experiments/ltx25-b70/notes/2026-10-08-continuation117-stream-design.md).

**21:16 UTC:** the attempt-7 container exited (code 1) at 21:13:16 UTC after the controller's single SIGINT; no process holds a render node; the fault burst lasted one minute (21:11:18–21:12) and no fault line has appeared since. One bounded four-card probe at 21:14:24 UTC **passed on all four cards** (`runs/…attempt7/postflight-after-fault.json`): the cards respond, but under the standing rule the second incident on this boot still halts launches until the owner decides on a reboot. CPU-only work continues (packet 117 build; Codex root-cause analysis of the fault in `notes/2026-10-08-attempt7-gpu-fault-analysis.md`).

**21:15 UTC: SECOND GPU FAULT INCIDENT OF THIS BOOT — launches halted; owner decision needed.** Attempt 7 (exact-size pinned slabs) loaded the model on all four ranks (`Model loading took 20.87 GiB`, 490–522 s; host pressure peaked ≈76 GB as predicted), then at **21:11:18 UTC all four cards** (0000:23/27/43/47:00.0) logged `Fault response: Unsuccessful -ENOENT`, `Engine memory CAT error class=ccs`, engine resets and device coredumps — 222 kernel lines in one minute — as the first forward/warm-up touched the weights. Most likely cause: the new slab sub-views give the UVA/expert kernels host pointers that are not GPU-mapped the way separate pinned allocations were (GPU page faults on first access); to be confirmed from the server log. The controller sent its single graceful stop; the container is winding down. Per the owner's standing rule this is the second incident on boot `10192010…` (first: the 14:04 UTC OOM teardown), so **no further launches on this boot**; `FAULT.json` written at the LTX results root so the LTX launchers refuse too; a reboot is the owner's call. Evidence: `runs/screen1b-mmap-calibrate-load-20261008-attempt7/` incl. `kernel-fault-window-20261008T2111Z.log`.

**21:05 UTC: attempt 7 running** (unit `flashnext-screen1-20261008T165744`): exact-size pinned slabs for the offloaded rows (213 CPU tests; predicted steady pressure 76.4 GB, loading 76.6 GB, no row move needed), loading guard 96 GB, watchdog at 24 GiB free, fresh probe `runs/postflight-pre-attempt7.json`. Packet 117 still building on CPU.

**21:00 UTC: the decisive host-memory term is allocator rounding.** Codex's phase-by-phase read of attempts 4–6 (`reopen-20261008/ATTEMPT7-BUDGET.md`): `GPUActive` here counts pinned host pages held for GPU objects (the offloaded expert rows), and those rows — 51.1 GB of tensors — occupy **74.5 GB** because PyTorch's caching host allocator rounds each separate allocation up to a power of two; attempt 6's samples track the rounded sizes. Projected steady pressure with the unchanged placement is 100.6 GB (above the 97 GB watchdog line), so no threshold-only attempt 7. The lossless fix is exact-size pinned slabs for the rows (same bytes, same row mapping; Lumnus 0002/0006 is prior art), expected to recover ≈23 GB and bring the steady footprint well under 90 GB; Codex is implementing it with CPU exactness tests. Attempt 7 follows that.

**20:40 UTC: correction — attempt 6 disproves my shadow claim.** With `NEOReadDebugKeys=1 EnableDeferBacking=0` set (verified in both launch.json files), attempt 6 still reached GPUActive 73.1 GB and 90.1 GB of host pressure during loading before the 90 GB guard cancelled it (MemAvailable min 34.1 GB; no OOM, no fault). Attempt 5's 1.4 GB GPUActive only meant it died at device init before the weights loaded. So on this stack `GPUActive` is most likely the pinned host-resident expert rows that the offload design places in host RAM on purpose (≈16 GiB per rank), not a shadow of device memory; the 19:40 UTC entry's conclusion is withdrawn. The real budget: ≥70 GB of weights must live in host RAM because four cards give only ≈110 GiB usable VRAM for 185 GB of weights, plus workers (≈11 GB) and the 4 GiB PLE cache — a plateau near 85–92 GB on a 121 GB host. Codex is re-interpreting the counter from the attempt 4–6 samples and sizing one plateau measurement (loading guard raised, watchdog kept as the hard stop) before any MTP1 run.

**20:04 UTC: attempt 6 running** (unit `flashnext-screen1-20261008T160407`): utilization 0.90, more expert rows in pinned host memory (predicted engine peak 23.3 GiB per rank, 1.3–1.5 GiB below the line; predicted host peak 78 GB with the shadow gone), fresh probe `runs/postflight-pre-attempt6.json`. Packet 117 (LTX: cone anchor decode, stage-B encode overlap, 121-frame chunks, prep-ahead) is being built on CPU in parallel.

**19:50 UTC: attempt 5 confirms the fix and moves the problem to VRAM.** With `NEOReadDebugKeys=1 EnableDeferBacking=0` in the container: GPUActive peak **1.4 GB** (was 74), MemAvailable min 111.9 GB, loading pressure 12.2 GB — host RAM is no longer the Flash-Next constraint. It then failed in vLLM's startup check: xpu:0 reports 27.65 of 30.3 GiB free (others 27.87) against the requested utilization 0.92 = 27.87 GiB; and the v5 placement's resident weights (≈29.5 GiB per rank) never fit at that free level. With ≈100 GB of host RAM now free, more expert rows can live in pinned host memory; Codex is producing the per-rank VRAM budget under utilization 0.90 and the matching offload. No fault, no OOM; probe clean.

**19:40 UTC: confirmed from the attempt-4 samples — `GPUActive` in /proc/meminfo reached 74.1 GB during the load** (AnonPages only 10.6 GB, page cache shrinking from 84 to 56 GB as it was evicted): the host "pressure" is the driver's deferred-backing shadow of the four ranks' device allocations, exactly the mechanism the LTX lane measured on 2026-10-04 (`notes/2026-10-04-host-ram-shadow-of-vram.md`: shadow 92.6 GiB → 0.3 GiB with `NEOReadDebugKeys=1 EnableDeferBacking=0`, outputs identical, copies still direct). Neither the certified Flash-Next lane, Lumnus, nor Screen 1 set it, so the certified line's ≈116 GB host use was mostly shadow. With the setting, the Flash-Next footprint should fall by ≈70 GB and fit this host with margin, without any change to model bytes or arithmetic. Codex is adding it to the container environment; attempt 5 follows.

**19:30 UTC: attempt 4 measured the load: host pressure reached 90 GB before readiness; guard stopped it cleanly (no OOM, no fault).** MemAvailable min 34.2 GB, Committed_AS 130.7 GB, yet worker RSS peaks only ≈2.8 GB each and the container cgroup 11.5 GB: ≈75 GB of the pressure is outside the workers' RSS. That is the signature of the NEO driver's deferred backing on this host (every device allocation in a multi-card process is mirrored in host RAM unless the process sets `NEOReadDebugKeys=1 EnableDeferBacking=0`; the LTX lane measured and fixed it on 2026-10-04). Four ranks × ≈29.5 GiB of device allocations ≈ 118 GB of shadow, which would also explain the certified line's ≈116 GB. Codex is adding the per-process driver setting to the container and re-predicting; if confirmed, Flash-Next fits with margin and the PLE/placement port was fighting the wrong number. Evidence in `runs/screen1b-mmap-calibrate-load-20261008-attempt4/`.

**18:58 UTC: Flash-Next calibrate-load attempt 4 running** (unit `flashnext-screen1-20261008T144209`, loading RAM guard aligned to 90 GB, watchdog SIGINT at 24 GiB free, receipt `postflight-stream116b.json`). Attempt 3's cancellation was the overlay's own 80 GB loading guard with 44.7 GB still free, not a host limit. Zero generation requests; the goal is the measured load plateau.

**18:50 UTC: 116b measured — captured decoder exact but only 9% faster; sharp 97-frame chain stands at 1.37 s/s.** Over ~60 chunks: cadence ≈5.5 s per 4.04 s chunk; stage costs text+A-prep 0.52, sampler A 1.62, upsample+B-prep 0.31, sampler B 1.20, **video decode on the chain 1.57 s (eager was 1.72)**, handoff 0.03, receipt 0.12; decode tail 0.92 and preview 0.49 off-chain; seams 0.87–0.96 (identical to the baseline bytes); zero faults; router route `axis-router-original` recorded. The decode is compute-bound at 97 frames, not dispatch-bound as the 45–60% overhead assumption supposed, so graph replay buys little. Standing results for one coherent 256² chain with sharp seams: **1.37 s of work per second of video at 4-second chunks** (5.98 → 5.74 → 5.50 s today), ≈2.15 s/s at 2-second chunks; the soft-seam latent modes reach 0.83 s/s but are not adopted. Remaining exact levers, each small: cone-restricted anchor decode (≈−0.5 s at 97, exactness unverified), stage-B encode overlap via a guard redesign (≈−0.25), 121-frame chunks (amortisation), prep/encode-ahead (≈−0.3); together they estimate ≈1.0–1.1 s/s. The owner's resolution goal (≥640×384) multiplies every term ≈3×. 116b is the best qualified sharp chain to date; server stopped once after the measurement for the Flash-Next calibration window.

**18:35 UTC: packet 116b qualified exact WITH the captured decoder.** Launched 18:21 UTC (97 frames, frame anchor, `LTX_DECODER_GRAPH=1`, manifest `06688f41…`). Gate: eager chain vs graph-replay chain vs repeat all byte-identical; the graph chain's decode ran twice (uncached eager first, then the captured decoder with the bounded RoPE/mask/noise caches) and matched byte for byte; no refusal latch written; the eager chain equals the 114 frame reference. First chunk: submit→anchor 4.78 s (text+A-prep 0.45, sampler A 1.54, sampler B 1.11, video decode 1.60 on the chain, handoff 0.02, receipt 0.08), decode tail 0.76 and preview 0.45 off-chain. Cadence over ~60 chunks being measured. Receipts `postflight-pre116b-frame-f97.json`, `continuation116b-frame-dg1-f97-storage-admission.json`.

**18:20 UTC: Flash-Next calibrate-load attempts 2 and 3 failed at worker init (no fault, no OOM); 116b launching.** Attempt 2 (17:21 UTC): TP0's device-only RoPE conversion was mis-charged as host staging and cancelled the load (fixed; a CPU rehearsal of all four ranks' model construction now exists, 163 tests). Attempt 3 (18:09 UTC), corrected after full receipt review: rank 1's internal allocation guard stopped construction at 80.006 GB of host pressure; rank 0 observed that cancellation in `determine_expert_map`. The half-second sampler peaked at 79.478 GB (MemAvailable 44.701 GB). The CPU fix preserves the first cause and explicitly tests all four maps; memory fit remains open. The external watchdog did not act; kernel log clean (local-time windows). **Packet 116b** (decoder-graph guard accepts the pinned axis router, 198/198 tests, manifest `06688f41…`) is launching at 97 frames, frame anchor, decoder graph on; 116's receipts show the chain wait is the video decode itself (1.72 s at 97), so the graph is the lever (predicted 4.7–5.0 s per 4.04 s chunk).

**18:05 UTC: 116 scheduling-only arm measured (decoder graph off, frame anchor, 97 frames):** exact gate pass (eager chain equal to the 114 frame reference); **5.74 s per 4.04 s chunk (1.42 s/s)** vs the 5.98 s baseline; seams identical to the baseline (0.87–0.96). Stage costs: text+A-prep 0.53, sampler A 1.63, upsample+B-prep 0.29, sampler B 1.19, decode in-chain 2.67, anchor handoff still 1.76 (the chain is not yet waiting only for the video decode as designed; the 116b builder is checking the receipts), preview 0.50 off-chain. So the scheduling change alone buys ~0.25 s; the decoder graph (116b, router-aware guard) is the lever that matters. Server stopped once after the measurement; postflight pass.

**17:45 UTC: packet 116 built and launched; refused itself at `prepare` (software, no fault).** 116 = frame anchor at both stages, the chain waiting only for the video decode (audio, hashing, record and preview behind it), and a decoder graph capture with bounded RoPE/mask/noise caches behind a byte-identity gate (`LTX_DECODER_GRAPH=1`), `stream116-` names; 195/195 new CPU tests; manifest `6bced5b4…`. Launched 17:31 UTC at 97 frames with the decoder graph on; the window probe passed, then the decoder-graph installer required `na3d` on xpu:3 to dispatch directly to the pinned eager backend, but the live runtime routes it through the lab's `ltx_na_axis_router.AxisRouter` (`integration.py:1113`), so it refused before any capture and the server latched. Kernel log clean (local-time window); server stopped once at 17:45 UTC; postflight pass; run dir kept as `…-f97.refused-20261008T1742Z`. Fix: accept the router when it resolves to the pinned eager module (and pin the router), re-seal as 116b. Flash-Next calibrate-load attempt 2 also failed at worker init (`create_model`, MemAvailable ≥95 GB, not memory); Codex is building a CPU worker-init rehearsal so the port stops iterating by live crash. Receipts `stream116-dg1-f97-stop.json`, `postflight-stream116-refused.json`.

**16:45 UTC: sharp-seam baseline at 97 frames measured (114, `LTX_ANCHOR=frame`, text reuse):** exact gate pass; **5.98 s per 4.04 s chunk (1.48 s/s)** with seams at 0.87–0.96 relative sharpness (none below 85%). Stage costs: text+A-prep 0.50, sampler A 1.62, upsample+B-prep 0.28, sampler B 1.19, decode in-chain 2.01, anchor handoff 2.15 (includes waiting for the decode thread's post-work: audio, hashing, record), preview 0.94 off-chain. This is what packet 116 must beat with sharp seams: the tail-decode idea is not exact (the LTX-2.5 decoder is a non-causal neighbourhood-attention diffusion decoder; every latent frame feeds the last pixel frame; row counts change rounding), so 116 = scheduling (chain waits only for the video decode; audio/hash/record/preview behind it) + decoder graph capture with bounded RoPE/mask/noise caches (owner-authorized experiment, byte-identity gated) + optional stage-B encode overlap. Predicted 116a ≈4.9 s at 97 (1.2 s/s); with decoder capture lower. [Design](experiments/ltx25-b70/notes/2026-10-08-continuation-tail-decode-design.md). Process slip to record: this 114 frame-mode launch went out about one minute after the previous stop instead of the lane's five-minute gap (probe had passed; no harm observed); the gap is restored in the launch scripts from here on.

**16:35 UTC: the softness is not a model fade-in.** Seven unanchored text-to-video first chunks (stream_seq 0 and qualification chunk 0 across the 112–115 runs) are sharp from frame 0 (relative sharpness 1.07–1.26 over frames 0–12), so the start-of-chunk softness is caused specifically by latent-side conditioning. Guide run stopped once at 16:22:29 UTC (154 chunks, exact); postflight pass. No server running. Receipts `stream115-guide49-stop.json`, `postflight-stream115-guide.json`. The tail-decode design for packet 116 is in progress.

**16:30 UTC: guide mode measured — exact, 2.94 s per 2.04 s chunk (1.44 s/s), seams as soft as the other latent modes.** Sharpness over 20 chunks: frames 0–11 at 0.54–0.85 of mid-chunk (0.67, 0.54, 0.57, 0.57, 0.65, 0.68, 0.71, 0.72, 0.77, 0.73, 0.77, 0.78), end of chunk 1.0–1.08. Guide tokens also cost sampler A 1.60 vs 1.35 s. **Conclusion across 114/115:** every latent-side conditioning (slot-0 latent, mixed, guide) leaves the first ~12 frames soft; only the decoded-frame anchor at both stages (113) is sharp, and it puts the full VAE decode on the chain. **Packet 116 idea:** keep the frame anchor at both stages, but obtain the anchor by decoding only the tail of the previous chunk (the causal VAE should reproduce its last frame from a short causal context; the gate checks byte-identity against the full decode's last frame), while the full decode for display runs off-chain. Estimated: ≈2.75 s per 2 s chunk at 49 frames and ≈3.5 s per 4 s at 97 (≈0.87 s/s) with 113-grade seams. Design starting.

**16:15 UTC: 115 `guide` mode qualified exact (3/3) and is streaming at 49 frames** (relaunched 16:07 UTC after archiving the mixed run's outputs to `output/archive-stream115-run01-mixed49/`; `LTXVAddLatentGuide` with the previous two latents per stage as guide tokens, 144/576 tokens at 49 frames, four signatures per route). First anchored chunk: submit→anchor 2.62 s (text+A-prep 0.10, sampler A 1.59, sampler B 0.89), decode 1.50 s off-chain. Guide chunks deliver all 49 frames (no overlap frame to drop). Cadence and seam sharpness over ~120 chunks being measured.

**16:10 UTC: mixed anchor measured — exact and 2.94 s per 2.04 s chunk (1.44 s/s), but the seam softness is NOT fixed.** Sharpness over 20 chunks: frames 0–11 at 0.54–0.85 of mid-chunk (0.74, 0.54, 0.58, 0.60, 0.66, 0.76, 0.81, 0.82, 0.82, 0.76, 0.79, 0.85), i.e. as soft as the pure latent anchor and for longer; stage B's three steps from the sharp decoded frame do not recover what the stage-A latent anchor loses. Stage costs: text+A-prep 0.20, sampler A 1.35, upsample+B-prep (frame wait + VAE encode) 0.35, sampler B 0.80; decode 1.64 off-chain. Conclusion: any slot-0 latent anchoring (stage A or B) blurs the seam; the only sharp mode so far is the decoded-frame anchor for both stages (113), which puts the decode back on the chain (≈4.4 s per 2 s chunk at 49 frames; ≈5.6 s per 4 s at 97, i.e. ≈1.4 s/s). Next test: 115's `guide` mode (`LTXVAddLatentGuide`, the previous two latents as extra guide tokens for both stages — the model-native conditioning path, not the still-frame slot), which keeps the decode off-chain; measured by the same gate and sharpness profile.

**15:55 UTC: packet 115 (mixed anchor) qualified exact and is streaming at 49 frames.** Launched 15:42 UTC as unit `ltx115-stream-server-20261008` (manifest `a934bac2…`, `LTX_ANCHOR=mixed`: latent anchor for stage A, decoded-frame anchor for stage B after the upsampler; decode thread off the chain; text reuse on; `stream115-` names; coredump-deletion lines no longer latch). Gate passed: eager vs graph-replay vs repeat, c0/c1/c2 byte-identical, the stage-B frame equal to the predecessor's decode record across all three chains. First anchored chunks: submit→anchor 2.60 s (text+A-prep 0.10, sampler A 1.34, upsample+B-prep incl. frame wait and VAE encode 0.33, sampler B 0.80), decode 1.5–2.0 s off-chain. Cadence and seam sharpness over ~120 chunks being measured. Receipts `postflight-pre115-mixed-f49.json`, `continuation115-mixed-f49-storage-admission.json`.

**15:45 UTC: Flash-Next — the certified line needed ~116 GB of host RAM; today's host has 124 GB.** Codex mined the rescued A367 supervisor trace (`reopen-20261008/evidence/a367-host-pressure.tsv`, 1,241 samples): MemAvailable fell from 132.4 GB to a minimum of 16.6 GB during the certified 46.85 tok/s run, i.e. **115.9 GB of unreclaimable host use**, on the pre-fence host (~135 GB total). With memory blocks 53–57 offline the host now has 124 GB total (115 GiB), so even the certified configuration is marginal (≈3 GB of margin after the OS), and the stock 0.30.0 path OOM'd at 14:04 UTC. The calibrate-load launch was then refused by the controller's own boot-journal fault check (the 14:04 lines), by design; it was not retried. Conclusion for the owner: re-opening Flash-Next on this host needs a **host-memory reduction** first. Lossless candidates: serve the PLE table (95 GB BF16, unchanged bytes) from NVMe via mmap/page cache instead of pinned RAM; smaller pinned offload with more rows on the cards is not available (ranks sit at ~29.5 GiB of 32). Output-changing candidates (owner's call): Lumnus-style INT8 PLE table (halves it) or W4A16 weights. A design note is being written; no further GPU launch for Flash-Next until the owner picks. Flash-Next Screen 1b code (v5 placement port, watchdog, calibrate-load mode, 77+ CPU tests) is committed under `experiments/qwen38-flash-next-fp8-b70/reopen-20261008/`.

**15:21 UTC: false fault latch on the 97-frame run; probe clean; fault tally this boot stays at one incident.** At 15:06:16 UTC the 114 server latched FAULT on the kernel line `xe 0000:43:00.0: [drm] Xe device coredump has been deleted.` — the driver clearing the devcoredump created during the 14:04 UTC OOM incident. The launcher's GPU_FAULT pattern matches any `coredump`, so a housekeeping line halted the chain after 32 exact 97-frame chunks. No new device fault: the only fault-pattern lines this boot are the 14:04:34–14:04:51 cluster (one incident) and this deletion line. Server stopped once at 15:21:13 UTC; `FAULT.json` archived to `fault-archive/FAULT-20261008T150616Z-coredump-deleted-false-latch.json`; four-card probe passed 15:21:13 UTC. Packet 115 will exclude `coredump has been deleted` from the latch (creation lines still latch). Correction to my own checks: `journalctl --since` reads bare timestamps as **local time** (EDT), so several earlier "0 fault lines since <UTC time>" checks looked four hours too late; recounted with local windows above. Receipts `stream114-f97-stop.json`, `postflight-stream114-f97.json`.

**15:10 UTC: 97-frame chunks qualified exact and run ABOVE real time on one chain (latent anchor).** 114 relaunched at `LTX_STREAM_FRAMES=97` (after archiving the 49-frame run's outputs; the new collision preflight refused the first attempt as designed, before any device work). Gate passed: exact replay c0/c1/c2, four signatures per route; measured geometry equals the formulas (images [97,256,256,3], waveform [1,2,192480], audio latent [1,8,101,16], stage-A latent [1,128,13,4,4], video latent [1,128,13,8,8]). Streaming: **0.83 s of work per second of video** (stage costs: text+A-prep 0.20 with reuse, sampler A 1.66, upsample+B-prep 0.06, sampler B 1.25, anchor 0.02; decode 2.46 s and preview 0.46 s off-chain); zero faults; xpu:0 floor held. Caveat, now measured at 97 frames: the latent anchor's softness is worse with the longer chunk — relative sharpness 0.57–0.79 over frames 0–18 and again below 0.85 over frames 90–96 (20 chunks), so this is the speed ceiling for the fix in 115, not an adopted mode. Cadence 3.37 s mean / 3.27 s median / 3.78 s p95 per 4.04 s chunk. Receipts `postflight-pre114-latent-f97.json`, `continuation114-latent-f97-storage-admission.json`; the 49-frame run dir is `…-f49.run01-20261008T1434Z`, its outputs under `output/archive-stream114-run01-f49/`.

**14:50 UTC: packet 114 result — fastest chain yet, but the latent anchor softens every seam; not adopted.** Over 119 anchored chunks at 49 frames: cadence **2.58 s per 2.04 s chunk (1.29 s of work per second of video)**, submit→anchor 2.38 s; stage costs text+A-prep 0.20 (reuse), sampler A 1.35, sampler B 0.80, anchor 0.02, decode 1.64 and preview 0.26 off-chain; zero faults. Quality: per-frame Laplacian sharpness over 20 chunks puts the first six frames of each chunk at 60–85% of mid-chunk sharpness (0.60, 0.61, 0.67, 0.71, 0.80, 0.83), while the 113 frame anchor shows no dip (1.0–1.15). Cause as predicted: the slot-0 conditioning path treats the anchor as one still frame and a moving 8-frame latent is outside the model's training. Decision: latent anchor stays an A/B option only. **Packet 115 (building):** `mixed` anchor — stage A on the latent (so the next chunk's text and stage A overlap the previous decode), stage B on the sharp decoded frame as in 113 — plus a `guide` variant (`LTXVAddLatentGuide`) if it fits the signature model, and a per-chunk sharpness diagnostic in the receipt. Expected cadence ≈2.6–2.9 s with 113-grade seams. 114 server stopped once at 14:48 UTC after the measurement; postflight pass. Receipts `stream114-stop.json`, `postflight-stream114.json`.

**14:42 UTC: packet 114 (latent anchor, decode off the chain) qualified exact and is streaming.** Launched 14:34 UTC at 49 frames, `LTX_ANCHOR=latent`, text reuse on, unit `ltx114-stream-server-20261008` (manifest `3e8b7abe…`, fresh probe `postflight-pre114-latent-f49.json`, admission ok). Gate: eager vs graph-replay vs exact repeat, three chunks with a prompt cut, every tensor byte-identical including the decode thread's images and waveform; replay chunks 2.4–2.8 s. First streamed chunk: submit→anchor 2.53 s (text+A-prep 0.46, sampler A 1.28, sampler B 0.76), decode 1.52 s and preview 0.26 s off-chain. Cadence over ~120 chunks being measured; seams to be viewed. Client fix: a stale "not sealed yet" guard removed.

**14:35 UTC: Screen 1 failed to load (host OOM) and one GPU fault was logged during the kill.** Unit memory peak 67.9 GB plus pinned offload/PLE exceeded the 115 GiB host; the OOM killer took a vLLM worker at 14:04:51 UTC. During the teardown card `0000:43:00.0` logged a bcs memory CAT error, engine reset and timed-out job (14:04:34–42 UTC). Owner rule applied: launches stopped, evidence kept, **one bounded four-card probe passed at 14:31:18 UTC**, no render-node holders. **This is the first fault on this boot; a second one means a reboot decision for the owner.** No retry of this configuration; Screen 1b needs a host-RAM fit (lab placement/PLE semantics on V30). [Result note](experiments/qwen38-flash-next-fp8-b70/notes/2026-10-08-screen1-mtp1-host-oom-result.md). Disk after the approved retirement: 113 GiB free.

**13:59 UTC: Flash-Next Screen 1 launching.** The approved duplicate-capture retirement freed the disk (122 GB free at 13:50 UTC; its receipts follow when the agent reports). The pinned official image `vllm/vllm-openai-xpu@sha256:e4446310…` (vLLM 0.30.0, 4.0 GiB compressed) was pulled after admission; the controller's render-node idle check now has a privileged scan option (sudo via stdin from the local password file) because root-owned PIDs were unreadable and it failed closed. `screen.py run --mode mtp1 --execute` started at 13:59 UTC: full model-tree hash, admission, one container (port 19988), health wait ≤30 min, 16 requests (exact-2K ×2, exact-4K ×2, 12 cold realistic prompts), one SIGINT. Expected: a fused-GDN pin miss (the exactness cost of the community path) plus a diagnostic suite speed against the 46.854250 historical line; not an A/B, not a record.

**13:49 UTC: text-encode reuse qualified exact and measured.** Owner (13:40 UTC) approved trying caches/text reuse, pulling vLLM 0.30.0, Flash-Next time, and the verify-then-delete reclaim. 113 relaunched with `LTX_STREAM_TEXT_REUSE=1` (unit `ltx113-stream-server-20261008`, run dir of the earlier run set aside as `…-f49.run01-20261008T0907Z`, its outputs archived to `output/archive-stream113-run01/`): the gate compared the reused-text chain against a fresh-encode eager chain and all three chunks were byte-identical. Over 143 anchored chunks: cadence **4.66 → 4.38 s** per 2.04 s chunk; reused-text chunks 4.03 s submit→anchor (text+A-prep 0.40) vs prompt-cut chunks 4.41 s (0.78). Server stopped once after the measurement; postflight pass. Receipts `data/resume-20261008/stream113c-stop.json`, `postflight-stream113c.json`; client log `/home/steve/ltx-stream/s113-reuse01/client.log`.
Design for the next step is in [the latent-anchor note](experiments/ltx25-b70/notes/2026-10-08-continuation-latent-anchor-design.md): ranked levers are 97-frame chunks (≈0.8 s saved per second of video), text reuse (done), latent anchoring with the decode off the chain (≈0.58), encode-ahead (≈0.30); at 97 frames these estimate near real time. **Packet 114** (latent anchor, decode thread, 49/97 at launch, text reuse default on, `stream114-` names, collision preflight) is being built on CPU. **Flash-Next Screen 1** is scripted (`experiments/qwen38-flash-next-fp8-b70/reopen-20261008/`): official vLLM 0.30.0 image + pinned Lumnus Python overlays, MTP0/1/3 single launches, exact pins + cold suite; it needs 89 GiB free, so the approved duplicate-capture retirement (Tier A+B, ≈89 GiB of byte-identical captures) runs first.

**13:22 UTC: stream stopped at the owner's request; cards free for optimization.** Owner: "I no longer need the stream to meshcast running; we can go back to optimizing performance/resolution and I'm open to ideas on how to create seemingly continuous video. I'm also open to more Qwen Flash-Next 3.8 optimizations." Client drained (3,124 chunks on the 113 chain, zero faults), server stopped once with SIGINT at 13:21:57 UTC, sink/relay/preview/cleaner stopped, four-card postflight passed. No model server is running. The internal Flash-Next weights stay (needed for the lane; the USB copy is verified as a backup). Receipts: `data/resume-20261008/stream113-stop.json`, `postflight-stream113.json`.

**12:40 UTC drift data from 2,547 chained chunks (3.5 h):** the receipt's border/centre chroma ratio is flat by run quarter (2.47 / 2.27 / 2.75 / 2.23; median 1.99, p95 5.8, max 12.9, 49% of chunks above 2.0) and similar across all ten scenes (2.1–2.8). So the colour halo does not accumulate along the chain; it is a persistent property of this anchored lane. A reset policy would not cure it; the comparison that matters is unanchored vs anchored chunks (first chunk and future reset chunks). Zero faults since the 113 relaunch; 54 GiB free.

**09:16 UTC: packet 113 qualified and streaming.** Relaunched 09:07:21 UTC after the gap (postflight pass, admission pass); qualification passed 09:15:36 UTC: exact replay c0/c1/c2 true, four signatures per route, window 64 (eager 18.1/7.5/6.8 s, first graph 10.4/10.3/5.0 s, replay 3.9/4.9/4.7 s). First stream chunk: submit→anchor 3.77 s, submit→preview 4.38 s, preview written off-chain (0.61 s, no longer on the critical path). Sink moved to the s113 manifest. Receipts: `data/resume-20261008/postflight-stream113a.json`, `continuation113b-storage-admission.json`.

**09:02 UTC: first 113 launch latched on a name collision (my mistake, no hardware fault).** Packet 113 keeps 112's request names, so its first qualification chunk tried to create `output/validation/stream112-qeager-c000000`, which still held the 112 run's capture, and the executor latched ("did not finish exactly one successful request"). Kernel log clean. Server stopped once with SIGINT at 09:02:11 UTC; evidence kept at the run dir renamed `…-f49.failed-20261008T0901Z`; the 112 run's nine qualification captures and 61 leftover preview dirs were moved (not deleted) to `output/archive-stream112-run01/`; relaunch after the gap. Lesson, again: grep for every reused literal name before launching a successor packet. Receipt: `data/resume-20261008/stream113a-stop.json`.

**08:55 UTC: reload to packet 113.** No owner answer after two hours, so the 113 reload went ahead with text reuse off (no output change: it only moves the preview write off the chain and adds the reset request and drift diagnostic). 112 ran 2,754 chunks on one chain with zero faults; client drained, server stopped once with SIGINT at 08:49:16 UTC, postflight passed, storage admitted, 113 launched 08:54:30 UTC as unit `ltx113-stream-server-20261008` (manifest `a23dbc94…`, same identity otherwise). Client unit `ltx113-stream-client-20261008` (`--packet 113 --poll 0.05`) is running qualification; the sink will be moved to the s113 manifest when it passes. Receipts in `experiments/ltx25-b70/data/resume-20261008/` (stream112-stop, postflight-stream112, continuation113-storage-admission).

**06:25 UTC:** the chain has run 930+ chunks without a fault. Client poll tightened to 50 ms: cadence 5.15 → 4.95 s per 2.04 s chunk (submit→preview 4.63 s unchanged). Over 30 minutes of sampled frames the border/centre saturation ratio wandered 0.6–1.9 with no trend: the colour halo is scene-dependent, not accumulating. **Packet 113 is built and sealed, not launched** (manifest `a23dbc94…`, 80/80 + 63/63 + 46/46 + 11/11 tests): preview MP4 written off the chain by an in-order writer with receipt timings `anchor_ready`/`preview_queued` (expected −0.2 to −0.25 s), a client-requested unanchored **chain reset** (`reset: 1`, `--reset-every-chunks`, `--reset-on-scene-change`), and a per-chunk anchor border/centre chroma diagnostic. **Graph-captured decode is blocked:** the decoder rebuilds its RoPE tables from host memory on every forward (no fp64 on B70), so capture was never exact; the only fix is a bounded device-resident table cache, an owner decision. Launch of 113 waits for the owner's text-reuse ruling so the stream takes one reload, not two. [113 design](experiments/ltx25-b70/notes/2026-10-08-continuation113-stream-design.md).

**05:18 UTC: the continuation stream is live on meshcast.** Packet 112 qualification passed at 04:59:31 UTC: eager chain vs graph-replay chain vs exact repeat, three 49-frame chunks each (chunk 2 a prompt cut), all four tensors byte-identical per chunk, four graph signatures per route, qualified text window 64. Timings: eager chunks 19.4/8.1/7.2 s, first graph (capturing) 10.3/10.8/5.2 s, replay 4.8/5.2/5.1 s. Streaming since 04:59: one anchor chain through the ten kitten scenes (four chunks per scene, cuts on the same chain), **4.6 s per 2.04 s chunk (0.44x real time)**: queue 0.01, text+stage-A prep 0.76, sampler A 1.61, sampler B 0.99, decode 0.95, preview write 0.30. The sink plays each anchored chunk minus its duplicated first frame (48 frames) and holds honestly when the chain is behind. Next exact levers on the chain, in order: text-encode reuse within a scene (`LTX_STREAM_TEXT_REUSE=1`, qualified against a fresh-encode eager chain; owner's call), preview write off the critical path, graph-captured VAE decode, then sampler-A work.

**04:52 UTC: reload to the continuation server.** Kitten driver drained (11,087 clips emitted), stream01 server stopped once with SIGINT at 04:45:49 UTC, four-card probe passed, storage admission passed (54 GiB free against 53 needed), packet 112 launched at 04:51:00 UTC as unit `ltx112-stream-server-20261008` (`two-way20-28`, one sampler worker, batch 1, 49-frame chunks, text reuse off, manifest `e49f669d…`). Its client unit `ltx112-stream-client-20261008` is running the built-in qualification (eager chain vs graph-replay chain vs exact repeat, three 2-second chunks each with a prompt cut at chunk 2, all four tensors byte-identical required) before any streaming. The meshcast stream is holding its last kitten frame with the buffering overlay meanwhile. Receipts: `experiments/ltx25-b70/data/resume-20261008/` (stream01-stop, postflight-stream01, continuation112-storage-admission). Client/packet docs: `experiments/ltx25-b70/stream/CONTINUATION-CLIENT.md`, `recovery/20261008-continuation112-stream/{CONTRACT,LAUNCH}.md`.

**04:10 UTC update:** the owner asked for one theme (kittens; "just cats has some viral aspect"), scenes that feel connected even across cuts, longer scenes, and much less lag (it was ~5 min of deliberate buffer). Done on the running lane: ten kitten prompts (`experiments/ltx25-b70/data/stream/kittens-01.json`, no references, 64-token window), buffer cap 45 s, sink restarted at the first kitten clip (lag now a few seconds, growing to the cap), sink routed through the local relay so the LAN preview and meshcast both work. Packet 112 brief updated: 49-frame (2 s) chunks by default, prompt may change at any chunk on the same anchor chain so cuts flow, per-chunk latency in receipts.

**Public stream live on meshcast since 03:33 UTC** (owner-created stream ID; ingest URL kept in `~/.config/ltx-stream/rtmp_url`, forwarded by `/home/steve/ltx-stream/relay2.sh` without re-encoding; LAN MJPEG preview at http://10.0.0.65:8090/). The owner watched it: "definitely working, but it's a bit like 2 second clips, back to back, with no continuation." That is the independent-take lane. **Next: packet 112**, the 111 continuation runtime at 256×256/25 frames with per-block graph replay and a streaming authority (unbounded ordered chunks, anchor-chained, built-in eager-vs-replay exact gate), being built on CPU; when it passes its gate the stream01 server is swapped for it in one controlled reload, accepting a below-real-time coherent stream with honest holds until the sampler gets faster. [Design note to follow](experiments/ltx25-b70/notes/2026-10-08-continuation112-stream-design.md).

**Earlier (01:34 UTC, local discard receiver until the destination arrived):** warm-up on the stream01 server passed (window probe, two capture passes, pool calibration, decode replica exact 10/10, freeze, self-check, both proof arms 20/20 byte-identical to `stability-01-b2`); the first ten stream clips also matched their references. Generation runs at 0.98 s per clip (about 25.5 fps generated, 24 fps played), the sink has played ~1,000 clips with one 11 s startup hold and no slips, buffer about 65 s, driver throttle at 300 s ahead. Start scripts `/home/steve/ltx-stream/start-sink.sh` / `start-driver.sh`; the key file is `~/.config/ltx-stream/rtmp_url` (outside Git). Stream clips' oracle tensors are pruned after hashing; disk growth is being measured for a receipt cleaner.

**Server:** the packet-97 server (two-way, two sampler workers, batch 2, shared
pool, decode replica on xpu:2; the 27.5 fps configuration of 2026-10-06, 613/613
exact against the `stability-01-b2` references) is being launched once as
`encoder-server-place-97-two-way-w2-b2-p1-dxpu2-stream01` (unit
`ltx97-stream01-server-20261008`) after the five-minute gap, to serve a
continuous stream driver. The stream uses the batch-2 lane because it is the
only configuration above real time; batch-2 clips remain a different take from
batch-1 (rounding), so this is a streaming choice, not a baseline ruling.
Being built (CPU): `experiments/ltx25-b70/stream/` — an RTMP sink (ffmpeg, now
installed from Ubuntu packages) and a continuous driver that reproduces the
runner's warm-up then cycles the ten fixtures with a new seed each cycle.
Stream previews are disposable by design; references, anchors and failures stay
protected. Flash-Next: Codex is producing a CPU-only analysis of the Lumnus
stack (`experiments/qwen38-flash-next-fp8-b70/notes/2026-10-08-lumnus-v0300-stack-analysis.md`);
no GPU time for Flash-Next while the stream owns the cards — time-sharing is the
owner's call.


**Live update, 2026-10-07 local / October8 UTC:** the native three-chunk
continuation/replay test is running under its fixed eight-request plan.111
launched once after a clean controlled110 application shutdown and passing
four-card postflight. PID3415570/start ticks29306475, unit
`ltx111-continuation-server-20261007`; campaign
`ltx111-continuation-campaign-20261007` started00:28:07 UTC. No continuation
quality or speed result is established yet. Preserve every predecessor and
capture; faults halt requests, successful application retained.

The preceding full ten-fixture,49-frame LTX qualification
passed. All 57 requests completed at 23:35:42 UTC. Twenty native outputs formed
ten exact repeat pairs; ten optimized and ten timed clips matched all four
video/audio tensors. The unchanged sealed verifier independently rebuilt the
complete proof at 23:38:47 UTC. Memory and capture checks passed, with no kernel
faults in the campaign window. About 58 GiB of disk space remains free.

Nine delivery intervals averaged 2.8836 seconds per 49-frame clip, or 16.99
generated frames/s. This is a short qualification screen, not a matched speed
gain, endurance result or public record. Playback remains 24 FPS; independent
clips do not establish coherent streaming.

The successful110 application received one necessary graceful SIGINT for the
111 continuation reload; PID3391197 was gone at00:26:31 UTC. All four cards
passed postflight with no faults this boot. No host restart or settings change.
Its finite57-request authority stays consumed; all outputs remain protected.
110 manifest`bfa78fcf6af59acc3d63318ca97c61846b3a9b80999f6f17cb4c4d3651f2ad09`;
client contract`70b5379a715b7c51008fbc65967e2dc503554b70e5e460d02ddbe8d4689df27d`.
[Completed proof and 1,246 file bindings](experiments/ltx25-b70/data/resume-20261007/duration110-closeout/summary.json),
[resource audit](experiments/ltx25-b70/notes/2026-10-07-duration110-resource-audit.md),
[operation](experiments/ltx25-b70/notes/2026-10-07-duration110-operation.md).

Next: prepare a native three-chunk scene-continuation reference and exact replay,
using the preceding decoded frame before both samplers. This is CPU preparation,
not an admitted GPU workload or adopted quality mode. Additional VAE encoding
needs separate memory admission; exact replay and visual seam quality are separate
gates. Raw audio remains unchanged and separate until its timeline is resolved.
[Continuation design](experiments/ltx25-b70/notes/2026-10-07-after110-continuation-priority.md).
The inactive frame/graph prototype passes 16 CPU tests and independent review.
The source-pinned encoder OOM refusal passes six tests; it preserves successful
encoding and the existing decoder path. The fixed eight-request native-only plan passes twelve CPU tests and independent
review; its six-output capture restriction passes five tests. The corrected per-stage memory guard and related safety components pass all
37 combined CPU tests in the actual LTX Python environment. Independent review
confirmed both ordering/reentry findings resolved; the earlier version is preserved.
The native-only runtime authority, provider, proof/client wiring and sealed source
assembly are now complete. All126 combined CPU tests pass, including actual110
receipt compatibility and independent source/concurrency reviews. The111 packet
was built exclusively while110 stayed running; its actual sealed CPU startup
check passed, without device discovery. The application and finite campaign
are now live as recorded above. A480,219-entry filename scan found no collisions for its eight
request names or six physical indices.4GiB runtime plus384MiB build admission
preserves the50GiB reserve; this is monitored headroom, not a filesystem quota.
111 manifest`65adf13fca14f92047960ed939c507cd7e28a08b41940decd089189c86c41363`.
Fresh launch admission left53.84GiB after the4GiB allowance. Actual registered
classes, source/process identity and client contract checks passed. IdentitySHA
`294fee41017abbe81ea1bba3160af98b28f1607cd4f2d018c17c23c604239909`;
clientcontractSHA`d6ad20e0534ebe6b152990dfa04b833d855952c188a9f0abc58ebfdfdca1f107`.
The first native and first conditioned proofs gate further requests. Seams and audio
alignment remain separate quality questions; no new speed result is claimed.
[Runtime integration and reviewed fixes](experiments/ltx25-b70/notes/2026-10-07-continuation111-runtime.md).
[Integration design](experiments/ltx25-b70/notes/2026-10-07-continuation111-integration-design.md),
[memory design](experiments/ltx25-b70/notes/2026-10-07-continuation111-memory-design.md).
[Runtime interface map](experiments/ltx25-b70/notes/2026-10-07-continuation111-runtime-interface-map.md)
identifies the exact authority, registration and native output interfaces to reuse.
The new authority must enforce all eight requests and durable per-chunk proofs in
global order;110's phase-local ordering cannot be reused unchanged.

The preceding49-frame109 pilot completed successfully at
22:56:44 UTC. Its application stopped cleanly once at2026-10-07T23:15:35.660027+00:00
for the necessary110 full-fixture application reload. PID3380321 is gone; no
host restart or settings change occurred. All four cards passed postflight at2026-10-07 23:15:46 UTC; no faults this boot.
All 29 requests completed: six native outputs formed three exact repeat pairs,
and three optimized plus three timed clips matched all four video/audio tensors.
The unchanged sealed verifier independently rebuilt the full proof. All memory
and capture limits passed; no kernel fault appeared in the campaign window.

The two measured delivery intervals average 3.0805 seconds per 49-frame clip
(15.91 generated frames/s). This is a three-fixture resource pilot, not a full-suite,
matched speed-gain, endurance, adoption or public-record claim. Playback is 24 FPS.
Named20/28 placement, BF16 and 8+3 steps remain unchanged. The tightest sampled
poststage memory was 4.968GiB free on the decoder card, above its 2GiB floor;
these observations are not continuous peak-memory bounds.

The full ten-fixture qualification is now complete. The old, stopped
97 B4-r2 arm's577 byte-identical duplicates have now been retired after two fresh
original-comparator passes. That recovered10.855GiB;20 reference/representative
archives were reverified, all metadata/previews retained, and direct ordinary-copy
restore maps are recorded. The first plan's wrong cyclic fixture assumption was
safely refused; the corrected map uses the pinned historical emitted order.
[Cleanup receipt](experiments/ltx25-b70/data/resume-20261007/after109-b4-retirement-completed.json).

The full ten-fixture110 successor passes305 combined runtime CPU tests and31
standalone plan controls, actual-venv source/runtime checks and independent review.
It admits57 requests/50 captures with9GiB runtime writes above the50GiB reserve;
prebuild admission additionally reserves384MiB. Its numerical path and memory
floors match109. 110 source construction and the actual sealed CPU startup check passed;
The110 campaign completed successfully as recorded above. Fresh9GiB launch admission left54.46GiB after allowance. Fresh prebuild available space was68,258,586,624bytes.
No extra requests are authorized by the consumed pilot plan, and no passive
observer is running. Models, failed experiments and unique outputs stay protected.
[Completed pilot proof](experiments/ltx25-b70/data/resume-20261007/duration109-closeout/summary.json),
[resource audit](experiments/ltx25-b70/notes/2026-10-07-duration109-resource-audit.md).

108b completed text preparation then safely refused the full-residency guard,
with zero49-frame generations and one graceful shutdown. Its missing setup
memory evidence is now fixed for109. Historical source arithmetic—not recovered
108b telemetry—supports one20/28 candidate; it is not a split sweep. The four
placement source files match earlier100b exactly, including host ownership fix.
303 runtime and30 plan CPU tests pass; independent review and actual sealed CPU
startup check pass. All four cards passed postflight at2026-10-07 22:43:43 UTC
with zero earlier/new faults. The109 source packet and request namespace are
sealed/reserved. Fresh4GiB runtime admission left50.394GiB after allowance.

109 manifest`e91e8994642cf03210c5bde724a485e0c314a409a300a40379cc79a43fc67906`;
client contract`aed8513ec6bdbc96571891738e7667772110b63261f2245eadaa98f2092cb251`.
[109 operational record](experiments/ltx25-b70/notes/2026-10-07-duration109-operation.md),
[108b refusal](experiments/ltx25-b70/data/resume-20261007/duration108b-closeout/summary.json),
[residency audit](experiments/ltx25-b70/notes/2026-10-07-duration108-residency.md).

107b stopped cleanly once at22:18:33UTC; all four GPUs passed postflight with no
faults. After two fresh full quality-proof reconstructions,40 whole-file duplicate
archives were retired against10 protected105 keepers, freeing2.780GiB, with direct
restore maps.108 startup then refused before GPU discovery or any model request
because serializer hashes extended the inherited dependency baseline. Its sealed
packet is preserved.108b adds an exact dependency adapter;292 CPU tests and the
actual CPU startup path pass. Fresh disk admission preserves50GiB after4GiB.

108b manifest`ef839f83eaea6526f09cc353c6996a56414a95beb41609278b4b6e2994697ad7`;
client contract`699c857274dc4687374a8dbeb157b28f612940712b7aad9867976ff600f084cd`.
[Operational record](experiments/ltx25-b70/notes/2026-10-07-duration108-operation.md),
[live admission](experiments/ltx25-b70/data/resume-20261007/duration108b-live-admission.json).
The following107b running state is its earlier completed campaign history.

The owner resumed continuous LTX optimization on `steve-b70s`. The105 application
completed its71-request campaign successfully at19:43:32UTC, then stopped cleanly
at2026-10-07T20:13:39.070899+00:00 for the necessary106 application reload. All four cards passed
postflight at2026-10-07 20:13:55 UTC; no host restart or settings change occurred.
The **106 application stopped cleanly** at2026-10-07T21:17:16.424803+00:00 for the necessary107
application reload. Its57-request campaign had completed at20:37:00UTC; the full
quality proof remains preserved. All four cards passed postflight at2026-10-07 21:17:42 UTC,
with zero kernel faults this boot. The corrected **107b application is running**, unit`ltx107b-sparse-server-20261007`,
PID**3362949**, start ticks`28246808`, same boot
`10192010-9700-4915-ac6c-980d6b74afa0`. Its57-request campaign started at
2026-10-07T21:31:48.975140+00:00 and completed successfully at21:45:14UTC.
The application remains healthy and idle; no fault/halt or kernel entries in the
campaign window. All20 native executions form10 exact repeat pairs;10 candidate
and10 timed clips match all four video/audio tensors. The unchanged sealed proof
independently reconstructed at21:47:23UTC. There is no passive collector.

The sparse transfer diagnostic is valid on both sampler workers. All14 actual
timed jobs recorded zero timing events; dormant CPU hooks remain. The short
repeated-workload screen delivered12.793 generated FPS, not a matched gain or
public record. Close the proposed direct-static activation-copy change: incoming
allocation takes0.100–0.158ms and the whole boundary fill0.374–1.182ms, too little
to justify its buffer-lifetime risk. Long host waits overlap queued compute and
are not removable copy latency. Next: offline audit and qualification design for
49-frame clips at640×384, retaining BF16,8+3steps and exact video/audio gates.
The full ten-fixture49-frame suite cannot fit the current disk reserve. A separately
labeled three-fixture resource pilot is CPU-implemented and independently reviewed:
29requests,22 capture-bearing graphs,4GiB allowance with bounded placeholder
outputs and a mandatory first-native shape/memory barrier.285 full CPU tests plus
focused post-change checks pass; actual-venv source/runtime preflight passes.
The new immutable packet has not been materialized or launched.
No longer-shape request or cleanup has occurred. Preserve all107b raw artifacts.
[Duration audit and pilot limits](experiments/ltx25-b70/notes/2026-10-07-duration108-audit.md).
[107b closeout](experiments/ltx25-b70/data/resume-20261007/sparse107b-closeout/summary.json),
[trace interpretation](experiments/ltx25-b70/data/resume-20261007/sparse107b-interpretation.json).
Manifest`fb26b0d5d3d2d892bce046e93547e1b71bf4c7d34ba2b1d0992dfabf9a4ab1fb`;
client contractSHA`4f0c3c01ed5b4d8c525706da33d069d61aebcd34718f8d4270547db1c1f29b7e`.

Failed107 had zero model requests: a mistaken graph-helper/node-wrapper copy
removed node registration. Its sealed source and startup refusal are preserved.
107b removes that packaging error;12 builder and5 actual-registration tests pass,
and all other292-test source bindings are unchanged.107 stopped cleanly at
2026-10-07T21:28:57.124406+00:00; all four cards passed postflight at2026-10-07 21:29:23 UTC,
zero earlier/new faults. No restart/retry loop, computer restart or settings change.
The unused107 request namespace is used by107b, with a fresh collision check.
The40-file106 duplicate retirement completed with direct105 keepers and restoration
maps. Fresh107b admission observed54.791GiB free and50.791GiB after4GiB.
[107 startup refusal](experiments/ltx25-b70/data/resume-20261007/sparse107-startup-refusal/summary.json),
[107b live admission](experiments/ltx25-b70/data/resume-20261007/sparse107b-live-admission.json).
Flash-Next and local-worker tuning remain parked.

106 preserved exact video and audio outputs:20 native executions form10 exact
repeat pairs, followed by10 exact candidate and10 exact timed clips. The unchanged
sealed final proof independently reconstructed at20:39:25UTC. The instrumented
short workload averaged1.99278seconds per25-frame clip (12.545 generated FPS);
this is a diagnostic rate, not a new record or matched speed improvement.

The **whole passive diagnostic remains invalid**:27 snapshots contained25 complete
and2 incomplete scans where an unclassified descriptor disappeared. One was
inside the scored delivery window. It ended normally at its128KiB output cap,
with no missed cadence slots. Two independent reviews identified seven later
complete interior intervals suitable only for explicitly posthoc raw-counter
analysis. They show sampler copy-accounting activity, not transfer latency,
critical-path causality or whole-device utilization. Do not rerun merely for a
green diagnostic flag. Next: one sparse attributed transfer/fill trace, then a
measured source change if the evidence supports it.
[106 closeout](experiments/ltx25-b70/data/resume-20261007/sampler106-closeout/summary.json),
[independent proof](experiments/ltx25-b70/data/resume-20261007/sampler106-post-completion-proof.json),
[integration and next-lever evidence](experiments/ltx25-b70/notes/2026-10-07-sampler106-integration.md).

The reduced-write client policy improved generation throughput in both tested
orders while preserving exact video and audio outputs:

| Test order | Control | Reduced writes | Throughput gain |
| --- | ---: | ---: | ---: |
| 104: control first | 12.040 generated frames/s | 12.786 | 6.20% |
| 105: reduced writes first | 12.098 | 12.617 | 4.29% |

Each application completed twenty native executions forming ten exact repeat
pairs, ten exact candidate clips, and two ten-clip exact timing blocks. All four
captured tensors matched: video latent, audio latent, images and waveform.
These are short repeated-workload screens, not cold-input, endurance or public
record claims. No unrelated tests, Git activity or file writes overlapped either
105 timing block; preparation stopped before 19:36 UTC. The reduced-write policy
keeps all fault/source/storage checks, changed-state saves and event-log fsyncs.
105 skipped 705 unchanged saves and retained 667, versus 1,282 control saves.
The full unmodified sealed proof was independently reconstructed at 19:46:02 UTC.

Keep the reduced-write policy and **close the client comparison lever**. The106
counter diagnostic now guides the sampler investigation, with the incomplete
coverage limitation above. The106 runtime passed253 CPU tests and independent
review before launch. Its57 requests and50-capture cap used a fresh4GiB runtime
allowance above50GiB; source construction had its separate384MiB admission.
Sealed106 manifest:
`59765f873aa553104691053c43f0964725353ddb25df471f806b039e1aa4c6e2`.
The standalone107 sparse-trace plan passes32 CPU tests. It retains57requests,
50captures and4GiB, with at most one candidate job on each of the two actual
sampler workers; every later timed request is trace-disabled. Runtime injection
is now CPU-reviewed:257 author and35 helper/overlay tests pass. It records at most
one candidate job per actual worker, with bounded events, and independently checks
zero timing events across all actual later timed jobs including tails. Model
quality gates remain mandatory; dormant CPU hooks remain. 107 source construction and the single106 controlled stop are complete.
107 startup refused model admission; corrected107b completed its first finite campaign.
106 duplicate retirement is complete.
[107 injection contract and next sequence](experiments/ltx25-b70/notes/2026-10-07-sparse107-integration.md).
The fixed40-file106 duplicate helper
passes17 synthetic safety tests and independent review; the real40-file106 retirement completed after stopped-owner and fresh full-proof
checks. All direct105 keepers remain protected; restore the40 mapped ordinary
copies before replaying106 full raw proof.
[106 cleanup and restoration](experiments/ltx25-b70/notes/2026-10-07-after106-storage.md).
Sampler A/B timings describe denoising stages, not individual GPU utilization;
they do not justify a blind placement or worker-count sweep.

105 sealed manifest:
`1ff7bd5ab281dad1a19f8d01aaf8899505168f0606689ba43ccb23cc05311fad`.
[105 closeout](experiments/ltx25-b70/data/resume-20261007/client105-closeout/summary.json),
[independent proof](experiments/ltx25-b70/data/resume-20261007/client105-post-completion-proof.json),
[105 measurements](experiments/ltx25-b70/notes/2026-10-07-client105-performance.md),
[104 measurements](experiments/ltx25-b70/notes/2026-10-07-client104-performance.md),
[sampler investigation](experiments/ltx25-b70/notes/2026-10-07-sampler-after105-audit.md),
[reviewed raw collector](experiments/ltx25-b70/recovery/20261007-driver-accounting106/README.md),
[106 plan](experiments/ltx25-b70/recovery/20261007-sampler-accounting106-plan/candidate-plan.json).

After two fresh full105 proof reconstructions,40 verified whole-file duplicate
captures were retired with durable restoration mappings, reclaiming2.780GiB.
Ten105 native-p1 anchors and all26 previous restoration anchors remain. Fresh106
admission observed55.067GiB free and51.067GiB after its4GiB runtime allowance.
After106 completion about52.24GiB remained before107 construction and verified
retirement. The fresh107 admission above is current; future admission must be
fresh, not borrowed from a completed run.
Restore the40 mapped ordinary copies before replaying105's full raw proof.
Models, previews, metadata, patches and failed experiments remain protected.
[105 cleanup and restoration](experiments/ltx25-b70/notes/2026-10-07-after105-storage-plan.md).

104 stopped cleanly at 19:14:56 UTC for the controlled 105 reload, and all four
cards passed postflight at 19:15:32 UTC. Then 52 verified whole-file duplicates
from stopped 101c, 102 and 104 were retired, reclaiming 3.614 GiB after all three
full sealed proofs were reconstructed twice. All 103 restoration anchors remain.
Restore the mapped ordinary copies before replaying affected full proofs; stored
bindings describe their pre-retirement state.
[Completed cleanup and restoration](experiments/ltx25-b70/notes/2026-10-07-after104-storage-options.md).

103 previously passed all ten fixtures and50 scored optimized clips, measuring
12.00FPS initially and11.03FPS in thirty continuity clips. Concurrent repository
work confounded its late delivery drift. Its application stopped cleanly at18:28
for104, and all four cards passed postflight at18:28:52UTC. Thirty verified duplicate
continuity archives were then retired, reclaiming2.08GiB. Restore mapped ordinary
copies before replaying the full103 proof; all its anchors remain protected.
[103 closeout](experiments/ltx25-b70/data/resume-20261007/resolution103-closeout/summary.json),
[retirement and restoration](experiments/ltx25-b70/notes/2026-10-07-resolution103-retirement-plan.md).
The earlier matched W1/W2 three-fixture screen improved8.710→12.282FPS, a41% gain;
its narrower workload is not directly comparable to the later ten-fixture results.

The latest owner-provided instructions prefer one continuously running application
and endpoint reuse. A necessary controlled application reload remains authorized;
no automatic stop-on-success, restart chain, request retry, host reboot, driver
reset or power/RAM/swap/page-cache change is authorized. Blocks53–57 remain offline
and `b70-offline-bad-memory.service` enabled; RAM replacement is deferred for2026.

The current-upstream compatibility control passed: **126 probe/timed clips and
two self-check clips match the accepted references exactly**, including video,
audio, images and waveform. Sustained generation is about **1.3156 seconds per
25-frame clip, 19.0 generated frames/s**, essentially the historical 1.3179-second
control. This is a qualified new source base, not a new speed record. The accepted
scope is native BF16, 256×256, 25 frames, 24 playback fps, original 8+3 schedule,
accepted short encoder window, batch 1, two workers and the 23/25 sampler split.
Generation throughput is distinct from playback fps and coherent long video.
[Run summary](experiments/ltx25-b70/data/upstream-99b/two-way-w2-b1-p1-dxpu2-s256x256/summary.json),
[postflight](experiments/ltx25-b70/data/resume-20261007/postflight-99b.json).

ComfyUI `b00c6e95279053474955540ba4f551646722b9aa` and the isolated dependencies
are preserved. The first upstream attempt failed because conditioning and full
outputs changed. A narrow process-local RoPE arithmetic compatibility patch now
restores the accepted outputs across the tested fixtures; source/package files
and references remain unchanged. Original failed clips and evidence remain
preserved. The qualified packet manifest is
`f819270165a7e8c59206b0dd641ebb1b7763e586b458a1e32a75344f96220d0a`.
[Compatibility result](experiments/ltx25-b70/notes/2026-10-07-rope-compatibility-results.md),
[Original failure](experiments/ltx25-b70/notes/2026-10-07-upstream99-quality-failure.md),
[compatibility plan](experiments/ltx25-b70/data/resume-20261007/runtime99b-preregistration.json).

The earlier 20/28 placement screen was only about1.1% faster at 256×256, so it did
not replace the 23/25 control. W3 at that small shape is not queued.
[Placement result](experiments/ltx25-b70/notes/2026-10-07-rebalance100b-results.md).
Two failed 640×384 attempts exposed admission/verifier assumptions, now corrected
without changing model calculations: original FP32 constructor state and the
window-encoder's mode-prefixed job tag. Both failed packets, six unqualified
native clips from 101b, and all failure evidence remain protected.
[Initial preparation refusal](experiments/ltx25-b70/notes/2026-10-07-resolution101-setup-refusal.md),
[verifier refusal](experiments/ltx25-b70/notes/2026-10-07-resolution101b-verifier-refusal.md),
[successful runtime components](experiments/ltx25-b70/recovery/20261007-resolution-runtime/README.md),
[follow-up choices](experiments/ltx25-b70/notes/2026-10-07-follow-up-levers.md).

The application-only 65,536-file soft limit prevented the original descriptor
exhaustion. The corrected observer also exited cleanly. This is a practical
limit/observation fix, not proof of no descriptor leak. Historical and current
source packets, failures, references, notes and models remain protected.
[Initial incident](experiments/ltx25-b70/data/resume-20261007/fd-incident/closeout.json).
Verified duplicate tensor retirement recovered 2.18 GiB, 1.99 GiB and 10.96 GiB
in three recorded batches. No model was deleted. A further 212 duplicate timed tensor archives from the completed 99b/100b runs
were freshly verified and retired, recovering 3.99 GiB and leaving about 63 GiB
free. Ten timed samples per run, all references, metadata, previews, fill captures
and failures remain. Previous experiment write allowances do not carry over
automatically.
Batch-2/4 output-changing results and larger speed-only arms remain unqualified
for the lossless objective.

## Four-card preceding consolidation (historical closeout)

The owner authorized the five follow-up priorities. The CPU-only
[lab navigator](experiments/lab-navigator-20261007/README.md) now indexes exact
source commits and exports verified passages. Frozen retrieval covered all
required spans for 4/6 development and 4/6 held-out questions; missing conditions
remain a known limit. This is source search, not model-memory qualification.
The companion reader now binds sources to actual Git tree paths and bytes,
refuses stale indexes by default, and supports complete selected documents with
explicit omitted ranges and separate policy/status previews. The
[practical review](experiments/lab-navigator-20261007/followup/results/practical-review.json)
uses the latest recorded short-source and history results; it does not rerun the
consumed retrieval evaluation or qualify an autonomous worker. Use complete
short sources where practical; defer new memory machinery until a concrete task
requires it. No new model requests were made for this follow-up.
The [scoped worker task](experiments/local-coding-worker/scoped-task-20261007/README.md)
selects about 203 KB of pinned source with explicit patch boundaries. All 135
worker CPU tests pass; historical bug/fix controls pass their expected outcomes.
The single [scoped coding attempt](experiments/local-coding-worker/scoped-task-20261007/CLOSEOUT.md)
closed at 12 steps after 114.54 seconds, with no edits and no acceptance submission.
The historical R276 server stopped cleanly; all four cards passed postflight.
All 80 temporary RAM model files were rehashed and released; the cold model is
retained and EX400U is unmounted.
Park further local-worker tuning and memory integration on this evidence. No resident service or newer-package
qualification is implied. Five other unused coding tasks remain untouched. LTX and Flash-Next remain parked.

[LFM source preparation](repro/lfm25-26b-q8-b70/README.md) now verifies the exact
public archive and every extracted file. Full strict-headline toolchain identity,
public runtime rebuild and clean-host replay remain pending; the older local
build is not the strict-headline build. No new measured speed is claimed.
The [bounded follow-up audit](experiments/lab-navigator-20261007/followup/toolchain-audit.json)
found matching strict runtime receipts and versioned library search paths, but
these do not recover the original compiler/build inventory or resolved libraries.
Recover that evidence or qualify a separate reconstruction; do not infer a
historical toolchain from search-path labels.

The owner asked to preserve both lanes and make the existing lab dependable before
returning to optimization. **No resident model service is authorized on `steve-b70s`.**
**No model server is running.** The earlier fresh [references-only recall trial](experiments/local-coding-worker/cited-recall-v2-20261007/CLOSEOUT.md)
completed all ten answers in 176 seconds, passed strict citation compilation,
and stopped cleanly with all four cards healthy. Independent review found all 20 citations relevant but only 12/30 criteria
fully covered: required conditions were omitted. Its semantic gate failed.
Keep it separate from unattended coding; no model/package is promoted.
The [4B trial](experiments/local-coding-worker/qwen4b-worker-pilot-20261007/CLOSEOUT.md)
and separate [27B trial](experiments/local-coding-worker/qwen27b-target-only-smallkv-20261007/CLOSEOUT.md)
each completed zero of two coding repairs under different runtime/budget profiles.
The 27B source-recall request reached its seven-minute limit before finishing;
partial answers are preserved without a quality score. Do not connect these
components or leave them serving on this evidence. Five unused coding cases remain after the separate scoped attempt described above.

A smaller full-precision application cache restored about 15 GiB of host RAM
headroom while keeping the same context limit; both finite runtime checks passed.
The server stopped cleanly, all four cards passed final checks, and no OOM or
new kernel fault appeared. Coding evidence is archived and verified. Disposable
source snapshots were released; all 80 model files remain in the verified cold
copy. The fresh recall trial
finished and its temporary RAM copy was fully rehashed and released.
EX400U is cleanly unmounted. The citation compiler passed 13 CPU tests; meaning
and relevance still require separate review. The new packet uses four complete
source documents and ten newly worded questions, with some shared themes.

LTX's earlier disk-full incident left a progress-bar lock stuck. Its evidence
was preserved and one SIGINT stopped the application cleanly. LTX and Flash-Next
stay parked. No reboot, driver reset, power, host memory, swap or page-cache
setting was changed.

- **LTX:** accepted-reference result 1.308 s/clip; batch-4 result 0.808 s/clip
  remains conditional on accepting its different outputs. Packet 98 is prepared,
  CPU-tested and unmeasured on GPUs. A zero-byte helper was recovered from its
  hash-verified sealed copy; incomplete run evidence remains unmodified.
  A separate [progress-lock fix](experiments/ltx25-b70/recovery/20261007-progress-lock/README.md)
  reproduces the ENOSPC lock leak and passes ten CPU tests; it is not installed.
  [Resume handoff](experiments/ltx25-b70/RESUME.md).
- **Flash-Next:** preserve the [46.854 tok/s closeout](results/qwen38-flash-next-fp8-b70/CLOSEOUT-20260913.md),
  model, runtime and evidence. No new experiment or weight relocation is queued.
- **Storage:** about 33 GiB of cold compiler caches were preserved in 2.64 GiB of
  verified compressed archives under `/home/steve/git-archives/cache-consolidation-20261006/`;
  only their unpacked copies were removed, initially freeing about 38 GiB.
  Full byte comparisons passed before removal; hashes and restore commands are in
  [the consolidation receipt](data/maintenance/consolidation-20261006/summary.json).
  A follow-up preserved eight inactive August research build trees (18.94 GiB)
  in 2.49 GiB of verified archives, bringing available space to about **54 GiB**.
  Complete member inventories and repeated byte comparisons passed. Original-path
  restore commands are in [the staging receipt](data/maintenance/staging-consolidation-20261007/summary.json);
  restore these trees before replaying their historical launchers.
  The internal archives are preservation; a separate physical copy is now verified
  below. The original SMART-command USB incident remains recorded in
  `data/maintenance/consolidation-20261006/`; do not repeat bridge passthrough.
- **Backup, completed October 6 21:00 EDT:** ordinary EX400U I/O passed a bounded
  pilot, then 61.45 GiB of selected research plus Git history/tracked files were
  preserved in a 25.63 GiB backup set at
  `/mnt/usb-models/lab-backups/steve-b70s-20261007/`. All nine files passed full
  SHA-256 read-back after clean unmount/read-only remount; Git restore/fsck and
  pinned LTX file restoration passed. No new storage/GPU fault appeared. Four
  Flash-Next run/supervisor trees (121 files) also gained verified internal copies.
  All originals remain; this is a selected additional backup, not a whole-machine
  backup or long-term drive certification. **EX400U is cleanly unmounted.** Keep it
  for planned cold-backup operations, not active runtime work. Do not force a mount,
  run filesystem repair or use the data-erasing firmware reinitialization tool.
  [Review and restore evidence](notes/2026-10-06-ex400u-backup-review.md).
- **Qwen 27B TP2:** a separate [correctness release candidate](experiments/qwen38-27b-b70/release-candidates/20261006-tp2-state-fix/README.md)
  passed 20 overlay and 14 offline-preflight CPU tests; published package pins
  remain unchanged. The preflight refuses unqualified kernels; actual serving
  integration remains pending. Local source confirms that missing/excluded plugins
  may be ignored, so the owning runtime must verify activation inside every worker.
  TP1 needs a separate kernel port. This host still lacks the documented R314
  build/image; the exact FP8 model is now verified separately below.
- **Coding worker and lab memory:** the owner chose a bounded usefulness trial
  before connecting these projects. The [new evaluation packet](experiments/local-coding-worker/evaluation-20261007/README.md)
  contains eight historical coding repairs and ten source-backed research
  questions. CPU controls are verified; both the separate 4B and 27B trials
  produced **zero completed patches in two attempts each**, under different
  model/runtime/budget identities. Judge reviewed patches rather than token
  speed. The worker can now mount a separate read-only acceptance folder
  and record/check its hashes. This does not qualify a model or serving package.
  Pinned worker dependencies and the CPU image are now installed; all 107 worker
  tests pass. Both initial tasks also passed their real full-snapshot Docker
  controls (four baseline/fixed checks), using disposable `/dev/shm` snapshots.
  Snapshot receipts are preserved at `/home/steve/worker-container-controls-20261007/`.
  Two hash-identical 0.8B weight-cache copies were consolidated into one read-only
  inode, preserving both model paths and recovering 1.63 GiB. The separate 0.8B
  workflow pilot closed at its format gate; the 27B trial is now closed as described above.
- **27B model and next steps:** the corrected download manifest includes required
  tokenizer/runtime files while preserving all 66 weight pins; five offline
  controls cover both wrappers. All 80 files (30.89 GB) passed publisher hashes
  and a full cold-copy read-back after clean remount. They remain under
  `/mnt/usb-models/worker-models/qwen38-27b-fp8-20261007/017b9c7af6b5689d5dd426a76e0bc077eb5ca20a/`.
  Only the temporary RAM copy was removed after another full hash check and clean
  server stop. [Preservation receipt](experiments/local-coding-worker/qwen27b-target-only-pilot-20261007/model-preservation/summary.json).
  The references-only trial used a freshly verified RAM restore, then released
  it after healthy shutdown and another full hash check. The downloader now resumes preallocated aria2 partials
  correctly. The separate R276 trials and failed usefulness outcomes are
  preserved; they do not qualify the newer speculative package.
  Qualify the corrected package when its exact inputs and host ownership
  are available. The 50 GiB reserve is now met, with only about 3 GiB above it;
  this does not admit a large build/download on the root filesystem.
  Use `scripts/check-storage-headroom.py` before new writing jobs, including
  estimated peak output/cache/build bytes. Worker snapshots now enforce admission
  before creating their archive or two source copies, retaining 50 GiB by default.
  All 119 worker tests passed. A real check on this repository refused the job
  before creating any snapshot; it would need about 4.25 GiB more headroom.
  [Check evidence](data/maintenance/worker-storage-admission-20261007/real-refusal.json).
  This protects initial snapshot creation, not later build/log writes. A verified additional research backup
  now exists; keep the internal sources and the documented backup-scope limits.
- **RAM, owner decision October 6:** no replacement in 2026. Blocks 53–57
  (10 GiB) were rechecked offline and `b70-offline-bad-memory.service` enabled.
  Keep that mitigation unchanged; replacement is not an immediate work item.

[Follow-up decisions and recovery checks](notes/2026-10-06-storage-and-recovery-followup.md)
record the archive restore rehearsal, isolated CPU fixes and remaining priorities.

Older four-card entries below are retained history, not instructions to resume
LTX, start a server, or change host settings. The two-card host has its own live entry.

Latest two-card review: **2026-10-07 07:56 UTC**. The direct-source screen is
complete, preserved and independently reviewed. Its server stopped, both cards
were released at 07:45:31 UTC, and health passed at 07:45:39. Both context owner
units are inactive; no model server remains running. The [updated website](https://skindeep.ai/context-results.html#bookkeeping)
is live at site commit `4351fe3208352f78d584cd477d91c75780f739c5`; both changed pages
were verified byte-identical to the reviewed build.
[Publication check](experiments/qwen38-27b-b70/data/2026-10-07-context-site-publication.json).
No additional model experiment is queued.

## 2026-10-07, project decision recall workflow

The [twelve-question application check](experiments/project-decision-recall-20261007/RESULTS.md)
is complete. Ordinary search/read covered all 38 required criteria and all twelve
questions. A separate complete-source delivery check covered 37 criteria fully
and missed one required caveat, despite quoting the right evidence. The original
full-source attempt remains a recorded failure: its display truncated and its
first submission failed the required format. No answer was repaired.

The [reviewed decision brief](experiments/project-decision-recall-20261007/DECISIONS.md)
links exact historical sources. Use original source access and explicit answer
completeness checks; no structured memory store or worker integration is admitted.
The selected records are agent-curated with claimed owner input, not authenticated
human transcripts. Fresh hosted assistant sessions supplied these answers; this
does not qualify local Qwen, general memory or speed. No local model server or
GPU experiment was started. Existing context owner units remain inactive.

## 2026-10-08 21:10 EDT, two-B70 host: retention study decided; archive-and-recall is the method; no more full-day runs

**Cards empty.** LongMemEval stage 2 (judged by the 27B, secondary): whole history in one call 46/56;
archive-and-recall with free notes 42/56 at 341 s and 10.5K tokens per question; summarising 19/23 at 960 s and
58K tokens (stopped after 23 by owner rule: "Do not do full day soaks like this; it's a waste of time"). On the
same 23 questions: 21 / 20 / 19. Archive-and-recall is recommended inside a 32K budget: same accuracy, a third
of the time, a sixth of the tokens. Its gap to whole-history reading is abstention (1/8 vs 4/8), the next lever.
[Result note](experiments/qwen38-27b-b70/notes/2026-10-08-longmemeval-stage2-result.md),
data `experiments/qwen38-27b-b70/data/2026-10-08-longmemeval-stage2/`. H3 live session earlier today: 17 passes,
136 clips (8-step turbo path, 960x544) streamed to the owner's meshcast endpoint 09:41-13:33, no faults.
Standing rule from today: any study must decide within a few hours (pilot, concurrency, stop early).

## 2026-10-08 09:35 EDT, two-B70 host: H3 live stream is on air; retention stage 2 interrupted by a memory-guard stop, resumes after the live session

**Live H3 video is streaming to the owner's meshcast.io RTMP endpoint** (unit `h3-stream`, key in
`~/.config/h3-stream/meshcast.env`, never in the repo). Unit `h3-live` runs duet generations (960x544, 124 frames,
51 steps, two cards, one process each, seed stepping from 1000) over
`experiments/minimax-h3-b70/data/live-prompts.txt` until 13:31 EDT or `STOP-LIVE` under the bench dir; each
finished clip is picked up by its receipt and cut in. **Fault of the day:** the first stream start at 09:27:34
used 830 MB host RAM (the tool cached four decoded clips) beside the stage-2 server, whose memory guard sat at
2.1 GiB available; the guard killed the server at 09:27:47 (`campaign-c2/tp2-lme2-w65536/MEMORY-GUARD.json`).
No GPU fault; cards left empty. `h3_stream.py` now streams one frame at a time (127 MB peak, measured).
Rule reaffirmed: nothing new starts beside a research server when available RAM is within a few hundred MB
of the guard floor. Stage 2 state: archive-and-recall 52/56 graded (kept; finished jobs are skipped on
resume), summarise 0/56. The live session chains into `launch-d.sh` (unit `ctx-lme-stage2b`, `campaign-c3`,
`client-d.sh`), which finishes the remaining 4 + 56 trials and judges (about 17 h, so tomorrow morning).

## 2026-10-08 03:50 EDT, two-B70 host: retention study on an outside benchmark, stage 1 done, stage 2 running

**One two-card server is up for the study (unit `ctx-lme-stage2`, about 19 h); it stops itself.** LongMemEval
(56 questions, ~110K tokens of chat history each): whole history in one call **46/56** judged; pilot (7 questions)
summarise-at-75% 6/7 at 17 min and 62K tokens written per question, archive-and-recall with free notes 4/7 at
6 min and 10K tokens, plain files agent 1/7. Judge is the 27B itself (secondary) until a GPT-4o key is given.
[Interim note](experiments/qwen38-27b-b70/notes/2026-10-08-longmemeval-stage1-result.md),
data `experiments/qwen38-27b-b70/data/2026-10-08-longmemeval-stage1/`. Stage 2 runs both deciding arms on all 56.

## 2026-10-07 23:30 EDT, two-B70 host: the many-users profile is an accepted package profile (875 tok/s at 64 users, exact)

**No model server is running.** One acceptance session through the public two-card package launcher
(`run-fp8-tp2-acceptance-session.py --commit 8a46c0cae --multi-user`, unit `fp8-tp2-acceptance-mu`) passed all
twelve existing gates (strict 12/12 identical to no-MTP, six practical requests, owned clean stop; recommended
profile now 90.31 tok/s median of 90.37/90.25) and the new gate: `serve.py start --profile multi-user`, and at
**16, 32 and 64 users every answer equal to the frozen single-user answer**, short ladder and 2K-8K long-prompt
suite, two passes each. Totals together: short 415 / 653 / **875** tok/s, long 51 / 60 / 66 tok/s.
Packet `experiments/qwen38-27b-b70/data/2026-10-07-fp8-two-card-multi-user/` (130 files; the collector's
DEFAULT now points here; the 2026-10-04 packet's declared drift is retired). `package.json` carries
`recommended_setup.multi_user_profile` (written by the publish script from the packet), the package README and
neural.download's top pick say "Ready to try". Runbook: `notes/2026-10-07-multi-user-profile-acceptance-plan.md`.
Not covered: a clean host; drafting with several users (needs R314, local only). Next on the cards: the
LongMemEval retention study, stage 1 (F control on 56 questions, then the 7-question pilot of three arms).

## 2026-10-07 23:00 EDT, two-B70 host: public context numbers re-verified on the fixed checker; site revamped; packaging and streaming prepared

**No model server is running.** The 2026-10-06 review's checker patch is applied to the live harness
(commit 414eb6374; 9/9 unit tests, 22/22 stub checks). The two quoted-events runs published on
skindeep.ai were repeated on the same task bytes with the patched checker and scored the same:
480K stream **10/10** in 1,165 s (was 1,173) and the million-token stream **24/24** in 2,867 s
(was 2,874), the latter call-for-call identical. Evidence `experiments/qwen38-27b-b70/data/2026-10-07-context-reverify/`,
note [re-verification](experiments/qwen38-27b-b70/notes/2026-10-07-context-reverify-fixed-checker.md).
The first attempt at the original 262K window was stopped by the host-memory guard (no GPU fault);
the repeat ran at a 65K window, which the agent never approaches.

Also tonight: neural.download leads with the two 27B FP8 packages, the rest collapsed, old many-user
figures labelled "throughput ceiling, not exact" (2d655c27e); the two-card package gained a
`multi-user` profile (64 users, exact by construction, acceptance pending, db98ba0d4) with an
acceptance stage prepared (715b9cc56, runbook `notes/2026-10-07-multi-user-profile-acceptance-plan.md`);
`experiments/minimax-h3-b70/scripts/h3_stream.py` streams finished lossless clips to RTMP/WHIP
(tested on a local sink; needs the owner's key); and the LongMemEval retention study is built and
wiring-checked (`notes/2026-10-07-longmemeval-retention-prereg.md`), not yet run. Next on the cards:
the multi-user acceptance session, then the retention pilot.

## 2026-10-07, two-B70 host: short-document decision settled

The [direct full-source baseline](experiments/qwen38-27b-b70/notes/2026-10-07-full-source-screen-result.md)
answered **24/24 on both documents**, including all ownership joins, in **27.75 and
34.86 seconds**, one cold request each. Exact source-only streaming took roughly
199–225 seconds per document including ingestion, answering and persistence.
This is a static final-answer comparison with a different information schedule
and total possible computation, not a general speed qualification or an
intermediate-state guarantee. Start with full source for these short documents;
close further retrieval-interface tuning for this use case.

The [complete history study](experiments/qwen38-27b-b70/notes/2026-10-07-history-state-study-result.md)
is negative. All four source-only conditions scored 24/24. History access scored
19/24 in three conditions and 23/24 in the fourth, despite all 96 numeric
checkpoints and 202 quoted postings being exact. All sixteen wrong joins used
an initial ticket owner's balance after ownership transferred. Ingestion prompts
and replies matched across access modes within each document/bookkeeping pair;
the divergence occurred while answering. Its fixed extension gate failed.
Keep t03/t04 unused; no holdout is admitted.

Both studies are fully preserved and independently replayed from separate
restored copies. The [history inventory](experiments/qwen38-27b-b70/data/2026-10-07-history-study-result/inventory.json)
binds 194 files and all eight byte-verified archived databases. The
[direct-source inventory](experiments/qwen38-27b-b70/data/2026-10-07-full-source-result/inventory.json)
binds 33 files, including both complete raw requests/responses and health receipts.
All 188 history calls and both direct calls reported zero cache reuse. No retry,
cap change, replacement trial, server restart or host/device setting change was
used. The direct client/auditor/supervisor passed 58 CPU tests; all 35 guide checks
passed. Both fresh servers passed all 12 strict reference prompts.

The [research priorities](experiments/qwen38-27b-b70/notes/2026-10-07-context-research-priorities.md)
and [CPU reviews](experiments/qwen38-27b-b70/data/2026-10-07-context-cpu-review/inventory.json)
separate numeric bookkeeping from general factual memory and prompt bounds from
total resource costs. Each temporal source is only about 1,500 tokens and fits in
one prompt. Future model work needs a concrete streaming/audit requirement or
independently sourced relevant history; another short seed/size matrix is not
the next step. Numeric snapshots cannot certify textual ownership or policy facts.

The earlier [sparse replication](experiments/qwen38-27b-b70/notes/2026-10-07-sparse-state-replication-result.md)
repeated the original exact/cold task's 21.6% elapsed reduction, but the new dispatch
archive invented zero at seven early checkpoints despite 24/24 final answers.
That pair is not a qualifying speed comparison. Its evidence and negative gate
remain preserved separately. Frozen sources and old negative outcomes stay intact.

The [temporal reference packet](experiments/qwen38-27b-b70/data/2026-10-07-temporal-development/review-note.md)
has two independent assistant annotations agreeing on 201 events, 48 tables and
96 answers; a separate source replay confirms them. Every historical balance
differs from final, but historical ownership coverage is narrower. Forty-eight
CPU fixtures fit the unchanged budgets; these are software checks, not model
results. The documents are short, assistant-authored and use controlled posting
grammar. The [history engine](experiments/qwen38-27b-b70/scripts/context/history_v1/README.md)
has nineteen CPU tests and twelve separate snapshot-audit tests passing.

Earlier findings remain in their own notes: the
[semantic diagnostic](experiments/qwen38-27b-b70/notes/2026-10-07-context-semantic-result.md)
found 84/84 quoted and summary answers versus 82/84 archive, with four wrong
archive checkpoints; the [initial sparse screen](experiments/qwen38-27b-b70/notes/2026-10-07-sparse-state-result.md)
produced the narrow wide-table signal. [Revision 3](experiments/qwen38-27b-b70/notes/2026-10-07-durable-context-r3-result.md)
and [revision 4](experiments/qwen38-27b-b70/notes/2026-10-07-durable-context-r4-result.md)
failed their original gates; their holdouts remain unused. Preserve the bounded
failures and unstarted rows rather than retrospectively completing those studies.

## 2026-10-06 23:52 EDT, two-B70 host: protocol repaired; reasoning gate failed

**No model server is running or queued.** All six revision 2 development trials
completed, with all 24 question IDs present and no lost partial answers. Summary
scored 36/48, archive 40/48 and quoted events 41/48 across both writing styles.
Both structured methods scored 24/24 on the report style but failed historical
questions in dispatch style. All 288 original batches survived exactly and all
192 structured-table checkpoints were correct: the remaining problem is using
the right evidence for the final question, rather than retaining the source.

The server passed 12/12 reference checks and both extraction diagnostics. The
complete development gate failed, so fresh held-out seeds were untouched and no
speed result qualifies. The owned server stopped at 03:51:33 UTC; release was
confirmed at 03:52:28 UTC. `ctx-durable-r2.service` exited with the expected
quality-gate failure after cleanup. Full output remains at
`/mnt/fast-ai/bench-results/context-durable-r2-20261007`.

[Plan](experiments/qwen38-27b-b70/notes/2026-10-07-durable-context-r2-plan.md),
[results and next development lever](experiments/qwen38-27b-b70/notes/2026-10-07-durable-context-r2-result.md),
and [audited native evidence](experiments/qwen38-27b-b70/data/2026-10-07-durable-r2-result/audit.json).
The next lever is bounded reasoning during final answering, with ingestion and
retrieval fixed, in a new frozen development revision. Do not edit the preserved
r2 sources or weaken its gate after seeing the result. Larger streams and speed
tuning remain deferred.

## 2026-10-06 23:29 EDT, two-B70 host: durable pilot stopped; quality gate failed

**No durable experiment is running or queued.** The pilot stopped at 02:15 UTC:
16 trials completed, the seventeenth hit the retrieval cap, and the last did not
start. The owned server stopped; GPU release was confirmed at 02:16:46 UTC.
Strict qualification passed 12/12 and both extraction diagnostics passed, but
the end-to-end quality gate failed and no speed result qualifies.

Quoted events got 46/48 current values, 7/48 historical details and 0/48
cross-references across six trials. All original batches survived exactly; state
was correct at 287/288 quoted checkpoints. Eight quoted/archive final replies
combined partial answers with another search request, which the harness wrongly
treated as a finished submission. The failed summary trial repeated one search
nineteen times. [Result and protocol findings](experiments/qwen38-27b-b70/notes/2026-10-07-durable-pilot-result.md)
include all native evidence and unequal-subset caveats.

Next: a separate development revision for unambiguous retrieval/submission,
partial-answer preservation and complete end-to-end development checks before
fresh held-out seeds. Preserve this failed frozen attempt. No new GPU run has
been scheduled; larger streams and speed tuning remain deferred.

## 2026-10-06 21:50 EDT, two-B70 host: handoff repaired; durable v2 in preflight

The protected legacy campaign ended and confirmed its server stop. The first
queued coordinator then failed its passive port check at 01:27 UTC (`EADDRINUSE`),
before health probes, server launch or model work. Its failure is preserved;
it was not still waiting when checked at 01:46 UTC.

**`ctx-durable-pilot-v2.service` is active in preflight**, output
`/mnt/fast-ai/bench-results/context-durable-v2-20261007`. The coordinator now waits
up to 180 seconds for socket teardown. This explicit new attempt requires proof
that v1 did no device/server work, retains its original fault baseline, and
allows only the coordinator code to differ. Twenty CPU tests and independent
review passed. [v2 receipt](experiments/qwen38-27b-b70/data/2026-10-07-durable-host/v2/receipt.json).
The model-facing harness, tasks and gates remain frozen. Do not launch another
GPU lane alongside this owner; live `status.json` supersedes this snapshot.

## 2026-10-06 20:31 EDT, two-B70 host: next durable experiment queued and waiting

**`ctx-durable-pilot-v1.service` is active, waiting for the protected plan-E
supervisor.** It has sent no model requests. Its live status and output are in
`/mnt/fast-ai/bench-results/context-durable-v1-20261007`; the
[queue receipt](experiments/qwen38-27b-b70/data/2026-10-07-durable-host/receipt.json)
records the pinned implementation/dependencies and the observed waiting state.

After a clean release, it will run bounded health checks, start one pinned
Plan-E-profile server, require the full strict qualification and both fixed
extraction diagnostics, then execute the eighteen-trial held-out pilot. It stops
its own server afterward. Failure leaves a recorded reason and does not retry
or restart the server. Existing Docker stop timeout and emergency memory-guard
behavior remain unchanged. **Do not launch another GPU lane alongside this
queued owner.** See [operation and cancellation](experiments/qwen38-27b-b70/scripts/context/DURABLE-HOST-RUNNER.md).

Seventeen host-coordinator tests and independent operational review passed;
58 durable harness tests remain passing. The existing supervisor/server were
still running when this service entered `waiting`. Model validation remains pending.

## 2026-10-06 20:22 EDT, two-B70 host: million-token quote run verified; handoff being prepared

The million-token quoted trial completed **24/24 in 47.9 minutes**, nonvoid.
Exact stream/answer hashes match read mode's **23/24 in 62.2 minutes**; the 23.0%
elapsed reduction describes one pair. The new [31-attempt snapshot](experiments/qwen38-27b-b70/data/2026-10-05-context/canonical-2026-10-07/manifest.json)
retains every prior attempt; 29 are completed, one interrupted and one incomplete.

**The retention seed-1 quote block did not run:** planning failed because its task
file was absent. The existing 35/36 in that directory is seed 0. The wrapper
continued; its future `plan complete` marker cannot certify every requested cell.
The 480K quoted seed 1 is running, with 21 actual questions. See the
[follow-up audit](experiments/qwen38-27b-b70/notes/2026-10-07-context-campaign-followup.md).

The user authorized proceeding with the next experiment. A separate one-shot
host coordinator is being prepared for the frozen durable pilot; it must wait
for the protected supervisor's full lifetime and clean server release, then
qualify a fresh server and enforce both development gates. No new model request
has been sent and the protected plan-E code/queue remains unchanged.

## 2026-10-06 19:59 EDT, two-B70 host: evidence pipeline and durable pilot ready; no new model results

The [canonical historical manifest](experiments/qwen38-27b-b70/data/2026-10-05-context/canonical-2026-10-06/manifest.json)
contains 28 completed, one interrupted and one incomplete attempt. Verified grader
counts now drive the site’s selected rows; unsuccessful attempts remain visible.
Unknown old runtime/checker identities remain unknown rather than being filled
from the current checkout.

A separate [durable pilot](experiments/qwen38-27b-b70/scripts/context/durable/README.md)
archives source text before delivery, applies quoted events transactionally, and
preserves records across restart. Its frozen eighteen-trial comparison uses
three methods, equal retrieval permissions and current/history/cross-reference
questions. It does not replace the active CLM code. Quote validity still does
not prove correct semantic interpretation or complete extraction.

[CPU validation and frozen tasks](experiments/qwen38-27b-b70/data/2026-10-06-durable-context/README.md):
58 durable tests, nine exporter tests and 11 site-import tests pass. Six oracle-fed
stub trials complete; these provide no model quality or speed evidence.

**Protected active work remains `context-planE-a1`, port 18196.** Its supervisor,
server and Harbor client were still running at 23:59 UTC. No new inference was
sent and no active code or queue was changed. After it releases the machine,
review its completed artifacts and run the normal preflight, then the frozen
seed-7 extraction diagnostic in both styles. Only matching, perfect diagnostic
results unlock the held-out pilot. The [preregistered protocol](experiments/qwen38-27b-b70/notes/2026-10-06-durable-context-prereg.md)
sets correctness before speed; wider streams and new optimizations follow only
if this comparison supports them. No unattended server launcher was installed.

## 2026-10-06 19:27 EDT, two-B70 host: context results reviewed; experiment still active

**The matched 480K narrative runs both answered 10 of 10 questions correctly, not the 24 of 24
previously reported.** Quoted events took 19.6 minutes; the read-mode agent took 25.7 minutes
(about 24% less elapsed time for quoted events on this one seed). The million-token read-mode
run is verified at 23 of 24. A claimed second 480K seed has no completed artifact and is withdrawn.

- Quoted reruns: retention seed 0 **35 of 36** in 5.7 minutes; density 12 **16 of 16** in
  7.4 minutes. These are completed. Quoting plus arithmetic in code does not guarantee correct
  event interpretation or completeness. Review found that the merged-batch fallback can accept
  model-authored text and lose it from the archive; an unapplied repair is being validated.
- **Protected active work:** `context-planE-a1` on the two cards, endpoint port 18196, output
  `/mnt/fast-ai/bench-results/context-planE-a1`, plan `/mnt/fast-ai/bench-results/context-plan-20261006e.sh`.
  The existing supervisor started its server at 19:20 EDT. Review leaves its server, plan and live
  harness unchanged. The plan includes quoted 1M, quoted second seeds, denser 480K reading and
  remaining retention/ledger trials; a queued entry is not evidence of completion.
- Memory guard remains 1.6 GiB under the owner's earlier authorization. The recorded 23:08 fault
  and passed health probe remain in the [fault note](experiments/qwen38-27b-b70/notes/2026-10-05-fault-2308-guard-kill.md).
- [Review and repair status](experiments/qwen38-27b-b70/notes/2026-10-06-context-review.md) ·
  [corrected results](experiments/qwen38-27b-b70/notes/2026-10-05-context-research-results.md).

**Next:** assess completed plan-E artifacts, then validate the checker repair as a separately
identified experiment. Parallel extraction and the one-card comparison remain proposed work.

## 2026-10-05 23:10 EDT, two-B70 host: the model read 1.8 times its window by understanding, every answer right; the comparison matrix and an explainer page are up

**A read-mode self-editing agent at a 32K budget read a 480K-token narrative stream (1.8 times the whole window),
answered 10 of 10 final questions correctly (denominator corrected 2026-10-06), in 26 minutes with never more than 24K tokens in view. Files plus
search stay the fastest route when code can do the reading. Keeping everything in the big window failed twice at
the window edge on long jobs. All of it is one or two seeds, one machine.**

- **Comparison on the 121K running ledger (no files):** paper's self-editing agent 19 of 24 in 64 min; summarise
  at 75 % 24 in 41 min; keep everything 24 in 26 min on one seed and 0 on the other (ran out of window with an
  exact table); improved agent 24 and 21 in 15-21 min; **thinking-reduced improved agent 24 and 24 in about 6 min**.
  With files allowed: 24 in under 2 minutes, context under 9K, at 121K and at 478K.
- **Reading by understanding (narrative text, 3 changes per 2K batch, calibrated so a single step is about 98 %
  right):** read-mode agent 23 of 24 and 18 of 18 at 119K (5 minutes each), **10 of 10 at 480K**; keep everything 24
  at 119K in 20 min; files 24 in 5 min. Before the loop guards the same agent got 20 of 24 at 119K and failed at
  480K; the losses were the loop repeating itself with thinking off, not the reading.
- **What an edit costs with the exact cache:** re-read from the last kept state before the edit to the end: 0.7 to
  16 s near the end of a 30K-200K context, the whole cold read (11 s to 152 s) near the start. The paper's suffix
  reuse avoids that by reusing stale cache; an explainer page with diagrams is on the research site
  (skindeep.ai, "Changing the context without re-reading it").
- **Standard gate with the cache on:** 12 of 12 exact twice, 89.6 tok/s against 88.5 off; write rate unchanged.
- **Prose ledger as first built** (40-95 interleaved changes per batch) is beyond the model in a single step (38-53
  %); that run was not a reading test and was recorded as such.
- Notes: [results for the owner](experiments/qwen38-27b-b70/notes/2026-10-05-context-research-results.md),
  [time and reuse](experiments/qwen38-27b-b70/notes/2026-10-05-context-time-and-reuse.md),
  [self-editing comparisons](experiments/qwen38-27b-b70/notes/2026-10-05-self-editing-first-comparison.md),
  [follow-up proposals](experiments/qwen38-27b-b70/notes/2026-10-05-context-followup-ideas.md).

**Doing next:** second seeds and the window-shown keep-everything retry (running); then harder reading (6 and 12
changes per batch), a 1M-token stream (four times the window), the files baseline at 480K; then the one-card server
(44K window) with the exact cache, which is the small-video-memory case the owner asked about.

## 2026-10-05 04:40 EDT, two-B70 host: context research, results of the night so far

**The 27B can open its whole 262,144-token window with nothing quantized, an exact prefix cache now makes a long
context cheap to keep using, and the first measurements say a small, pruned working context is still the better
place to be.** Work continues; the self-editing comparison is running.

- **Window.** Opens at 262,144 tokens, 16-bit cache, drafting on. Reading: 3,300 tok/s at 8K falling to 1,550 at
  250K (a cold 200K prompt takes about two minutes). Writing: 127 tok/s at 8K, 48 at 120K, 26 at 250K.
- **Recall by length (720 codes asked).** Exact at 60K. From 120K to 250K about one lookup in forty returns a
  look-alike record's code (the neighbour, or a number sharing most digits); never an invented value, and no
  cliff. The "empty answer above 212K" I reported earlier was a bare-text prompt artifact; chat form answers.
- **Exact prefix cache (new add-on `b70-prefix-cache-exact`).** The stock cache also stores what the model wrote,
  which falls outside "a cached answer equals a cold answer". The add-on stores only what was made while reading a
  prompt. With drafting on: 99 of 99 cases identical to a server without the cache, second and third turns
  included; a question over a cached 200K context starts in 2 s instead of 114 s; an edit in the middle of a long
  context resumes from just before the edit. Cost: cold reads are 14 to 27 % slower (832-token pieces).
- **Self-editing, first comparison: it measured the wrong thing, and that is a finding.** In all 12 trials the
  model saved the data to files and searched them at the end, keeping its context at 11-35K tokens on a 140K-token
  task. Every lost answer came from one shell mistake while saving. A rebuilt comparison (files forbidden or
  allowed, a second task with overwrites, arms that drop old thinking) is on the cards now.
- **A CPU-side cleaner does not turn 32K into 100K.** On 5 million tokens of real agent sessions, strictly no-loss
  cleaning frees 1.8 %; moving large tool outputs to disk 7.5 %. The one sizeable lever: the 27B re-sends all its
  earlier thinking on every call, about 10 % of a typical call and up to 56 %.
- **One-step decisions.** Restricting the first token to the allowed labels gave the same answer as decoding on
  80 of 80 items. The time saved is in not thinking (0.09 s against 0.59 s), not in skipping the label.
- **Host memory is the tight resource on this host.** The two-card server leaves about 3.2 GiB; a request for
  token scores with drafting on, a heavy client, or CPU test jobs beside it tripped the memory guard five times
  tonight before the cause was found. No GPU fault all night.
- Notes: [window, recall, decisions](experiments/qwen38-27b-b70/notes/2026-10-05-context-window-prereg.md);
  [exact prefix cache](experiments/qwen38-27b-b70/notes/2026-10-05-prefix-cache-exactness-prereg.md);
  [cache reuse rules from the engine source](experiments/qwen38-27b-b70/notes/2026-10-05-prefix-cache-reuse-rules.md);
  [self-editing comparisons](experiments/qwen38-27b-b70/notes/2026-10-05-self-editing-first-comparison.md);
  [CPU cleaner census](experiments/qwen38-27b-b70/notes/2026-10-05-context-hygiene-census.md).

**Doing next:** the second self-editing comparison (running), then the winners at longer sizes; a scores-level
check of the cache; larger reading pieces that keep the cache exact.

## 2026-10-06 01:00 EDT, four-B70 host: LTX 2.5 at 27.5 fps over a ten-minute run, 30.8 fps at batch 4; the baseline ruling is still open

**Packet 97 moved the second decode worker from the busiest sampler card to the idle one. Everything else is packet 96.**

- **No ruling needed:** batch 1 with the decode worker on card 2 is byte-exact on today's references at **1.308 s per
  clip** (was 1.348).
- **Needs the owner's ruling (batch clips are a different take of the same prompt, see the 10-04 entry):**
  two batch-2 jobs **0.927 s per clip (27.0 fps)**; held over a 600-prompt arm at **0.910 s per clip (27.5 fps), 613 of
  613 clips exact, steady, never more than 1.8 s behind a steady pace**; two batch-4 jobs **0.812 s per clip (30.8 fps)**,
  131 of 131 exact against the batch-4 references. A third decode worker makes both slower.
- **Measurement correction:** the client had been polling every queued prompt each cycle and slowing the server in
  proportion to the queue; fixed on 10-05. The 10-04 figure of 1.026 s became 0.992 s on the same server configuration.
- **Lost day:** 2026-10-05 02:11 to 10-06 01:43 UTC, a debugger attached to a live server hung and its watcher had no
  deadline; recorded in the packet 96 results note with the rules that follow from it.
- Zero GPU faults and zero lockups in 38 hours on kernel 7.0.0-39, about thirty server runs.
- [Packet 97 results](experiments/ltx25-b70/notes/2026-10-06-packet-97-results.md).

**Doing next:** measuring what 640x384 output would cost (probe running), then the two-card machine question and
clip-to-clip continuation, both the owner's calls.

## 2026-10-04 20:40 EDT, four-B70 host: LTX 2.5 reached 24.4 fps with two clips per transformer pass; the owner must rule on the new baseline

**One clip every 0.992 s (25.2 fps equivalent; the budget is 1.042 s; 2026-10-06 01:49 UTC, 111 of 111 exact), every clip byte-identical to its reference.
The references are new ones made with two clips per pass, so this counts only if the owner accepts them.**

- **What changed.** One sampler job now carries two clips through the transformer together, so the 42 GB of weights
  are read once for both (packet 96, `LTX_SAMPLER_BATCH=2`). Three such jobs run at once on the four-card block
  layout, with one shared graph memory pool per card and worker (`LTX_SAMPLER_SHARED_POOL=1`).
- **Why it is not cheating, and why it still needs a ruling.** At batch 2 (and 4) a clip's bytes depend only on its
  own prompt and seed: the server regenerated every fixture with other batch neighbours and in other slots and got
  identical bytes (hundreds of clips, five servers, three block layouts). But a batch-2 clip is not byte-identical to
  the same clip made alone: matrix products round differently with more rows, and 11 sampler steps turn that into a
  different take (picture PSNR 17-29 dB against today's references, the same range as the text-window milestone).
  Same mathematics, different rounding. **Decision needed from the owner: may batch-2 (and batch-4) clips be the
  baseline?** Until then the standing exact figure on today's references is 1.348 s per clip.
- **Also new and needing no ruling:** the shared graph pool is byte-exact on today's references (126 of 126) and
  cuts a sampler worker's video memory from about 2.8 GiB per card to about 0.25 GiB.
- **Caveats:** 120-prompt arms (the measurement client's polling had been slowing the server in proportion to the
  queued prompts; fixed 2026-10-05, which took the same configuration from 1.026 to 0.992 s per clip; a 600-prompt
  arm under the old client ran at 1.131); clips arrive in pairs, so playback needs a small buffer; these are
  independent clips back to back, not clip-to-clip continuation. A day was lost between 2026-10-05 02:11 and
  2026-10-06 01:43 UTC to a hung debugger step with no deadline on its watcher (recorded in the results note).
- **Open:** two batch-4 jobs fail at their first capture with no recorded error (one batch-4 job works: 1.209 s per
  clip, exact against batch-4 references).
- Zero lockups and zero GPU faults in nine and a half hours on kernel 7.0.0-39, about fifteen server runs.
- [Results](experiments/ltx25-b70/notes/2026-10-04-packet-96-results.md);
  [why batching is row-independent](experiments/ltx25-b70/notes/2026-10-04-batch-row-independence-probe.md);
  [packet build](experiments/ltx25-b70/notes/2026-10-04-packet-96-build.md).

**Doing next:** repeat the 24.4 fps configuration and run it longer; find the batch-4 two-job failure; then decode
capacity and uneven clip spacing.

## 2026-10-04 15:25 EDT, four-B70 host: the video server was using host RAM equal to its video memory; found and fixed

**A four-card process was costing a GiB of host RAM for every GiB of video memory. One runtime setting removes it.**

- **What happened.** The LTX server with three clips in flight was killed by the out-of-memory killer (14:18 EDT,
  no GPU fault). With two clips in flight the GPU driver was holding 92.6 GiB of the 115.6 GiB of host RAM
  (`GPUActive` in `/proc/meminfo`), while the server's own memory was under 10 GiB.
- **Cause.** In a process with several cards open, every GPU buffer is shared with the other cards, and with the
  runtime's default deferred backing each shared buffer also holds system pages of its own size. A one-card
  process does not pay this. Compute speed was never affected.
- **Fix.** Launch with `NEOReadDebugKeys=1 EnableDeferBacking=0`. Placement only, no arithmetic change. In a small
  four-card probe: host RAM held 12.6 GiB -> 0.3 GiB, same speed, identical results.
- **On the real server (runner 95b).** Four-card layout, three clips in flight, the combination that was killed:
  driver-held host RAM peaked at 3.6 GiB, swap untouched, 10 of 10 and 115 of 115 clips byte-identical to the
  references, 1.387 s per clip. The two-card, two-clip control with the setting: 116 of 116 exact,
  **1.358 s per clip** (1.413 without it), the best figure so far.
- **What it does not fix.** Speed is now limited by compute per clip on the busiest card (about 1.27 s). More
  clips in flight will not reach 1.042 s; less GPU work per clip is the next lever.
- Zero lockups and zero GPU faults this boot on kernel 7.0.0-39 (4.3 hours up, several server runs).
- This is a per-process environment setting. No host memory setting, power setting, kernel or driver was changed.
- [Note](experiments/ltx25-b70/notes/2026-10-04-host-ram-shadow-of-vram.md);
  [guide section](docs/host-stability-and-fault-diagnosis.md#host-ram-that-vanishes-while-a-multi-gpu-process-runs).

**Doing next:** cutting compute per clip. The candidate is one transformer pass serving two or three clips (weights
read once instead of once per clip); a one-card probe is checking whether each clip's result in a fixed-size batch
depends only on its own inputs. That would change rounding, like the text window did, so adopting it is the
owner's call.

## 2026-10-05 01:30 EDT: optimization work pinned; context-length research under way

**The owner asked to pin the speed work and research context length.** The pin, with the full table and what is
owed before anything is packaged, is
[here](experiments/qwen38-27b-b70/notes/2026-10-05-state-of-optimization-pin.md). Short form, two cards, every
answer exact by construction:

| Users at once | Tokens a second together | Mode |
| ---: | ---: | --- |
| 1 | 90 | drafting on (the shipped recipe) |
| 2 / 4 / 8 | 138 / 227 / 336 | drafting on (needs the new local image and tonight's engine fixes) |
| 16 | about 420 | either |
| 32 / 64 | 657 / 874 | drafting off |

**Context length (new).** The model has 262,144 trained positions and the two-card cache holds about 268,000 tokens
at full precision, so the 33K window was a packaging choice. Under test now: how the server reads, writes and
recalls at 8K to 250K tokens; the model editing its own context (the Context Language Models paper) against simply
keeping everything in the big window; an exact prefix cache so an edit only costs re-reading what follows it; and
reading a decision from the first step instead of decoding it. Plan and test records:
[context plan](experiments/qwen38-27b-b70/notes/2026-10-05-context-window-prereg.md),
[paper review](experiments/qwen38-27b-b70/notes/2026-10-05-context-research-review.md).

## 2026-10-04 20:40 EDT: many users at once, exact by construction: 874 tokens a second for 64 users

**Three times this morning's first table, and every answer is still exactly what a lone user gets**, on short and
long prompts, identical to the published single-user reference. "Exact by construction" means every kernel on the
path has been measured to give a row the same bits alone or in a batch, for the shapes this mode uses.

| Users at once | Tokens a second together | 17:45 today | This morning | Each user gets |
| ---: | ---: | ---: | ---: | ---: |
| 1 (the shipped recipe) | 90 | 90 | 90 | 90 |
| 16 | **419** | 374 | 325 | 26 |
| 32 | **657** | 536 | 428 | 21 |
| 64 | **874** (two fresh servers) | 630 | 488 | 14 |

- **All three rows are exact by construction (a 22:00 note here said only the 16-user row was; that was wrong and
  is withdrawn).** The check behind it had assumed a code path the compiled server never takes. The server's own
  compiled graphs show the small layer in question always uses one path, and that path is measured bit-identical
  for 1 to 512 rows.
- **How.** Two scheduling rules and nothing else: each step is either prompt reading or writing, never both; and
  each long conversation gets its own attention call. New tonight: several short prompts may be read in one step,
  but only inside the range the kernel checks prove identical to reading each alone (each prompt at least 17
  tokens, at most 512 tokens in the step). Long prompts are still read one at a time (66 tok/s together on the
  2K to 8K suite at 64 users).
- **Corrections made today.** The word-picking step is identical for 1 to 32 rows, so this morning's "four rows
  at a time" fix was never needed. The image's own "exact" switches were either not read at all or three times
  slower on long prompts.
- **One user, drafting, now checked end to end.** On the new local images (R313, R314) every kernel the six-word
  check uses is measured identical to plain one-word decoding: main layers, normalisation, word-picking, the
  recurrent kernel (after tonight's fix), attention, and the small projection. Speed unchanged (90.3 tok/s).
  Longer copy drafts pass every gate on two fresh servers: +10 to +17 % on long prompts, 3 % slower on short ones.
- **One user: the drafting kernel was not identical to plain decoding, and is now.** A direct check showed the
  shipped drafting matched plain decoding on every test but not bit for bit inside one kernel. An eight-line kernel
  fix (image R313, local only) makes it identical in all 74 checked cases at the same speed (90.3 tok/s). The
  published packages are still on the old image; moving them needs the image pushed and a fresh acceptance each.
- **In progress:** longer copy drafts for one user (+26 % on long prompts measured; the cause of their wrong
  answers was an out-of-range read after six or more accepted words, now fixed in the overlay and being
  confirmed).
- Notes: [many users](experiments/qwen38-27b-b70/notes/2026-10-04-fp8-multiuser-prereg.md),
  [drafting kernel](experiments/qwen38-27b-b70/notes/2026-10-04-speculation-not-exact-by-construction.md),
  [copy drafts](experiments/qwen38-27b-b70/notes/2026-10-04-copy-draft-sizing-prereg.md).

## 2026-10-04 11:10 EDT: the model-load GPU fault is explained and has a validated fix; no reboot was needed

**The fault that has hit this host since September is one specific thing, and a small overlay now avoids it.**

- **What it was.** When more than about 256 MiB is uploaded to a card in one go, Intel's runtime makes a temporary
  mapping of the host memory and has the card's copy engine read it. Every saved start-up fault (four of them, both
  cards, two kernels) is the copy engine finding that mapping gone. In this model only the 1.27 GB embedding and
  output-layer weights are that large: eight uploads per two-card start.
- **The fix.** The `b70-chunked-upload` overlay sends those uploads in 128 MiB pieces during model load. Measured on
  the two-card server: the mapping is never made, answers are exact (12 of 12) and speed is unchanged (90.3 tok/s).
- **One card too.** The one-card server made three such mappings (2.5 GB each, one of them a copy back to host
  memory); with the overlay none, 12 of 12 exact.
- **Video lane too.** The exact dividing line is 512 MiB. The video lane made one such transfer per session and
  four per clip; they now go in pieces, and two clips are bit-identical to last night's
  ([note](experiments/minimax-h3-b70/notes/2026-10-04-piecewise-transfers.md)).
- **Both published 27B packages now ship it, re-accepted the same day.** Two cards: 12 of 12 gates, 12/12 exact,
  90.32 tok/s. One card: all three profiles 12/12 exact (54.0, 54.0, 52.2 tok/s). The launcher files are unchanged;
  the overlay is one more file in each package's `overlays/` folder.
- **Reported to Intel** with the owner's approval:
  [comment on compute-runtime#948](https://github.com/intel/compute-runtime/issues/948#issuecomment-5982081300).
- **Not caused by:** a bad card, memory running out, or container swap (swap only made the timing worse).
- The owner chose a health check over a reboot at 09:40; it passed and there has been no fault since.
- Also settled this morning: speculation is **not** lossless with several users (stays single-user), and exchanging
  the output-layer results once a step gains nothing (489 vs 488 tok/s at 64 users). Both closed.
- [Fault note](experiments/qwen38-27b-b70/notes/2026-10-04-gpu-fault-mtp-start.md).

**Recommended next:** back to optimizing. The real remaining lever for many users on the 27B is an output-layer
kernel that gives the same result for any number of rows (a kernel build); size it first.

## 2026-10-04, overnight: many users at once, lossless on short and long prompts, up to 488 tokens a second together

**Sixteen users can share the two cards and each still gets exactly their solo answer, at 325 tokens a second
together (one user gets 90).** This holds for short prompts and for prompts of 2,000 to 8,000 tokens. It needed
three small fixes, none of which changes any arithmetic: keep each processing step pure (one user's prompt chunk
alone, or writing only), feed the output layer four rows at a time, and give each long conversation its own
attention call. Each cause was found by measurement, not guessed. Earlier tonight this page said "lossless" on the
short test alone; the long-prompt test showed that was not yet true, and this entry replaces it. Confirmed on a second fresh
server. The same three fixes also make 32 users (428 tokens a second together) and 64 users (488) lossless, where
before nothing above sixteen was. It is a research setup, not a package profile yet.

| Users at once | Tokens a second together | Each user gets | Lossless |
| ---: | ---: | ---: | --- |
| 1 (the shipped recipe) | 90 | 90 | yes |
| 16 | 325 | 20 | yes, short and long prompts |
| 32 | 428 | 13 | yes, short and long prompts |
| 64 | 488 | 8 | yes, short and long prompts |

**The owner's direction for this work: lossless only, no server left running, keep optimizing the Qwen 27B (one
card or two) or the MiniMax video model.** The cards are empty between experiments.

**The headline.** Until now the 27B was measured for one user: about 90 tokens a second on two cards. Tonight
we measured several users at once. **With speculation off, sixteen users each get exactly the answer they would
get alone, and together they get 423 tokens a second, 4.7 times the single-user rate.** Eight users get 237
together. Past sixteen a few answers begin to differ, so sixteen is the limit. These are the same answers the
published single-user recipe gives. [Full result](experiments/qwen38-27b-b70/notes/2026-10-04-fp8-multiuser-result.md).

**What else was settled overnight, all lossless:**

- **Video: 396.6 seconds a clip, down from 410**, eight clips in a row, every one bit-identical to September's.
  That is twice the original baseline.
- **Video clips are now repeatable as files**, not only as pictures: same seed and prompt, same `clip.mp4`, byte
  for byte. The video encoder had been the odd one out.
- **Single-user 27B: the levers tried so far are used up (this is not a stopping point; new levers are owed).** Reusing the card-to-card exchange buffers was exact and worth +0.05 %.
  One card is limited by how fast it reads the weights; two cards lose under 4 ms a step to the exchange; the
  model's own draft accuracy caps the rest. Every remaining idea was sized at one or two percent and closed.
- **A loaded two-card 27B uses 9 GB of host memory and none of it can be released**; it is the GPU runtime's own
  working memory. The research launcher's memory guard, which stopped two healthy servers on October 3, now has
  a 2 GB floor.
- **One GPU fault on October 3 (22:39), caused by that guard killing a busy server.** The health check passed
  afterwards and work carried on without a reboot, as the owner's rule now says. The second fault, at 06:25 on
  October 4, is the entry at the top of this page.

**Recommended next:** see the entry at the top of this page.

## 2026-10-03: back after twelve days — the machine was stable all day, a newer kernel is installed, and it restarts itself to test it

**Where things stand, in one paragraph.** Today the two-card chat service was started and stopped
thirteen times and the video model made nine runs, on the same old kernel that had all the September
faults, and **not one GPU fault appeared**. The fix from September 19 (stop the service's container
from swapping while it loads the model) looks like it was the real cure for the start-up faults. A
newer kernel with genuine graphics-driver fixes is installed anyway, and the machine reboots into it
at the end of this session and tests itself.

**After the reboot, read this first:** `/mnt/fast-ai/bench-results/kernel-soak-20261003/k38/`
(`postboot.log`, `summary.json`, `cycles.tsv`). The machine runs the same ten start/stop cycles by
itself as its first GPU work and **leaves the chat service running on port 18124** (unit
`fp8-soak-k38-c10`) if all ten are clean. If `postboot.log` says a fault happened, nothing was reset
and the service is down: that is a decision for you. If it says the wrong kernel booted, nothing ran.

### What was done today

- **"Upgrade to kernel 7" turned out not to be news here.** This machine was already on kernel 7.0
  for every September fault. What is new is build 7.0.0-38 (released October 1), which fixes a
  driver deadlock at job teardown and several page-table bugs. It is installed; the old build
  7.0.0-31 is kept as the fallback. Nothing else changed with it: same GPU firmware, same Intel
  runtime. Automatic kernel and GPU-firmware upgrades are now switched off so a kernel can never
  change without a decision (`/etc/apt/apt.conf.d/51b70-no-auto-kernel`); other security updates
  still install by themselves.
- **Our fault is a known, unfixed Intel bug.** Other owners of two B70 cards report the same
  copy-engine fault at `intel/compute-runtime` issue 948, on several kernels and firmware versions.
  Nobody there found a cure; some found the older 6.17 kernel calmer. Full notes:
  [upstream, kernel and driver review](notes/2026-10-03-upstream-kernel-and-driver-review.md).
- **A memory guard is in place.** Three of the September freezes were the 15 GB of RAM running
  out. A small system service (`earlyoom`) now stops the model-loading program before the machine
  locks up, and leaves the desktop, remote logins and Docker alone. It did not fire today; the
  lowest free memory during a service start was 2.9 GB.
- **The baseline was measured before changing anything.** Ten start/stop cycles of the chat service
  on the old kernel: ten clean, twelve of twelve test prompts exact every time, 90.2 tokens a second.
  Then three more cycles straight after the video runs (the pattern behind three of the five
  September faults): also clean. Numbers:
  [kernel soak](experiments/qwen38-27b-b70/data/2026-10-03-kernel-soak/README.md). Because the old
  kernel scored ten out of ten, the new kernel cannot look *better* on this test; it can only match it.
- **Video model: the stay-loaded picture step passed its exactness check.** In a batch, turning
  the result into pixels now takes 41 seconds per clip instead of 56, and the output is identical
  bit for bit. The test run found and fixed three bugs on the way.
- **Your decision on the faster picture step is applied, with a limit.** On one card it takes 15
  seconds instead of 80, gives the same result every time, and is now the default for making clips
  (`EXACT=1` brings back the old exact way; all correctness checks still use the exact way). On two
  cards it is faster still, 9 seconds, **but two identical runs produced slightly different
  pictures**, so there it is not the default and the script warns if you ask for it. Details: the
  2026-10-03 rows of the [video ledger](experiments/minimax-h3-b70/notes/2026-09-20-realtime-goal.md).
- **Housekeeping.** Sixteen unpushed commits from September 21 are on GitHub. The 21 open audit
  pull requests are closed with every recommendation answered in
  [one triage file](audits/efficiency/TRIAGE-2026-10-03.md); the auditor now runs weekly and commits
  directly. The audit scripts got the fixes the reports kept asking for.

### Result after the reboot (2026-10-03 20:55 EDT)

**The new kernel passed its own test: ten of ten start/stop cycles clean, twelve of twelve prompts
exact every time, 90.3 tokens a second, no GPU faults.** That is the same score as the old kernel, so
the kernel is safe to stay on but was not what cured the September faults; the no-swap fix was. The
chat service is running on port 18124 on kernel 7.0.0-38
([numbers](experiments/qwen38-27b-b70/data/2026-10-03-kernel-soak/README.md)).

### Later the same evening: the flagship two-card recipe was re-checked end to end and passed

After the reboot the repo's own goals were re-read to choose what to do next. The clearest owed work
was that the two published Qwen3.8 FP8 packages had carried an "acceptance pending" label since the
September 19 no-swap fix: the launcher had changed and nobody had re-run the full user-style check.

- **Two-card package: done.** From an anonymous download of the repository, through the package's
  own scripts: twelve of twelve gates pass, the twelve test prompts are exact, six practical
  requests repeat exactly, clean stop, no faults, **90.0 tokens a second**. The pending label is
  retired. The published headline moves from 90.5 to **90.2** (it is the median of two fresh
  servers and the new one was a little slower, well inside normal run-to-run spread). The approved
  LocalMaxxing record is left as it is; no new submission was made.
- **One-card package: done too.** All three profiles passed every check (54.0, 54.0 and 52.2 tokens a
  second, within 0.7 % of September), and the memory reading this run was owed came back with room to
  spare: 6.9 to 7.7 GB used of the 12 GB limit, nothing killed, nothing swapped. Three one-card servers
  followed by a two-card start is the exact sequence that faulted three times in September; tonight it
  logged **no faults**. [Receipts](experiments/qwen38-27b-b70/data/2026-10-03-fp8-onecard-noswap/README.md).
- **The chat service is up** on port 18124 (unit `fp8-service-20261003-after-onecard`, state
  `/mnt/fast-ai/bench-results/fp8-onecard-noswap-20261003/service`), twelve of twelve exact at 90.2
  tokens a second, on kernel 7.0.0-38.
- **The stability finding is published** in the [host stability guide](docs/host-stability-and-fault-diagnosis.md)
  and its site page: the two-card host's GPU faults came from the container swapping at its own
  memory limit, and one launcher argument ended them.
- **Upstream fixes: nothing worth a rebuild.** None of the three candidate fixes reaches our serving
  path ([review note](notes/2026-10-03-upstream-kernel-and-driver-review.md)).

### 23:10 EDT, owner's direction: no server is hosted while optimization is under way

**The cards are empty on purpose and stay that way between experiments.** The owner said it plainly:
this is a shared repository whose focus is optimizing; a server gets hosted when the optimizing is
done, and it is not done. Earlier entries on this page (and tonight's runs) kept putting the Qwen3.8
27B model back on port 18124 after every experiment, following a September 13 line in `AGENTS.md`
("prefer one continuously running server"). That was not what the owner wanted. Do not start, restore
or queue a resident server unless the owner asks for one. `AGENTS.md` now says the same (rule 1 of the owner's standing rules).

**State of the machine:** nothing loaded, about 14 GB of host memory free, kernel 7.0.0-38. **This
boot has GPU fault lines on it** (three lines at 22:39:47 EDT, caused by a hard kill, see below). GPU
work waits until health is re-established with the bounded probe, or until a reboot.

**How the fault lines got there (22:37-22:40 EDT).** The next speed idea for the two-card recipe was
started (reusing the buffers of the card-to-card exchange, expected gain small). Its first stage was a
measurement run with a profiler on. The profiler used memory faster than expected, the launcher's
safety guard stopped the server, and stopping a busy GPU server that abruptly made the driver log
fault lines. The experiment halted itself. The machine never froze and nothing was lost; the real
test did not run. [Full account](experiments/qwen38-27b-b70/notes/2026-10-03-fp8-comm5-attempt1-guard-kill.md).

**Ready to run once the cards are cleared for work, nothing is queued to start by itself:** the reworked experiment
`experiments/qwen38-27b-b70/scripts/run-20261003-fp8-comm5b-campaign.py`. It needs no server before
it and leaves none after it.

### Open items, dated 2026-10-03

1. ~~Read the post-reboot result~~ done, see above.
2. **If faults come back on 7.0.0-38:** try 7.0.0-39 (still in Ubuntu's testing pocket, it has the fix
   closest to our fault), then 6.17, one change per boot, same ten cycles each.
3. **Why is the fast picture step not repeatable on two cards?** One card is repeatable. Not yet
   known whether it is the other card or the two-process arrangement.
4. **Upstream code worth porting** when the chat-model lane is next opened: three small candidates
   are listed in the review note. A full rebase to the newest vLLM is high risk for exact outputs.
5. ~~`AGENTS.md` was not updated~~ Done 2026-10-03 at the owner's request: the file was reviewed and
   consolidated (no resident server, the no-cheating rules kept whole, machine-safety rules reconciled
   with `docs/local-ops.md`, stale paths and duplicated rules removed, the old Gemma record moved out
   to its result packet).

## 2026-09-19 (decided 2026-10-03, see above): a video clip takes three minutes instead of four

**Your call, when you have a moment: should the faster picture-conversion setting become the
default?** Everything below is the evidence for that one decision. Nothing has been switched on; the
software still does it the old, slow way until you say otherwise.

**What we found.** The step that turns the model's output back into actual pixels used to take 80
seconds of every 4-minute clip. There is a setting -- one the people who made this model wrote into
their own documentation, and which their code turns on automatically on Nvidia cards but not on ours
-- that does the same work in **16 seconds. Five times faster.** A whole clip goes from **4 minutes 4
seconds to about 3 minutes**.

**The catch, stated honestly: the picture is not identical.** It is very slightly different, and the
sound and everything before the picture step are untouched, bit for bit. How different:

* **Almost every pixel changes** -- 99.8 % of them, in all 124 frames.
* **By an amount smaller than a picture file can even store.** Picture brightness is recorded in 256
  steps. The average change is **three hundredths of one of those steps**. You could not store it if
  you wanted to.
* **The worst single pixel** in the whole clip -- one out of 66 million -- changes by **7.5 steps out
  of 256**, about 3 % of the brightness range. One pixel, on one frame.
* The video file we actually save is a compressed format that throws away more than this by itself.

**Why it still matters.** Our rule in this lab is that a change is either provably identical -- we
compare fingerprints of the output and they match exactly -- or it is a judgement call. This one is a
judgement call, permanently: the fingerprint will never match the old one again. It is reliable and
repeatable (we ran it twice and got byte-for-byte the same result both times), so it is a *different*
answer, not an *unpredictable* one.

**The recommendation: switch it on, and keep a flag to turn it off** for any run that has to
reproduce an old result exactly. But this is a quality question about your video, so it is yours to
decide, not ours.

**The other thing we tried did not work, and that is worth knowing.** The obvious fix was to split
the picture step across both cards instead of one -- twice the hardware, and exactly the same answer,
so no judgement call at all. **We built it, and it is provably exact: it reproduced the original
clip's fingerprint perfectly.** We also proved first that both cards compute identical results down
to the last bit, which was the real risk and which this lab has been bitten by before.

**And it saved one second out of eighty.** The work was divided evenly between the cards and the
clock did not move, because of a limitation in Python itself: the two halves took turns instead of
running side by side. Fixing it properly means running each card in its own separate program, which
is real work. We are not doing it now -- the fast setting above already finishes the job in 16
seconds, so there is nothing left to win. But the lesson is filed, because **the next big speed idea
we had planned -- keeping both cards busy during the slow generating step -- would hit exactly this
same wall.** That moves "one program per card" from "not worth it" onto the critical path for the
biggest remaining improvement, whenever we get to it.

**What is now the slowest part.** With the picture step at 16 seconds, the three-minute clip is
**61 % generating, 27 % loading model files from disk, 9 % pictures**. The loading is 46 seconds of
reading the same files every single time, and it does not depend on the prompt at all -- running this
as a service that stays loaded instead of a script that starts fresh would remove it from every clip
after the first, with no quality question attached. That is now the best guaranteed improvement left.

Nothing stressed the machine: six runs in ten minutes of card time, free memory never dropped below
10,232 MiB (just under 10 GiB), the safety watchdog never fired, and neither card logged a single fault.

The numbers, the fidelity table and the re-ordered list of what to try next:
[decode experiments](experiments/minimax-h3-b70/notes/2026-09-19-first-light.md#decode-experiments-2339-2345-utc)
and the [full analysis](experiments/minimax-h3-b70/notes/2026-09-19-speed-plan.md#results-window-4-2026-09-19-1939-1949-edt);
receipts in
[`data/2026-09-19-decode-experiments/`](experiments/minimax-h3-b70/data/2026-09-19-decode-experiments/).

### The service is up, and the swapping fix passed all three checks

**The FP8 service is UP on both cards**, unit `fp8-service-20260918-resume`, state directory
`/mnt/fast-ai/bench-results/resume-20260919g/service`, port 18124 -- **twelve out of twelve test
prompts exactly right, at 89.84 tokens a second, no faults.** It was stopped for the video work above
and restarted straight after, which is the start that became the third check.

**Three for three: the swapping fix works.** The container swapped nothing at all again -- zero
pages, for the third time running -- and there were no out-of-memory kills. The machine as a whole
swapped 275 MB, against 288 and 293 MB on the two earlier checks and 4,514 MB before the fix. How
much memory the service really holds came back at 8.94 GB, a third reading within a tenth of a
percent of the other two. The container did press against its memory ceiling and hand pages back
16,117 times over the run -- **which is the fix working as intended**: that pressure is exactly what
used to go to swap instead, and this time none of it did and nothing was killed.

**That closes the measurement.** The remaining work is the code change that makes the setting stick
by itself, in `serve.py` -- **another agent is preparing that right now**, along with regenerating the
published evidence and re-running acceptance. Until it lands, the fix still has to be applied by hand
beside every single start, because it applies to one container and every restart makes a new one.

## Earlier today: the video model reached full size, and the service came back up

**This evening's second window, 18:46 to 19:03, did two things and both worked.** Nothing is on the
cards now except the FP8 service, which is up and answering.

### The video model runs at the size it was designed for

**MiniMax-H3 made a 960 by 544 clip -- the picture size the model was actually trained at -- and it
did it on both versions of the model.** An hour earlier it could only do 448 by 256, barely a fifth
of the area, and there was a real worry that the full size would not fit in the two cards at all. It
fits, with room left over: the tighter card still had 8.4 GB free.

**It takes about four minutes to make five seconds of video.** Four minutes four seconds, to be
exact, of which:

* **1 minute 49 seconds** is the actual generating,
* **1 minute 20 seconds** is turning the result back into pixels,
* **46 seconds** is loading the model files,
* and the rest -- reading the prompt, the sound, writing the file -- is about 9 seconds all together.

The smaller INT8 version of the model also made the same clip, in 4 minutes 34 seconds. Both clips
show a convincing rainy night street: neon reflected in wet road, someone with an umbrella walking
away. The INT8 one has more detail in the scene. **That is two frames of one prompt and it is not a
verdict on which version is better** -- we still need a proper set of prompts for that.

The clips are too big for Git and are here:

* `/mnt/fast-ai/bench-results/minimax-h3-canvas-20260919/pruned-960x544/smoke-20260919T224948Z/clip.mp4`
  (the main version, 3.1 MB)
* `/mnt/fast-ai/bench-results/minimax-h3-canvas-20260919/int8-960x544/smoke-20260919T225400Z/clip.mp4`
  (the INT8 version, 4.9 MB)
* `/mnt/fast-ai/bench-results/minimax-h3-canvas-20260919/pruned-576x320/smoke-20260919T224743Z/clip.mp4`
  (the middle size we stepped through on the way, 0.8 MB)

**Knowing where the four minutes go changes what is worth fixing.** Three things stand out, and none
of them has been tried yet:

1. **46 seconds of every run is loading the same model files again**, and none of that work depends
   on the prompt or the picture size. Running this as a service that stays loaded instead of a
   script that starts fresh would save those 46 seconds on every clip after the first. It should
   also give byte-for-byte identical output, so it is easy to prove correct.
2. **The pixel-conversion step runs on one card while the other sits completely idle**, and it is now
   a third of the run and the fastest-growing part. Splitting it across both cards should be exact,
   because it is the same work just divided.
3. **The generating step is now 42 % attention maths** at this size, up from 15 % at the small size,
   and that part grows with the square of the picture size. Anything larger than this will be
   dominated by it.

Nothing stressed the machine: free memory never dropped below 8.9 GB, the safety watchdog never
fired, and neither card logged a single fault all evening.

Details, the five-run table, the timing breakdown and the five speed ideas written up properly:
[canvas ladder](experiments/minimax-h3-b70/notes/2026-09-19-first-light.md#canvas-ladder-2246-2259-utc);
receipts in
[`data/2026-09-19-canvas-ladder/`](experiments/minimax-h3-b70/data/2026-09-19-canvas-ladder/).

### The service is back up, and the no-swap fix passed test 2 of 3

**The FP8 service is UP on both cards**, unit `fp8-service-20260918-resume`, state directory
`/mnt/fast-ai/bench-results/resume-20260919f/service`, port 18124 -- **twelve out of twelve test
prompts exactly right, at 89.79 tokens a second, no faults.**

This was the second of three chances to check the swapping fix, and again it was a start that was
going to happen anyway rather than one made for the test. **It matched the first one closely enough
to be convincing.** The container swapped nothing at all again; the machine as a whole swapped 288
MB against 293 MB last time (and 4,514 MB before the fix); no out-of-memory kills.

**The important repeat: how much memory the service really holds came back at 8.94 GB against 8.95
GB last time** -- a difference of under a tenth of a percent. That was the number that changed the
safety margin yesterday, and two independent readings agreeing that closely means the roughly 3 GB
of room to spare is a real figure, not a one-off.

Two things moved slightly and neither is a problem: the service took 10 seconds longer to be ready,
all of it inside a code-compilation step, while the model load itself was identical to the hundredth
of a second; and the speed reading was 89.79 against 89.9 tokens a second, a tenth of a percent, with
the answers still all twelve exactly right.

**Next: one more clean start, then we edit `serve.py`**, regenerate the published evidence packets
and re-run acceptance. Until that edit lands the setting still does not stick -- it applies to one
container, and every restart makes a new one with swapping allowed again, so the little helper has to
be run beside every single start.

Write-up and the three-way table:
[container memory cap and swap](experiments/qwen38-27b-b70/notes/2026-09-19-container-memory-cap-swap.md#validation-start-2-of-3-2026-09-19-1859-edt--2259-utc);
receipts in
[`data/2026-09-19-service-start-noswap-2/`](experiments/qwen38-27b-b70/data/2026-09-19-service-start-noswap-2/).

### What is next, in order

1. **One more clean service start**, then the `serve.py` edit for the swap setting -- but measure the
   one-card setup's real memory use on a live server first, because that one has less room to spare.
2. **Make the video pipeline a service instead of a script.** Biggest guaranteed saving, 46 seconds a
   clip, and it should not change a single pixel.
3. **Use the idle card for the pixel-conversion step.**
4. **Run the slow 51-step schedule once** at full size, to find out whether the 8-step shortcut we
   have been using costs anything in quality. It will take about 13 minutes for one clip.
5. **Build a small set of prompts** so the two versions of the video model can be compared properly.

## Earlier this evening: the video model made its first video, and the swapping fix passed test 1

**This section describes the 18:16-18:28 EDT window. The canvas ladder above is the later window and
supersedes it on picture size and timings; this is where first light and the repeat gate happened.**

**Both things in this evening's twelve-minute window worked.** Nothing is running on the cards now
except the FP8 service, which is up and answering.

### The video model finally produced a clip

**MiniMax-H3 rendered its first video: 5.2 seconds, 448 by 256, 124 frames, with sound.** It took 83
seconds of machine time to make those 5 seconds. The picture is what the prompt asked for -- a
rain-slicked city street at night, neon signs reflecting in puddles, a figure with an umbrella
walking away from camera.

**And it does the same thing twice.** We ran it two more times with the same settings and got files
that are identical down to the last byte. That matters more than the clip does: from here on, if two
runs differ, the difference came from the thing we changed, not from the machine being moody. It is
the gate this lane has been trying to reach since the 17th.

We also ran the alternative, smaller version of the model (the INT8 one) on the same prompt. It works
too, gives a different-looking take on the same scene, and is **1.7 times slower at the actual
generating step** (31 seconds against 18) because its compressed weights have to be unpacked on every
one of the eight steps. Which one looks better is not something one frame of one prompt can answer,
and we are not claiming it does.

Nothing about the run was stressful for the machine: free memory never dropped below 10 GB, the
safety watchdog never fired, and neither card logged a single fault all evening.

**What it took to get here, in one line:** five separate things had to be fixed, in order -- a
start-up call made too early, a memory cap that killed the desktop session instead of protecting it,
a setting without which every gigabyte put on a card also ate a gigabyte of main memory, a card
fault that forced every card-to-card copy to go through main memory, and finally the one that had
been hiding behind all of them: the code was quietly saving everything it computed in case someone
wanted to train the model, which filled a 32 GB card with 21 GB of junk during the decode.

**What was next for it:** step the picture size up toward the size the model was actually trained at
(544 by 960), one size at a time, reading the memory numbers at each stop -- **done in the 18:46
window above, and it worked**; compare the fast 8-step shortcut against the full 51-step schedule the
model was trained for; and put together a handful of prompts so the two versions of the model can be
compared properly instead of by looking at one frame. The last two are still open.

Details, numbers and the five blockers:
[first light](experiments/minimax-h3-b70/notes/2026-09-19-first-light.md); receipts in
[`data/2026-09-19-first-light/`](experiments/minimax-h3-b70/data/2026-09-19-first-light/). The clips
themselves are too big for Git and live in `/mnt/fast-ai/bench-results/resume-20260919d/minimax/`.

### The service is up, and the no-swap fix passed its first of three tests

**The FP8 service came back up right afterwards, on both cards, twelve out of twelve test prompts
exactly right, at 89.9 tokens a second, with no faults.**

This was the first chance to try the fix for the swapping problem found earlier today, and it was a
start that was going to happen anyway rather than a restart made to test something. A small helper
caught the new container about a minute before the model load began and told it "no swap at all".

**It worked.** The container swapped **nothing** -- zero, against 3.9 GB last time -- and the machine
as a whole swapped 293 MB instead of 4,514 MB. No out-of-memory kills. And the load was very slightly
*faster*, not slower, which was the one cost we had been prepared to accept.

**One number came out worse, and it is worth knowing.** With nothing able to escape to swap, we can
finally see how much memory the service really holds: **9 GB, not the 7 GB we measured last time**,
because 2 to 3 GB of it had been hiding in swap when we looked. So the room to spare under the 12 GB
ceiling is about 3 GB, not about 5. Still comfortable for the two-card setup, which is stable after
it finishes loading. Not comfortable enough to guess at for the **one-card** setup, which carries an
extra 2.4 GB in main memory by design -- that one now has to be measured on a live server before it
gets the same change.

**Important, until the launcher files are edited: this setting does not stick.** It applies to one
container, and every restart makes a new container that comes back with swap allowed again. The
helper has to be run beside **every** service start until we change `serve.py` -- which needs two
more clean starts first, then regenerated evidence packets and a re-run of acceptance.

Write-up and the side-by-side table:
[container memory cap and swap](experiments/qwen38-27b-b70/notes/2026-09-19-container-memory-cap-swap.md#validation-start-1-of-3-2026-09-19-1823-edt--2223-utc);
receipts in
[`data/2026-09-19-service-start-noswap-1/`](experiments/qwen38-27b-b70/data/2026-09-19-service-start-noswap-1/).

### Do not repeat

A new row went into the
[do-not-repeat index](experiments/qwen38-27b-b70/DO-NOT-REPEAT.md): **running inference code without
turning gradient tracking off.** The video model's decode step filled a 32 GB card and crashed on a
396 MB request, having grown 21.7 GB *during* the decode from 9.7 GB of weights, because nothing in
the script said "we are not training". It looks exactly like running out of room and is not. One
line at the top of the program fixed it and changed no arithmetic. The tell is memory growing
*during* a step rather than at its start.

## Earlier on 2026-09-19: the FP8 service came back UP, and we found what was doing the swapping

**This section describes the 17:20 EDT start. The service was stopped and restarted once more at
18:23 for the batch window above, so read this as the measurement that produced the finding, not as
the current service.**

**The service came up at 21:22 UTC (17:22 EDT), on both cards, answering all twelve test
prompts exactly right at 90.24 tokens a second, with no fault lines from either card on this boot.**
You rebooted at 17:17, the one-shot unit started the service first thing on the fresh boot at 17:20,
and the recorder ran beside it.

**The finding, in three sentences.** Even with the swapping setting turned almost all the way off,
the machine still pushed 4.4 GB out to swap while the model was loading -- 4.2 GB of it in one
20-second burst. That is not the host's doing: our own launcher starts the server in a box limited to
12 GB of memory with 4 GB of swap, and reading the 29 GB model file fills that box about two thousand
times over, so the kernel keeps shoving the server's live working memory out to swap to make room for
more of the file. It is the same mistake as the 4 GB memory cap that helped kill your desktop session
on the 17th -- a limit set below what the job actually touches -- and it is the best explanation we
have for why the card's copy engine keeps breaking during model loads, though that part is still
**not proven** (this load swapped 4.4 GB and did not break anything).

**What happens next.** The fix is one word in each of the two launcher files: give the container no
swap at all, so that when it fills up the kernel throws away file cache it can re-read from disk
instead of pushing out memory the card may be reading. Those launcher files are frozen by published
evidence packets, so we do not edit them first. Instead, the next **three** times the service has to
start for its own reasons -- not a restart made to test this -- a small helper applies the setting to
the fresh container about a minute before the model load begins, with the recorder beside it. If all
three come back with no swapping, no out-of-memory kills, and twelve-out-of-twelve exact answers,
we change the launchers, regenerate the packets and re-run acceptance. **Nothing is being restarted
for this**, and no GPU work is queued.

The write-up, the second-by-second numbers and the risk list:
[container memory cap and swap during a service start](experiments/qwen38-27b-b70/notes/2026-09-19-container-memory-cap-swap.md);
receipts in [`data/2026-09-19-service-start-swap/`](experiments/qwen38-27b-b70/data/2026-09-19-service-start-swap/).

**The video model (MiniMax-H3) retry was still pending its own window when this was written.** That
window came at 18:16 the same evening and the retry worked -- see the top of this file.

## Earlier on 2026-09-19: fifth GPU fault on the two-B70 host (resolved by the reboot above)

**This section describes the state before the 17:17 reboot. The service is UP again; read it as
history, not as the current state.**

**One of the two cards faulted this afternoon, and nothing ran on the cards until the user decided.
The Qwen FP8 service was DOWN.** It was stopped on purpose at 14:40 to free the cards for a batch of
work, and when the batch tried to put it back at 15:03 the card broke 70 seconds into loading the
model. That is the fifth time this card has done this. Nothing was reset, cleared, killed or
rebooted, and the card is holding a crash dump that only a reboot or your say-so will clear.

**What went right today, before the fault.** The video model (MiniMax-H3) ran its whole denoising
pass twice with no fault, which is the thing that broke yesterday -- routing every card-to-card copy
through main memory really is the fix, and it is now proven rather than assumed. And at 14:20 the
FP8 service came up on both cards and answered all twelve test prompts exactly right at 90.36
tokens a second. So the cards work; they just do not survive this one particular moment.

**What is proven:**

* The fault is real and always the same: the same card (the one at address `03:00.0`), the same
  copy engine inside it, always while a model is being loaded onto both cards, never once the
  service is up and running. The evidence is saved at
  `/mnt/fast-ai/bench-results/gpu-fault-20260919T1904/`.
* It is not the card-to-card copying we blamed yesterday. That was not happening this time.
* Three of the five faults of this kind follow the same order of events: one-card work earlier in
  the day, then a two-card service start on the same boot.

**What is not proven:**

* **Why.** The best guess is that the computer was busy moving memory out to swap while the card
  was reading from it -- 15 GB moved to swap in this 49-minute session -- and the card asks for a
  page that has just been taken away. That is a guess with two supporting observations, not a
  finding, and a simply faulty card fits the evidence just as well.
* Whether starting the service first on a fresh boot would actually avoid it. It is a pattern in
  five events, not a rule.

**What was asked for, and what you chose.** A reboot, and a choice about how to spend it:

1. Reboot, and **start the FP8 service first, before anything else touches the cards**. *Chosen --
   done at 17:17/17:20, and it came up clean.*
2. Record what the memory system is doing second by second while that start runs
   (`scripts/measure-swap-during-start.sh`, read-only, touches nothing). *Chosen -- and it is the
   measurement that produced the finding at the top of this file.*
3. Turn the memory-swapping setting down (`vm.swappiness` from 60 to 1). *Chosen -- and it turned out
   to be the wrong lever: the swapping was the container's own memory cap, not the host's setting.*

Details, the full history of all seven faults and what would settle the question:
[incident note](experiments/qwen38-27b-b70/notes/2026-09-19-gpu-fault-service-start.md).

**Also today:** the stock-versus-lab FP8 comparison ran and came back **unusable, not informative**.
The plain-vanilla upstream image disagreed with our image on all twelve prompts *and* ran 57%
slower, which means the two were not running the same maths kernels at all -- so the comparison
cannot say anything about the small rounding question it was built to answer. The runner had
printed a recommendation off that result; that recommendation was wrong and has been removed.
Nothing we have shipped is affected, because every one of our quality checks compares a candidate
against a reference produced by the same image.
[Write-up](experiments/qwen38-27b-b70/notes/2026-09-16-fp8-review-findings.md).

**And:** the video model's decode step ran out of card memory a second time, for a new reason -- the
script was keeping every intermediate result as if it were going to train the model. One line fixed
it (commit `feeecf5c1`). It has still not been re-run; it is waiting for a window of its own.

The paragraphs below are older. Verify the FP8 service state before acting on any of them.

## Authority And Update Rule

**Four-B70 host `steve-b70s`, September12:** user selected a new-model native
baseline campaign. MiniCPM5-2B setup completed, but BF16 qualification failed
the strict output-format pilot (4/6); optimization has not started. The campaign
has exited and all four cards passed postflight. No baseline is promoted. See [lane packet](experiments/minicpm5-2b-b70/README.md).
It uses a dedicated environment and original external-drive weights, with
exclusive locks and fresh processes; no permanent listener is planned. Preserve
the older queued lanes and all protected artifacts below. Actual running state
must still be checked before another launch.

This is the sole cross-repository authority for loaded service, active lane,
protected work, and immediate next actions. Verify Git status, relevant
processes, listeners, and the actual endpoint before operational changes.
Update this page when a service starts or stops; keep experiment chronology
in lane notes.

The [archived workspace ledger](CURRENT-history-20260909.md) preserves the
previous 4,577-line page verbatim. Its live-service statements and queued
actions are historical, span multiple hosts, and are not current instructions.

## Local Host And Active Review

**Four-card host, October 4 (15:00 UTC): rebooting into kernel 7.0.0-39 on the owner's say-so; no server is running.**
Why: the GPU driver lockup (the machine stalls 14-70 seconds, about every 15-30 minutes of GPU load, five times on the last boot) now interrupts most test runs and would break a continuous stream, and 7.0.0-39 has fixes in exactly that driver code. This is the one change for this boot. After the reboot: check the kernel and the memory fence (both automatic now), run packet 94d (the sampler spread over three and four cards, [build note](experiments/ltx25-b70/notes/2026-10-04-packet-94-build.md)), and count lockups. Packets 94 to 94c produced no speed numbers: each stopped early on a packet bug or on the lockup, all without a GPU fault. The baseline is unchanged: 1.39 s per clip (18 fps) with the short-window encoder.

**Four-card host, October 4 (05:20 UTC): milestone - the short-window text encoder is the new baseline (owner's decision); no server is running.**
The owner accepted it after seeing the results: it is the same model, the same precision and the same steps, the mathematics is unchanged, and the finished clip differs the way another random seed would (same scene and quality, a different take). From here on the reference clips are the short-window ones (`stability-01-w93c-*`, fixtures file `experiments/ltx25-b70/data/stability-01-window-prereg.json`), and every later change must match them byte for byte. Results before this point were checked against the padded-encoder references and are not comparable clip for clip. Speed at the new baseline: 1.39 s per clip (18 fps); the goal is under 1.04. The two sampler cards are now the busy ones, so the next step is spreading the sampler onto the cards the encoder freed. [Milestone note](experiments/ltx25-b70/notes/2026-10-04-milestone-window-baseline.md).

**Four-card host, October 4 (05:00 UTC): no server is running; superseded by the entry above.**
The short window ran in the full pipeline: it is repeatable (two reference passes identical, 116 more clips identical to them) and faster (1.39 s per clip, 18 fps, against 1.59-1.68 s; GPU work per clip 3.8 s against 5.2 s). But the finished clips are **not** the same clips with tiny differences, as expected beforehand: they are a different take of the same scene, like another seed (PSNR 17-27 dB against the padded-encoder clips). By eye the quality is the same. The owner's first condition, "negligible finished-clip difference", is therefore not met as stated, and the window is not adopted. **Owner decision needed: is an equally good but different take acceptable (new references, byte-identical from then on), or must the output stay identical to today's?** [Results and side-by-side frames](experiments/ltx25-b70/notes/2026-10-04-packet-93c-results.md). Separately, computing the connector pass once per clip is byte-identical to today's output and is kept.

**Four-card host, October 4 (03:30 UTC): no server is running; the cards are healthy; superseded by the entry above.**
LTX 2.5 makes one second of video in about 1.56 seconds (about 15.5 fps); the goal is under 1.04. Every clip in the last two days matched its reference exactly (about 800 clips).
What we learned: the four cards are already 73-87% busy, so moving work around cannot close the gap; each clip has to cost less GPU work. The text encoder is about 40% of that work, and about 97% of what it computes is padding that is thrown away. Encoding only the real words is five times faster and is the same mathematics, but the result is not byte-identical to today's (the GPU's matrix kernels round differently for different row counts). **Owner decision (2026-10-04): the short-window text encoder may be used on two conditions: the finished-clip comparison confirms the difference is negligible, and new reference clips are made with it, with the byte-identical rule applied against those from then on.** It changes the output at rounding level (the same size as running the unchanged encoder on a CPU instead of the GPU: 4-6 parts per million), so it is recorded as a change, with its own references, never mixed with the padded-encoder references. Evidence: [probe](experiments/ltx25-b70/notes/2026-10-04-encoder-suffix-window-probe.md), [GPU budget](experiments/ltx25-b70/notes/2026-10-04-gpu-budget-from-driver-counters.md).
Faults on this boot (kernel 7.0.0-38): the experiment that put a second process on one card faulted that card at 02:46 UTC ([note](experiments/ltx25-b70/notes/2026-10-04-packet-92b-two-contexts-fault.md)); the stuck server then had to be terminated, which logged two more engine resets. A bounded four-card health probe passed at 03:25 UTC with a clean kernel log ([receipt](experiments/ltx25-b70/data/health/four-card-health-20261004T0325Z.json)), so work carries on without a reboot. The interrupt lockup on card 0000:43:00.0 still happens about every 15-30 minutes of GPU load; with panic-on-lockup off it is a 10-70 second stall, not a freeze.
Host changes made on this machine on October 3-4 (owner told the agent to use sudo and continue): memory blocks 53-57 (10 GiB around the bad chip) are taken offline at every boot by `b70-offline-bad-memory.service`; `kernel.hardlockup_panic` and `kernel.softlockup_panic` are 0 in `/etc/sysctl.d/99-hardlockup-panic.conf` (backup `.bak-20261003`); kernel 7.0.0-39 (from noble-proposed, with GPU page-fault and video-memory fixes) is installed and will be used at the next reboot, with 38, 34 and 31 kept.

**Four-B70 host, October 3: lane resumed after a 12-day gap; no server is running; boot 37491ca5 (kernel 7.0.0-34, GuC 70.44.1) is clean.**
The 09-21 entry below is superseded: a reboot followed it, packets 89 and 90
ran, and the host froze during packet 90's endure arm at 03:29 EDT on 09-21.
Packet 90 salvage: 101 clips exact through all three sentries, no wrong clip,
median 1.60 s/clip; the busy-window timers never ran (they are on the
unmerged `origin/packet-90` branch). Host review: memory is non-ECC; three
hard lockups sit in the xe GuC interrupt handler of card 0000:43:00.0;
`hardlockup_panic=1` with `panic=0` turns such a lockup into a silent halt;
the "storage-first" freeze pattern is journald's five-minute sync, not an
NVMe stall; kernel 7.0.0-38 (teardown-deadlock and bind fixes) is the apt
candidate and -34 has no xe change. Speed stands at 15.3 fps effective.
[Salvage](experiments/ltx25-b70/notes/2026-10-03-packet90-salvage.md);
[host review](experiments/ltx25-b70/notes/2026-10-03-host-forensics-and-catch-up.md).

**Four-B70 host, September 21 05:30 UTC (superseded by the entry above): boot f64b14c5 is burned for GPU work (xe engine fault 00:24:38 EDT during a probe teardown; the sealed launcher refuses launches) - the lane waits on a reboot. Speed stands at 15.3 fps effective; the 24 fps capacity budget says every stage must move.**
The two warm-900 crashes were one heap-corruption signature at
`PyBytes_FromObject` during the encoder load, twice - not a code regression;
memtest remains the standing ask. Analysis while gated: the sampler's packing
loss is ~0.7 s/pair (in-phase card contention; a simulation REFUTED the
stagger-gate fix - co-run already beats strict serialization); encode
(1.70 s/clip, contention-inflated), decode (1.60), sampler (1.63) are each
over the 1.042 s/clip budget. Queue: packet 89 (adaLN fusion, built+gated,
one command after reboot) -> 90 (busy-window attribution, branch ready) ->
91 (decode capacity: VAE-replica probe + MP4-save offload) -> 92 (second
encode worker). [Budget](experiments/ltx25-b70/notes/2026-09-21-capacity-budget-24fps.md);
[packet 90 design](experiments/ltx25-b70/notes/packet-90-packing-loss-design.md);
[lever order](experiments/ltx25-b70/notes/2026-09-21-timing-evaluation-and-lever-order.md);
[forensics](experiments/ltx25-b70/notes/2026-09-21-load-crash-forensics-and-probes.md).

**Four-B70 host, September 19 21:19 UTC: the sharded encoder's failures on servers 79b-81 traced to one race (worker encodes ran eager parts on the default stream, unordered against thread-stream replays: one all-NaN clip per run); packet 82 launches with the fix.**
Boat and marble clips from the sharded encoder are byte-identical to their
references; the failing clip varied by prompt and thread. Packet 82 runs the
whole worker encode on the thread's per-device streams. Server 81 stopped
21:14 UTC (pipeline latched on the NaN clip). [Findings](experiments/ltx25-b70/notes/graph-capture-81-results.md).

**Four-B70 host, September 19 21:08 UTC: server 80 stopped after an inert-capture refusal on its second sharded clip; packet 81 launches with capture diagnostics and one bounded retry.**
Server 80 (guarded preview save) emitted one exact clip, then block 0's
capture proof reported an inert graph on a new argument signature after
96 good captures on both sampler threads, and the pipeline latched. No
code path explains a genuinely empty capture; packet 81 records thread,
signature count and replay-versus-eager equality in the receipt, drains
every device and captures once more before refusing. Sharded encoder
remains bit-exact where measured (boat, marble on 79b).

**Four-B70 host, September 19 20:57 UTC: ninth freeze (18:04, no lockup report); server 79b proved the sharded encoder bit-exact, then a preview-MP4 muxer error latched the pipeline; packet 80 launches with a guarded save.**
The 18:04 freeze hit the instant the sharded arm started, with no CPU
lockup report and no pstore record despite the armed detectors (a
whole-platform stop; BMC rails and VRM temperatures normal, SEL empty).
Server 79b (relaunch): shard on xpu:2/xpu:3, oracle exact on boat and
marble, decoder placement clean, then `avcodec_send_frame()` EINVAL on the
bird clip's audio; stopped 20:52 UTC. Packet 80 records the failure and
continues; the oracle judges. [Findings](experiments/ltx25-b70/notes/graph-capture-79-results.md).

**Four-B70 host, September 19 18:00 UTC: freeze diagnosis revised to a Zen C6 idle-state lockup (evidence note); server 78b stopped after the VAE gate latched; packet 79 launches 18:02 UTC.**
Host: the 09-18 09:19 boot ran nothing and died with `soft lockup - CPU#9
stuck for 157s` in `smp_call_function_many_cond` (a core never answered an
IPI); freezes span both kernels, both GuC blobs, load and idle. The user
holds the C2-disable lines and the BIOS idle-control setting; lockup
sysctls now dump all CPUs and panic into pstore. Lane: on server 78b the
encoder shard installed for the first time (24 layers, 10.4 GB on xpu:3,
per-thread bookkeeping held), but the VAE gate's strict single-device check
refused the first sharded-arm prompt and latched. Packet 79 keeps strict
placement only for capture, records the decoder's per-device histogram and
ComfyUI's loaded-model table, and reruns the campaign.
[Evidence](experiments/ltx25-b70/notes/2026-09-19-freeze-evidence-soft-lockup.md).

**Two-B70 host `steve-TURIND8-2L2T`, end of day September 18: the FP8 package shipped, the video lane hit a GPU
fault, and nothing runs on the cards until you say so. The FP8 service is DOWN. Three decisions are waiting for you;
they are at the bottom of this entry with the commands.**

**Disks cleaned 2026-09-19 (13:04-13:25 EDT).** `/mnt/fast-ai` went from 24 GB to **503 GB free** (43 % used) and
`/` from 15 GB to **208 GB free**; only the Qwen3.8-27B FP8 and MiniMax-H3 lanes are left on the fast disk, and the
17 other model dirs, 1,250 pre-2026-09-14 campaign dirs and the llama.cpp worktree sources are in cold storage at
`/media/steve/extended-ssd/model-cold-storage/b70-host-20260919/` (verified copies; swap untouched). Details and the
root-ownership lesson: [notes/2026-09-19-disk-review.md](notes/2026-09-19-disk-review.md).

**MiniMax-H3, 2026-09-19 14:18-14:19 EDT: the video model ran its denoising all the way through, on both cards, with
no GPU fault. It then ran out of card memory while turning the result into pixels.** In plain terms: the thing that
broke yesterday is fixed and proven fixed, and what broke today is our own bookkeeping, not the hardware.

* **The card-to-card copy really was the problem.** Yesterday's run died three seconds into denoising, the instant
  data first crossed between the two cards. Today's run did the same work with every crossing routed through host
  memory instead, and it finished all eight steps in 17.7 seconds with a clean kernel log. Same split, same clip, same
  settings -- one difference. That was the experiment the lane was waiting on, and the standing rule ("never copy
  directly card to card on this host") is now backed by a control run rather than a guess.
* **Then it ran out of memory in the decode step.** The big denoising model -- 18.8 GB of it -- was still sitting on
  card 0 when the two decoders loaded on top of it, and the decoders are 10.3 GB, not the 5 GB we had assumed
  (the library keeps them at full precision no matter what precision you ask for). 31.2 GB on a 31.9 GB card, and it
  stopped. **This is not a card fault**: no fault lines, no coredump, nothing to clear, no halt.
* **Fixed today, on CPU only.** The runner now tears the denoising model off both cards explicitly before the decode,
  loads the two decoders one at a time on whichever card has more room, and prints a memory line for every card at
  every stage so this is visible in the log instead of being worked out afterwards from an error message. The decode
  should now peak around 10.8 GB instead of 31.2 GB. `smoke_h3.sh dry` prints the expected numbers per stage.
* **What is still open:** nobody has seen a finished clip yet. The next run should reach the mp4. The bigger canvas
  (544x960) may hit a *denoising* memory wall rather than a decode one; the new memory lines from the 320x576 step
  will say. Details: [fault note addendum](experiments/minimax-h3-b70/notes/2026-09-18-gpu-fault-first-light.md),
  [first-light plan, step 4a](experiments/minimax-h3-b70/notes/2026-09-18-first-light-plan.md).
* **Updated 14:41 EDT (second run).** The tear-down fix works and the log proves it: both cards read 0 GB after the
  denoising model is released, and the decoder loads at exactly the predicted 9.7 GB. The decode still ran out of
  memory, for a *different* reason -- the script was holding on to every intermediate result as if it were about to
  train the model, so 9.7 GB of weights grew to 31.4 GB during the decode. One line fixed it (commit `feeecf5c1`).
  Not re-run; waiting behind the reboot decision. The "should peak around 10.8 GB" figure above was always the
  figure for a run that does not do that, so it is still an expectation and not a measurement.
  [Step 4b](experiments/minimax-h3-b70/notes/2026-09-18-first-light-plan.md).

**What shipped today.** The one-card FP8 package is finished and public. It is accepted on the `r312d-c` image, all
three profiles reproduce their references exactly through the launcher a user would actually run, and long prompts now
write 10-17% faster above 16K. The image is pushed to ghcr and its digest matches what the package already pinned, so
`docker pull` of the pinned digest works for anyone. The LocalMaxxing record `cmu6ytqyr0827lq01b76whp6d` is approved at
54.224 tok/s. One piece of housekeeping is upstream, not ours: the same payload got posted twice (you posted it, the
assistant posted it again seconds later) and both were approved, so `cmu6ytvxr082alq015dpjgiz4` is a duplicate. It is
recorded as withheld and flagged for withdrawal; only the record owner can withdraw it, there is no delete call.
Nothing on this lane is waiting on anybody.

**What we learned today, in four lines.**
1. *Build pins matter more than build tools.* The last remaining 7.6e-6 numeric gap turned out to be which revision of
   the CUTLASS/sycl-tla library the kernel was compiled against -- not the compiler, not our code. Every future kernel
   build now reads that revision from the kernel's own build file instead of whatever the source tree happens to have
   checked out.
2. *The video lane was quietly eating the host's RAM, and one flag stops it.* With both cards visible, every gigabyte
   we put on a card was costing a gigabyte of host RAM as well -- 8 GiB on the card, 8 GiB gone from the desktop. That
   is what killed the run on the 17th and took your desktop session with it. Setting
   `PYTORCH_ALLOC_CONF=expandable_segments:True` drops that cost to about 50 MiB. It is now mandatory for every
   two-card run and the smoke script sets it and prints it.
3. *We were counting the denoise steps wrong.* The step number the code wants is grid points, and every published
   figure is the other kind, so each needs +1. Settled: 51 for the plain model, 9 with the turbo adapter.
4. *The 8-step turbo LoRA is on disk and wired in.* It is what makes a short run legitimate rather than a shortcut, so
   the script now applies it by default and picks the matching step count automatically. All 208 adapter weights map
   cleanly onto our rebuilt model.

**The fault, and why everything was stopped (2026-09-18 -- superseded by the 2026-09-19 entry above; the cards are cleared and the denoise now passes).** The MiniMax-H3 first-light run got further than any before it -- text
encoder loaded in 12.6 s, the video model streamed onto both cards in 20.6 s, evenly split -- and then died three
seconds into the very first denoising step, at the exact moment data first crosses from one card to the other. The
kernel logged a copy-engine fault on `0000:03:00.0`, an engine reset, a timed-out job and a device coredump, and the
run came back with "device lost". **New today, and it matters: the OTHER card faulted too.** `0000:e3:00.0` logged the
same class of copy-engine error four minutes later. Both ends of the card-to-card copy failed, which is the best
evidence yet that the card-to-card copy itself is the problem -- that is the hypothesis the next run is built to test,
because the runner now routes every cross-card move through host memory instead (bit-for-bit identical either way).
Nothing was reset, reloaded or rebooted, and the hung process was killed by pid only.

**The coredump is already dealt with -- so one of the decisions you were expecting has answered itself.** It was
copied out at 11:08 EDT, 503 KB, and it is in the evidence folder; it names the timed-out job, the kernel and the
firmware. Nobody then cleared the sysfs node, but the driver expired it on its own at 12:06 EDT
(`Xe device coredump has been deleted`). So **there is nothing left to clear** -- the evidence is saved and the node is
gone. Worth remembering for next time: these dumps expire after about an hour, so they have to be copied promptly.

**DECISION 1 -- reboot first, or not?** The coredump question is settled (saved, then expired), so this is purely
about whether you trust the driver state on two cards that both took a copy-engine fault, on a host that has been up
since the 17th and has faulted on 09-16, 09-17 (twice) and today.
* Not rebooting is defensible: the health probe is the gate, and it stops everything if the cards are unwell.
* Rebooting is the stronger reset. If you reboot, the service comes back with the autolauncher:
  ```bash
  nohup scripts/autolaunch-fp8-service.sh &
  ```

**DECISION 2 -- run the resume script?** It is written, checked and waiting:
[`experiments/minimax-h3-b70/scripts/resume-after-fault-20260918.sh`](experiments/minimax-h3-b70/scripts/resume-after-fault-20260918.sh).
It refuses to start unless the host is genuinely clear, runs the health probe, then the MiniMax control clip and its
repeat check, then the int8 comparison, then puts the FP8 service back on 18124 and proves it still matches the
reference 12/12. It stops at the first failure and it never clears, resets, reboots, stops or kills anything. Launch it
as a background unit, never from a chat session -- the first phase alone is tens of minutes:
```bash
# full session: health probe, MiniMax control + repeat, int8 A/B, then the FP8 service back up
systemd-run --user --unit h3-resume-20260918 --collect \
    --working-directory=/home/steve/b70-optimization-lab \
    bash experiments/minimax-h3-b70/scripts/resume-after-fault-20260918.sh

# or just get the FP8 service back, nothing else
systemd-run --user --unit fp8-resume-20260918 --collect \
    --working-directory=/home/steve/b70-optimization-lab \
    bash experiments/minimax-h3-b70/scripts/resume-after-fault-20260918.sh --only-service

tail -f /mnt/fast-ai/bench-results/resume-20260918/session.log    # watch it
```

**DECISION 3 -- delete the 62 GB reference copy of the video model?** `/mnt/fast-ai/llm-models/minimax-h3/transformer`
is the original full-precision model. We do not run it -- it is far too big for these cards, and the two versions we
actually run are separate, smaller files. **But it is not dead weight: it is the thing our correctness tests compare
against.** The CPU check that proves our rebuilt model is bit-exact, and the check that proves the int8 version
decompresses correctly, both read tensors out of it. Delete it and those two tests stop running (they skip cleanly and
say so, they do not fail) and we lose the ability to re-prove the rebuild if anything changes.
The trade: `/mnt/fast-ai` has **24 GB free of 916 GB (98% full)**, which is tight enough that a long video run could
fail on disk. Deleting it buys 62 GB.
* Recommendation: **keep it until the video lane has produced a good clip and the int8 comparison is done** -- that is
  exactly when those two tests matter most -- then delete it. If you need the space sooner, delete it and re-download
  later; it is a public checkpoint.
```bash
du -sh /mnt/fast-ai/llm-models/minimax-h3/transformer   # 62G
df -h /mnt/fast-ai                                      # 24G free
# only when you have decided:
rm -rf /mnt/fast-ai/llm-models/minimax-h3/transformer
```

**Also queued, not run:** the stock-versus-lab check, which answers whether our rebuilt kernels produce exactly the
same words as the untouched upstream image. It is a runner you can queue in any GPU window:
[`experiments/qwen38-27b-b70/scripts/run-20260918-fp8-stock-gdn-check.py`](experiments/qwen38-27b-b70/scripts/run-20260918-fp8-stock-gdn-check.py).
Nothing shipped depends on the answer, but it is the last open question on the FP8 lane.

[Fault note](experiments/minimax-h3-b70/notes/2026-09-18-gpu-fault-first-light.md),
[plan](experiments/minimax-h3-b70/notes/2026-09-18-first-light-plan.md),
[steps and LoRA](experiments/minimax-h3-b70/notes/2026-09-18-steps-and-lora.md), evidence
`/mnt/fast-ai/bench-results/gpu-fault-20260918T1506/`.

**Four-B70 host, September 18 04:40 UTC: packet 78 launched as server 78 after two clean reloads on the new kernel/firmware (no freeze, no fault).**
Server 77b's sharded warm failed on the second clip: the host-embedding
CLIP's observation protocol (observe, encode, consume) is single-threaded
and two encode workers interleaved (`Previous embedding observations were
not consumed`). Packet 78 makes that bookkeeping per thread (numerics
untouched; CPU test), keeps the encoder shard and two-clip sampler, and
the checker allowlists the replaced parent file. Runner 78: 3-prompt warm
on the sharded arm, `pipe-samp2-tsh` 30, `pipe-samp2` 24, endurance 120.
Log `campaign-78.log`.

**Four-B70 host, September 18 04:31 UTC: packet 77 campaign done (1.515 s/clip, 16.5 fps equiv, all exact; load lock proven over 120 prompts), but the encoder shard never installed; server 77 stopped for a controlled reload as 77b (warm on the sharded graph).**
The runner's plain-graph warm clip placed the whole encoder on xpu:2 before
the shard gate ran; two encode workers on one card still overlapped. First
teardown transition on kernel 7.0.0-30 / GuC 70.44.1 with the hard-lockup
panic armed. [Results](experiments/ltx25-b70/notes/graph-capture-77-results.md).

**Four-B70 host, September 18 04:15 UTC: rebooted on kernel 7.0.0-30 with the packaged GuC 70.44.1 restored and hard-lockup panic armed (pstore erst); packet 77 launched as this boot's single server.**
Both stability levers changed together on the user's instruction after six
silent freezes on 09-17, so attribution is deferred; a further freeze now
leaves a pstore backtrace (`scripts/collect-pstore.sh`). Packet 77 = encoder
sharded across xpu:2/xpu:3 with two encode workers + two-clip sampler with
the load lock; runner 77: warm, `pipe-samp2-tsh` 30, `pipe-samp2` 24,
endurance 120. Log `campaign-77.log`.

**Four-B70 host, September 18 01:00 UTC: six silent freezes on 09-17; next boot set to kernel 7.0.0-30; packet 77 waits for it.**
Freezes hit idle, during server load, and minutes after an xe client
teardown; no backtrace exists (hardlockup_panic was 0). GuC 70.72.1 (manual,
installed 09-03) sits in BOTH initrds, so the kernel change alone does not
revert it; the GuC restore and `kernel.hardlockup_panic=1` (pstore backend
erst) were handed to the user as sudo lines. Packet 76 never ran: its text
node failed to import (`ltx_text_shard.py` was not copied); packet 77 ships
it and the generator now proves every custom node's imports resolve. The
23:57 UTC freeze zeroed 307 tracked working-tree files and a git pack;
objects recovered from a bare clone, lane files restored, bulk restore left
to the user. Runner 77: warm, `pipe-samp2-tsh` 30, `pipe-samp2` 24,
endurance 120.
[Idle freeze](experiments/ltx25-b70/notes/2026-09-17-idle-freeze-1555utc.md),
[firmware review](experiments/ltx25-b70/notes/2026-09-17-firmware-and-kernel-review.md).

**Four-B70 host, September 17 14:28 UTC: packet 76 launched (encoder sharded across xpu:2/xpu:3 with two encode workers, load lock in the fast path); firmware review done.**
Server 74b segfaulted on the fourth prompt of a 120-prompt endurance run:
both sampler workers' first clips fell through the fast path into
ComfyUI's non-thread-safe loader (module.to() under a concurrent replay);
fixed with a load lock. Firmware review: the installed GuC 70.72.1 is a
manual, upstream "testing-only" blob replacing the package's 70.44.1 (backup
on disk); the kernel moved to 7.0.0-31 on 09-05, the closest correlate of
the lockups; recommendation is to boot 7.0.0-30 first, then restore
70.44.1, then kdump. Packet 76 arms: warm, `pipe-samp2-tsh` 30 prompts,
`pipe-samp2` control 24. Log `campaign-76.log`.
[Firmware review](experiments/ltx25-b70/notes/2026-09-17-firmware-and-kernel-review.md),
[crash](experiments/ltx25-b70/notes/graph-capture-74b-endurance-crash.md).

**Two-B70 host, September 18 06:12 UTC: the one-card FP8 lane is CLOSED for the night -- the package is accepted on
the r312d-c image, the image is pushed to ghcr, and the LocalMaxxing record `cmu6ytqyr0827lq01b76whp6d` is approved at
54.224 tok/s.** The push happened at ~06:05 UTC and the registry digest came back as `sha256:ea61e698...`, the same
value the package already pinned, so the manifest is `registry_pushed: true` with a verified digest note. One thing to
clean up upstream: the queue payload was submitted twice by mistake -- the user posted it, then the assistant posted the
identical file seconds later -- and both POSTs returned 201 APPROVED, so `cmu6ytvxr082alq015dpjgiz4` exists as a
duplicate of the canonical record. It is recorded as withheld and flagged for withdrawal in
`results/localmaxxing-submissions.md` (the submitter script and the public API have no delete call, so it can only be
withdrawn or ignored by the record owner); receipts for both are in
`experiments/qwen38-27b-b70/data/localmaxxing-responses/`. Nothing on this lane waits on anyone now; what remains in the
workspace is the MiniMax-H3 host-RAM measurement and the two-card exchange fusion / four-card replay listed below. The
depth-5 two-card service is back UP on 18124 (unit
`fp8-service-20260918-onecard-r312d`, state `/mnt/fast-ai/bench-results/fp8-onecard-r312d-20260918/service`), 12/12 vs
the comm-2 no-MTP reference at 90.27 tok/s. The acceptance campaign ran 05:02-05:58 UTC through
`packages/qwen38-27b-fp8-tp1-b70/scripts/serve.py` on the `r312d-c` image (`sha256:ea61e698...`, local tag via
`B70_FP8_TP1_IMAGE`), receipts `/mnt/fast-ai/bench-results/fp8-onecard-r312d-20260918/` and
[data/2026-09-18-fp8-onecard-r312d](experiments/qwen38-27b-b70/data/2026-09-18-fp8-onecard-r312d/):
`recommended` (32,768 at 0.975) strict 12/12 twice at **54.236 / 54.011 tok/s** plus ladder 64/64 three times, the
2K/8K/16K screen, the 2,048-30,720-token long corpus in three content types, chat quality and the 21-request logprob
replay all exact; `max-context` (40,960) 12/12 at **54.324**; `no-quantization` (28,672) 12/12 at **52.421**; ladder
and context screen exact on both. **Writing speed after a long prompt is +4.0% at 8K, +9.9% at 16K, +14.5% at 24K and
+17.3% at 30K** (30,720: 37.5 to 44.0 tok/s), with 2K level, so `B70_FA_MULTIQ_MIN_K=4096` costs nothing. Every
profile stopped cleanly and removed its container; no fault lines. **In the repository:** the manifest's
`acceptance_status` is `passed-on-configured-lab-host` with the measured per-profile numbers, the featured metric is
the shipped-launcher pair (median 54.124 tok/s), `registry_pushed` is true with the verified digest note, catalog,
README and model pages regenerated, and the findings note has the acceptance section. **Both waiting-on-user steps are
done:** `publish-r312d-image-ghcr.sh` ran (tag `r312d-fp8-tp1-20260918`, digest verified equal to the pinned local id),
and the submission went out and was approved as `cmu6ytqyr0827lq01b76whp6d` (54.224 tok/s from two fresh servers,
supersedes `cmu5wc2e50804lq01r0br2i5p`, 54.325, R311b) -- plus the duplicate `cmu6ytvxr082alq015dpjgiz4` noted above.
The ledger rows and both response receipts are written. R311b was pushed on September 17. Earlier on this boot, session
`fp8-r312d-session8-20260918` rebuilt the multiq library twice with the cards idle, one compiler job at a time: variant
b (upstream DPC++ 2026.0.0 + IGC 2.34.4 / ocloc 26.18, 03:25-03:40) is still 8/22 exact at 7.63e-6, the same cases as
r312c, so the toolchain was never the cause; **variant c (b plus sycl-tla `87f6850`, the revision the kernel
`CMakeLists.txt` actually pins, 03:40-03:56) is bit-exact, 22/22, max abs 0.0 at both v-tile 64 and 256.** Every lab
build from r309 on had used the March `cd76379`. Nothing shipped is invalidated, but every future `_xpu_C`/GDN rebuild
must use the pinned revision. MiniMax-H3 stays off (its smoke runner no longer sets a cgroup
memory ceiling; it must never run beside a build or the service). A kernel build in a container overlapped with the MiniMax-H3 first-light run (a
27 GB text-encoder load under `MemoryMax=4G`, which thrashed instead of failing fast) on this 15 GiB host;
`systemd-oomd` killed by memory pressure up through the GNOME session to `user@1000.service` itself, so
`fp8-r312d-session6-20260918` (before its service restore), the b/c rebuild `r312d-build-bc-20260918`, the armed
`fp8-r312d-session7-20260918` and the monitors all died. No `xe` fault, both cards free, no container running. The
02:43 restore had already lost the port race (`[Errno 98]`, `serve.py` binds without `SO_REUSEADDR`). Full account,
evidence paths and the preconditions before the MiniMax lane runs again:
[host OOM incident](experiments/qwen38-27b-b70/notes/2026-09-18-host-oomd-incident.md). The user authorized restarts at
03:24 UTC and the user manager came back at 03:25, which is how session 8 ran; the rule that killed the last attempt
still holds -- one host-RAM-heavy job at a time, never beside a build. Census receipts and the variant comparison:
[`data/2026-09-18-fa-multiq-census/`](experiments/qwen38-27b-b70/data/2026-09-18-fa-multiq-census/). Still true from
earlier on this boot: the last measured service (unit `fp8-service-20260918-lc2`) was
12/12 vs the no-MTP reference at 90.52 tok/s; two-card package = allgather allreduce (90.48 tok/s, LocalMaxxing
`cmu5qk0kz07zglq01eh1opkhx`); the one-card package was R311b single-checkpoint state, 32,768 default at 54.3 tok/s
(LocalMaxxing `cmu5wc2e50804lq01r0br2i5p`) -- it is now r312d-c with record `cmu6ytqyr0827lq01b76whp6d`, see the
acceptance entry above -- max-context 40,960
(engine ceiling ~44,800 at 0.983), probes exact to 36,864 tokens. Closed: replicated drafter (never faster), two-card
checkpoint state (speed-neutral), and the multi-row verifier attention kernel, which is the change that shipped. Git: the other host's
commit `03830fa00` pushed 302 tracked files as zero-length blobs (including `DO-NOT-REPEAT.md`); restored from
`b0c85ccc5` in `283383ed6` and local work rebased on top -- check `git diff --stat` before rebasing onto anything from
that host, whose own checkout is probably still zeroed. MiniMax-H3 (a video+audio generator, not an LLM) is halted, not
armed: `experiments/minimax-h3-b70/README.md`.

**Two-B70 host, September 17 07:50 UTC: rebooting with the user's approval after the third fault; the service needs one manual start after the boot.**
After the boot, from the repo: `nohup scripts/autolaunch-fp8-service.sh &` (health probe, then one two-card package
start on 18124; log `/mnt/fast-ai/bench-results/service-autolaunch.log`, state `service-autolaunch-<time>`), then the
strict parity against `/mnt/fast-ai/bench-results/fp8-review-20260916/tp2-mtp0-strict`. The collective A/B must not be
retried (oneCCL's peer-access kernels fault both cards); the pinned thresholds stay.

**Two-B70 host, September 17 07:25 UTC: GPU FAULT on BOTH cards during the collective A/B; port 18124 is DOWN; all GPU work halted; user decision needed (reset or reboot).**
The first server with oneCCL's default small-message kernels (`CCL_SYCL_*_SIMPLE_THRESHOLD=0`) faulted both cards two
minutes in (compute-engine page faults, CAT errors, coredumps devcd3/devcd4); the pinned-environment control had just run
cleanly at 88.50 tok/s. The fault is attributable to the experiment: those kernels use peer memory access over PCIe, the
September 14 fault class. The pinned thresholds are now documented as a guard. Third fault on this boot; the two earlier
ones were copy-engine faults on one card. Evidence `/mnt/fast-ai/bench-results/gpu-fault-20260917T0717/`. Once you
decide: health probe, then `packages/qwen38-27b-fp8-tp2-b70/scripts/serve.py start` with a new state directory.
[Findings](experiments/qwen38-27b-b70/notes/2026-09-16-fp8-review-findings.md).

**Two-B70 host, September 17 07:15 UTC: two-card collective A/B running (service down for about 45 minutes, returns as unit `fp8-service-20260917k`); both FP8 records on LocalMaxxing; decode profiles done.**
Records: two cards `cmu4zwfht07nzlq01tyj03f17` (88.41 tok/s), one card `cmu53h4l407o3lq01od0vwjrr` (53.43 tok/s at
24,576 tokens). Profiles (in-worker torch/XPU traces): on one card the W8A16 GEMM is 92% of device time at about 83% of
memory bandwidth, so only the 26% of launch gaps remain; on two cards the PCIe allreduce is 47% of device time (134
calls per step at 223 µs), so the running A/B tests oneCCL's default and low-latency allreduce paths against the
pinned ring kernel, each gated against its own no-MTP reference. One-card profiles `max-context` (30,720) and
`no-quantization` (20,480) shipped and verified. Graph capture on one card disqualified. Plan for lossless 32K+ on
one card: [single-checkpoint GDN state](experiments/qwen38-27b-b70/notes/2026-09-17-gdn-single-checkpoint-plan.md).
[Findings](experiments/qwen38-27b-b70/notes/2026-09-16-fp8-review-findings.md).
**Four-B70 host, September 17 13:03 UTC: rebooted by the user after the 07:00 UTC kernel stall hard-locked; LTX packet 74 launched as the single server for this boot (never to be stopped).**
The udev rule pinned all four B70s on at boot without help. The stall that
formed at 07:00 UTC (all cards pinned on, five minutes after a clean server
stop, triggered by a process that only imported torch) shows runtime PM was
necessary but not sufficient: teardown followed by a new xe initialisation
remains a lockup trigger on this kernel/driver. Rule from here: one sealed
server per boot, never stopped; no second torch process while it runs.
Packet 74 runs the two-clip sampler with explicit fills (24 prompts, ten
fixtures, per-clip oracles) then a fast+save control; log `campaign-74.log`.
[Incident](experiments/ltx25-b70/notes/2026-09-17-incident-kernel-spin-after-stop.md).

**Four-B70 host, September 17 06:52 UTC: two-clip sampler v2 launched (packet 73) after five probes established the recipe: per-clip streams, device contexts, pinned-host staged activations give 1.68x overlap bit-exact.**
Batching is closed (packet 72). Probes 1–5 (exclusive cards, block-sized
graphs): baton hand-off 0.997x, free threads on default streams 1.19x,
per-clip streams with peer copies 0.996x, explicit device contexts plus
pinned-host staging **1.68x** (ideal 1.78x), all bitwise exact. Packet 73
runs two sampler workers with a capture/replay reader-writer lock (captures
exclusive after a device drain), per-clip streams on both shard cards,
staged cross-card moves, the resident fast path and save-behind; 24 prompts
on ten fixtures with per-clip oracles, then a fast+save control. Log
`campaign-73.log`. Host stable since the runtime-PM fix (05:57 UTC).

**Four-B70 host, September 17 06:25 UTC: batch-2 route closed by proof (identical rows differ by up to 0.98); server 72 idle; next lever is the single-scheduler two-clip sampler.**
Since the runtime-PM fix at 05:57 UTC: four launches and three clean stops
with five-minute gaps, no lockup, no fault line. Packets 69–72 ran the
batch-2 row-equality proof to completion: rows differ even for identical
inputs, so batching is not bit-exact on this stack and is not pursued.
Standing position unchanged: 2.03 s per distinct clip, exact.
[Verdict](experiments/ltx25-b70/notes/graph-capture-72-results.md).

**Four-B70 host, September 17 05:57 UTC: freeze cause fixed (two B70s were runtime-suspending: boot policy raced the xe probe); all four endpoints pinned on, bind-time udev rule installed; LTX packet 69 launched.**
Eight silent lockups since 09-14 all sat on idle transitions, two on idle
boots. `0000:23:00.0` and `0000:27:00.0` had `power/control=auto` because
`b70-runtime-performance-policy.service` wrote `on` before the xe probe
finished and the probe reset it. Fix applied at 05:57 UTC (sysfs) and made
durable with `systemd/60-b70-runtime-pm-on.rules`; runners now refuse to
start unless `scripts/check-b70-runtime-pm.sh` passes, and
`scripts/check-packet-integrity.sh` refuses freeze-truncated packets (packet
68 was zeroed). Packet 69 runs the batch-2 row-equality proof; log
`campaign-69.log`. Standing position 2.03 s per distinct clip, exact.
[Cause note](experiments/ltx25-b70/notes/2026-09-17-freeze-cause-runtime-pm-race.md).

**Two-B70 host, September 17 05:30 UTC: depth-5 service is UP on 18124 (88.09 tok/s, 12/12); the night's goals are done; no GPU work running.**
Three unattended campaigns after the user chose to try the GPUs without a reset: two clean two-card starts (from idle
88.35, after one-card work 88.09, both 12/12 vs no-MTP), no new fault. One card gained two verified profiles through the
shipped launcher: `max-context` (30,720 tokens at 0.983 memory, 53.41 / 53.51 tok/s) and `no-quantization` at 20,480
tokens (51.77 / 51.78); 32K fits at depth 4 (50.97, research server). The two-card record is on LocalMaxxing as
`cmu4zwfht07nzlq01tyj03f17` (88.41). A general-text draft shortlist costs 3.6% on the suite with identical outputs (now
disclosed in the package). Graph capture on one card is disqualified (9/12). Service: unit `fp8-service-20260917f`,
state `/mnt/fast-ai/bench-results/fp8-night3-20260917/service-d`, one request at a time.
[Findings](experiments/qwen38-27b-b70/notes/2026-09-16-fp8-review-findings.md).
**Four-B70 host, September 17 05:00 UTC: server 65 stopped cleanly; packet 66 (batch-2 row-equality proof) launches after the five-minute gap.**
The blocks are weight-read bound (1.57 s of the 2.03 s clip), so two clips in
one batch would read each weight once for both. That is admissible only if a
batch-2 forward is bitwise equal, row for row, to two batch-1 forwards on
this stack. Packet 66 runs that proof on the resident model (three clips,
every forward compared: original row, perturbed second row, stacked batch)
and then repeats the fast+save arm. Runner commits per arm; log
`campaign-66.log`.

**Four-B70 host, September 17 04:55 UTC: LTX packet 65 complete: 2.029 s per distinct clip, 19/19 exact (12.3 fps equivalent); server PID 22356 idle on port 8188.**
Fast path + save-behind 2.029 s; fast-path repeat 2.140 s; pipe control
2.499 s (matches packet 58); forward-timing diagnostic: 1.67 s of forwards
per clip, blocks 1.57 s, glue 0.09 s. The block region alone exceeds the
1.042 s budget, so the next lever is a single-scheduler two-clip sampler
across the shard cards, then block-level kernel work. No fault; the server
stays up idle. [Results](experiments/ltx25-b70/notes/graph-capture-65-results.md).

**Four-B70 host, September 17 04:48 UTC: LTX resident fast path lands, 2.52 → 2.135 s per distinct clip (19/19 exact, 11.7 fps equivalent); packet 65 queued.**
Packet 64 timed ComfyUI's model-management calls with every model resident:
0.42 s per clip, almost all in the transformer's call before the first
sampling stage. Skipping the bookkeeping for fully resident models (no tensor
touched) took the interval to 2.135 s on ten distinct fixtures, all exact.
The remaining arms were refused by a gate's `original` mode (now
self-restoring); server 64 stopped cleanly. Packet 65 combines the fast path
with save-behind, repeats the fast arm, runs the pipe control and the
forward-timing diagnostic; launches after the five-minute gap.
[Packet 64 results](experiments/ltx25-b70/notes/graph-capture-64-results.md).

**Four-B70 host, September 17 04:37 UTC: LTX packet 63 stopped after its diagnostic arm was refused by a guard; packet 64 launches after the five-minute gap.**
The graph-capture gate's patcher check refused the new forward-timer wrapper
(whitelist, now extended); its latch is sticky, so server 63 was stopped with
one SIGINT (3 s). Packet 64 runs the lever arms first: resident fast path
(timed, then on), save-behind, pipe control, then the forward timer last. The
runner commits after every arm. Log `campaign-64.log`.
[Packet 63 note](experiments/ltx25-b70/notes/graph-capture-63-results.md).

**Two-B70 host, September 17 03:30 UTC: GPU FAULT during the final two-card service start; port 18124 is DOWN, no GPU work running, user decision needed. Everything else tonight passed and is published.**

- **What happened:** the one-card 24K campaign finished its tests and started the two-card depth-5 service at
  03:09:38Z; at 03:10:45Z `xe 0000:03:00.0` (renderD129) raised repeated copy-engine page faults and an engine memory
  CAT error with a device coredump, about 67 s into weight load. The launcher halted the server; the runner halted
  with no restore. No reset, power change or reboot. This is the **second identical fault today** (06:02Z, same
  card, same engine, same phase: a two-card start after long one-card work). Evidence:
  `/mnt/fast-ai/bench-results/gpu-fault-20260917T0310/`.
- **Next step needs the user:** a driver reset or reboot is not mine to make. Once approved, the normal path is
  `scripts/check-qwen36-xpu-xccl-health.sh`, then one `packages/qwen38-27b-fp8-tp2-b70/scripts/serve.py start`
  (new state dir) and the strict parity check.
- **Published tonight:** two-card package at MTP depth 5 on R310 (88.32 / 88.49 tok/s pair, accepted from public
  source, was 54.8); one-card package at 24,576 tokens of context (53.43 / 53.43 tok/s, was 16,384); both one-card
  profiles passed the 64-prompt sequential oracle. CI green through commit `28c4aab9e`.
  [Findings](experiments/qwen38-27b-b70/notes/2026-09-16-fp8-review-findings.md).
**Four-B70 host, September 17 04:45 UTC: three more silent lockups (03:14 UTC mid-campaign, then two idle boots); user restarted 04:11 UTC; packet 63 launched.**
Packet 62 completed two arms exact on ten fixtures before the host locked up
with no fault line: the latent upsampler's node cost is ComfyUI model
management (0.068 s per call on a resident model), not its forward (0.024 s);
capturing the forward gained nothing (2.529 s vs 2.519 s). The next two boots
locked up idle (23:40 and 23:48 EDT) with nothing running, which points at the
platform rather than the workload. No fault latch exists on this boot. Packet
63 (timed diffusion forwards, resident fast path for model management,
save-behind rerun, pipe control) runs on one server; its runner commits after
every arm because the freezes zero unflushed files. Log `campaign-63.log`.
[Packet 62 results](experiments/ltx25-b70/notes/graph-capture-62-results.md).

**Four-B70 host, September 17 03:05 UTC: LTX server 61 stopped cleanly (one SIGINT, 6 s); packet 62 launches after a five-minute gap.**
Packet 61 measured the latent upsampler's forward at 0.025 s of the node's
0.24 s (11 distinct clips exact); the remainder is model-management and
cross-device glue, so packet 62 adds a phase-timed drop-in of that node, the
captured-forward arm, a save-behind decode mode (MP4 written on the decode
worker) and a pipe control; the upsampler gate now restores itself across
mode switches. Runner `run-campaign-62.sh`, log `campaign-62.log`.
[Packet 61 results](experiments/ltx25-b70/notes/graph-capture-61-results.md).

**Four-B70 host, September 17 02:58 UTC: user-confirmed reboot after a second silent freeze; boot-03 health passed; LTX packet 61 server launched (PID 4523, port 8188).**
The previous boot froze at 00:10 UTC with only the halted DEVICE_LOST LTX
process resident (no launch pending), 43 minutes after the 23:27 UTC fault.
The user restarted the host at 02:47 UTC. Following the external-boot-health
precedent: a boot-03 admission pinned this boot, the unchanged FAULT bytes, the
2,270-record kernel prefix, runtime, packet 61 and the device properties; the
passive check and the one bounded four-card copy/compute/peer-copy probe both
passed with no new kernel records; the old fault was archived under root
review. Packet 61 now runs the latent-upsampler gate campaign (warm clip,
pipe-uptime 12, pipe-up 20, pipe control 12; log `campaign-61.log`). No
driver reset, power change or retry chain.
[Admission and receipts](experiments/ltx25-b70/data/external-boot-health-03/).

**Two-B70 host, September 17 02:45 UTC: two-card depth-5 package accepted from public source (88.32 / 88.49 tok/s pair); the new depth-5 service is on 18124 (87.76 tok/s, 12/12 vs no-MTP); one-card 24K context verified and being promoted.**
The follow-up campaign passed the one-card `no-quantization` profile's back-to-back test (64/64, strict 12/12 at
51.77), found that a 2,048-token prefill chunk lets the one-card depth-5 recipe run 24,576 tokens of context at the
same speed (32K still 0.3 GiB short), showed two-card depth 6 is exact but slower over whole answers, and replayed
the two-card package from an anonymous download of commit `5b494649f`: strict 12/12 identical to no-MTP at 88.49
tok/s, six practical requests with exact repeats, clean stop ([packet](experiments/qwen38-27b-b70/data/2026-09-17-fp8-two-card-depth5/)).
Service: unit `fp8-service-20260917`, state `/mnt/fast-ai/bench-results/fp8-followup-20260917/service`, model
`qwen38-27b-fp8`, 33,024 tokens, one request at a time. Next: the one-card 24K campaign stops it once to verify the
updated one-card launcher, then starts it again (unit `fp8-service-20260917b`).

**Two-B70 host, September 17 01:40 UTC (superseded above): review of the one-card FP8 work passed; two-card MTP depth 5 reclaimed at 88.3 tok/s; service on 18124 (depth 1, 54.71 tok/s, 12/12).**
A review campaign re-tested the shipped one-card package through its own launcher with the gate the earlier work had
skipped (64 prompts back to back plus two queued passes, all identical to no-MTP), plus strict 12/12 at 53.31 tok/s,
long prompts, the chat quality suite and a logprob replay: it holds up. Two fixes landed on the way: the launchers
now start under both Docker image stores, and the package text says 16,384 tokens of context.

- **Two cards:** on the R310 image, no-MTP matches the frozen control 12/12; MTP depths 3, 4 and 5 with the draft
  shortlist pass every gate (strict, 64-prompt oracle, 2K-16K prompts, chat quality) at 80.4 / 84.0 / **88.3 tok/s**;
  depth 1 still measures 54.90, so nothing was lost. The two-card package now ships depth 5 on R310 (`depth-1`
  profile kept); its public-source acceptance replay is the second fresh server and runs in the follow-up campaign.
- **Service:** the depth-1 R304 service was restored by the review runner (unit `fp8-service-20260916`, state
  `/mnt/fast-ai/bench-results/fp8-review-20260916/service-restored-6`). The follow-up campaign stops it once, runs the
  one-card `no-quantization` oracle, one-card context probes, two-card depth 6 and the acceptance replay, then starts
  the new depth-5 service.
- No GPU faults. [Findings](experiments/qwen38-27b-b70/notes/2026-09-16-fp8-review-findings.md),
  [receipts](experiments/qwen38-27b-b70/data/2026-09-16-fp8-review/).
**Four-B70 host, September 16 23:27 UTC: GPU fault latched during the LTX pipelined-sampler arm; PID 6955 halted, no new launches possible on this boot.**
Packet 58 first delivered the corrected results on ten distinct fixtures:
serial 4.584 s per clip (12/12 exact), three-stage pipe **2.519 s per distinct
clip (19/19 exact, 9.9 fps equivalent)**. The pipelined-sampler arm then
faulted `0000:27:00.0` (page fault, devcoredump, DEVICE_LOST) on its third
clip: the second worker's graph captures ran concurrently with the first
worker's replays on the same cards. The arm is retired.
The server stays up halted as evidence; the sealed launcher refuses launches
while the boot journal carries fault lines. Next lever (latent-upsampler
graph capture, packet 60) is prepared inactive and check-only passed.
No retry, reset, power change or reboot was performed; the reboot/reset
decision belongs to the user.
[Results and incident](experiments/ltx25-b70/notes/graph-capture-58-results.md).

**Four-B70 host, September 16 23:20 UTC: LTX packet 58 server launched (PID 6955, port 8188) for the corrected ten-fixture pipeline campaign.**
The host rebooted at 17:23 UTC during Opus's packet 56 start (silent lockup, no
kernel fault line; not this session). An offline audit of the September 15-16
claims found the exactness claims hold for the boat fixture (452 clips hashed,
19 comparator passes) but every throughput prompt used one prompt and one
seed, which hid a stale-conditioning race in encode-ahead, a global-RNG race
between two sampler threads, and a confirmed stale delivery in packet 55
(parked oracle-prompt clips served as stream output). Encode-ahead now binds
to the queued next prompt's text, noise generation is serialised, reused
pipeline indices are refused, and a new driver cycles ten distinct fixtures
with a per-clip oracle. Campaign order: warm clip, serial 12, three-stage pipe
20, pipelined sampler 20; log `campaign-58.log` in the evidence root.
[Audit](experiments/ltx25-b70/notes/2026-09-16-audit-of-sep15-16-claims.md).
No power, swap, driver or reboot action; one launch, no restart chain.

**Two-B70 host, September 15 05:35 UTC: communicator NaN characterization done; user decision needed on NaN comparison.**
Stage `nan-semantics-01` completed cleanly on the newest base with no faults.
All four add formulations match XCCL on every non-NaN result at every shape and
rank; the only differences are NaN payload/sign bits, which XCCL chooses by
element position, so no fixed formula is bit-identical. Stage 05 (the IPC gate)
was not run. Continuing requires the user to accept NaN-class comparison for
this operator. No GPU work is running; port 18124 stays offline by user decision.
[NaN result](experiments/qwen38-27b-b70/notes/2026-09-15-nan-semantics-results.md).

**Two-B70 host, September 16 06:40 UTC: recovered from the fault; service back on 18124 at 54.801 tok/s, 12/12 exact.**
After the user approved a retry: the bounded XPU/XCCL health probe passed on both cards (single-device compute and
rank-to-rank allreduce), a fresh service start reached ready with no new fault, and the strict suite measured
**54.801 tok/s** with all 12 complete outputs identical to the frozen control. No driver reset, power change or reboot
was performed. Fault evidence stays at `/mnt/fast-ai/bench-results/gpu-fault-20260916T0602/`; treat the fault as a
one-off unless it repeats.

**Two-B70 host, September 16 06:05 UTC: GPU fault during a two-card service start; port 18124 is DOWN and no GPU work is running.**
`serve.py` detected the fault, halted and did not retry, exactly as designed.

- **What happened:** the one-card two-user screen finished and stopped cleanly at 06:00:11Z. The two-card service
  started at 06:00:11Z and faulted at 06:02:02Z, about 111 s in, during weight load/compile.
- **Kernel:** `xe 0000:03:00.0` (card2) Tile0 GT0, EngineClass 3 (copy engine): repeated
  `Fault response: Unsuccessful -EINVAL`, then `Timedout job ... in python3`, then a device coredump. No reset,
  recovery or wedged line followed.
- **State now:** no containers, no GPU processes, no driver reset, no reboot, devcoredump still present.
- **Evidence:** `/mnt/fast-ai/bench-results/gpu-fault-20260916T0602/` (kernel log, journal window, states, summary).
- **Next step needs the user:** faults halt work, and a driver reset, power change or reboot is not mine to make.
  A bounded XPU/XCCL health probe is the normal first check once approved.

**Two-B70 host, September 16 00:30 UTC: one-card FP8 packet published; R310 kernel fix replaces the head-group overlay; service back on 18124.**

- **New packet** `qwen38-27b-fp8-vllm-tp1-b70`: package, recipe, 7 measured graphs. It replaces
  the August one-card eager entry, now marked replaced.
- **Image** R310 `ghcr.io/steveseguin/vllm-openai-xpu-qwen38-int4@sha256:eb816507…`: R304
  plus the oneDNN r309 one-card shapes and the kernels r310 GDN output fences.
- **Recommended** (MTP depth 5, INT4 draft shortlist, 13,824 context): 53.45 / 53.55 tok/s on
  two fresh servers, prefill 1,987-2,043 tok/s at 2K-12K.
- **No-quantization profile:** 51.6 tok/s at 12,544 tokens. No MTP: 19.4 tok/s.
- **Checks:** every depth 3-6 and both draft heads are 12/12 identical to no MTP. The context
  screens, the chat quality suite and a 21-request logprob replay are all exact.
- **Package test:** `serve.py` pulled the published image and passed strict 12/12 for both
  profiles, with clean stops.
- **Site checks:** validators and tests pass. `check-pinned-hashes` still reports the 231
  historical Flash-Next drifts from before this work.
- [Final measurements](experiments/qwen38-27b-b70/notes/2026-09-15-fp8-one-card-package-results.md).

**Two-B70 host, September 15 20:50 UTC: one-card FP8 broad matrix, no-quantization draft option, chat quality parity; GPUs in use by research queue.**

- **Depths 3-6 with both determinism overlays:** all 12/12 strict and
  context-screen identical to MTP0.
  - No single metric decides: depth 6 leads early and long-context decode, depth
    4 leads whole answers, and depth 5 stays the balanced default (53.40 tok/s).
- **Draft-only INT4 shortlist head:** worth 20-25% over FP16 shared-head
  drafting.
- **FP16 67k-row draft shortlist (`b70_draft_fp16_shortlist`):** removes all
  quantization. 51.86 tok/s, needs 0.975 memory for a 12,544 context.
- **Chat-mode quality suite** (exact answers, JSON, repeat hash, 7.6K needle):
  depth 5 with either head matches MTP0 exactly.
- **Queued:** R310 kernel build with global memory fences in the GDN output
  kernel, then a 200-repeat census. Its goal is to replace the head-group
  overlay. The two-card service is stopped for this and will be restored
  afterwards.

[Matrix note](experiments/qwen38-27b-b70/notes/2026-09-15-fp8-one-card-depth-draft-matrix.md).

**Two-B70 host, September 15 18:30 UTC: one-card FP8 made deterministic and long-context exact (two overlays); service back on 18124 (54.705 tok/s, 12/12 vs control).**
Broader tests found two one-card-only issues the short strict suite missed.

- **GDN prefill:** identical prompts changed logprobs on every repeat, because
  the XPU chunked delta-rule output races with 48 value heads (7-71 of 200
  repeats at 1K-8K tokens; TP2 24 heads 0/200, and the TP2 service replay is
  bitwise stable).
- **Long-context verify:** depth-5 verifier attention rows differ from decode
  once key length exceeds 1,984 (FA2 census), flipping a near-tie after a
  12,288-token prompt.
- **Fixes:** research overlays `b70_gdn_head_groups` (delta rule in 2×24 head
  groups) and `b70_fa_verify_rows` (verify rows as decode calls above 1,536
  keys).
- **Result:** R309 depth 5 + shortlist at 13,824 context is 12/12 strict and
  18/18 long-context continuations identical to MTP0 on two fresh servers, at
  53.40 tok/s (unchanged), prefill 1,340/1,979/1,947 tok/s at
  512/2,048/12,288.
- **Also fixed:** the embed plugin's dead 2.37 GiB host copy.

[Notes](experiments/qwen38-27b-b70/notes/2026-09-15-fp8-one-card-gdn-prefill-nondeterminism.md).

**Two-B70 host, September 15 16:10 UTC: one-card FP8 depth 5 made exact (R309); 53.5 tok/s lossless; service back on 18124.**
The one-card depth-4/5 answer changes came from the oneDNN W8A16 fixed-K gate
(r137a), which covered only TP2 per-rank shapes; a new census showed full-width
rows identical only for M=1-4. Patch r309 adds the five one-card shapes; the
local image R309 (R304 + rebuilt kernels, `7d3219a0`, not pushed) makes M=1-16
identical. On one card, depths 3/4/5 are now 12/12 against R309 no-MTP. Depth 5
with the existing 67k draft shortlist measured 53.602 / 53.463 tok/s on two
fresh servers at 11,264 / 13,824 context (was 46.9 at depth 3). Depth 6 gave
54.6 once, with a lower full-answer rate. No kernel faults. The two-card service
still runs R304 and was restarted afterwards (state `service-after-r309`): 54.767 tok/s, 12/12 identical to the pre-test control.
[R309 results](experiments/qwen38-27b-b70/notes/2026-09-15-fp8-one-card-r309-depth5-exact.md).

**Two-B70 host, September 15 14:45 UTC: FP8 runs on one B70 (46.9 tok/s lossless); cold-start fix restores 54.8; service on 18124.**
The earlier 54.3 restore readings were a first-request cost: a fresh server
JIT-compiles two MTP draft kernels during the strict suite's first prompt.
`serve.py` now sends one untimed warm-up completion before ready; the restored
service (`final-service-warmup`) measured 54.762 tok/s cold, first prompt 56.54,
12/12 outputs identical to the pre-test control. Official FP8 on one card: a new
lossless host-embedding plugin frees 2.37 GiB, and compiled serving then gives
MTP0 19.3, MTP1 32.5 (20,480 context) and MTP3 46.9 tok/s (16,384 context), all
12/12 identical across fresh servers and to MTP0; MTP4/5 reach 49.7/51.7 but
change three answers and are not qualified. No kernel faults. Research launcher
only; no one-card package yet.
[One-card results](experiments/qwen38-27b-b70/notes/2026-09-15-fp8-one-card-results.md),
[warm-up fix](experiments/qwen38-27b-b70/notes/2026-09-15-fp8-cold-start-warmup.md).

**Two-B70 host, September 15 13:30 UTC: qualified FP8/MTP1 service restored on 18124 and matched pre-test quality and speed.**
The unchanged R304 FP8 TP2/MTP1 service (image `7cd7bb16`, helper state
`/mnt/fast-ai/bench-results/optimization-validation-20260915/restored-service`)
is ready at `http://127.0.0.1:18124/v1`, model `qwen38-27b-fp8`. Strict check:
12/12 complete outputs match the pre-test reference, canaries pass, cache zero,
54.306 tok/s versus 54.855 control (-1.0%, within session drift; the September
14 post-reboot restore measured 54.316). Context profile: all 18 continuations
exact; prefill 2,861/3,670/3,296 input tok/s at 512/2,048/16,384 versus
2,859/3,677/3,305 before. No kernel faults. Today's stopped test containers were
removed after their receipts were saved; incident containers are kept.
[Restore results](experiments/qwen38-27b-b70/data/2026-09-15-post-test-restore/),
[community cookbook claim review](community/sergiiob-b70-inference-cookbook/validation/2026-09-15-qwen38-engine-comparison-review.md).

**Two-B70 host, September 15 13:10 UTC: both transfer optimizations validated; neither is worth adopting; GPUs idle.**
Exact two-card communicator stage 05 passed every quality case at 1/2/512/4,096
rows under the user-approved NaN-class rule, with peer IPC, clean retirement, no
kernel faults, a clean memory guard and container exit 0. Paired operator timing:
153% and 124% slower at 1 and 2 rows (decode), 30% slower at 512 rows, 8.2%
faster at 4,096 rows (5/5 blocks). The gain covers only long-prompt chunks, is
about 1% of prefill before integration copies, and decode gets slower, so XCCL
stays. The metadata tweak (earlier entry) is exact but speed-neutral and stays
off. No GPU work or service is running; port 18124 remains offline by user
decision and can be restored on request.
[Communicator results](experiments/qwen38-27b-b70/notes/2026-09-15-exact-comm-nan-results.md),
[metadata results](experiments/qwen38-27b-b70/notes/2026-09-15-metadata-tweak-results.md).

**Two-B70 host, September 15 12:55 UTC: user approved NaN-class comparison; communicator stage 05 running.**
The user chose to count any two NaN outputs as equal for the exact two-card
communicator; every other bit must still match XCCL. Under that rule all four
formulations match the saved characterization, and stage 05 runs the Native04
arithmetic (`m0`) on the newest base: exact checks at 1/2/512/4,096 rows, then
alternating XCCL-versus-candidate timing, under the memory guard and fault
monitor. It uses peer IPC, the path that coincided with the September 14 fault.

**Two-B70 host, September 15 12:40 UTC: communicator NaN characterization done; stage 05 awaits a user decision on NaN comparison.**
`nan-semantics-01` completed cleanly on the newest base (no faults, guard clean,
exit confirmed). No fixed add formulation matches XCCL bit for bit: every
mismatch is NaN versus NaN with a different payload or sign, XCCL's choice
depends on element position, and all real numbers and infinities matched.
Stage 05 is not admitted under the bit-exact NaN rule. It could continue only if
NaNs are compared as a class; that oracle change is the user's decision. No GPU
work running; same boot `b13caae3`.
[NaN results](experiments/qwen38-27b-b70/notes/2026-09-15-exact-comm-nan-results.md).

**Two-B70 host, September 15 05:25 UTC: metadata tweak validated exact but speed-neutral; exact communicator tests next.**
On the newest base (`506fcc26`) the unchanged server matched all 12 reference
outputs, the native gate passed 36 cases on both GPUs, and four alternating
normal/tweak rounds all matched exactly with zero cached tokens. Writing speed
54.245/54.392/54.450/54.543 tok/s and reading speeds within 0.4% show no gain
beyond control drift; the tweak stays off. Research server 18129 is being
stopped once. Next: the no-IPC NaN characterization (`nan-semantics-01`) for the
exact two-card communicator on the same image, then its stage-05 gate only if a
single add formulation matches XCCL. Port 18124 stays offline by user decision.
[Results](experiments/qwen38-27b-b70/notes/2026-09-15-metadata-tweak-results.md),
[communicator preparation](experiments/qwen38-27b-b70/notes/2026-09-15-exact-comm-fixes.md).

**Two-B70 host, September 15 04:50 UTC: after restart, allocation diagnostic confirmed the OOM cause; metadata research server starting on 18129.**
The user restarted the host (boot `b13caae3`); the bounded health check passed
with no kernel faults. A no-model 2 GiB allocation on the newest image reproduced
the research-launch memory problem at small scale: with both GPUs visible and no
`PYTORCH_ALLOC_CONF`, driver-held host memory grew 2.05 GiB; with
`expandable_segments:True` it grew 0.06 GiB, and with one GPU 0.13 GiB. No GPU
faults. The research launcher now adds the five qualified environment variables
and starts a root host-memory guard that kills the container cgroup without
Docker (live-tested on a throwaway container). The metadata research server is
starting on localhost18129; the preregistered client campaign follows. Port
18124 stays offline by user decision. The exact two-card communication fixes
are being prepared offline. Evidence:
`/mnt/fast-ai/bench-results/optimization-validation-20260915`;
[diagnostic summary](experiments/qwen38-27b-b70/data/2026-09-15-newest-base-alloc-diagnostic/summary.json).

**Two-B70 host, September 15 03:00 UTC: user decision — validate the optimizations on the newest base; the service can wait; host restart pending.**
The user set the goal to validating the transfer optimizations, not restoring
the API. Decisions: (1) run the metadata tweak campaign on the newest upstream
base (`506fcc26`) after fixing its launch environment; (2) fix the exact
two-card communication prototype offline (NaN operand selection versus XCCL,
abrupt-exit retirement), then test it on the cards. The user will restart the
host to clear the GPU fault. After the restart, in order: bounded health check;
research launcher environment fix plus a host-memory watchdog; a small no-model
allocation diagnostic on the newest image; the full metadata campaign; then the
communicator fixes, a no-IPC NaN characterization and its native exact gate.
Any GPU fault halts the work for review; no retries. DFlash stays excluded.

**Two-B70 host, September 15 02:20 UTC: GPU fault during FP8 restore; GPU work halted, API offline, reboot decision needed.**
The bounded standard health check passed on both cards at 01:58 UTC. Loading
the unchanged qualified R304 FP8/MTP1 service in `final-service` then faulted
card 0000:e3:00.0 at 02:00:38 UTC as target weights finished loading: 33
unsuccessful copy-engine (bcs) page-fault responses, 8 engine memory CAT errors,
a bcs engine reset, a timed-out job and a device coredump. The helper halted and
stopped once; the container is gone, no model process owns the GPUs and port
18124 is closed. The campaign `FAULT.json` latch is set and the campaign is
closed; the metadata change remains unvalidated. Same boot; no retry, reboot,
driver reset or settings change by the agent. **Restoring the service needs the
user's decision on a host reboot**; afterwards use a newly admitted recovery
root (health check, qualified service, full strict check). Cause not
established; a swap-out burst preceded the fault by seconds. The research
launch's missing environment variables (see the entry below) do not explain
this fault; the restore carried them.
[Fault note](experiments/qwen38-27b-b70/notes/2026-09-15-fp8-restore-gpu-fault.md).
This supersedes the restore statement below.

**Two-B70 host, September 15 02:00 UTC: research server ran the host out of memory during load; restoring original FP8 service.**
The newest-base V1/native-MTP control on localhost18129 (image `506fcc26`,
upstream `dc36fcce9`) never became ready and served no requests. From about
19:40 UTC its model load exhausted host RAM: the root filesystem stalled, the
owner's monitor blocked and could not stop it, and after about four hours the
kernel OOM killer ended the desktop session, login-screen processes and one vLLM
worker. The container exited at 00:39 UTC (Docker OOMKilled). About 12.7 GiB was
held outside normal memory counters; worker allocations failed inside xe dma-buf
export. No xe memory fault, CAT error or engine reset was recorded; memory has
recovered and no model process owns the GPUs. Same boot; no reboot, driver
reset or settings change. The metadata client never ran. Do not relaunch
that research recipe unchanged: it and the 09:27 freeze candidate omitted five
qualified environment variables, including
`PYTORCH_ALLOC_CONF=expandable_segments:True`; the launcher now refuses. Next:
one bounded standard health check, then
restore the qualified R304 service on 18124 in `final-service` and repeat the
full strict output check.
[Incident note](experiments/qwen38-27b-b70/notes/2026-09-15-research-load-host-oom.md).
This supersedes the loading statement below.

**Two-B70 host, September 14 19:27 UTC: recovery qualified; metadata research loading.**
The original FP8/MTP1 service passed all12 complete frozen-reference outputs,
canaries and cache-zero checks at54.0136 output tokens/s. Its planned graceful
stop completed with no owners and no new GPU fault. Loading the separate
reviewed V1/native-MTP control on localhost18129 for metadata validation.
Port18124 is temporarily offline during this planned test. No custom
communicator, DFlash, target-arithmetic change or quality waiver is enabled.
Same boot; no reboot/reset or host settings changes. The original service will
be restored after the bounded comparison if device health remains clean.
[Recovery and metadata plan](experiments/qwen38-27b-b70/notes/2026-09-14-fp8-recovery-metadata-plan.md).
Raw root: `/mnt/fast-ai/bench-results/fp8-mtp-recovery-metadata-20260914`.
The prior incident entry below remains historical evidence of the halted run.

**Two-B70 host, September 14 18:36 UTC: GPU work halted after exact-TP2 probe fault.**
The corrected communication probe passed 12 finite/edge cases per rank, then
failed exact NaN-payload parity. At 18:30:41 UTC the kernel also recorded BCS
memory faults on both GPUs, a CAT error and driver-initiated engine resets.
The controller preserved the fault latch and confirmed container exit; no
subsequent GPU request or model reload occurred. The causal relationship to
IPC cleanup/process exit is unproven. Do not retry this probe or start a model
under the current faulted campaign. Offline analysis and the failed-attempt evidence packet are complete.

Read-only postflight at 18:36 UTC: no render-device owners, no running Docker
containers, both 18124 and 18129 closed, same computer boot. GPU compute health
has not been requalified. The original service was stopped once at 18:07 UTC for
the planned exclusive test; the API is currently unavailable. No agent reboot,
driver reset or power/memory-setting change occurred.

Metadata relocation passed 36 offline cases on both source versions; its native
and endpoint gates remain unrun. The separate V1/MTP control image is built but
unqualified. No speed measurement or optimization is promoted. Preserve
`/mnt/fast-ai/bench-results/mtp-lossless-transfer-20260914/FAULT.json`, all four
operator-stage snapshots and the earlier unrelated freeze packet below.
[Implementation results and incident](experiments/qwen38-27b-b70/notes/2026-09-14-mtp-lossless-transfer-results.md),
[implementation plan](experiments/qwen38-27b-b70/notes/2026-09-14-mtp-lossless-transfer-plan.md),
[earlier review](community/1337hero-r9700-qwen38-radiance/validation/2026-09-14-mtp-fp8-transfer-review.md).

**Four-B70 host, September15 05:25 UTC: clip 6.415 -> 4.682 s, all exact; GPU work paused for a reboot.**
Qualified position (packet21, `prepared-encoder-graph-capture-21`, manifest
`d515527a6f7eb1277df5f354a46522e6da1597b73fca08a91519caee70fa5498`): warm clip
preview **4.682 s** against a 6.415 s control, sampler **1.942 s** at **1.86x**,
video decode **0.560 s**, text encode unchanged at 1.741 s. Thirteen clips,
**every one bytewise identical** on images, video latent, audio latent and
waveform, at 256x256, 25 frames, 24 fps, native BF16, 8+3 steps. Two independent
exact changes: per-block `torch.xpu.XPUGraph` capture of the 48 transformer
blocks, and the already-qualified axis-cache decoder.
[Result](experiments/ltx25-b70/notes/graph-capture-21-results.md).

**Paused:** packet22 tried to extend graph capture to the video decoder. It was
blocked by a single host read of tensor contents used as a shape
(`int(en.max())`), which returns garbage inside a capture and asked the allocator
for 1,044,902 GiB. Abandoning the capture left a GPU **CAT error and engine
reset** on one card. The driver recovered and the host is up with all four render
devices free, but the sealed launcher greps the whole boot journal for device
faults and will now refuse every launch on boot `831530c8`. **A reboot is needed
before GPU work resumes**; nothing else is blocked.
[Analysis and the one-line fix](experiments/ltx25-b70/notes/vae-graph-capture-blocked-01.md).

Earlier on the previous boot, two spontaneous `xe` GuC hard lockups occurred, the
second of which froze the host; the first ran ordinary eager clips before graph
capture existed, so it is not attributable to this work.
[Incident](experiments/ltx25-b70/notes/xe-lockup-incident-01.md).

**Four-B70 host, September15 03:30 UTC: first exact LTX speedup landed; sampler 1.83x.**
Per-block `torch.xpu.XPUGraph` capture of the 48 native transformer blocks cuts
the sampler from 3.669 s to 2.001 s and the warm clip from 6.459 s to 4.792 s,
with **all ten campaign clips bytewise identical** on images, video latent, audio
latent and waveform. Checkpoint, precision, 256x256, 25 frames at 24 fps and the
original 8+3 sampler schedule are unchanged. Packet
`prepared-encoder-graph-capture-19`, manifest
`e378498bb183982c59a76c366efc8d9e39f0197c747fb01e176299ab05ae84c7`, server
`encoder-server-graph-capture-19` (PID22639) on user-reboot boot `64bbd5d2`.
Each of the 96 graphs is proven bit-identical to a fresh eager execution of the
same block before it is used, and proven non-inert. See
[the result](experiments/ltx25-b70/notes/graph-capture-19-results.md) and
[why the clip was dispatch-bound](experiments/ltx25-b70/notes/dispatch-bound-diagnosis-01.md).

Two candidate levers were **retired on evidence** rather than pursued: the
transformer output-column partition (the linear layers already run at the
537 GB/s copy roofline, so it attacked the wrong term) and whole-model
compilation (the lane's own all-48 screen is exact but 0.93 s *slower* in the
sampler). Packet13's text-encoder full residency is exact and speed-neutral;
it is kept as the base because it removes a per-request growing CPU offload.

The sampler is now GPU-bound: 77.6% of profiler samples wait on the model call,
the adapter's own Python is ~12%, and per-step cost finally scales with token
count (165 ms at 64 tokens, 224 ms at 256) where eager barely did. The next
structural inefficiency is that **only one of four B70s computes at any instant
during sampling**: blocks 0-20 run on XPU0, then 21-47 on XPU1, strictly
serially, while XPU2 and XPU3 sit idle. No reboot, driver reset or
power/memory setting change was made.

**Four-B70 host, September14: packet12 idle after safe memory refusal.**
LTX PID11888/exec40923 remains healthy and idle at `http://127.0.0.1:8188`,
packet12 manifest`b29b750c31feda9d4be7fdc768e876a1f5d58ad11a699022b1d8ae6bdaa59666`.
Screen02 client/exec12642 exited1: five control clips passed all four raw
oracles, then the first encoder transition refused replacement construction.
After full old-encoder weakref/registry release, available RAM was46.58GiB,
below the unchanged56.89GiB construction floor. Diffusion/VAEs/upscaler stayed
owned. No replacement encoder was allocated. Requests halted; no retry/reload.
Postflight: same user-reboot boot5414a640, empty queue, only11888 owns renders,
no FAULT latch and no new kernel entries. No agent reboot/reset/settings action.
Preserve the failed screen; it does not qualify host timing or full transitions.
Terminal evidence is exported (325 text files, exact archived hashes).
Next: keep a fixed encoder mode for later sampler work; separately design
private ownership reuse without checkpoint/constructor allocation. The next
sampler candidate is a two-stage, same-device full-N versus half-N Linear
exactness diagnostic; its new adapter needs source review before any reload.
Existing constructor floor and all quality gates remain unchanged.
[Postflight](experiments/ltx25-b70/data/host-embedding-screen-02-postflight.json).

**Historical Four-B70 host, September14 19:32 UTC: bounded post-reboot health assessment passed.**
One diagnostic (parent8068/worker8088) passed four exact copy/compute checks and
twelve directed BF16 copies on the expected ordinal UUIDs. Both exited0;
locked passive postflight confirmed released render nodes and no new kernel
faults. No agent reboot/reset or host settings change. The root operator
archived the old-boot FAULT byte-for-byte after separate evidence review;
the prior failed model campaign remains invalid. LTX is still stopped.
The guarded tiny CPU qualification then passed all six cases (child8812,
exit0): actual encoder/registry release, exact CPU output and memory-refusal
ordering; both GPU backends stayed uninitialized. Parent postflight was clean.
Next: successor runtime/client preparation and cold-assembly RAM review.
Large model transitions, full clip performance
and endurance remain unqualified; a new fault halts requests.
[Health result and admission](experiments/ltx25-b70/data/external-boot-health-02/recovery-admission.json).
[CPU lifecycle result](experiments/ltx25-b70/notes/host-embedding-resident-lifecycle-native-01.md).

**Historical four-B70 state, September14 19:20 UTC: user-reported freeze and user-confirmed reboot.**
The computer is now on boot `5414a640-c223-4a67-baa2-ec2f4c4c5917`,
started about19:12 UTC. The user confirms restarting it after a freeze; the
agent did not reboot or reset it. LTX remains stopped and the original FAULT
latch remains byte-identical. The planned same-boot health diagnostic never
ran (its one-use output directory is absent); its old-boot admission is invalid.
Passive checks find unowned render nodes and no detected current-boot kernel
fault. These observations do not qualify GPU health. A new, separately reviewed
bounded assessment is being prepared; no model or native CPU tests are admitted.
The previous boot's kernel tail contains the earlier18:13 xe fault; it does not
establish the cause or precise time of the later reported freeze.
[Passive incident evidence](experiments/ltx25-b70/data/user-reported-freeze-02/report.json).

**Historical four-B70 state, September14 18:13 UTC: LTX stopped after host OOM and xe fault.**
Linux OOM-killed LTX PID116013 at18:12:58 UTC during the third component
transition (host-table back to control), before the next clip completed.
Exec15201 exited137. Xe GPU0 reported a bcs engine fault/reset at18:13:01,
after the process kill. Client116455/exec91667 exited1 and submissions halted.
The root FAULT.json now records the incident; no new native GPU/CPU work.
No automatic reboot, driver reset, application restart or settings change.
The computer remains on the same boot; passive postflight is preserved below.

Ten completed clips passed all four raw oracles, including all five host-table
clips with full remaining encoder residency. Host warm previews6.322–6.455s
versus first-control6.378–6.576s; the final control is missing, so this is an
incomplete screen and no speed promotion. The failed export and memory audit
are preserved. An inactive successor retains diffusion/VAEs/upscaler across
encoder changes, requires old encoder owner release, and checks separate
restore/construction RAM budgets. Ten stdlib fake/header-only tests and an
independent source review passed. Actual CPU lifecycle qualification, a new
packet/client and native testing remain pending under the fault latch. Its
memory guards cover encoder transitions, not initial diffusion construction.
[Transition fix](experiments/ltx25-b70/notes/host-embedding-clip-only-transition-01.md),
[memory audit](experiments/ltx25-b70/notes/host-embedding-transition-memory-audit-01.md).
The separate C++ CPU v8 cache-policy proposal is also source-only and inactive.
Keep successful raw parity evidence and all failures.
[Incident postflight](experiments/ltx25-b70/data/host-embedding-screen-01-incident/postflight.json).

The earlier four-B70 entries below are historical snapshots; the fault state
above supersedes their live-process and pending-launch statements.

**Four-B70 host, September14 18:07 UTC: packet11 ready; encoder comparison starting.**
LTX PID116013/exec15201 serves `http://127.0.0.1:8188`, using
`prepared-encoder-host-embedding-11` at manifest
`34b7ff2f7a74b6951f87dd2621738b37930d15a5de9d064409c8b12351adcf08`.
All four startup device checks, strict determinism, complete endpoint identity
and both new node interfaces passed. Same computer boot, no host/settings action.
Client PID116455/exec91667 runs the bounded15-clip `host-embedding-screen-01` comparison, with original
transformer/decoder and all four raw oracles. No GPU quality/speed claim yet.
[Startup admission](experiments/ltx25-b70/data/host-embedding-migration-11/startup-admission.json).

**Four-B70 host, September14 18:05 UTC: controlled LTX application migration.**
Packet10 PID84255/exec33936 exited0 after one SIGINT to load reviewed packet11.
The computer is on the same boot; no host or memory/power settings action.
Packet11 manifest34b7ff2f7a74b6951f87dd2621738b37930d15a5de9d064409c8b12351adcf08
passed CPU integration, source assembly, builder and startup offline gates;
the independently reviewed15-clip client passed10 stdlib checks and source
admission. Starting the application and verifying registration precede all clips.
[Migration evidence](experiments/ltx25-b70/data/host-embedding-migration-11/preflight.json).

**Four-B70 host, September14 17:54 UTC: actual CLIP integration CPU gate passed.**
The inactive host-table adapter passed all six actual tiny CPU CLIP integration
groups, including unchanged memory estimation/native owner loading, clone and
state lifecycle, byte-exact encoding, bounded metadata observations and inference
tensors. PID112132/exec53199 exited0; both GPU backends remained uninitialized.
The resident component assembly also passed nine stdlib lifecycle/source tests.
Full-model GPU residency, original four-output clip parity and speed remain
unqualified. Packet11 and its comparison client are being prepared offline;
packet10 PID84255/exec33936 remains the live application. No reload or host
settings action occurred. The17:54 postflight found the same full identity,
empty queue, only84255 on all four render nodes, and no faults.
[CPU evidence](experiments/ltx25-b70/data/host-embedding-integration-postflight-01.json).

The separate C++ CPU v7 fixture installed the reviewed virtual CPU registry and
completed one eager call. Its first compile halted at the retained CUDA
current-device trap in AOT cache system metadata; no compiled result or C++ call
completed. Both GPU backends remained uninitialized. Preserve the refusal;
no unchanged retry. This does not block the encoder comparison.
[V7 result](experiments/ltx25-b70/native-cpp-block-01/guarded-v7-result-01.json),
[postflight](experiments/ltx25-b70/native-cpp-block-01/guarded-v7-postflight-01.json).

**Four-B70 host, September14 17:34 UTC: encoder CPU proof passed; application unchanged.**
The CPU embedding candidate passed all six actual-source groups: raw-byte
token/embedding equality, named-owner loading, clone/detach/restore, inference
storage, mutation refusals and installation rollback. PID107471/exec35632
exited0 with both GPU backends uninitialized. This is a tiny CPU fixture proof;
GPU residency, full-clip equality and speed remain unmeasured. Next: inactive
CLIP/runtime integration with explicit CPU and encoder ownership, followed by
native gates. [CPU results](experiments/ltx25-b70/notes/host-embedding-cpu-v3-results-01.md).

Packet10 PID84255/exec33936 remains healthy and idle with the same full endpoint
identity, empty queue, sole ownership of all four render nodes and no fault.
Saved-event attribution puts about1.82s in encoding and3.54s in the two sampler
nodes. A new inactive CPU embedding ownership candidate could free1,920MiB of
encoder VRAM and replace465MiB of recurring weight uploads with7.5MiB of token
rows. Native correctness/residency and speed are unmeasured; unchanged memory
reserve and full actual residency remain required. Source review caught and
corrected named-owner loading and inference-tensor version assumptions.
[Candidate](experiments/ltx25-b70/notes/host-embedding-gather-candidate-01.md),
[review](experiments/ltx25-b70/notes/host-embedding-source-review-01.md).

The guarded C++ CPU v6 diagnostic verified PyTorch's built-in CPU detection
disable setting and completed one eager call. Generic Dynamo torch-function
handler registration still enumerates device interfaces; the first compile
halted at that retained trap. Both GPU backends stayed uninitialized; no
compiled C++ qualification yet. A future explicit CPU device-registry policy
needs source review; no unchanged retry is scheduled. Encoder integration
continues independently. No live application or host action occurred.
[V6 refusal](experiments/ltx25-b70/native-cpp-block-01/guarded-v6-native-attempt-01.md).
Unconditional cross-step text K/V reuse was rejected from the actual checkpoint
and source: ADaLN changes the projection inputs with timestep.
[Audit](experiments/ltx25-b70/notes/cross-step-text-kv-audit-01.md).

**Four-B70 host, September14 16:57 UTC: decoder confirmation complete; scoped gain retained.**
All18 balanced `na-axis-confirm-01` clips passed the four original raw-output
oracles and full24-call decoder checks on unchanged packet10 PID84255/exec33936.
Across this screen and confirmation,29/29 clips are exact. All six balanced
decoder comparisons favor the cache, median−83.231ms. Whole-preview effects
split3wins/3losses, median−41.966ms; preview medians remain about6.4s. Retain the
local decoder gain, with no overall speed promotion or streaming qualification.
Client31882 exited0; same boot, queue empty, onlyPID84255 owns all four render
devices, no fault. Default route is original; private axis-cache remains
available. No reload was required for confirmation. Next: saved-event attribution
of encoder/sampler variation and the remaining transformer/encoder costs.
[Confirmation results](experiments/ltx25-b70/notes/na-axis-confirm-01-results.md).

**Four-B70 host, September14 16:42 UTC: decoder screen passed; small speed gain to confirm.**
PID84255 serves `http://127.0.0.1:8188` in exec33936, packet
`prepared-encoder-na-axis-10`, manifest
`d6ec6c63869d30dbe009708095f53811372e228becf16b7475ad30d11213fe6a`.
Four startup device checks, strict determinism, full identity and private decoder
node registration passed. Packet09 PID82046 exited0 after one SIGINT following
the reviewed source-pin correction; same computer boot and no fault recorded.
All11 `na-axis-screen-01` clips passed full original four-output raw parity;
nine scoped decodes passed the complete24-call sequence and owner/config checks.
Cache previews6.297–6.446s; median paired changes −119.528ms preview and
−83.436ms decoder. Client80638 exited0; queue empty, no fault, original dispatch
and default NA route. This is a screening gain, not a promotion or streaming
qualification. Next: preserve terminal evidence and prepare a balanced18-request
confirmation on this same application. No reload is required. Halt submissions
on failure without cycling the service.
[Screen results](experiments/ltx25-b70/notes/na-axis-screen-01-results.md).
The separate guarded CPU compiler probe exited1 after blocking an import-time
`torch.xpu.device_count` query; XPU stayed uninitialized, no model/compile calls
occurred, and LTX PID84255 remained idle and healthy. It did not reach the earlier
cache-metadata hypothesis. No retry is scheduled during confirmation.
[Guarded probe](experiments/ltx25-b70/native-cpp-block-01/guarded-v2-native-attempt-01.md).
[Corrected preparation](experiments/ltx25-b70/notes/na-axis-runtime-10-prepared.md).
This supersedes all older PID/startup statements below.

**Four-B70 host, September14 16:33 UTC: packet09 node startup rejected; zero clip requests.**
PID82046 serves `http://127.0.0.1:8188` (exec49702) with an empty queue.
All four startup device checks passed and strict determinism is enabled, but
`LTXNAAxisDecode` failed registration before router installation: its sd.py pin
incorrectly names the upstream source rather than the inherited encoder source.
No native campaign was launched, and no automatic retry follows. Preserve this
idle application and packet09 while correcting the source integration offline.
Old PID66846 exited0 after one SIGINT; computer boot remains
`8e4b1b65-1c38-47bb-8ca5-e4fd6bbdf94a`, no host reboot or settings changes.
[Startup failure evidence](experiments/ltx25-b70/data/na-axis-migration-09/startup-failure.json).
This supersedes every older live PID and next-launch statement below.

**Four-B70 host, September14: decoder packet09 preparation (historical).**
Packet `/mnt/fast-ai/bench-results/ltx25-baseline-20260913/prepared-encoder-na-axis-09`
is sealed at manifest`a53e06ae5bd1be8931eff11d4e9112b850912147b37fcabf1bda064b12f419ed`.
The private original-VAEDecode integration passed9 CPU groups; the11-request
client passed14 stdlib checks and offline packet admission. Root reviewed the
node, builder, receipts and client; independent builder review found no blocker.
The new graphs change only decoder374 and retain original transformer dispatch.
Startup must prove the node is registered through object_info before requests.
[Prepared package](experiments/ltx25-b70/notes/na-axis-runtime-09-prepared.md).
PID66846/packet08 is still the live healthy application; no09 native request
or application reload has occurred yet. Next: one controlled application reload
to load09, then the bounded bare/original/cache comparison with full raw parity.

The separate C++ CPU tiny-block probe stopped after detecting unintended XPU
initialization during the first Python-boundary compile; no C++ compiled call
followed. Root checked an empty queue, no FAULT or new kernel entries, and only
the original LTX PID owning the four render devices. That probe stays separate;
its source-backed cache metadata/driver initialization hypothesis and inactive
guarded successor are preserved. Do not run CPU compilation during native timing.

**Two-B70 host, September 14: user-reported freeze during candidate startup.**
The user restarted the computer. Current boot is
`5ba85b30-0455-466a-b9fc-d9132975417e`; the prior boot ended after logs stopped
at about 09:27:55 EDT. The newest-base/V2/DFlash2 candidate never reached
readiness or benchmark requests. Its last model log is target loading, not a
completed draft or generation operation; cause remains unknown. Do not retry
this candidate unchanged. Both GPUs passed bounded compute and XCCL recovery
checks with no new kernel faults. The original R304 FP8/MTP1 service is healthy
at `http://127.0.0.1:18124/v1`, model `qwen38-27b-fp8`; post-reboot strict checks
passed 12/12 complete outputs and all 18 measured
512/2K/16K continuations match the pre-incident control, with cache zero.
Strict decode measured 54.3158 tokens/s and all recovery monitor windows passed.
Its persistent helper owns
`/mnt/fast-ai/bench-results/amd-transfer-fp8-20260914/restored-service`.
Preserve the stopped candidate container and all raw evidence under
`/mnt/fast-ai/bench-results/amd-transfer-fp8-20260914`;
`FAULT.json` records the incident. The root fault receipt remains preserved;
the explicit recovery admission
applies only to the original qualified service. The earlier control
and exact-but-neutral projection screen remain valid separate observations.
[Incident receipt](experiments/qwen38-27b-b70/data/2026-09-14-amd-transfer/freeze-incident.json),
[final results and recovery evidence](experiments/qwen38-27b-b70/notes/2026-09-14-amd-transfer-results.md).

**Four-B70 host, September14: retained profile captured; recorder failed after exact clip.**
The same packet08 PID66846 remains alive and idle, now on **compiled all48**
dispatch. One diagnostic clip matched all four original raw outputs; its graph,
component and owner evidence still passes. The recorder then rejected its own
run name during output inventory (`unregistered/protected run`). No restored
request, retry, deletion, application reload or host action followed. Client
exec11241 exited1; bounded nonblocking profiler exited0. Queue/kernel postflight
clean, no FAULT latch. This is a recorder integration failure, not a device or
numerical fault, and it supersedes the restored-dispatch claim immediately below.

[Profile/postmortem](experiments/ltx25-b70/notes/retained-multiblock-profile-01-results.md)
preserves the trace and exact clip. Offline analysis and a corrected recorder
continue; do not rerun the failed campaign. The saved profile is sufficient for
the next source investigation: decoder geometry-mask construction and native
operation wrapper overhead. No speed promotion or streaming qualification.

The inactive [per-call decoder axis cache](experiments/ltx25-b70/notes/na-axis-cache-01.md)
now passes23 CPU exactness/lifecycle groups, including unchanged SDPA inputs and
call order. Root reviewed the patch and tests. Its source-derived untiled path
reduces522 axis builds to100 with at most1,878 bytes predicted cached payload;
the general cap is256KiB plus allocator/metadata overhead. Native shape coverage,
full-clip equality and speed remain pending. The startup-only scoped router
passed11 actual Kitchen CPU dispatcher lifecycle groups with XPU access
blocked; root reviewed source/tests. [Routing gate](experiments/ltx25-b70/notes/na-axis-router-cpu-01.md).
No installed or loaded runtime source changed. Next: private original-VAEDecode
node integration, complete native shape/route receipts, then a sealed packet and
bounded original/cache/original clip comparison. Keep the C++ experiment separate.

The independent [private C++ operator prototype](experiments/ltx25-b70/native-cpp-ops-01/README.md)
built once on CPU and passed119 operator/fake comparisons with exact outputs.
Small matched CPU dispatch observations are favorable but do not predict XPU
speed; larger RMS samples include a loss and substantial noise. Root reviewed
the C++ source and test/timing drivers. This namespace has CPU implementations
only; compiled tiny-block, XPU and full-clip qualification remain pending.
At16:07UTC the application was still healthy and idle on compiled all48 with
the same boot, empty queue and no kernel/fault evidence after the CPU work.
[Observation](experiments/ltx25-b70/data/retained-profile-final-observation-01.json).

**Four-B70 host, September14: packet08 native screen complete; original selected.**
PID66846 serves `http://127.0.0.1:8188`, manifest
`a32f645772d2ef59d46b66c9181f1d9433950172bcc763924de8aa7acb679b6b`.
All12 screen03 clips match all four original raw outputs, including all48
compiled blocks. Compiled previews7.38–8.04s remain slower than adjacent original
controls6.39–6.59s; median penalties1.273s preview/0.927s samplers. No promotion.
Client exec97668 exited0; server exec53546 is idle on restored dispatch with
all48 retained. Queue empty, clean kernel postflight and no FAULT latch.
[Native results](experiments/ltx25-b70/notes/multiblock-screen-03-results.md).
Old PID56711 exited0 after one SIGINT. Same host boot; no computer reboot,
driver reset or power/memory changes. [Startup](experiments/ltx25-b70/data/multiblock-migration-08/startup.json).

Next: complete and review the packet08-only retained diagnostic profiler client,
then one warmed compiled clip with bounded nonblocking stack sampling and one
restored control after all gates pass. This reuses the current application;
no profiler/GPU diagnostic request has occurred yet. It must bind screen03's
same-process qualification and preserve full-output/receipt/identity/fault gates.
The CPU traversal improvement is not a native video speed claim. This supersedes
older live PID56711/packet07 and running-client statements below.

**Four-B70 host, September14: packet07 screen complete; original dispatch selected.**
PID56711 serves `http://127.0.0.1:8188`, manifest
`afdbad186a6873a286f93e9d1e715f6bf4c17e1552d75dbce2a3e03c0a1f35c1`.
All 12 screen02 clips match all four original raw outputs, including all48
compiled blocks. Warm compiled previews7.59–7.65s remain slower than adjacent
restored controls6.37–6.45s (median penalty1.214s preview/1.167s samplers).
Client exec40600 exited0. Server exec70494 is idle on restored dispatch with
all48 retained; queue empty, clean kernel postflight and no FAULT latch.
[Native results](experiments/ltx25-b70/notes/multiblock-screen-02-results.md).
Old PID39793 exited cleanly after one SIGINT. Same computer boot, no host reboot,
driver reset or settings changes. [Startup](experiments/ltx25-b70/data/multiblock-migration-07/startup.json).

A subsequent offline replay measured only52.5ms potential savings from compact
receipt serialization across528 calls, with all parsed fields equal. This is
CPU/filesystem attribution, not a native speed result; no reload is warranted
for it alone. A corrected native-class CPU fixture then measured0.480s per528
route calls with fake compute, preserving1584 state/registry boundaries. The
separate profile points to repeated metadata traversal; this is not native
speed attribution. The inactive single-traversal state/hook candidate then
passed all60 existing lifecycle checks and measured0.313s in the same CPU
fixture versus earlier0.480s. No native speed claim; focused alias/None-state
gates and native qualification remain pending. Next: finish those focused CPU
checks and prepare the next native comparison without touching live packet07.
[Candidate and CPU cost](experiments/ltx25-b70/notes/onepass-state-04-cpu.md).
[Replay evidence](experiments/ltx25-b70/notes/serializer-replay-cpu-01.md),
[metadata attribution](experiments/ltx25-b70/notes/metadata-dispatch-cpu-02-results.md).
This supersedes PID39793/packet06 and running-client statements below.

**Four-B70 host, September14: multiblock screen complete; exact but slower.**
PID39793 serves `http://127.0.0.1:8188` on packet06, manifest
`3676b1e47b514f5c28597063b42c9806ed13639cc2dde0f3b25fd44564c08394`.
All 32 clips passed all four original raw-output comparisons, including all48
compiled blocks. Median all48 penalty was +1.303 seconds versus adjacent
restored controls; no speed promotion. The client exited zero. The application
is idle on restored dispatch, queue empty, kernel postflight clean and no FAULT
latch; all three compiled selections remain retained. Server exec38020.
PID17769 exited after one SIGINT; same host boot, no computer reboot, driver
reset or power/memory-setting changes. [Native results](experiments/ltx25-b70/notes/multiblock-screen-01-results.md).

The next inactive adjacent-state reuse03 patch passed all 60 CPU checks for
both parent and candidate, preserving three validation boundaries while
removing two adjacent duplicate state checks per block call. Native quality
and speed remain pending. Prepare its sealed runtime and bounded comparison,
then perform any necessary controlled application reload within authorized work.
[Patch and CPU evidence](experiments/ltx25-b70/notes/adjacent-state-reuse-03-cpu.md).
This supersedes earlier process, inactive-packet and running-client statements below.

**Four-B70 host, September 14: native block compilation exact; paired timing complete.**
PID17769 serves `http://127.0.0.1:8188`, server `encoder-server-compiler-05`,
packet `prepared-encoder-compiler-05`, manifest
`45dc23a7c0a0a234412e31a36225716edf60bb16ad342d96fe12f65139bccbe5`.
All nine compiler-screen-04 clips match all four original raw outputs. Five
compiled clips covered three scenes; both native stages passed eager/compiled
and compiled/repeat checks. Two emitted graphs each retain15 native RMS, six
sigmoid and two tanh-GELU calls. This qualifies block24 only, with no demonstrated
speed win (warm compiled median6.607s; restored boat about6.49s).
Postflight: empty queue, matching identity, clean kernel and no FAULT latch.

The bounded18-request `compiler-timing-01` completed on this same process, with
all original-output checks passing. Median compiled-minus-adjacent-control mean
was+99.797ms preview and+17.977ms sampler intervals: a measured speed loss, not
promotion. The application is idle on restored dispatch, with the qualified
compiled candidate retained and no fault. Across both campaigns27 clips passed,
including11 compiled clips. [Paired results](experiments/ltx25-b70/notes/compiler-timing-01-results.md).

An inactive registry-binding reuse patch removes one duplicate full registry
walk per lifecycle validation while keeping all late-mutation/ownership checks.
Parent and candidate native CPU lifecycle gates passed; no GPU speed result or
deployment. Next: qualify overhead changes and prepare bounded multi-block
selection without per-block application reloads. Continuous real-time generation
remains incomplete. [Patch and CPU evidence](experiments/ltx25-b70/notes/compile-registry-reuse-01-cpu.md).
The multi-block successor now passes CPU qualification. Initial five-block
capture failed at graph9 under the unchanged recompile_limit8; its preserved
successor uses private per-block compiler entry frames and passed10graphs,
20 block cases with exact eager/repeated outputs, plus54 native CPU lifecycle
checks. Packet06 is prepared and inactive, manifest
`3676b1e47b514f5c28597063b42c9806ed13639cc2dde0f3b25fd44564c08394`;
its launcher check-only passed. PID17769/packet05 remain unchanged and idle;
passive kernel/fault checks passed. Next: finish the bounded multiblock client,
then a necessary controlled application reload and native GPU qualification.
No new GPU speed/quality result or application reload in this preparation.
[CPU fix and preparation](experiments/ltx25-b70/notes/multiblock-private-entry-02.md).

[Exact native results](experiments/ltx25-b70/notes/compiler-screen-04-results.md),
[scaling/guard audit](experiments/ltx25-b70/notes/compiler-screen-04-conditional-scaling-audit.md),
[prepared source](experiments/ltx25-b70/notes/native-activations-runtime-05-prepared.md).
This supersedes all earlier process and failed-candidate state below.

**Four-B70 host, September14: native RMS compiler successor running.** One
controlled LTX application replacement completed: PID6502 exited cleanly after
one SIGINT; render ownership cleared and the port was available. The computer
was not rebooted. PID12199 now serves `http://127.0.0.1:8188` from
`encoder-server-compiler-04`, packet `prepared-encoder-compiler-04`, manifest
`c4e0f7e56fc7bbc51101894d79d279dd9886f07272868dc99cc7953c647a65c9`.
Four-card startup checks and strict after-import determinism passed; endpoint
identity matched. No fault latch. The candidate preserves original native RMS
calls inside one compiled block; small CPU gates passed, native GPU/full-clip
qualification failed in compiler-screen-03: audio differences fell from5,923 to10
bytes; video remains54 bytes different. Both eager clips matched all original
outputs (warm7.954s). The first compiled block failed before repeat/stage2/full
clip; no speed result is qualified. Queue empty, kernel clean, no FAULT latch.
The numerical gate remains failed; do not retry it. Next is remaining rounding
localization. [Result](experiments/ltx25-b70/notes/compiler-screen-03-results.md).
This supersedes PID6502 and historical blocked/fault states below.
[CPU qualification](experiments/ltx25-b70/notes/native-rms-cpu-qualification-01.md),
[prepared source](experiments/ltx25-b70/notes/native-rms-runtime-04-prepared.md).
The separate native activation successor is now CPU-qualified:21 guard checks,
four tiny block cases, and two emitted graphs each retaining15 RMS/six sigmoid/
two GELU calls. It is not deployed; native GPU and full-clip parity remain
pending. Prepare its immutable packet/client before another necessary controlled
application reload. [Candidate and exact scope](experiments/ltx25-b70/notes/native-activations-cpu-qualification-01.md).

**Two-B70 host, September 14: AMD transfer tests authorized.** The unchanged
FP8 service at localhost:18124 passed 12/12 full-output reference checks and
short/16K continuation controls. A newest-upstream candidate with the accepted
arithmetic overlay is being built for a bounded projection-dispatch and DFlash2
screen. The original service is still running during CPU preparation; one
controlled maintenance transition will precede exclusive GPU testing. No new
runtime or speed result is promoted. Evidence root:
`/mnt/fast-ai/bench-results/amd-transfer-fp8-20260914`.
[Preregistration](experiments/qwen38-27b-b70/notes/2026-09-14-amd-transfer-prereg.md).

**Four-B70 host recovered after an external boot, September14.** Current boot
`8e4b1b65-1c38-47bb-8ca5-e4fd6bbdf94a` differs from the faulted boot; all three
old processes are absent. Four-card copy/compute and clean-kernel checks passed,
with render ownership clear after exit. The original FAULT was preserved
byte-for-byte under `external-boot-recovery-01/historical-FAULT.json` and an
explicit recovery admission was recorded there. No reboot, driver reset or host
setting change was performed by this agent. This supersedes the blocked status
below; the full generation goal remains incomplete.

The prepared decoder mask-extent candidate passed all16 small XPU:3 native
mask/attention cases, including BF16/F32 and exact repeats. Kernel postflight is
clean and render devices were released. Full-clip parity and speed are still
unmeasured; installed Comfy Kitchen remains unchanged. Compiler packet03 is now
running as PID6502 at `http://127.0.0.1:8188`, server directory
`encoder-server-compiler-03`, manifest
`9ecd5f9863289e00a934c1f4f400582092f37d0ee92035512fc095773ad02980`.
Startup four-card checks and strict after-import determinism passed; endpoint
identity matched. Campaign `compiler-screen-02` completed two exact eager clips
(warm control6.262s), then stopped on first native compiled block24 mismatch:
54 differing video bytes and5,923 audio bytes, finite/layout-matched. No compiled
full clip, repeat or speed result is qualified. The queue is empty, PID6502
remains present, the compiler gate is failed, and kernel postflight is clean.
Preserve the process/evidence; do not retry the failed gate. Next is numerical
localization, with native RMS reduction decomposition a source-supported
hypothesis. [Failure and evidence](experiments/ltx25-b70/notes/compiler-screen-02-results.md).
[Recovery evidence](experiments/ltx25-b70/notes/external-boot-recovery-01.md).

**LTX goal blocked on host recovery, September14.** The same kernel fault and
pending-interrupt native clients were revalidated across three consecutive goal
turns. Prepared source work is saved, but the next meaningful steps require a
healthy native runtime: compiler exactness/speed and actual continuation quality.
No new native request, restart or reboot was performed. Generation remains about
6.4s per clip; the full real-time goal is incomplete. Do not continue producing
synthetic-only qualification as a substitute for those native measurements.
[Recovery handoff and resume order](experiments/ltx25-b70/notes/native-progress-recovery-handoff.md).

**Four-B70 host, September14: kernel incident; GPU requests halted.**
`/mnt/fast-ai/bench-results/ltx25-baseline-20260913/FAULT.json` is present.
The first compiler-screen-01 eager control clip completed generation, but client
PID96119 became stuck in a kernel cross-CPU TLB wait during post-request work.
CPU13/CPU6 soft lockups, RCU stalls and blocked system tasks are recorded.
Only eager mode ran: no compiled candidate/block execution or completed oracle
qualification. PID95931 remains present with an empty queue; one client SIGINT
was sent, exit unconfirmed. No reboot/reset/restart or host-setting changes were
performed after the fault. The stale campaign `running` status is superseded by
this incident and the fault latch. **No new GPU requests until recovery and
health are established.** Preserve all failed/current clip files and the earlier
25/25 exact encoder results. [Incident and evidence](experiments/ltx25-b70/notes/compiler-screen-01-kernel-incident.md).

Subsequent source progress: the same boot/client kernel wait persists. One
bounded CPU-stack diagnostic timed out without a captured backtrace; no retry,
reboot or new GPU request. Future compiler packet03 is prepared with explicit
host-fault detection; its copied launcher correctly refuses current FAULT.
Runtime remains on packet02, never migrated to03.
[Preparation and fault revalidation](experiments/ltx25-b70/notes/kernel-fault-source-progress-01.md).

Further offline work prepared a continuation graph constructor (13 source tests
passed) and two inactive loader-memory patches. The loader's tiny Torch CPU
test did not finish: PID102144 remains present with SIGINT pending; no numerical
pass or RAM-saving result exists. No further Torch/GPU test retries on this
faulted host. The last durable test artifact is the extracted candidate source,
which does not identify the exact stalled instruction.
[Loader candidate and incomplete test](experiments/ltx25-b70/notes/loader-memory-candidate-02.md);
[continuation source checks](experiments/ltx25-b70/notes/continuation-graph-constructor-cpu.md).

The float-anchor provider and closed continuation graph are now implemented
offline. Thirteen byte-reader tests and12 integration checks passed without
Torch imports; frame extraction also matched independently read final frames
from all three protected originals, whose full-image hashes still matched.
No new video saved or generated. Native tensor construction, runtime deployment,
predecessor lineage, delivery state, continuation quality and speed remain
unqualified. [Implementation and evidence](experiments/ltx25-b70/notes/continuation-anchor-provider-01.md).

Offline continuation work now includes a bounded four-tensor verifier/frame
reader and a single-request coordinator with predecessor binding, explicit sink
acknowledgements, atomic metadata checkpoints and a three-capture admission
limit. Fifteen reader tests and15 simulated coordinator tests pass. Both25/24
frame delivery modes matched independent byte reads for all three original
reference captures, with their four tensor hashes intact. No GPU request,
playback, generation-speed result or footage deletion occurred. Transport,
cleanup, native continuation and playback remain pending; host FAULT persists.
[Bounded state and delivery evidence](experiments/ltx25-b70/notes/continuation-stream-state-01.md).

The inactive continuation verifier now uses exact integer bit intersections
for F32 finite checks. All65 affected bit/reader/provider/state checks pass;
paired scalar/candidate verification of the three original captures produced
identical receipts and all four original hashes. Provisional faulted-host CPU
medians were304.38ms scalar versus44.04ms candidate for full capture verification.
This is verification overhead only, not a generation-speed improvement or
promotion. No GPU request, restart or host-setting change occurred.
[Exact candidate, patch and timing limits](experiments/ltx25-b70/notes/finite-f32-bit-intersections-01.md).

An inactive streaming comparison client now checks complete F32 archive bytes
without importing Torch or loading entire tensors. Fifteen contract tests and
seven arithmetic tests pass. Saved baseline02 and resident-split03 match all
four baseline01 outputs; a different-prompt marble capture correctly fails.
The old comparer and frozen callers remain unchanged. Historical-evidence
reports cannot satisfy a live gate; no generation-speed gain or runtime
qualification is claimed. Host FAULT remains present.
[Candidate and exact evidence](experiments/ltx25-b70/notes/streaming-comparison-01.md).

An inactive one-line decoder candidate removes GPU scalar readbacks when the
attention-window maximum is already available as a Python integer. All17,728
source/integer extent cases pass and the complete AST differs only in that
extent expression. No native mask, attention, full-clip parity or speed result
exists yet. Installed runtime source remains unchanged; FAULT still prevents
native tests. [Patch and qualification scope](experiments/ltx25-b70/notes/na-mask-extent-01.md).
The separate small native mask/attention gate is prepared; its check-only run
correctly halted before importing Torch under the existing fault.
[Gate and refusal evidence](experiments/ltx25-b70/notes/na-mask-extent-native-gate.md).

**Historical startup, superseded by the fault above: native compiler comparison.**
PID95931 serves `http://127.0.0.1:8188` from prepared-encoder-compiler-02,
manifest `f1fc467a4620caabac9065e72fb7fd1628db437d1c977c86237bb0378ef8f952`.
Endpoint identity and strict after-import determinism match the startup receipt.
The bounded nine-request compiler-screen-01 is active; inspect its progress
under `/mnt/fast-ai/bench-results/ltx25-baseline-20260913/compiler-screen-01`
before any new GPU request. It checks one native block24 with the original
control encoder, both native stage outputs against eager/repeat calculations,
and every completed clip against all four original raw references. No compiled
speed or correctness result is claimed before those gates finish.
PID78769 exited cleanly after one controlled SIGINT to load this new application
code; the computer was not rebooted. No fault latch at startup. This supersedes
the idle PID78769 statements below. [Preregistration](experiments/ltx25-b70/data/compiler-screen-01-prereg.json)
and [native gate](experiments/ltx25-b70/notes/ltx-block-compile-node-ready.md).

**Four-B70 host, September14: encoder comparison complete; compiler integration next.**
All25 encoder-screen-02 clips passed strict four-output original-reference parity
and all four unload transitions passed. No convincing speed winner: warm medians
6.364s control-before,6.377s crop,6.430s small-state,6.441s combined,6.643s
control-after. Small-state residency fixes the observed loaded-byte accounting
drift, but has no demonstrated full-clip speed gain. PID78769 is idle on control,
generation5, at `http://127.0.0.1:8188`; no fault latch. Preserve this process
while preparing the compiler successor; no competing GPU requests. Next is a
bounded one-native-block exact compilation gate, then full-clip verification if
it passes. [Results](experiments/ltx25-b70/notes/encoder-screen-02-results.md).
This supersedes the active-screen statements immediately below.

**Four-B70 host, September14: strict startup fixed; encoder comparison started.**
PID78769 serves `http://127.0.0.1:8188` from prepared-encoder-03 / encoder-server-02.
Startup identity matches the endpoint and the after-import receipt verifies
strict determinism (enabled, warning-only off). Encoder-screen-02 is running;
reuse this process and inspect its progress before any new GPU request.
The first screen on PID75850 stopped after one completed control clip: all four
outputs matched baseline bytes, but strict-mode qualification failed because
Comfy import reset warning-only mode. The corrected launcher restores the
original import order;11 CPU regression checks passed. Only the launcher differs
between the immutable packets. No quality gate was waived. Evidence and exact
scope: [startup correction](experiments/ltx25-b70/notes/encoder-strict-startup-fix.md).
User clarified that routine application reloads should not cause approval
pauses or stop optimization; the host-reboot/power/restart-chain constraints
remain. This supersedes all earlier pending-approval and process statements below.

**Four-B70 host, September14: authorized LTX replacement completed.**
User approved the restart and clarified that optimization must continue without
an unnecessary application-restart approval pause. Original PID24848
stopped cleanly after one SIGINT. Replacement PID75850 is ready at
`http://127.0.0.1:8188`; endpoint identity matches the encoder-server-01 receipt,
the queue is empty and the fault latch is absent. Host LAN IP is10.0.0.65, but
the application listens on localhost only. The immutable prepared-encoder-02
packet is active. The preregistered encoder-screen-01 comparison is now running
on this process; inspect its live progress before any new GPU work. An initial launcher
preflight exited before Torch import because the old TCP socket was in TIME-WAIT;
after its observed expiry, the bind check passed and the replacement started.
Evidence: `/mnt/fast-ai/bench-results/ltx25-baseline-20260913/encoder-migration-01.json`
and `encoder-server-01/`. This supersedes pending-replacement statements below.

**Four-B70 host, compiler preparation: routed CPU gates pass; inactive.**
The native block adapter passed its initial 29 checks; the additive ownership
guard passed 51 checks with the compiler callback itself in the full options
registry. Both stage token counts and two seeds matched video/audio outputs
exactly and repeated identically, with two compiled graphs and no graph breaks.
These are tiny CPU fixtures, not native-weight GPU or speed results. The
[checkpoint header census](experiments/ltx25-b70/notes/native-block-header-census.md)
records native block dimensions and mixed stored dtypes without loading weights.
A subsequent [executing-patcher lifecycle gate](experiments/ltx25-b70/notes/ltx-block-compile-pre-run-lifecycle.md)
passed 25 CPU checks for live owner anchoring, late changes, clone behavior and
cleanup. A subsequent [real bound CPU capture](experiments/ltx25-b70/notes/ltx-bound-lifecycle-capture-cpu.md)
passed one 64-video/26-audio-token case with the lifecycle callback present:
both outputs exact and repeatable, one compiled graph and zero graph breaks.
Native GPU correctness/overhead and broader cases remain unqualified. The
cancelled optional CPU compilation attempt is preserved separately. The
[continuation audit](experiments/ltx25-b70/notes/continuation-source-boundary.md)
also records two-stage mask loss and unresolved audio timing before streaming.
PID24848 remains idle, fault-free and unchanged; the encoder v2 maintenance
approval is still pending after multiple goal turns. The prepared launcher again
passed its read-only check. Further measured speed work is waiting on that
decision; do not infer approval from automatic continuation. Compiler work is
separate from that immutable packet.
See the [route gate](experiments/ltx25-b70/notes/ltx-block-compile-route-cpu.md).

**Four-B70 host, encoder runtime v2: GPU screen prepared, maintenance pending.**
Startup, actual placement/unload diagnostics and the 25-request bounded client
are complete. Eight startup, ten diagnostics and eight client CPU tests pass;
the copied launcher's read-only check passed and all 1,214 packet files still
match their hashes. No new GPU request, runtime change or server replacement
occurred. PID24848 remains running and idle, with its original identity and no
fault latch. The new `encoder-server-01` directory does not exist. One deliberate
graceful replacement is needed to load v2; do not start a second process beside
the current server or create a retry/restart chain. The next action is a
maintenance decision for the [concrete launch and screen](experiments/ltx25-b70/notes/encoder-runtime-v2-ready.md).
The source snapshot is `prepared-encoder-02`, manifest SHA256
`920d0e35774f298c9b11f80b3dd5e3708d0541f914e4c1857e96493bfd7282a8`.

**Four-B70 host, encoder integration follow-up: inactive source packet built.**
The four encoder variants now pass 17 CPU lifecycle tests and four integration
tests through tiny real Gemma4/CLIP/LTX projection paths. Review fixed a shared
clone policy bypass; integration also fixed rejection of CLIP's stock compute
dtype setting. Original patches and earlier receipts remain preserved. A new
non-Git source snapshot under `prepared-encoder-01` inventories 1,205 files and
keeps all baseline graph inputs except explicit encoder options. Every staged
file hash and the unchanged loaded-source hashes passed verification. No GPU
job, server restart or runtime edit occurred. PID24848 remains the loaded idle
service; no new speed claim. Next: finish startup identity/client and actual
placement diagnostics before any maintenance decision or the bounded 25-request
comparison. See the [source packet and remaining gates](experiments/ltx25-b70/notes/encoder-runtime-packet.md).

**2026-09-14 UTC, two-B70 host: bounded worker comparison finished; FP8 ready.**
Readable tool output passed stable acceptance and independent agent review on all
five original issues, plus one confirmation each of the formerly failed hardware
and zero-cost tasks. Both new held-out issues failed. The readable profile remains
opt-in/experimental; original defaults and model performance qualification stay
unchanged. All generated patches remain unmerged, with human review pending.
[Results and evidence](experiments/local-coding-worker/overnight-2026-09-14-results.md).
The original 3/5 trial and first failed profile screen remain frozen separately.

One unchanged qualified FP8 TP2/MTP1 server remains healthy at `127.0.0.1:18124`,
33,024 total capacity / 4,096 scheduling batch / one active sequence. Exact helper
state/logs: `/mnt/fast-ai/bench-results/local-worker-20260914/server/`.
All nine corrected-campaign CPU containers stopped before patch export. No model
patch was applied to either source checkout. No server restart, inference
optimization, host-setting change, local GPU fault or cloud fallback occurred.
The eight-hour authorization was an upper bound; this bounded model campaign is
closed. No queued model/GPU tasks remain in this lane.
Use the existing endpoint for subsequent worker jobs; do not launch a competing
GPU lane. [Worker commands and API capacity](worker/README.md).
Preserve independent four-card LTX work and its fault-halt state above.

**Four-B70 host, post-stability LTX diagnostics: next runtime candidates prepared.**
One 15-second nonblocking py-spy attachment and one unchanged clip completed on
PID24848; all four output tensors matched baseline-01. The trace points to
repeated CPU copies of tiny encoder RMSNorm weights and layer scalars totaling
only 1.47 MiB. The opt-in small-state residency patch passed 12 real Gemma4 CPU
lifecycle tests; it includes a scoped accounting correction and must not be
stacked with the separate generic accounting patch. It is inactive.
Stock whole-model compilation was rejected by source audit. Default CPU
Inductor changed BF16 values despite deterministic repeats; preserving rounding
passed 6/6 toy cases. An actual native LTXAV block CPU fixture then passed both
stage token counts: two compiled graphs, zero graph breaks, both outputs exact.
These are CPU preparation gates, not GPU speed/quality results. No server restart
or runtime patch occurred; the server is idle and fault-free. Diagnostic media
was pruned after exact verification. Next work is a bounded runtime integration
packet for small-state residency/cropping and one-block compilation; do not use
the unsafe stock compile node or inject code into the live process.
See [profile result](experiments/ltx25-b70/notes/stack-profile-01-results.md),
[small-state candidate](experiments/ltx25-b70/notes/encoder-small-state-audit.md),
and [compiler block gate](experiments/ltx25-b70/notes/ltx-block-compile-cpu.md).

**2026-09-14 UTC, two-B70 host: official FP8 quickstart replay complete.**
The public-source helper ran one R304 TP2/MTP1 server at 33,024 capacity /
4,096 batch / one sequence. Strict 12/12 complete outputs matched the qualified
reference; all six practical requests passed with exact repeated outputs and
zero cached tokens. Single-replay decode 54.201 tok/s; no optimization promoted.
The documented exact-owned stop passed, all owned processes/listeners are gone,
and both GPUs/XCCL plus the full journal postflight passed. State and logs are
under `/mnt/fast-ai/bench-results/qwen-fp8-flagship-20260914`; the hash-bound
[results packet](experiments/qwen38-27b-b70/notes/2026-09-14-fp8-flagship-results.md)
records public commit, image/model checks and remaining installation limits.
No restart chain or power/memory-setting changes; four-card LTX work preserved.

**Four-B70 host, September13, LTX campaign started toward the revised goal.**
User requires one second of new video in **under one second**, at24fps with no
quality/losslessness sacrifice. Final output floor is256x256; <=3s is only an
intermediate marker. Minimal rolling review footage is authorized, including
deleting older verified campaign outputs while preserving compact hashes and
receipts. Existing model/reference artifacts stay protected. The first bounded
work completed [30 sequential requests over10 fixtures](experiments/ltx25-b70/notes/stability-01-results.md)
on the existing PID24848 endpoint: all exact repeats passed, median preview6.515s,
p956.680s, no faults/OOM. Physical memory stayed within observed bounds while
the encoder's reported offload grew690→2718MiB; source/CPU work supports an
accounting defect. Longer soaks remain deferred. Verified pruning reclaimed607MB,
retaining three campaign previews totaling170KB plus compact receipts. Two
inactive candidate patches target accounting and unnecessary hidden-state CPU
copies; no runtime change or further restart occurred. The server is idle.
See the updated [plan](experiments/ltx25-b70/PLAN.md).


**2026-09-13 EDT, two-B70 host: final FP8 prefill pass complete and stopped.**
Official 27B FP8, R304 TP2/MTP1, measured 512/2048 inputs at 2,857/3,679 input
tokens/s with 4096 capacity/batch. All 36 measured outputs repeated exactly;
strict 12/12 original-reference parity, decode −0.13%. Profiling found FP8 matrix
operations dominant and no justified quick candidate; defaults retained and
prefill campaign closed. Owned server stopped, both GPUs/XCCL and journal
postflights passed. [Results](experiments/qwen38-27b-b70/notes/2026-09-14-fp8-prefill-focus-results.md).
Raw root `/mnt/fast-ai/bench-results/qwen-fp8-prefill-focus-20260914`.
No restart chain or power/memory-setting changes; four-card LTX work preserved.

**Four-B70 host, 2026-09-13 22:23 EDT: exact-output LTX speed result.**
User prioritizes first usable clip within a few seconds, while retaining exact
baseline outputs. Baseline PID11499 exited cleanly after one planned SIGINT;
new ComfyUI PID24848 owns `127.0.0.1:8188`, with the same exclusive locks,
strict deterministic mode and cache-none computation. All four small startup
preflights passed, with no device fault. Resident model components and exact
layer placement are startup extensions; generated outputs and prompt encodings
are always recomputed. **Validated warm 256x256/25-frame clips take 6.44–7.10 s
to playable preview**, using all four B70s: transformer split across XPU0/1,
encoder XPU2 and VAEs XPU3. Three boat repeats and marble/bird reference scenes
match all four original tensors bitwise. Exact float media export also passed.
Matched warm boat client medians improved 7.85×; first split initialization took
81.21 s to preview. BasicGuider was exact but neutral and is not selected.
The one-second clip is not yet continuous real time; prolonged operation remains
untested. The transformer stays resident; the encoder still partially offloads.
Server is idle with split components retained. Further variants
use this same process; no restart chains/power/swap/cache-drop/driver changes.
See [speed campaign handoff](experiments/ltx25-b70/SPEED-HANDOFF.md).
The [LTX north star and plan](experiments/ltx25-b70/PLAN.md) now define the next
milestones: bounded stability validation, exact clips under1s, coherent streaming,
then sustained generation above24fps. The later start instruction is recorded above.
Original baseline remains frozen; new process identity is under the original
evidence root's `speed-server/`. Use `profile-clip.py --server-run` pointing there.

**2026-09-13 21:47 EDT, two-B70 host: bounded prefill follow-up complete.**
4B TP2, 9B TP2 and 27B INT4 TP1 measured at 256/512 input tokens, one user,
cache zero; all 108 measured requests repeat exactly and all three strict suites
match their original qualified outputs 12/12. One 4B TP2 profiler trace is
retained; no new runtime candidate or decode record promoted. All three owned
servers are stopped, both GPUs/XCCL and journal postflights passed. [Results](experiments/qwen38-27b-b70/notes/2026-09-14-prefill-followup-results.md),
raw evidence `/mnt/fast-ai/bench-results/qwen-prefill-followup-20260914`.
No restart chain or power/memory-setting changes; four-card LTX work preserved.

**Four-B70 host, 2026-09-13 20:42 EDT: LTX baseline bring-up.** User authorized
a very short native-precision clip and deterministic repeat checks. One local
ComfyUI server (historical PID 11499, `127.0.0.1:8188`) ran with exclusive device
locks; all four cards passed its small copy/compute preflight. **Baseline complete,
original server since replaced as described above:** three fixed-seed 256x256/25-frame generations are bitwise identical
across images, video/audio latents and waveform, with strict determinism and zero
cached nodes. First/repeat server times were 97.590/54.009/52.774 seconds. Exact
float video/audio export passed independent decode round-trip verification.
No GPU fault, OOM or tiled-VAE fallback occurred. This establishes one-prompt,
same-process repeatability, not cross-process or other-model parity. The RAID transformer and encoder failed fresh
SHA-256 checks; rejected bytes and failed receipts are preserved. The transformer
was repaired by replacing 79 damaged bytes, and the encoder by replacing 112.
All five final component files passed publisher/direct-I/O hashes; the generation
gate is now open. Rejected files and partial downloads remain preserved. Preserve the server, source and environment at
`/home/steve/src/ComfyUI-ltx25-baseline` and
`/home/steve/.venvs/ltx25-baseline`; no restart chain or power-setting changes.
See [verified baseline and reuse instructions](experiments/ltx25-b70/README.md). Evidence root:
`/mnt/fast-ai/bench-results/ltx25-baseline-20260913`.

**Four-B70 host, 2026-09-13 after 20:17 EDT reboot: LTX 2.5 pivot.** User
requested parking the completed Flash-Next campaign, archiving its checkpoint
to USB, then focusing on LTX 2.5. Recent LTX, YuE2 and MiniCPM downloads were
located on the RAID, now mounted read-only. Corsair's read-only mount failed
with an NTFS chkdsk recommendation; Qwen archive verification/reclaim is
pending, and the internal checkpoint remains intact. No GPU workload was
launched. The active task is storage/download review and LTX bring-up planning;
prior queued four-card launch instructions are superseded. See the
[pivot and storage review](notes/2026-09-13-ltx25-focus-and-storage-review.md).

**2026-09-13 20:30 EDT, two-B70 host: short-prefill campaign complete.**
Measured 4B/9B W4A16 and 27B INT4/FP8 at c1 with 128/256/512-token inputs.
All 324 measured requests were cache-zero and output-exact across off/on/off;
each model passed 12/12 full-suite candidate/control and original-reference
parity. A direct-output allocation screen showed +3.0% on 4B, +2.1% on 9B,
and neutral 27B results, with strict decode differences below 0.3%. Existing
serving defaults remain unchanged; this is a single-process screen, not a new
promotion. See the [results and replay](experiments/qwen38-27b-b70/notes/2026-09-13-short-prefill-results.md)
and [complete summary](experiments/qwen38-27b-b70/data/2026-09-13-short-prefill/summary.json).
All four model stages are stopped, optimization flags removed, both GPUs/XCCL
and final journal postflights passed. No power, swap, cache-drop, driver or
reboot changes. Raw evidence remains at
`/mnt/fast-ai/bench-results/qwen-short-prefill-20260913`.

**2026-09-13 19:32 EDT, two-B70 host: R308 work complete.** The optional
single-request repair for Qwen3.5 4B and 9B is published, anonymously pullable,
and verified on the live site. Both models passed 60/60 oracle checks,
52/52 boundary checks on each of two fresh speculative servers, and all four
strict comparisons 12/12. Public-parent reconstruction matched all 17 runtime
hashes. Source/evidence integrity, guide tests, recipe CI and Pages deployment
passed. See the [qualification note](experiments/qwen35-4b-b70/notes/2026-09-13-r308-qualified-single-request.md)
and [completion receipt](experiments/qwen35-4b-b70/data/2026-09-13-r308-single-request-qualification/evidence/publication/completion.json).
All owned model and preview servers are stopped; both GPUs and XCCL passed
final health checks. No power, swap, driver, or reboot changes were made.
Scope is TP1, fixed depth 3, one active request: boundary capacity 256 and strict
capacity 1024. Clean-host certification, concurrent speculation and a new 32K
profile remain outside this qualification. R307 failures and diagnostic roots
remain preserved in the linked evidence; existing defaults retain their
original identities.

**Four-B70 Flash-Next closeout, 2026-09-13:** user requested finishing Fable's
optimization campaign and publishing existing results. A340-A394 is closed:
46.854250 tok/s approved realistic-suite record, +23.87% vs previous line;
A382/A394 repeated 32K depth median 44.052 tok/s with equal output hashes.
[Closeout](results/qwen38-flash-next-fp8-b70/CLOSEOUT-20260913.md) owns the wins,
nonpromoted trials and remaining certification limits. No server or optimization
chain is running. The separate disabled single-session draft is set aside.
User constraints remain: no AI power-setting changes and no repeated restarts.

**Four-B70 host, 2026-09-13 20:10 UTC recovery:** A394 depth repeats pass, but
teardown rc is 143 and another host interruption followed. No workload running;
hold Flash-Next launches pending teardown/host-restoration review. Git damage
restored from the already-pushed A394 commit; evidence USB mounted read-only,
RAID unmounted. See [recovery evidence](notes/2026-09-13-a394-freeze-recovery.md).
Follow-up: full Git fsck passes, NVMe reports zero media/errors; offline audit
found stop-protocol mismatch, stale health receipts and a nested-cleanup race.
See [teardown audit and next gates](notes/2026-09-13-a394-teardown-audit.md).

**2026-09-13 (EDT):** the whole INT4/W4A16 runtime is rebased onto stock vLLM XPU
v0.29.0 as **R304** (`ghcr.io/steveseguin/vllm-openai-xpu-qwen38-int4@sha256:7cd7bb16`,
pushed and anonymously pullable): the R294b overlays ported as net diffs, the kernel
library rebuilt from public sources (vllm-xpu-kernels 0.1.14.1, which carries upstream
GDN fix #544, plus the lab's oneDNN r137a/r137b/r221), and three open upstream vLLM
fixes applied verbatim (#53059 alias guard, #51565 GDN first-chunk, #53542 active width).
It fixes two failures that were live on R294b: every one-token prompt and every
(1+K)-token prompt at depth K degenerated into single-character walls (30/30). Strict
gates 12/12 at published speed on the 4B, 9B and FP8-27B lanes under the recipe contract
(`verify-image-contract.sh` v0290 digest set); the INT4-27B pair is running. The 4B and
9B and both 27B recipes, packages and compose packets now point at R304 (all gates 12/12, long context 18/18,
high concurrency reproduced; kernel library reproduced bit-identically from a clean clone). The 9B scheduled-draft
profile runs on R306 (`@sha256:f124c6fb`, R304 plus its overlays and a contiguous-staging fix for upstream PR #53542). Serve with `VLLM_USE_V2_MODEL_RUNNER=0` (the launchers pin it; v0.29.0
defaults XPU to the V2 runner, which has no draft INT4 head). Details:
`experiments/qwen38-27b-b70/notes/2026-09-12-rebase-onto-vllm-v0290.md`.

**2026-09-11 (EDT):** the Qwen3.5 4B/9B and Qwen3.8 27B INT4 lanes finished the
class-consistent FP16 linear work (R290-R293 overlays, `VLLM_XPU_FP16_LINEAR_CLASSPAD`):
the R224 32-row pieces re-read the vocabulary projection once per 32 rows, 25-56% of
throughput on the 4B/9B and 3-8% on the 27B, removed losslessly. 27B package staged
on R293 (`packages/qwen38-27b-int4-fixed-k-tp2-b70`, rows R295-R298); the R293
image is built locally (`sha256:40d46730`) and awaits the GHCR push
(`repro/qwen38-27b-autoround-int4-b70/scripts/publish-r293-image-ghcr.sh`). No
containers running after 19:03 EDT; both cards passed postflight.

Host: `steve-TURIND8-2L2T`, **two B70s**. At the verification time above,
no Docker containers are running; all PR45 review servers were stopped.
Both GPUs and XCCL passed final postflight. Recheck actual process and endpoint
state before operational changes.

Target-oracle follow-up completed: both fresh compiled target-only strict tests
passed, all five comparisons were 12/12 exact, and 96 additional probes passed.
All owned containers stopped; localhost 18124 is closed and postflight passed. See
[preregistration](community/dominick253-qwen38-27b-fp8-uniform-decode-alias/validation/target-oracle-20260909.md).
The six-hour soak has not been started.

The active task is correctness and reproducibility review. An isolated
Qwen3.8 27B official-FP8 R50 baseline/candidate comparison completed for PR #45:
normal-suite parity passed, tiny-prompt screens failed, candidate not promoted.
The initial review model containers were stopped; both GPUs and XCCL passed
postflight. Follow-up isolated the fresh one-token GDN routing defect: the
phase-guard candidate passed 120/120 probes, two fresh compiled MTP full suites,
12/12 baseline/fresh-repeat parity and pre/post workload screens. The campaign
is complete and stopped, not a permanent service. See the
[preregistered follow-up](community/dominick253-qwen38-27b-fp8-uniform-decode-alias/validation/priority-followup-plan.md).
Read the
[maintainer validation record](community/dominick253-qwen38-27b-fp8-uniform-decode-alias/validation/README.md)
for the candidate identity, completed tests and outstanding gates.

The previous Gemma listener and Qwen3.5 active-lane claims are superseded by
this observation. Preserve the existing Qwen3.5 work listed below. Run one
GPU lane at a time; verify endpoint and health independently of an image tag.

## Working Recipes And Candidates

- **Qwen3.8 27B FP8 TP2:** the [reproduction packet](repro/qwen38-27b-fp8-vllm-tp2-asrock-b70/README.md)
  owns the lab-qualified R187 configuration, exact-output concurrency limits
  and historical results. Its certification remains `candidate-portable-repro`;
  it is not a verified beginner setup. Consult the
  [multi-host handoff](experiments/qwen38-27b-b70/MULTI-HOST-HANDOFF.md) and
  [do-not-repeat index](experiments/qwen38-27b-b70/DO-NOT-REPEAT.md) before work.
- **PR #45 classifier fix:** separate R50 candidate, not promoted into the
  above recipe. Actual-source CPU checks pass against both source copies.
  Normal GPU suite passed 12/12 exact baseline/candidate parity, but both
  failed tiny-prefill screens; compilation-disabled candidate also failed.
  Sustained mixed-session validation remains unperformed; not a verified fix.
  A separate maintainer GDN phase guard fixes the local one-token symptom in
  the [bounded follow-up](community/dominick253-qwen38-27b-fp8-uniform-decode-alias/validation/priority-20260909/README.md),
  but is not promoted as the contributor's incident resolution.
- **Gemma 4 26B Q8:** [result/handoff](results/gemma4-26b-a4b-q8-b70/HANDOFF.md)
  and [standalone recipe](repro/gemma4-26b-a4b-q8-b70-125tps-20260701/README.md)
  preserve the measured setup. Their existence does not mean Gemma is loaded.
- Other lane status belongs in the [model effort index](docs/model-effort-index.md)
  and [reproducibility map](docs/current-reproducibility-map.md).
  The [scoreboard](results/scoreboard.md) is historical measurement evidence,
  not service state.

## Known Issues And Next Actions

1. Before promoting the GDN local fix, run the contributor's actual mixed-session
   soak. The matched-image MTP0/MTP1 strict-oracle matrix now passes; the
   multi-hour incident remains unverified. PR #45 is merged as a community
   contribution, not a production promotion.
2. Reproduce one selected recipe end to end: pinned inputs, build, launch,
   quality gate and clean teardown. Correct defects found along that route
   before additional speed tuning.
3. Audit recent changes by affected runtime, shared harness and published
   recipe. The [September 8 review](notes/2026-09-08-targeted-correctness-cleanup.md)
   was bounded: syntax checks are not execution coverage, and commit author
   labels do not establish which model wrote a change.
4. Three promoted Flash-Next replay paths now use exact frozen verifier
   snapshots; four replay clients now stop their servers on failure. Bundle
   chains were restored and verified from the public base. See the
   [audit record](notes/2026-09-09-replay-and-validator-audit.md).
   The broader 229 historical experimental hash mismatches were not blindly
   repinned. Four-card runtime replay remains untested on this two-card host.
5. Keep ML Bottleneck automatic refresh paused. Numerical fixture tests are
   now separated from refreshed-data checks. The ingestion parser correction
   passes 94 tests and resolves the 3060 interpretation in a migration test.
   Publication still blocks on the 4070, nine ambiguous measurements and
   calibration thresholds. Published evidence remains unchanged. Details are in
   that repository's `docs/refresh-review-2026-09-08.md`.

## Other Host: Four-Card Work

MiniMax M2.7 INT4 and Flash-Next TP4 belong to the **four-B70 host**, not
this two-card machine. The [MiniMax post-reboot note](notes/NEXT-minimax-after-reboot.md)
is that host's resume packet; its remount, driver and launch instructions
must not be applied here. It records an unresolved bring-up validation after
a driver wedge, not a successful serving result. On the owning host, avoid
polling `xpu-smi` during initialization, verify the four devices and use its
bounded health checks before continuing.

Flash-Next history and accepted identities live in its
[handoff](results/qwen38-flash-next-fp8-b70/HANDOFF.md) and
[result packet](results/qwen38-flash-next-fp8-b70/README.md).
Historical reboot notices in the archive do not describe this boot.

### Four-B70 host, 2026-09-11: Qwen3.5-9B W4A16 lane closed, Flash-Next next

The Qwen3.5-9B W4A16 one-B70 lane on `steve-b70s` is closed and published: the
static depth-3 headline (113.27 tok/s) stands, and a second operating
configuration - one server for every batch size, draft depth scheduled by
batch size on three pure-Python overlays over R276 - is promoted in the
[guide](repro/qwen35-9b-w4a16-b70/README.md#one-server-for-every-batch-size-campaigns-cudynm1--cudynm1r-2026-09-11),
[package](packages/qwen35-9b-w4a16-b70/package.json) and
[performance index](results/scoreboard.md): 110.7 tok/s at one user, 1,184 at
64 users, exact through 32 users, 18/18 exact 2K-32K. The env-knob ladder for
single-user decode on this lane is exhausted (defaults optimal on every axis);
what remains is kernel work (fused INT4 draft head) recorded in the
[campaign note](experiments/qwen35-9b-b70/notes/2026-09-10-one-server-for-every-batch-size.md).
No lane container is running. The next active lane on this host is Qwen3.8
Flash-Next (its [handoff](results/qwen38-flash-next-fp8-b70/HANDOFF.md)).

### Four-B70 host, 2026-09-13: Flash-Next lossless MTP1 at 46.85 tok/s (record approved)

The Flash-Next lane's step-timing decomposition (A340-A358) put 8.7 ms of the 42.7 ms
two-row verify step in vLLM's Python serial GDN path and showed the cost is in neither its
kernels nor its glue. The kernel extension's own exact serial mode, gated to four verifier rows
by the served build, accepts two when `_xpu_C.abi3.so` is rebuilt from the lane's kernel head
(`bbae3c5` over `e421889`, [series](patches/qwen38-flash-next-fp8-b70/xpu-kernels-gdn-exact-serial-bbae3c5/README.md)).
With that mode selected the verify step is 33.7 ms and every output pin holds (kernel probe
bit-identical; exact-2K `afffd211…`, exact-4K `1d833e5f…` on four servers; 12/12 suite outputs
equal to the 37.83 record). Certified on three servers (A364, A365, A366: short 53.4, exact-2K
48.2, exact-4K 48.5 tok/s) and recorded on a fourth (A367: **46.854250 tok/s** class-balanced,
LocalMaxxing [`cmtzask41000nlq011f16bpbc`](https://www.localmaxxing.com/runs/cmtzask41000nlq011f16bpbc)
approved). Guide [`repro/qwen38-flash-next-fp8-tp4-mtp1-exactgdn-b70-47tps-20260913/`](repro/qwen38-flash-next-fp8-tp4-mtp1-exactgdn-b70-47tps-20260913/README.md),
package `packages/qwen38-flash-next-fp8-tp4-mtp1-exactgdn-b70-47tps-20260913/`, narrative in the
[result packet](results/qwen38-flash-next-fp8-b70/README.md). Host notes: two silent freezes hit
launches started 60-90 s after the previous server's teardown (swap toggle); leave five minutes
between a stop and the next launch. Unused models (laguna-s-2.1, muse-glimmer, the 9B pair) were
moved to `/mnt/raid-models` with symlinks left in place; root NVMe at 301 GB free. No lane
server is running.

## Protected Work And Artifacts

Preserve these paths and inspect their status before any build, cleanup, or
service change:

- `/home/steve/src/llama.cpp-muse-100`: preserved source/build used by the inactive Muse fleet;
- `/mnt/fast-ai/src/llama.cpp-q38-q4k-glu-tp2`: accepted Qwen3.8 Q4_K_M source at
  `a4349bcee`; preserve its intentional three-file uncommitted fusion delta;
- `/mnt/fast-ai/src/llama.cpp-q38-q4k-glu-tp2/build-sycl-aot-bmg-g31-oneapi-2026.1.1`:
  accepted oneAPI 2026.1.1 BMG-G31 AOT build;
- `/mnt/fast-ai/llm-models/qwen3.8-27b-gguf/`: accepted Qwen3.8 GGUF targets and MTP sidecars;
- `/mnt/fast-ai/llm-models/qwen3.8-27b-fp8/`: official FP8 artifact retained for the separate vLLM lane;
- `/mnt/fast-ai/bench-results/qwen38-official-fp8-vllm-xpu-20260816/`:
  official FP8 eager/graph/P2P controls, final quality gate, cache-zero result,
  runtime capture, and post-run health evidence;
- `/mnt/fast-ai/llm-models/qwen3.8-27b-gptq-int4-mtp/`: hash-verified
  SergioB GPTQ INT4 target with 15 BF16 MTP tensors; community replay lane;
- `/mnt/fast-ai/bench-results/qwen38-q4km-asrock-b70-20260815-pass2/`:
  accepted Q4_K fusion A/B and cold-suite evidence;
- `/mnt/fast-ai/bench-results/qwen38-gptq-int4-asrock-b70-20260816/`:
  SergioB target-only eager/graph validation, failed conservative-U graph
  attempt, logs, inspect records, prompts, and raw SSE evidence;
- `/mnt/fast-ai/bench-results/qwen38-gptq-quality-20260816/`: native/FP8 KV,
  semantic quality, MTP runtime-dtype, Q8/Q4 controls, and reset-window evidence;
- `/mnt/fast-ai/src/llama.cpp-q8-tp2-directq8-isolated`: current accepted Qwen TP2 source;
- `/mnt/fast-ai/src/llama.cpp-q38-tp2-distributed-greedy-directq8`: closed
  exact distributed-argmax candidate; preserve for mechanism reuse only;
- `/mnt/fast-ai/bench-results/qwen38-q8-asrock-b70-20260816-distributed-greedy/`:
  position-balanced reasoning-off controls/candidates and exact output oracle;
- `/mnt/fast-ai/src/llama.cpp-mndodd-intel-sycl`: prior accepted Qwen TP2 source; preserve as control;
- `/mnt/fast-ai/llm-models/qwen3.6-27b-q8_0-gguf/`: accepted Qwen model;
- `/mnt/fast-ai/bench-results/qwen36-q8-asrock-b70-20260813-tp2-fusion/`:
  promoted Qwen evidence and bounded negatives;
- `/mnt/fast-ai/bench-results/qwen36-q8-asrock-b70-20260814-40tps/`:
  Qwen pass-1/pass-2 evidence and current clean result;
- `experiments/qwen27_graphsafe_flash_attention/`: graph-safe INT4 source and
  generated research state;
- `experiments/qwen36-27b-autoround-int4-b70/`: INT4/MTP research packet and
  diagnostic artifacts.

Large ignored Qwen artifacts may be archived only after a complete inventory,
hash verification, and a recorded restore path. Never use broad `git clean` or
delete tracked experiment material to make the tree look tidy.

## Additional Preserved Work And Operational Guards

Pre-existing dirty Qwen3.5 work at review start; inspect and preserve:

- `experiments/qwen35-9b-b70/probes/drift-reproduction.py`
- `experiments/qwen35-9b-b70/scripts/analyze-admission-composition.py`
- `experiments/qwen35-9b-b70/scripts/run-20260908-drift-reproduction.sh`

The prior ledger also protects the dirty Flash-Next source tree; do not
reuse or modify it for the Qwen3.8 R50 review. Root-NVMe/BIOS work remains
paused. Retain the existing frozen-runner guards: no bulk reads/scans of
`/mnt/fast-ai` or `/mnt/usb-models`; do not start
`generate-q38-root-nvme-link-clearance-v1.py` or any `w13`/`hc` runner.
Do not run process-search commands containing
`w13-m1-xpu-graph-gate.py` or the A2 result path: frozen health checks can
mistake the search itself for a surviving runner. See the
[archived ownership notice](CURRENT-history-20260909.md#immediate-manager-actions)
for the original guard and its recorded false positives.

Do not place new model downloads on NVMe based on an old free-space report.
Verify current capacity, mount identity and lane ownership first. Follow
[AGENTS.md](AGENTS.md) for main-only Git, secrets, runtime isolation,
quality gates and exact publication requirements.
**Four-B70 host, September 19 22:05 UTC: tenth silent freeze at 21:20 UTC during server 82's model construction (no lockup line, no pstore, no BMC event); host reset 21:25; packet 82 relaunched as server 82b with runner 82b (bases 90900-95200).**
The runtime C2 disable recorded on 09-19 18:00 was never actually
installed (no unit exists; `cpuidle/state2/disable` is 0 on the last two
boots), so the idle-state hypothesis is still untested; the user holds the
`! sudo` line and the BIOS setting. [Evidence and correction](experiments/ltx25-b70/notes/2026-09-19-freeze-evidence-soft-lockup.md).

**Four-B70 host, September 19 22:20 UTC: server 82b stopped. The sharded arm ran 30 prompts, 29 exact and one finite mismatch (bird, prompt 05, 100% of elements differ, equal to no fixture); the NaN of servers 79b-81 is gone, so the stream fix held. Steady 1.622 s/clip (p95 1.955), no gain over packet 74's 1.607 because the sampler stage (3.26 s mean with two clips in flight) is now the pacing stage. Stop reason: the samp2 control arm cannot follow a sharded arm by design (`only graph-shard arms may follow`) and its refusal latched the text encoder node (`Previous text encoder graph failure`), so no further prompts can run on this server; runner 82's arm order carried that defect from runners 78-79. Residual race: `_POOLS` in ltx_graph_text_encoder.py keys the graph memory pool by device only, so both worker threads' 48 layer graphs replay out of one pool per card and their transients alias when the threads dispatch concurrently (the mismatch fell in the fill phase, where both threads run back to back; later bird clips were exact). Packet 83: one pool per (device, worker thread); runner 83 drops the control arm.**

**Four-B70 host, September 19 22:40 UTC: eleventh freeze at 22:20 UTC, 28 s into packet 83's sharded arm (fill phase). First trace: a 6.035 s clocksource readout gap at the last journal line, a whole-platform stall (SMI/power class), no pstore, no SEL. Packet 83's warm arm was exact with four graph pools (2 devices x 2 threads). Relaunching packet 83 as server 83b (runner 83b, bases 110900-115200).**
[Evidence](experiments/ltx25-b70/notes/2026-09-19-freeze-evidence-soft-lockup.md).

**Four-B70 host, September 19 22:39 UTC: server 83b's first prompt failed on one corrupted byte of the tokenizer in host memory (file on disk verified exact against the model receipt); server not latched, campaign retried on it as f83br2-* (bases 120900-125200). Hardware evidence is now: eleven silent freezes, a 6 s platform stall, and a silent host memory error minutes after boot; memtest and the BIOS/PSU items are the user's calls.**

**Four-B70 host, September 19 22:41 UTC: server 83b stopped. Reason: the memory-error prompt left the host-components node latched (`Component transition failed; halt new requests`, host_embedding_resident_node.py `_failure`), so the retry runner's first prompt was refused; no prompt can run on this server. Packet 83 relaunches as server 83c at 22:47 UTC (runner 83c, bases 130900-135200).**

**Four-B70 host, September 20 00:35 UTC: packet 83 fixed the sharded encoder's wrong clip (server 83c ran 30/30 prompts byte-exact, bird included, four graph pools) at 1.685 s/clip steady, no gain over packet 74's 1.607 because the two-clip sampler paces; the encoder is closed as a lever. The host is now the blocker: the twelfth freeze (22:50 UTC) was preceded by two whole-platform stalls of 18.2 s and 10.7 s inside the running arm, matching a 4.276 s clocksource readout gap in the journal, and a second single-byte memory corruption (position 7,941,018, 0x5d read as 0xb5) killed server 83d on the next boot after the first killed 83b. Both files verify exact on disk and in page cache. Memtest86+ before any further promotion.**
[Packet 83 results](experiments/ltx25-b70/notes/graph-capture-83-results.md),
[freeze and corruption evidence](experiments/ltx25-b70/notes/2026-09-19-freeze-evidence-soft-lockup.md).
The freeze zeroed 34 git objects including HEAD's commit; all recovered from
origin (quarantine at .git/quarantine-zero-objects-20260920), fsck clean, no
receipt lost, because the runner pushes after every arm.
