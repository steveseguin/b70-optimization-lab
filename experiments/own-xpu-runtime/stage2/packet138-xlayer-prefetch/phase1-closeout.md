# Packet138 cross-layer expert prediction — phase-1 closeout

<!-- campaign-closeout -->

## Question and identity

Can an unchanged next-layer router predict enough missing experts to justify
one-card prefetch with an 18,000,000,000-byte global LRU cache? This October 18,
2026 phase-1 arm uses the quantized compressed Flash-Next model and unchanged
`iq3-p49-split32-v1` arithmetic. The coordinator captured the first 48 accepted
tokens of all twelve packet55 held-out test prompts on lane B, physical cards
2+3, plus a separate packet49 sanity prompt. Cache outcomes are CPU projections
for one card, not two-card timing presented as one-card measurement.

The five predictors are the current router input and each of the four current
layer output residual streams. All use the next layer's original F32 router
weights read from the pinned GGUF, exact production arithmetic, and widths
10, 12 and 16. No fitting or benchmark prompt selection occurs.

## Outcome

**Closed for phase-2 design under the registered gain and traffic gate.** Every
candidate loses time in the conservative and middle scenarios. Optimistic
router-input cases project a gain, but no candidate clears +3% throughout the
registered range with every charged copy fitting its causal window. The full
ranges, miss bytes and traffic appear in [RESULTS.md](RESULTS.md).

The best case is router input, width 12, optimistic assumptions: +5.750%, or
30.536 projected tok/s versus the modeled 28.876 control. Its zero-copy reads
fall from 97.026 to 64.681 MB/token, but it submits 66.106 MB/token of prefetch,
including 42.039 MB/token not used by the immediately predicted next layer.
Even this case has 248 late batches out of 9,217. **None of the 45 cases fits
every copy within its assumed layer window**, including the optimistic cases.
Width 12 spans -16.35% to +5.75% gain across the full timing range.

This is a decision about this phase-1 arm and its assumptions. It is not a
measured device slowdown or proof that all cross-layer prediction is unhelpful.
No prefetch device implementation was built or launched. The measured one-card
record remains 26.228599 tok/s; no new speed is promoted.

All 624 captured output tokens match their pinned references. The 48 sanity
tokens also match packet49's CPU oracle; the other 576 use packet55's saved
target references and do not become independent CPU-oracle certifications.
Same-layer replay matches 14,155,776 BF16 logits and 276,480 expert IDs exactly.
Those checks qualify the diagnostic capture and router replay, not a future
prefetch implementation's device exactness.

## What worked

The router-input predictor recalls 66.47%, 72.46% and 79.93% of the true experts
at widths 10, 12 and 16. Raw residual stream 3 is the best residual predictor,
at 53.84%, 59.21% and 66.89%. Full per-layer and per-class evidence is retained.

The original 100b capture design, oracle binding, native limit checks, closed
launch environment and cooperative drain worked on the coordinator's capture.
All 26 raw rank files fit inside the 1 GB output bound. The CPU cache model
matches the frozen 58v allocator's offsets, bytes and eviction order in 150
randomized cases. Fresh GNU/Intel router repeats agree, and the full-size layout
test validates every rank, layer, token and predictor input.

## What failed or remains uncertain

Recall alone is insufficient: correct guesses often name experts already in
the cache, while wrong misses consume copy time and cache space. Predictor,
publication, planning and late-copy costs are all charged. The conservative
window cannot hide even one complete expert copy under its registered bandwidth
and overhead assumptions. Wider predictions do not guarantee faster generation.

The 58g/58p receipts have no measured per-layer clocks. Windows use registered
fractions of the measured aggregate remainder, with explicit bandwidth and
overhead sensitivities. The 58v control rate is modeled from 58p; it is not a
measured 58v result. Remote-read penalties come from historical K1 proxies.
Overflow is charged serially as a conservative assumption as well as retaining
late zero-copy reads. Historical packet55 prefill initializes both caches and is
not a newly measured one-card hit-rate trace. Positive candidates are rechecked
with shorter decode windows; prefill timing is unchanged.

The coordinator released this capture cleanly. The CPU preparer did not start
or queue device work, change host settings, or signal another task's processes.

## Evidence and patches

- [Preregistration and chronological work note](../../../../notes/2026-10-18-own-runtime-packet138.md)
- [Capture readiness and proposal identity](READY-FOR-DEVICE.json)
- [Capture hashes and exactness scope](evidence/capture-inputs.json)
- [Exact replay and per-prompt/layer recall](evidence/router-replay.json.gz)
- [Retained complete predictions](evidence/predictions.json.gz)
- [Cache projections and assumptions](evidence/cache-projections.json.gz)
- [CPU continuation receipt](evidence/continuation.json)
- [Analysis method, source identity and literature credit](ANALYSIS.md)
- [Retention and restoration](RETENTION.md)

The raw `evidence/capture-B/` bytes remain locally retained and Git-ignored;
their tracked hash manifest is not a substitute for those bytes. All source,
input authority links, native checks and CPU analysis code are in this packet.
Earlier packet trees and shared orchestration were not edited by this task.

## When to revisit

Reopen only with new evidence that changes the cost or traffic constraint:
measured causal layer windows and predictor/copy costs, or a separately
preregistered CPU admission/cache policy that avoids the failed traffic and
pollution behavior. Reuse the retained capture and prediction lists where
applicable. Require the same +3% and per-layer traffic gate before phase-2 device
design; high recall or one favorable projected rate alone is insufficient.
