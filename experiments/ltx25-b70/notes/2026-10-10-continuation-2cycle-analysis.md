# Continuation packet 125: the two-cycle is the post-prompt housekeeping window

The saved timestamps locate the extra wait **after the receipt commits and the
prompt executor exits, before the HTTP receipt is first served**. They do not
show an alternating decode FIFO wait, a missing A precompute, or a long
request-before snapshot. The two-cycle is already present at 121 frames.

The sealed ComfyUI prompt worker provides the matching mechanism: after a prompt
it runs `gc.collect()` and `soft_empty_cache()` whenever more than ten seconds
have elapsed since the previous collection. Two streaming chunks take just over
ten seconds. Collection stops Python threads while it scans objects; the XPU
cache helper also synchronizes and empties the allocator cache. This work runs
outside the recorded executor interval, beside the decoder's A precompute and
the server's attempt to serve the completed receipt. This is a strong
source-and-timestamp attribution, **not a direct measurement of individual GC,
GIL or allocator calls**: the historical packets did not time those calls.

## Frozen inputs and reproduction

[Analysis script](../data/resume-20261008/continuation125-evidence-analysis.py),
[frozen per-chunk output and source hashes](../data/resume-20261008/continuation125-evidence.json).
The script reads regular JSON/JSONL evidence and the matching sealed source files only;
it imports no runtime and opens no endpoint or device. Run it with:

```sh
OMP_NUM_THREADS=2 /home/steve/.venvs/ltx25-baseline/bin/python -B experiments/ltx25-b70/data/resume-20261008/continuation125-evidence-analysis.py
```

The JSON records the capture time and SHA256/byte length of each input. Its
client manifests are snapshots; rerunning against a growing session can produce
more rows. Source session identities match the receipt identities, rather than
assuming a filename's device suffix describes its actual placement. Only
completed manifest rows are included. Interior rows start at sequence 10 and
require both neighbours; this excludes startup and the final bounded go wait.
`s123b-legacy-live01/manifest.jsonl` did not exist at capture, so its requested
contrast remains open. `s123b-live02` had 213 completed manifest rows at capture,
which is later than the coordinator's 190-row observation.

**Parity convention:** the coordinator's fast even/slow odd period is the
interval ending at that sequence (`submit[n]-submit[n-1]`). A chunk's own
pre-sampler work belongs to the interval beginning at that sequence. These
indices differ by one; joining an ending period to that row's own buckets would
misattribute the cause. Both definitions are saved. Tables below use the
unambiguous interval beginning at the source sequence.

## Session census

| Session | Frames | Interior intervals | Even→odd period | Odd→even period | Even-source commit→serve | Odd-source commit→serve |
|---|---:|---:|---:|---:|---:|---:|
| s121-live01 | 145 | 409 | 5.945 | 5.526 | 0.313 | 0.032 |
| s121-live02 | 145 | 305 | 5.910 | 5.547 | 0.307 | 0.033 |
| s123b-live01 | 145 | 30 | 6.062 | 5.641 | 0.323 | 0.027 |
| s123b-live02 | 145 | 202 | 6.144 | 5.706 | 0.342 | 0.047 |
| s118b-live01 | 121 | 90 | 5.502 | 5.072 | 0.306 | 0.027 |
| s118b-live02 | 121 | 260 | 5.667 | 5.125 | 0.312 | 0.021 |
| s118b-live03 | 121 | 156 | 5.627 | 5.126 | 0.309 | 0.029 |
| s120-live01 | 121 | 124 | 5.246 | 4.906 | 0.341 | 0.054 |

All times are seconds. These are descriptive distributions, not subtracted
bucket medians. The causal examples below use original nanosecond endpoints.

## Consecutive-chunk timelines

Each column has its own origin: that chunk's `timing_ns.submit`. A negative
number means the predecessor's work began before this submit. The decode rows
refer to predecessor `n-1`, whose A/B precomputes feed current chunk `n`; its
full display and audio tail run while current chunk `n` samples. The preview
rows belong to the **separate preview writer**, not the decode thread.
The current chunk's own A precompute at the bottom feeds `n+1` and overlaps the
post-receipt handoff under examination.

Intervals are rounded to milliseconds here; exact offsets and integer origins
are in the JSON. Anchor-read bounds include node bookkeeping and are not a
separate measured file-read duration. The text window is the interval between
A-condition completion and the stream-text node: fresh text work appears there
when the prompt changes; the reused-text path is almost empty.

### s121-live01: 145 frames

| Event / worker | seq 10 | seq 11 | seq 12 | seq 13 |
|---|---:|---:|---:|---:|
| Prior A prep / decode | -0.049–0.253 | -0.321–0.218 | -0.107–0.179 | -0.325–0.238 |
| Prior B prep / decode | 0.538–0.694 | 0.481–0.633 | 0.849–1.012 | 0.503–0.663 |
| Prior display / decode | 0.694–3.402 | 0.633–3.346 | 1.012–3.742 | 0.663–3.369 |
| Prior audio + hash + record / decode | 3.402–4.328 | 3.346–4.286 | 3.742–4.691 | 3.369–4.292 |
| Prior preview encode / preview | 4.392–5.045 | 4.358–5.040 | 4.756–5.395 | 4.353–4.952 |
| Request-before outer / prompt | 0.023–0.162 | 0.043–0.124 | 0.023–0.096 | 0.047–0.129 |
| Anchor-read node bounds / prompt | 0.165–0.274 | 0.126–0.244 | 0.100–0.203 | 0.132–0.264 |
| A lookup / prompt | 0.274–0.282 | 0.244–0.252 | 0.203–0.214 | 0.264–0.275 |
| A condition tail / prompt | 0.282–0.530 | 0.252–0.474 | 0.214–0.453 | 0.275–0.494 |
| Text window / prompt | 0.530–0.531 | 0.474–0.475 | 0.453–0.842 | 0.494–0.495 |
| Sampler A start / prompt | 0.538 | 0.481 | 0.849 | 0.502 |
| Receipt staged / prompt | 5.430 | 5.374 | 5.783 | 5.395 |
| Executor exit / prompt | 5.459 | 5.398 | 5.808 | 5.413 |
| Receipt first served / HTTP | 5.758 | 5.442 | 6.107 | 5.466 |
| Next submit / HTTP | 5.780 | 5.506 | 6.133 | 5.525 |
| Current A prep for successor / decode | 5.459–5.998 | 5.398–5.685 | 5.808–6.371 | 5.414–5.707 |
| Request-before inner snapshot | 0.100–0.162 | 0.061–0.124 | 0.038–0.096 | 0.065–0.129 |
| Origin, Unix nanoseconds | 1791605904386939985 | 1791605910167258090 | 1791605915672780767 | 1791605921806096157 |

### s123b-live02: 145 frames

| Event / worker | seq 10 | seq 11 | seq 12 | seq 13 |
|---|---:|---:|---:|---:|
| Prior A prep / decode | -0.037–0.326 | -0.339–0.281 | -0.042–0.321 | -0.336–0.255 |
| Prior B prep / decode | 0.629–0.807 | 0.570–0.730 | 1.010–1.159 | 0.534–0.686 |
| Prior display / decode | 0.807–3.674 | 0.730–3.477 | 1.168–4.102 | 0.686–3.465 |
| Prior audio + hash + record / decode | 3.674–4.088 | 3.477–3.880 | 4.102–4.524 | 3.465–3.876 |
| Prior preview encode / preview | 4.155–4.878 | 3.947–4.698 | 4.592–5.320 | 3.950–4.629 |
| Request-before outer / prompt | 0.076–0.238 | 0.084–0.180 | 0.076–0.227 | 0.074–0.165 |
| Anchor-read node bounds / prompt | 0.240–0.351 | 0.184–0.303 | 0.229–0.343 | 0.168–0.281 |
| A lookup / prompt | 0.351–0.363 | 0.303–0.316 | 0.343–0.354 | 0.281–0.291 |
| A condition tail / prompt | 0.363–0.621 | 0.316–0.562 | 0.354–0.616 | 0.291–0.526 |
| Text window / prompt | 0.621–0.622 | 0.562–0.563 | 0.616–1.001 | 0.526–0.527 |
| Sampler A start / prompt | 0.629 | 0.570 | 1.009 | 0.533 |
| Receipt staged / prompt | 5.728 | 5.607 | 6.146 | 5.598 |
| Executor exit / prompt | 5.777 | 5.661 | 6.188 | 5.649 |
| Receipt first served / HTTP | 6.097 | 5.678 | 6.503 | 5.668 |
| Next submit / HTTP | 6.116 | 5.704 | 6.524 | 5.686 |
| Current A prep for successor / decode | 5.777–6.397 | 5.662–6.025 | 6.188–6.779 | 5.649–6.026 |
| Request-before inner snapshot | 0.164–0.238 | 0.109–0.180 | 0.154–0.227 | 0.096–0.165 |
| Origin, Unix nanoseconds | 1791614482358690370 | 1791614488475183004 | 1791614494179235508 | 1791614500703201613 |

### s120-live01: 121 frames

| Event / worker | seq 10 | seq 11 | seq 12 | seq 13 |
|---|---:|---:|---:|---:|
| Prior A prep / decode | -0.054–0.261 | -0.359–0.230 | -0.133–0.192 | -0.412–0.217 |
| Prior B prep / decode | 0.530–0.690 | 0.491–0.659 | 0.853–1.017 | 0.490–0.657 |
| Prior display / decode | 0.690–3.399 | 0.660–3.355 | 1.017–3.706 | 0.657–3.360 |
| Prior audio + hash + record / decode | 3.399–3.817 | 3.355–3.761 | 3.706–4.102 | 3.360–3.779 |
| Prior preview encode / preview | 3.873–4.433 | 3.823–4.392 | 4.161–4.763 | 3.835–4.438 |
| Request-before outer / prompt | 0.101–0.177 | 0.052–0.132 | 0.017–0.095 | 0.021–0.123 |
| Anchor-read node bounds / prompt | 0.180–0.281 | 0.136–0.254 | 0.098–0.216 | 0.126–0.241 |
| A lookup / prompt | 0.281–0.287 | 0.254–0.261 | 0.216–0.225 | 0.241–0.247 |
| A condition tail / prompt | 0.287–0.525 | 0.261–0.483 | 0.225–0.459 | 0.247–0.485 |
| Text window / prompt | 0.525–0.525 | 0.483–0.484 | 0.459–0.847 | 0.485–0.486 |
| Sampler A start / prompt | 0.530 | 0.491 | 0.853 | 0.490 |
| Receipt staged / prompt | 4.851 | 4.815 | 5.158 | 4.829 |
| Executor exit / prompt | 4.869 | 4.832 | 5.177 | 4.845 |
| Receipt first served / HTTP | 5.203 | 4.880 | 5.564 | 4.896 |
| Next submit / HTTP | 5.228 | 4.964 | 5.589 | 4.980 |
| Current A prep for successor / decode | 4.869–5.458 | 4.831–5.157 | 5.176–5.806 | 4.845–5.155 |
| Request-before inner snapshot | 0.117–0.177 | 0.065–0.132 | 0.030–0.095 | 0.062–0.123 |
| Origin, Unix nanoseconds | 1791604377111370277 | 1791604382339642640 | 1791604387303889610 | 1791604392892450830 |

For a clean unchanged-text pair at 145, legacy seq 10's executor exits at
+5.458891 and its receipt is first served at +5.758408: **299.518 ms** later.
The preceding preview finished at +5.045347, 384.651 ms before this receipt
was staged. The next chunk's A precompute starts at +5.459007, almost exactly
when the executor exits, and finishes +5.998115. Seq 11 instead has a
44.440 ms executor-exit-to-first-served gap. Its preceding preview also finished
before its receipt. The corresponding 121-frame seq 10 gap is 334.165 ms;
seq 11's is 48.670 ms. No 145-only display-window threshold is needed.

## What is, and is not, waiting

* **Request-before snapshots:** in the two 145 legacy sessions the inner
  four-card snapshot median is about 65 ms on both parities; the outer
  synchronization-plus-snapshot wrapper is about 85–89 ms. In the tables,
  predecessor display has not started yet when request-before runs. Thus the
  proposed request-before barrier waiting behind that display does not fit
  these records. Per-card synchronization timestamps were not saved, so a
  particular XPU cannot be named as the residual few-millisecond wait.
* **A precompute availability:** every analyzed A conditioning source in all
  eight sessions is `precomputed`; none falls back to a native encode.
  The measured event wait is microseconds, and the precompute is already
  finished before the condition lookup in the illustrated pairs. A consume,
  A-before and A-after remain in the approximately 55–65 ms range.
* **Decode FIFO:** 145's median queue wait is tens of microseconds on both
  parities. 118b has about 36–47 ms FIFO wait, but it is present on both
  parities. 120's queue is again effectively empty while its two-cycle remains.
* **Preview:** encoding already has its own bounded worker. In the legacy 145
  sessions its predecessor file finishes about 0.35–0.37 seconds before the
  current receipt; aux placement gives about 0.86–0.95 seconds of lead.
  It does not hold the next receipt observation in these examples.
* **A precompute wall time:** legacy even-source chunks cost about
  0.55–0.56 seconds versus 0.32 odd-source, but their actual native-call
  bracket is **shorter**, 0.135 versus 0.19–0.20 seconds. The extra wall time
  lies outside that bracket. It coincides with the post-executor handoff
  gap. Splitting that remainder into Python GC, source checks, locks and
  device synchronization needs new instrumentation.
* **Go wait:** it ends at the successor sampler-A event. Delayed receipt
  delivery delays admission and therefore that event. It is downstream of
  the handoff problem, not an independent three-second display timeout.

There is also an independent **four-chunk text cadence**. The schedule changes
prompt at `seq % 4 == 0`; those rows do real text work. For legacy session 1,
source classes 0/1/2/3 have submit-to-sampler-A medians
0.944/0.502/0.532/0.507 seconds. Even-source class 2 has no text change, yet
its commit-to-first-served median is 0.313 seconds, the same as class 0;
classes 1/3 have 0.034/0.031. Consequently, the pooled even pre-sampler median
must not be interpreted as a pure two-cycle penalty, and a correct fix cannot
make fresh-text chunks cost exactly the same as text-reuse chunks.

## Source mechanism and the ten-second timestamp check

Sealed packet 124 `source/main.py` sets `gc_collect_interval = 10.0` in
`prompt_worker`. After `e.execute`, queue completion and logging, it tests
`current_time - last_gc_collect > gc_collect_interval`, then calls
`gc.collect()` followed by `comfy.model_management.soft_empty_cache()`.
The XPU implementation of that helper calls `torch.xpu.synchronize()` and
`torch.xpu.empty_cache()`. These are application allocator housekeeping calls;
this CPU analysis executed none of them. The source hashes are included in
the evidence JSON. Packets 118b, 120, 121, 123b and 124 have exactly the same
`source/main.py` SHA256: `d8cdcb6c4158766069722c6beae524b023ae9dfe720cbd5af8264d1497e45756`.

A deterministic interpretation check of the already-saved timeline is possible
without inventing GC timestamps: seed the first handoff longer than 150 ms,
use each executor-exit timestamp as the post-prompt timer proxy, and thereafter
predict collection exactly when more than ten seconds have elapsed since the
previous predicted collection. Compare against observed commit-to-first-served
longer than 150 ms. This predicts the observed phase changes as well as the
usual parity:

| Session | Matching classifications | Exceptions |
|---|---:|---|
| s121-live01 | 407/408 | 155 |
| s121-live02 | 297/304 | 308, 309, 310, 311, 312, 313, 314 |
| s123b-live01 | 29/29 | none |
| s123b-live02 | 201/201 | none |
| s118b-live01 | 87/89 | 44, 70 |
| s118b-live02 | 258/259 | 202 |
| s118b-live03 | 155/155 | none |
| s120-live01 | 104/123 | 103, 104, 105, 106, 110, 111, 112, 113, 123, 124, 125, 126, 127, 128, 129, 130, 131, 132, 133 |

The legacy session's exception at 155 lies at the recorded preview-route
failure/client pause. The final session-2 rows are near its stopped/resumed
or throttled tail. 120 sits close to the ten-second boundary; using
executor-exit rather than the unsaved actual housekeeping-check timestamp can
shift the model's later phase. These are limitations, not discarded data.
The 150 ms threshold distinguishes the separated observed handoff populations;
it is a classification aid, not a measured collection duration. No timing
parameter was fitted to maximize matches.

## Packet 125 lever and forecast boundary

Reordering A before display or moving preview to another thread would duplicate
the existing parent schedule. Packet 125 instead exposes the existing prompt
worker's collection interval as `LTX_GC_INTERVAL_SECONDS`: **10 is the parent
control; 60 is the first candidate**. It retains the original collection call,
cache-release call and their order, leaves Python's automatic collector unchanged,
and retains every memory floor and halt check. The candidate is scoped to
145 frames, serial display on xpu:3, with legacy or aux placement; the first
comparison uses legacy placement. It does not move collection into a GPU sampler
window, where a GIL pause or allocator synchronization could disturb submissions.

At a roughly 5.55-second period, the 60-second interval leaves about one periodic
housekeeping chunk per eleven chunks instead of every second chunk. It breaks
the persistent two-cycle rather than eliminating housekeeping. New records time
the original GC and cache-release calls separately and expose them in the next
receipt and status. The exact mechanism and CPU gates are recorded in the packet
125 design and contract. Native allocation growth between collections must still
pass the existing floors; an interval change is not permission to relax them.

With the observed regular handoff pause removed from most chunks, the steady
145 legacy median is forecast at **5.45–5.75 s**, or **0.908–0.958 s/s** for six
seconds of new video. The midpoint target 5.55 s is **0.925 s/s**; a mean near
5.58 s is an optimistic forecast that still includes a residual maintenance
chunk. An adverse 5.75–6.10 s outcome remains possible if freed allocator storage,
CPU scheduling or the new phase dominates. These are predictions, not benchmark
results. Fresh-prompt chunks retain their approximately 0.4-second text work, so
“every chunk exactly 5.55 seconds” is not a realistic byte-preserving gate.
The native test must show loss of the periodic two-chunk handoff penalty within
matching text classes, not merely a lower pooled median or a parity phase flip.

Three-chain identity, every cone==display comparison, each preview SHA256,
unchanged conditioning hashes and memory floors remain mandatory. All recorded
cone/display comparisons in the frozen input sessions are true; this CPU task
did not rerun the native identity oracle. Native timings of GC/cache work, memory between the less-frequent collections,
the mean period and the legacy-123b session remain open.

## CPU analysis verification

Six structural checks passed: Python AST parsing, eight captured sessions,
1,576 interior rows, every A source marked precomputed, every recorded
cone/display comparison true, and four retained consecutive detailed timelines
per session. These are checks of the frozen analysis artifact, **not six native
correctness tests**. Their names and outcomes are embedded in the evidence JSON.
