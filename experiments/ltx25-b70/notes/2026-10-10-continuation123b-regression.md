# Packet 126: receipt evidence for the 121 → 123b regression

The new synchronous own-writes scans are a real request-path regression. The
larger plan also makes the unchanged full-plan integrity check slower. Preview
fsync is **already on its own worker** in 123b; moving it off the decoder again
would fix a path that does not exist. The evidence supports removing repeated
storage walks while preserving admission and durability checks. It does not
support assigning exactly 150 ms to one call, or a further 150 ms to one card hop.

This is a CPU-only analysis of saved files, with no GPU, server, launch,
check-only, endpoint, unit, process signal, host setting, existing-run write, or
client-tree write. Commands used nice 19, OMP_NUM_THREADS=2 and the pinned
baseline Python with `-B`. The coordinator retains the live machine.

## Reproduction and definitions

[Analysis script](../data/resume-20261008/continuation126-regression-analysis.py)
and [frozen evidence](../data/resume-20261008/continuation126-regression-evidence.json)
include input paths, exact source hashes, all per-chunk metrics and four full
nanosecond timelines per session. The script binds sessions to receipt server
identities, not device-looking run-directory names. It imports only the standard
library and the sealed CPU-only storage walker. Its metadata replay never writes
to a source directory.

```sh
nice -n 19 env OMP_NUM_THREADS=2 /home/steve/.venvs/ltx25-baseline/bin/python -B experiments/ltx25-b70/data/resume-20261008/continuation126-regression-analysis.py
```

Period means next submit minus current submit. Tables use the **source** sequence:
even-source is the slow even→odd interval; odd-source is the fast odd→even
interval. The coordinator's even/odd labels identify the destination and are
therefore reversed. Fresh text is every fourth source sequence; a two-parity
median still mixes reused and fresh text. All five sessions use 145 frames,
frame anchor, eager cone, overlapping B encode, A prep-ahead, fingerprint
snapshots, sampler-A display release, full snapshot schedule and actual display
on xpu:3. Packet 124's parallel display/early audio is absent here.

The 5.611-second baseline is the fixed **40 intervals 10→11 through 49→50**
previously reported in the [145-frame note](2026-10-10-continuation121-results-145.md).
It is not the median of all 420 chunks. The user-supplied numbers also mix odd
and even counts from a strongly alternating distribution. This changes a pooled
median substantially without changing either parity. We preserve both the full
capture and fixed windows rather than force the data to match a requested delta.

| Session | Completed manifest rows | Full interior intervals | Full median | Fixed-40 median | Fixed-40 even-source / odd-source |
|---|---:|---:|---:|---:|---:|
| 121 live01 | 420 | 409 | 5.717 | 5.611 | 5.995 / 5.482 |
| 121 live02 | 316 | 305 | 5.757 | 5.620 | 5.962 / 5.484 |
| 123b legacy live01 | 61 | 50 | 5.828 | 5.828 | 6.255 / 5.679 |
| 123b aux live01 | 41 | 30 | 5.838 | unavailable | unavailable |
| 123b aux live02 | 213 | 202 | 5.897 | 5.857 | 6.255 / 5.693 |

The JSON's `destination_all_available` additionally includes interval 9→10:
123b legacy then has 51 intervals and median **5.7688**, reproducing the stated
5.770. Aux live01 has 31 and median **5.7322**. Aux live02's completed capture
is later than the coordinator's 190-chunk summary; its corresponding 203-interval
median is 5.8358. Counts and endpoints must accompany future comparisons.
Packet 121 live01 also contains a 99-second client pause, which is retained in
the full capture; fixed-40 comparison avoids that later pause without trimming
selected slow results.

On the fixed-40 comparison, legacy 123b is **+0.208–0.217 seconds in pooled
median**, **+0.260–0.294 on even-source**, and **+0.195–0.198 on odd-source**.
On all interior rows it is +0.071–0.111 pooled, +0.188–0.222 even-source and
+0.142–0.163 odd-source. Thus “about +0.15” is a useful problem description,
but not a single reproducible session-wide estimate.

## Where the time moved

The following **mean** differences partition the fixed-40 period exactly.
Unlike separately subtracted medians, these non-overlapping endpoint differences
add to the period difference. Reference is 121 live02; comparison is 123b legacy.
Milliseconds are rounded. These identify locations, not isolated causes.

| Exclusive chain interval | All | Even-source | Odd-source |
|---|---:|---:|---:|
| Submit → sampler A | +75.6 | +88.8 | +62.3 |
| Sampler A | +19.3 | +12.9 | +25.7 |
| Upsample + B conditioning | +30.9 | +26.3 | +35.5 |
| Sampler B | +5.6 | +6.3 | +5.0 |
| B done → anchor published | +32.4 | +36.8 | +27.9 |
| Anchor → receipt staged | +25.7 | +30.0 | +21.5 |
| Receipt staged → next submit | +46.5 | +60.8 | +32.1 |
| **Period** | **+236.0** | **+261.9** | **+210.1** |

The submit split and inner snapshot endpoints narrow the candidates:

| Fixed-40 median, seconds | 121 live02 all (even / odd) | 123b legacy all (even / odd) |
|---|---:|---:|
| Admission precheck | .00076 (.00212 / .00070) | .01494 (.01555 / .01468) |
| Before-request checks | .03786 (.02767 / .03957) | .05983 (.08612 / .05441) |
| Request-before wrapper | .08441 (.08693 / .08290) | .09574 (.09747 / .09245) |
| Request-before inner snapshot | .06213 (.06198 / .06213) | .06975 (.07156 / .06825) |
| Request-after inner snapshot | .05886 (.05915 / .05886) | .07141 (.07535 / .06919) |
| Receipt staged → commit mark | .00536 (.00536 / .00541) | .02949 (.03002 / .02868) |
| Commit write | .00740 (.00697 / .00774) | .01537 (.01533 / .01545) |
| Commit → executor exit | .00544 (.00553 / .00536) | .00687 (.00680 / .00710) |
| Commit written → first served | .17739 (.30283 / .03174) | .18490 (.33688 / .03283) |

The inner four-card request snapshot changes by approximately 8 ms before and
13 ms after. It cannot by itself explain the regression. The slow-parity
commit-to-serve gap remains the older ten-second GC/allocator phenomenon
analyzed for [packet 125](2026-10-10-continuation-2cycle-analysis.md). No new
per-card timestamp exists to label snapshot residuals as a specific GPU sync.

### Own-writes accounting: four request walks and additional status walks

Sealed 123b `integration.py` calls `storage_check` in admission `precheck`, at
entry to `before_request`, in `_after_chunk` while constructing the receipt's
`storage`, and again at the end of `after_request`. It also calls it for **every
status request**, as well as install/action boundaries. `mutate=False` does not
select a cheap path: it still calls the same `OwnWrites.check` and walk.

`run_storage.OwnWrites.allocated_bytes` takes an RLock for the entire traversal.
It walks the run and matching output, validation and request subtrees; cached
directory membership avoids some scandir calls, but it **restats every owned file
on every check**, and scans all names in shared parents to select the prefix.
The new lock serializes event-loop status/admission work against prompt-thread
checks. There is no historical timestamp around lock acquisition or the walk.
Consequently neither lock wait nor scan service time can be separately recovered
from receipts. The 15-ms precheck is a containing bucket, not a direct scan timer.

A bounded nine-scan CPU replay of the completed legacy run took **22.6 ms** on
the first scan and **5.72 ms median** on the next eight (311 accounted paths,
11 cached directories). This is a current archived-layout diagnostic: the run's
old output and request entries were moved, so its 13.3 MB total does not match
the approximately 1 GiB historical receipt. It must not be presented as the
historical scan duration. The uncached first-scan value is not a cold-page-cache
measurement; no cache was dropped.

The request path's measured precheck increase is about 14 ms, the before-request
check increase about 22 ms overall (58 ms on slow parity), and staged-to-commit
increases about 24 ms. These contain three of the four synchronous walks and
other Python work. The fourth is inside the receipt construction/tail. Status
calls fall from median seven to five in the fixed window, but their summed
recorded time rises from **4.2 ms to 67.2 ms per chunk** (even 3.8→84.2 ms;
odd 5.4→61.1 ms). Status runs concurrently, so this is not another 63 ms to add
onto the partition table. It does establish a large new event-loop service cost
and a route for lock/GIL contention. Removing request walks but retaining status
walks would leave this part of the regression.

### Repeated plan integrity serialization also got larger

`Session.healthy` still serializes and hashes the complete mutable inner plan
on each call, preserving immediate mutation detection. The canonical inner plan
grows from **1,007,146 bytes at 121 to 1,257,136 at 123b (+24.8%)**. On the common
30-row window, healthy calls stay at median 35/chunk; recorded plan-digest time
grows from **154 ms to 200 ms/chunk**. These timers aggregate calls on multiple
threads and can include contention; they are not an exclusive period bucket.

A same-process, nice-19 CPU replay of exactly the same canonical JSON + SHA256
operation, 35 times per plan, takes **131.3 ms for 121 and 165.6 ms for 123b**
(+34.2 ms). The larger plan therefore creates real additional CPU work even
without a server. It is a second specific regression path, with an approximate
30–50 ms/chunk cost envelope, rather than an unexplained GPU slowdown. Simple
cached hashes would weaken the existing mutable-plan gate and are not justified.
The timing table must not count this again on top of the request/conditioning
buckets where those calls occur.

### Preview durability: on its own worker already

`_decode_job` publishes the durable frame anchor first, waits for the receipt
commit, computes successor A/B preparation, performs display/audio and record
work, makes private CPU copies, and calls `preview.submit`. `StreamPreviewWriter`
then runs `_save_preview`, `publish_exclusive` and `_commit_preview` on the
`ltx116-preview-writer` thread. MP4 and JSON file fsync, exclusive same-directory
rename, and directory fsync all belong to that worker. The anchor fsync remains
on the decoder and predates 123. The preview is not in front of that chunk's
anchor publication or A prep-ahead.

The fixed-40 legacy preview-write median moves **.6654→.6792 s (+13.8 ms)**;
even-source .6825→.6869 (+4.4 ms), odd .6535→.6669 (+13.4 ms). This timer
includes encoding, MP4 fsync/read/hash/rename/directory fsync, and cannot isolate
fsync. The preview JSON commit follows the `preview_written` stamp and has no
separate timestamp, another explicit limit. Preview queue wait remains about
**9.6→9.8 ms**; private-copy/enqueue bracket **41.5→42.7 ms**. The predecessor's
MP4 publication leads the current receipt by median **.372→.395 s**; it is
already finished before that receipt in the measured interior records. The
same preview overlaps the current cone (about .64–.67 s after cone starts),
so indirect CPU/I/O contention is possible; no evidence quantifies it as 150 ms.
Atomic publication, SHA256, single-link identity, FIFO/back-pressure and failure
latch should remain intact.

Exit-7 status plumbing executes on a client error path; successful interior
chunks do not enter it. The transient replica allowance only changes launch
admission and the xpu:2-display replica branch, which these xpu:3 runs do not
use. Neither supplies a new serial 150-ms operation. The own-writes RLock is the
relevant new recurring synchronization; no added legacy device synchronization
was found in the auxiliary placement selector (legacy returns immediately).

## Auxiliary placement: bucket attribution, not a fabricated 150-ms hop

The fixed-40 123b-to-123b comparison is legacy 5.828 versus aux live02 5.857 s:
**+28.6 ms pooled median**, +0.13 ms even-source and +14.2 ms odd-source. Its
exact mean partition is +15.3 ms overall. A further +150 ms is not established
under this matched packet/window comparison. The shorter aux live01 is retained
with a separate fixed-30 comparison in the JSON, not extended to 40 points.

| Fixed-40 median, seconds | 123b legacy | 123b aux live02 | Difference |
|---|---:|---:|---:|
| Upsampler → B conditioning start | .06555 | .06471 | −.00084 |
| Sampler B | 1.68331 | 1.62244 | −.06087 |
| Cone `video_decode` bracket | .90758 | 1.00880 | +.10123 |
| B done → anchor | .95089 | 1.04975 | +.09886 |
| Audio decode, off-chain | .75176 | .29559 | −.45617 |
| Preview write, off-chain | .67916 | .72541 | +.04625 |

The principal positive on-chain change is the **xpu:3 cone bracket**, about
+0.10–0.12 seconds (full captures agree). Sampler B recovers about 0.06 seconds;
the audio tail recovers about 0.45 seconds off-chain. The overall move cannot be
summarized by the cone delta alone. Aux status has about 13 calls/chunk versus
legacy's five and consumes .153 versus .067 seconds concurrently, reflecting
changed client polling timing as well as the same storage-walk overhead.

Source establishes the transfers that change: upsampler residency/load target
**xpu:0 → xpu:2**, and audio VAE/vocoder **xpu:3 → xpu:2**. The upsampler moves
its input to that chosen device, then returns to the runtime intermediate device
(the default is CPU) before B preparation/sampling. This is not evidence of a
measured direct xpu:0→xpu:2 peer copy. Aux mode also adds before/after xpu:2
synchronization/free-memory guards around upsampling and audio; legacy skips
those guards. Video VAE, cone and frame encoders stay on xpu:3. The timed cone
includes native VAE loading/copy/decode/synchronization work but has no individual
copy timestamps. **No recorded card-hop duration explains its +0.10 seconds.**
Its cause may involve changed overlap/allocator scheduling; assigning that time
to a specific hop would exceed the evidence. Keep legacy placement for the
first 126 comparison; aux is a separate matched arm when memory requires it.

## Packet 126 expectation and open gate

Packet 126's proposed background bundle addresses both measured CPU paths.
Storage refresh runs off the request path with a .25-second periodic cadence,
a maximum one-second sample age, and required after-request/after-preview
refresh epochs before the next admission. Admission also retains 256 MiB of
additional allowance headroom for in-flight writes. Every request still checks
the filesystem reserve; stale samples, worker errors and incomplete required
epochs fail closed. Request mode preserves the parent's synchronous path.
The new admission/refresh timing evidence must establish the actual recovery;
these policy bounds alone do not prove a faster native stream.

For repeated plan checks, the proposed full-tree typed marshal-v2 comparison
uses the initial canonically verified plan as its baseline. It traverses the
current tree on each check; any binary difference runs the original canonical
JSON/SHA256 gate. This is not a cached hash of a mutable object. The
[CPU timing artifact](../data/resume-20261008/continuation126-cpu-timing.json)
records the final implementation's benchmark; that diagnostic isolates Python
work and is not a measured model period. The parent request-mode path remains
unchanged. Atomic preview publication was already asynchronous and stays intact,
including exact hash, original HTTP paths and failure/back-pressure behavior.

Packet 125 remains the sealed parent. Hold its GC interval at the off setting
(10 seconds), serial display and legacy auxiliaries when isolating 126's
background bundle; evaluate its 60-second lever separately. Preserve the same
byte/quality gates, geometry, precision and snapshots.

The planning target is **5.61–5.64 s per six seconds of video
(0.935–0.940 s/s)** on legacy, with an initial forecast envelope of
**5.55–5.75 s (0.925–0.958 s/s)**. This is a forecast, not CPU verification of
native period: it assumes the off-request storage checks and cheaper full-tree
plan checks remove most of the measured extra Python work without moving the
bottleneck to refresh readiness. Plan growth, in-flight storage races, native
session variation and asynchronous worker scheduling remain relevant.

Native unchanged-output checks, new scan/lock/refresh timing, matched
fixed-window cadence on two fresh coordinator-operated servers, and any
residual timing cost remain open. The saved receipts cannot establish a further
150-ms auxiliary card-hop penalty. No historical receipt was edited and no GPU
experiment was performed to fill those gaps.
