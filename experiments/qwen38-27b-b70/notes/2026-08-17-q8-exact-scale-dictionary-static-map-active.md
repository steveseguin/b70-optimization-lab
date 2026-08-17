# Qwen3.8 Q8 exact-scale dictionary: static-map retry

Date: 2026-08-17  
Status: active; implementation/build not yet measured  
Owner: ASRock 2x B70 reference host

## Hypothesis

The first exact 11-bit scale-plane prototype established that all 840,417,280
Q8 blocks in the pinned Qwen3.8-27B artifact are representable without loss.
Its slow binary-search encoder completed a real TP2 one-token decode, but model
setup took minutes. Two runtime lookup-table revisions then failed the safety
gate: one segfaulted and one reached the first prompt graph before Level Zero
reported an invalid memory object.

This retry removes that failure mechanism rather than repeating it. The half
scale is split into exponent and ten-bit mantissa fields. The model uses:

- 510 exponent-zero patterns; and
- the same 128 mantissas for each normal exponent 1 through 8.

Two compile-time 1,024-entry `uint16_t` maps can therefore encode either field
directly inside the reorder kernel. They require no runtime USM allocation, no
cross-context pointer, and no deferred lifetime. The packed representation and
decode arithmetic remain bit-exact to the already audited codec.

## Bound and gates

The ideal traffic saving remains only 1.838235% of ordinary Q8_0 weights, so a
perfectly scaling result would be about 37.46 tok/s from the accepted 36.773
tok/s baseline. This is an incremental exact optimization, not by itself a
route to 40 tok/s.

Execution order:

1. reconstruct an isolated source from the retained slow revision;
2. replace only the encoder search/allocation with compile-time maps;
3. build with `-j2` under 6 GiB RAM / 8 GiB swap bounds;
4. run `p64/n1` first under 8/10 GiB bounds to exercise prompt and decode;
5. require zero Xe/GuC fault/reset/hang and exact output before any speed test;
6. only then run a same-binary codec-off/on position-balanced bracket.

Do not touch the accepted source or binaries. If prompt processing again
fails, close the format as incompatible with an unmodified secondary matrix
path and do not attempt another device-table revision.
