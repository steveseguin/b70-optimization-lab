# Packet 137: residual cycle and preparation attribution

The remaining pooled odd-period excess is chiefly a **fresh-text mixture**, not
a demonstrated two-chunk stall. Packet 137 therefore targets a different,
measurable CPU cost: repeated scalar F32 finiteness scans. The proposed bulk
predicate retains each fresh check and every hash, owner, snapshot and floor.
Its direct-chain CPU saving is estimated at **0.152 s/chunk**, including
**0.076 s before sampler A**. No native saving has been measured.

This is a CPU-only audit of saved files on steve-b70s. Commands use nice 19,
OMP_NUM_THREADS=2 and `/home/steve/.venvs/ltx25-baseline/bin/python -B`.
No GPU, device, model server, launcher, check-only, live port, unit,
model-process signal or host setting was touched. Existing runs and
`/home/steve/ltx-stream` were read only. CPU tests use inherited isolated mock
services; interrupted CPU test processes are recorded in the design note.

## Evidence and parity

The [analyzer](../experiments/ltx25-b70/data/resume-20261008/continuation137-analysis/analyze.py)
freezes **120 consecutive GC10 source chunks 10–129**, corresponding to
destination periods 11–130, plus **110 GC60 source chunks 10–119**.
Capture time is 2026-10-10 16:23:27 UTC; the growing GC10 client manifest then
contained 175 rows. Selection is fixed by sequence, with no outlier removal.
The [JSON](../experiments/ltx25-b70/data/resume-20261008/continuation137-analysis/timelines.json)
retains 706 input hashes, absolute integer timestamps, relative timestamps,
all submit/decode/preview buckets, every node mark, six labeled snapshots and
their parts, turnaround marks and recorded maintenance events.
Four structural checks pass, including consecutive coverage and telescoping
each row's chain intervals to its actual submit period.

**Period(s) = submit(s) − submit(s−1).** Its work belongs to source chunk
`s−1`. Thus source-even work makes destination-odd periods. A chunk's own
preparation must never be joined to its incoming period as its cause.
The fixed window's median outgoing period is 5.236262 s, mean 5.740145 s.
These window-specific values do not replace the coordinator's longer-session
5.242 s median or its earlier 116-period census.

Parent packet 135 manifest is
`4356482eae2f1d7ac95b17e6483379ceed0cc90ed488d46765803451980402c3`;
inner plan is
`7750e7b54c885f99a73ab87b17013fc0a850a1af942f0c00422adbae596258c4`.
The JSON records both complete run paths and server identities; the historical
`dxpu2` run-name token does not override receipt placement on card 3.

## Which bucket grows

All figures below are medians in seconds, grouped by **source** sequence.
Independent bucket medians are descriptive and must not be added as a budget.

| Source mod 4 | Destination mod 4 | Fresh text | GC10 period | Pre-A | Text window | Commit→served | Own go-wait | GC60 period |
| ---: | ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 0 | 1 | yes | 5.625967 | 0.799904 | 0.378417 | 0.008246 | 0.212794 | 5.671482 |
| 1 | 2 | no | 5.195889 | 0.430897 | 0.000795 | 0.006010 | 0.218547 | 5.209212 |
| 2 | 3 | no | 5.195179 | 0.428988 | 0.000812 | 0.027233 | 0.218809 | 5.215489 |
| 3 | 0 | no | 5.194081 | 0.402496 | 0.000824 | 0.028677 | 0.597108 | 5.213238 |

Every group has 30 GC10 rows. The two source-even groups contain 30 fresh-text
and 30 reuse requests; source-odd contains 60 reuse requests. Pooled
destination-odd/even medians are **5.464209/5.194625 s**. Crucially, reused
text on source mod-4=2 is as fast as the other reuse classes. The pooled slow
median averages source122's 5.441202 and source118's 5.487217: the fresh-text
half pushes its midpoint into the slow end of the reuse distribution. It is
not evidence that every odd destination pays another 0.270 s.

Fresh text executes **after A conditioning**, in node364 before stream_text.
The historical `first_node_to_condition_a` comment mentioning text is not an
accurate execution-order description of these graphs. The 0.378417-s text
window carries the clear class-dependent growth. Period minus its own text
window, computed per row before grouping, has source-even/odd medians
5.219545/5.193864 s; that arithmetic is a diagnostic, not an achievable
performance projection or permission to reuse future text.

Own go-wait grows on source mod-4=3 because its decoder waits for the *next*
request's sampler A, after that request's fresh text. This wait is a
consequence of next-request preparation, not an independent delay to subtract.
Median decode FIFO wait is 47 microseconds. All120 rows consume precomputed A;
B is precomputed on113 rows and native-inline on seven (sources62,67,78,88,98,
114,124), following the predecessor's bounded three-second go timeout. These
seven outgoing periods are4.937–5.254s, not the slow odd population. All rows
have all six snapshots and report equal cone/display anchors.

Manual GC/allocator work still overlaps 12/120 periods and 8/120 handoffs.
Median overlap among those eight handoffs is 0.274201 s. Four other handoffs
over 150 ms (sources14,32,85,118) lack a recorded manual-maintenance overlap;
automatic GC, GIL and individual native locks are not separately instrumented.
They remain unexplained outliers, not proof of another periodic mechanism.
The earlier [two-cycle analysis](../experiments/ltx25-b70/notes/2026-10-10-continuation-2cycle-analysis.md)
and [maintenance analysis](../experiments/ltx25-b70/notes/2026-10-10-continuation-evenchunk-stall.md)
describe real older stalls; neither attribution can be extended to all current
odd periods. Changing the GC interval again has no supported residual saving.

## Both threads and the next request

The [50 consecutive timelines](../experiments/ltx25-b70/data/resume-20261008/continuation137-analysis/timelines.md)
show sources10–59 in seven tables: full chain, pre-A components, handoff,
predecessor display/tail/preview, own successor preparation, every prompt
snapshot, and the other submit-split durations. Maintenance events are retained
in the JSON. The JSON supplies every available mark without
rounding, including null/missing marks and node events not compressed into the
tables. The decoder's source n−1 display and tail overlap source n sampling;
its preview runs on a third worker. Source n's own A precompute feeds n+1.

Relative to the current submit, predecessor display starts at median 0.598992,
ends at 3.424818, tail ends at 4.217689 and preview ends at 4.990830 s.
**Zero of 120** current request-before snapshot windows overlaps predecessor
display, tail or preview. These jobs cannot explain the request-before cost.
Preview occasionally extends beyond receipt staging (minimum slack −0.252538 s),
so it would also be wrong to claim that all previews always finish before
every handoff. Its recorded overlap does not establish a GIL or allocator
stall. Per-card synchronization cost is not timed independently.

## Composition of the 0.44-second path

The total submit→sampler-A median is **0.441516 s**. Text has a low pooled
median because 90/120 requests reuse it; fresh-text requests are about 0.80 s.
Every bucket and snapshot below remains in the candidate.

| Component | Median s | Exact-removable portion proposed |
| --- | ---: | --- |
| Precheck | 0.000750 | none |
| Validation/handler return | 0.001465 | none |
| Queue→executor | 0.000820 | none; signed intervals retained |
| Authority begin | 0.002253 | none |
| Before-request checks | 0.024184 | none |
| Request-before outer snapshot | 0.047737 | none; inner snapshot 0.040983 |
| Before-request tail | 0.000001 | none |
| Executor→first node | 0.001050 | none |
| First node→A condition | 0.153225 | includes anchor span below, not fresh text |
| Anchor node bounds, nested in preceding row | 0.150868 | two finite scans: estimated 0.025281; not the full read/lock span |
| A precompute lookup | 0.003038 | none |
| A guarded tail, containing next three rows | 0.175762 | four finite scans: estimated 0.050562 across guarded boundaries |
| A-before snapshot | 0.037597 | none |
| A consume between snapshot endpoints | 0.050202 | includes native/replay and guard checks, not isolated encode time |
| A-after snapshot | 0.035924 | none |
| Dispatch after A condition, pooled | 0.003972 | includes fresh text on fresh rows; no new text reuse |
| Text window, fresh/reused | 0.378417 / approximately 0.0008 | none in this packet |

The A-tail also contains checks before/after its snapshot brackets. None of
these rows may be summed twice. In an extended 140-row CPU census the median
sum of those guard margins is 0.047610 s. The shorter frozen120 window is the
authority for the main table. Snapshot residence enumeration, source/code
checks, encoder lock, memory barriers, precompute ownership and fresh hashes
are not removed. Earlier read-ahead and reduced-barrier options are existing
levers, not a newly established 0.15-s anchor-read saving. The binary plan
guard and immutable-signature digest cache are also already active.

## Exact candidate and predicted saving

The [CPU screen](../experiments/ltx25-b70/data/resume-20261008/continuation137-analysis/finite-screen.py)
and [receipt](../experiments/ltx25-b70/data/resume-20261008/continuation137-analysis/finite-screen.json)
use a deterministic 786,432-byte finite anchor, 51 alternating trials and
262,235 assertion cases. Scalar median is **0.013031439 s**; bounded bulk
median is **0.000390965 s**. This is a CPU mechanism measurement, not a native
stream benchmark. Correctness includes all65,536 upper-byte pairs under four
lower-mantissa patterns, NaNs/infinities, signs, subnormals, signed zero,
opposite-word flags and block boundaries.

For a little-endian F32 word, exponent255 means byte3's low seven bits are all
one **and** byte2's high bit is one. Mapping byte3 to either0x80 or0, then
ANDing corresponding byte2 lanes as integers, tests the identical condition.
AND has no carries between bytes. Aligned64KiB blocks bound temporary memory.
No floating conversion, tensor operation, content cache or numerical change
is introduced. Every invocation reads all required immutable input bytes anew.

There are six scans before A (file read, begin, four A boundaries), four B
boundary scans, one finish scan and one cone-anchor publication scan:
**12 direct-chain scans**, estimated **0.151686 s** saved. Four more scans in
A/B precompute overlap other work; their0.050562 s CPU estimate is explicitly
excluded from the period forecast. A rough no-new-wait forecast is **5.09 s
per6 s of video**, versus the coordinator's5.242 s baseline, about2.9% less.
Scheduling or changed overlap can reduce that gain; only native qualification
and matched measurements can establish it. The0.270 s pooled parity gap is
not added to this saving. Fresh text and maintenance outliers remain.

Packet construction and qualification are separate from these saved-file
findings; the native performance prediction remains unmeasured.

## Consecutive two-thread timeline

Sources10–59; each origin is its own submit, in seconds. R is the current request-before outer snapshot; A is its sampler-A start. D/T/P are predecessor display, decode tail and preview intervals. Prep is the current decoder’s A preparation for its successor. The handoff is current commit-written→first-served. These are intervals, not added durations; the linked seven-table companion and JSON retain the remaining buckets and every exact mark.

| Source | Period→next | R | A start | D | T | P | Own prep A | Handoff |
| ---: | ---: | --- | ---: | --- | --- | --- | --- | --- |
| 10 | 5.188 | 0.036–0.085 | 0.442 | 0.610–3.428 | 3.428–4.226 | 4.297–4.983 | 5.178–5.408 | 5.176–5.180 |
| 11 | 5.254 | 0.030–0.076 | 0.445 | 0.608–3.431 | 3.431–4.240 | 4.314–5.007 | 5.196–5.437 | 5.194–5.226 |
| 12 | 5.570 | 0.046–0.097 | 0.768 | 0.924–3.720 | 3.720–4.548 | 4.620–5.306 | 5.518–5.756 | 5.516–5.547 |
| 13 | 5.199 | 0.017–0.069 | 0.425 | 0.594–3.430 | 3.430–4.215 | 4.284–4.887 | 5.176–5.420 | 5.174–5.178 |
| 14 | 5.406 | 0.015–0.070 | 0.437 | 0.595–3.411 | 3.411–4.209 | 4.282–5.347 | 5.197–5.348 | 5.195–5.397 |
| 15 | 5.014 | 0.013–0.055 | 0.283 | 0.435–3.249 | 3.249–4.056 | 4.127–4.735 | 5.005–5.238 | 5.002–5.006 |
| 16 | 5.645 | 0.031–0.080 | 0.819 | 0.970–3.775 | 3.775–4.604 | 4.674–5.275 | 5.587–5.828 | 5.584–5.619 |
| 17 | 5.208 | 0.019–0.067 | 0.417 | 0.591–3.389 | 3.389–4.184 | 4.260–4.952 | 5.146–5.400 | 5.144–5.178 |
| 18 | 5.190 | 0.045–0.101 | 0.410 | 0.566–3.421 | 3.421–4.221 | 4.295–4.967 | 5.180–5.429 | 5.177–5.182 |
| 19 | 5.278 | 0.031–0.073 | 0.464 | 0.643–3.482 | 3.482–4.296 | 4.372–5.104 | 5.251–5.582 | 5.249–5.261 |
| 20 | 6.316 | 0.040–0.167 | 1.324 | 1.497–4.430 | 4.430–5.287 | 5.360–6.041 | 6.306–6.555 | 6.303–6.308 |
| 21 | 5.500 | 0.035–0.115 | 0.453 | 0.622–3.452 | 3.452–4.267 | 4.337–4.975 | 5.199–5.718 | 5.197–5.482 |
| 22 | 5.240 | 0.037–0.084 | 0.440 | 0.600–3.425 | 3.425–4.217 | 4.291–4.955 | 5.181–5.422 | 5.179–5.210 |
| 23 | 5.126 | 0.021–0.069 | 0.403 | 0.567–3.359 | 3.359–4.148 | 4.217–4.832 | 5.101–5.339 | 5.099–5.109 |
| 24 | 5.621 | 0.022–0.093 | 0.798 | 0.951–3.807 | 3.807–4.637 | 4.709–5.336 | 5.597–5.843 | 5.595–5.600 |
| 25 | 5.176 | 0.049–0.101 | 0.441 | 0.609–3.428 | 3.428–4.184 | 4.256–5.004 | 5.150–5.385 | 5.148–5.152 |
| 26 | 5.182 | 0.044–0.091 | 0.427 | 0.597–3.419 | 3.419–4.218 | 4.289–4.949 | 5.172–5.453 | 5.169–5.174 |
| 27 | 5.816 | 0.037–0.089 | 0.487 | 0.673–3.346 | 3.346–4.256 | 4.328–5.501 | 5.270–5.407 | 5.267–5.807 |
| 28 | 5.433 | 0.015–0.056 | 0.678 | 0.852–3.543 | 3.543–4.483 | 4.542–5.246 | 5.422–5.663 | 5.419–5.424 |
| 29 | 5.208 | 0.033–0.077 | 0.470 | 0.637–3.449 | 3.449–4.242 | 4.311–5.031 | 5.198–5.425 | 5.195–5.199 |
| 30 | 5.215 | 0.031–0.096 | 0.414 | 0.580–3.435 | 3.435–4.253 | 4.316–5.062 | 5.204–5.432 | 5.201–5.206 |
| 31 | 5.183 | 0.034–0.078 | 0.426 | 0.581–3.396 | 3.396–4.176 | 4.251–4.882 | 5.136–5.375 | 5.134–5.163 |
| 32 | 5.768 | 0.018–0.073 | 0.774 | 0.922–3.594 | 3.594–4.551 | 4.628–5.694 | 5.610–5.759 | 5.608–5.760 |
| 33 | 5.019 | 0.011–0.051 | 0.266 | 0.412–3.233 | 3.233–4.052 | 4.126–4.884 | 5.008–5.241 | 5.005–5.010 |
| 34 | 5.135 | 0.029–0.071 | 0.424 | 0.575–3.363 | 3.363–4.159 | 4.236–4.951 | 5.124–5.374 | 5.122–5.126 |
| 35 | 5.233 | 0.039–0.117 | 0.461 | 0.632–3.425 | 3.425–4.229 | 4.314–4.967 | 5.181–5.462 | 5.179–5.211 |
| 36 | 5.692 | 0.027–0.083 | 0.850 | 1.035–3.834 | 3.834–4.677 | 4.751–5.416 | 5.640–5.867 | 5.638–5.669 |
| 37 | 5.134 | 0.019–0.062 | 0.389 | 0.570–3.378 | 3.378–4.185 | 4.260–4.940 | 5.124–5.352 | 5.120–5.125 |
| 38 | 5.358 | 0.029–0.077 | 0.443 | 0.597–3.430 | 3.430–4.226 | 4.302–5.291 | 5.246–5.477 | 5.244–5.349 |
| 39 | 5.422 | 0.041–0.086 | 0.339 | 0.489–3.359 | 3.359–4.171 | 4.242–4.917 | 5.129–5.728 | 5.127–5.404 |
| 40 | 6.019 | 0.036–0.150 | 1.011 | 1.172–4.153 | 4.153–4.999 | 5.073–5.719 | 6.008–6.281 | 6.005–6.010 |
| 41 | 5.259 | 0.034–0.088 | 0.464 | 0.635–3.500 | 3.500–4.321 | 4.395–5.088 | 5.249–5.475 | 5.246–5.251 |
| 42 | 5.139 | 0.052–0.098 | 0.416 | 0.560–3.367 | 3.367–4.184 | 4.245–4.943 | 5.127–5.360 | 5.122–5.130 |
| 43 | 5.433 | 0.058–0.107 | 0.454 | 0.613–3.641 | 3.641–4.467 | 4.542–5.302 | 5.410–5.637 | 5.407–5.412 |
| 44 | 5.615 | 0.042–0.082 | 0.803 | 0.943–3.780 | 3.780–4.615 | 4.686–5.396 | 5.566–5.790 | 5.564–5.593 |
| 45 | 5.166 | 0.017–0.059 | 0.390 | 0.539–3.333 | 3.333–4.150 | 4.222–4.920 | 5.087–5.304 | 5.085–5.135 |
| 46 | 5.089 | 0.013–0.055 | 0.356 | 0.514–3.319 | 3.319–4.114 | 4.185–4.903 | 5.078–5.307 | 5.076–5.081 |
| 47 | 5.217 | 0.031–0.077 | 0.432 | 0.602–3.417 | 3.417–4.204 | 4.277–5.075 | 5.207–5.438 | 5.204–5.209 |
| 48 | 5.848 | 0.032–0.075 | 0.802 | 0.951–3.765 | 3.765–4.589 | 4.661–5.324 | 5.797–6.024 | 5.795–5.825 |
| 49 | 5.093 | 0.019–0.059 | 0.378 | 0.526–3.336 | 3.336–4.127 | 4.197–4.925 | 5.083–5.316 | 5.080–5.085 |
| 50 | 5.197 | 0.027–0.074 | 0.443 | 0.601–3.431 | 3.431–4.246 | 4.319–4.943 | 5.175–5.395 | 5.172–5.177 |
| 51 | 5.409 | 0.035–0.083 | 0.402 | 0.546–3.376 | 3.376–4.194 | 4.267–4.903 | 5.120–5.606 | 5.117–5.391 |
| 52 | 5.538 | 0.035–0.080 | 0.774 | 0.932–3.741 | 3.741–4.599 | 4.672–5.373 | 5.527–5.758 | 5.524–5.529 |
| 53 | 5.148 | 0.031–0.080 | 0.432 | 0.581–3.375 | 3.375–4.178 | 4.244–4.936 | 5.135–5.390 | 5.133–5.139 |
| 54 | 5.227 | 0.034–0.083 | 0.465 | 0.637–3.421 | 3.421–4.211 | 4.282–5.005 | 5.179–5.409 | 5.177–5.204 |
| 55 | 5.141 | 0.016–0.063 | 0.405 | 0.569–3.372 | 3.372–4.174 | 4.247–4.962 | 5.130–5.382 | 5.128–5.132 |
| 56 | 5.678 | 0.061–0.108 | 0.841 | 0.999–3.832 | 3.832–4.661 | 4.729–5.333 | 5.628–5.839 | 5.626–5.657 |
| 57 | 5.286 | 0.016–0.055 | 0.363 | 0.517–3.528 | 3.528–4.337 | 4.405–5.062 | 5.276–5.502 | 5.273–5.277 |
| 58 | 5.244 | 0.030–0.073 | 0.444 | 0.601–3.417 | 3.417–4.217 | 4.292–4.937 | 5.170–5.394 | 5.168–5.216 |
| 59 | 5.089 | 0.013–0.057 | 0.354 | 0.501–3.325 | 3.325–4.130 | 4.194–4.830 | 5.078–5.388 | 5.075–5.080 |

Implementation and qualification scope: [packet 137 design](2026-10-10-continuation137-stream-design.md).
