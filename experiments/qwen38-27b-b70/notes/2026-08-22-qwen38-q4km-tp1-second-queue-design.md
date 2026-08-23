# TP1 second-queue quantize-overlap: design and preregistration

Date: 2026-08-22

Status: **design owned; implementation deliberately deferred to a reviewed
arc.** This note sizes the opportunity, states the exact mechanism, and
freezes the gates. It does not authorize a hasty edit to the
submission-ready lane.

## Why this is the live TP1 rung

The [z-row cold verdict](2026-08-22-qwen38-q4km-tp1-zrow-cold-verdict.md)
established that the mid-size MMVQ rows are NOT kernel-geometry bound: the
`[6144,5120]` z kernel streams at 536.7 GB/s cold (shared, memo-deduped
activation) but shows 87.7 us/call in-graph vs 62.4 us/call cold - a
~25 us per-call tax that is per-activation Q8_1 quantize plus in-order
dispatch gap. The decode profile counts ~240 residual quantize launches
per 64-layer graph after dedup. Summed across the distinct-activation
rows this is the ~2-3 ms/token pool - the bulk of the 27.82 -> 30+ gap,
and the largest uncommitted decode lever on the bench.

Producer-side Q8 emission (fuse the quantize into the upstream kernel)
was already rejected for exactness: icpx `fp-model=fast` per-TU codegen
divergence makes byte-identical cross-TU quantizer replication
impossible (`q8out-rejected` note). So the quantize must remain its own
kernel launch; the only remaining lever is to stop paying for it on the
critical path.

## Mechanism

Today (`ggml-sycl.cpp` ~4342): one in-order `stream` runs
`quantize_row_q8_1_sycl(src1_ddf -> src1_ddq)` then the consuming GEMV,
serially, per node. Distinct activations serialize quantize-then-GEMV.

Overlap: run node N+1's activation quantize on a SECOND queue concurrently
with node N's GEMV on the main queue; the main queue waits on a SYCL event
before node N+1's GEMV reads the buffer. Same quantize kernel, same
inputs -> byte-identical output; the event enforces the consumer ordering,
so correctness is preserved and the win is the hidden quantize time.

Ceiling: quantize cost is < GEMV cost for every mid-size row, so a perfect
overlap hides essentially all ~25 us/call of tax -> ~2-3 ms/token ->
roughly +12 to +15% at the 27.82 operating point (~31-32 tok/s), the
first credible path past 30/GPU.

## Why it is NOT a quick edit (owned assessment)

The per-node dispatch (`ggml_sycl_op_mul_mat`) has no lookahead: it sees
one node. Overlap needs (1) graph-level knowledge of the next consumer's
activation, (2) a second `sycl::queue`, (3) cross-queue event plumbing,
(4) lifetime management of the second queue's output buffers across the
node boundary, and (5) interaction with the memo (a prefetched quantize
must land in the same memo slot the consumer looks up). That is a new
scheduling subsystem. The lane's code standard says prefer the simpler
change and avoid invasive subsystems that risk existing behavior; this
lane also carries the only 24/24 bit-exact, quality-battery-passed,
submission-ready result (27.813629/27.824790). Landing this wrong wedges
a GPU or silently breaks exactness. It is worth doing - under review, not
in an unattended edit.

## Preregistered gates (frozen before any implementation)

1. **Default off.** New door `GGML_SYCL_Q8_QUANT_PREFETCH` (0 default).
   Off must be byte-identical to today's binary path (a no-op door test,
   same pattern as the accepted fusion doors).
2. **Bit-exact.** With the door on, the full cold 12-prompt suite must
   produce 24/24 output hashes identical to the registered oracle
   (`2026-08-21-q4km-tp1-gpu0-final-*.json`). One mismatch rejects the
   door, permanently, like Q8OUT.
3. **Race-clean.** A preregistered stress arm (repeated decode, varied
   batch) under the door must be hash-stable across >=8 runs and show no
   device error; a poison-control (deliberately drop the event wait) must
   go red, proving the gate can see a missing dependency.
4. **Win threshold.** Conventional median must improve by a bootstrap
   95%-lower-bound > +2% over the 27.82 baseline on two fresh cold
   suites, or the complexity is not justified and the door is rejected.
5. **Mechanism counter.** A prefetch-hit counter must show the overlap
   actually engaged (nonzero, matching the distinct-activation count);
   a source symbol without runtime engagement is not a pass.

## Cheap kill-check to run first

Before writing the subsystem: confirm the residual quantize launches are
genuinely distinct activations (irreducible) and not memo policy misses.
The `[Q8-DEDUP]` counters (`g_q8_quant_launches` vs `g_q8_dedup_hits`) in
a normal decode already report this; if a large fraction of the 240 are
policy-evictable, a memo-policy tweak is the simpler 90% change and this
subsystem is unnecessary. That check gates whether the arc proceeds.

## Kill-check RESULT (2026-08-22): irreducible; arc justified

Ran a normal GPU0 decode on the promoted TP1 build (100 tokens, door set
as promoted, `GGML_SYCL_QDEDUP_STATS=1`). `[Q8-DEDUP]` over 103 graphs:
`quantize_launches=24631` (239.1/graph), `dedup_hits=26064` (253.0/graph),
`bypass=0`. The memo already removes 51.4% of would-be quantizes and had
ZERO capacity/OOM misses, so the residual ~239 launches/graph are
genuinely distinct activations with no prior identical quantize to reuse.
The simpler memo-policy-tweak alternative is therefore DEAD - there are
no policy misses left to recover. The only lever that removes this tax
from the critical path is overlapping the (irreducible) quantizes, i.e.
the second-queue design above. Arc confirmed justified.

## Feasibility finding (2026-08-22)

`ggml_backend_sycl_context::qptrs[dev][stream]` every entry resolves to
`dpct::get_device(dev).default_queue()` - the multi-stream array is
vestigial; all indices alias ONE queue. So there is no existing
concurrent queue to reuse: the overlap requires a genuinely new
`sycl::queue` (lifetime + events = new subsystem, not infra reuse).
Further, a lookahead-free version (quantize on q2, main queue waits
immediately) serializes and wins nothing; the win requires graph-level
lookahead to quantize node N+1 while node N's GEMV runs. That is a
multi-session, correctness-critical restructuring, and a bad cross-queue
dependency can hang the device (recovery needs sudo). It is the right
work, but supervised - not a single-turn autonomous edit on the
submission-ready lane.

## Disposition

Opportunity real, large, and now confirmed irreducible by the cheap
kill-check. Implementation is a reviewed future arc behind the five
frozen gates, on a scratch build, never on the promoted binary until all
gates pass. Not implemented autonomously against the submission-ready
lane. This is the largest remaining decode-tok/s lever on the bench.

**CLOSED 2026-08-23:** the arc ran under supervision and the candidate was
rejected at the win gate with a hardware root cause - the B70 has a single
compute command streamer, so a second queue cannot overlap compute at all.
See [the closure note](2026-08-23-qwen38-q4km-tp1-second-queue-closure.md).
