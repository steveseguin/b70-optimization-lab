# Packet 128: the alternating receipt stall is timed maintenance

2026-10-10. CPU-only saved-file analysis; no runtime import, GPU work, model server, endpoint, port, launch, check-only, unit, signal, device, host-setting change, existing-run write or client-tree write. Commands ran at nice 19 with OMP_NUM_THREADS=2 using `/home/steve/.venvs/ltx25-baseline/bin/python -B`.

**The recorded blocker is full Python garbage collection followed by allocator housekeeping on the prompt worker. The hypothesized display/preview two-chunk beat is contradicted by the timestamps.** Every one of packet 126's **119 handoffs over 150 ms** overlaps the recorded maintenance pair; none overlaps the previous display, decode tail or preview. The pair takes a median **0.308 s**, including **0.252 s in `gc.collect()`** and **0.056 s in `soft_empty_cache()`**. The receipt route constructs its response a median **4.4 ms after that pair ends**. GC can hold the process GIL even though the aiohttp loop runs on another thread. The timings establish the pair as the blocker; they do not separately prove how much of the allocator call blocks the GIL versus a native/runtime lock.

The coordinator's initial GC60 aggregate result remains a real observation. It does **not** establish that GC60 left the receipt stall unchanged: packet 125's direct timings show median handoffs **48/46 ms** on the two parities, and all its 19 long handoffs overlap its less frequent maintenance. The earlier budget note already contains this correction. Fresh text every fourth chunk and other costs kept the aggregate period near its prior value. Replacing the encoder or removing hashes would target work outside the stalled interval and change the experiment without evidence.

## Reproducible evidence and scope

[Analyzer](../data/resume-20261008/continuation128-overlap-analysis.py), [frozen evidence](../data/resume-20261008/continuation128-overlap-evidence.json), and [complete per-chunk overlap table](../data/resume-20261008/continuation128-overlap-table.csv) cover **1,476 interior intervals across eight sessions**, retaining raw nanosecond-derived intervals and hashes of all 4,707 inputs (4,700 receipt/client files and seven source files). The six structural checks pass; these are analysis checks, not packet runtime tests or native byte gates. The only development failure was an initial summary trying to sort an absent maintenance-end value; filtering missing observations fixed it, after which the full census passed twice.

```sh
nice -n 19 env OMP_NUM_THREADS=2 /home/steve/.venvs/ltx25-baseline/bin/python -B experiments/ltx25-b70/data/resume-20261008/continuation128-overlap-analysis.py
```

Source sequence owns the period from its submit to its successor's submit. Destination-sequence parity is reversed. Handoff means `commit_written → first_served`; `first_served` is response construction, not network delivery. The prep window in the overlap table is **next submit → next sampler A**, while the current prompt's submit→A is stored separately. Interior rows begin at 10 and require both neighboring receipts and complete decode/preview records. We retain every eligible row, not only slow examples. Older packets did not record the maintenance pair, so zero measured overlap there means unavailable instrumentation, not no collection.

The initial packet 126 budget captured 128 interior rows. This later stopped-session census captures **240, source sequences 10–249**. Its even-source median is 5.926 s and odd-source median 5.559 s; this does not overwrite the earlier 6.103/5.568 snapshot. The cadence slips late: 104 even and 15 odd rows have long handoffs. The source event identity, not parity alone, is the causal classifier.

| Session | Rows | Handoffs >150 ms | With measured maintenance | With predecessor display / tail / preview | Even / odd handoff median s |
|---|---:|---:|---:|---:|---:|
| s121-live01 | 409 | 207 | not instrumented | 0 / 0 / 0 | 0.313 / 0.032 |
| s121-live02 | 305 | 154 | not instrumented | 0 / 0 / 0 | 0.307 / 0.033 |
| s123b-legacy-live01 | 50 | 25 | not instrumented | 0 / 0 / 0 | 0.340 / 0.035 |
| s123b-live01 | 30 | 15 | not instrumented | 0 / 0 / 0 | 0.323 / 0.027 |
| s123b-live02 | 202 | 101 | not instrumented | 0 / 0 / 0 | 0.342 / 0.047 |
| s124-live01 | 34 | 17 | not instrumented | 0 / 0 / 0 | 0.384 / 0.042 |
| s125-live01 | 206 | 19 | 19 | 0 / 0 / 0 | 0.048 / 0.046 |
| s126-live01 | 240 | 119 | 119 | 0 / 0 / 0 | 0.321 / 0.041 |

## Consecutive per-chunk overlap table

All endpoints below are seconds relative to the source chunk's submit. Display, tail and preview belong to the **predecessor**; the A-precompute row belongs to the **source** and supplies the next request. Twelve consecutive rows show both source parities and fresh-text rows. The linked CSV is the complete per-chunk table for all 1,476 rows; JSON retains every interval endpoint and the overlapping maintenance event. No display, tail or preview overlaps any shown handoff. For packet 126, predecessor preview always finishes **at least 0.228 s before commit**, across all 240 rows.

| Source seq | Receipt commit→served | Previous display | Previous tail | Previous preview | Own successor A prep | Maintenance overlap s | GC portion s | Next submit→A |
|---:|---|---|---|---|---|---:|---:|---|
| 10 | 5.535–5.842 | 0.711–3.588 | 3.588–4.401 | 4.473–5.151 | 5.540–6.099 | 0.299 | 0.244 | 5.852–6.352 |
| 11 | 5.492–5.497 | 0.667–3.537 | 3.537–4.352 | 4.428–5.107 | 5.495–5.814 | 0.000 | 0.000 | 5.506–6.455 |
| 12 | 5.958–6.287 | 1.118–3.940 | 3.940–4.789 | 4.854–5.559 | 5.961–6.552 | 0.323 | 0.267 | 6.305–6.814 |
| 13 | 5.542–5.595 | 0.675–3.562 | 3.562–4.413 | 4.484–5.125 | 5.544–5.835 | 0.000 | 0.000 | 5.660–6.114 |
| 14 | 5.463–5.784 | 0.609–3.493 | 3.493–4.352 | 4.410–5.043 | 5.465–6.038 | 0.314 | 0.258 | 5.802–6.306 |
| 15 | 5.480–5.509 | 0.674–3.542 | 3.542–4.363 | 4.432–5.079 | 5.484–5.785 | 0.000 | 0.000 | 5.534–6.449 |
| 16 | 5.870–6.172 | 1.083–3.878 | 3.878–4.776 | 4.841–5.451 | 5.872–6.448 | 0.297 | 0.242 | 6.185–6.709 |
| 17 | 5.477–5.536 | 0.686–3.556 | 3.556–4.371 | 4.436–5.112 | 5.481–5.798 | 0.000 | 0.000 | 5.598–6.043 |
| 18 | 5.467–5.785 | 0.614–3.493 | 3.493–4.314 | 4.381–5.045 | 5.469–6.052 | 0.313 | 0.257 | 5.797–6.320 |
| 19 | 5.526–5.557 | 0.685–3.569 | 3.569–4.399 | 4.472–5.173 | 5.530–5.921 | 0.000 | 0.000 | 5.582–6.746 |
| 20 | 6.450–6.762 | 1.338–4.404 | 4.404–5.245 | 5.304–5.966 | 6.456–7.000 | 0.303 | 0.249 | 6.773–7.259 |
| 21 | 5.462–5.518 | 0.654–3.521 | 3.521–4.344 | 4.406–5.051 | 5.465–5.763 | 0.000 | 0.000 | 5.580–6.019 |

The source-10 maintenance starts 1.6 ms after executor exit. It occupies 0.244 s collecting and 0.055 s emptying cached allocations; service follows 1.8 ms after the pair ends. Its own A preparation spans 5.540–6.099 s, overlapping the maintenance. Moving cleanup merely after admission can therefore move the delay into prep rather than remove it. The next chunk's display begins only after its sampler-A go signal; the current source's display, tail and preview overlap **zero** next-prep windows in all eight sessions. This follows the existing `sampler-a` scheduling and is visible in the saved event marks.

Packet 126's next request snapshot overlaps its next-prep window by median **73.0 ms on both source parities**. Snapshots remain real cost, but neither this symmetry nor their later timing explains the alternating receipt handoff. The packet 127 immutable-signature digest memo is a separate lever; it must not be credited here as measured saving.

## Why the beat is two chunks

The parent's prompt worker tests its elapsed **10-second** maintenance interval after prompt execution. One normal period is about 5.6–5.9 seconds, so the due condition usually fires after two prompts. It then calls full collection synchronously. That naturally creates a roughly two-prompt beat, with phase slips when a prompt or gap is long. A 60-second interval produces roughly one maintenance event per ten prompts instead. The measured source-126 maintenance events are exact timestamp evidence; the older 121/123/124 pattern is consistent but uninstrumented.

A proposed beat between about 4.4 seconds of decode occupancy and a 5.7-second submit period is not supported: decode and preview finish before the relevant handoff, there is no alternating FIFO queue delay, and moving display to the separate packet 124 worker leaves the long handoff. The apparent longer A-precompute bracket shares the same GC pause rather than proving that preparation is independently blocking the route.

## Candidate weights and source audit

| Candidate | Evidence weight | Finding |
|---|---|---|
| Full manual GC + allocator pair | Identified blocker | 119/119 long 126 handoffs and 19/19 long 125 handoffs overlap it. Median 126 pair 0.308 s; service follows within 4.4 ms median. Full GC is 0.252 s of it. |
| Preview encode/MP4 hash | Contradicted for this stall | Zero overlapping handoffs; minimum 126 preview-to-commit slack 0.228 s. Already a separate bounded thread. `CreateVideo` ultimately calls in-process PyAV `av.open`; it is not an ffmpeg child. No claim about every PyAV operation releasing the GIL is needed to exclude this timing window. |
| Decode-tail tensor hash/receipt writes | Contradicted for this stall | Zero tail overlap. Native audio decode and hash/bookkeeping complete before preview begins. Python serialization can hold the GIL, but these records are outside the stalled windows. |
| Receipt-route JSON serialization | Absent on this path | The parent reads the stored regular-file bytes and returns `web.Response(body=raw, content_type='application/json')`; it does not parse or serialize the receipt JSON. The route already serves pre-serialized bytes. |
| Background own-writes storage scan | Weak, uninstrumented residual | No scan start/end timestamps were recorded, so small coincident contention cannot be excluded. The periodic handoff predates 126, and every instrumented long handoff has the maintenance explanation. |
| Next four-card request snapshot | Contradicted as receipt-window cause | It starts after next admission; median wrapper overlap in next prep is equal by parity. Keep all freshness and byte gates. |
| Fresh text | Strong independent prep cost | Source modulo-four class 0 has ~0.43 s more submit→A work; this persists when the receipt gap disappears. Do not pool it into a claim that all even chunks should match reused-text chunks. |

Audited sealed parent files: `source/main.py`, `scripts/maintenance125.py`, `scripts/integration.py`, `scripts/stream_preview.py`, `scripts/stream_decode.py`, `scripts/run_storage.py`, and `comfy_api/latest/_input_impl/video_types.py`. Their exact hashes are in the evidence input map. Full GC is process-local: moving `gc.collect()` to another thread still competes for the same GIL; moving it to another process cannot collect this server's object graph. A preview worker process is not a fix for the observed blocker.

## Period forecast and limits

Removing only each measured handoff's excess above 40 ms from the 240 saved 126 periods yields a **counterfactual median 5.5666 s per 6.0 seconds of new video = 0.9278 s/s**. This is an arithmetic budget estimate, not a benchmark or assurance that rescheduling removes all that wall time. It supports the requested ~5.57/~0.93 target for the **overall median and reused-text population**. It does not support promising both pooled parities will be identical.

Subtracting each row's directly overlapping maintenance, while leaving every other measured interval intact, gives source modulo-four medians **5.988 / 5.551 / 5.541 / 5.527 s**. Fresh text is still required, so an exact solution should retain that class's extra cost. Packet 125 demonstrates that less frequent full cleanup removes the regular handoff while preserving the calls, but it also demonstrates why a neutral aggregate alone cannot diagnose the mechanism.

At 169 frames, each continuation contributes 168/24 = **7.0 s**. If a ten-second full cleanup still hits about every second handoff, removing a 0.28–0.31 s excess from affected rows is worth roughly **0.14–0.16 s/chunk on the mean**, or **0.020–0.023 s/s**. A median cannot be derived by subtracting this mean opportunity from another session's median. The prior parallel-display forecast remains **6.20–6.65 s / 7.0 = 0.886–0.950 s/s** until coordinator measurements establish the combined setup. GC60 greatly reduces the available gain; no second recurring 0.3 s penalty remains established under that option.

Packet 128 selects a launch option for **bounded idle deferral**, with the off form preserving packet 127. Under GC10, a due periodic collection waits for a **250 ms quiet admission window**, with a **60-second maximum age since the last collection plus completion of any already executing prompt**. The native pair remains on the prompt thread; both callbacks and automatic GC remain unchanged. Explicit free/unload requests bypass the deferral. Every deferral and forced cleanup must be recorded. GC60 has no new forecast gain from this policy.

The selected policy's first 145-frame forecast is conservatively **5.50–5.75 s per 6.0 s = 0.917–0.958 s/s**, working center **5.60 s = 0.933 s/s**. Reused-text chunks target roughly 5.57 s, while fresh-text class 0 remains slower. This is a forecast, not a native result. A 250 ms grace may expire before the next submit when safety/admission work is expensive; cleanup can still hold the GIL at that point. The maximum-age cleanup also remains visible roughly once per minute under a continuous stream. Merely waiting until next admission would instead shift the same pause into text/prep. Native period and memory checks decide whether the chosen bounded quiet window creates a net win.

No CPU timing test can prove a sub-50-ms response while an arbitrary other thread continuously owns the GIL; a meaningful timing test must exercise the selected scheduling contract and synthetic work under its actual admission/cleanup rules. No hash, serializer, preview encoder or model arithmetic changes solely on this evidence.

Open: native byte and memory gates, two fresh-server matched speed measurements, the combined 169-frame configuration, exact own-writes scan timings, and any residual automatic-GC pauses remain outside this CPU-only analysis. The packet design records the final selected policy and CPU gate counts.

Coordinator update during preparation (CURRENT,2026-10-10 09:15UTC): the127
169parallel/display2 qualification refused its memory guard,8,465,399,808bytes
free below6.5GiB transient+2GiB floor. The169 projection above is therefore
conditional on recovering headroom;128 scheduling changes do not clear this
blocker or authorize lowering the reserve.145 remains the first proposed arm.
