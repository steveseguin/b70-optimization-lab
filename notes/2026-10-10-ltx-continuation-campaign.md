# LTX continuation-stream campaign, 2026-10-09/10: packets 117–131

The useful production configuration at this campaign boundary is **packet 129,
145 frames, eager cone (`dg0`), legacy auxiliaries, serial display on xpu:3,
idle maintenance, GC60, immutable digest caching and background storage scans**.
Packets 127/128 supplied the best measured 145-frame periods, approximately
**5.47–5.53 seconds per six seconds of new video (0.91–0.92 s/s)**. Packet 129
adds complete atomic publication of evidence read by HTTP routes. Its completed
609-chunk log gives 599 consecutive periods: median **5.554 seconds (0.926
s/s)**, mean 5.947 and p90 6.239; its own result remains separate from the
faster 127/128 measurements. These are
local continuation-session measurements with their recorded byte gates, not a
new public recipe or a two-fresh-server speed certification.

The [results ledger](../results/ltx25-continuation-stream-2026-10-10.md) owns
recomputed client-log statistics, configuration/run/work-directory identities,
verdicts, comparison counts and incidents. The [captured summary](../data/ltx25-continuation-stream-2026-10-10.json) and
[CPU analyzer](../scripts/analyze-ltx-continuation-ledger.py) preserve the input
hashes, calculation and endpoints. This note preserves why each arm
was tried and what the evidence changed. Figures attributed below to a timed
CURRENT entry or a fixed analysis window are historical observations, not
substitutes for the ledger's complete captured log windows.
Chronology headings follow CURRENT reporting times, which can lag the logged
event. For example, the packet-127/169 refusal was logged at 09:05:11 UTC;
the coordinator reported it in the later 09:10–09:50 sequence.

This consolidation read evidence only, at nice 19 with OMP_NUM_THREADS=2. It
performed no GPU/runtime import, server, launch, systemd/unit, port, device,
process-signal or host-setting operation; existing runs and `/home/steve/ltx-stream`
were not written. No `/tmp` scratch was created. The main chronology starts at
2026-10-10 01:20 UTC and includes the preceding October 9 packet-117/118 work
needed to explain that continuation. The status boundary is CURRENT's October
10 11:35 UTC entry: packet 129 closed and packet 131 launching, with its native
result pending.
The final ledger capture includes 131's client header and first qualification
request at 11:32:09.449 UTC, with no verdict or streamed chunk. That captured
prefix is preserved as a pending row rather than a measured result.

## Measurement rules that prevent a false history

An anchored chunk repeats its first frame. At 24 frames/s, 97, 121, 145 and
169 frames add **4, 5, 6 and 7 seconds of new video**, respectively. Earlier
notes sometimes divided by the nominal total duration (for example 121/24 =
5.0417 seconds). That slightly flattering denominator is preserved only as
an attributed historical reading; the ledger uses new video.

Period is submit-to-submit wall time, not the sum of separately reported
median timing buckets. Some buckets overlap. Analyses also label parity by
the source chunk, while the client period printed on a chunk identifies the
destination chunk; those even/odd labels reverse. The ledger uses destination sequence ≥10, including 9→10, and nearest-rank
p90. It does not bridge separate client segments after a client restart; the
99.360-second 121 interruption and 87.372-second 127 interruption remain
recorded separately. All other measured periods are retained. Strong alternating timings mean that adding one sample or mixing
windows can move the pooled median without improving either population.
Client interruption gaps belong in the incident history and must not silently
become either model work or selectively discarded slow samples.

Three-chain qualification and per-chunk cone/display anchor equality are
separate from cross-packet comparisons. A changed frame count has no
same-shape predecessor oracle unless one is explicitly recorded. Full-image
cross-card qualification is stronger than checking only the final anchor.
CPU test passes, projected memory and estimated speeds never count as native
qualification or streamed results.

## Chronology

**October 9: packet 117 establishes the cone and overlap baseline.** At 97
frames, the cone anchor, stage-B encode overlap and preparation ahead of the
next request reduced the fixed 100-period median from packet 116b's 5.54 to
4.82 seconds. Its 72 shared stream chunks were byte-identical to 116b. The
121-frame decoder-graph attempt then refused during qualification: xpu:3 was
76 MB below its existing floor. The fallback with the decoder graph off
qualified and measured 5.40 seconds in the fixed 100-period window. Longer
chunks amortized fixed work, but the pre-sampler path remained about 0.52
seconds despite zero measured waits for the prepared encodes. A memory
refusal was recorded as a refusal, not a correctness failure or GPU fault.
See the [97-frame result](../experiments/ltx25-b70/notes/2026-10-09-continuation117-results-97.md)
and [121-frame result](../experiments/ltx25-b70/notes/2026-10-09-continuation117-results-121.md).

**October 9 CPU review: packet 118 is withdrawn before launch.** The new
fingerprint snapshots and decoder-pool cap needed review before replacing
117. Review found concurrent dual-inspection bookkeeping attached to the
wrong chunk, incomplete memory-verdict comparison, inherited cap leakage in
an off control, and timing claims stronger than the instrumentation justified.
118b was rebuilt as a separate identity. The failed parent and the repair
remain in the [review](../experiments/ltx25-b70/notes/2026-10-09-continuation118-review.md)
and [rebuild](../experiments/ltx25-b70/notes/2026-10-09-continuation118b-rebuild.md).

**October 10, 01:20–01:47 UTC: owner acceptance, then 117 → 118b dg0.** The
owner accepted continuing on boot 4aafe57b after the earlier Flash-Next fault
halt; this was not a reboot or deletion of the earlier fault evidence. Packet
117 qualified under verdict `508f2f2bac6a`, streamed 63 chunks and stopped
cleanly. The 118b rehearsal initially rejected a runtime identity mismatch:
the launcher used `bin/python3`, whereas the pin named `bin/python`. The
one-line fix preceded launch. 118b then qualified as `6824dd4a6fae`; its first
101-chunk stream compared exact to 117 on 63/63 shared chunks. The historical
steady median was 5.227 seconds, an improvement over the 117 baseline. The
[fingerprint result](../experiments/ltx25-b70/notes/2026-10-10-continuation118b-results-121-dg0.md)
retains that window. A separate CPU-test mock in the Flash-Next preparation
accidentally opened a render device; CURRENT records its exit without a new
fault and the corrected test guard. It was not an LTX stream failure.

**02:02–02:18 UTC: 118b dg1, capped pool, loses despite a faster cone.** The
1.0 cap allowed the first decoder method to be captured; it was never a
hard bound on the first capture's growth. Qualification passed, and the
37-chunk arm was exact, but its historical median rose to 5.559 seconds.
Cone work fell about 0.19 seconds while the combined upsample/B-preparation
bucket rose about 0.52. The coordinator restored dg0, first as
`s118b-live02` and later as `s118b-live03`. The original
[graph-arm note](../experiments/ltx25-b70/notes/2026-10-10-continuation118b-results-121-dg1-cap1.md)
proposed graph contention. Later evidence narrows that claim below; it must
not survive as a proved device-level cause.

**02:56–03:30 UTC: packet 119 tests eager display and anchor read-ahead.**
It retained the graph cone, made full display eager, and read the next anchor
ahead. The arm streamed 61 chunks, qualified as `9dac6eb450ba`, and matched
118b on 37/37 compared outputs. Its historical median was 5.421 versus
118b's 5.279 seconds: a loss. The first account blamed a slower upsampler
and an anchor read inside the receipt HTTP handler. The
[receipt analysis](../experiments/ltx25-b70/notes/2026-10-10-continuation119-results-121.md)
corrected both. The upsampler resides on xpu:0; eager display restored its
short interval. Read-ahead runs after receipt commit on the decode worker.
119 retained enough graph memory on xpu:3 to trigger near-floor dual walks
at every sampled B-before, B-after and request-after snapshot. Their extra
roughly 0.15 seconds in B checks and 0.08 seconds after the request explain
the remaining loss. The earlier dg1 sampler-a trace still shows a blocking
host interval ending with display, but its queue-level cause is unproven.
The lesson is to relieve the triggering memory pressure while retaining the
checks, not label all dg1 costs graph contention or remove safety work.

**03:43–04:06 UTC: packet 120 moves only full display to xpu:2.** A separate
eager decoder copy freed xpu:3's display transient while retaining its graph
cone. Read-ahead stayed off. Qualification `0d3305d1a160` checked copied
weights and full cross-card images; 109/109 stream images, last frames and
previews matched 118b. The fixed 100-period median was 5.082 seconds. The
first 28 periods at 5.029 had been called real time using total chunk length;
the longer observation and the five-second new-video denominator show that
claim was premature. The graph saving survived once the extra dual-walk cost
was removed. See the [120 result](../experiments/ltx25-b70/notes/2026-10-10-continuation120-results-121.md).

**04:08–05:08 UTC: packet 121 reaches faster-than-real-time continuation at
145 frames, then exposes two reliability defects.** The simplest first arm
used dg0, legacy auxiliaries and serial display on xpu:3. Qualification
`356b25be584b` passed; the early 24-period median was 5.612 seconds per six
seconds of new video. At chunk 154, preview publication raced the guarded
reader and returned HTTP 500. The client stopped with exit 7; the healthy
server's chain continued, and a client resume followed. Later, at 420
completed chunks, HTTP 409 stopped admission because the three-GiB allowance
counted all filesystem writers rather than this run's writes. A controlled
restart made a second 121 session (`9a57f69a751f`). These are distinct
incidents, not model faults. The
[145-frame analysis](../experiments/ltx25-b70/notes/2026-10-10-continuation121-results-145.md)
separates exact output, memory and timing. Its fixed-window values must not
be mistaken for full-session medians.

**04:52–05:58 UTC: packets 122, 123 and 123b address admission and storage.**
122 refined the memory census and made the replica reserve explicit; it was
not launched. Its planning evidence did not admit the 145 graph combination
or conservative legacy 169 geometry. Packet 123 prepared atomic previews,
exit-7 status capture and an optional move of the upsampler and audio
VAE/vocoder to xpu:2; it too was not launched. 123b added per-run own-writes
accounting with a recorded 16-GiB allowance for this campaign, preserving the
50-GiB filesystem floor. Its first client refused a plan pin: a file byte
hash had been used where the protocol requires the sealed inner-plan hash.
Correcting that pin allowed qualification; no evidence was rewritten.
See [123 residency design](../experiments/ltx25-b70/notes/2026-10-10-continuation123-stream-design.md)
and [123b storage design](../experiments/ltx25-b70/notes/2026-10-10-continuation123b-storage.md).

**06:12–07:28 UTC: 123b tests auxiliary placement, 169 frames, and a legacy
control.** The 145 auxiliary-xpu:2 arm qualified as `d410928322ba` and
matched 121 on 32/32 compared chunks. The 169 arm qualified as
`4eeb3b603c94`, but the early 27-period reading was 6.824 seconds per seven
seconds of new video; the completed interior slice was slower still. It lost
to the good 145 line. The early explanation that the cone waited for the
previous display was corrected by the
[169 timeline](../experiments/ltx25-b70/notes/2026-10-10-continuation123b-results-169.md):
in 37/38 interior intervals display had already finished when the cone was
queued. Audio, hashing and record work kept the same decode worker busy for
roughly another 0.6 seconds; actual cone execution grew only about 0.12
seconds. The three-second bound limits waiting for the next sampler event,
not the execution time of full display. The arm returned to 145 aux, then
123b legacy (`b6bcdae18297`) supplied the missing placement control.

The initial apparent auxiliary cost was partly a **123b bookkeeping
regression**, colloquially about half of the apparent loss. That fraction is
not an isolated measurement. The matched analysis found legacy 123b itself
slower than 121, with repeated synchronous storage walks and larger plan
checks. A fixed 40-interval 123b-to-123b comparison gave only +28.6 ms pooled
median for the auxiliary move, not an independently proved +150-ms card hop.
Cone time increased, but sampler B and audio improved; the whole transfer
cost cannot be inferred from one bucket. Preserve the correction in the
[regression analysis](../experiments/ltx25-b70/notes/2026-10-10-continuation123b-regression.md).

**07:28–08:02 UTC: packets 124 and 125 test worker separation and GC cadence.**
124 put full display on xpu:2, kept legacy auxiliaries, moved audio earlier
and used a parallel completion worker. At 145 it qualified as
`24e7fd6c6dbb` and measured a historical 5.746 seconds, neutral against the
123b legacy baseline. The intended benefit was the longer 169 worker tail;
no 124-at-169 result was obtained. Packet 125 restored serial xpu:3 display
and tested GC60. Its `7c1e8a6ef3b2` qualification passed, but the early median
5.780 versus 5.770 seconds was also neutral. The assertion that changing the
ten-second interval would itself remove the two-cycle was too strong. The
[124 design](../experiments/ltx25-b70/notes/2026-10-10-continuation124-stream-design.md)
and [125 analysis](../experiments/ltx25-b70/notes/2026-10-10-continuation-2cycle-analysis.md)
retain the original hypotheses and their limits.

**08:22–08:53 UTC: packet 126 removes request-thread bookkeeping work.**
Background storage sampling and cheaper full-tree plan comparisons retained
fresh admission, mutation checks, reserve checks and refusal behavior. The
CPU replay's 0.144-second saving was diagnostic, not a model speed result.
Native qualification `a4b739676c5a` passed. The early 56-period median was
5.722 seconds, a partial recovery; the later observed window was 5.759.
Atomic preview fsync was already on a separate worker, so moving it again
could not explain or repair the regression. The remaining loss motivated a
full [145-frame budget](../experiments/ltx25-b70/notes/2026-10-10-continuation-budget-145.md),
not removal of the reliability fixes.

**09:10–09:50 UTC: packet 127 refuses 169, then establishes the best 145
measurement.** The first 169 rehearsal inherited GC60/digest settings outside
their permitted 145/serial/xpu:3 scope and refused before launch. The actual
169 parallel-display qualification, with those settings out of scope, later
refused at `qrepeat-c000001`: xpu:2 free was 7.884 GiB against 6.5 GiB
transient plus 2 GiB floor, with a further screening allowance in the code.
There were seven completed cross-card-equal decodes but no completed
three-chain qualification or stream. This was a clean memory refusal, not a
GPU fault, and the reserve was not reduced. The fallback 145 serial xpu:3
arm added immutable signature-digest caching, GC60 and background scanning.
It qualified as `cbd91ba8a8cc`; the historical 85-period median was **5.467
seconds (0.911 s/s)**. At chunk 80 the decode-record reader hit the same
publication-race class as the earlier preview incident. The client stopped
and resumed; the server stayed healthy. The
[127 design](../experiments/ltx25-b70/notes/2026-10-10-continuation127-stream-design.md)
keeps mutable state and tensor facts freshly inspected on every snapshot.

**09:40–10:18 UTC: packet 128 identifies and reschedules the real receipt
stall.** Direct timing showed all **119** long packet-126 handoffs overlap
full Python GC plus allocator cleanup: median 252 + 56 = 308 ms. Preview,
display and the decode tail had finished earlier. Thus the cause was the
cleanup pair blocking receipt service; the maintenance interval alone was
not the complete two-cycle explanation. Packet 125 had already reduced
receipt handoffs to about 48/46 ms on the two parities even though its whole
period was neutral. Fresh-text work every fourth chunk and other costs
remain. The [overlap analysis](../experiments/ltx25-b70/notes/2026-10-10-continuation-evenchunk-stall.md)
corrects both the display/preview theory and the conclusion drawn from that
neutral aggregate.

128's idle policy waits for a bounded quiet admission window while preserving
mandatory cleanup. The GC10/digest arm (`86134e704d4f`) closed at 70 chunks:
historical n=60 median **5.493 seconds (0.915 s/s)**. The combined idle +
GC60 + digest arm (`0d1d0d811ce2`) gave n=61 median **5.528 seconds (0.921
s/s)**. Their gains overlap; adding the individual savings or claiming
identical parity populations is unsupported.

**10:18–11:35 UTC: packet 129 becomes the production line.** It keeps that
145-frame combined configuration and publishes every route-read evidence
file only after writing and fsync, using exclusive atomic publication. The
reader guard remains strict. This extends 123's preview fix to receipts,
decode records, captures and identity/halt files, addressing both exit-7
incidents. CURRENT's closure report records approximately 500 exact chunks,
a 36-second buffer and no stops before the controlled transition toward 131.
The completed client log captured for this ledger has **609 chunks**, so the
coordinator's approximate closure count is not its final count. Its 599
consecutive periods have median **5.554 seconds**, mean 5.947, p90 6.239
and median ratio **0.926 s/s**. The
[129 design](../experiments/ltx25-b70/notes/2026-10-10-continuation129-stream-design.md)
is a reliability change; assigning 127's best value to it would be misleading.

**10:50 UTC: packet 130 prepares a remedy for the missed xpu:2 census, but
169 is not launched.** The older census reused the 121-frame serialized
replica's before-decode recovery in a new concurrent 169 schedule. Actual
qualification did not recover that free memory. Card 2 holds the primary
text shard and other text state, not a sampler shard. The
[corrected inventory](../experiments/ltx25-b70/notes/2026-10-10-xpu2-residency-169.md)
found a 0.616-GiB base deficit and **1.366 GiB including the existing 0.75-GiB
screening margin**. Reserved-but-unused memory of 2.400–3.856 GiB is a
candidate reclaim pool, not a guaranteed release. 130 prepared one optional
allocator release followed by fresh admission; CPU work verifies zero
reclaimed GiB. Its projected 169 range already overlaps the measured 145
line, so the coordinator did not spend a launch on it.

**11:35 UTC: packet 131 targets the 145-frame cone graph; result pending.**
The next candidate retains the 129 production options, moves serial eager
display to xpu:2 and conditionally releases unused allocator blocks before
cone admission. The cone already captures only its first decoder method in
its own pool; another soft cap cannot make that first capture smaller.
The measured 121 growth is 3.195 GiB; 4.506 GiB at 145 is an estimate.
Qualification still performs full xpu:3 reference decodes, whose allocation
tail cannot be assumed gone. First capture requires **14.75 GiB physically
free**, later cones 9.75 GiB. The conditional 5.25–5.35-second target is not
a measurement. CURRENT records the launch transition, not a qualification or
speed outcome. See [xpu:3 inventory](../experiments/ltx25-b70/notes/2026-10-10-xpu3-residency-145.md)
and [131 design](../experiments/ltx25-b70/notes/2026-10-10-continuation131-stream-design.md).

## Open items at the evidence boundary

- **169-frame memory:** the 127 refusal stands. 130's optional release needs
  measured reclaimed memory, full qualification and a stable plateau. No
  lower floor, smaller reserve, skipped comparison or automatic fallback is
  justified. Even a fit must beat the measured 145 ratio to count as a win.
- **145-frame cone graph:** await packet 131's native result. CPU validation
  and the 121 graph saving do not prove its 145 capture will fit or run faster.
- **Snapshot schedule, owner's decision:** retain `full`. The
  [schedule audit](../experiments/ltx25-b70/notes/2026-10-10-continuation131-snapshot-schedule.md)
  measures about 121–125 ms for the first three snapshots, but the optional
  schedule removes selected barriers, not the inspections. Only about
  1.73–1.79 ms is timed in the affected memory sections; other barrier wait is
  unmeasured. A 0.12-second saving is not established. Combining the option
  with production GC60/digest settings also needs a reviewed scope change.
- **Flash-Next probes, awaiting the owner:** the clean-exit, sleep-exit and
  first-forward probes were prepared under the recorded boot acceptance;
  CURRENT says the coordinator's permission classifier still required owner
  action. They were not run as part of this ledger task. See
  [admission and limits](../experiments/qwen38-flash-next-fp8-b70/reopen-20261008/VALIDATION.md#owner-acceptance-admission-2026-10-10).
- **Storage cleanup proposal, awaiting the owner:** the
  [inventory](2026-10-10-storage-inventory.md) proposes conditionally reclaiming
  42.02 GB / 39.13 GiB from one redundant rejected transformer only after
  reconstructibility proof, external archive and fresh verification. It
  preserves every preview, anchor, receipt, log, latch, verdict and oracle.
  The inventory authorizes no deletion, and none was performed here.

The sealed build receipts under
`experiments/ltx25-b70/data/resume-20261008/continuation1*-build.json` preserve
packet identities and CPU validation. Their hashes and tests describe the
prepared code; the native verdicts and client logs in the results ledger
remain the authority for what actually ran.
