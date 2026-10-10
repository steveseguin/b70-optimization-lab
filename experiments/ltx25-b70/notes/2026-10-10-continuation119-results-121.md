# Packet 119 at 121 frames: the remaining loss is safety-check work

2026-10-10. CPU analysis only. All live files and existing run directories were
read-only. No device, endpoint, service, launcher or host setting was accessed.
The coordinator owns the live LTX server.

Packet 119 is exact in the observed sample, but slower than 118b dg0. The owner's
whole-session summary is 5.421 versus 5.279 seconds per chunk, a loss of 0.142 s.
The faster cone works. Eager display also restores the short upsampler interval.
The remaining increase in B preparation and receipt time is chiefly the extra
safety inspection triggered by low xpu:3 headroom, not a slower upsampler or a
synchronous anchor read in the receipt HTTP handler.

[Evidence JSON](../data/resume-20261008/continuation120-evidence.json) and the
[CPU analyzer](../recovery/20261010-continuation120-stream/analyze_evidence_120.py)
retain hashes, observed read times, exact source paths, every sampled chunk's
relative timeline, snapshot parts, memory readings and qualification identities.
The analyzer reads only regular evidence files and one safetensors header. It
imports no model runtime. It emits JSON to stdout.

## Sample and identity

The primary comparison uses the same stream sequences **10–35**, 26 complete
submit-to-next-submit intervals in each configuration. Outputs compare sequences
**0–36**, 37 chunks. This paired window differs from the owner's pooled summary;
its medians must not be silently substituted for the whole sessions. The dg0
session's manifest contains 271 rows. The 119 session was still growing while
read; hashes identify the observed bytes, not an immutable final log.

| Paired median, seconds | 118b dg0, eager cone/display | 118b dg1, sampler-a graph display | 119 dg1, eager display + read-ahead |
|---|---:|---:|---:|
| Submit to next submit | 5.302675 | 5.559306 | 5.413709 |
| Cone on chain | 0.981650 | 0.765218 | 0.790564 |
| Upsample + B preparation | 0.287656 | 0.790991 | 0.431339 |
| Upsampler start → condition-B start | 0.032609 | 0.505792 | 0.032480 |
| Condition-B node | 0.251033 | 0.282811 | 0.398279 |
| Anchor ready → receipt staged | 0.097847 | 0.095543 | 0.176899 |
| Text + A preparation | 0.525343 | 0.485451 | 0.496856 |
| Full display decode | 2.701439 | 2.116919 | 2.789599 |
| Anchor ready → sampler-A go mark | 0.951932 | 0.762712 | 0.852121 |
| Actual bounded go wait only | 0.270406 | 0.243227 | 0.259101 |

The client's displayed “go-wait” bucket includes the path from anchor readiness
to go, including receipt commit and A precompute. It is not the decode worker's
actual wait duration. Medians of different buckets do not add to the median
whole period.

119 qualification verdict starts `9dac6eb450ba`; its full identity is in the
JSON. Against both 118b sessions, all 37 image hashes and all 37 waveform hashes
match. Every sampled cone/display last-frame equality is true. These observations
preserve 119's exactness evidence; they do not qualify a new xpu:2 decoder.

## Receipt attribution: the suspected read is later

The exact source order is:

1. Decode worker writes/publishes the cone anchor and signals `anchor_ready`.
2. Prompt execution finishes the request, including the `request-after` safety
   snapshot. It stamps `receipt_staged`.
3. `SessionAuthority.finish()` writes the receipt exclusively, fsyncs it, updates
   chain state and notifies `committed` waiters.
4. The decode worker wakes from `wait_committed()`, then synchronously calls
   `anchor_reads.prepare()` on **that worker**. This reads the frame, verifies
   inode/path/hash and runs the native Python finiteness scan. A precompute follows.
5. Independently, the async receipt route reads the committed receipt, constructs
   `web.Response`, records `first_served`, and returns it. The client reads this
   response and submits its successor.

See 119 `integration.py` lines 578–592 and 2250–2272, `session.py` lines 457–482,
`stream_schedule.py` lines 81–88, and `stream_receipts.py` lines 181–195. The
response route contains **no** call to `prepare()`. Read-ahead starts after the
receipt is committed, whereas the client's receipt bucket ends before commit.
It therefore cannot directly account for the +0.09 s in that bucket. CPU thread,
GIL and I/O contention can still affect later HTTP progress; this is distinct
from running the read synchronously inside the HTTP handler.

119's median request-after snapshot is **0.142341 s**, versus **0.061681 s**
for dg0: +0.080660 s. The receipt bucket rises +0.079052 s in the paired sample.
This is a much closer attribution than the read-ahead hypothesis. All 26 sampled
119 request-after snapshots are dual, versus one periodic dual snapshot in dg0.

No receipt records socket delivery completion. `first_served` means response
construction, not bytes sent. Read-ahead completion relative to that mark is
median +0.000346 s, range −0.023814 to +0.019600 s: either ordering occurs.
Relative to the successor submit, completion is median −0.021180 s; one sample
finishes 0.000521 s after submit. Thus packet 119 has no “after response delivered”
ordering guarantee. Post-commit wake-to-prepare completion is also not a timer
of `read_anchor` alone.

The paired receipt-staged→next-submit turnaround is 0.238434 s dg0, 0.198441 s
dg1 sampler-a, and 0.203445 s in 119. These runs do not show a 0.09 s new
post-commit penalty from read-ahead either. They cannot isolate small contention
costs without a matched on/off arm.

Read-ahead's maximum removable work is the native read/finite scan it replaces.
There is no dedicated timer around that call in 119. A conservative *loose* bound
is the whole first-node→condition-A interval: median 0.123734 s in dg0, including
other work which cannot be removed. 119 measures 0.109437 s there, a difference
of only 0.014297 s across these runs, with other timings and snapshot behavior
changed. This is not a demonstrated read-ahead gain. The previous0–0.06 s
prediction remains a prediction. All 36 anchored 119 chunks in the identity sample
report verified hits; hits do not prove a period benefit.

**Lever B decision:** recommend `LTX_ANCHOR_READ_AHEAD=0` in packet 120's first
replica arm. Retain 119's off and on paths for exact compatibility. Do not add an
HTTP ordering mechanism to chase an unmeasured saving, and do not claim disabling
read-ahead saves the receipt bucket. The lever is dropped from the recommendation.

## Timeline and the actual xpu:3 pressure

The table reconstructs each successor's timeline from its receipt and the
predecessor's decode record. Zero is the successor's sampler-A start. Entries
are medians of recorded boundaries; the JSON contains each individual row.

| Boundary, seconds after sampler-A start | dg0 | dg1 sampler-a | dg1 eager-display 119 |
|---|---:|---:|---:|
| Previous display starts | 0.154 | 0.144 | 0.146 |
| Sampler A ends | 1.788 | 1.756 | 1.774 |
| Upsampler starts | 1.788 | 1.757 | 1.775 |
| Upsampler returned by / condition B starts | 1.822 | 2.261 | 1.810 |
| Sampler B starts | 2.078 | 2.547 | 2.209 |
| Previous display ends | 2.858 | 2.262 | 2.935 |
| Sampler B ends | 3.467 | 3.878 | 3.590 |
| Current cone decode starts | 3.519 | 3.892 | 3.629 |
| Current cone decode ends | 4.461 | 4.656 | 4.394 |

There is no distinct upsampler-end stamp. Condition-B node start is an upper
bound on its return and includes intervening dispatch overhead. `decode_start`
is the cone worker's start boundary, not an individual kernel timestamp.
These are host intervals, not device profiler traces; overlapping intervals do
not establish simultaneous execution of particular kernels.

A source correction is essential: the resident **upsampler is on xpu:0**, not
xpu:3. `stream-preparation.json` and sealed `native_safety.ROLES` both say so.
The native upsampler also uses the video VAE's per-channel statistics and returns
its result to the intermediate device. A host wait in this interval can involve
shared xpu:3 work; the receipts cannot identify the exact synchronization or
queue instruction. The old description of the entire upsampler as resident on
xpu:3 is incorrect.

- **dg0:** display spans sampler A, the short upsampler interval, B conditioning,
  and part of sampler B. Condition B starts about 1.041 s before display ends.
  The cone starts after the previous display finishes.
- **dg1 sampler-a:** display graph execution again overlaps sampler A. The
  upsampler host call does not return until display ends: the median
  display-end minus condition-B-start is −0.001142 s. B conditioning and sampler
  B then run after display. This is the 118b blocking pattern; queue-level cause
  remains unproven.
- **dg1 eager-display 119:** eager display restores dg0's interleaving. The
  upsampler interval is 0.032480 s, effectively the dg0 value. Display continues
  about 1.132 s past condition-B start and overlaps early sampler B. The cone
  still starts after previous display has ended.

Why, then, is 119's combined bucket still 0.144 s higher? B-before and B-after
snapshots are respectively 0.135642 and 0.135447 s, versus 0.059054 and 0.060935 s
in dg0. Their combined increase is 0.151100 s, matching the condition-B increase
of 0.147246 s. The upsampler is already fixed.

The graph cone retains a graph pool while eager display is in flight. At B,
xpu:3 physical free memory is about**9,956,986,880 bytes**, only**293,310,464 bytes**
above the 9GiB pre-request floor. `SnapshotInspector` escalates at a margin of
0.5GiB and keeps dual inspection for the rest of that chunk. Consequently 119
has **26/26 dual B-before, B-after and request-after** snapshots; both 118b
samples have only 1/26 at those sites, their scheduled periodic check. The dual
walk is real safety work and must remain. Do not defeat it by lowering the
threshold, retaining stale readings, skipping a walk or changing host memory.

This also explains why eager display with an eager cone does not incur the same
cost: it has no retained cone graph pool pushing the in-flight display within
the near-floor band. The pool reports3,430,940,672 bytes of reserved growth in 119.
The1,000,000,000-byte cap is a soft first-capture admission limit, not a hard
maximum; the first capture can exceed it.

## Replica census and packet 120 gate

The xpu:2 premise needs correction too. Its preparation receipt says
**12,709,556,224 bytes free**, not 12.5GB used. Allocated is 17,773,215,232 bytes,
reserved 20,252,196,864, recorded peak 19,405,864,448. The 2GiB floor leaves
**10,562,072,576 bytes** of physical headroom for additional work.

The unchanged video-VAE safetensors header gives:

| Stored payload | Bytes |
|---|---:|
| Decoder tensors | 834,267,488 |
| Encoder tensors | 637,873,794 |
| Per-channel statistics | 512 |
| Whole video VAE | 1,472,141,794 |

This is a stored-weight census, not a measurement of the replica's final
allocator footprint. Clone only the needed decoder and necessary normalization
state; do not copy the encoder, active graph wrapper, captured storage or cached
bindings. Preserve arithmetic, precision, input shapes and output conversion.
Use no graph pool on the xpu:2 replica. The xpu:3 graph remains separately counted.

For the 121-frame dg0 receipts, xpu:3 peak allocated 17,624,276,480 minus minimum
observed idle allocated15,219,862,016 is**2,404,414,464 bytes** (2.239GiB).
The corresponding 119 envelope is 2,157,868,032 bytes. Mature dg0 reserved minus
preparation reserved is**2,751,463,424 bytes** (2.5625GiB). These are conservative
observed aggregate envelopes including other work, **not isolated decode
transient measurements or proven upper bounds**. A 4GiB transient admission
allowance exceeds both observed envelopes by more than 1GiB and leaves roughly
5.43GB headroom after decoder weights and the2GiB floor; actual residency and
physical free must still be checked at runtime. Scene-change text work shares
xpu:2 and may change the peak. No extrapolation of these envelopes establishes
safe 121-frame native execution.

One decode worker remains appropriate: the recorded previous display finishes
before the next cone, so the current evidence does not identify a decode FIFO
bottleneck requiring a second worker. Moving only display kernels to another
card can remove xpu:3 contention and memory pressure without concurrent access
to shared decoder caches. A second worker would need new ownership, queue and
peak-memory proofs; no measured benefit justifies it here.

Cross-card bit identity cannot be proven with CPU evidence. The candidate is
therefore off by default and must qualify the complete xpu:2 display output
against uncached eager xpu:3 display on every chunk of the eager, graph and repeat
qualification chains. Compare the full frame bytes, not only the anchor. Keep
latent, waveform, conditioning and repeat gates. During streaming, the existing
per-chunk display-last-frame == cone-anchor check becomes a cross-card check;
any mismatch latches. This detects an anchor mismatch on every chunk but does
not replace full-frame qualification. Allocator, source/weight identity,
residency, floor and no-new-capture checks also remain mandatory.

## Net decisions and estimates

- Graph cone: confirmed chain saving about 0.19 s against dg0; retain.
- Eager display: restores the short upsampler interval, but retaining the graph
  pool makes the existing safety inspector perform extra work.119 as a complete
  configuration loses about 0.14 s in the owner's broader sample.
- Read-ahead: hits are exact; no isolated or convincing net speed benefit.
  Remove it from the first recommendation, without attributing receipt savings.
- Replica on xpu:2: unqualified candidate. It can plausibly recover the roughly
  0.22–0.24 s of extra B/request-after inspections by relieving xpu:3 pressure,
  while preserving those inspections whenever a floor is approached. The aim
  is to avoid the triggering memory condition, not suppress its safety response.
- Extra display splitting or upsampler-first scheduling: do not add it solely
  to fix 119's already-short upsampler. Delaying display may move delay into the
  next cone's FIFO. The evidence supports the replica as the larger next lever;
  scheduling changes would confound its comparison.

At 121 frames, a first replica-arm period of **5.10–5.40 s**, central about 5.22 s,
is a planning estimate from 119 minus the observed extra inspection cost with
allowance for cross-card scheduling and replica guard overhead. A conservative
5.35–5.70 s outcome allows for text-card contention and candidate guard overhead
that offsets the expected saving. These are not measured results. No sub-real-time claim is justified:
121/24=5.041667 s nominal duration and anchored chunks add only 120 new frames,
so keeping up with new video needs a period below 5.0 s.

Still open: native xpu:2 full-frame exactness, actual replica peak/reserve, whether
xpu:3 margins stay above the dual threshold, text-turn interference, and a fresh
matched speed repeat. No CPU test can close these device-dependent questions.
