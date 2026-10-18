# Packet88: miss-path attribution

CPU analysis, October 18 UTC / October 17 Toronto, 2026. **No new mechanism
is supported strongly enough to build in this packet.** The suggested overlap
already exists; the corrected half cannot reuse the wrong token's activations.
This is an attribution closeout, not a speed or quality qualification.

## Identity and reproducibility

The inputs are packet77's frozen paired lane-B screen of packet70 wide64,
draft-HC, batched rollback, 24/24 target layers and rank-1 draft. Target
arithmetic is `iq3-p49-split32-v1`, packet49 is the oracle, and KV is BF16.
Packet84's bundle sources are the prospective implementation parent; they were
read, not edited or copied into a candidate. Packet84 also includes independent
host/kernel choices, so packet77 times are not packet84 measurements.

[attribute.py](attribute.py) reads the twelve `control/*/receipt.json` files,
their paired `attribution` receipts, rank-0 `timings.jsonl`, `sites.jsonl` and
`speculative-snapshot.json` under
[the packet77 run](../screen/v4-lanes/evidence/packet77-attribution-B-a/run/).
[attribution.json](attribution.json) records their hashes and the source hashes.
It checks the saved packet49 oracle passes, paired tokens and identities,
zero cached tokens, 128 outputs, and the 24/24 placement. These checks validate
existing evidence, not a new model run.

```sh
nice -n 19 taskset -c 8-15,24-31 python3 -B \
  experiments/own-xpu-runtime/stage2/packet88-miss-path/attribute.py --check </dev/null
```

The first 99 emission intervals per prompt reproduce packet85 exactly:
1,188 intervals, 936 hits, 252 misses (21.212% pooled). Packet85's sensitivity
uses 21.260% misses from median acceptance, hence the brief's about 21.3%.
Command joins use rank, operation, position and speculative flag, never trace
list order. A is the next speculative half; C is correction of the current
miss. Every analyzed miss has different speculative and corrected token IDs.

## C versus A: what can actually be separated

Uninstrumented first-99 means, milliseconds:

| Host clock accounting | A: speculative (1,188) | C: corrected (252) |
| --- | ---: | ---: |
| Complete command | 13.688277 | 12.655226 |
| Outside the half's inner busy timer | 0.646706 | 0.032564 |
| Inner busy timer | 13.041571 | 12.622662 |
| Token preparation | 0.106105 | 0.105857 |
| Enqueue loop, subtracting waits inside that loop | 3.173793 | 3.157025 |
| Recorded host waits | 9.513017 | 9.123931 |
| Signed inner remainder after the three preceding buckets | 0.248656 | 0.235848 |

Both issue 708 logical launches on every analyzed half, without cancellation.
The host rows are **not a CPU/GPU partition**: device execution overlaps host
enqueue, and waits during token preparation are also inside its timer. The
signed remainder makes the arithmetic reconcile but is not an independently
timed phase or an idle-time budget. Control `gpu_ms` is zero because this
control does not collect those timings; it does not mean the GPU did no work.

The 1.033051 ms A-minus-C difference splits algebraically into 0.614142 ms
outside the inner timer and 0.418909 ms inside it. Source explains the extra
speculative work: `image.begin(shared)` drains, saves host metadata and the
65,536-byte shared slot, enumerates written extents, uploads the copy table
and captures the target write set. It happens before the inner timer.
Speculation also checks cancellation and executes with rank1's target half;
C overlaps the shorter draft instead. Position admission, event retirement,
different tokens/routes, execution overlap and capture completion affect the
timers. **Neither difference isolates snapshot device copy time.** C already
skips `image.begin`; it has no capture to remove a second time.

The independent, instrumented sample supplies a useful device split:

| Complete sampled halves | A (96) | C (20) |
| --- | ---: | ---: |
| Same commands in uninstrumented arm, ms | 13.606557 | 12.587212 |
| Instrumented command, ms | 14.237609 | 13.224988 |
| First layer start to final layer end on rank0, ms | 12.168773 | 12.157776 |
| Instrumented command minus layer span, ms | 2.068836 | 1.067212 |

That device span includes inter-kernel gaps. It is not a sum of kernel execution
times. The outside span includes preparation, observation, handoff and other
host work; it is not all removable overhead. These 20 sampled corrections
cannot be substituted into the 252-correction mean of 12.655226 ms.

Packet77 samples layers 22 (GDN) and 23 (QSA). Summing stages within each site,
taking its median, then multiplying by 18 GDN / 6 QSA occurrences gives this
**estimated**, instrumented class breakdown for C:

| Class | Estimated ms per half |
| --- | ---: |
| GDN projections, convolution, recurrence and gating | 2.883762 |
| Expert gate/up and down | 2.729367 |
| HC gates, norms and mixing | 2.142804 |
| Attention output projection | 1.120929 |
| QSA projections, preparation, pooling, selection and attention | 1.056564 |
| Router and route selection | 1.000923 |
| Combining and expert activation | 0.550941 |
| Shared expert activation and down | 0.364383 |
| Sum of these estimates | 11.849673 |

These are not measured times for all 24 layers and must not be subtracted from
12.655226 to invent a launch-overhead measurement. Per-site calls, counts and
both speculative/corrected samples remain in the JSON. For example GDN
recurrence is 35.834 microseconds per sampled corrected call versus 35.833
speculative; expert gate/up is 61.458 versus 61.355. The source and samples
show ordinary target work, not a distinct cheap corrected kernel family.

## What depends on the wrong guess

`rank.hpp::half_step` uses the same target plan on both paths. Correction sets
the verified token, calls `prepare_token`, runs the target launches and reads
back the resulting streams. It commits only after the unchanged verifier's
decision. Static weights, prepared command bindings and committed history are
already resident or retained; reusing those is existing behavior.

| Work/state | Dependence and reuse decision |
| --- | --- |
| Embedding lookup | The row index is the token ID. On a miss the corrected token is different. The speculative embedding is not reusable. Coincidental row equality is no general proof. |
| PLE lookups | `prepare_token` hashes the current token with the prior one/two tokens, including EOS handling. The prior history agrees after rollback, but the current-token term changes. Individual hash collisions do not justify general reuse. |
| First HC norm/gates and attention projections | They consume streams derived from the new embedding/PLE inputs. There is no complete token-independent first layer to retain. |
| GDN/conv state | The committed active bank is a valid shared input and already preserved. New convolution values, gates and recurrent output depend on the corrected activation. Spare-bank results from the wrong token cannot become the corrected state. |
| QSA | Historical committed KV is already retained. Current Q/K/V, selection queries, appended rows and attention output depend on the token. Position/RoPE constants alone do not make the activation calculation reusable. |
| Router, routed experts, shared expert, HC and FFN combine | Routes and operands depend on incoming activations. Even equal expert IDs do not establish equal inputs. Every later layer inherits that dependence. |
| Position and prepared launch metadata | Position/shape can agree, but these are already cached. Context-boundary rollback restores both prepared banks and their extents; skipping this needs a separate observable-state proof. |
| Target output/state | No speculative output, response, or extra KV reuse is introduced. Every canonical state byte and metadata field remains observable. |

This does not claim every output bit must differ for every pair of tokens.
It says no unchanged-input subgraph covering a target layer is proved by the
miss condition or these receipts. The embedding of the *corrected* token was
not computed by A. Borrowing rank1 draft activations would be a different
cross-rank ownership/transfer mechanism, not reuse of A, and is not supported
by a measured benefit here.

## R: copies, bytes, and the missing device timer

Every observed redo copies **19,025,640 payload bytes** back from the private
image to rank0 target allocations. Every speculative capture copies
**48,627,432 bytes** into that image. The difference is **29,601,792 bytes**
of proved GDN/conv spare-bank writes already omitted on confirmed redo.
The counters are cumulative across the paired screen, including incident64;
they are checked as cumulative ratios, never summed as per-request counts.
All saved snapshots have two capture submissions per capture and two restore
submissions per restore: **one descriptor-table upload plus one flat copy
compute kernel**. There are no abandoned redos in these performance receipts.

The standalone split follows the production allocation and scratch-write
formulas; the plan-buffer remainder is reconciled to the raw total:

| Restored allocation group | Payload bytes |
| --- | ---: |
| GEMV workspace | 8,388,608 |
| Nonbank plan buffers (remainder, not separately timed) | 6,948,692 |
| Operator scratch written span | 1,609,936 |
| Layer snapshots | 983,040 |
| FP32 input | 696,320 |
| Attention scores | 196,896 |
| Attention probabilities | 196,896 |
| Ordered mixture | 5,120 |
| Compact routes | 120 |
| Parallel controls | 12 |
| Total | 19,025,640 |

Payload bytes count the copied extent once, not both its device read and write.
The descriptor upload and host metadata copies are additional. Host restoration
includes the 65,536-byte rank0 shared slot, history, lookup IDs, expert selection,
loaded-layer and FP32-source metadata, bank parity and both launch extents.
No per-extent device times or raw descriptor-table byte count were saved.

**The flat copy kernel's device time is unknown.** `strict_snapshot.hpp::copy`
submits `SnapshotFlat` directly via `e.dev(0).compute`, without registering that
event in `Engine::pending` or the attribution recorder. Packet77's 60 sampled
rollback transfer events all have zero-width timestamps; these describe
upload/readback wrappers, not a separately timed flat restore kernel. They
cannot establish a zero-time upload, copy bandwidth, or host/device split.
R = 0.569390 ms is the whole rollback command: validation, drains, copy setup,
upload, flat kernel completion and metadata restoration.

## Mechanism decisions

1. **Overlap R with D: already present.** Across all 252 misses, mean R/D
   overlap is 0.569325 ms out of R's 0.569390 ms. Their starts differ by only
   0.000013 ms on average; sub-microsecond start order explains the uncovered
   sliver. The controller issues rank1 draft asynchronously before rank0
   rollback. Moving rank0 copies onto BCS cannot create this cross-card
   overlap. C needs restored state, so its R→C dependency remains. A faster
   R would still help: R+C exceeds D, so existing overlap does not hide R
   from the miss critical path. A different
   copy transport is conceivable, but no isolated copy measurement here
   supports predicting that many BCS transfers beat the current one-kernel
   batch. No BCS performance claim or candidate is made.
2. **Skip more restore bytes: no new proof.** Packet45 SPEED4 already skips
   complete spare-bank overwrites, and packet64/70 already batch the remaining
   copies. Scratch tails, canonical plan buffers and terminal metadata remain
   observable. A matching confirmed redo may omit only fully proved writes;
   cancelled/abandoned redo must restore deferred bytes before dump/reset/end
   or any other observer. Existing packet45 negative controls reject omitted
   stream state. Private buffering would need a new write-range, tail and
   ownership proof; the receipts do not supply it.
3. **Reuse A inside C: no valid activation reuse found.** The table above
   accounts for embedding through final rank0 state. Static reuse already
   exists. No masked hashes, changed arithmetic, speculative output reuse,
   response reuse or compressed cache is acceptable.
4. **Corrected-half launch/setup: insufficient exposed saving.** The measured
   0.105857 ms preparation includes necessary token/PLE work and transfers.
   Removing even all of it would save only about 0.12% in packet85's model,
   before overlap effects. R-to-C dispatch averages 0.001233 ms (maximum
   0.001954 ms). The 3.157025 ms enqueue loop overlaps GPU work; treating it as
   removable serial delay is invalid. Prepared commands already exist. No
   measured 0.30–1.00 ms C-only launch/setup mechanism emerges.

The +0.46–1.51% budget is conditional on real R/C component savings; it is not
evidence that such a mechanism exists. Existing small-kernel and recurrence
work targets actual arithmetic costs but belongs to those separate packets.
Depth two, draft relocation and draft bytes are not reopened.

## Disposition

Use the brief's **close with attribution** branch. No candidate executable,
selection views, production changes, seals, screen jobs or proposed lane-queue
files are created. CPU byte identity, mock accept/miss state identity and the
full-shape startup gate are **not run / not applicable to an unbuilt candidate**,
not claimed passed. No live queue or shared v4 file changed.

See [closeout](CLOSEOUT.md) for retained evidence and concrete reopening
conditions. The optimization lane remains open; this packet closes only the
unsupported miss-path mechanisms above.
